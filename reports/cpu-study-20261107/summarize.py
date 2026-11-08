"""Validate the CPU replay outputs and generate descriptive tables/figures."""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from projecao.download import atomic_json,sha256
from projecao.models import convergence

base=Path('reports/cpu-study-20261107')
years=[2018,2022,2026]
labels={'baseline':'Parcial simples','poststrat':'Pós-estratificação','swing':'Swing','hierarchical':'Hierárquico'}
colors={'baseline':'#737b7c','poststrat':'#235d9c','swing':'#b76e28','hierarchical':'#6c4c91'}
cfg=json.loads(Path('configs/elections.json').read_text())
frames=[];conv_rows=[];one_percent=[]
for year in years:
    folder=base/f'grid-{year}';f=pd.read_parquet(folder/'projections.parquet')
    meta=json.loads((folder/'run.json').read_text())
    assert meta['device']=='cpu' and meta['gpu'] is None
    assert (meta['year'],meta['turn'],meta['reference_year'],meta['reference_turn'])==(year,2,year,1)
    assert set(f.method)=={'poststrat','swing','hierarchical'}
    reference=f[f.method.eq('poststrat')].sort_values('fraction_sections')
    common=['fraction_sections','observed_sections','baseline_share_a','baseline_error_pp']
    for method in ['swing','hierarchical']:
        current=f[f.method.eq(method)].sort_values('fraction_sections')
        pd.testing.assert_frame_equal(reference[common].reset_index(drop=True),current[common].reset_index(drop=True))
    assert len(f[f.fraction_sections.eq(1)])==3
    assert f.loc[f.fraction_sections.eq(1),'error_pp'].eq(0).all()
    baseline=reference.copy();baseline['method']='baseline'
    baseline['share_a']=baseline.baseline_share_a;baseline['error_pp']=baseline.baseline_error_pp
    baseline['share_b']=1-baseline.share_a
    baseline['votes_a']=baseline.share_a*baseline.observed_valid
    baseline['votes_b']=baseline.observed_valid-baseline.votes_a
    baseline['turnout_ratio']=float('nan');baseline['elapsed_seconds']=float('nan')
    display=pd.concat([f,baseline],ignore_index=True);frames.append(display)
    fractions=reference.fraction_sections.to_list()
    one=reference[reference.fraction_sections.ge(.01)].iloc[0]
    for method in labels:
        rows=display[display.method.eq(method)].sort_values('fraction_sections')
        row=rows[rows.fraction_sections.eq(one.fraction_sections)].iloc[0]
        one_percent.append({'year':year,'method':method,'fraction_sections':float(row.fraction_sections),
            'observed_sections':int(row.observed_sections),'estimate_pct':float(row.share_a*100),
            'final_pct':float(row.final_share_a*100),'error_pp':float(row.error_pp)})
        for epsilon in [1.,.5,.25]:
            c=convergence(fractions,rows.error_pp.to_list(),epsilon)
            conv_rows.append({'year':year,'method':method,'epsilon_pp':epsilon,'fraction_sections':c})
all_rows=pd.concat(frames,ignore_index=True)
pd.DataFrame(one_percent).to_csv(base/'at-one-percent.csv',index=False)
pd.DataFrame(conv_rows).to_csv(base/'convergence-comparison.csv',index=False)
all_rows.to_parquet(base/'comparison.parquet',index=False,compression='zstd')

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2})
fig,axes=plt.subplots(2,3,figsize=(13.5,7.5),constrained_layout=True)
for col,year in enumerate(years):
    f=all_rows[all_rows.year.eq(year)]
    for r,xmax in enumerate([100,10]):
        ax=axes[r,col]
        for method,label in labels.items():
            data=f[f.method.eq(method)].sort_values('fraction_sections')
            data=data[data.fraction_sections.le(xmax/100)]
            ax.plot(data.fraction_sections*100,data.error_pp,label=label,color=colors[method],lw=1.5,
                linestyle='--' if method=='baseline' else '-',marker='.',markersize=2)
        ax.axhline(.5,color='#364a43',ls=':',lw=1,label='Limite 0,5 p.p.' if r==col==0 else None)
        ax.set(xlim=(0,xmax),ylim=(0,None),xlabel='Seções reveladas (%)')
        ax.set_title(f'{year} · '+('trajetória completa' if r==0 else 'primeiros 10%'))
        if col==0:ax.set_ylabel('Erro absoluto (p.p.)')
