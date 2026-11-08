"""Adapters for official totalization histories, separate from BU reception replay."""
from pathlib import Path
import zipfile
import pandas as pd


def read_totalization(path,year,candidate_a,candidate_b):
    parts=[]
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith('.csv'):continue
            with archive.open(member) as raw:
                f=pd.read_csv(raw,sep=';',encoding='latin1',dtype=str,keep_default_na=False)
            f.columns=f.columns.str.strip()
            for c in f.columns:f[c]=f[c].str.strip()
            parts.append(f)
    if not parts:raise ValueError('History has no CSV files')
    f=pd.concat(parts,ignore_index=True)
    f['timestamp']=pd.to_datetime(f.DT_TOTALIZACAO,format='mixed',dayfirst=True,errors='raise')
    if 'LULA_QT_VOTOS_TOT_ACUMULADO' in f:
        if (str(year),candidate_a,candidate_b)!=('2022','13','22'):
            raise ValueError('National column-to-candidate mapping not configured for this election')
        out=pd.DataFrame({'timestamp':f.timestamp,
            'sections':pd.to_numeric(f.QT_SECOES_TOT_ACUMULADO),
            'sections_total':pd.to_numeric(f.QT_SECOES_TOTAL),
            'votes_a':pd.to_numeric(f.LULA_QT_VOTOS_TOT_ACUMULADO),
            'votes_b':pd.to_numeric(f.JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO)})
        out=out.sort_values('timestamp',kind='stable').drop_duplicates('timestamp',keep='last')
    elif 'ID_TOTALIZACAO' in f:
        event=['SG_UF','CD_MUNICIPIO','NR_ZONA','ID_TOTALIZACAO']
        if f[f.NR_VOTAVEL.isin([candidate_a,candidate_b])].duplicated(event+['NR_VOTAVEL']).any():
            raise ValueError('Duplicate totalization event/candidate; cannot sum safely')
        for col in ['QT_SECOES_TOT','QT_SECOES_BRASIL','QT_VOTOS_TOT']:f[col]=pd.to_numeric(f[col],errors='raise')
        if not f.groupby(event).QT_SECOES_TOT.nunique().eq(1).all():
            raise ValueError('Conflicting section counts within a totalization event')
        if not f.groupby(event).timestamp.nunique().eq(1).all():
            raise ValueError('Conflicting timestamp within a totalization event')
        if f.QT_SECOES_BRASIL.nunique()!=1:raise ValueError('Changing national section denominator requires a new adapter')
        events=f.drop_duplicates(event).groupby('timestamp').QT_SECOES_TOT.sum()
        votes=f[f.NR_VOTAVEL.isin([candidate_a,candidate_b])].groupby(['timestamp','NR_VOTAVEL']).QT_VOTOS_TOT.sum().unstack(fill_value=0)
        increments=pd.DataFrame({'sections':events,'votes_a':votes.get(candidate_a,0),'votes_b':votes.get(candidate_b,0)}).fillna(0).sort_index()
        out=increments.cumsum().reset_index()
        out['sections_total']=int(f.QT_SECOES_BRASIL.iloc[0])
    else:raise ValueError('Unsupported official totalization layout')
    out=out.reset_index(drop=True)
    for col in ['sections','sections_total','votes_a','votes_b']:out[col]=out[col].astype('int64')
    if out.empty or out.timestamp.isna().any():raise ValueError('Empty or invalid timeline')
    if (out[['sections','votes_a','votes_b']]<0).any().any():raise ValueError('Negative cumulative counts')
    if (out.sections>out.sections_total).any() or (out.sections.diff().dropna()<0).any():
        raise ValueError('Nonmonotone or excessive section counts')
    out['year']=int(year)
    out['fraction_sections']=out.sections/out.sections_total
    valid=out.votes_a+out.votes_b
    out=out[valid>0].copy()
    out['share_a']=out.votes_a/valid[valid>0]
    out['share_b']=1-out.share_a
    return out[['year','timestamp','sections','sections_total','votes_a','votes_b','fraction_sections','share_a','share_b']]


def parse_pdf_table(text):
    """Parse the official 2014 national table; section counts are genuinely absent."""
    import re
    pattern=r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+([\d.]+)\s+([\d,]+)%\s+([\d.]+)\s+([\d,]+)%\s+([\d.]+)'
    rows=[]
    for date,clock,a,pa,b,pb,total in re.findall(pattern,text):
        a,b,total=(int(v.replace('.','')) for v in [a,b,total])
        if a+b!=total or total<=0:raise ValueError('PDF candidate votes do not sum to published valid votes')
        if abs(100*a/total-float(pa.replace(',','.')))>.0051 or abs(100*b/total-float(pb.replace(',','.')))>.0051:
            raise ValueError('PDF percentages do not match vote counts within rounding tolerance')
        rows.append({'year':2014,'timestamp':pd.to_datetime(date+' '+clock,format='%d/%m/%Y %H:%M'),
            'votes_a':a,'votes_b':b,'sections':None,'sections_total':None,'fraction_sections':float('nan'),
            'share_a':a/total,'share_b':b/total})
    if not rows:raise ValueError('No 2014 table rows recognized')
    f=pd.DataFrame(rows)
    if f.timestamp.duplicated().any() or not f.timestamp.is_monotonic_increasing:raise ValueError('Duplicate or unordered PDF timestamps')
    if (f[['votes_a','votes_b']].diff().dropna()<0).any().any():raise ValueError('Nonmonotonic cumulative PDF votes')
    f['sections']=f.sections.astype('Int64');f['sections_total']=f.sections_total.astype('Int64')
    return f[['year','timestamp','sections','sections_total','votes_a','votes_b','fraction_sections','share_a','share_b']]


def read_pdf_totalization(path):
    from pypdf import PdfReader
    reader=PdfReader(path)
    return parse_pdf_table('\n'.join(p.extract_text(extraction_mode='layout') for p in reader.pages))


def reconstruct_first_totalization(root,year):
    """Final section outcomes placed at their original first-totalization timestamps."""
    import json
    from .download import sha256
    root=Path(root)
    meta=json.loads((root/'processed'/str(year)/'chronology.json').read_text())
    if not meta.get('usable') or sha256(root/'processed'/str(year)/'sections.parquet')!=meta.get('sections_sha256'):
        raise ValueError('Reconstruction votes checksum mismatch or audit not usable')
    if sha256(root/'processed'/str(year)/'section_timing.parquet')!=meta.get('timing_sha256'):
        raise ValueError('Reconstruction timing checksum mismatch')
    f=pd.read_parquet(root/'processed'/str(year)/'sections.parquet')
    timing=pd.read_parquet(root/'processed'/str(year)/'section_timing.parquet')
    keys=['uf','municipality','zone','section']
    joined=f.merge(timing,on=keys,validate='one_to_one')
    if len(joined)!=len(f) or joined.first_totalized_at.isna().any():raise ValueError('Incomplete timing coverage')
    curve=joined.groupby('first_totalized_at').agg(sections=('section','count'),votes_a=('votes_a','sum'),votes_b=('votes_b','sum')).sort_index().cumsum().reset_index().rename(columns={'first_totalized_at':'timestamp'})
    curve['year']=year;curve['sections_total']=len(f);curve['fraction_sections']=curve.sections/len(f)
    valid=curve.votes_a+curve.votes_b;curve=curve[valid>0].copy()
    curve['share_a']=curve.votes_a/(curve.votes_a+curve.votes_b);curve['share_b']=1-curve.share_a
    return curve[['year','timestamp','sections','sections_total','votes_a','votes_b','fraction_sections','share_a','share_b']]
