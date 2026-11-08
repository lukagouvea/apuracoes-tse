"""Chunked official-file normalization and observed-only snapshots."""
import csv
import json
import zipfile
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from .download import atomic_json, ensure_space, sha256
from .models import History, Snapshot, KEY
from .study import evaluation_years

SECTION=KEY+['zone','section']
REGIONS={**dict.fromkeys(['AC','AM','AP','PA','RO','RR','TO'],'N'),
 **dict.fromkeys(['AL','BA','CE','MA','PB','PE','PI','RN','SE'],'NE'),
 **dict.fromkeys(['DF','GO','MS','MT'],'CO'),**dict.fromkeys(['ES','MG','RJ','SP'],'SE'),
 **dict.fromkeys(['PR','RS','SC'],'S'),'ZZ':'EX','VT':'TRANSIT'}
LEGACY=['DT_GERACAO','HH_GERACAO','ANO_ELEICAO','NR_TURNO','DS_ELEICAO','SG_UF','CD_MUNICIPIO','NM_MUNICIPIO','NR_ZONA','NR_SECAO','CD_CARGO','DS_CARGO','NR_VOTAVEL','QT_VOTOS']
COLUMNS={'ANO_ELEICAO':'year','NR_TURNO':'turn','SG_UF':'uf','CD_MUNICIPIO':'municipality',
 'NR_ZONA':'zone','NR_SECAO':'section','NR_VOTAVEL':'candidate','QT_VOTOS':'votes',
 'NM_VOTAVEL':'candidate_name','NR_LOCAL_VOTACAO':'local'}


def normalize_chunk(frame,year,valid_only=True):
    required={'NR_TURNO','SG_UF','CD_MUNICIPIO','NR_ZONA','NR_SECAO','CD_CARGO','NR_VOTAVEL','QT_VOTOS'}
    if not required.issubset(frame.columns): raise ValueError(f'Missing TSE columns: {required-set(frame.columns)}')
    code=pd.to_numeric(frame.NR_VOTAVEL,errors='raise')
    mask=frame.CD_CARGO.eq('1') & frame.NR_TURNO.isin(['1','2'])
    if valid_only: mask &= code.between(1,94)
    if 'ANO_ELEICAO' in frame: mask &= frame.ANO_ELEICAO.eq(str(year))
    f=frame.loc[mask].rename(columns=COLUMNS).copy(); f['year']=int(year)
    if 'local' not in f: f['local']=''
    if 'candidate_name' not in f: f['candidate_name']=f.candidate
    for col in ['turn','votes']: f[col]=pd.to_numeric(f[col],errors='raise').astype('int64')
    if (f.votes<0).any(): raise ValueError('Negative votes')
    for col,width in [('municipality',5),('zone',4),('section',4)]: f[col]=f[col].str.strip().str.zfill(width)
    f['candidate']=f.candidate.str.strip()
    return f[['year','turn',*SECTION,'local','candidate','candidate_name','votes']]


def csv_chunks(archive,member,chunksize=250_000):
    with archive.open(member) as raw: first=raw.readline().decode('latin1')
    header=next(csv.reader([first],delimiter=';')); modern='NR_TURNO' in header
    if not modern and len(header)!=len(LEGACY): raise ValueError(f'Unknown headerless layout: {member}')
    with archive.open(member) as raw:
        yield from pd.read_csv(raw,sep=';',encoding='latin1',dtype=str,keep_default_na=False,
            header=0 if modern else None,names=None if modern else LEGACY,chunksize=chunksize)


