import unittest
from dataclasses import replace
from lottery_sim.ml.generic import ml_adapter_for_game, train_generic_ml_model, recommend_generic_ml, _rank_group_products
from lottery_sim.models import Draw3D, DrawKL8


class MlCombinationTests(unittest.TestCase):
    def setUp(self):
        self.history = [Draw3D(f'2026{i:03}','2026-09-01',(i%10,(i*3)%10,(i*7)%10)) for i in range(1,21)]
        self.adapter = ml_adapter_for_game('3d')
        self.model = train_generic_ml_model(self.history,self.adapter,min_history=2,epochs=1)

    def test_requested_count_is_fulfilled(self):
        self.assertEqual(len(recommend_generic_ml(self.history,self.model,self.adapter,count=100)),100)

    def test_joint_changes_are_enumerated(self):
        groups = [[((i,),1-i*.1) for i in range(3)] for _ in range(3)]
        combos = _rank_group_products(groups)
        self.assertEqual(len(combos),27)
        self.assertTrue(any(tuple(x[0][0] for x in c)==(1,1,0) for c in combos))

    def test_full_position_pool_and_top_mode(self):
        full = recommend_generic_ml(self.history,self.model,self.adapter,count=3,position_counts=(2,3,2),combination_mode='full')
        top = recommend_generic_ml(self.history,self.model,self.adapter,count=3,position_counts=(2,3,2),combination_mode='top')
        self.assertEqual(len(full),12)
        self.assertEqual(len(top),3)
        self.assertTrue(all(len(c.number_text)==3 for c in full))
        for pos,n in enumerate((2,3,2)):
            self.assertEqual(len({c.numbers[pos] for c in full}),n)

    def test_play_mismatch_rejected(self):
        history = [DrawKL8(f'2026{i:03}','2026-09-01',tuple(range(1,21))) for i in range(1,5)]
        model = train_generic_ml_model(history,ml_adapter_for_game('kl8',10),min_history=1,epochs=1)
        with self.assertRaises(ValueError):
            recommend_generic_ml(history,model,ml_adapter_for_game('kl8',5),1)

    def test_stale_model_has_training_cutoff(self):
        self.assertEqual(self.model.history_until_issue,self.history[-1].issue)

    def test_impossible_count_is_rejected(self):
        with self.assertRaises(ValueError):
            recommend_generic_ml(self.history,self.model,self.adapter,count=1001)
