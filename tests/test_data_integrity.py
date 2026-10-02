import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from lottery_sim.models import Draw3D
from lottery_sim.data_sources.incremental import merge_incremental_draws, update_draws_csv
from lottery_sim.recommendation_store import RecommendationStore
from lottery_sim.recommendation_tracking import RecommendationRecord, available_recommendation_draws
from lottery_sim.recommendation_summary import summarize_recommendation_records


class DataIntegrityTests(unittest.TestCase):
    def test_existing_draw_correction_is_applied(self):
        old = Draw3D('2026001','2026-01-01',(1,2,3))
        new = replace(old,numbers=(4,5,6))
        merged, _ = merge_incremental_draws([old],[new])
        self.assertEqual(merged[0].numbers,(4,5,6))

    def test_empty_feed_is_error(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            update_draws_csv(Path(d)/'draw.csv',[],lambda p:[],lambda rows,p:None)

    def test_all_batches_preserved_but_summary_counts_unique(self):
        r = RecommendationRecord('3d','3D','2026001','2026002',1,'test','123','',status='checked',cost=2,payout=1040,run_id='one')
        with tempfile.TemporaryDirectory() as d:
            store = RecommendationStore(Path(d))
            store.append_records([r])
            path, added, total = store.append_records([replace(r,run_id='two')])
            self.assertEqual((added,total),(1,2))
            from lottery_sim.recommendation_tracking import load_recommendation_records
            result = summarize_recommendation_records(load_recommendation_records(path))
            self.assertEqual(result.total_records,1)
            self.assertEqual(result.total_payout,1040)

    def test_bad_date_is_not_ready(self):
        self.assertFalse(available_recommendation_draws([Draw3D('2099001','bad',(1,2,3))]))
