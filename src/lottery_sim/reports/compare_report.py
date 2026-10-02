from typing import Iterable, Tuple

from lottery_sim.analysis.metrics import winning_bet_count
from lottery_sim.models import BacktestResult
from lottery_sim.draw_metadata import payout_basis_summary


def render_compare_report(results: Iterable[Tuple[str, BacktestResult]]) -> str:
    rows = list(results)
    lines = [
        "多策略回测对比",
        "策略 | 回测期数 | 投注注数 | 投入金额 | 中奖金额 | 返奖率 | 中奖注数",
        "--- | ---: | ---: | ---: | ---: | ---: | ---:",
    ]
    if not rows:
        lines.append("暂无策略结果")
        return "\n".join(lines)

    for name, result in rows:
        lines.append(
            " | ".join([
                name,
                str(result.total_draws),
                str(result.total_bets),
                _format_number(result.total_cost),
                _format_number(result.total_payout),
                _format_percent(result.roi),
                str(winning_bet_count(result)),
            ])
        )
    lines.extend(["", payout_basis_summary(bet for _, result in rows for bet in result.bet_results)])
    return "\n".join(lines)


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
