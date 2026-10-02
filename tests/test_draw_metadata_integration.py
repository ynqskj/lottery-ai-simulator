import csv
from datetime import datetime
from importlib import import_module

import pytest

from lottery_sim.models import DrawDLT, DrawSSQ, DrawQXC, DrawQLC, DrawKL8, DltPick, SsqPick, QxcPick, QlcPick, QlcDrawNumbers, Kl8Pick


CASES = [
    ('dlt',DrawDLT,DltPick((1,2,3,4,5),(1,2)),DltPick((1,2,3,4,5),(1,2))),
    ('ssq',DrawSSQ,SsqPick((1,2,3,4,5,6),1),SsqPick((1,2,3,4,5,6),1)),
    ('qxc',DrawQXC,QxcPick((1,2,3,4,5,6),7),QxcPick((1,2,3,4,5,6),7)),
    ('qlc',DrawQLC,QlcDrawNumbers((1,2,3,4,5,6,7),8),QlcPick((1,2,3,4,5,6,7))),
    ('kl8',DrawKL8,tuple(range(1,21)),Kl8Pick(tuple(range(1,11)))),
]


@pytest.mark.parametrize('code,draw_type,numbers,pick',CASES)
def test_metadata_csv_roundtrip_and_old_columns(tmp_path,code,draw_type,numbers,pick):
    source = import_module(f'lottery_sim.data_sources.{code}_17500')
    metadata = dict(prize_amounts={'一等奖':123456.5},special_prize_active=True,prize_pool=800000000)
    draw = draw_type('2026014','2026-02-03',numbers,**metadata)
    path = tmp_path/'draw.csv'
    getattr(source,f'save_{code}_draws_csv')([draw],path)
    assert getattr(source,f'load_{code}_draws_csv')(path) == [draw]
    with path.open(encoding='utf-8',newline='') as f:
        rows = list(csv.DictReader(f))
    row = {key:value for key,value in rows[0].items() if key not in metadata}
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    loaded = getattr(source,f'load_{code}_draws_csv')(path)[0]
    assert loaded.prize_amounts == {}
    assert loaded.special_prize_active is None
    assert loaded.prize_pool is None


@pytest.mark.parametrize('code,draw_type,numbers,pick',CASES)
def test_actual_csv_to_backtest_uses_official_award(tmp_path,code,draw_type,numbers,pick):
    source = import_module(f'lottery_sim.data_sources.{code}_17500')
    game_class = getattr(import_module(f'lottery_sim.games.{code}'),f'{code.title()}Game')
    game = game_class()
    level = game.prize_level(numbers,pick)
    target = draw_type('2026014','2026-02-03',numbers,prize_amounts={level:123456})
    path = tmp_path/'draw.csv'
    getattr(source,f'save_{code}_draws_csv')([target],path)
    draws = getattr(source,f'load_{code}_draws_csv')(path)
    strategy = type('Constant',(),{'name':'constant','generate':lambda self,history:pick})()
    run = getattr(import_module(f'lottery_sim.backtest.{code}_engine'),f'run_{code}_backtest')
    result = run(draws,game,strategy,min_history=0)
    assert result.total_payout == 123456
    assert result.bet_results[0].payout_basis == 'official'


def test_new_dlt_missing_metadata_is_estimated_and_report_says_so():
    from lottery_sim.backtest.dlt_engine import run_dlt_backtest
    from lottery_sim.games.dlt import DltGame
    from lottery_sim.reports.text_report import render_backtest_report
    numbers = DltPick((1,2,3,4,5),(1,2))
    pick = DltPick((1,2,3,4,6),(1,2))
    strategy = type('Constant',(),{'generate':lambda self,history:pick})()
    result = run_dlt_backtest([DrawDLT('26014','2026-02-02',numbers)],DltGame(),strategy,0)
    assert result.total_payout == 5000
    assert result.bet_results[0].payout_basis == 'estimated'
    assert '估算' in render_backtest_report(result,'constant')


