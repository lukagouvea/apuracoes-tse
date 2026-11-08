import tempfile, unittest, zipfile
from pathlib import Path
import pandas as pd
from projecao.data import normalize_chunk, prepare_zip, make_history, build_snapshot
from projecao.download import select_resources, ensure_space

class DataTests(unittest.TestCase):
    def test_modern_layout_excludes_invalid_votes(self):
        f=pd.DataFrame({'ANO_ELEICAO':['2022']*3,'NR_TURNO':['2']*3,'SG_UF':['ZZ']*3,'CD_MUNICIPIO':['00001']*3,
          'NR_ZONA':['1']*3,'NR_SECAO':['2']*3,'CD_CARGO':['1']*3,'NR_VOTAVEL':['13','22','96'],'QT_VOTOS':['3','4','5']})
        n=normalize_chunk(f,2022)
        self.assertEqual(n['votes'].sum(),7); self.assertEqual(n['municipality'].iloc[0],'00001')
        self.assertEqual(set(n['candidate']),{'13','22'})

    def test_legacy_headerless_zip(self):
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/'old.zip'
            row='"01/01/2011";"12:00:00";"2010";"2";"ELEIÇÕES 2010";"SP";"71072";"SÃO PAULO";"1";"2";"1";"PRESIDENTE";"13";"10"\n'
            with zipfile.ZipFile(z,'w') as f: f.writestr('votacao_secao_2010_BR.txt',row.encode('latin1'))
            report=prepare_zip(z,2010,Path(d)/'out',('13','45'),reserve=0)
            self.assertEqual(report['valid_votes'],10)
            p=pd.read_parquet(Path(d)/'out'/'sections.parquet'); self.assertEqual(p.iloc[0].votes_a,10)

    def test_section_with_only_invalid_votes_is_in_universe(self):
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/'votes.zip'
            header='ANO_ELEICAO;NR_TURNO;SG_UF;CD_MUNICIPIO;NR_ZONA;NR_SECAO;CD_CARGO;NR_VOTAVEL;QT_VOTOS\n'
            text=header+'2022;2;SP;1;1;1;1;13;10\n2022;2;SP;1;1;2;1;96;15\n'
            with zipfile.ZipFile(z,'w') as f: f.writestr('votes.csv',text)
            r=prepare_zip(z,2022,Path(d)/'out',('13','22'),reserve=0)
            self.assertEqual(r['sections'],2); self.assertEqual(r['zero_valid_sections'],1)

    def test_history_fallback_and_hidden_votes_not_accessed(self):
        ref=pd.DataFrame({'uf':['SP','SP'],'municipality':['1','1'],'zone':['1','1'],'section':['1','2'],'votes_a':[60,60],'votes_b':[40,40]})
        current=pd.DataFrame({'uf':['SP','SP'],'municipality':['1','2'],'zone':['1','1'],'section':['1','1'],'votes_a':[70,99],'votes_b':[30,1]})
        h=make_history(ref,current[['uf','municipality','zone','section']]); self.assertEqual(h.frame.ref_share.tolist(),[.6,.6])
        a=build_snapshot(current.iloc[:1]); current.loc[1,'votes_a']=1
        pd.testing.assert_frame_equal(a.frame,build_snapshot(current.iloc[:1]).frame)

    def test_catalog_selects_presidential_only(self):
        r=[{'name':'Presidente','url':'https://cdn.tse.jus.br/votacao_secao_2022_BR.zip'}, {'name':'SP','url':'https://cdn.tse.jus.br/votacao_secao_2022_SP.zip'}]
        self.assertEqual(len(select_resources(r,'votes')),1)

    def test_bu_selector_excludes_checksum_files(self):
        r=[{'url':'https://cdn.tse.jus.br/bweb_2t_AC.zip','name':'BU'}, {'url':'https://cdn.tse.jus.br/bweb_2t_AC.zip.sha512','name':'Hash'}]
        self.assertEqual(len(select_resources(r,'bu')),1)

    def test_low_space_rejected(self):
        with self.assertRaises(OSError): ensure_space(Path('/tmp'),10**20,10*1024**3)

if __name__=='__main__': unittest.main()
