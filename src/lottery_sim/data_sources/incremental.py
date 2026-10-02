from dataclasses import dataclass, replace
from lottery_sim.issue_calendar import normalize_issue
from pathlib import Path
from lottery_sim.file_io import file_lock, atomic_path
from typing import Any, Callable, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class IncrementalUpdateResult:
    output_path: Path
    previous_latest_issue: str
    latest_issue: str
    added_count: int
    total_count: int
    corrected_count: int = 0

    @property
    def is_latest(self) -> bool:
        return self.total_count > 0 and self.added_count == 0 and self.corrected_count == 0


def merge_incremental_draws(existing: Sequence[Any], incoming: Iterable[Any]) -> Tuple[List[Any], List[Any]]:
    by_issue = {normalize_issue(draw.issue): draw for draw in existing}
    added: List[Any] = []

    for draw in incoming:
        issue = normalize_issue(draw.issue)
        if issue in by_issue:
            old = by_issue[issue]
            # A feed without metadata must not erase verified payouts on unchanged draws.
            if old.numbers == draw.numbers and old.draw_date == draw.draw_date:
                preserved = {key: getattr(old, key) for key in ("prize_amounts", "special_prize_active", "prize_pool")
                             if hasattr(draw, key) and getattr(draw, key) in (None, {}) and getattr(old, key) not in (None, {})}
                if preserved:
                    draw = replace(draw, **preserved)
            by_issue[issue] = draw
            continue
        by_issue[issue] = draw
        added.append(draw)

    merged = sorted(by_issue.values(), key=lambda draw: normalize_issue(draw.issue))
    added = sorted(added, key=lambda draw: normalize_issue(draw.issue))
    return merged, added


def update_draws_csv(
    path: Path,
    source_draws: Sequence[Any],
    load_csv: Callable[[Path], List[Any]],
    save_csv: Callable[[Iterable[Any], Path], None],
) -> IncrementalUpdateResult:
    output_path = Path(path)
    if not source_draws:
        raise ValueError("数据源没有有效开奖数据，未修改本地文件")
    with file_lock(output_path):
        existing = load_csv(output_path) if output_path.exists() else []
        previous_latest_issue = _latest_issue(existing)
        before = {normalize_issue(draw.issue): draw for draw in existing}
        merged, added = merge_incremental_draws(existing, source_draws)
        corrected = sum(normalize_issue(draw.issue) in before and before[normalize_issue(draw.issue)] != draw for draw in merged)
        if added or corrected or len(existing) != len(merged) or not output_path.exists():
            with atomic_path(output_path) as temporary:
                save_csv(merged, temporary)
        return IncrementalUpdateResult(
            output_path=output_path, previous_latest_issue=previous_latest_issue,
            latest_issue=_latest_issue(merged), added_count=len(added),
            total_count=len(merged), corrected_count=corrected,
        )



def render_incremental_update_result(game_name: str, result: IncrementalUpdateResult) -> str:
    lines = [
        f"{game_name}开奖数据增量更新",
        f"输出文件：{result.output_path}",
        f"更新前最新期号：{result.previous_latest_issue or '-'}",
        f"当前最新期号：{result.latest_issue or '-'}",
        f"新增期数：{result.added_count}",
        f"修正期数：{result.corrected_count}",
        f"总期数：{result.total_count}",
    ]
    if result.is_latest:
        lines.append("状态：已是最新")
    else:
        lines.append("状态：已更新开奖数据")
    return "\n".join(lines)


def _latest_issue(draws: Sequence[Any]) -> str:
    if not draws:
        return ""
    return max((draw.issue for draw in draws), key=normalize_issue)
