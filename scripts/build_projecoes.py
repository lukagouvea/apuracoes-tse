"""Compute conditional bootstrap bands and build an offline election chart."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from projecao.data import SECTION, make_history, load_first_turn_reference
from projecao.experiment import load_historical_order, reveal_order
from projecao.download import atomic_json, sha256
from projecao.models import Config
from projecao.results import prepare_election, METHODS
from projecao.study import evaluation_years
from projecao.uncertainty import bootstrap_intervals

FOLDER = Path('reports/projecoes')
LABELS = {'poststrat': 'Pós-estratificação', 'swing': 'Swing', 'hierarchical': 'Hierárquico'}


def compute(root, draws, seed):
    started = time.perf_counter(); elections = {}; rows = []; samples = []; sources = {}; coverages = []
    computed_intervals = 0; reused_intervals = 0
    for year in evaluation_years():
        run = Path(f'reports/cpu-study-20261107/grid-{year}')
        metadata = json.loads((run / 'run.json').read_text())
        election = prepare_election(pd.read_parquet(run / 'projections.parquet'), metadata)
        cfg = metadata['elections_config'][str(year)]
        reference, _ = load_first_turn_reference(root, year, (cfg['candidate_a'], cfg['candidate_b']))
        current_path = root / 'processed' / str(year) / 'sections.parquet'
        current = pd.read_parquet(current_path)
        assert sha256(current_path) == metadata['current_sha256']
        assert sha256(root / 'processed' / str(year) / 'first_turn_sections.parquet') == metadata['reference_sha256']
        assert Config().__dict__ == metadata['defaults']
        history = make_history(reference, current[SECTION])
        order, _ = load_historical_order(root, year, current)
        ordered = reveal_order(current, order)
        sources[str(year)] = {str(p): sha256(p) for p in (run / 'run.json', run / 'projections.parquet')}
        protocol = {'draws': draws, 'seed': seed, 'coverage': .9,
                    'uncertainty_code': sha256(Path('src/projecao/uncertainty.py')),
                    'model_code': sha256(Path('src/projecao/models.py')),
                    'data_code': sha256(Path('src/projecao/data.py')),
                    'current_sha256': metadata['current_sha256'], 'reference_sha256': metadata['reference_sha256'],
                    'source_runs': sources[str(year)]}
        assert protocol['model_code'] == metadata['code_sha256']['models.py']
        cache_path = FOLDER / f'bootstrap-{year}.json'
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {'protocol': protocol, 'snapshots': {}}
        if cache['protocol'] != protocol: raise ValueError('Incompatible bootstrap cache; preserve it and choose a new folder')
        for i, point in enumerate(election['points']):
            end = point['observed_sections']; key = str(end)
            if key not in cache['snapshots']:
                observed = ordered.iloc[:end][SECTION + ['votes_a', 'votes_b']]
                assert end == len(ordered) or ordered.batch.iloc[end - 1] != ordered.batch.iloc[end]
                result = bootstrap_intervals(observed, history, draws=draws, seed=seed + year * 1000 + i, return_samples=True)
                cache['snapshots'][key] = result
                atomic_json(cache_path, cache)
                computed_intervals += len(METHODS)
            else:
                reused_intervals += len(METHODS)
            result = cache['snapshots'][key]
            point['intervals'] = {}; point['unobserved_municipalities'] = result['pending_municipalities_without_observations']
            point['one_section_municipalities'] = result['one_section_municipalities']
            for method in METHODS:
                p = result['methods'][method]
                assert abs(p['share_a'] - point['estimates'][method]['share_a']) < 1e-11
                point['intervals'][method] = {'lower_a': p['lower_a'], 'upper_a': p['upper_a']}
                row = {'year': year, 'turn': 2, 'reference_year': year, 'reference_turn': 1,
                       'point_index': i, 'method': method, 'observed_sections': end,
                       'requested_fraction': point['requested_fraction'], 'fraction_sections': point['fraction'],
                       'partial_a': point['baseline_share'], 'share_a': p['share_a'],
                       'lower_a': p['lower_a'], 'upper_a': p['upper_a'],
                       'share_b': 1 - p['share_a'], 'lower_b': 1 - p['upper_a'], 'upper_b': 1 - p['lower_a'],
                       'final_a': election['final_a'], 'nominal_coverage': .9,
                       'draws': draws, 'seed': result['seed'], 'calibrated': False,
                       'unobserved_municipalities': point['unobserved_municipalities'],
                       'one_section_municipalities': point['one_section_municipalities']}
                rows.append(row)
                for replicate, share in enumerate(result['samples_a'][method]):
                    samples.append({'year': year, 'point_index': i, 'method': method, 'replicate': replicate, 'share_a': share})
            if i % 10 == 0 or i == len(election['points']) - 1:
                print(f'{year}: {i+1}/{len(election["points"])} snapshots; {time.perf_counter()-started:.1f}s', flush=True)
        elections[str(year)] = election
    table = pd.DataFrame(rows)
    table.to_parquet(FOLDER / 'intervalos.parquet', index=False, compression='zstd')
    table.to_csv(FOLDER / 'intervalos.csv', index=False)
    pd.DataFrame(samples).to_parquet(FOLDER / 'replicas.parquet', index=False, compression='zstd')
    for (year, method), group in table.groupby(['year', 'method']):
        for scope, selected in [('all', group), ('first_10_percent', group[group.requested_fraction <= .1])]:
            coverages.append({'year': int(year), 'method': method, 'scope': scope, 'points': len(selected),
                              'covered': int(((selected.lower_a <= selected.final_a) & (selected.upper_a >= selected.final_a)).sum()),
                              'median_width_pp': float((selected.upper_a - selected.lower_a).median() * 100)})
    pd.DataFrame(coverages).to_csv(FOLDER / 'cobertura.csv', index=False)
    payload = {'years': list(evaluation_years()), 'methods': LABELS, 'elections': elections,
               'interval': {'coverage': .9, 'draws': draws, 'base_seed': seed, 'calibrated': False,
                            'kind': 'municipal_stratified_fractional_weight_bootstrap'},
               'sources': sources, 'coverage_audit': coverages}
    atomic_json(FOLDER / 'series.json', payload)
    assert not torch.cuda.is_initialized()
    atomic_json(FOLDER / 'resources.json', {'device': 'cpu', 'gpu_exposed': False, 'cuda_initialized': False,
        'seconds': time.perf_counter() - started, 'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'threads': torch.get_num_threads(), 'projection_intervals': len(table), 'replicates': len(samples),
        'computed_intervals': computed_intervals, 'reused_intervals': reused_intervals})
    return payload


def render(payload):
    output = Path('reports/projecoes.html'); template = Path('templates/projecoes.html')
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    output.write_text(template.read_text().replace('__PROJECTION_DATA__', encoded))
    code = [Path(__file__), template, Path('src/projecao/uncertainty.py'), Path('src/projecao/models.py')]
    artifacts = [output, *[p for p in FOLDER.iterdir() if p.name in ('series.json', 'intervalos.csv', 'intervalos.parquet', 'replicas.parquet', 'cobertura.csv', 'resources.json')]]
    atomic_json(FOLDER / 'manifest.json', {'years': payload['years'], 'interval': payload['interval'],
        'source_runs': payload['sources'], 'source_code': {str(p): sha256(p) for p in code},
        'artifacts': {str(p): sha256(p) for p in artifacts}})
    print(f'{output}: {len(payload["years"])} years, 3 methods, experimental bootstrap bands, offline.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/data/tse'))
    parser.add_argument('--draws', type=int, default=200)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--compute-only', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    FOLDER.mkdir(parents=True, exist_ok=True)
    payload = json.loads((FOLDER / 'series.json').read_text()) if args.render_only else compute(args.root, args.draws, args.seed)
    if not args.compute_only: render(payload)
