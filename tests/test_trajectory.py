import unittest
from projecao.results import trajectory_metrics


class TrajectoryTests(unittest.TestCase):
    def test_irregular_spacing_uses_progress_not_snapshot_count(self):
        r = trajectory_metrics([.01, .02, .1], [.5, .52, .5], .5, .01, .1)
        self.assertAlmostEqual(r['mean_absolute_error_pp'], 2 * .08 / .09)
        self.assertAlmostEqual(r['error_area_pp_fraction'], 2 * .08)
        self.assertAlmostEqual(r['within_fraction']['0.5'], .01 / .09)
        self.assertAlmostEqual(r['total_variation_pp'], 2)
        self.assertAlmostEqual(r['amplitude_pp'], 2)

    def test_boundaries_use_last_known_value_and_exclude_end_jump(self):
        r = trajectory_metrics([.005, .025, .07, .1], [.51, .52, .50, .8], .5, .01, .1)
        self.assertAlmostEqual(r['error_area_pp_fraction'], .015 + 2 * .045)
        self.assertAlmostEqual(r['total_variation_pp'], 3)
        self.assertAlmostEqual(r['within_fraction']['1.0'], .045 / .09)

    def test_constant_biased_curve_is_stable_but_inaccurate(self):
        r = trajectory_metrics([.01, .1], [.6, .5], .5, .01, .1)
        self.assertAlmostEqual(r['mean_absolute_error_pp'], 10)
        self.assertEqual(r['total_variation_pp'], 0)
        self.assertEqual(r['amplitude_pp'], 0)
        self.assertEqual(r['within_fraction']['0.5'], 0)

    def test_no_extrapolation_before_first_snapshot(self):
        self.assertFalse(trajectory_metrics([.02, 1], [.5, .5], .5, .01, .1)['available'])

    def test_invalid_or_uncovered_trajectory_is_rejected(self):
        for xs, ys in [([.1,.1],[.5,.5]), ([.1,1],[float('nan'),.5]), ([.1],[.5,.5])]:
            with self.assertRaises(ValueError): trajectory_metrics(xs, ys, .5, .1, 1)
        with self.assertRaises(ValueError): trajectory_metrics([.01,.05], [.5,.5], .5, .01,.1)
