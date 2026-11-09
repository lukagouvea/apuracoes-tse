"""Build the offline experiment entry point from the versioned results/code."""
from pathlib import Path
import hashlib
import html
import json


def build():
    root = Path(__file__).resolve().parents[1]
    study = json.loads((root / 'configs/study.json').read_text())
    data = json.loads((root / 'reports/convergencia/series.json').read_text())
    snapshot = json.loads((root / 'reproducibility/tse-snapshot.json').read_text())
    code = (root / 'src/projecao/models.py').read_text()
    rows = []
    for year in study['evaluation_years']:
        e = data['elections'][str(year)]
        if (e['reference_year'], e['reference_turn']) != (year, 1):
            raise ValueError('Expected the first turn of the same year')
        rows.append('<tr><th scope="row">'+str(year)+'</th><td>'+html.escape(e['name_a'])+'</td><td>'+html.escape(e['name_b'])+'</td><td>'+f'{e["points"][-1]["observed_sections"]:,}'.replace(',', '.')+'</td></tr>')
    replacements = {
        '__MODELS_SOURCE__': html.escape(code),
        '__MODELS_SHA__': hashlib.sha256(code.encode()).hexdigest(),
        '__YEARS_TABLE__': ''.join(rows),
        '__PROJECTION_COUNT__': str(data['model_projections']),
        '__SNAPSHOT_COUNT__': str(len(next(iter(data['elections'].values()))['points'])),
        '__RAW_FILES__': str(snapshot['raw_files']),
        '__RAW_GIB__': f'{snapshot["raw_bytes"] / 1024**3:.2f}'.replace('.', ','),
    }
    result = (root / 'templates/experimento.html').read_text()
    for token, value in replacements.items(): result = result.replace(token, value)
    (root / 'index.html').write_text(result)
    print('index.html: experiment, four pages, reproduction and actual models.py; offline.')


if __name__ == '__main__': build()
