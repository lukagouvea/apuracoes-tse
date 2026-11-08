"""Descriptive comparison; published percentages are not paired voter samples."""
import json
import collections
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from projecao.download import atomic_json,sha256

base=Path('reports/mattecca-comparison-20261107')
cases=json.loads((base/'raw/backtests.json').read_text())
case=[c for c in cases if c.get('caso')=='2022-2' and c.get('cargo')==1 and c.get('uf') is None]
assert len(case)==1;case=case[0]
live=json.loads((base/'raw/presidente-2026.json').read_text())
mat={2022:[{'t':case['serie']['t'][i],'pct_secoes':x,
    'proj':{k:v[i] for k,v in case['serie']['proj'].items()}} for i,x in enumerate(case['serie']['pct_secoes'])],2026:live['serie']}
labels={'poststrat':'Pós-estratificação','swing':'Swing','hierarchical':'Hierárquico','mattecca':'Mattecca'}
colors={'poststrat':'#235d9c','swing':'#b76e28','hierarchical':'#6c4c91','mattecca':'#0f766e'}
align=json.loads((base/'alignment.json').read_text())
records=[];milestones=[];convergences=[];curves={};truths={};quality={}

def sustained(points,epsilon):
    # Preserve publication order, including repeated percentages and corrections.
    for i,p in enumerate(points):
        if all(q['error_pp']<=epsilon for q in points[i:]):return p['pct_secoes']
    return None

for year in [2022,2026]:
    aligned=pd.read_parquet(base/f'cpu-aligned-{year}/projections.parquet')
    original=pd.read_parquet(f'reports/cpu-study-20261107/grid-{year}/projections.parquet')
    meta=json.loads((base/f'cpu-aligned-{year}/run.json').read_text())
    before=json.loads(Path(f'reports/cpu-study-20261107/grid-{year}/run.json').read_text())
    assert meta['device']=='cpu' and (meta['reference_year'],meta['reference_turn'],meta['turn'])==(year,1,2)
    assert meta['current_sha256']==before['current_sha256'] and meta['reference_sha256']==before['reference_sha256']
    assert meta['defaults']==before['defaults'] and meta['code_sha256']['models.py']==before['code_sha256']['models.py']
    truth=float(original.final_share_a.iloc[0])*100;truths[year]=truth
    for p in mat[year]:
        assert 0<=p['pct_secoes']<=100 and 0<=p['proj']['Lula']<=100
        p['error_pp']=abs(p['proj']['Lula']-truth)
    assert all(b['pct_secoes']>=a['pct_secoes'] for a,b in zip(mat[year],mat[year][1:]))
    counts=collections.Counter(p['t'] for p in mat[year])
    quality[year]={'records':len(mat[year]),'distinct_percentages':len(set(p['pct_secoes'] for p in mat[year])),
        'most_repeated_timestamp':counts.most_common(1)[0],
        'source_type':'author_published_backtest_by_section' if year==2022 else 'current_public_api_series',
        'live_chronology_verified':False}
    combined=pd.concat([original,aligned],ignore_index=True)
    for method in ['poststrat','swing','hierarchical']:
        f=combined[combined.method.eq(method)].sort_values('fraction_sections').drop_duplicates('fraction_sections')
        points=[{'pct_secoes':float(r.fraction_sections*100),'proj':{'Lula':float(r.share_a*100)},'error_pp':float(r.error_pp)} for r in f.itertuples()]
        curves[year,method]=points
        for epsilon in [1.,.5,.25]:convergences.append({'year':year,'model':method,'epsilon_pp':epsilon,'progress_pct':sustained(points,epsilon),'sample_points':len(points)})
    curves[year,'mattecca']=mat[year]
    for epsilon in [1.,.5,.25]:convergences.append({'year':year,'model':'mattecca','epsilon_pp':epsilon,'progress_pct':sustained(mat[year],epsilon),'sample_points':len(mat[year])})
    for mark,target in zip([1,2,5,10],align['published_target_fractions'][str(year)]):
        index=next(i for i,p in enumerate(mat[year]) if p['pct_secoes']>=mark)
        point=mat[year][index]
        assert abs(point['pct_secoes']/100-target)<1e-12
        subset=aligned[np.isclose(aligned.requested_fraction,target,rtol=0,atol=1e-12)]
        assert len(subset)==3 and subset.fraction_sections.nunique()==1
        actual=float(subset.fraction_sections.iloc[0])*100
        entry={'year':year,'nominal_mark_pct':mark,'mattecca_progress_pct':point['pct_secoes'],'our_progress_pct':actual,
            'mattecca_estimate_pct':point['proj']['Lula'],'final_lula_pct':truth,'mattecca_error_pp':point['error_pp']}
        for r in subset.itertuples():
            entry[r.method+'_error_pp']=float(r.error_pp)
            records.append({'year':year,'nominal_mark_pct':mark,'model':r.method,'source_progress_pct':actual,
                'mattecca_target_progress_pct':point['pct_secoes'],'estimate_lula_pct':float(r.share_a*100),
                'final_lula_pct':truth,'error_pp':float(r.error_pp),'source_index':None,'source_timestamp':None})
        records.append({'year':year,'nominal_mark_pct':mark,'model':'mattecca','source_progress_pct':point['pct_secoes'],
            'mattecca_target_progress_pct':point['pct_secoes'],'estimate_lula_pct':point['proj']['Lula'],
            'final_lula_pct':truth,'error_pp':point['error_pp'],'source_index':index,'source_timestamp':point['t']})
        milestones.append(entry)

