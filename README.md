# Projeção eleitoral — INF425

Três estimadores em Python/Torch para investigar a convergência da projeção do **segundo turno presidencial**, conforme aumenta o **percentual de urnas/seções apuradas**. Cada pleito usa exclusivamente o **primeiro turno do mesmo ano** como referência.

| Avaliação | Referência | Finalistas |
|---|---|---|
| 2018 · 2º turno | 2018 · 1º turno | Fernando Haddad / Jair Bolsonaro |
| 2022 · 2º turno | 2022 · 1º turno | Lula / Jair Bolsonaro |
| 2026 · 2º turno | 2026 · 1º turno | Lula / Flávio Bolsonaro |

O modelo recebe somente os votos revelados até cada snapshot. O final fica no avaliador, para calcular erro e convergência. Consulte a [metodologia](docs/metodologia.md) e a [especificação visual com Mermaid](docs/especificacao.md).

## Abrir as páginas prontas

Os quatro HTMLs estão no Git e funcionam offline. Abra-os diretamente no navegador, sem instalar Python nem baixar os dados.

| Página | Conteúdo |
|---|---|
| [Projeções com faixa sombreada](reports/projecoes.html) | Parcial, projeção e faixa experimental; hover/toque, três anos/modelos e exportação CSV/SVG. |
| [Convergência e estabilidade](reports/convergencia.html) | Trajetórias, erros, oscilações e tabela de 1%, 2%, 5% e 10%. |
| [Apuração dos candidatos](reports/apuracao.html) | Parciais de votação; eixo X sempre em percentual de seções. |
| [Guia dos métodos](reports/metodos.html) | Exemplos fictícios interativos e contas dos três estimadores. |

Mantenha as pastas de apoio de `reports/` junto dos HTMLs: elas contêm CSV/Parquet e figuras para download. Os dados para desenhar as curvas estão incorporados nas páginas.

**As faixas sombreadas são experimentais:** o bootstrap atual apresentou cobertura baixa e subestima fontes importantes de incerteza. Seus quantis 5–95% não representam uma margem eleitoral calibrada de 90%. Essa limitação e a cobertura observada aparecem no painel.

## O que está no Git

```text
configs/                 # Anos, finalistas e protocolo
src/projecao/            # Download, preparação, auditoria e modelos
scripts/                 # Ambiente, reprodução e geradores dos HTMLs
tests/                   # Testes automatizados
templates/               # Fontes das páginas
reproducibility/         # Catálogos, hashes e evidências do ambiente CPU
reports/                 # Páginas e resultados selecionados
docs/                    # Metodologia, esquemas e especificação
```

Entram código, configurações, testes, documentação, propostas originais, os quatro HTMLs e os arquivos que sustentam suas curvas. Os Parquets pequenos de **resultados** e as respostas públicas usadas na comparação com Mattecca também são preservados.

Os **ZIPs e Parquets de entrada do TSE**, imagens Docker, ambientes Python, `.env`, capturas de QA e execuções antigas descartadas ficam fora do Git. Novas execuções podem ser gravadas em `reports/runs/`, que é ignorado.

## 1. Preparar o ambiente CPU

Requisitos: Docker Engine com Compose v2 e execução de imagens **Linux x86_64** (`linux/amd64`). A imagem usa Python **3.11.15**, Torch **2.12.0+cpu**, NumPy **2.4.4**, Pandas **3.0.3**, PyArrow **23.0.0** e Matplotlib **3.10.9**.

```bash
cp .env.example .env
# Edite TSE_DATA_ROOT no .env para apontar para seu SSD/disco de dados.
# O padrão desta máquina é /mnt/ssd1tb/inf425-tse.

./scripts/cpu.sh build
./scripts/cpu.sh --read-only -m unittest discover -s tests -v
```

[Dockerfile.cpu](Dockerfile.cpu) fixa a imagem Python por digest. [requirements-reproduce.txt](requirements-reproduce.txt) fixa as dependências; [requirements-torch-cpu.txt](requirements-torch-cpu.txt) contém URL e SHA-256 do wheel oficial do Torch CPU. A [validação numérica](reproducibility/cpu-validation.json) registra o teste desse wheel contra as projeções originais.