def prepare_zip(path,year,out,finalists,reserve=10*1024**3):
    out=Path(out); out.mkdir(parents=True,exist_ok=True); ensure_space(out,512*1024**2,reserve)
    temp=out/'votes.parquet.tmp'; writer=None; rows=0; source_rows=0; roster=[]
    try:
        with zipfile.ZipFile(path) as z:
            members=[n for n in z.namelist() if n.lower().endswith(('.csv','.txt')) and 'leiame' not in n.lower()]
            if not members: raise ValueError('ZIP has no CSV/TXT')
            for member in members:
                for chunk in csv_chunks(z,member):
                    source_rows+=len(chunk)
                    all_votes=normalize_chunk(chunk,year,valid_only=False)
                    roster.append(all_votes.loc[all_votes.turn.eq(2),SECTION].drop_duplicates())
                    f=all_votes[pd.to_numeric(all_votes.candidate).between(1,94)]
                    if f.empty: continue
                    table=pa.Table.from_pandas(f,preserve_index=False)
                    ensure_space(out,table.nbytes,reserve)
                    if writer is None: writer=pq.ParquetWriter(temp,table.schema,compression='zstd')
                    writer.write_table(table); rows+=len(f)
        if writer is None: raise ValueError('No presidential votes found')
    finally:
        if writer is not None: writer.close()
    temp.replace(out/'votes.parquet')
    second=pd.read_parquet(out/'votes.parquet',filters=[('turn','==',2)])
    codes=sorted(second.candidate.unique().tolist())
    if finalists[0] is None or finalists[1] is None:
        if len(codes)==2 and '13' in codes: finalists=('13',next(c for c in codes if c!='13'))
        else: raise ValueError(f'{year}: confirm finalist mapping manually: {codes}')
    if not set(codes).issubset(set(finalists)) or not len(second): raise ValueError(f'{year}: unexpected finalists {codes}, configured {finalists}')
    duplicates=int(second.duplicated(SECTION+['candidate']).sum())
    if duplicates: raise ValueError(f'{year}: {duplicates} duplicate section/candidate rows; resolve source')
    sections=second.pivot_table(index=SECTION,columns='candidate',values='votes',aggfunc='sum',fill_value=0)
    sections=sections.reindex(columns=list(finalists),fill_value=0).rename(columns={finalists[0]:'votes_a',finalists[1]:'votes_b'}).reset_index()
    sections.columns.name=None
    universe=pd.concat(roster,ignore_index=True).drop_duplicates().sort_values(SECTION).reset_index(drop=True)
    sections=universe.merge(sections,on=SECTION,how='left',validate='one_to_one').fillna({'votes_a':0,'votes_b':0})
    sections[['votes_a','votes_b']]=sections[['votes_a','votes_b']].astype('int64')
    if not sections.uf.isin(REGIONS).all(): raise ValueError(f'Unknown UF: {sections.loc[~sections.uf.isin(REGIONS),"uf"].unique()}')
    ensure_space(out,int(universe.memory_usage(deep=True).sum()+sections.memory_usage(deep=True).sum()),reserve)
    universe.to_parquet(out/'universe.parquet',index=False,compression='zstd')
    p=out/'sections.parquet.tmp'; sections.to_parquet(p,index=False,compression='zstd'); p.replace(out/'sections.parquet')
    report={'year':year,'source_sha256':sha256(path),'source_rows':source_rows,'normalized_rows':rows,
      'sections':len(sections),'municipalities':len(sections[KEY].drop_duplicates()),'duplicate_rows':duplicates,
      'zero_valid_sections':int((sections.votes_a+sections.votes_b).eq(0).sum()),
      'candidate_a':finalists[0],'candidate_b':finalists[1],
      'candidate_names':second.groupby('candidate').candidate_name.first().to_dict(),
      'votes_a':int(sections.votes_a.sum()),'votes_b':int(sections.votes_b.sum()),
      'valid_votes':int(sections.votes_a.sum()+sections.votes_b.sum()),
      'votes_parquet_bytes':(out/'votes.parquet').stat().st_size,'sections_parquet_bytes':(out/'sections.parquet').stat().st_size,
      'universe_limitation':'Includes sections with only blanks/nulls; sections absent from source cannot be counted.'}
    atomic_json(out/'preparation.json',report); return report


