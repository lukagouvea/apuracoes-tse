import tempfile,unittest,zipfile
from pathlib import Path
import pandas as pd
from projecao.download import atomic_json,sha256
from projecao.timing import extract_detail_order

class DetailTimingTests(unittest.TestCase):
    def fixture(self,root,missing=False):
        out=root/'processed/2018';out.mkdir(parents=True)
        f=pd.DataFrame({'uf':['SP','RS'],'municipality':['00001','00002'],'zone':['0001','0001'],'section':['0001','0002'],'votes_a':[6,4],'votes_b':[4,6]})
        f.to_parquet(out/'sections.parquet',index=False);f.drop(columns=['votes_a','votes_b']).to_parquet(out/'universe.parquet',index=False)
        raw=root/'raw/2018/detail';raw.mkdir(parents=True);z=raw/'detail.zip'
        header='ANO_ELEICAO;NR_TURNO;CD_CARGO;SG_UF;CD_MUNICIPIO;NR_ZONA;NR_SECAO;QT_VOTOS_NOMINAIS;DT_RECEBIMENTO_BU_HOR_TSE;DT_PRIM_TOT_PARCIAL_HOR_TSE\n'
        content=header+'2018;2;1;SP;1;1;1;10;28/10/2018 17:01:00;28/10/2018 17:02:00\n2018;2;1;RS;2;1;2;10;25/02/2019 18:00:00;'+('#NULO#' if missing else '25/02/2019 18:01:00')+'\n'
        with zipfile.ZipFile(z,'w')as f:f.writestr('detalhe_2018_BR.csv',content)
        atomic_json(root/'manifests/2018-detail-detail.zip.json',{'status':'complete','path':'raw/2018/detail/detail.zip','sha256':sha256(z),'url':'https://cdn.tse.jus.br/detail.zip'})
        return out

    def test_first_totalization_keeps_late_dates_and_exposes_semantics(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);out=self.fixture(root);r=extract_detail_order(root,2018)
            self.assertTrue(r['usable']);self.assertEqual(r['coverage'],1.)
            self.assertTrue(r['reconstructed_from_final_votes']);self.assertEqual(r['late_sections'],1)
            order=pd.read_parquet(out/'order.parquet');self.assertEqual(order.timestamp.max().year,2019)
            self.assertTrue((out/'section_timing.parquet').exists())

    def test_missing_timestamp_is_not_imputed(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);self.fixture(root,missing=True);r=extract_detail_order(root,2018)
            self.assertFalse(r['usable']);self.assertEqual(r['invalid_timestamps'],1)

    def test_reconstruction_rejects_votes_changed_after_nominal_audit(self):
        from projecao.totalization import reconstruct_first_totalization
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);out=self.fixture(root);r=extract_detail_order(root,2018)
            self.assertEqual(r['sections_sha256'],sha256(out/'sections.parquet'))
            f=pd.read_parquet(out/'sections.parquet');f.loc[0,'votes_a']-=1;f.loc[1,'votes_a']+=1
            f.to_parquet(out/'sections.parquet',index=False)
            with self.assertRaisesRegex(ValueError,'checksum'):
                reconstruct_first_totalization(root,2018)

if __name__=='__main__':unittest.main()
