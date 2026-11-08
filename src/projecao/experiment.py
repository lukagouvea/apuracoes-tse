"""Replay and retrospective evaluation; complete election outcomes stay here."""
from dataclasses import replace
import math
import platform
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from .data import SECTION, build_snapshot, make_history, load_first_turn_reference
from .download import atomic_json, sha256
from .models import Config, predict, convergence
from .study import load_study


def audit_order(universe,order,meaning):
    required=set(SECTION+['timestamp'])
    if not required.issubset(order.columns):
        return {'usable':False,'coverage':0.,'reason':'missing columns'}
    duplicate_rows=int(order.duplicated(SECTION).sum())
    timestamps=pd.to_datetime(order.timestamp,errors='coerce')
    matched=universe.merge(order[SECTION].drop_duplicates(),on=SECTION,how='inner')
    coverage=len(matched)/len(universe) if len(universe) else 0.
    unexpected=len(order[SECTION].drop_duplicates().merge(universe,on=SECTION,how='left',indicator=True).query('_merge == "left_only"'))
    usable=coverage==1 and duplicate_rows==0 and timestamps.notna().all() and meaning in {'reception','totalization'} and unexpected==0
    return {'usable':bool(usable),'coverage':coverage,'duplicate_sections':duplicate_rows,
        'unmatched_order_sections':unexpected,'invalid_timestamps':int(timestamps.isna().sum()),
        'timestamp_meaning':meaning,'tied_sections':int(timestamps.duplicated(keep=False).sum()),
        'first_timestamp':str(timestamps.min()),'last_timestamp':str(timestamps.max()),
        'limitation':'Reception order is not necessarily the order of official totalization.' if meaning=='reception' else None}


def reveal_order(sections,order=None,seed=42):
    if order is None:
        rng=np.random.default_rng(seed)
        f=sections.iloc[rng.permutation(len(sections))].reset_index(drop=True).copy()
        f['batch']=np.arange(len(f))
        return f
    f=sections.merge(order[SECTION+['timestamp']],on=SECTION,validate='one_to_one')
    if len(f)!=len(sections): raise ValueError('Incomplete chronology')
    f['timestamp']=pd.to_datetime(f.timestamp,errors='raise')
    f=f.sort_values(['timestamp',*SECTION],kind='stable').reset_index(drop=True)
    f['batch']=f.timestamp.factorize(sort=True)[0]
    return f


def evaluate(ordered,history,config,milestones):
    if not len(ordered): raise ValueError('No sections')
    if not milestones or any(not 0<float(p)<=1 for p in milestones): raise ValueError('Milestones must be in (0,1]')
    total_a=int(ordered.votes_a.sum()); total=int((ordered.votes_a+ordered.votes_b).sum())
    if total<=0: raise ValueError('No valid votes in target election')
    truth=total_a/total
    results=[]; seen=set(); batches=ordered.batch.to_numpy()
    for mark in sorted(set(milestones)):
        k=min(len(ordered),max(1,math.ceil(mark*len(ordered))))
        end=int(np.searchsorted(batches,batches[k-1],side='right'))
        if end in seen: continue
        seen.add(end)
        observed=ordered.iloc[:end][SECTION+['votes_a','votes_b']]
        snapshot=build_snapshot(observed)
        start=time.perf_counter(); p=predict(snapshot,history,config)
        elapsed=time.perf_counter()-start
        n_valid=int((observed.votes_a+observed.votes_b).sum())
        baseline=float(observed.votes_a.sum()/n_valid) if n_valid else None
        results.append({**p.to_dict(),'requested_fraction':mark,'observed_sections':end,
            'baseline_share_a':baseline,'baseline_error_pp':abs(baseline-truth)*100 if baseline is not None else None,
            'final_share_a':truth,'error_pp':abs(p.share_a-truth)*100,'elapsed_seconds':elapsed})
    return results


