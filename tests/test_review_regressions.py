import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from lottery_sim.dashboard import llm_snapshot, DashboardModel
from lottery_sim.models import Draw3D
from lottery_sim.data_sources.incremental import update_draws_csv
from lottery_sim.data_sources.fucai3d_17500 import load_draws_csv, save_draws_csv
from lottery_sim import cli

class ReviewRegressionTests(unittest.TestCase):
    def test_large_snapshot_fits_service_budget(self):
        game=SimpleNamespace(code='3d',name='福彩3D',reports={str(i):'汉'*10000 for i in range(6)})
        model=SimpleNamespace(generated_at='now',recommendation_summary='汉'*30000,games=(game,)*8)
        with patch('lottery_sim.dashboard.load_dashboard_model',return_value=model):
            snapshot=llm_snapshot(Path('reports'))
        self.assertLessEqual(len(json.dumps(snapshot,ensure_ascii=False)),100000)
    def test_duplicate_csv_is_rewritten(self):
        draw=Draw3D('2026001','2026-01-01',(1,2,3))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'draw.csv';save_draws_csv([draw,draw],path)
            update_draws_csv(path,[draw],load_draws_csv,save_draws_csv)
            self.assertEqual(len(load_draws_csv(path)),1)
    def test_damaged_model_retrains(self):
        from lottery_sim.ml.generic import ml_adapter_for_game
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.json';path.write_text('{bad',encoding='utf-8')
            args=SimpleNamespace(model=str(path),min_history=1,epochs=1)
            with patch.object(cli,'train_generic_ml_model',return_value='trained') as train,patch.object(cli,'save_generic_ml_model'):
                result=cli._get_generic_recommendation_model(args,[],ml_adapter_for_game('3d'))
                self.assertEqual(result,'trained');train.assert_called_once()

    def test_empty_weights_are_not_reused(self):
        from lottery_sim.ml.generic import train_generic_ml_model, ml_adapter_for_game, save_generic_ml_model
        draws=[Draw3D(str(2026001+i),f'2026-01-{i+1:02}',(1,2,i)) for i in range(3)]
        adapter=ml_adapter_for_game('3d')
        model=train_generic_ml_model(draws,adapter,min_history=1,epochs=1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'m.json';save_generic_ml_model(model,path)
            data=json.loads(path.read_text(encoding='utf-8'))
            for group in data['groups']:group['weights']=[]
            path.write_text(json.dumps(data),encoding='utf-8')
            args=SimpleNamespace(model=str(path),min_history=1,epochs=1)
            with patch.object(cli,'train_generic_ml_model',return_value=model) as train:
                cli._get_generic_recommendation_model(args,draws,adapter)
                train.assert_called_once()

    def test_set_games_have_enough_ranked_candidates(self):
        from lottery_sim.ml.generic import _group_variants
        for maximum,pick_count,count in [(30,7,200),(80,10,1000)]:
            with self.subTest(maximum=maximum):
                rows=_group_variants([(n,1-n/1000) for n in range(1,maximum+1)],pick_count,count)
                self.assertGreaterEqual(len(rows),count)
                self.assertEqual(len({numbers for numbers,score in rows}),len(rows))
