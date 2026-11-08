"""Re-evaluate our CPU models at the section percentages published by Mattecca."""
import json
import resource
import time
from pathlib import Path
import torch
from projecao.experiment import run_experiment
from projecao.download import atomic_json

base=Path('reports/mattecca-comparison-20261107')
assert not list(Path('/dev').glob('nvidia*'))
torch.set_num_threads(2);torch.set_num_interop_threads(1)
config=json.loads(Path('configs/elections.json').read_text())
alignment=json.loads((base/'alignment.json').read_text())
started=time.perf_counter();runs=[]
for year in [2022,2026]:
    marks=sorted(set(alignment['published_target_fractions'][str(year)]+[1.]))
    rows=run_experiment('/data/tse',year,config,base/f'cpu-aligned-{year}',device='cpu',mode='historical',milestones=marks)
    assert all(r['error_pp']==0 for r in rows if r['fraction_sections']==1)
    runs.append({'year':year,'model_rows':len(rows),'requested_fractions':marks})
assert not torch.cuda.is_initialized()
atomic_json(base/'cpu-resources.json',{'device':'cpu','gpu_exposed':False,'cuda_initialized':False,
    'seconds':time.perf_counter()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'runs':runs})