def run_experiment(root,year,elections,output,device='cuda',mode='simulated',seed=42,milestones=None,methods=None):
    study=load_study()
    if year not in study['evaluation_years']:
        raise ValueError(f'{year} is not an evaluated election; allowed: {study["evaluation_years"]}')
    root=Path(root); output=Path(output)
    if output.exists(): raise ValueError(f'Output already exists: {output}; choose a new output path')
    cfg=elections[str(year)]
    if cfg.get('reference')!={'year':year,'turn':1}:
        raise ValueError('Reference must be the first turn of the same year')
    ref_year=year;ref_turn=1
    current_path=root/'processed'/str(year)/'sections.parquet'
    ref_path=root/'processed'/str(year)/'first_turn_sections.parquet'
    ref,ref_provenance=load_first_turn_reference(root,year,(cfg['candidate_a'],cfg['candidate_b']))
    current=pd.read_parquet(current_path)
    history=make_history(ref,current[SECTION])
    order=None; audit=None
    if mode=='historical':
        order,audit=load_historical_order(root,year,current)
    elif mode!='simulated': raise ValueError(f'Unknown mode: {mode}')
    ordered=reveal_order(current,order,seed)
    marks=milestones or study['smoke_milestones']
    methods=methods or ['poststrat','swing','hierarchical']
    all_rows=[]; conv={}
    for method in methods:
        cfg=Config(method=method,device=device)
        rows=evaluate(ordered,history,cfg,marks)
        for r in rows: r.update(year=year,turn=2,reference_year=ref_year,reference_turn=ref_turn,mode=mode)
        all_rows.extend(rows)
        conv[method]={str(e):convergence([r['fraction_sections'] for r in rows],[r['error_pp'] for r in rows],e) for e in study['convergence_thresholds_pp']}
        print(f'{year} {mode} {method}: {len(rows)} snapshots, final sampled error {rows[-1]["error_pp"]:.6f} pp',flush=True)
    output.mkdir(parents=True)
    pd.DataFrame(all_rows).to_parquet(output/'projections.parquet',index=False,compression='zstd')
    pd.DataFrame(all_rows).to_csv(output/'projections.csv',index=False)
    atomic_json(output/'convergence.json',{'sampled_grid_only':True,'milestones':marks,'convergence':conv})
    import importlib.metadata as md
    atomic_json(output/'run.json',{'year':year,'turn':2,'reference_year':ref_year,'reference_turn':ref_turn,'mode':mode,'seed':seed,'device':device,
        'milestones':marks,'methods':methods,'defaults':Config().__dict__,'chronology':audit,
        'current_sha256':sha256(current_path),'reference_sha256':sha256(ref_path),
        'study':study,'reference_provenance':ref_provenance,'elections_config':elections,'code_sha256':code_hashes(),'python':platform.python_version(),
        'packages':{n:md.version(n) for n in ['torch','numpy','pandas','pyarrow','requests']},
        'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name() if device=='cuda' else None,
        'calibration':'Fixed initial parameters, not optimized against target outcomes.',
        'historical_alignment':'Same finalists, first turn to second turn of the same year; preference conditional on A+B, volume includes all valid first-turn votes.'})
    return all_rows


def code_hashes():
    return {p.name:sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def load_historical_order(root,year,current):
    import json
    root=Path(root); out=root/'processed'/str(year)
    op=out/'order.parquet'; meta_path=out/'chronology.json'
    if not op.exists() or not meta_path.exists(): raise ValueError('No audited chronology; use --mode simulated explicitly')
    meta=json.loads(meta_path.read_text())
    if not meta.get('usable') or not meta.get('source_manifests'): raise ValueError('Chronology is not usable or lacks official provenance')
    if sha256(op)!=meta.get('order_sha256'): raise ValueError('Chronology checksum mismatch; run audit again')
    if meta.get('universe_sha256') and sha256(out/'universe.parquet')!=meta['universe_sha256']:
        raise ValueError('Universe checksum mismatch; run audit again')
    if meta.get('reconstructed_from_final_votes') and sha256(out/'sections.parquet')!=meta.get('sections_sha256'):
        raise ValueError('Reconstruction votes checksum mismatch; run audit again')
    for source in meta['source_manifests']:
        mp=root/source['manifest']; manifest=json.loads(mp.read_text())
        if manifest.get('status')!='complete' or manifest.get('sha256')!=source['sha256']:
            raise ValueError('BU source manifest checksum mismatch')
        # Audit already hashed every BU; preserve those exact source manifests in run.json.
    order=pd.read_parquet(op)
    checked=audit_order(current[SECTION],order,meta['timestamp_meaning'])
    if not checked['usable']: raise ValueError(f'Chronology not usable: {checked}')
    return order,{**checked,**meta,'runtime_audit':checked}
