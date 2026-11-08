import tempfile,unittest,zipfile
from pathlib import Path
from projecao.totalization import read_totalization

class TotalizationTests(unittest.TestCase):
    def test_national_2022_layout_whitespace_and_cumulative_counts(self):
        text=(' DT_TOTALIZACAO ;QT_SECOES_TOTAL;QT_SECOES_TOT_ACUMULADO;LULA_QT_VOTOS_TOT_ACUMULADO;JAIR_BOLSONARO_QT_VOTOS_TOT_ACUMULADO\n'
              '30/10/2022 17:00:00;10;1;60;40\n30/10/2022 17:01:00;10;2;110;90\n')
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/'national.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('historico.csv',text)
            frame=read_totalization(z,2022,'13','22')
            self.assertEqual(frame.sections.tolist(),[1,2]); self.assertEqual(frame.votes_a.tolist(),[60,110])

    def test_zone_layout_does_not_count_sections_per_candidate(self):
        h='DT_TOTALIZACAO;SG_UF;CD_MUNICIPIO;NR_ZONA;ID_TOTALIZACAO;QT_SECOES_BRASIL;QT_SECOES_TOT;NR_VOTAVEL;QT_VOTOS_TOT\n'
        rows=['25/10/2026 17:01:00;SP;1;1;10;10;1;13;60',
              '25/10/2026 17:01:00;SP;1;1;10;10;1;22;40',
              '25/10/2026 17:01:00;SP;1;1;10;10;1;-3;2',
              '25/10/2026 17:01:00;SP;1;1;10;10;1;-3;5',
              '25/10/2026 17:01:00;BA;2;1;11;10;1;13;30',
              '25/10/2026 17:01:00;BA;2;1;11;10;1;22;70',
              '25/10/2026 17:02:00;SP;1;1;12;10;2;13;100',
              '25/10/2026 17:02:00;SP;1;1;12;10;2;22;100']
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/'zone.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('hist_SP.csv',h+'\n'.join(rows))
            frame=read_totalization(z,2026,'13','22')
            self.assertEqual(frame.sections.tolist(),[2,4])
            self.assertEqual(frame.votes_a.tolist(),[90,190]);self.assertEqual(frame.votes_b.tolist(),[110,210])

if __name__=='__main__':unittest.main()

class Pdf2014Tests(unittest.TestCase):
    def test_pdf_table_parses_votes_without_inventing_sections(self):
        from projecao.totalization import parse_pdf_table
        text='Data/Hora Totalização Votos Dilma % Dilma Votos Aécio % Aécio Votos Válidos\n26/10/2014 17:01 2.465 48,38% 2.630 51,62% 5.095\n27/10/2014 02:13 54.501.118 51,64% 51.041.155 48,36% 105.542.273'
        f=parse_pdf_table(text)
        self.assertEqual(len(f),2);self.assertEqual(f.votes_a.tolist(),[2465,54501118])
        self.assertTrue(f.sections.isna().all());self.assertTrue(f.fraction_sections.isna().all())

    def test_inconsistent_pdf_row_is_rejected(self):
        from projecao.totalization import parse_pdf_table
        with self.assertRaises(ValueError):
            parse_pdf_table('26/10/2014 17:01 2.465 48,38% 2.630 51,62% 5.000')
