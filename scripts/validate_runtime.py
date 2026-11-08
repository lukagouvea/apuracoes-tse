"""Real-data CPU/CUDA agreement and hardware/dependency manifest."""
import importlib.metadata as md
import json
import platform
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from projecao.data import SECTION, make_history, build_snapshot, load_first_turn_reference
from projecao.download import atomic_json, sha256
from projecao.models import Config, predict
from projecao.study import load_study

root=Path('/data/tse')
current=pd.read_parquet(root/'processed/2026/sections.parquet')
elections=json.loads(Path('configs/elections.json').read_text());cfg=elections['2026']
reference,reference_provenance=load_first_turn_reference(root,2026,(cfg['candidate_a'],cfg['candidate_b']))
history=make_history(reference,current[SECTION])
rng=np.random.default_rng(42)
observed=current.iloc[rng.permutation(len(current))[:max(1,len(current)//20)]]
snapshot=build_snapshot(observed)
checks=[]
for method in ['poststrat','swing','hierarchical']:
    cpu=predict(snapshot,history,Config(method=method,device='cpu'))
    gpu=predict(snapshot,history,Config(method=method,device='cuda'))
    delta=abs(cpu.share_a-gpu.share_a)
    assert delta<=1e-6,(method,delta)
    checks.append({'method':method,'cpu_share_a':cpu.share_a,'cuda_share_a':gpu.share_a,'absolute_difference':delta})
m=torch.tensor([[1.,2.],[3.,4.]],dtype=torch.float64,device='cuda')
assert torch.equal(m@m,torch.tensor([[7.,10.],[15.,22.]],device='cuda',dtype=torch.float64))
report={'year':2026,'turn':2,'reference_year':2026,'reference_turn':1,'study':load_study(),
 'reference_provenance':reference_provenance,'python':platform.python_version(),'image_id':'sha256:bddd3bf9b9e44eee13044ba2afe85a757c1e5009e94bfba5701facf600465c63',
 'packages':{x:md.version(x) for x in ['torch','numpy','pandas','scipy','scikit-learn','pyarrow','requests','certifi','charset-normalizer','idna','urllib3']},
 'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(),'architectures':torch.cuda.get_arch_list(),
 'matrix_cuda_result':(m@m).tolist(),'official_2026_5pct_snapshot':checks,
 'current_sha256':sha256(root/'processed/2026/sections.parquet'),'reference_sha256':sha256(root/'processed/2026/first_turn_sections.parquet')}
atomic_json('reports/runtime.json',report)
print(json.dumps(report,indent=2))
