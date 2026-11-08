"""Replay the complete three-year CPU grid into a new output directory."""
import argparse
import json
from pathlib import Path
import resource
import time
import numpy as np
import pandas as pd
import torch
from projecao.download import atomic_json
from projecao.experiment import run_experiment
from projecao.study import evaluation_years


def reproduce(root, output, compare_to=None):
    if output.exists(): raise ValueError(f'Output already exists: {output}; use a new directory')
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    config = json.loads(Path('configs/elections.json').read_text())
    marks = [.001, .002, .005] + [i / 100 for i in range(1, 101)]
    started = time.perf_counter(); runs = []
    for year in evaluation_years():
        folder = output / f'grid-{year}'
        rows = run_experiment(root, year, config, folder, device='cpu', mode='historical', milestones=marks)
        entry = {'year': year, 'rows': len(rows), 'snapshots': len(rows) // 3}
        if compare_to is not None:
            original = pd.read_parquet(compare_to / f'grid-{year}/projections.parquet').sort_values(['method', 'observed_sections']).reset_index(drop=True)
            current = pd.DataFrame(rows).sort_values(['method', 'observed_sections']).reset_index(drop=True)
            assert current[['method', 'observed_sections', 'fraction_sections']].equals(original[['method', 'observed_sections', 'fraction_sections']])
            difference = float(np.max(np.abs(current.share_a.to_numpy() - original.share_a.to_numpy())))
            entry['max_share_a_difference'] = difference
            if difference > 1e-10: raise ValueError(f'{year}: numeric comparison failed: {difference}')
        runs.append(entry)
    assert not torch.cuda.is_initialized()
    summary = {'device': 'cpu', 'torch': torch.__version__, 'cuda_initialized': False,
               'reference_policy': 'same_year_first_round', 'years': list(evaluation_years()),
               'seconds': time.perf_counter() - started,
               'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
               'compared_to': str(compare_to) if compare_to is not None else None, 'runs': runs}
    atomic_json(output / 'reproduction.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/data/tse'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-to', type=Path)
    args = parser.parse_args()
    reproduce(args.root, args.output, args.compare_to)
