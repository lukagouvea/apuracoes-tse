# Pesquisa de cronologia eleitoral — fontes recuperadas

> **Registro da investigação.** A [metodologia vigente](metodologia.md) avalia somente 2018/2022/2026. Cada segundo turno usa o primeiro turno do mesmo ano; 2014 fica apenas no acervo; as lacunas de 2010/2014 descritas abaixo não bloqueiam esse recorte. Dados recuperados continuam preservados no SSD.

**Atualização: 7 de novembro de 2026.** A busca foi ampliada após a primeira inspeção dos BUs. Os novos resultados substituem a afirmação anterior de que o acervo só permitia curvas para 2022 e 2026.

## O que conseguimos recuperar

| Ano | Dados temporais confirmados | Uso possível | Lacuna restante |
|---|---|---|---|
| **2018** | Horário de recebimento e de primeira totalização parcial por seção no arquivo de detalhe do TSE. | Reconstrução por seção e experimentos com ordem registrada. Cobertura de 100% das 454.448 seções do dataset; votos nominais conferidos seção a seção. | Resultados finais colocados na primeira totalização não recuperam correções intermediárias ou publicação na internet. |
| **2014** | PDF original do TSE com **333 observações nacionais** de horário e votos dos finalistas. | Série nacional por horário preservada em Parquet/CSV no acervo; fora do HTML e do replay vigentes. | O PDF não informa seções nem ordem territorial: não permite alimentar os três estimadores com snapshots por seção. |
| **2010** | **Cinco parciais documentadas** em publicações contemporâneas; quatro com votos inteiros e uma com votos arredondados. | Conferência documental e pontos nacionais esparsos. | Não há série densa ou ordem por seção verificada nesta busca. Horários das notícias não são automaticamente horários da totalização. |
| **2006** | Publicação estatística do TSE preservada com percentuais de avanço em intervalos de meia hora. | Material auxiliar do acervo, fora da avaliação e das referências atuais. | Não fornece a evolução dos votos dos candidatos. |

**Consequência adotada:** os experimentos com ordem registrada avaliam **2018, 2022 e 2026**, identificando a natureza de cada reconstrução. O acervo nacional de 2014 e os pontos de 2010 permanecem auxiliares. Uma ampliação futura para esses anos exigiria cronologia territorial adicional; simulações não devem ser apresentadas como apurações históricas.

## 2018: a informação estava em outro recurso oficial