def test_ssq_special_award_flows_through_verification_and_storage(tmp_path):
    from lottery_sim.games.ssq import SsqGame
    from lottery_sim.recommendation_tracking import RecommendationRecord,evaluate_recommendation_records,parse_pick_text,save_recommendation_records,load_recommendation_records,render_recommendation_verification_report
    record = RecommendationRecord('ssq','双色球','2026013','2026014',1,'constant','01 02 03 10 11 12 + 02','test')
    draw = DrawSSQ('2026014','2026-02-03',SsqPick((1,2,3,4,5,6),1),special_prize_active=True)
    result = evaluate_recommendation_records([record],[draw],SsqGame(),lambda text:parse_pick_text('ssq',text),as_of=datetime(2026,2,4))
    checked = result.records[0]
    assert (checked.prize_level,checked.payout,checked.payout_basis) == ('福运奖',5,'fixed')
    path = tmp_path/'records.csv'
    save_recommendation_records(result.records,path)
    assert load_recommendation_records(path) == list(result.records)
    assert '固定' in render_recommendation_verification_report(result)


def test_compare_report_includes_estimated_basis():
    from lottery_sim.models import BacktestResult, BetResult
    from lottery_sim.reports.compare_report import render_compare_report
    bet = BetResult('2026001',(),(),True,2,100000)
    result = BacktestResult('双色球',1,1,2,100000,{},(bet,))
    assert '估算' in render_compare_report([('constant',result)])


def test_old_recommendation_csv_defaults_to_estimated(tmp_path):
    from lottery_sim.recommendation_tracking import RecommendationRecord,save_recommendation_records,load_recommendation_records
    path=tmp_path/'old.csv'
    save_recommendation_records([RecommendationRecord('ssq','双色球','2026013','2026014',1,'constant','01 02 03 10 11 12 + 02','test')],path)
    with path.open(encoding='utf-8',newline='') as f:
        row=list(csv.DictReader(f))[0]
    row.pop('payout_basis')
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    assert load_recommendation_records(path)[0].payout_basis == 'estimated'


def test_legacy_qxc_actual_engine_uses_consecutive_rule():
    from lottery_sim.backtest.qxc_engine import run_qxc_backtest
    from lottery_sim.games.qxc import QxcGame
    pick=QxcPick((0,9,2,9,4,9),6)
    strategy=type('Constant',(),{'generate':lambda self,history:pick})()
    result=run_qxc_backtest([DrawQXC('20099','2020-10-11',QxcPick((0,1,2,3,4,5),6))],QxcGame(),strategy,0)
    assert result.total_payout == 0


@pytest.mark.parametrize('row',[{'prize_amounts':'[]'},{'prize_amounts':'{"一等奖":-1}'},{'special_prize_active':'unknown'},{'prize_pool':'nan'}])
def test_invalid_metadata_rejected(row):
    from lottery_sim.draw_metadata import metadata_from_row
    with pytest.raises(ValueError):
        metadata_from_row(row)


def test_verification_matches_mixed_issue_formats():
    from lottery_sim.games.ssq import SsqGame
    from lottery_sim.recommendation_tracking import RecommendationRecord,evaluate_recommendation_records,parse_pick_text
    record=RecommendationRecord('ssq','双色球','2026013','26014',1,'constant','01 02 03 04 05 06 + 01','test')
    draw=DrawSSQ('2026014','2026-02-03',SsqPick((1,2,3,4,5,6),1),prize_amounts={'一等奖':123456})
    result=evaluate_recommendation_records([record],[draw],SsqGame(),lambda text:parse_pick_text('ssq',text),as_of=datetime(2026,2,4))
    assert result.records[0].status == 'checked'
    assert result.total_payout == 123456


def test_recommendation_window_mixed_format_avoids_future_leakage():
    from lottery_sim.recommendation_tracking import select_recommendation_window
    numbers=SsqPick((1,2,3,4,5,6),1)
    draws=[DrawSSQ('2026013','2026-02-01',numbers),DrawSSQ('26014','2026-02-03',numbers)]
    window=select_recommendation_window(draws,target_issue='2026014')
    assert [draw.issue for draw in window.history] == ['2026013']


def test_backtest_sorts_mixed_format_by_normalized_issue():
    from lottery_sim.backtest.dlt_engine import run_dlt_backtest
    from lottery_sim.games.dlt import DltGame
    numbers=DltPick((1,2,3,4,5),(1,2))
    strategy=type('Constant',(),{'generate':lambda self,history:numbers})()
    result=run_dlt_backtest([DrawDLT('2026013','2026-01-31',numbers),DrawDLT('26014','2026-02-02',numbers)],DltGame(),strategy,1)
    assert result.bet_results[0].issue == '26014'
