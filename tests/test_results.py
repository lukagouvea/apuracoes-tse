import unittest
import pandas as pd
from projecao import results
from projecao.study import load_study


class ResultsTests(unittest.TestCase):
    def fixture(self):
        rows=[];fractions=[.015,.026,.056,.105,1.]
        for method,offset in [('poststrat',0),('swing',.001),('hierarchical',-.001)]:
            for i,(fraction,share) in enumerate(zip(fractions,[.52,.51,.515,.507,.5])):
                share+=offset if fraction<1 else 0
                baseline=.45 if fraction<1 else .5
                rows.append({'year':2022,'turn':2,'reference_year':2022,'reference_turn':1,
                    'method':method,'fraction_sections':fraction,'requested_fraction':[.001,.02,.05,.1,1][i],
                    'observed_sections':round(fraction*1000),'share_a':share,'share_b':1-share,
                    'final_share_a':.5,'error_pp':abs(share-.5)*100,
                    'baseline_share_a':baseline,'baseline_error_pp':abs(baseline-.5)*100})
        meta={'year':2022,'turn':2,'reference_year':2022,'reference_turn':1,'mode':'historical','device':'cpu',
            'study':load_study(),'milestones':[.001,.01,.02,.05,.1,1.],
            'elections_config':{'2022':{'name_a':'Candidato A','name_b':'Candidato B','reference':{'year':2022,'turn':1}}},
            'chronology':{'timestamp_meaning':'reception'}}
        return pd.DataFrame(rows),meta

    def prepare(self,frame,meta):
        fn=getattr(results,'prepare_election',None)
        self.assertIsNotNone(fn,'Results presentation must preserve recorded snapshots')
        return fn(frame,meta)

    def test_milestone_uses_effective_snapshot_when_requested_row_was_deduplicated(self):
        frame,meta=self.fixture();data=self.prepare(frame,meta)
        self.assertEqual(len(data['milestones']),12)
        row=next(r for r in data['milestones'] if r['requested_fraction']==.01 and r['method']=='poststrat')
        self.assertEqual(row['fraction_sections'],.015)
        self.assertEqual(row['observed_sections'],15)
        self.assertEqual(row['point_index'],0)

    def test_table_includes_both_finalists_and_actual_result(self):
        frame,meta=self.fixture();data=self.prepare(frame,meta)
        row=data['milestones'][0]
        self.assertAlmostEqual(row['share_a'],.52);self.assertAlmostEqual(row['share_b'],.48)
        self.assertEqual(row['final_a'],.5);self.assertEqual(row['final_b'],.5)
        self.assertAlmostEqual(row['error_pp'],2.)

    def test_stability_is_absolute_change_and_first_snapshot_has_no_previous_value(self):
        frame,meta=self.fixture();data=self.prepare(frame,meta)
        self.assertIsNone(data['points'][0]['estimates']['poststrat']['change_pp'])
        self.assertIsNone(data['points'][0]['step_sections_pp'])
        self.assertAlmostEqual(data['points'][1]['estimates']['poststrat']['change_pp'],1.)
        self.assertAlmostEqual(data['points'][1]['step_sections_pp'],1.1)

    def test_missing_requested_milestone_is_rejected_instead_of_inferred(self):
        frame,meta=self.fixture();meta['milestones'].remove(.02)
        with self.assertRaisesRegex(ValueError,'milestone'):self.prepare(frame,meta)

    def test_different_observed_sections_between_methods_are_rejected(self):
        frame,meta=self.fixture();frame.loc[frame.method.eq('swing'),'observed_sections']+=1
        with self.assertRaisesRegex(ValueError,'same snapshots'):self.prepare(frame,meta)

    def test_missing_snapshot_is_not_replaced_by_a_later_requested_milestone(self):
        frame,meta=self.fixture();frame=frame[frame.requested_fraction.ne(.02)]
        with self.assertRaisesRegex(ValueError,'milestone'):self.prepare(frame,meta)

    def test_wrong_reference_or_missing_endpoint_is_rejected(self):
        frame,meta=self.fixture();meta['reference_turn']=2
        with self.assertRaisesRegex(ValueError,'first-turn'):self.prepare(frame,meta)
        frame,meta=self.fixture()
        with self.assertRaisesRegex(ValueError,'100%'):self.prepare(frame[frame.fraction_sections.lt(1)],meta)

if __name__=='__main__':unittest.main()
