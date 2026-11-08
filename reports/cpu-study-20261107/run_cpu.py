"""CPU-only experiment driver; uses the existing estimators without changing them."""
import argparse
import gc
import json
import os
import resource
import time
from pathlib import Path
import torch
from projecao.download import atomic_json,sha256
from projecao.experiment import run_experiment

BASE=Path('reports/cpu-study-20261107')
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['pilot','grid'])
args=parser.parse_args()
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='-1'
assert not list(Path('/dev').glob('nvidia*')),'GPU devices must not be exposed to this container'
assert not torch.cuda.is_initialized()
torch.set_num_threads(2);torch.set_num_interop_threads(1)
config=json.loads(Path('configs/elections.json').read_text())
years=[2022] if args.phase=='pilot' else [2018,2022,2026]
marks=[.01,.02,.05,.1,1.] if args.phase=='pilot' else [.001,.002,.005]+[i/100 for i in range(1,101)]
executions=[];started=time.perf_counter()
for year in years:
    output=BASE/f'{args.phase}-{year}'
    begin=time.perf_counter()
    rows=run_experiment('/data/tse',year,config,output,device='cpu',mode='historical',milestones=marks)
    assert not torch.cuda.is_initialized()
    final=[r for r in rows if r['fraction_sections']==1]
    assert len(final)==3 and all(r['error_pp']==0 for r in final)
    entry={'year':year,'seconds':time.perf_counter()-begin,'rows':len(rows),
        'snapshots_per_method':len(rows)//3,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'output':str(output),'cuda_initialized':torch.cuda.is_initialized()}
    executions.append(entry);print(json.dumps(entry),flush=True);gc.collect()
limits={p:(Path('/sys/fs/cgroup')/p).read_text().strip() for p in ['cpu.max','memory.max','memory.swap.max'] if (Path('/sys/fs/cgroup')/p).exists()}
atomic_json(BASE/f'{args.phase}-resources.json',{'phase':args.phase,'device':'cpu','gpu_devices_exposed':False,
    'cuda_initialized':torch.cuda.is_initialized(),'torch_threads':torch.get_num_threads(),'nice':os.getpriority(os.PRIO_PROCESS,0),
    'limits':limits,'requested_milestones':marks,'wall_seconds':time.perf_counter()-started,
    'driver_sha256':sha256(Path(__file__)),'executions':executions})
