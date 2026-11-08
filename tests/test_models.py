import unittest
import numpy as np
import pandas as pd
import torch
from projecao.models import Config, History, Snapshot, predict, convergence


def example():
    h = History(pd.DataFrame({
        'uf':['SP','SP','BA','ZZ'], 'municipality':['1','2','3','4'],
        'region':['SE','SE','NE','EX'], 'n_sections':[2,2,2,2],
        'ref_share':[.6,.4,.7,.5], 'ref_per_section':[100.,100.,100.,100.],
        'ref_size':[200.,200.,200.,200.], 'matched':[True]*4,
    }))
    s = Snapshot(pd.DataFrame({'uf':['SP','BA'], 'municipality':['1','3'],
                              'n_observed':[1,1], 'votes_a':[70,60], 'votes_b':[30,40]}))
    return h,s

class ModelTests(unittest.TestCase):
    def test_all_methods_and_devices(self):
        h,s=example()
        for name in ['poststrat','swing','hierarchical']:
            p=predict(s,h,Config(method=name))
            self.assertTrue(0 <= p.share_a <= 1)
            self.assertAlmostEqual(p.share_a+p.share_b,1)
            self.assertEqual(p.fraction_sections,.25)
            if torch.cuda.is_available():
                g=predict(s,h,Config(method=name,device='cuda'))
                self.assertAlmostEqual(p.share_a,g.share_a,places=6)

    def test_full_count_reproduces_observed_result(self):
        h,_=example()
        s=Snapshot(h.frame[['uf','municipality']].assign(n_observed=2,votes_a=[120,80,140,100],votes_b=[80,120,60,100]))
        for name in ['poststrat','swing','hierarchical']:
            p=predict(s,h,Config(method=name))
            self.assertAlmostEqual(p.share_a,.55)
            self.assertEqual(p.votes_a,440)

    def test_empty_and_zero_valid_and_singular(self):
        h,_=example()
        for s in [Snapshot.empty(),Snapshot(pd.DataFrame({'uf':['SP'],'municipality':['1'],'n_observed':[1],'votes_a':[0],'votes_b':[0]}))]:
            for name in ['poststrat','swing','hierarchical']:
                self.assertTrue(np.isfinite(predict(s,h,Config(method=name)).share_a))
        h.frame['ref_share']=.5
        self.assertTrue(np.isfinite(predict(example()[1],h,Config(method='swing')).share_a))

    def test_poststrat_fallback_and_known_values(self):
        h,s=example()
        p=predict(s,h,Config(method='poststrat'))
        # Global turnout ratio = 1; SP municipality 2 gets .7, exterior gets .65.
        self.assertAlmostEqual(p.share_a,(70+60+70+140+60+130)/800)

    def test_hierarchy_shrinks_sparse_group(self):
        h,s=example()
        p=predict(s,h,Config(method='hierarchical',lambda_region=1e15,lambda_uf=1e15))
        q=predict(s,h,Config(method='swing'))
        self.assertAlmostEqual(p.share_a,q.share_a,places=6)

    def test_invalid_counts_rejected(self):
        h,s=example(); s.frame.loc[0,'n_observed']=3
        with self.assertRaises(ValueError): predict(s,h,Config())

    def test_sustained_convergence(self):
        self.assertEqual(convergence([1,2,5,10],[.1,.6,.4,.2],.5),5)
        self.assertIsNone(convergence([1,2],[2,1],.5))

if __name__=='__main__': unittest.main()
