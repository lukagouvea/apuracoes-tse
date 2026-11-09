"""Audit exported interval quantiles independently of the bootstrap engine."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from projecao.download import atomic_json, sha256

folder = Path('reports/projecoes')
payload = json.loads((folder / 'series.json').read_text())
manifest = json.loads((folder / 'manifest.json').read_text())
for group in ('source_code', 'artifacts'):
    for file, digest in manifest[group].items(): assert sha256(Path(file)) == digest, file
for files in manifest['source_runs'].values():
    for file, digest in files.items(): assert sha256(Path(file)) == digest, file
table = pd.read_parquet(folder / 'intervalos.parquet')
csv = pd.read_csv(folder / 'intervalos.csv')
pd.testing.assert_frame_equal(table, csv, check_dtype=False, atol=1e-14)
replicas = pd.read_parquet(folder / 'replicas.parquet')
assert payload['years'] == [2018, 2022, 2026]
assert set(table.year) == set(payload['years'])
assert len(table) == 927 and len(replicas) == len(table) * payload['interval']['draws']
assert not table.duplicated(['year', 'point_index', 'method']).any()
assert table.turn.eq(2).all() and table.reference_turn.eq(1).all()
assert table.year.eq(table.reference_year).all()
assert np.isfinite(table[['share_a', 'share_b', 'lower_a', 'upper_a', 'lower_b', 'upper_b']].to_numpy()).all()
assert np.allclose(table.lower_b, 1-table.upper_a, atol=1e-14)
assert np.allclose(table.upper_b, 1-table.lower_a, atol=1e-14)
assert table.lower_a.ge(0).all() and table.upper_a.le(1).all() and table.lower_a.le(table.upper_a).all()
assert table.calibrated.eq(False).all()
quantiles = replicas.groupby(['year', 'point_index', 'method']).share_a.quantile([.05, .95]).unstack()
assert len(quantiles) == len(table)
assert replicas.groupby(['year', 'point_index', 'method']).size().eq(payload['interval']['draws']).all()
assert not replicas.duplicated(['year', 'point_index', 'method', 'replicate']).any()
originals = {year: pd.read_parquet(f'reports/cpu-study-20261107/grid-{year}/projections.parquet') for year in payload['years']}
for year, original in originals.items():
    assert len(table[table.year.eq(year)]) == len(original)
    assert len(payload['elections'][str(year)]['points']) == original.observed_sections.nunique()
assert payload['elections']['2018']['reconstructed'] is True
assert payload['elections']['2018']['clock'] == 'Primeira totalização por seção'
for row in table.itertuples():
    q = quantiles.loc[row.year, row.point_index, row.method]
    assert abs(q[.05] - row.lower_a) < 1e-12 and abs(q[.95] - row.upper_a) < 1e-12
    point = payload['elections'][str(row.year)]['points'][row.point_index]
    original = originals[row.year]
    source = original[original.method.eq(row.method) & original.observed_sections.eq(row.observed_sections)]
    assert len(source) == 1 and abs(source.iloc[0].share_a - row.share_a) < 1e-11
    assert point['estimates'][row.method]['share_a'] == source.iloc[0].share_a
    assert point['intervals'][row.method] == {'lower_a': row.lower_a, 'upper_a': row.upper_a}
    if row.fraction_sections == 1:
        assert row.lower_a == row.upper_a == row.final_a
coverage = pd.read_csv(folder / 'cobertura.csv')
for row in coverage.itertuples():
    selected = table[table.year.eq(row.year) & table.method.eq(row.method)]
    if row.scope == 'first_10_percent': selected = selected[selected.requested_fraction <= .1]
    assert row.points == len(selected)
    assert row.covered == int(((selected.lower_a <= selected.final_a) & (selected.upper_a >= selected.final_a)).sum())
resources = json.loads((folder / 'resources.json').read_text())
assert resources['device'] == 'cpu' and resources['cuda_initialized'] is False and resources['gpu_exposed'] is False
result = {'status': 'passed', 'intervals': len(table), 'replicates': len(replicas),
          'quantiles_independently_verified': len(quantiles), 'original_points_preserved': True,
          'csv_parquet_equal': True, 'same_year_first_turn_reference': True,
          'endpoint_collapsed': True, 'coverage_counts_verified': True, 'calibrated': False,
          'gpu_used': False, 'years': payload['years'],
          'chronology_2018': 'first_totalization_reconstruction_with_final_votes', 'sha256': manifest['artifacts']}
atomic_json(folder / 'verification.json', result)
print(json.dumps({k: v for k, v in result.items() if k != 'sha256'}))
