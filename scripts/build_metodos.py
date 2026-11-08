"""Generate the offline teaching guide from production-model worked examples."""
from pathlib import Path
import json
import importlib.metadata as md
from projecao.didactic import poststrat_case,swing_case,hierarchy_case
from projecao.download import atomic_json,sha256
from projecao.study import load_study


def build():
    lambdas=[100,500,1500,5000,15000,150000]
    examples={'study':load_study(),'synthetic':True,'lambda_options':lambdas,
        'poststrat':{f'{x}:{y}':poststrat_case(x,y) for x in range(11) for y in range(21)},
        'swing':{str(s):swing_case(s) for s in range(-10,11)},
        'hierarchical':{f'{n}:{lam}':hierarchy_case(n,lam) for n in range(101) for lam in lambdas}}
    output=Path('reports/metodos.html');asset=Path('reports/metodos');asset.mkdir(parents=True,exist_ok=True)
    atomic_json(asset/'examples.json',examples)
    template=Path('templates/metodos.html').read_text()
    encoded=json.dumps(examples,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    output.write_text(template.replace('__METHOD_EXAMPLES__',encoded))
    files=['templates/metodos.html','scripts/build_metodos.py','src/projecao/didactic.py','src/projecao/models.py','src/projecao/study.py','configs/study.json']
    atomic_json(asset/'manifest.json',{'synthetic':True,'states':{k:len(examples[k]) for k in ['poststrat','swing','hierarchical']},
        'html_sha256':sha256(output),'examples_sha256':sha256(asset/'examples.json'),
        'source_sha256':{p:sha256(p) for p in files},'torch':md.version('torch'),'study':load_study()})
    print(f'{output}: {output.stat().st_size/1024:.1f} KiB; {sum(len(examples[k]) for k in ["poststrat","swing","hierarchical"])} model-verified states')

if __name__=='__main__':build()