def make_history(reference,universe):
    if set(universe.columns)!=set(SECTION): raise ValueError('Universe must contain structural identifiers only')
    if universe.duplicated(SECTION).any(): raise ValueError('Duplicate universe sections')
    reference=reference.copy()
    # Legacy synthetic fixtures may contain only the two finalists. Official
    # first-turn references always supply valid_votes, including other candidates.
    if 'valid_votes' not in reference: reference['valid_votes']=reference.votes_a+reference.votes_b
    if (reference[['votes_a','votes_b','valid_votes']]<0).any().any() or ((reference.votes_a+reference.votes_b)>reference.valid_votes).any():
        raise ValueError('Invalid reference vote totals')
    if reference.duplicated(SECTION).any():raise ValueError('Duplicate reference section')
    ref=reference.groupby(KEY,as_index=False).agg(ref_a=('votes_a','sum'),ref_b=('votes_b','sum'),ref_size=('valid_votes','sum'),ref_n=('section','count'))
    ref['ref_pair']=ref.ref_a+ref.ref_b
    columns=['ref_a','ref_pair','ref_size','ref_n']
    national=ref[columns].sum()
    if national.ref_pair<=0: raise ValueError('No valid historical finalist votes')
    uf=ref.groupby('uf')[columns].sum()
    f=universe.groupby(KEY,as_index=False).size().rename(columns={'size':'n_sections'}).merge(ref,on=KEY,how='left',validate='one_to_one')
    f['matched']=f.ref_pair.fillna(0)>0; f['region']=f.uf.map(REGIONS)
    if f.region.isna().any(): raise ValueError('Unknown geographic region')
    for i,row in f.iterrows():
        state=uf.loc[row.uf] if row.uf in uf.index else national
        preference=row if row.matched else (state if state.ref_pair>0 else national)
        volume=row if pd.notna(row.ref_n) else (state if state.ref_size>0 else national)
        f.loc[i,'ref_share']=float(preference.ref_a/preference.ref_pair)
        f.loc[i,'ref_per_section']=float(volume.ref_size/volume.ref_n)
        f.loc[i,'ref_size']=float(volume.ref_size)
    return History(f[[*KEY,'region','n_sections','ref_share','ref_per_section','ref_size','matched']])


def build_snapshot(observed):
    if observed.empty: return Snapshot.empty()
    if observed.duplicated(SECTION).any(): raise ValueError('Duplicate observed section')
    return Snapshot(observed.groupby(KEY,as_index=False).agg(n_observed=('section','count'),votes_a=('votes_a','sum'),votes_b=('votes_b','sum')))


def prepare_all(root,elections,years):
    root=Path(root); reports=[]
    for year in years:
        z=root/'raw'/str(year)/'votes'/f'votacao_secao_{year}_BR.zip'
        if not z.exists(): reports.append({'year':year,'status':'missing_source'}); continue
        cfg=elections[str(year)]
        r=prepare_zip(z,year,root/'processed'/str(year),(cfg['candidate_a'],cfg['candidate_b']))
        if year in evaluation_years():prepare_first_turn_reference(root,year,(cfg['candidate_a'],cfg['candidate_b']))
        reports.append(r); print(f'prepared {year}: {r["sections"]:,} sections, {r["valid_votes"]:,} valid votes',flush=True)
    atomic_json(root/'manifests'/'preparation.json',reports); return reports