fig.suptitle('Segundo turno: erro da projeção conforme chegam as seções\nReferência exclusiva: primeiro turno do mesmo ano · CPU · parâmetros fixos',fontsize=13)
handles,legend=axes[0,0].get_legend_handles_labels()
fig.legend(handles,legend,loc='outside lower center',ncols=5,frameon=False)
fig.savefig(base/'error-curves.png',dpi=170)
fig.savefig(base/'error-curves.svg')
plt.close(fig)

resources=json.loads((base/'grid-resources.json').read_text())
fmt=lambda value,n=2:f'{value:.{n}f}'.replace('.',',')
lines=['# Testes em CPU: convergência dos três métodos','',
 '**Referência:** primeiro turno do mesmo ano. **Alvos:** segundos turnos de 2018, 2022 e 2026. Ordem histórica auditada: primeira totalização por seção em 2018; recebimento de BUs em 2022/2026.','',
 '## Viabilidade com a GPU ocupada','',
 'O piloto de 2022 foi executado em CPU e a grade completa também. O container não recebeu dispositivos NVIDIA e CUDA não foi inicializado. Limites efetivos: 2 CPUs, 2 GiB de RAM, zero swap adicional e prioridade nice 10. O dataset foi montado somente para leitura. A imagem CUDA existente foi reutilizada, sem reconstrução.','',
 f'A grade dos três anos levou {fmt(resources["wall_seconds"])} segundos, excluindo a inicialização do container e do Python. Pico de RSS do processo: {fmt(max(r["peak_rss_mib"] for r in resources["executions"]),1)} MiB. Esses números são desta execução, com outro treinamento em andamento; não constituem benchmark CPU versus GPU.','',
 'As opções de limite seguem a [documentação do Docker](https://docs.docker.com/engine/containers/resource_constraints/). Também foi definido `CUDA_VISIBLE_DEVICES=-1`, conforme a [documentação do PyTorch](https://docs.pytorch.org/docs/2.15/cuda_environment_variables.html), além da ausência dos dispositivos no container.','',
 '## Protocolo utilizado','',
 '1. Ordenar as seções pelo relógio registrado. Revelar prefixos acumulados: 2% inclui o primeiro 1%. Empates de horário entram juntos.',
 '2. Executar os três métodos sobre exatamente as mesmas seções, mantendo ocultos os demais votos do segundo turno.',
 '3. Comparar projeção e parcial simples com o resultado final, em pontos percentuais. A parcial simples é o controle sem correção.',
 '4. Usar 0,1%, 0,2%, 0,5% e depois 1% a 100%, passo de 1 ponto percentual. Registrar o percentual efetivo quando um empate supera o marco.',
 '5. Medir convergência sustentada: primeiro snapshot após o qual todos os erros seguintes ficam ≤ 1,0, 0,5 ou 0,25 p.p., até 100%. Não basta entrar na faixa uma vez.',
 '6. Manter parâmetros fixos, sem escolher penalizações olhando o resultado final do próprio pleito. Não foram feitos ajustes para favorecer um método.','',
 'Em 100%, os métodos apenas somam votos já conhecidos e devem reproduzir o resultado final. Isso é uma checagem, não sinal de antecipação útil. As conexões entre pontos nas figuras são visuais; as métricas só afirmam comportamento nos snapshots calculados.','',
 '## O que acontece no primeiro 1%','',
 'A é Haddad em 2018 e Lula em 2022/2026. Os percentuais abaixo são dos votos válidos projetados para A. O percentual de seções pode exceder 1% por causa de empates.','',
 '| Ano | Método | Seções efetivas (%) | A estimado (%) | A final (%) | Erro (p.p.) |',
 '|---|---|---:|---:|---:|---:|']
for row in one_percent:
    lines.append(f'| {row["year"]} | {labels[row["method"]]} | {fmt(row["fraction_sections"]*100,4)} | {fmt(row["estimate_pct"])} | {fmt(row["final_pct"])} | {fmt(row["error_pp"])} |')
