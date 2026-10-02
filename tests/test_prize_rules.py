from types import SimpleNamespace

import pytest

from lottery_sim.games.dlt import DltGame
from lottery_sim.games.qxc import QxcGame
from lottery_sim.games.ssq import SsqGame
from lottery_sim.models import DltPick, QxcPick, SsqPick


def evaluate(game, issue, numbers, pick, **metadata):
    from lottery_sim.prize_rules import evaluate_draw_prize
    return evaluate_draw_prize(game, SimpleNamespace(issue=issue, numbers=numbers, **metadata), pick)


@pytest.mark.parametrize('issue,level,payout', [('19018','三等奖',10000),('2019019','四等奖',3000),('26013','四等奖',3000),('2026014','三等奖',5000)])
def test_dlt_rule_boundary(issue, level, payout):
    result = evaluate(DltGame(), issue, DltPick((1,2,3,4,5),(1,2)), DltPick((1,2,3,4,6),(1,2)))
    assert result[:2] == (level,payout)


@pytest.mark.parametrize('front,back,level,payout', [(5,0,'三等奖',5000),(4,1,'四等奖',300),(4,0,'五等奖',150),(3,2,'五等奖',150),(3,1,'六等奖',15),(2,2,'六等奖',15),(3,0,'七等奖',5),(2,1,'七等奖',5),(1,2,'七等奖',5),(0,2,'七等奖',5)])
def test_dlt_new_combinations_and_unknown_pool(front, back, level, payout):
    pick = DltPick(tuple(range(1,front+1))+tuple(range(10,15-front)), tuple(range(1,back+1))+tuple(range(8,10-back)))
    result = evaluate(DltGame(),'26014',DltPick((1,2,3,4,5),(1,2)),pick)
    assert result[:2] == (level,payout)
    assert result[2] == 'estimated'


def test_official_amount_overrides_estimates():
    numbers = DltPick((1,2,3,4,5),(1,2))
    assert evaluate(DltGame(),'26014',numbers,numbers,prize_amounts={'一等奖':123456}) == ('一等奖',123456,'official')


def test_known_high_pool_uses_high_fixed_prize():
    result = evaluate(DltGame(),'26014',DltPick((1,2,3,4,5),(1,2)),DltPick((1,2,3,4,5),(3,4)),prize_pool=800_000_000)
    assert result == ('三等奖',6666,'fixed')


@pytest.mark.parametrize('active,expected,basis', [(True,('福运奖',5),'fixed'),(False,('未中奖',0),'fixed'),(None,('未中奖',0),'estimated')])
def test_ssq_special_award_requires_state(active, expected, basis):
    result = evaluate(SsqGame(),'2026014',SsqPick((1,2,3,4,5,6),1),SsqPick((1,2,3,10,11,12),2),special_prize_active=active)
    assert result == (*expected,basis)


def test_ssq_special_award_does_not_override_fifth():
    assert evaluate(SsqGame(),'2026014',SsqPick((1,2,3,4,5,6),1),SsqPick((1,2,3,10,11,12),1),special_prize_active=True)[:2] == ('五等奖',10)


@pytest.mark.parametrize('pick,level,payout', [((0,1,2,3,4,5,9),'二等奖',100000),((9,1,2,3,4,5,9),'三等奖',1800),((9,1,2,3,4,9,9),'四等奖',300),((0,9,2,9,4,9,6),'未中奖',0),((9,9,2,3,4,9,9),'五等奖',20),((9,9,9,3,4,9,9),'六等奖',5)])
def test_legacy_qxc_requires_consecutive_positions(pick,level,payout):
    assert evaluate(QxcGame(),'20099',QxcPick((0,1,2,3,4,5),6),QxcPick(pick[:6],pick[6]))[:2] == (level,payout)


def test_legacy_qxc_rejects_modern_special_range():
    from lottery_sim.prize_rules import game_for_draw
    old = game_for_draw(QxcGame(), SimpleNamespace(issue='2020099'))
    with pytest.raises(ValueError):
        old.validate_pick(QxcPick((1,2,3,4,5,6),14))
    game_for_draw(QxcGame(),SimpleNamespace(issue='20100')).validate_pick(QxcPick((1,2,3,4,5,6),14))


def test_generic_direct_game_remains_supported():
    from lottery_sim.games.fucai3d import Fucai3DGame
    assert evaluate(Fucai3DGame(),'2026001',(1,2,3),(1,2,3)) == ('直选',1040,'fixed')


def test_qlc_third_is_floating():
    from lottery_sim.games.qlc import QlcGame
    from lottery_sim.models import QlcDrawNumbers, QlcPick
    assert evaluate(QlcGame(),'2026001',QlcDrawNumbers((1,2,3,4,5,6,7),8),QlcPick((1,2,3,4,5,6,9)))[2] == 'estimated'


def test_official_fractional_amount_is_preserved():
    from lottery_sim.games.kl8 import Kl8Game
    from lottery_sim.models import Kl8Pick
    game = Kl8Game(1)
    level = game.prize_level(tuple(range(1,21)),Kl8Pick((1,)))
    assert evaluate(game,'2026001',tuple(range(1,21)),Kl8Pick((1,)),prize_amounts={level:4.5}) == (level,4.5,'official')


@pytest.mark.parametrize('amount', [True,-1,float('nan'),float('inf'),'5'])
def test_invalid_official_amount_is_rejected(amount):
    numbers = DltPick((1,2,3,4,5),(1,2))
    with pytest.raises(ValueError):
        evaluate(DltGame(),'26014',numbers,numbers,prize_amounts={'一等奖':amount})


@pytest.mark.parametrize('issue,front,back,level,payout', [('14051',4,2,'四等奖',3000),('2014051',4,1,'五等奖',600),('14051',4,0,'六等奖',100),('14051',3,2,'六等奖',100),('14051',3,1,'七等奖',10),('14051',2,2,'七等奖',10),('14051',3,0,'八等奖',5),('14051',0,2,'八等奖',5),('14052',4,2,'三等奖',10000),('2014052',4,1,'四等奖',200),('14052',4,0,'五等奖',10)])
def test_dlt_pre2014_eight_tiers_and_boundary(issue,front,back,level,payout):
    pick = DltPick(tuple(range(1,front+1))+tuple(range(10,15-front)), tuple(range(1,back+1))+tuple(range(8,10-back)))
    result = evaluate(DltGame(),issue,DltPick((1,2,3,4,5),(1,2)),pick)
    assert result[:2] == (level,payout)
