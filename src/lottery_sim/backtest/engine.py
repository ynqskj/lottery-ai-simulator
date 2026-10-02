from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.prize_rules import evaluate_draw_prize, game_for_draw
from typing import List, Protocol, Sequence

from lottery_sim.games.fucai3d import Fucai3DGame
from lottery_sim.models import BacktestResult, BetResult, Draw3D, Pick3D


class Strategy3D(Protocol):
    name: str

    def generate(self, history: Sequence[Draw3D]) -> Pick3D:
        ...


def run_backtest(
    draws: Sequence[Draw3D],
    game: Fucai3DGame,
    strategy: Strategy3D,
    min_history: int = 1,
) -> BacktestResult:
    if min_history < 0:
        raise ValueError("min_history 不能小于0")

    ordered_draws = sorted(draws, key=lambda draw: normalize_issue(draw.issue))
    bet_results: List[BetResult] = []
    hit_distribution = {"direct_hit": 0, "miss": 0}

    for index in range(min_history, len(ordered_draws)):
        target = ordered_draws[index]
        history = tuple(ordered_draws[:index])
        pick = game_for_draw(game, target).validate_pick(strategy.generate(history))
        level, payout, payout_basis = evaluate_draw_prize(game, target, pick)
        hit = payout > 0

        if hit:
            hit_distribution["direct_hit"] += 1
        else:
            hit_distribution["miss"] += 1

        bet_results.append(
            BetResult(
                issue=target.issue,
                draw_numbers=target.numbers,
                pick_numbers=pick,
                hit=hit,
                cost=game.ticket_cost,
                payout=payout,
                payout_basis=payout_basis,
            )
        )

    total_cost = sum(result.cost for result in bet_results)
    total_payout = sum(result.payout for result in bet_results)

    return BacktestResult(
        game_name=game.name,
        total_draws=len(bet_results),
        total_bets=len(bet_results),
        total_cost=total_cost,
        total_payout=total_payout,
        hit_distribution=hit_distribution,
        bet_results=tuple(bet_results),
    )