def prepare_first_turn_reference(root,year,finalists,reserve=10*1024**3):
    """Extract first-turn votes and its own section roster without rewriting round 2."""
    root=Path(root);out=root/'processed'/str(year);out.mkdir(parents=True,exist_ok=True)
    source=root/'raw'/str(year)/'votes'/f'votacao_secao_{year}_BR.zip'
    rosters=[];frames=[]
    with zipfile.ZipFile(source) as archive:
        members=[n for n in archive.namelist() if n.lower().endswith(('.csv','.txt')) and 'leiame' not in n.lower()]
        for member in members:
            for chunk in csv_chunks(archive,member):
                all_votes=normalize_chunk(chunk,year,valid_only=False)
                first=all_votes.loc[all_votes.turn.eq(1)]
                rosters.append(first[SECTION].drop_duplicates())
                valid=first.loc[pd.to_numeric(first.candidate).between(1,94),SECTION+['candidate','votes']]
                if len(valid):frames.append(valid)
    if not frames:raise ValueError(f'{year}: no first-turn presidential valid votes')
    valid=pd.concat(frames,ignore_index=True)
    if valid.duplicated(SECTION+['candidate']).any():raise ValueError(f'{year}: duplicate first-turn section/candidate')
    if not set(finalists).issubset(set(valid.candidate)):raise ValueError(f'{year}: finalists absent from first turn')
    universe=pd.concat(rosters,ignore_index=True).drop_duplicates().sort_values(SECTION).reset_index(drop=True)
    totals=valid.groupby(SECTION,as_index=False).votes.sum().rename(columns={'votes':'valid_votes'})
    pair=valid[valid.candidate.isin(finalists)].pivot_table(index=SECTION,columns='candidate',values='votes',aggfunc='sum',fill_value=0)
    pair=pair.reindex(columns=list(finalists),fill_value=0).rename(columns={finalists[0]:'votes_a',finalists[1]:'votes_b'}).reset_index()
    pair.columns.name=None
    reference=universe.merge(totals,on=SECTION,how='left',validate='one_to_one').merge(pair,on=SECTION,how='left',validate='one_to_one')
    vote_columns=['votes_a','votes_b','valid_votes']
    reference[vote_columns]=reference[vote_columns].fillna(0).astype('int64')
    reference['votes_other']=reference.valid_votes-reference.votes_a-reference.votes_b
    reference=reference[SECTION+['votes_a','votes_b','votes_other','valid_votes']]
    path=out/'first_turn_sections.parquet';temp=out/'first_turn_sections.parquet.tmp'
    ensure_space(out,int(reference.memory_usage(deep=True).sum()),reserve)
    reference.to_parquet(temp,index=False,compression='zstd');temp.replace(path)
    meta={'status':'complete','year':year,'turn':1,'candidate_a':finalists[0],'candidate_b':finalists[1],
        'source_file':str(source.relative_to(root)),'source_sha256':sha256(source),'reference_sha256':sha256(path),
        'sections':len(reference),'zero_valid_sections':int(reference.valid_votes.eq(0).sum()),
        'zero_finalist_sections':int((reference.votes_a+reference.votes_b).eq(0).sum()),
        'votes_a':int(reference.votes_a.sum()),'votes_b':int(reference.votes_b.sum()),
        'votes_other':int(reference.votes_other.sum()),'valid_votes':int(reference.valid_votes.sum()),
        'preference':'A1 / (A1 + B1), municipal; fallback if no finalist votes',
        'volume':'All first-turn valid presidential votes, including eliminated candidates',
        'parquet_bytes':path.stat().st_size}
    atomic_json(out/'first_turn_reference.json',meta)
    print(f'{year} first-turn reference: {len(reference):,} sections, {meta["valid_votes"]:,} valid votes',flush=True)
    return meta


def load_first_turn_reference(root,year,finalists):
    root=Path(root);out=root/'processed'/str(year)
    path=out/'first_turn_sections.parquet'
    meta=json.loads((out/'first_turn_reference.json').read_text())
    if (meta.get('status'),meta.get('year'),meta.get('turn'),meta.get('candidate_a'),meta.get('candidate_b'))!=('complete',year,1,*finalists):
        raise ValueError('First-turn reference metadata does not match the target election')
    source=root/'raw'/str(year)/'votes'/f'votacao_secao_{year}_BR.zip'
    if sha256(path)!=meta.get('reference_sha256') or sha256(source)!=meta.get('source_sha256'):
        raise ValueError('First-turn reference checksum mismatch; prepare the reference again')
    reference=pd.read_parquet(path)
    if not set(SECTION+['votes_a','votes_b','votes_other','valid_votes']).issubset(reference.columns):
        raise ValueError('First-turn reference schema is incomplete')
    return reference,meta
