import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import pandas as pd
from projecao import data
from projecao.data import SECTION, make_history
from projecao.download import sha256
from projecao.experiment import run_experiment
from projecao.study import load_study


class FirstTurnReferenceTests(unittest.TestCase):
    def reference(self):
        return pd.DataFrame({'uf':['SP','SP'],'municipality':['00001','00002'],
            'zone':['0001']*2,'section':['0001']*2,'votes_a':[40,0],
            'votes_b':[30,0],'votes_other':[30,100],'valid_votes':[100,100]})

    def test_preference_and_total_valid_volume_have_different_denominators(self):
        ref=self.reference().iloc[:1]
        h=make_history(ref,ref[SECTION]).frame.iloc[0]
        self.assertAlmostEqual(h.ref_share,4/7)
        self.assertEqual(h.ref_per_section,100)
        self.assertEqual(h.ref_size,100)

    def test_no_finalist_votes_uses_preference_fallback_and_keeps_local_volume(self):
        ref=self.reference();ref.loc[1,['votes_other','valid_votes']]=200
        h=make_history(ref,ref[SECTION]).frame.set_index('municipality')
        self.assertFalse(h.loc['00002','matched'])
        self.assertAlmostEqual(h.loc['00002','ref_share'],4/7)
        self.assertEqual(h.loc['00002','ref_per_section'],200)

    def test_policy_requires_same_year_first_turn(self):
        self.assertEqual(load_study()['reference_policy'],'same_year_first_round')
        elections=json.loads(Path('configs/elections.json').read_text())
        for year in [2018,2022,2026]:
            self.assertEqual(elections[str(year)]['reference'],{'year':year,'turn':1})

    def test_known_zero_volume_is_preserved_instead_of_state_fallback(self):
        ref=self.reference();ref.loc[1,['votes_other','valid_votes']]=0
        h=make_history(ref,ref[SECTION]).frame.set_index('municipality')
        self.assertAlmostEqual(h.loc['00002','ref_share'],4/7)
        self.assertEqual(h.loc['00002','ref_per_section'],0)
        self.assertEqual(h.loc['00002','ref_size'],0)

    def make_zip(self,root,duplicate=False):
        source=root/'raw/2018/votes/votacao_secao_2018_BR.zip'
        source.parent.mkdir(parents=True)
        header='ANO_ELEICAO;NR_TURNO;SG_UF;CD_MUNICIPIO;NR_ZONA;NR_SECAO;CD_CARGO;NR_VOTAVEL;QT_VOTOS\n'
        rows=['2018;1;SP;1;1;1;1;13;40','2018;1;SP;1;1;1;1;17;30',
            '2018;1;SP;1;1;1;1;12;30','2018;1;SP;1;1;2;1;96;100',
            '2018;2;SP;1;1;1;1;13;999999']
        if duplicate:rows.append(rows[0])
        with zipfile.ZipFile(source,'w') as z:z.writestr('votes.csv',header+'\n'.join(rows)+'\n')
        return source

    def prepare_reference(self,root,duplicate=False):
        self.make_zip(root,duplicate)
        fn=getattr(data,'prepare_first_turn_reference',None)
        self.assertIsNotNone(fn,'The first-turn reference preparation is missing')
        return fn(root,2018,('13','17'),reserve=0)

    def test_extracts_only_first_turn_and_preserves_zero_valid_sections(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);meta=self.prepare_reference(root)
            ref=pd.read_parquet(root/'processed/2018/first_turn_sections.parquet')
            self.assertEqual(len(ref),2)
            self.assertEqual(ref.valid_votes.sum(),100)
            self.assertEqual(ref.votes_a.sum(),40)
            self.assertEqual(ref.votes_other.sum(),30)
            self.assertEqual(meta['turn'],1)
            self.assertEqual(meta['reference_sha256'],sha256(root/'processed/2018/first_turn_sections.parquet'))
            h=make_history(ref,ref[SECTION]).frame.iloc[0]
            self.assertEqual(h.ref_per_section,50)

    def test_first_turn_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            fn=getattr(data,'prepare_first_turn_reference',None)
            self.assertIsNotNone(fn,'The first-turn reference preparation is missing')
            self.make_zip(Path(d),duplicate=True)
            with self.assertRaisesRegex(ValueError,'[Dd]uplicate'):fn(Path(d),2018,('13','17'))

    def test_run_rejects_previous_election_reference(self):
        cfg={'2018':{'reference':{'year':2014,'turn':2},'candidate_a':'13','candidate_b':'17'}}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'first turn of the same year'):
                run_experiment(Path(d),2018,cfg,Path(d)/'result',device='cpu')

    def test_run_records_turns_and_does_not_require_an_earlier_election(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.prepare_reference(root)
            ref=pd.read_parquet(root/'processed/2018/first_turn_sections.parquet')
            target=ref[SECTION].assign(votes_a=[60,60],votes_b=[40,40])
            target.to_parquet(root/'processed/2018/sections.parquet',index=False)
            cfg=json.loads(Path('configs/elections.json').read_text())
            output=root/'result'
            rows=run_experiment(root,2018,cfg,output,device='cpu',milestones=[.5,1])
            meta=json.loads((output/'run.json').read_text())
            self.assertEqual(meta['reference_year'],2018)
            self.assertEqual(meta['reference_turn'],1)
            self.assertEqual(meta['turn'],2)
            self.assertTrue(all(r['reference_turn']==1 and r['turn']==2 for r in rows))
            self.assertTrue(all(r['error_pp']==0 for r in rows if r['fraction_sections']==1))
            tampered=ref.copy();tampered.loc[0,'votes_a']+=1
            tampered.to_parquet(root/'processed/2018/first_turn_sections.parquet',index=False)
            with self.assertRaisesRegex(ValueError,'checksum'):
                run_experiment(root,2018,cfg,root/'tampered-result',device='cpu',milestones=[1])

if __name__=='__main__':unittest.main()
