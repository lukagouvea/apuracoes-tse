import unittest
from projecao.didactic import poststrat_case,swing_case,hierarchy_case

class DidacticTests(unittest.TestCase):
    def test_poststrat_worked_example(self):
        p=poststrat_case(2,2)
        self.assertAlmostEqual(p['projection'],1400/3000)
        self.assertAlmostEqual(p['baseline'],.5)
        self.assertEqual(p['remaining_a'],1200)

    def test_poststrat_empty_and_complete(self):
        self.assertIsNone(poststrat_case(0,0)['baseline'])
        self.assertAlmostEqual(poststrat_case(0,0)['projection'],.5)
        self.assertEqual(poststrat_case(10,20)['remaining_valid'],0)

    def test_swing_five_points_learns_five_points(self):
        p=swing_case(5)
        self.assertAlmostEqual(p['target_prediction'],.45)
        self.assertAlmostEqual(p['projection'],.525)
        self.assertAlmostEqual(p['baseline'],.55)

    def test_hierarchy_shrinks_and_accounts_for_all_votes(self):
        p=hierarchy_case(10,1500)
        self.assertTrue(p['region_swing']<p['state_swing']<.2)
        self.assertAlmostEqual(p['state_swing'],p['weight']*.2+(1-p['weight'])*p['region_swing'])
        self.assertAlmostEqual(p['projection'],(p['observed_a']+p['remaining_valid']*p['target_prediction'])/30000)
        self.assertAlmostEqual(hierarchy_case(100,1500)['projection'],.55)
        z=hierarchy_case(0,1500)
        self.assertIsNone(z['observed_sp_share']);self.assertAlmostEqual(z['state_swing'],z['region_swing'])

if __name__=='__main__':unittest.main()
