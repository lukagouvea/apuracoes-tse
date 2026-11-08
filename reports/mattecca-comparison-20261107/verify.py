"""Independent numerical/provenance audit of the saved public comparison."""
import collections
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

base = Path('reports/mattecca-comparison-20261107')
summary = json.loads((base / 'summary.json').read_text())
sources = json.loads((base / 'sources.json').read_text())['sources']
for source in sources:
    raw = Path(source['file']).read_bytes()
    assert len(raw) == source['bytes']
    assert hashlib.sha256(raw).hexdigest() == source['sha256']
for filename, digest in summary['sha256'].items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest

cases = json.loads((base / 'raw/backtests.json').read_text())
selected = [c for c in cases if c['caso'] == '2022-2' and c['cargo'] == 1 and c['uf'] is None]
assert len(selected) == 1
case = selected[0]
state = json.loads((base / 'raw/presidente-2026.json').read_text())
points = {
    2022: list(zip(case['serie']['pct_secoes'], case['serie']['proj']['Lula'], case['serie']['t'])),
    2026: [(p['pct_secoes'], p['proj']['Lula'], p['t']) for p in state['serie']],
}
table = pd.read_csv(base / 'comparison.csv')
pd.testing.assert_frame_equal(table, pd.read_parquet(base / 'comparison.parquet'), check_dtype=False)
assert len(table) == 32 and not table.duplicated(['year', 'nominal_mark_pct', 'model']).any()
convergence = pd.read_csv(base / 'convergence.csv')
assert len(convergence) == 24
checked_convergences = 0
for year in (2022, 2026):
    raw_points = points[year]
    assert all(b[0] >= a[0] for a, b in zip(raw_points, raw_points[1:]))
    quality = summary['data_quality'][str(year)]
    assert len(raw_points) == quality['records']
    assert len(set(p[0] for p in raw_points)) == quality['distinct_percentages']
    most_common = collections.Counter(p[2] for p in raw_points).most_common(1)[0]
    assert list(most_common) == quality['most_repeated_timestamp']
    original_dir = Path(f'reports/cpu-study-20261107/grid-{year}')
    aligned_dir = base / f'cpu-aligned-{year}'
    original = pd.read_parquet(original_dir / 'projections.parquet')
    aligned = pd.read_parquet(aligned_dir / 'projections.parquet')
    old = json.loads((original_dir / 'run.json').read_text())
    new = json.loads((aligned_dir / 'run.json').read_text())
    assert (new['year'], new['turn'], new['reference_year'], new['reference_turn']) == (year, 2, year, 1)
    assert new['device'] == 'cpu'
    for key in ('current_sha256', 'reference_sha256', 'defaults'):
        assert new[key] == old[key]
    for filename in ('data.py', 'models.py', 'experiment.py', 'study.py'):
        assert new['code_sha256'][filename] == old['code_sha256'][filename]
        assert hashlib.sha256((Path('src/projecao') / filename).read_bytes()).hexdigest() == new['code_sha256'][filename]
    truth = float(original.final_share_a.iloc[0]) * 100
    assert math.isclose(truth, summary['truth_lula_pct'][str(year)], abs_tol=1e-12)
    assert len(aligned) == 15
    for row in table[table.year.eq(year)].itertuples():
        index = next(i for i, point in enumerate(raw_points) if point[0] >= row.nominal_mark_pct)
        published_pct, published_estimate, timestamp = raw_points[index]
        assert row.mattecca_target_progress_pct == published_pct
        if row.model == 'mattecca':
            assert (row.source_progress_pct, row.estimate_lula_pct, row.source_index, row.source_timestamp) == (published_pct, published_estimate, index, timestamp)
        else:
            matches = aligned[aligned.method.eq(row.model) & (aligned.requested_fraction.sub(published_pct / 100).abs() < 1e-12)]
            assert len(matches) == 1
            run = matches.iloc[0]
            assert math.isclose(row.estimate_lula_pct, run.share_a * 100, abs_tol=1e-12)
            assert math.isclose(row.source_progress_pct, run.fraction_sections * 100, abs_tol=1e-12)
            assert row.source_progress_pct >= published_pct
        assert math.isclose(row.final_lula_pct, truth, abs_tol=1e-12)
        assert math.isclose(row.error_pp, abs(row.estimate_lula_pct - truth), abs_tol=1e-12)
    combined = pd.concat([original, aligned], ignore_index=True)
    for model in ('poststrat', 'swing', 'hierarchical', 'mattecca'):
        if model == 'mattecca':
            progress = [p[0] for p in raw_points]
            errors = [abs(p[1] - truth) for p in raw_points]
        else:
            frame = combined[combined.method.eq(model)].sort_values('fraction_sections').drop_duplicates('fraction_sections')
            progress = (frame.fraction_sections * 100).tolist()
            errors = (frame.share_a * 100 - truth).abs().tolist()
        for epsilon in (1., .5, .25):
            bad = [i for i, error in enumerate(errors) if error > epsilon]
            start = max(bad, default=-1) + 1
            expected = progress[start] if start < len(progress) else None
            recorded = convergence[convergence.year.eq(year) & convergence.model.eq(model) & convergence.epsilon_pp.eq(epsilon)]
            assert len(recorded) == 1 and recorded.iloc[0].sample_points == len(progress)
            actual = recorded.iloc[0].progress_pct
            assert (expected is None and pd.isna(actual)) or math.isclose(expected, actual, abs_tol=1e-10)
            checked_convergences += 1

result = {
    'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'passed', 'raw_sources_hashed': len(sources),
    'comparison_rows_verified': len(table), 'csv_parquet_equal': True,
    'aligned_cpu_model_rows_verified': 30, 'convergences_verified': checked_convergences,
    'same_year_first_turn_reference': True, 'unchanged_estimator_parameters_and_core_code': True,
    'figure_visually_inspected': True, 'paired_snapshots': False,
    'mattecca_2026_live_chronology_verified': False,
}
(base / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
