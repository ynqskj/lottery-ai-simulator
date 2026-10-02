from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.file_io import file_lock
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from lottery_sim.recommendation_tracking import (
    RecommendationRecord,
    load_recommendation_records,
    save_recommendation_records,
)


class RecommendationStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def record_path(self, game_code: str, target_issue: str) -> Path:
        return self.root / game_code / f"{target_issue}.csv"

    def append_records(self, records: Sequence[RecommendationRecord]) -> Tuple[Path, int, int]:
        if not records:
            raise ValueError("records must not be empty")

        first = records[0]
        path = self.record_path(first.game_code, first.target_issue)
        if any(r.game_code != first.game_code or r.target_issue != first.target_issue for r in records):
            raise ValueError("一个保存批次只能包含同彩种同目标期")
        with file_lock(path):
            existing = load_recommendation_records(path) if path.exists() else []
            merged, added = merge_unique_recommendation_records(existing, records)
            save_recommendation_records(merged, path)
        return path, added, len(merged)


    def all_record_paths(self) -> Tuple[Path, ...]:
        if not self.root.exists():
            return ()
        return tuple(sorted(path for path in self.root.glob("*/*.csv") if path.is_file()))


def merge_unique_recommendation_records(
    existing: Sequence[RecommendationRecord],
    incoming: Iterable[RecommendationRecord],
) -> Tuple[List[RecommendationRecord], int]:
    merged: List[RecommendationRecord] = []
    indexes = {}
    for record in existing:
        key = _record_key(record)
        if key not in indexes:
            indexes[key] = len(merged)
            merged.append(record)
            continue
        current_index = indexes[key]
        merged[current_index] = _prefer_record(merged[current_index], record)

    added = 0

    for record in incoming:
        key = _record_key(record)
        if key in indexes:
            current_index = indexes[key]
            merged[current_index] = _prefer_record(merged[current_index], record)
            continue
        indexes[key] = len(merged)
        merged.append(record)
        added += 1

    return merged, added


def _prefer_record(left: RecommendationRecord, right: RecommendationRecord) -> RecommendationRecord:
    if _record_completeness(right) > _record_completeness(left):
        return right
    return left


def _record_completeness(record: RecommendationRecord) -> Tuple[int, int, int, float]:
    return (
        1 if record.status == "checked" else 0,
        1 if record.draw_numbers else 0,
        1 if record.prize_level else 0,
        record.payout,
    )


def _record_key(record: RecommendationRecord) -> tuple:
    return (
        record.game_code,
        normalize_issue(record.target_issue),
        record.strategy_name,
        record.numbers,
        record.run_id or record.generated_at,
    )


def unique_recommendation_records(records):
    """Keep batches on disk, count each strategy/issue/pick once in aggregate."""
    unique = {}
    for record in records:
        key = (record.game_code, normalize_issue(record.target_issue), record.strategy_name, record.numbers)
        unique[key] = _prefer_record(unique[key], record) if key in unique else record
    return list(unique.values())
