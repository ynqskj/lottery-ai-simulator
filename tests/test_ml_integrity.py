import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lottery_sim.ml import generic, ssq
from lottery_sim.models import Draw3D, DrawSSQ, SsqPick


class MlIntegrityTests(unittest.TestCase):
    def test_training_metadata_survives_roundtrip_and_old_models_load(self):
        import json
        draws = [Draw3D(str(2026001+i), f'2026-01-{i+1:02}', (i,i,i)) for i in range(4)]
        model = generic.train_generic_ml_model(draws, generic.ml_adapter_for_game('3d'), min_history=2, epochs=1)
        self.assertEqual(model.training_epochs, 1)
        self.assertTrue(model.history_fingerprint)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'model.json'
            generic.save_generic_ml_model(model, path)
            self.assertEqual(generic.load_generic_ml_model(path), model)
            data = json.loads(path.read_text(encoding='utf-8'))
            del data['training_epochs']; del data['history_fingerprint']
            path.write_text(json.dumps(data), encoding='utf-8')
            legacy = generic.load_generic_ml_model(path)
            self.assertEqual(legacy.training_epochs, 0)
            self.assertEqual(legacy.history_fingerprint, '')

    def test_ssq_candidates_are_top_scoring_joint_combinations(self):
        draw = DrawSSQ('2026001', '2026-01-01', SsqPick((1,2,3,4,5,6),1))
        # A small red-score gap means all top tickets should use the best blue.
        red = [(i, .9 - i*.001) for i in range(1,34)]
        blue = [(1,.9)] + [(i,.1) for i in range(2,17)]
        with patch.object(ssq, '_score_numbers', side_effect=[red, blue]):
            candidates = ssq.recommend_ssq_ml([draw], None, count=10)
        self.assertEqual(len(candidates),10)
        self.assertTrue(all(candidate.numbers.blue == 1 for candidate in candidates))

    def test_ssq_count_capped_before_scoring(self):
        with patch.object(ssq, '_score_numbers', side_effect=AssertionError('must not score')):
            with self.assertRaises(ValueError):
                ssq.recommend_ssq_ml([], None, count=1001)

    def test_ssq_training_metadata_roundtrip(self):
        draws = [DrawSSQ(str(2026001+i), f'2026-01-{i+1:02}', SsqPick((1,2,3,4,5,6),i+1)) for i in range(4)]
        model = ssq.train_ssq_ml_model(draws, min_history=2, epochs=1)
        self.assertEqual(model.training_epochs, 1)
        self.assertEqual(model.history_fingerprint, generic.history_fingerprint(draws))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'model.json'
            ssq.save_ssq_ml_model(model, path)
            self.assertEqual(ssq.load_ssq_ml_model(path), model)

    def test_ml_backtests_use_official_payout_and_preserve_basis(self):
        from types import SimpleNamespace
        from lottery_sim.games.dlt import DltGame
        from lottery_sim.models import DltPick
        dlt_pick = DltPick((1,2,3,4,5),(1,2))
        ssq_pick = SsqPick((1,2,3,4,5,6),1)
        for module, pick, code in [(generic,dlt_pick,'dlt'), (ssq,ssq_pick,'ssq')]:
            draws = [SimpleNamespace(issue=str(2026001+i), draw_date=f'2026-01-{i+1:02}', numbers=pick, prize_amounts={'一等奖':123456}) for i in range(3)]
            train_name = 'train_generic_ml_model' if code == 'dlt' else 'train_ssq_ml_model'
            recommend_name = 'recommend_generic_ml' if code == 'dlt' else 'recommend_ssq_ml'
            with patch.object(module, train_name, return_value=object()), patch.object(module, recommend_name, return_value=[SimpleNamespace(numbers=pick)]):
                if code == 'dlt':
                    result = module.run_generic_ml_backtest(draws, generic.ml_adapter_for_game('dlt'), DltGame(), min_train=2, min_history=1, epochs=1)
                else:
                    result = module.run_ssq_ml_backtest(draws, min_train=2, min_history=1, epochs=1)
            self.assertEqual(result.total_payout,123456)
            self.assertEqual(result.bet_results[0].payout_basis,'official')

    def test_ssq_thousand_candidates_are_unique(self):
        draw = DrawSSQ('2026001','2026-01-01',SsqPick((1,2,3,4,5,6),1))
        with patch.object(ssq, '_score_numbers', side_effect=[[(i,1-i*.001) for i in range(1,34)],[(i,1-i*.01) for i in range(1,17)]]):
            candidates = ssq.recommend_ssq_ml([draw],None,count=1000)
        self.assertEqual(len(candidates),1000)
        self.assertEqual(len({candidate.number_text for candidate in candidates}),1000)
