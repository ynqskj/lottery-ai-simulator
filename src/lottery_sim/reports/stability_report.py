from typing import Iterable, Sequence, Tuple

from lottery_sim.analysis.stability import SeedSensitivity, SegmentMetric


StrategySection = Tuple[str, SegmentMetric, Sequence[SegmentMetric]]


def render_stability_report(
    seed_sensitivity: SeedSensitivity,
    strategy_sections: Iterable[StrategySection],
    game_label: str,
    metric_label: str = "直选命中",
) -> str:
    lines = [
        f"{game_label}策略稳定性报告",
        "奖金口径：金额为模拟票面奖金，浮动奖缺失实际单注奖金时采用估算，未扣税，不代表实际领取收益。",
        "",
        "随机种子敏感性：",
        f"随机种子数量：{seed_sensitivity.seed_count}",
        f"平均返奖率：{_format_percent(seed_sensitivity.average_roi)}",
        f"最低返奖率：{_format_percent(seed_sensitivity.min_roi)}",
        f"最高返奖率：{_format_percent(seed_sensitivity.max_roi)}",
        f"平均{metric_label}：{seed_sensitivity.average_direct_hits:.2f}",
    ]

    for name, overall, segments in strategy_sections:
        lines.extend([
            "",
            name,
            _render_metric_row("总体", overall, metric_label),
            "年份 | 投注注数 | 投入金额 | 中奖金额 | 返奖率 | " + metric_label,
            "--- | ---: | ---: | ---: | ---: | ---:",
        ])
        if segments:
            lines.extend(_render_metric_row(metric.segment, metric, metric_label) for metric in segments)
        else:
            lines.append("暂无分段数据")

    lines.extend([
        "",
        "风险提示：稳定性分析只衡量历史模拟结果，彩票具有强随机性，不能保证命中。",
    ])
    return "\n".join(lines)


def _render_metric_row(label: str, metric: SegmentMetric, metric_label: str) -> str:
    return " | ".join([
        label,
        str(metric.total_bets),
        _format_number(metric.total_cost),
        _format_number(metric.total_payout),
        _format_percent(metric.roi),
        str(metric.direct_hits),
    ])


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
