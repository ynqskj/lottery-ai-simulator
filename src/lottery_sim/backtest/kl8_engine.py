from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.prize_rules import evaluate_draw_prize, game_for_draw
from typing import List, Protocol, Sequence

from lottery_sim.games.kl8 import Kl8Game
from lottery_sim.models import BacktestResult, BetResult, DrawKL8, Kl8Pick


class Kl8Strategy(Protocol):
    name: str

    def generate(self, history: Sequence[DrawKL8]) -> Kl8Pick:
        ...


def run_kl8_backtest(
    draws: Sequence[DrawKL8],
    game: Kl8Game,
    strategy: Kl8Strategy,
    min_history: int = 1,
) -> BacktestResult:
    if min_history < 0:
        raise ValueError("min_history 不能小于0")

    ordered_draws = sorted(draws, key=lambda draw: normalize_issue(draw.issue))
    bet_results: List[BetResult] = []
    hit_distribution = {f"中{hits}": 0 for hits in sorted(game.prize_amounts, reverse=True)}
    hit_distribution["未中奖"] = 0

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
