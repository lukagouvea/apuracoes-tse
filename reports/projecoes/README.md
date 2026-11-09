# Faixas condicionais de incerteza

O HTML `../projecoes.html` mostra as parciais e os três estimadores de segundo turno de 2018, 2022 e 2026. A referência continua sendo o primeiro turno do próprio ano. Os pontos são os mesmos da grade CPU original. Em 2018, os finalistas são Fernando Haddad e Jair Bolsonaro; a reconstrução revela votos finais na primeira totalização por seção, incluindo oito registros de fevereiro de 2019. Em 2022/2026, o relógio é o recebimento de BUs.

As linhas de projeção têm tooltip por hover/toque: candidato, modelo/ano, projeção, parcial, faixa experimental e percentual efetivo do snapshot. Os valores são os do snapshot calculado mais próximo. A tooltip acompanha a cor do candidato, ajusta sua posição à tela e fecha ao sair, trocar o contexto ou pressionar Escape. O gráfico também aceita foco e setas para consultar snapshots/candidatos pelo teclado. Isso não altera os dados ou intervalos.

Cada snapshot recebe 200 réplicas de bootstrap ponderado. Para cada seção já recebida sorteia-se um peso exponencial de média 1, normalizado dentro do município para preservar seu número de seções recebidas. A mesma réplica é utilizada pelos três métodos. Os modelos são reajustados aos totais municipais reponderados; apenas a parcela pendente desses refits varia. Os votos já recebidos permanecem fixos no total projetado. O intervalo pontual vai dos quantis 5% a 95%; em 100% não há votos pendentes e a faixa se reduz ao resultado conhecido.

Esse procedimento mede sensibilidade às seções observadas, sob a hipótese de que elas informam as pendentes do mesmo município. Não simula erros sistemáticos de chegada nem perfis inteiramente ausentes. Municípios com uma seção recebida não têm variabilidade local na distribuição empírica; o painel mostra quantos são. A faixa pode ser estreita e não conter o final real. Não foi calibrada para cobertura eleitoral de 90%, não é banda simultânea da trajetória e não é a implementação do Mattecca.

O resultado final não entra na função que calcula as faixas. `cobertura.csv` mede retrospectivamente se ele ficou dentro de cada intervalo; essa inspeção não modifica os limites. Snapshots de um mesmo pleito são dependentes: a fração coberta não é estimativa de desempenho em eleições independentes.

- `intervalos.csv`/Parquet: 927 intervalos, pontos, parciais, finais de avaliação, seeds e percentuais efetivos.
- `replicas.parquet`: valores das 200 réplicas por intervalo, para conferir os quantis.
- `bootstrap-<ano>.json`: cache auxiliar local, fora do Git; dispensável para abrir o painel ou auditar quantis.
- `series.json`: dados incorporados no HTML.
- `manifest.json`: hashes de dados, código e artefatos.
- `resources.json`: consumo CPU e confirmação de CUDA não inicializado.

Geração: `scripts/build_projecoes.py`, no container CPU com o SSD somente para leitura. `--compute-only` calcula; `--render-only` recria apenas o HTML. Os anos vêm de `configs/study.json`. A configuração padrão usa 200 réplicas, seed base 42 e duas threads. São 185.400 réplicas. As projeções originais permanecem nos Parquets da grade CPU. A auditoria `scripts/check_projecoes.py` confere os pontos e calcula os quantis independentemente a partir das réplicas preservadas.

Base estatística: [Rubin (1981), The Bayesian Bootstrap](https://people.eecs.berkeley.edu/~jordan/sail/readings/rubin.pdf), [documentação do bootstrap ponderado](https://ngreifer.github.io/fwb/reference/fwb.html). Estratificação municipal e preservação dos votos conhecidos são decisões deste projeto.
