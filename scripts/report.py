"""Build a compact, measured inventory from persisted manifests (no network)."""
import json
from pathlib import Path
from datetime import datetime, timezone
from projecao.download import atomic_json, YEARS
from projecao.study import load_study

root=Path('/data/tse'); base=Path('reports'); study=load_study()
read=lambda p:json.loads(p.read_text()) if p.exists() else {}
rows=[]
for y in YEARS:
    d=root/'processed'/str(y); prep=read(d/'preparation.json'); check=read(d/'totals-check.json'); chrono=read(d/'chronology.json')
    files=[p for p in (root/'raw'/str(y)).rglob('*') if p.is_file() and p.suffix in {'.zip','.pdf'}]
    role='Avaliação 2º / referência 1º' if y in study['evaluation_years'] else 'Acervo'
    reference=read(d/'first_turn_reference.json')
    row={'year':y,'study_role':role,'raw_bytes':sum(p.stat().st_size for p in files),
      'parquet_bytes':sum(p.stat().st_size for p in d.glob('*.parquet')),
      'sections':prep.get('sections'),'valid_votes':prep.get('valid_votes'),
      'votes_a':prep.get('votes_a'),'votes_b':prep.get('votes_b'),
      'totals_status':check.get('status'),'chronology_status':chrono.get('status'),'chronology_field':chrono.get('source_time_field'),
      'historical_usable':chrono.get('usable',False),'chronology_coverage':chrono.get('coverage'),
      'source_sha256':prep.get('source_sha256'),
      'first_turn_reference':reference if y in study['evaluation_years'] else None}
    rows.append(row)
category={k:sum(p.stat().st_size for p in (root/'raw').glob(f'*/{k}/*') if p.is_file() and p.suffix in {'.zip','.pdf'}) for k in ['votes','summary','totals','bu','detail']}
all_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
report={'generated_at':datetime.now(timezone.utc).isoformat(),'root':str(root),'study':study,'categories':category,
 'parquet_bytes':sum(x['parquet_bytes'] for x in rows),'all_files_bytes':all_bytes,'years':rows}
atomic_json(base/'inventory.json',report)
lines=['# Validação e armazenamento','',f'Inventário medido em {report["generated_at"]}. Dados em `/mnt/ssd1tb/inf425-tse/`.','',
 'Estudo vigente: **segundos turnos de 2018, 2022 e 2026**, com referência exclusivamente no **primeiro turno do próprio ano**. O inventário inclui também o acervo anterior, preservado no SSD e fora dos modelos. Consulte a [metodologia](../docs/metodologia.md).','',
 '| Conteúdo | MiB |','|---|---:|']
labels={'votes':'ZIPs presidenciais, seis eleições','summary':'ZIPs de resumos oficiais independentes','totals':'Históricos de totalização agregada e PDF2014','bu':'Boletins de segundo turno (2014–2026)','detail':'Detalhe por seção (2006, 2010, 2014, 2018)'}
lines += [f'| {labels[k]} | {v/1024**2:.2f} |' for k,v in category.items()]
lines += [f'| Parquets de análise e ordens | {report["parquet_bytes"]/1024**2:.2f} |',
 f'| **Total, incluindo dependências e manifestos** | **{all_bytes/1024**2:.2f}** |','',
 'Os Parquets usam Zstandard e o recorte presidencial. Não há cópia descompactada permanente dos CSVs. A imagem CUDA já existente é compartilhada; não foi duplicada. Reserva operacional: manter 10 GiB livres, como exige o downloader. A reserva de 10 GiB é adicional ao espaço ocupado pelos arquivos. Para reproduzir somente 2018/2022/2026, reserve 20 GiB livres; outras coleções e novas publicações podem exigir mais.','',
 '| Ano | Papel no estudo | Seções no dataset | Votos válidos 2º turno | Totais independentes | Ordem histórica | Parquet (MiB) |',
 '|---|---|---:|---:|---|---|---:|']
