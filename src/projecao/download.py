"""Official CKAN discovery, conservative disk checks and atomic ZIP downloads."""
import hashlib
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

YEARS=(2006,2010,2014,2018,2022,2026)
API='https://dadosabertos.tse.jus.br/api/3/action/'
GIB=1024**3


def session():
    s=requests.Session()
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
    return s


def atomic_json(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''): h.update(block)
    return h.hexdigest()


def ensure_space(path, incoming, reserve=10*GIB):
    free=shutil.disk_usage(path).free
    if free-incoming<reserve:
        raise OSError(f'Insufficient space: {free/GIB:.2f} GiB free, incoming {incoming/GIB:.2f} GiB; reserve {reserve/GIB:.0f} GiB')


def select_resources(resources, kind):
    def selected(r):
        u=r.get('url','').lower(); name=r.get('name','').lower()
        if kind=='votes': return 'votacao_secao_' in u and '_br.zip' in u and 'detalhe' not in u
        if kind=='detail': return 'detalhe_votacao_secao_' in u and u.endswith('.zip')
        if kind=='summary': return 'votacao_candidato_munzona_' in u and u.endswith('.zip')
        if kind=='totals': return 'historico_totalizacao_presidente' in u and '_2t_' in u
        if kind=='bu': return u.endswith('.zip') and ('bweb_2t_' in u or ('2º turno' in name and 'bweb' in u))
        raise ValueError(f'Unknown resource kind: {kind}')
    return [r for r in resources if selected(r)]


def catalog(root, year, kind='votes', refresh=False):
    name=f'resultados-{year}'+('-boletim-de-urna' if kind=='bu' else '')
    path=Path(root)/'manifests'/f'catalog-{name}.json'
    if path.exists() and not refresh: return json.loads(path.read_text())
    s=session(); response=s.get(API+'package_show',params={'id':name},timeout=60)
    response.raise_for_status(); data=response.json()
    if not data.get('success'): raise RuntimeError(f'Catalog unavailable: {name}: {data.get("error")}')
    atomic_json(path,data)
    return data


def resources_for(root, year, kind):
    return select_resources(catalog(root,year,kind)['result']['resources'],kind)


def download_one(root, year, kind, resource):
    root=Path(root); url=resource['url']
    if urlparse(url).hostname not in {'cdn.tse.jus.br','dadosabertos.tse.jus.br'}:
        raise ValueError(f'Unexpected source host: {url}')
    dest=root/'raw'/str(year)/kind/Path(urlparse(url).path).name
    dest.parent.mkdir(parents=True,exist_ok=True)
    mp=root/'manifests'/f'{year}-{kind}-{dest.name}.json'
    old=json.loads(mp.read_text()) if mp.exists() else {}
    if dest.exists() and old.get('status')=='complete' and sha256(dest)==old.get('sha256'):
        print(f'cached {year} {dest.name}',flush=True); return old
    record={'year':year,'kind':kind,'url':url,'resource_name':resource.get('name'),'resource_id':resource.get('id'), 'path':str(dest.relative_to(root)),'status':'downloading','retrieved_at':datetime.now(timezone.utc).isoformat()}
    atomic_json(mp,record)
    temp=dest.with_suffix(dest.suffix+'.part')
    try:
        with session().get(url,stream=True,timeout=(30,120)) as resp:
            resp.raise_for_status(); size=int(resp.headers.get('Content-Length',0))
            ensure_space(dest.parent,size)
            record.update(expected_bytes=size,etag=resp.headers.get('ETag'),last_modified=resp.headers.get('Last-Modified'))
            atomic_json(mp,record); written=0
            with temp.open('wb') as out:
                for chunk in resp.iter_content(4*1024**2):
                    if chunk:
                        ensure_space(dest.parent,len(chunk)); out.write(chunk); written+=len(chunk)
            if size and not resp.headers.get('Content-Encoding') and written!=size: raise OSError(f'Truncated download: {written}/{size}')
        if not zipfile.is_zipfile(temp): raise ValueError(f'Not a ZIP: {url}')
        # CRC and content checks happen during streaming preparation; avoid decompressing twice here.
        record.update(status='complete',bytes=temp.stat().st_size,sha256=sha256(temp))
        temp.replace(dest); atomic_json(mp,record)
        print(f'downloaded {year} {dest.name}: {record["bytes"]/1024**2:.1f} MiB',flush=True)
        return record
    except Exception as e:
        record.update(status='failed',error=str(e)); atomic_json(mp,record)
        raise


def download(root, years=YEARS, kinds=('votes','totals')):
    failures=[]
    for year in years:
        for kind in kinds:
            try:
                resources=resources_for(root,year,kind)
                if not resources: print(f'unavailable {year} {kind}',flush=True)
                for resource in resources: download_one(root,year,kind,resource)
            except OSError:
                raise
            except Exception as e:
                failures.append({'year':year,'kind':kind,'error':str(e)})
                print(f'failed {year} {kind}: {e}',flush=True)
    atomic_json(Path(root)/'manifests'/'download-failures.json',failures)
    return failures


def storage_estimate(root):
    rows=[]
    for year in YEARS:
        for kind in ('votes','totals','bu'):
            try:
                for r in resources_for(root,year,kind):
                    resp=session().head(r['url'],timeout=45,allow_redirects=True)
                    rows.append({'year':year,'kind':kind,'url':r['url'],'status':resp.status_code,'bytes':int(resp.headers.get('Content-Length',0))})
            except Exception as e: rows.append({'year':year,'kind':kind,'error':str(e)})
    atomic_json(Path(root)/'manifests'/'storage-estimate.json',rows)
    return rows