Fonte: [Detalhe da votação por seção — TSE, ZIP](https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2018.zip), listado no [catálogo oficial de resultados de 2018](https://dadosabertos.tse.jus.br/dataset/resultados-2018).

Campos encontrados:

- `DT_RECEBIMENTO_BU_HOR_TSE`: horário de recebimento.
- `DT_PRIM_TOT_PARCIAL_HOR_TSE`: horário da primeira totalização parcial, usado na reconstrução.

Esses campos não estavam nos BUs examinados inicialmente. A primeira busca foi incompleta por não ter inspecionado o arquivo de detalhe por seção.

A extração prefere o membro federal `_BR.csv`; os arquivos por UF e o membro `BRASIL` podem repetir seus registros. A união usa UF, município, zona e seção, com cardinalidade 1:1. Os votos finais A+B precisam coincidir com `QT_VOTOS_NOMINAIS` em todas as seções incluídas.

| Verificação | Resultado |
|---|---:|
| Seções presidenciais no detalhe federal | 454.490 |
| Seções presentes no dataset de votos usado pelo projeto | 454.448 |
| Seções do dataset sem horário correspondente | 0 |
| Divergências de votos nominais por seção | 0 |
| Horários distintos na reconstrução nacional | 1.554 |
| Seções com data de fevereiro de 2019 | 8 |
| Votos válidos nessas oito seções | 1.712 |

As 42 seções adicionais do detalhe ficam fora do universo de votação já definido; não recebem votos inventados. As oito datas de 2019 são mantidas. Não foi determinada a razão administrativa desses registros. O HTML usa eixo percentual fixo e preserva todo o acervo; os horários originais permanecem nas atualizações e na exportação CSV.

Arquivos produzidos no SSD:

```text
raw/2018/detail/detalhe_votacao_secao_2018.zip
processed/2018/section_timing.parquet
processed/2018/order.parquet
processed/2018/chronology.json
```

O manifesto registra `reconstructed_from_final_votes: true` e `exact_published_partials: false`. A execução de validação está em [`reports/historical-2018-first-totalization`](../reports/historical-2018-first-totalization).

## 2014: PDF nacional original recuperado

- [Endereço oficial atual do PDF no TSE](https://www.tse.jus.br/comunicacao/noticias/arquivos/evolucao-da-totalizacao-para-presidente-no-2o-turno-de-2014/@@display-file/file/tse-evolucao-totalizacao-presidente-2-turno-2014.pdf).
- [Cópia do endereço oficial antigo preservada pelo Internet Archive](https://web.archive.org/web/20210731123238id_/https://www.tse.jus.br/imprensa/noticias-tse/arquivos/evolucao-da-totalizacao-para-presidente-no-2o-turno-de-2014/at_download/file).
- [Coleção independente que ajudou a localizar a fonte e sua transcrição](https://numerosdaeleicao.com.br/fontes).

O endereço atual respondeu HTTP 403 neste ambiente. Recuperamos os **bytes do documento original arquivado**, e não apenas uma transcrição de terceiros: **282.892 bytes, nove páginas**. O SHA-256 coincide com a referência previamente recuperada pela coleção independente; isso identifica os mesmos bytes, sem constituir assinatura digital ou checksum oficial anunciado pelo TSE.

```text
d1b7b52fe9dfca7cc7333daf580afb11133b9af09facdb91b5b126aa2b637b15
```

A tabela tem seis colunas: horário de totalização, votos de Dilma, percentual de Dilma, votos de Aécio, percentual de Aécio e votos válidos. Foram extraídas **333 linhas**, de **26/10/2014 às 17h01** até **27/10/2014 às 02h13**.

Em cada linha, verificamos a soma dos votos e os percentuais dentro da tolerância de arredondamento de duas casas. O último registro coincide exatamente com os totais já auditados: **54.501.118** e **51.041.155** votos.

**Seções permanecem desconhecidas.** `sections`, `sections_total` e `fraction_sections` são nulos nessa série. O HTML mantém o eixo percentual fixo: em 2014 informa a limitação em vez de desenhar uma curva por horário. Os 333 registros permanecem disponíveis para exportação CSV.

Arquivos preservados:

```text
raw/2014/totals/tse-evolucao-totalizacao-presidente-2-turno-2014.pdf
manifests/2014-totals-pdf.json
processed/2014/national_totalization.parquet
research/2014-pdf-provenance.json
```

## 2010: pontos reais, ainda insuficientes para uma série completa

Os horários abaixo são os de **publicação das notícias**. Não atribuímos esses horários à totalização sem evidência adicional.

| Publicação em 31/10/2010 | Urnas informadas | Dilma | Serra | Precisão dos votos |
|---|---:|---:|---:|---|
| [19h11 — Folha](https://m.folha.uol.com.br/poder/2010/10/823415-com-7209-urnas-apuradas-dilma-tem-5316-dos-votos-e-serra-4684.shtml) | 72,09% | 38.942.560 | 34.318.516 | Inteiros publicados. |
| [19h25 — Senado](https://www12.senado.leg.br/noticias/materias/2010/10/31/dilma-lidera-apuracao-com-5321-contra-4679-de-serra) | 73,01% | 39,49 milhões | 34,73 milhões | Arredondados na fonte; não convertidos em inteiros exatos. |
| [21h31 — Folha](https://www1.folha.uol.com.br/poder/2010/10/823535-com-9914-da-apuracao-dilma-chega-aos-55-milhoes-de-votos.shtml) | 99,14% | 55.229.355 | 43.456.857 | Inteiros publicados. |
| [22h11 — Folha](https://m.folha.uol.com.br/poder/2010/10/823563-em-seu-primeiro-pronunciamento-dilma-destaca-papel-das-mulheres.shtml) | 99,34% | 55.354.520 | 43.514.344 | Inteiros publicados. |
| [22h58 — Folha](https://m.folha.uol.com.br/poder/2010/10/823587-serra-vence-em-sao-paulo-com-54-dos-votos-validos.shtml) | 99,90% | 55.691.882 | 43.686.875 | Inteiros publicados; 22h30 no corpo do texto refere-se a São Paulo. |

O percentual é de **urnas**, conforme a notícia. Não o renomeamos como percentual exato de seções. Há grandes lacunas entre os pontos. Não interpolamos uma trajetória, não criamos ponto final com horário presumido e não usamos esse conjunto para calcular convergência sustentada dos três métodos.

Os dados estão em `processed/2010/documented_partials.parquet` e `.csv`. Os votos arredondados e os horários de totalização desconhecidos são campos nulos, com os textos publicados e a proveniência preservados em `research/2010-documented-leads.json`.

Também foi recuperada uma publicação estatística oficial de 2010, mas sua tabela de acompanhamento trata de **2002 e 2006**. Ela não foi usada como série de 2010.

## O que foi pesquisado e o que falta pedir

Foram conferidos os catálogos CKAN, BUs já baixados, detalhes por seção de 2006/2010/2014/2018, documentos originais do TSE, capturas do Internet Archive, coleções independentes e publicações contemporâneas. O detalhe por seção de 2006, 2010 e 2014 não contém os campos de horário encontrados em 2018.

Isso não prova que o TSE não detenha registros adicionais. Uma eventual ampliação da comparação por seção para 2010/2014 dependeria de uma extração oficial desses anos; o recorte atual de 2018/2022/2026 já tem ordem auditada. A [minuta de solicitação dos dados](solicitacao-dados-tse.md) especifica os campos e distingue relógios, correções e granularidades.
