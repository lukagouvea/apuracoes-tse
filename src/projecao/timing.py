"""Section-level first-totalization reconstruction from official TSE detail files."""
import csv
import json
import zipfile
from pathlib import Path
import pandas as pd
from .data import SECTION
from .download import atomic_json,sha256
from .experiment import audit_order

FIELDS={'DT_RECEBIMENTO_BU_HOR_TSE':'received_at','DT_PRIM_TOT_PARCIAL_HOR_TSE':'first_totalized_at'}


def extract_detail_order(root,year):
    root=Path(root);out=root/'processed'/str(year)
    archives=sorted((root/'raw'/str(year)/'detail').glob('*.zip'))
    if len(archives)!=1:return {'usable':False,'status':'missing_detail','year':year}
    path=archives[0];mp=root/'manifests'/f'{year}-detail-{path.name}.json'
    manifest=json.loads(mp.read_text())
    if manifest.get('status')!='complete' or sha256(path)!=manifest['sha256']:raise ValueError('Detail source checksum mismatch')
    parts=[]
    with zipfile.ZipFile(path)as z:
        members=[n for n in z.namelist() if n.lower().endswith('.csv')]
        # BR is the federal presidential file; BRASIL/all-UF files can duplicate it.
        national=[n for n in members if n.upper().endswith('_BR.CSV')]
        if national:members=national
        for member in members:
            with z.open(member)as raw:header=next(csv.reader([raw.readline().decode('latin1')],delimiter=';'))
            if not set(FIELDS).issubset(header):continue
            cols=['ANO_ELEICAO','NR_TURNO','CD_CARGO','SG_UF','CD_MUNICIPIO','NR_ZONA','NR_SECAO','QT_VOTOS_NOMINAIS',*FIELDS]
            with z.open(member)as raw:
                for f in pd.read_csv(raw,sep=';',encoding='latin1',dtype=str,keep_default_na=False,usecols=cols,chunksize=250000):
                    f=f[f.ANO_ELEICAO.eq(str(year))&f.NR_TURNO.eq('2')&f.CD_CARGO.eq('1')]
                    if len(f):parts.append(f)
    if not parts:return {'usable':False,'status':'no_detail_timestamp','year':year,'source_url':manifest['url']}
    f=pd.concat(parts,ignore_index=True).rename(columns={**FIELDS,'SG_UF':'uf','CD_MUNICIPIO':'municipality','NR_ZONA':'zone','NR_SECAO':'section'})
    for c,w in [('municipality',5),('zone',4),('section',4)]:f[c]=f[c].str.strip().str.zfill(w)
    f=f[SECTION+['QT_VOTOS_NOMINAIS',*FIELDS.values()]].drop_duplicates()
    if f.duplicated(SECTION).any():raise ValueError('Conflicting detail records for a section')
    for c in FIELDS.values():f[c]=pd.to_datetime(f[c],format='mixed',dayfirst=True,errors='coerce').astype('datetime64[ns]')
    f['detail_nominal']=pd.to_numeric(f.QT_VOTOS_NOMINAIS,errors='raise')
    sections=pd.read_parquet(out/'sections.parquet')
    joined=sections.merge(f[SECTION+['detail_nominal',*FIELDS.values()]],on=SECTION,how='left',validate='one_to_one',indicator=True)
    missing=joined._merge.ne('both')
    mismatches=(~missing)&(joined.detail_nominal.ne(joined.votes_a+joined.votes_b))
    timing=joined[SECTION+list(FIELDS.values())]
    timing.to_parquet(out/'section_timing.parquet',index=False,compression='zstd')
    order=timing[SECTION+['first_totalized_at']].rename(columns={'first_totalized_at':'timestamp'})
    order.to_parquet(out/'order.parquet',index=False,compression='zstd')
    report=audit_order(sections[SECTION],order,'totalization')
    election_day=pd.Timestamp(f'{year}-10-28') if year==2018 else order.timestamp.min().normalize()
    late=order.timestamp>=election_day+pd.Timedelta(days=2)
    report.update(year=year,status='audited_first_totalization',source_time_field='DT_PRIM_TOT_PARCIAL_HOR_TSE',
        reconstructed_from_final_votes=True,exact_published_partials=False,
        missing_detail_sections=int(missing.sum()),nominal_mismatches=int(mismatches.sum()),
        source_sections=len(f),excluded_source_sections=len(f)-int((~missing).sum()),late_sections=int(late.sum()),
        late_votes=int((joined.loc[late,'votes_a']+joined.loc[late,'votes_b']).sum()),
        limitation='Final section votes ordered by first totalization; intermediate corrections and public release delays are not recovered. Late dates are preserved.',
        source_manifests=[{'manifest':str(mp.relative_to(root)),'sha256':manifest['sha256'],'url':manifest['url']}],
        order_sha256=sha256(out/'order.parquet'),universe_sha256=sha256(out/'universe.parquet'),
        timing_sha256=sha256(out/'section_timing.parquet'),sections_sha256=sha256(out/'sections.parquet'))
    if missing.any() or mismatches.any():report['usable']=False
    atomic_json(out/'chronology.json',report)
    return report
