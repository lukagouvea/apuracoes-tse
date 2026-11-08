import unittest
from pathlib import Path
from projecao.study import load_study, evaluation_years
from projecao.cli import parser
from projecao.experiment import run_experiment

class StudyTests(unittest.TestCase):
    def test_only_three_evaluation_years(self):
        self.assertEqual(evaluation_years(),(2018,2022,2026))
        self.assertEqual(load_study()['progress_unit'],'sections_in_dataset')

    def test_cli_rejects_archived_years_for_experiments(self):
        import contextlib,io
        for year in [2006,2010,2014]:
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                parser().parse_args(['experiment','--year',str(year),'--output','unused'])
        self.assertEqual(parser().parse_args(['smoke','--year','2018','--output','unused']).year,2018)
        self.assertIn(2014,parser().parse_args(['prepare']).years)

    def test_api_rejects_excluded_year_before_reading_data(self):
        with self.assertRaisesRegex(ValueError,'evaluated'):
            run_experiment(Path('/nonexistent-study-data'),2014,{},Path('/nonexistent-study-output'))

if __name__=='__main__':unittest.main()
