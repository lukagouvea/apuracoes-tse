"""Independent totals and BU timestamp provenance; never infer time from ZIP dates."""
import csv
import io
import json
import zipfile
from pathlib import Path
import pandas as pd
from .data import SECTION, normalize_chunk
from .download import atomic_json, sha256
from .experiment import audit_order


def check_summary(root,year):
    root=Path(root); out=root/'processed'/str(year)
    prep=json.loads((out/'preparation.json').read_text())
    totals={prep['candidate_a']:0,prep['candidate_b']:0}
    files=list((root/'raw'/str(year)/'summary').glob('*.zip'))
    if not files: return {'status':'unverified','reason':'No independent summary resource'}
    with zipfile.ZipFile(files[0]) as z:
        # BRASIL is the federal presidential table, not a duplicate of the state office files.
        members=[n for n in z.namelist() if 'BRASIL' in n.upper() and n.lower().endswith('.csv')]
        if len(members)!=1: raise ValueError(f'Expected one BRASIL summary table, found {members}')
        with z.open(members[0]) as raw:
            for f in pd.read_csv(raw,sep=';',encoding='latin1',dtype=str,keep_default_na=False,chunksize=250_000,usecols=['CD_CARGO','NR_TURNO','NR_CANDIDATO','QT_VOTOS_NOMINAIS']):
                f=f[f.CD_CARGO.eq('1') & f.NR_TURNO.eq('2')]
                for c in totals:
                    totals[c]+=int(pd.to_numeric(f.loc[f.NR_CANDIDATO.eq(c),'QT_VOTOS_NOMINAIS']).sum())
    expected={prep['candidate_a']:prep['votes_a'],prep['candidate_b']:prep['votes_b']}
    report={'year':year,'status':'matched' if totals==expected else 'mismatch','official_totals':totals,'section_totals':expected,
        'source':str(files[0].relative_to(root)),'source_sha256':sha256(files[0]),
        'difference':{c:expected[c]-totals[c] for c in totals}}
    atomic_json(out/'totals-check.json',report)
    return report


def extract_bu_order(root,year):
    root=Path(root); out=root/'processed'/str(year)
    universe=pd.read_parquet(out/'sections.parquet',columns=SECTION)
    zips=sorted((root/'raw'/str(year)/'bu').glob('*.zip'))
    if not zips:
        r={'year':year,'usable':False,'status':'missing_bu','timestamp_meaning':None,'source_manifests':[]}
        atomic_json(out/'chronology.json',r); return r
    rows=[]; provenance=[]; seen_fields=set(); conflicts=0; invalid=0; unsupported=[]
    for path in zips:
        manifest=root/'manifests'/f'{year}-bu-{path.name}.json'
        if not manifest.exists(): raise ValueError(f'No source manifest for {path}')
        m=json.loads(manifest.read_text())
        if m.get('status')!='complete' or sha256(path)!=m.get('sha256'): raise ValueError(f'Invalid provenance for {path}')
        provenance.append({'manifest':str(manifest.relative_to(root)),'sha256':m['sha256'],'url':m['url']})
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if not n.lower().endswith(('.csv','.txt')): continue
                with z.open(n) as raw:
                    header=next(csv.reader([raw.readline().decode('latin1')],delimiter=';'))
                # DT_RECEBIMENTO_BU carries the full date/time in modern BU archives.
                time_field=next((c for c in ['DT_BU_RECEBIDO','DT_RECEBIMENTO_BU'] if c in header),None)
                if time_field is None:
                    seen_fields.update(c for c in header if 'DT_' in c or 'HH_' in c)
                    unsupported.append(n); continue
                needed=['SG_UF','CD_MUNICIPIO','NR_ZONA','NR_SECAO',time_field]
                needed += [c for c in ['NR_TURNO','CD_CARGO_PERGUNTA','HH_RECEBIMENTO_BU'] if c in header]
                with z.open(n) as raw:
                    for f in pd.read_csv(raw,sep=';',encoding='latin1',dtype=str,keep_default_na=False,usecols=needed,chunksize=250_000):
                        if 'NR_TURNO' in f: f=f[f.NR_TURNO.eq('2')]
                        if 'CD_CARGO_PERGUNTA' in f: f=f[f.CD_CARGO_PERGUNTA.eq('1')]
                        f=f.rename(columns={'SG_UF':'uf','CD_MUNICIPIO':'municipality','NR_ZONA':'zone','NR_SECAO':'section',time_field:'timestamp'})
                        for c,w in [('municipality',5),('zone',4),('section',4)]: f[c]=f[c].str.strip().str.zfill(w)
                        if 'HH_RECEBIMENTO_BU' in f: f['timestamp']=f.timestamp+' '+f.HH_RECEBIMENTO_BU
                        f=f[SECTION+['timestamp']].drop_duplicates()
                        rows.append(f)
    if not rows:
        r={'year':year,'usable':False,'status':'no_reception_timestamp','available_time_fields':sorted(seen_fields),
            'timestamp_meaning':None,'source_manifests':provenance,'members_without_verified_receipt_field':unsupported}
        atomic_json(out/'chronology.json',r); return r
    order=pd.concat(rows,ignore_index=True).drop_duplicates()
    conflicts=int(order.duplicated(SECTION,keep=False).sum())
    # Multiple identical per-candidate timestamps are expected; different timestamps are not silently resolved.
    iso=order.timestamp.str.match(r'^\d{4}-')
    parsed=pd.Series(pd.NaT,index=order.index,dtype='datetime64[ns]')
    parsed.loc[iso]=pd.to_datetime(order.loc[iso,'timestamp'],dayfirst=False,errors='coerce',format='mixed')
    parsed.loc[~iso]=pd.to_datetime(order.loc[~iso,'timestamp'],dayfirst=True,errors='coerce',format='mixed')
    order['timestamp']=parsed
    invalid=int(order.timestamp.isna().sum())
    order=order.drop_duplicates()
    report=audit_order(universe,order,'reception')
    report.update(year=year,status='audited',conflicting_section_records=conflicts,invalid_source_timestamps=invalid,source_manifests=provenance)
    if conflicts or invalid: report['usable']=False
    order.to_parquet(out/'order.parquet',index=False,compression='zstd')
    report['order_sha256']=sha256(out/'order.parquet')
    report['universe_sha256']=sha256(out/'universe.parquet') if (out/'universe.parquet').exists() else None
    atomic_json(out/'chronology.json',report)
    return report


def audit_all(root,years):
    root=Path(root); rows=[]
    for year in years:
        out=root/'processed'/str(year)
        if not (out/'sections.parquet').exists():
            rows.append({'year':year,'status':'missing_prepared_data'}); continue
        totals=check_summary(root,year)
        chronology=None
        if list((root/'raw'/str(year)/'detail').glob('*.zip')):
            from .timing import extract_detail_order
            candidate=extract_detail_order(root,year)
            if candidate.get('status')=='audited_first_totalization':chronology=candidate
        if chronology is None:chronology=extract_bu_order(root,year)
        r={'year':year,'totals':totals,'chronology':chronology}
        rows.append(r)
        print(f'audited {year}: totals={totals["status"]}, historical_order={chronology["usable"]}',flush=True)
    atomic_json(root/'manifests'/'audit.json',rows)
    return rows
