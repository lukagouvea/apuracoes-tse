"""Build an offline comparison of recorded CPU projection trajectories."""
import argparse
import json
from pathlib import Path
import pandas as pd
from projecao.download import atomic_json,sha256
from projecao.results import prepare_election,METHODS
from projecao.study import load_study

COLORS={'poststrat':'#235d9c','swing':'#b76e28','hierarchical':'#6c4c91'}
LABELS={'poststrat':'Pós-estratificação','swing':'Swing','hierarchical':'Hierárquico'}


def figures(elections,folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
    fig,axes=plt.subplots(2,3,figsize=(13.5,7.5),constrained_layout=True)
    for col,e in enumerate(elections.values()):
        points=[p for p in e['points'] if p['fraction']>=.01]
        xs=[p['fraction']*100 for p in points]
        for method in METHODS:
            axes[0,col].plot(xs,[p['estimates'][method]['share_a']*100 for p in points],color=COLORS[method],label=LABELS[method],lw=1.5)
            axes[1,col].plot(xs,[p['estimates'][method]['change_pp'] for p in points],color=COLORS[method],lw=1.4)
        axes[0,col].axhline(e['final_a']*100,color='#20272b',ls='--',lw=1,label='Resultado final de A')
        axes[0,col].axhspan((e['final_a']-.005)*100,(e['final_a']+.005)*100,color='#20272b',alpha=.045)
        axes[0,col].set_title(f'{e["year"]} · projeção de A')
        axes[1,col].set_title(f'{e["year"]} · variação entre snapshots')
        for ax in axes[:,col]:ax.set_xlim(0,100);ax.set_xlabel('Seções reveladas (%)')
        axes[1,col].set_ylim(bottom=0)
    axes[0,0].set_ylabel('A nos votos válidos (%)')
    axes[1,0].set_ylabel('|Mudança da projeção| (p.p.)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncols=4,frameon=False)
    fig.suptitle('Trajetória das projeções e variação entre snapshots\nReferência: 1º turno do próprio ano · desde o marco de 1% · faixa cinza: ±0,5 p.p.',fontsize=13)
    for extension in ['png','svg']:fig.savefig(folder/f'trajetorias.{extension}',dpi=170)
    plt.close(fig)


def build(runs_root,output):
    study=load_study();elections={};sources={};tables=[]
    for year in study['evaluation_years']:
        run=Path(runs_root)/f'grid-{year}';meta_path=run/'run.json';parquet=run/'projections.parquet'
        election=prepare_election(pd.read_parquet(parquet),json.loads(meta_path.read_text()))
        elections[str(year)]=election;tables.extend(election['milestones'])
        sources[str(year)]={str(p):sha256(p) for p in [meta_path,parquet]}
    output=Path(output);folder=output.parent/'convergencia';folder.mkdir(parents=True,exist_ok=True)
    payload={'study':study,'elections':elections,'methods':LABELS,'model_projections':sum(len(e['points'])*3 for e in elections.values())}
    atomic_json(folder/'series.json',payload)
    table=pd.DataFrame(tables)
    table.to_csv(folder/'marcos.csv',index=False)
    table.to_parquet(folder/'marcos.parquet',index=False,compression='zstd')
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    template=Path('templates/convergencia.html');output.write_text(template.read_text().replace('__PROJECTION_DATA__',encoded))
    figures(elections,folder)
    code=[Path(__file__),template,Path('src/projecao/results.py'),Path('src/projecao/models.py'),Path('src/projecao/study.py'),Path('configs/study.json')]
    atomic_json(folder/'manifest.json',{'study':study,'source_runs':sources,'source_code':{str(p):sha256(p) for p in code},
        'artifacts':{str(p):sha256(p) for p in [output,folder/'series.json',folder/'marcos.csv',folder/'marcos.parquet',folder/'trajetorias.png',folder/'trajetorias.svg']},
        'table_rows':len(table),'model_projections':payload['model_projections'],'recomputed_estimators':False})
    print(f'{output}: {payload["model_projections"]} recorded projections; {len(table)} milestone rows; no estimators rerun.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-root',type=Path,default=Path('reports/cpu-study-20261107'))
    parser.add_argument('--output',type=Path,default=Path('reports/convergencia.html'))
    args=parser.parse_args();build(args.runs_root,args.output)
