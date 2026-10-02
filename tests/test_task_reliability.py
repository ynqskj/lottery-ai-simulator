import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from lottery_sim import dashboard
from lottery_sim.fastapi_app import create_fastapi_app


class TaskReliabilityTests(unittest.TestCase):
    def test_spawn_failure_finishes_job(self):
        job = dashboard._create_dashboard_job('generate', '3d', ['missing'])
        with patch('lottery_sim.dashboard._stream_command', side_effect=FileNotFoundError('missing')), patch('lottery_sim.dashboard._record_dashboard_job_history'):
            dashboard._run_dashboard_job(job, Path.cwd())
        self.assertEqual(job.status, 'failed')
        self.assertGreater(job.finished_at, 0)
        self.assertTrue(job.output_lines)

    def test_extreme_and_zero_parameters_are_rejected(self):
        for options in ({'count':'999999999'}, {'count':'0'}, {'mlTrainEpochs':'-1'}, {'mlMinTrain':'1'}, {'mlBacktestLimit':'no'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                dashboard._dashboard_daily_options('3d', options)

    def test_empty_login_does_not_return_server_error(self):
        with tempfile.TemporaryDirectory() as d:
            app = create_fastapi_app(Path(d)/'reports', Path(d))
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post('/login', data={'username':'', 'password':''})
            self.assertIn(response.status_code, (400,401))

    def test_utf8_bom_report_is_removed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'report.txt'
            path.write_text('候选号码报告', encoding='utf-8-sig')
            self.assertEqual(dashboard._read_text(path), '候选号码报告')

    def test_real_subprocess_timeout_finishes(self):
        import sys
        import os
        with patch.dict(os.environ, {'LOTTERY_JOB_TIMEOUT':'1'}):
            with self.assertRaises(TimeoutError):
                dashboard._stream_command([sys.executable,'-c','import time; time.sleep(10)'],Path.cwd(),lambda line:None)
    def test_real_subprocess_chinese_output(self):
        import sys
        lines=[]
        result=dashboard._stream_command([sys.executable,'-c','print("完成：中文日志")'],Path.cwd(),lines.append)
        self.assertEqual(result,0)
        self.assertEqual(lines,['完成：中文日志'])