pd.DataFrame(records).to_csv(base/'comparison.csv',index=False)
pd.DataFrame(records).to_parquet(base/'comparison.parquet',index=False,compression='zstd')
pd.DataFrame(milestones).to_csv(base/'milestones.csv',index=False)
pd.DataFrame(convergences).to_csv(base/'convergence.csv',index=False)

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2})
fig,axes=plt.subplots(2,2,figsize=(12,7.5),constrained_layout=True)
for col,year in enumerate([2022,2026]):
    for method,label in labels.items():
        points=[p for p in curves[year,method] if p['pct_secoes']>=1]
        xs=[p['pct_secoes'] for p in points]
        axes[0,col].plot(xs,[p['proj']['Lula'] for p in points],color=colors[method],label=label,lw=1.5)
        axes[1,col].plot(xs,[p['error_pp'] for p in points],color=colors[method],lw=1.5)
    axes[0,col].axhline(truths[year],color='#20272b',ls='--',lw=1,label='Resultado final de referência')
    axes[1,col].axhline(.5,color='#20272b',ls=':',lw=1)
    axes[0,col].set_title(f'{year} · projeção de Lula')
    axes[1,col].set_title(f'{year} · erro absoluto')
    axes[0,col].set_ylabel('Votos válidos de Lula (%)');axes[1,col].set_ylabel('Erro (p.p.)')
    for ax in axes[:,col]:ax.set_xlim(0,100);ax.set_xlabel('Seções apuradas (%)')
    axes[1,col].set_ylim(bottom=0)
fig.suptitle('Comparação descritiva: nossos métodos e curva publicada pelo Mattecca\nGrades e conjuntos de urnas diferentes · 2026: horários originais não verificáveis na API',fontsize=12)
handles,names=axes[0,0].get_legend_handles_labels();fig.legend(handles,names,loc='outside lower center',ncols=3,frameon=False)
for ext in ['png','svg']:fig.savefig(base/f'comparison.{ext}',dpi=170)
plt.close(fig)