[compose.cpu.yaml](compose.cpu.yaml) usa `runc`, não expõe GPU e limita os replays a duas CPUs, duas threads e 2 GiB de RAM. A preparação no serviço `tools` tem limite de 6 GiB de RAM e 8 GiB contando swap; recomenda-se uma máquina com pelo menos 8 GiB de RAM para essa etapa. O serviço `experiment` mantém o limite de 2 GiB. O wrapper aplica seu UID/GID. Dentro do container, o projeto está em `/workspace` e o dataset em `/data/tse`.

- `./scripts/cpu.sh ...`: executa Python com o dataset para escrita, para download/preparação.
- `./scripts/cpu.sh --read-only ...`: dataset somente para leitura, para experimentos/verificações.

## 2. Baixar os dados do TSE

O snapshot contém **65 ZIPs**, totalizando **2.518 GiB**, e cinco catálogos oficiais. Reserve **20 GiB livres** para dados, Parquets, ambiente e margem operacional. O downloader exige manter pelo menos **10 GiB livres** durante o download. Os CSVs são processados sem extração permanente no disco.

Em uma pasta de dataset **nova**, copie primeiro os catálogos congelados para utilizar as URLs registradas neste estudo.

```bash
# Rejeita manifestos locais diferentes; não sobrescreve um acervo existente.
./scripts/cpu.sh scripts/dataset_snapshot.py seed

# Votos dos dois turnos, resumo independente e históricos agregados.
./scripts/cpu.sh -m projecao download --years 2018 2022 2026 --kinds votes summary totals

# Fonte da cronologia de 2018.
./scripts/cpu.sh -m projecao download --years 2018 --kinds detail

# Ordem de recebimento dos BUs em 2022/2026.
./scripts/cpu.sh -m projecao download --years 2022 2026 --kinds bu

# Confere os arquivos com os hashes preservados no Git.
./scripts/cpu.sh --read-only scripts/dataset_snapshot.py verify
```

Os [manifestos congelados](reproducibility/tse-manifests/) registram URLs, nomes, datas, tamanhos e SHA-256. As fontes são `dadosabertos.tse.jus.br` e `cdn.tse.jus.br`. O download passa por `.part`, verifica tamanho/formato/hash e reaproveita arquivos completos conferidos.

2018 não tem um ZIP de histórico nacional selecionado pelo catálogo; o comando pode informar essa indisponibilidade, pois sua curva usa o detalhe por seção. Se `verify` apontar diferença de hash, a fonte recebida mudou: preserve essa informação e não a trate como a mesma base dos resultados registrados.

Para um acervo já existente, execute somente `verify`; `seed` rejeita manifestos diferentes. Os demais anos continuam suportados no acervo do código, mas os experimentos atuais aceitam apenas 2018/2022/2026.

## 3. Preparar Parquet e auditar

```bash
./scripts/cpu.sh -m projecao prepare --years 2018 2022 2026
./scripts/cpu.sh -m projecao audit --years 2018 2022 2026

# Se a base já existia e falta apenas a referência do primeiro turno:
./scripts/cpu.sh -m projecao prepare-reference --years 2018 2022 2026
```

`prepare` lê em blocos, seleciona Presidente, preserva os dois turnos e prepara a referência do primeiro. `audit` confere os totais contra o resumo municipal independente e valida a cronologia: cobertura integral das seções do dataset, sem duplicatas ou horários inválidos.

```text
TSE_DATA_ROOT/
  raw/<ano>/{votes,summary,totals,bu,detail}/
  processed/<ano>/
    votes.parquet                 # Votos presidenciais dos dois turnos
    universe.parquet              # Identificadores das seções do segundo turno
    sections.parquet              # Votos A/B por seção do segundo turno
    first_turn_sections.parquet   # A/B/outros e todos os válidos do primeiro
    first_turn_reference.json     # Ano/turno, totais e hashes
    order.parquet                 # Ordem auditada do replay
    section_timing.parquet        # Em 2018: horários oficiais por seção
    preparation.json
    totals-check.json
    chronology.json
  manifests/
```

**A** é o finalista do PT; **B**, o outro finalista. A preferência municipal usa `A1/(A1+B1)`. O volume utiliza **todos os válidos do primeiro turno**, incluindo candidatos eliminados. O histórico é agregado por município, sem pareamento de seções entre turnos. Exterior e seções sem válidos permanecem no universo conforme os arquivos oficiais.

