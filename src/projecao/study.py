"""Current evaluation scope, distinct from the historical dataset archive."""
import json
from pathlib import Path


def load_study(path=None):
    path=Path(path) if path else Path(__file__).resolve().parents[2]/'configs/study.json'
    study=json.loads(path.read_text())
    years=study['evaluation_years']
    if not years or years!=sorted(set(years)):raise ValueError('Evaluation years must be nonempty, sorted and unique')
    if study.get('reference_policy')!='same_year_first_round' or study.get('reference_turn')!=1 or study.get('turn')!=2:
        raise ValueError('Study requires second-turn targets with same-year first-turn reference')
    return study


def evaluation_years():
    return tuple(load_study()['evaluation_years'])
