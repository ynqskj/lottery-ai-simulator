import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from lottery_sim.fastapi_app import create_fastapi_app
from lottery_sim.dashboard import _dashboard_daily_options

class LlmDashboardTests(unittest.TestCase):
    def test_actions_require_login_and_do_not_run_on_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with TestClient(create_fastapi_app(root/'reports/latest',root)) as client:
                self.assertEqual(client.post('/api/llm/models').status_code,401)
                client.post('/login',data={'username':'admin','password':'admin'})
                with patch('lottery_sim.llm_service.perform_action',return_value={'ok':True,'models':['m1']}) as action:
                    page=client.get('/')
                    action.assert_not_called()
                    self.assertIn('llm-model-list',page.text)
                    response=client.post('/api/llm/models',data={'llm_base_url':'https://example.com/v1'})
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.json()['models'],['m1'])
                    self.assertIn('users',str(action.call_args.args[0]))
                with patch('lottery_sim.llm_service.perform_action',side_effect=ValueError('连接失败')):
                    self.assertEqual(client.post('/api/llm/test').status_code,400)
    def test_combination_options_validate_and_propagate(self):
        options=_dashboard_daily_options('3d',{'positionCounts':'2,3,2','combinationMode':'full'})
        self.assertIn('-PositionCounts',options)
        self.assertIn('2,3,2',options)
        for game,counts in [('3d','2,2'),('ssq','2,2,2'),('pl5','10,10,10,10,10')]:
            with self.subTest(game=game),self.assertRaises(ValueError):
                _dashboard_daily_options(game,{'positionCounts':counts,'combinationMode':'full'})
