"""Presentation helpers for recorded projection trajectories."""
import math
import numpy as np
import pandas as pd
from .models import convergence
from .study import evaluation_years

METHODS=('poststrat','swing','hierarchical')
MILESTONES=(.01,.02,.05,.1)


def prepare_election(frame,metadata):
    """Validate a recorded run and expose its actual snapshots without interpolation."""
    year=metadata['year']
    if year not in evaluation_years() or (metadata.get('turn'),metadata.get('reference_year'),metadata.get('reference_turn'))!=(2,year,1):
        raise ValueError('Expected a same-year first-turn reference and second-turn target')
    if metadata.get('mode')!='historical' or metadata.get('study',{}).get('reference_policy')!='same_year_first_round':
        raise ValueError('Expected historical snapshots with first-turn reference')
    for milestone in MILESTONES:
        if not any(math.isclose(milestone,m,abs_tol=1e-12) for m in metadata.get('milestones',[])):
            raise ValueError(f'Required milestone {milestone} is absent from the recorded grid')
    required={'year','turn','reference_year','reference_turn','method','fraction_sections','requested_fraction',
        'observed_sections','share_a','share_b','final_share_a','error_pp','baseline_share_a','baseline_error_pp'}
    if not required.issubset(frame.columns):raise ValueError('Incomplete results schema')
    if set(frame.method)!=set(METHODS):raise ValueError('All three methods are required')
    for column,value in [('year',year),('turn',2),('reference_year',year),('reference_turn',1)]:
        if not frame[column].eq(value).all():raise ValueError('Result rows have incompatible first-turn reference metadata')
    if not np.isfinite(frame[['share_a','share_b','final_share_a','fraction_sections','error_pp']].to_numpy()).all():
        raise ValueError('Nonfinite projection data')
    if not frame.share_a.between(0,1).all() or not np.allclose(frame.share_a+frame.share_b,1,atol=1e-12):
        raise ValueError('Invalid candidate proportions')
    final=float(frame.final_share_a.iloc[0])
    if not frame.final_share_a.eq(final).all() or not np.allclose(frame.error_pp,100*(frame.share_a-final).abs(),atol=1e-9):
        raise ValueError('Final result or projection errors are inconsistent')
    groups={m:frame[frame.method.eq(m)].sort_values('fraction_sections').reset_index(drop=True) for m in METHODS}
    reference=groups[METHODS[0]]
    common=['fraction_sections','requested_fraction','observed_sections','baseline_share_a','baseline_error_pp']
    if any(not reference[common].equals(g[common]) for g in groups.values()):
        raise ValueError('Methods must use the same snapshots')
    fractions=reference.fraction_sections.to_list()
    if not fractions or any(not 0<f<=1 for f in fractions) or any(b<=a for a,b in zip(fractions,fractions[1:])):
        raise ValueError('Snapshot fractions must be strictly increasing')
    if fractions[-1]!=1 or any(abs(float(g.iloc[-1].share_a)-final)>1e-12 for g in groups.values()):
        raise ValueError('A verified 100% endpoint is required')
    def nullable(value):return None if pd.isna(value) else float(value)
    points=[]
    for i,row in reference.iterrows():
        previous=points[-1] if points else None
        baseline=nullable(row.baseline_share_a)
        estimates={}
        for method,g in groups.items():
            r=g.iloc[i];share=float(r.share_a)
            estimates[method]={'share_a':share,'share_b':float(r.share_b),'error_pp':float(r.error_pp),
                'change_pp':100*abs(share-previous['estimates'][method]['share_a']) if previous else None}
        points.append({'fraction':float(row.fraction_sections),'requested_fraction':float(row.requested_fraction),
            'observed_sections':int(row.observed_sections),'baseline_share':baseline,'baseline_error_pp':nullable(row.baseline_error_pp),
            'baseline_change_pp':100*abs(baseline-previous['baseline_share']) if previous and baseline is not None and previous['baseline_share'] is not None else None,
            'previous_fraction':previous['fraction'] if previous else None,
            'step_sections_pp':100*(float(row.fraction_sections)-previous['fraction']) if previous else None,'estimates':estimates})
    milestones=[]
    for mark in MILESTONES:
        index=next(i for i,p in enumerate(points) if p['fraction']>=mark)
        point=points[index]
        if point['requested_fraction']>mark+1e-12:
            raise ValueError(f'Recorded snapshot for milestone {mark} is missing; cannot use a later requested milestone')
        for method in METHODS:
            milestones.append({'year':year,'turn':2,'reference_year':year,'reference_turn':1,
                'requested_fraction':mark,'fraction_sections':point['fraction'],'observed_sections':point['observed_sections'],
                'point_index':index,'method':method,'share_a':point['estimates'][method]['share_a'],
                'share_b':point['estimates'][method]['share_b'],'final_a':final,'final_b':1-final,
                'error_pp':point['estimates'][method]['error_pp']})
    cfg=metadata['elections_config'][str(year)];chrono=metadata.get('chronology',{})
    return {'year':year,'name_a':cfg['name_a'],'name_b':cfg['name_b'],'final_a':final,'final_b':1-final,
        'device':metadata['device'],'points':points,'milestones':milestones,'reference_year':year,'reference_turn':1,
        'clock':'Primeira totalização por seção' if chrono.get('reconstructed_from_final_votes') else 'Recebimento de BUs',
        'reconstructed':bool(chrono.get('reconstructed_from_final_votes')),
        'convergence':{method:{str(e):convergence(fractions,g.error_pp.to_list(),e) for e in [1.,.5,.25]} for method,g in groups.items()},
        'parameters':metadata.get('defaults',{})}
