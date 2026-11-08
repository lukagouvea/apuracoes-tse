import json, tempfile, unittest, zipfile
from pathlib import Path
import pandas as pd
from projecao.audit import extract_bu_order, check_summary
from projecao.experiment import load_historical_order
from projecao.download import atomic_json, sha256

class AuditTests(unittest.TestCase):
    def test_official_reception_field_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); out=root/'processed/2022'; out.mkdir(parents=True)
            pd.DataFrame({'uf':['SP'],'municipality':['00001'],'zone':['0001'],'section':['0002'],'votes_a':[3],'votes_b':[4]}).to_parquet(out/'sections.parquet')
            raw=root/'raw/2022/bu'; raw.mkdir(parents=True); z=raw/'bweb_2t_SP.zip'
            header='SG_UF;CD_MUNICIPIO;NR_ZONA;NR_SECAO;NR_TURNO;CD_CARGO_PERGUNTA;DT_BU_RECEBIDO\n'
            row='SP;1;1;2;2;1;2022-10-30 18:00:00\n'
            with zipfile.ZipFile(z,'w') as f: f.writestr('bu.csv',header+row+row)
            atomic_json(root/'manifests/2022-bu-bweb_2t_SP.zip.json',{'status':'complete','sha256':sha256(z),'url':'https://cdn.tse.jus.br/bu.zip'})
            a=extract_bu_order(root,2022)
            self.assertTrue(a['usable']); self.assertEqual(a['timestamp_meaning'],'reception')
            self.assertEqual(a['order_sha256'],sha256(out/'order.parquet'))
            order,_=load_historical_order(root,2022,pd.read_parquet(out/'sections.parquet'))
            order['timestamp']=order.timestamp+pd.Timedelta(seconds=1)
            order.to_parquet(out/'order.parquet',index=False)
            with self.assertRaisesRegex(ValueError,'checksum'):
                load_historical_order(root,2022,pd.read_parquet(out/'sections.parquet'))
            # A second, conflicting reception timestamp must invalidate chronology.
            with zipfile.ZipFile(z,'w') as f: f.writestr('bu.csv',header+row+row.replace('18:00','19:00'))
            atomic_json(root/'manifests/2022-bu-bweb_2t_SP.zip.json',{'status':'complete','sha256':sha256(z),'url':'https://cdn.tse.jus.br/bu.zip'})
            self.assertFalse(extract_bu_order(root,2022)['usable'])

    def test_summary_comparison_does_not_double_count_state_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); out=root/'processed/2022'; out.mkdir(parents=True)
            atomic_json(out/'preparation.json',{'candidate_a':'13','candidate_b':'22','votes_a':3,'votes_b':4})
            raw=root/'raw/2022/summary'; raw.mkdir(parents=True)
            text='CD_CARGO;NR_TURNO;NR_CANDIDATO;QT_VOTOS_NOMINAIS\n1;2;13;3\n1;2;22;4\n3;2;13;100\n'
            with zipfile.ZipFile(raw/'summary.zip','w') as f:
                f.writestr('votos_BRASIL.csv',text); f.writestr('votos_SP.csv',text)
            self.assertEqual(check_summary(root,2022)['status'],'matched')

if __name__=='__main__': unittest.main()
