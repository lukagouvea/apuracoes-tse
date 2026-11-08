import argparse
import json
import sys
from pathlib import Path
import numpy as np
from .download import YEARS, download, storage_estimate
from .data import prepare_all, prepare_first_turn_reference
from .audit import audit_all
from .experiment import run_experiment
from .study import load_study,evaluation_years


def parser():
    p=argparse.ArgumentParser(description='Projeções eleitorais: dados TSE e replay sem vazamento')
    p.add_argument('--root',default='/data/tse',type=Path)
    p.add_argument('--config',default='configs/elections.json',type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['download','prepare','audit']:
        s=sub.add_parser(name); s.add_argument('--years',type=int,nargs='+',default=list(YEARS),choices=YEARS)
        if name=='download': s.add_argument('--kinds',nargs='+',choices=['votes','summary','totals','bu','detail'],default=['votes','summary','totals'])
    sub.add_parser('storage')
    s=sub.add_parser('prepare-reference',help='Prepare first-turn references for the three second-turn experiments')
    s.add_argument('--years',type=int,nargs='+',default=list(evaluation_years()),choices=evaluation_years())
    for name in ['smoke','experiment']:
        s=sub.add_parser(name)
        s.add_argument('--year',type=int,default=2026,choices=evaluation_years())
        s.add_argument('--device',choices=['cpu','cuda'],default='cuda')
        s.add_argument('--mode',choices=['historical','simulated'],default='simulated')
        s.add_argument('--seed',type=int,default=42)
        s.add_argument('--output',type=Path,required=True)
        s.add_argument('--milestones',type=float,nargs='+',default=load_study()['smoke_milestones'])
        s.add_argument('--grid-step',type=float,help='Additional grid spacing as a fraction, e.g. .01')
    return p


def main():
    p=parser(); a=p.parse_args()
    try:
        if a.command=='download':
            failures=download(a.root,a.years,a.kinds)
            return 1 if failures else 0
        if a.command=='storage':
            rows=storage_estimate(a.root)
            print(json.dumps({k:sum(x.get('bytes',0) for x in rows if x.get('kind')==k and x.get('status')==200) for k in ['votes','totals','bu']},indent=2)); return 0
        if a.command=='audit':
            rows=audit_all(a.root,a.years)
            return 1 if any(r.get('totals',{}).get('status')=='mismatch' for r in rows) else 0
        elections=json.loads(a.config.read_text())
        if a.command=='prepare-reference':
            for year in a.years:
                cfg=elections[str(year)]
                prepare_first_turn_reference(a.root,year,(cfg['candidate_a'],cfg['candidate_b']))
            return 0
        if a.command=='prepare':
            rows=prepare_all(a.root,elections,a.years)
            return 1 if any(r.get('status')=='missing_source' for r in rows) else 0
        marks=a.milestones
        if a.grid_step is not None:
            if not 0<a.grid_step<=1: raise ValueError('--grid-step must be in (0,1]')
            marks=sorted(set(marks+np.arange(a.grid_step,1.,a.grid_step).tolist()+[1.]))
        run_experiment(a.root,a.year,elections,a.output,a.device,a.mode,a.seed,marks)
        return 0
    except (ValueError,OSError,RuntimeError,KeyError) as e:
        print(f'Error: {e}',file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