O [dicionário dos dados](docs/dados.md) detalha colunas, tipos, chaves e exemplos.

## 4. Repetir os experimentos

A grade contém **0,1%, 0,2%, 0,5% e 1%–100%**, passo de 1 ponto percentual: 103 snapshots × três modelos × três anos = **927 projeções**.

```bash
# Escolha uma saída ainda inexistente; os resultados registrados são preservados.
./scripts/cpu.sh --read-only scripts/reproduce.py \
  --output reports/runs/reproducao-01 \
  --compare-to reports/cpu-study-20261107
```

O script executa os três pleitos em CPU, exige os mesmos snapshots e compara as projeções com tolerância de `1e-10` na proporção de A. `reproduction.json` registra Torch, dispositivo, tempo, memória e diferenças. Tempos e metadados variam por máquina; a comparação é numérica.

Para executar um ano pela CLI:

```bash
# Cinco marcos: 1%, 2%, 5%, 10% e 100%.
./scripts/cpu.sh --read-only -m projecao experiment \
  --year 2022 --device cpu --mode historical \
  --output reports/runs/2022-curto

# Acrescentar uma grade de 1 ponto percentual.
./scripts/cpu.sh --read-only -m projecao experiment \
  --year 2022 --device cpu --mode historical --grid-step .01 \
  --output reports/runs/2022-grade

# Ordem aleatória, explicitamente simulada.
./scripts/cpu.sh --read-only -m projecao smoke \
  --year 2018 --device cpu --mode simulated --seed 42 \
  --output reports/runs/2018-simulado
```

`--milestones` recebe frações, como `.01 .02 .05 .1 1`. Seções com o mesmo horário entram juntas; o percentual efetivo pode ultrapassar o marco solicitado. O replay histórico não preenche lacunas com uma ordem artificial.

| Saída | Conteúdo |
|---|---|
| `projections.csv` / `projections.parquet` | Projeções A/B, parcial simples, erro, marco pedido/efetivo e tempo. |
| `run.json` | Anos/turnos, parâmetros, fontes, hashes, versões, dispositivo e cronologia. |
| `convergence.json` | Primeiro ponto após o qual o erro permanece abaixo de 1,0/0,5/0,25 p.p. |

**Cronologia:** 2018 revela votos finais na primeira totalização registrada por seção, incluindo oito registros tardios de fevereiro de 2019. 2022/2026 usam recebimento de BUs. Esses relógios diferem do instante de publicação das parciais ao público. A convergência vale na resolução da grade calculada.

## 5. Como usar e entender os modelos

Todos reajustam a projeção a cada snapshot. Os votos conhecidos ficam fixos; o modelo estima os votos pendentes e soma as parcelas.

| Método | Estimativa dos votos pendentes |
|---|---|
| `poststrat` — pós-estratificação | Preferência municipal observada; sem votos locais, recorre à UF e depois ao nível nacional. |
| `swing` | WLS nacional da mudança entre turnos: intercepto, preferência dos finalistas no primeiro turno e log do volume municipal de válidos. |
| `hierarchical` | Mesmas covariáveis, com ajuste nacional → região → UF e Ridge aproximando grupos com pouca evidência do nível superior. |

O volume pendente usa válidos históricos por seção e fator nacional de comparecimento suavizado. As penalizações iniciais são **300 mil** votos-equivalentes para região, **150 mil** para UF e **200 mil** para comparecimento. Estão em `Config`, sem calibração contra o resultado alvo. Matrizes sem posto completo usam pseudoinversa; proporções ficam em `[0,1]`.

A API é `predict(snapshot, history, Config(...))`, em [models.py](src/projecao/models.py). `make_history` recebe a referência do primeiro turno e os identificadores estruturais do segundo; `build_snapshot` agrega somente as seções reveladas. Em 100%, os modelos reproduzem o total observado. Não há pesquisas eleitorais externas no prior.

O [guia interativo](reports/metodos.html) explica os mecanismos com 858 estados fictícios. A [especificação](docs/especificacao.md) traz diagramas e equações; os exemplos didáticos não medem desempenho eleitoral.

## 6. Regenerar as páginas