for r in rows:
    c=('Primeira totalização por seção (reconstrução)' if r.get('chronology_field') else 'Recebimento BU, cobertura 100%') if r['historical_usable'] else ('Sem campo de recebimento verificável' if r['chronology_status']=='no_reception_timestamp' else 'Sem BU no catálogo consultado')
    lines.append(f'| {r["year"]} | {r["study_role"]} | {r["sections"]:,} | {r["valid_votes"]:,} | {r["totals_status"]} | {c} | {r["parquet_bytes"]/1024**2:.2f} |')
lines += ['', '## Referências do primeiro turno','',
 '| Ano | Seções 1º turno | Válidos 1º turno | Votos A | Votos B | Outros candidatos |',
 '|---|---:|---:|---:|---:|---:|']
for r in rows:
    ref=r['first_turn_reference']
    if ref:
        lines.append(f'| {r["year"]} | {ref["sections"]:,} | {ref["valid_votes"]:,} | {ref["votes_a"]:,} | {ref["votes_b"]:,} | {ref["votes_other"]:,} |')
lines += ['', 'A preferência usa A1/(A1+B1). O volume usa todos os válidos do primeiro turno, incluindo os candidatos eliminados, e seu próprio número de seções. Os hashes do Parquet e do ZIP são verificados antes de cada experimento.','',
 '2014 também possui 333 parciais nacionais em PDF, sem ordem por seção, mas não alimenta os estimadores atuais. Em 2010, cinco observações documentais estão preservadas separadamente e não constituem série temporal completa. A cobertura refere-se às seções presentes no dataset oficial baixado. Seções ausentes da publicação não são inventadas; esse denominador pode diferir do número de seções previstas pelo TSE. Recebimento BU não equivale a totalização oficial; reconstrução por primeira totalização também não recupera correções intermediárias. As ordens preservam os timestamps publicados, sem reinterpretá-los como UTC.','',
 '## Verificações','',
 '- Os totais por finalista são confrontados com outro recurso oficial: votação nominal por município/zona.',
 '- Testes automatizados: leiautes moderno/legado, votos inválidos e seções com zero válidos, matrizes singulares, fallback histórico, VT/exterior, empates, cobertura, conflitos e checksum da ordem, ausência de vazamento e CPU/CUDA.',
 '- Todas as execuções com referência no segundo turno de eleições anteriores estão descartadas da metodologia vigente e identificadas em [legacy-methodology.md](legacy-methodology.md); seus arquivos originais foram preservados.',
 '- Novas validações em `reports/first-turn-reference-2018`, `-2022` e `-2026`: referência no primeiro turno do mesmo ano, três métodos e cronologia registrada do segundo turno. 2018 preserva oito datas de 2019.',
 '- Grades curtas: 1%, 2%, 5%, 10% e 100%. Convergência reportada apenas nessa resolução, sem interpretação de curva completa.',
 '- Grade recomendada para a análise científica atual: 1% a 100%, passo de 1 p.p., em 2018/2022/2026. As validações curtas não substituem essa análise.',
 '- Guia `reports/metodos.html`: 858 estados fictícios calculados pela API real, com dados e hashes separados; não são resultados eleitorais.',
 '- `reports/runtime.json` registra matriz CUDA real e comparação CPU/GPU sobre um snapshot oficial de 5% de 2026.',
 '- Os parâmetros são iniciais e fixos; não houve calibração contra os resultados das eleições avaliadas.','']
if (base/'cpu-study-20261107/summary.json').exists():
    lines += ['- Primeira grade completa em CPU: 103 snapshots por método/ano e 927 projeções, com referência correta e parcial simples; [análise e gráficos](cpu-study-20261107/analysis.md). Sem dispositivos GPU no container, 2 CPUs e 2 GiB de limite de RAM.','']
(base/'validation.md').write_text('\n'.join(lines))
print(json.dumps(report,indent=2))
