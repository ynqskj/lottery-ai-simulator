from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.prize_rules import evaluate_draw_prize, game_for_draw
from typing import List, Protocol, Sequence

from lottery_sim.games.dlt import DltGame
from lottery_sim.models import BacktestResult, BetResult, DltPick, DrawDLT


class DltStrategy(Protocol):
    name: str

    def generate(self, history: Sequence[DrawDLT]) -> DltPick:
        ...


def run_dlt_backtest(
    draws: Sequence[DrawDLT],
    game: DltGame,
    strategy: DltStrategy,
    min_history: int = 1,
) -> BacktestResult:
    if min_history < 0:
        raise ValueError("min_history 不能小于0")

    ordered_draws = sorted(draws, key=lambda draw: normalize_issue(draw.issue))
    bet_results: List[BetResult] = []
    hit_distribution = {
        "一等奖": 0,
        "二等奖": 0,
        "三等奖": 0,
        "四等奖": 0,
        "五等奖": 0,
        "六等奖": 0,
        "七等奖": 0,
        "八等奖": 0,
        "九等奖": 0,
        "未中奖": 0,
    }

    for index in range(min_history, len(ordered_draws)):
        target = ordered_draws[index]
        history = tuple(ordered_draws[:index])
        pick = game_for_draw(game, target).validate_pick(strategy.generate(history))
        level, payout, payout_basis = evaluate_draw_prize(game, target, pick)
        hit_distribution[level] = hit_distribution.get(level, 0) + 1

        bet_results.append(
            BetResult(
                issue=target.issue,
                draw_numbers=target.numbers,
                pick_numbers=pick,
                hit=payout > 0,
                cost=game.ticket_cost,
                payout=payout,
                payout_basis=payout_basis,
            )
        )

    return BacktestResult(
        game_name=game.name,
        total_draws=len(bet_results),
        total_bets=len(bet_results),
        total_cost=sum(result.cost for result in bet_results),
        total_payout=sum(result.payout for result in bet_results),
        hit_distribution=hit_distribution,
        bet_results=tuple(bet_results),
    )