fmt=lambda x,n=2:f'{x:.{n}f}'.replace('.',',')
lines=['# Comparação com Mattecca: segundo turno de 2022 e 2026','',
 '**Natureza:** comparação descritiva de curvas publicadas e replays. Não é uma avaliação dos quatro modelos sobre os mesmos votos observados.','',
 '## Fontes e alinhamento','',
 '- Mattecca 2022: backtest presidencial, caso `2022-2`, modo por seção, da [API pública de backtests](https://apuracao.mattecca.com.br/api/backtests_cliente). Não é uma projeção que presumimos ter sido publicada em 2022.',
 '- Mattecca 2026: série presidencial disponível na [API pública do painel](https://apuracao.mattecca.com.br/api/estado/presidente). Foram preservados os percentuais, projeções e horários exatamente como consultados.',
 '- Nossos métodos: replays com recebimento de BUs, referência no primeiro turno do mesmo ano, parâmetros fixos. Os arquivos originais da grade CPU foram preservados.',
 '- Para cada marco nominal de 1%, 2%, 5% e 10%, escolhemos o primeiro registro do Mattecca que atinge o marco. Recalculamos nossos três métodos em CPU naquele percentual. Empates dos nossos timestamps podem ultrapassá-lo um pouco; ambos os avanços aparecem na tabela.',
 '- O erro é calculado para Lula, em pontos percentuais, usando um resultado final comum: o resultado validado no nosso dataset. Isso evita comparar erros contra finais de referência diferentes.','',
 f'Referências finais de Lula: **2022 = {fmt(truths[2022],6)}%**; **2026 = {fmt(truths[2026],6)}%**. Não usamos a última parcial bruta do Mattecca como verdade final.','',
 '## Erro nos marcos publicados e alinhados','',
 'Valores em pontos percentuais. As linhas identificam os marcos pedidos; a porcentagem efetivamente disponível pode ser maior. As projeções de Lula e os valores sem arredondamento estão em `comparison.csv`/Parquet.','',
 '| Ano | Marco nominal | Seções Mattecca (%) | Seções nossas (%) | Pós-estratificação | Swing | Hierárquico | Mattecca |',
 '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in milestones:
    lines.append(f'| {r["year"]} | {r["nominal_mark_pct"]}% | {fmt(r["mattecca_progress_pct"])} | {fmt(r["our_progress_pct"],4)} | {fmt(r["poststrat_error_pp"])} | {fmt(r["swing_error_pp"])} | {fmt(r["hierarchical_error_pp"])} | {fmt(r["mattecca_error_pp"])} |')
lines+=['','## Convergência sustentada até erro de 0,5 p.p.','',
 'Primeiro ponto após o qual todos os pontos posteriores da própria série ficam dentro do limite. Cada fonte tem sua grade; não há garantia entre os pontos. Mantivemos os registros repetidos de percentual do Mattecca, inclusive atualizações depois de atingir 100%. Nossas curvas usam a grade original acrescida dos quatro pontos alinhados.','',
 '| Ano | Pós-estratificação | Swing | Hierárquico | Curva Mattecca consultada |','|---|---:|---:|---:|---:|']
for year in [2022,2026]:
    values={r['model']:r['progress_pct'] for r in convergences if r['year']==year and r['epsilon_pp']==.5}
    lines.append('| '+str(year)+' | '+' | '.join(fmt(values[m])+'%' if values[m] is not None else 'Não atingiu' for m in labels)+' |')
lines+=['','![Curvas comparativas, desde o marco de 1%](comparison.png)','',
 '## Limitação decisiva da série de 2026','',
 f'A resposta consultada contém {quality[2026]["records"]} registros. **{quality[2026]["most_repeated_timestamp"][1]} trazem o mesmo horário: {quality[2026]["most_repeated_timestamp"][0]}**, na manhã seguinte à eleição. A lista está ordenada por percentual, mas esses campos não comprovam os horários originais de publicação. Não é possível afirmar, apenas com essa API, que cada projeção corresponde ao que foi exibido ao vivo naquele percentual.',
 '',f'Além disso, a última parcial bruta da API é Lula {fmt(live["ultimo"]["bruto"]["Lula"],3)}%, enquanto o final de referência do nosso dataset é {fmt(truths[2026],6)}%. A última projeção deles é {fmt(live["ultimo"]["proj"]["Lula"],3)}%. Isso reforça que as bases não são idênticas; parcial bruta e projeção não foram confundidas com o resultado final.',
 '', 'Os números de 2026 apresentados neste relatório descrevem a curva atualmente disponibilizada. Não constituem comprovação de desempenho operacional ao vivo nem justificam uma afirmação geral de superioridade.','',
 '## Leitura dos resultados','',
 '- Em 2022, o Mattecca tem erro menor no primeiro e no último dos quatro pontos comparados. Nossos métodos têm erros menores em parte dos pontos intermediários. Na permanência abaixo de 0,5 p.p., a curva publicada pelo Mattecca entra muito antes das nossas curvas.',
 '- Em 2026, nossos métodos têm erros menores nos três primeiros pontos dessa série consultada. Perto de 10%, o nosso swing e o Mattecca ficam próximos, com vantagem numérica pequena para o Mattecca. A anomalia dos horários impede transformar essa observação em uma conclusão sobre a noite ao vivo.',
 '- As diferenças não isolam o efeito do estimador: nossos snapshots seguem recebimento de BUs; o site usa seus dados de totalização e disponibilidade de boletins, com modos por seção/município. Porcentagem de urnas próxima não significa que sejam as mesmas urnas.',
 '- As densidades das grades também diferem. A variação entre pontos não foi usada para ranquear estabilidade entre fontes com frequências distintas. Nossos modelos não produzem os intervalos de incerteza publicados por eles.',
 '- Uma comparação experimental controlada exige executar ambos os modelos sobre exatamente os mesmos snapshots, com o mesmo resultado final e protocolo de calibração. Esta comparação pública não fornece isso.','',
 '## Arquivos e reprodução','',
 '`sources.json` registra URLs, horário de consulta e hashes das respostas originais em `raw/`. `cpu-aligned-<ano>` contém os novos replays CPU, sem apagar a grade original. `milestones.csv`, `comparison.csv`/Parquet e `convergence.csv` preservam os números. `summary.json` registra as métricas e hashes; `verification.json` registra a conferência independente com `verify.py`.','',
 'Reprodução: executar `run_aligned.py`, `compare.py` e `verify.py`, nessa ordem, a partir da raiz do projeto, no ambiente Docker descrito no README. Os dois primeiros reutilizam os arquivos de `raw/` e a grade original; não consultam uma API mutável. Utilizar CPU, runtime `runc`, duas threads, sem expor dispositivos NVIDIA e com o dataset montado somente para leitura.','']
(base/'comparison.md').write_text('\n'.join(lines))
mae=pd.DataFrame(records).groupby(['year','model']).error_pp.mean().reset_index().to_dict('records')
files=[base/'comparison.md',base/'comparison.csv',base/'comparison.parquet',base/'milestones.csv',base/'convergence.csv',base/'comparison.png',base/'comparison.svg',Path(__file__)]
atomic_json(base/'summary.json',{'years':[2022,2026],'truth_lula_pct':truths,'data_quality':quality,
    'milestones':milestones,'sustained_convergence':convergences,'mean_error_selected_points':mae,
    'comparison_type':'descriptive, similar section percentages, not paired snapshots',
    'sha256':{str(p):sha256(p) for p in files}})
print(json.dumps({'milestones':milestones,'convergence_0.5':[r for r in convergences if r['epsilon_pp']==.5],'mean_error':mae},ensure_ascii=False))
