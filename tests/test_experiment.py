import unittest
import pandas as pd
from projecao.experiment import audit_order, reveal_order, evaluate
from projecao.models import Config
from projecao.data import make_history, SECTION

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.f=pd.DataFrame({'uf':['SP']*3,'municipality':['1','1','2'],'zone':['1']*3,'section':['1','2','3'],
          'votes_a':[10,20,30],'votes_b':[30,20,10]})
        self.order=self.f[SECTION].assign(timestamp=['2022-10-30 18:00:00','2022-10-30 18:01:00','2022-10-30 18:01:00'])

    def test_order_coverage_duplicates_and_timestamp_meaning(self):
        a=audit_order(self.f[SECTION],self.order,'reception')
        self.assertTrue(a['usable']); self.assertEqual(a['coverage'],1)
        self.assertFalse(audit_order(self.f[SECTION],self.order.iloc[:1],'reception')['usable'])
        self.assertFalse(audit_order(self.f[SECTION],pd.concat([self.order,self.order.iloc[:1]]),'reception')['usable'])
        self.assertFalse(audit_order(self.f[SECTION],self.order,'issuance')['usable'])

    def test_ties_revealed_together(self):
        ordered=reveal_order(self.f,self.order,seed=42)
        h=make_history(self.f,self.f[SECTION])
        r=evaluate(ordered,h,Config(),[.5,1.])
        self.assertEqual(len(r),1) # Both requested milestones reveal the same entire tied batch.
        self.assertEqual(r[0]['fraction_sections'],1)

    def test_future_votes_do_not_change_current_predictions(self):
        ordered=reveal_order(self.f,None,seed=42)
        h=make_history(self.f,self.f[SECTION]); a=evaluate(ordered,h,Config(),[1/3])[0]
        ordered.loc[1:,'votes_a']+=1000
        b=evaluate(ordered,h,Config(),[1/3])[0]
        self.assertEqual(a['share_a'],b['share_a'])
        self.assertNotEqual(a['error_pp'],b['error_pp'])

    def test_transit_uf_preserved(self):
        f=self.f.iloc[:1].copy(); f['uf']='VT'
        h=make_history(f,f[SECTION]); self.assertEqual(h.frame.region.iloc[0],'TRANSIT')

if __name__=='__main__': unittest.main()
