from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from lottery_sim.draw_metadata import payout_basis_summary
from lottery_sim.recommendation_tracking import RecommendationRecord, load_recommendation_records


@dataclass(frozen=True)
class StrategyRecommendationSummary:
    game_code: str
    game_name: str
    strategy_name: str
    total_records: int
    checked_count: int
    pending_count: int
    winning_count: int
    total_cost: float
    total_payout: float
    payout_note: str = "奖金口径：含历史估算，非实际领取收益。"

    @property
    def hit_rate(self) -> float:
        if self.checked_count == 0:
            return 0.0
        return self.winning_count / self.checked_count

    @property
    def roi(self) -> float:
        if self.total_cost == 0:
            return 0.0
        return self.total_payout / self.total_cost


@dataclass(frozen=True)
class RecommendationSummaryResult:
    strategy_summaries: Tuple[StrategyRecommendationSummary, ...]
    total_records: int
    checked_count: int
    pending_count: int
    winning_count: int
    total_cost: float
    total_payout: float
    payout_note: str = "奖金口径：含历史估算，非实际领取收益。"

    @property
    def hit_rate(self) -> float:
        if self.checked_count == 0:
            return 0.0
        return self.winning_count / self.checked_count

    @property
    def roi(self) -> float:
        if self.total_cost == 0:
            return 0.0
        return self.total_payout / self.total_cost


def load_records_from_paths(paths: Sequence[Path]) -> List[RecommendationRecord]:
    records: List[RecommendationRecord] = []
    for path in paths:
        records.extend(load_recommendation_records(Path(path)))
    return records


def summarize_recommendation_records(records: Iterable[RecommendationRecord]) -> RecommendationSummaryResult:
    from lottery_sim.recommendation_store import unique_recommendation_records
    record_list = unique_recommendation_records(records)
    buckets: Dict[Tuple[str, str, str], List[RecommendationRecord]] = {}
    for record in record_list:
        key = (record.game_code, record.game_name, record.strategy_name)
        buckets.setdefault(key, []).append(record)

    strategy_summaries = tuple(
        _summarize_strategy(game_code, game_name, strategy_name, bucket)
        for (game_code, game_name, strategy_name), bucket in sorted(buckets.items())
    )
    checked = [record for record in record_list if record.status == "checked"]

    return RecommendationSummaryResult(
        strategy_summaries=strategy_summaries,
        total_records=len(record_list),
        checked_count=len(checked),
        pending_count=sum(1 for record in record_list if record.status == "pending"),
        winning_count=sum(1 for record in checked if record.payout > 0),
        total_cost=sum(record.cost for record in checked),
        total_payout=sum(record.payout for record in checked),
        payout_note=payout_basis_summary(checked),
    )


def render_recommendation_summary_report(result: RecommendationSummaryResult) -> str:
    lines = [
        "推荐长期表现汇总",
        "统计口径：同一期、同策略、同号码只统计一次；所有生成批次保留。",
        result.payout_note,
        "",
        f"记录总数：{result.total_records}",
        f"已校验：{result.checked_count}",
        f"待开奖：{result.pending_count}",
        f"中奖记录：{result.winning_count}",
        f"已校验命中率：{_format_percent(result.hit_rate)}",
        f"总投入：{_format_number(result.total_cost)}",
        f"总奖金：{_format_number(result.total_payout)}",
        f"投资回报率：{result.roi:.2f}",
        "",
        "彩种 | 策略 | 记录 | 已校验 | 待开奖 | 中奖 | 命中率 | 投入 | 奖金 | ROI",
        "--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:",
    ]

    for summary in result.strategy_summaries:
        lines.append(
            f"{summary.game_name} | "
            f"{summary.strategy_name} | "
            f"{summary.total_records} | "
            f"{summary.checked_count} | "
            f"{summary.pending_count} | "
            f"{summary.winning_count} | "
            f"{_format_percent(summary.hit_rate)} | "
            f"{_format_number(summary.total_cost)} | "
            f"{_format_number(summary.total_payout)} | "
            f"{summary.roi:.2f}"
        )

    lines.extend([
        "",
        "风险提示：长期表现汇总只衡量已记录的历史模拟结果，彩票具有强随机性，不能保证命中。",
    ])
    return "\n".join(lines)


def _summarize_strategy(
    game_code: str,
    game_name: str,
    strategy_name: str,
    records: Sequence[RecommendationRecord],
) -> StrategyRecommendationSummary:
    checked = [record for record in records if record.status == "checked"]
    return StrategyRecommendationSummary(
        game_code=game_code,
        game_name=game_name,
        strategy_name=strategy_name,
        total_records=len(records),
        checked_count=len(checked),
        pending_count=sum(1 for record in records if record.status == "pending"),
        winning_count=sum(1 for record in checked if record.payout > 0),
        total_cost=sum(record.cost for record in checked),
        total_payout=sum(record.payout for record in checked),
    )


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