lines+=['','## Convergência sustentada: limite de 0,5 p.p.','',
 'Percentual efetivo de seções a partir do qual o erro permanece na faixa em toda a grade restante. Os outros limiares estão em `convergence-comparison.csv`.','',
 '| Ano | Parcial simples | Pós-estratificação | Swing | Hierárquico |','|---|---:|---:|---:|---:|']
for year in years:
    values={r['method']:r['fraction_sections'] for r in conv_rows if r['year']==year and r['epsilon_pp']==.5}
    cells=[fmt(values[m]*100)+'%' if values[m] is not None else 'Não atingiu' for m in labels]
    lines.append('| '+str(year)+' | '+' | '.join(cells)+' |')
post18=next(r for r in one_percent if r['year']==2018 and r['method']=='poststrat')
c18={r['method']:r['fraction_sections']*100 for r in conv_rows if r['year']==2018 and r['epsilon_pp']==.5}
lines+=['',
 f'Em 2018, a pós-estratificação já tinha erro de {fmt(post18["error_pp"])} p.p. no marco inicial, mas voltou a sair da faixa: sua convergência sustentada foi em {fmt(c18["poststrat"])}% das seções. O swing, inicialmente menos preciso nesse marco, permaneceu dentro da faixa a partir de {fmt(c18["swing"])}%. Comparar somente o primeiro 1% inverteria essa leitura.',
 '', 'Nesta configuração de parâmetros, o swing nacional atingiu convergência sustentada de 0,5 p.p. antes dos outros dois projetores nos três pleitos. A versão hierárquica não foi automaticamente melhor. Isso descreve estes dados e estes parâmetros, sem demonstrar superioridade universal ou identificar a causa da diferença.','',
 '![Erro ao longo da apuração e detalhe dos primeiros 10%](error-curves.png)','',
 '## Interpretação e próximos cuidados','',
 'A proposta de testar o primeiro 1% é adequada como início. A comparação útil exige seguir a trajetória inteira, pois um método pode acertar cedo e se afastar depois. O critério sustentado resolve isso na resolução da grade. Os limites foram fixados antes de ler estes resultados.','',
 'Os três pleitos são estudos de caso, com relógios de chegada diferentes. Os resultados não demonstram superioridade universal nem intervalos de confiança. Não use reamostragem aleatória de seções como substituto da sequência registrada; ela altera o viés que estamos investigando. Ordens aleatórias podem ser um experimento complementar identificado separadamente.','',
 'Para uma comparação isolada do desempenho computacional, CPU e GPU precisam ser medidas posteriormente em condições controladas, sem o treinamento concorrente. Para testar a qualidade das projeções agora, CPU é suficiente.','',
 '## Arquivos e verificações','',
 '- `grid-<ano>/`: projeções, convergência, metadados e hashes da execução real.',
 '- `at-one-percent.csv`: estimativas e erros do primeiro 1%.',
 '- `convergence-comparison.csv`: os três limiares, incluindo a parcial simples.',
 '- `comparison.parquet`: curvas dos três métodos e da parcial simples. Nas linhas `baseline`, votos A/B são apenas observados; ajuste de comparecimento e tempo do modelo ficam ausentes.',
 '- `grid-resources.json`: limites efetivos, tempos, pico de RAM e confirmação de ausência de CUDA.',
 '- `error-curves.png` e `.svg`: gráficos exportáveis.',
 '- Todos os métodos foram conferidos sobre os mesmos snapshots; os nove endpoints dos modelos reproduzem os resultados finais.','']
(base/'analysis.md').write_text('\n'.join(lines))
atomic_json(base/'summary.json',{'reference_policy':'same_year_first_round','at_one_percent':one_percent,
    'convergence':conv_rows,'resources':resources,'rows':len(all_rows),
    'sha256':{p.name:sha256(p) for p in [base/'analysis.md',base/'comparison.parquet',base/'error-curves.png',base/'error-curves.svg',Path(__file__)]}})
print('One percent:',json.dumps(one_percent,ensure_ascii=False))
print('Convergence <= 0.5 pp:',json.dumps([r for r in conv_rows if r['epsilon_pp']==.5]))
print('Resources:',resources['wall_seconds'],'seconds;',max(r['peak_rss_mib'] for r in resources['executions']),'MiB peak RSS')
