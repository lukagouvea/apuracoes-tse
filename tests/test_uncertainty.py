import unittest
import numpy as np
import pandas as pd
from projecao.models import Config, History, Snapshot, predict
from projecao.data import build_snapshot
from projecao.uncertainty import ReplicateProjector, bootstrap_intervals


def fixture():
    history = History(pd.DataFrame({
        'uf': ['SP', 'SP', 'BA', 'BA', 'ZZ'], 'municipality': ['1', '2', '3', '4', '5'],
        'region': ['SE', 'SE', 'NE', 'NE', 'EX'], 'n_sections': [4, 4, 4, 4, 4],
        'ref_share': [.6, .4, .7, .3, .5], 'ref_per_section': [100.] * 5,
        'ref_size': [400., 600., 800., 900., 500.], 'matched': [True] * 5,
    }))
    observed = pd.DataFrame({
        'uf': ['SP', 'SP', 'BA', 'BA'], 'municipality': ['1', '1', '3', '3'],
        'zone': ['0001'] * 4, 'section': ['0001', '0002', '0001', '0002'],
        'votes_a': [90, 10, 80, 20], 'votes_b': [10, 90, 20, 80],
    })
    return history, observed


class UncertaintyTests(unittest.TestCase):
    def test_batched_refits_match_existing_estimators_with_fixed_observed_votes(self):
        h, observed = fixture(); snapshot = build_snapshot(observed)
        engine = ReplicateProjector(h, snapshot)
        rng = np.random.default_rng(12)
        a = rng.uniform(50, 190, (7, 5)); b = rng.uniform(50, 190, (7, 5))
        a[:, [1, 3, 4]] = 0; b[:, [1, 3, 4]] = 0
        for method in ('poststrat', 'swing', 'hierarchical'):
            for penalty in (0., 150_000.):
                cfg = Config(method=method, lambda_uf=penalty, lambda_region=penalty)
                actual = engine.predict(a, b, cfg)
                for i in range(len(a)):
                    pseudo = snapshot.frame.copy()
                    pseudo['votes_a'] = pseudo.municipality.map({'1': a[i, 0], '3': a[i, 2]})
                    pseudo['votes_b'] = pseudo.municipality.map({'1': b[i, 0], '3': b[i, 2]})
                    projection = predict(Snapshot(pseudo), h, cfg)
                    pending_a = projection.votes_a - pseudo.votes_a.sum()
                    pending_b = projection.votes_b - pseudo.votes_b.sum()
                    expected = (200 + pending_a) / (400 + pending_a + pending_b)
                    self.assertAlmostEqual(actual[i], expected, places=11, msg=f'{method=} {penalty=} {i=}')

    def test_known_votes_are_not_randomized_in_the_projected_result(self):
        h = History(pd.DataFrame({'uf': ['SP'], 'municipality': ['1'], 'region': ['SE'],
            'n_sections': [2], 'ref_share': [.5], 'ref_per_section': [100.],
            'ref_size': [200.], 'matched': [True]}))
        s = Snapshot(pd.DataFrame({'uf': ['SP'], 'municipality': ['1'],
            'n_observed': [1], 'votes_a': [60], 'votes_b': [40]}))
        result = ReplicateProjector(h, s).predict(np.array([[0.]]), np.array([[100.]]), Config())
        self.assertAlmostEqual(result[0], .3)

    def test_intervals_reproducible_variable_and_do_not_mutate_input(self):
        h, observed = fixture(); original = observed.copy(deep=True)
        first = bootstrap_intervals(observed, h, draws=100, seed=9, batch_size=7)
        second = bootstrap_intervals(observed, h, draws=100, seed=9, batch_size=20)
        for method in ('poststrat', 'swing', 'hierarchical'):
            p = first['methods'][method]; q = second['methods'][method]
            self.assertAlmostEqual(p['lower_a'], q['lower_a'], places=12)
            self.assertAlmostEqual(p['upper_a'], q['upper_a'], places=12)
            self.assertLess(p['lower_a'], p['upper_a'])
            self.assertTrue(0 <= p['lower_a'] <= p['upper_a'] <= 1)
            expected = predict(build_snapshot(observed), h, Config(method=method)).share_a
            self.assertAlmostEqual(p['share_a'], expected, places=12)
        pd.testing.assert_frame_equal(observed, original)

    def test_at_full_count_every_interval_collapses_to_known_result(self):
        h, observed = fixture()
        h = History(h.frame.iloc[[0, 2]].assign(n_sections=2))
        result = bootstrap_intervals(observed, h, draws=40)
        for p in result['methods'].values():
            self.assertEqual(p['share_a'], .5)
            self.assertEqual(p['lower_a'], .5)
            self.assertEqual(p['upper_a'], .5)

    def test_zero_valid_or_empty_sample_does_not_claim_uncertainty_is_zero(self):
        h, observed = fixture()
        for sample in (observed.iloc[:0], observed.assign(votes_a=0, votes_b=0)):
            result = bootstrap_intervals(sample, h, draws=40)
            for p in result['methods'].values():
                self.assertIsNone(p['lower_a']); self.assertIsNone(p['upper_a'])

    def test_invalid_draw_settings_and_duplicate_sections_rejected(self):
        h, observed = fixture()
        for kwargs in ({'draws': 10}, {'coverage': 1}, {'batch_size': 0}):
            with self.assertRaises(ValueError): bootstrap_intervals(observed, h, **kwargs)
        with self.assertRaises(ValueError): bootstrap_intervals(pd.concat([observed, observed]), h)

    def test_singular_design_and_zero_reference_volume_remain_finite(self):
        h, observed = fixture()
        h.frame['ref_share'] = .5; h.frame['ref_size'] = 100.
        h.frame.loc[4, 'ref_per_section'] = 0
        result = bootstrap_intervals(observed, h, draws=40)
        for p in result['methods'].values():
            self.assertTrue(np.isfinite([p['share_a'], p['lower_a'], p['upper_a']]).all())


if __name__ == '__main__': unittest.main()
