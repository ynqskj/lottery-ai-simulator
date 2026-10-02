import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lottery_sim import cli
from lottery_sim.data_sources.fucai3d_17500 import save_draws_csv
from lottery_sim.models import Draw3D
from lottery_sim.recommendation_tracking import load_recommendation_records


class CliPipelineTests(unittest.TestCase):
    def test_full_position_report_and_records_use_identical_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            csv = base / 'draws.csv'
            save_draws_csv([Draw3D(str(2026001 + i), f'2026-01-{i+1:02}', (i%10, (i+1)%10, (i+2)%10)) for i in range(6)], csv)
            common = ['--csv', str(csv), '--model', str(base/'model.json'), '--min-history', '2', '--epochs', '1', '--count', '1', '--position-counts', '2,2,2', '--combination-mode', 'full']
            output = io.StringIO()
            with redirect_stdout(output):
                cli.main(['recommend-ml-3d'] + common)
                cli.main(['record-recommend-ml-3d'] + common + ['--output', str(base/'records.csv')])
            records = load_recommendation_records(base/'records.csv')
            self.assertEqual(len(records), 8)
            for record in records:
                self.assertIn(record.numbers, output.getvalue())

    def test_invalid_position_counts_fail_before_loading_data(self):
        with patch.object(cli, '_load_generic_ml_context', side_effect=AssertionError('data should not load')):
            with self.assertRaisesRegex(ValueError, 'position'):
                cli.main(['recommend-ml-3d', '--csv', 'missing.csv', '--position-counts', '2,2'])

    def test_stale_model_retrains_after_new_issue(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            csv = base/'draws.csv'
            draws = [Draw3D(str(2026001+i), f'2026-01-{i+1:02}', (i%10, i%10, i%10)) for i in range(6)]
            common = ['--csv', str(csv), '--model', str(base/'model.json'), '--min-history', '2', '--epochs', '1', '--count', '1']
            with redirect_stdout(io.StringIO()):
                save_draws_csv(draws[:-1], csv)
                cli.main(['recommend-ml-3d'] + common)
                save_draws_csv(draws, csv)
                cli.main(['recommend-ml-3d'] + common)
            model = cli.load_generic_ml_model(base/'model.json')
            self.assertEqual(model.history_until_issue, draws[-1].issue)

    def test_daily_position_dry_run_skips_stat_recommend_and_record(self):
        import subprocess
        result = subprocess.run(['pwsh', '-NoProfile', '-File', str(Path(__file__).resolve().parents[1]/'scripts/daily.ps1'), '-Game', '3d', '-PositionCounts', '2,2,2', '-CombinationMode', 'full', '-DryRun'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--position-counts 2,2,2 --combination-mode full', result.stdout)
        self.assertNotIn('[recommend-3d]', result.stdout)
        self.assertNotIn('[record-3d]', result.stdout)


    def test_historical_record_trains_only_selected_history(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            csv = base/'draws.csv'
            draws = [Draw3D(str(2026001+i), f'2026-01-{i+1:02}', (i%10, i%10, i%10)) for i in range(6)]
            save_draws_csv(draws, csv)
            actual_train = cli.train_generic_ml_model
            observed = []
            def train(history, *args, **kwargs):
                observed.extend(history)
                return actual_train(history, *args, **kwargs)
            with patch.object(cli, 'train_generic_ml_model', side_effect=train), redirect_stdout(io.StringIO()):
                cli.main(['record-recommend-ml-3d', '--csv', str(csv), '--model', str(base/'model.json'), '--output', str(base/'records.csv'), '--target-issue', '2026005', '--history-until', '2026004', '--min-history', '2', '--epochs', '1'])
            self.assertEqual([draw.issue for draw in observed], [draw.issue for draw in draws[:4]])
            self.assertFalse((base/'model.json').exists())

    def test_qxc_ml_context_uses_only_modern_rule_draws(self):
        from types import SimpleNamespace
        from lottery_sim.models import DrawQXC, QxcPick
        draws = [DrawQXC(issue, '2020-10-01', QxcPick((1,2,3,4,5,6), 7)) for issue in ('20099', '20100', '20101')]
        with patch.object(cli, 'load_qxc_draws_csv', return_value=draws):
            history, _, _ = cli._load_generic_ml_context(SimpleNamespace(csv='unused'), 'qxc')
        self.assertEqual([draw.issue for draw in history], ['20100', '20101'])

    def test_unchanged_history_reuses_model_but_corrected_numbers_retrain(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            csv = base/'draws.csv'
            draws = [Draw3D(str(2026001+i), f'2026-01-{i+1:02}', (i%10, i%10, i%10)) for i in range(6)]
            save_draws_csv(draws, csv)
            common = ['--csv', str(csv), '--model', str(base/'model.json'), '--min-history', '2', '--epochs', '1', '--count', '1']
            with redirect_stdout(io.StringIO()):
                cli.main(['recommend-ml-3d'] + common)
                with patch.object(cli, 'train_generic_ml_model', wraps=cli.train_generic_ml_model) as train:
                    cli.main(['recommend-ml-3d'] + common)
                    self.assertEqual(train.call_count, 0)
                    draws[0] = Draw3D(draws[0].issue, draws[0].draw_date, (9,9,9))
                    save_draws_csv(draws, csv)
                    cli.main(['recommend-ml-3d'] + common)
                    self.assertEqual(train.call_count, 1)
