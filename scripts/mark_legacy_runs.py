"""Identify superseded reference configurations without rewriting their artifacts."""
import json
import shutil
from pathlib import Path
from projecao.download import atomic_json

root=Path('reports');entries=[]
for path in sorted(root.glob('*/run.json')):
    meta=json.loads(path.read_text())
    if meta.get('reference_year')==meta.get('year') and meta.get('reference_turn')==1:continue
    entries.append({'directory':path.parent.name,'year':meta.get('year'),'reference_year':meta.get('reference_year'),
        'reference_turn':meta.get('reference_turn',2),'status':'superseded_wrong_reference'})
    (path.parent/'SUPERSEDED.md').write_text('# Configuração descartada\n\nEsta execução usou o segundo turno de uma eleição anterior como referência. Não integra a investigação vigente, que usa exclusivamente o primeiro turno do mesmo ano para projetar seu segundo turno. Os resultados e metadados originais são preservados para auditoria.\n\nConsulte [a metodologia atual](../../docs/metodologia.md) e [o índice de arquivos antigos](../legacy-methodology.md).\n')
atomic_json(root/'legacy-runs.json',{'reason':'Previous-election second-turn reference is outside the intended study','runs':entries})
lines=['# Resultados de configuração descartada','',
 'A metodologia vigente investiga o segundo turno de 2018, 2022 e 2026 usando exclusivamente o **primeiro turno do mesmo ano**. As execuções abaixo usaram o segundo turno de uma eleição anterior; seus resultados não entram nas curvas de erro, tabelas de convergência ou conclusões atuais. Os arquivos originais não foram alterados.','',
 '| Diretório arquivado | Alvo | Referência incorreta |','|---|---:|---|']
lines += [f'| [{r["directory"]}]({r["directory"]}/SUPERSEDED.md) | {r["year"]} | {r["reference_year"]}, 2º turno |' for r in entries]
lines += ['', 'As novas validações usam diretórios `first-turn-reference-<ano>` e registram `reference_year == year`, `reference_turn == 1` e `turn == 2`. Consulte a [metodologia corrigida](../docs/metodologia.md).','']
(root/'legacy-methodology.md').write_text('\n'.join(lines))
runtime=root/'runtime.json'
if runtime.exists() and json.loads(runtime.read_text()).get('reference_turn')!=1:
    archive=root/'legacy-runtime';archive.mkdir(exist_ok=True)
    if not (archive/'runtime.json').exists():shutil.copy2(runtime,archive/'runtime.json')
    (archive/'SUPERSEDED.md').write_text('# Validação CPU/CUDA anterior\n\nA referência usada foi o segundo turno de 2022 para avaliar 2026. Este manifesto está arquivado; a validação corrente em ../runtime.json usa o primeiro turno de 2026.\n')
print(f'{len(entries)} superseded runs identified; original outputs preserved.')
