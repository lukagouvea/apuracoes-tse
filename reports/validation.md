# Validação e armazenamento

Inventário medido em 2026-11-08T00:52:26.440568+00:00. Dados em `/mnt/ssd1tb/inf425-tse/`.

Estudo vigente: **segundos turnos de 2018, 2022 e 2026**, com referência exclusivamente no **primeiro turno do próprio ano**. O inventário inclui também o acervo anterior, preservado no SSD e fora dos modelos. Consulte a [metodologia](../docs/metodologia.md).

| Conteúdo | MiB |
|---|---:|
| ZIPs presidenciais, seis eleições | 800.69 |
| ZIPs de resumos oficiais independentes | 2113.16 |
| Históricos de totalização agregada e PDF2014 | 10.91 |
| Boletins de segundo turno (2014–2026) | 313.49 |
| Detalhe por seção (2006, 2010, 2014, 2018) | 439.34 |
| Parquets de análise e ordens | 119.15 |
| **Total, incluindo dependências e manifestos** | **3968.96** |

Os Parquets usam Zstandard e o recorte presidencial. Não há cópia descompactada permanente dos CSVs. A imagem CUDA já existente é compartilhada; não foi duplicada. Reserva operacional: manter 10 GiB livres, como exige o downloader. A reserva de 10 GiB é adicional ao espaço ocupado pelos arquivos. Para reproduzir somente 2018/2022/2026, reserve 20 GiB livres; outras coleções e novas publicações podem exigir mais.

| Ano | Papel no estudo | Seções no dataset | Votos válidos 2º turno | Totais independentes | Ordem histórica | Parquet (MiB) |
|---|---|---:|---:|---|---|---:|
| 2006 | Acervo | 361,406 | 95,838,220 | matched | Sem BU no catálogo consultado | 6.48 |
| 2010 | Acervo | 399,962 | 99,463,917 | matched | Sem BU no catálogo consultado | 6.93 |
| 2014 | Acervo | 428,852 | 105,542,273 | matched | Sem campo de recebimento verificável | 8.63 |
| 2018 | Avaliação 2º / referência 1º | 454,448 | 104,838,753 | matched | Primeira totalização por seção (reconstrução) | 40.80 |
| 2022 | Avaliação 2º / referência 1º | 472,028 | 118,552,353 | matched | Recebimento BU, cobertura 100% | 28.11 |
| 2026 | Avaliação 2º / referência 1º | 499,205 | 124,082,273 | matched | Recebimento BU, cobertura 100% | 28.20 |

## Referências do primeiro turno

| Ano | Seções 1º turno | Válidos 1º turno | Votos A | Votos B | Outros candidatos |
|---|---:|---:|---:|---:|---:|
| 2018 | 454,450 | 107,050,749 | 31,342,051 | 49,277,010 | 26,431,688 |
| 2022 | 472,028 | 118,229,719 | 57,259,504 | 51,072,345 | 9,897,870 |
| 2026 | 499,206 | 119,306,034 | 53,879,538 | 56,104,503 | 9,321,993 |

A preferência usa A1/(A1+B1). O volume usa todos os válidos do primeiro turno, incluindo os candidatos eliminados, e seu próprio número de seções. Os hashes do Parquet e do ZIP são verificados antes de cada experimento.

2014 também possui 333 parciais nacionais em PDF, sem ordem por seção, mas não alimenta os estimadores atuais. Em 2010, cinco observações documentais estão preservadas separadamente e não constituem série temporal completa. A cobertura refere-se às seções presentes no dataset oficial baixado. Seções ausentes da publicação não são inventadas; esse denominador pode diferir do número de seções previstas pelo TSE. Recebimento BU não equivale a totalização oficial; reconstrução por primeira totalização também não recupera correções intermediárias. As ordens preservam os timestamps publicados, sem reinterpretá-los como UTC.

## Verificações

- Os totais por finalista são confrontados com outro recurso oficial: votação nominal por município/zona.
- Testes automatizados: leiautes moderno/legado, votos inválidos e seções com zero válidos, matrizes singulares, fallback histórico, VT/exterior, empates, cobertura, conflitos e checksum da ordem, ausência de vazamento e CPU/CUDA.
- Todas as execuções com referência no segundo turno de eleições anteriores estão descartadas da metodologia vigente e identificadas em [legacy-methodology.md](legacy-methodology.md); seus arquivos originais foram preservados.
- Novas validações em `reports/first-turn-reference-2018`, `-2022` e `-2026`: referência no primeiro turno do mesmo ano, três métodos e cronologia registrada do segundo turno. 2018 preserva oito datas de 2019.
- Grades curtas: 1%, 2%, 5%, 10% e 100%. Convergência reportada apenas nessa resolução, sem interpretação de curva completa.
- Grade recomendada para a análise científica atual: 1% a 100%, passo de 1 p.p., em 2018/2022/2026. As validações curtas não substituem essa análise.
- Guia `reports/metodos.html`: 858 estados fictícios calculados pela API real, com dados e hashes separados; não são resultados eleitorais.
- `reports/runtime.json` registra matriz CUDA real e comparação CPU/GPU sobre um snapshot oficial de 5% de 2026.
- Os parâmetros são iniciais e fixos; não houve calibração contra os resultados das eleições avaliadas.

- Primeira grade completa em CPU: 103 snapshots por método/ano e 927 projeções, com referência correta e parcial simples; [análise e gráficos](cpu-study-20261107/analysis.md). Sem dispositivos GPU no container, 2 CPUs e 2 GiB de limite de RAM.