Os comandos usam dados auditados ou resultados registrados. Sobrescrevem as páginas e arquivos correspondentes; confira as alterações com Git.

```bash
./scripts/cpu.sh --read-only scripts/build_apuracao.py
./scripts/cpu.sh --read-only scripts/build_metodos.py
./scripts/cpu.sh --read-only scripts/build_convergencia.py
./scripts/cpu.sh --read-only scripts/build_projecoes.py --render-only

# Apresentar uma nova grade no painel de convergência:
./scripts/cpu.sh --read-only scripts/build_convergencia.py \
  --runs-root reports/runs/reproducao-01
```

O painel com faixas usa `reports/cpu-study-20261107`. Sem `--render-only`, o gerador utiliza/prepara o cache de 200 refits por snapshot; protocolo e hashes precisam coincidir. A [descrição dos intervalos](reports/projecoes/README.md) explica a reamostragem e a cobertura baixa. O final entra somente na avaliação retrospectiva das faixas.

## 7. Imagem GPU original

[compose.yaml](compose.yaml) e [scripts/container.sh](scripts/container.sh) preservam a imagem local do TCC:

```text
sha256:bddd3bf9b9e44eee13044ba2afe85a757c1e5009e94bfba5701facf600465c63
Python 3.11.15 · Torch 2.12.0.dev20260407+cu128 · CUDA 12.8 · RTX 5060/sm_120
```

É necessário ter essa imagem importada localmente, driver NVIDIA e NVIDIA Container Toolkit. O ID é local, não uma imagem pública que `docker pull` possa obter. Para repetir exatamente esse ambiente, obtenha a imagem original por `docker save`/`docker load`; o arquivo da imagem fica fora do Git. A alternativa CPU pública funciona sem esse artefato.

```bash
docker image inspect sha256:bddd3bf9b9e44eee13044ba2afe85a757c1e5009e94bfba5701facf600465c63
./scripts/container.sh setup
./scripts/container.sh up -d app
./scripts/container.sh run --rm experiment experiment \
  --year 2026 --device cuda --mode historical --grid-step .01 \
  --output reports/runs/2026-gpu
```

`setup` instala dependências em `TSE_DATA_ROOT/runtime/python`, sem substituir Torch. O serviço `experiment` monta o dataset somente para leitura. Para CPU com a GPU ocupada, use `scripts/cpu.sh`.

## 8. Conferências e referências

```bash
./scripts/cpu.sh --read-only -m unittest discover -s tests -v
./scripts/cpu.sh --read-only scripts/check_projecoes.py
./scripts/cpu.sh --read-only reports/mattecca-comparison-20261107/verify.py
```

Os testes cobrem dados, referências, fallback, seções sem válidos, matrizes singulares, ordem auditada, ausência de vazamento, endpoints e refits. As auditorias usam os Parquets e hashes registrados.

QA de navegador é opcional: exige Node.js, **Playwright 1.62.1** e Google Chrome em `/usr/bin/google-chrome`. Os verificadores desabilitam aceleração GPU.

```bash
npm install --no-save --package-lock=false playwright@1.62.1
node scripts/check_metodos.cjs
node scripts/check_visuals.cjs --html-only
node scripts/check_convergencia.cjs
node scripts/check_projecoes.cjs
node scripts/check_projecoes_tooltip.cjs
```

- [Portal do TSE](https://dadosabertos.tse.jus.br/) e [manifestos congelados](reproducibility/tse-manifests/).
- [Instalações oficiais anteriores do PyTorch](https://pytorch.org/get-started/previous-versions/), origem do ambiente CPU público.
- [Primeira análise CPU](reports/cpu-study-20261107/analysis.md) e [inventário](reports/validation.md).
- [Comparação com Mattecca, 2022/2026](reports/mattecca-comparison-20261107/comparison.md): descritiva, com bases/grades diferentes e ressalva sobre horários de 2026.
- [Pesquisa da cronologia](docs/pesquisa-cronologia.md), [proposta original](proposta_projeto.pdf) e [guia técnico](guia_tecnico.pdf).
- [Projeto de João Gallo](https://github.com/joaogallo/projecao-apuracao-eleicoes): referência conceitual; os modelos deste repositório são uma implementação própria.
