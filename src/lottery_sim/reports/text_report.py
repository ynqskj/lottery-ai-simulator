from lottery_sim.draw_metadata import payout_basis_summary
from lottery_sim.analysis.metrics import winning_bet_count
from lottery_sim.models import BacktestResult


def render_backtest_report(result: BacktestResult, strategy_name: str) -> str:
    lines = [
        f"{result.game_name}回测报告",
        f"策略：{strategy_name}",
        f"回测期数：{result.total_draws}",
        f"投注注数：{result.total_bets}",
        f"投入金额：{_format_number(result.total_cost)}",
        f"中奖金额：{_format_number(result.total_payout)}",
        payout_basis_summary(result.bet_results),
        f"返奖率：{_format_percent(result.roi)}",
        f"中奖注数：{winning_bet_count(result)}",
        "",
        "命中分布：",
    ]
    if result.hit_distribution:
        for label, count in result.hit_distribution.items():
            lines.append(f"- {label}：{count}")
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "风险提示：回测只衡量历史模拟结果，彩票具有强随机性，不能保证命中。",
    ])
    return "\n".join(lines)


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
