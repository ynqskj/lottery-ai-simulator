from lottery_sim.issue_calendar import normalize_issue
import csv
from dataclasses import dataclass
from datetime import datetime, time as datetime_time
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from lottery_sim.draw_metadata import PAYOUT_BASIS_LABELS, payout_basis_summary
from lottery_sim.prize_rules import evaluate_draw_prize, game_for_draw
from lottery_sim.file_io import atomic_path
from lottery_sim.models import DltPick, Kl8Pick, QlcPick, QxcPick, SsqPick


@dataclass(frozen=True)
class RecommendationWindow:
    history: Tuple[Any, ...]
    history_until_issue: str
    target_issue: str


@dataclass(frozen=True)
class RecommendationRecord:
    game_code: str
    game_name: str
    history_until_issue: str
    target_issue: str
    rank: int
    strategy_name: str
    numbers: str
    reason: str
    status: str = "pending"
    draw_numbers: str = ""
    prize_level: str = ""
    cost: float = 2
    payout: float = 0
    generated_at: str = ""
    run_id: str = ""
    payout_basis: str = "estimated"


@dataclass(frozen=True)
class RecommendationVerificationResult:
    game_name: str
    records: Tuple[RecommendationRecord, ...]
    total_records: int
    checked_count: int
    pending_count: int
    winning_count: int
    total_cost: float
    total_payout: float

    @property
    def roi(self) -> float:
        if self.total_cost == 0:
            return 0.0
        return self.total_payout / self.total_cost


_CSV_FIELDS = [
    "game_code",
    "game_name",
    "history_until_issue",
    "target_issue",
    "rank",
    "strategy_name",
    "numbers",
    "reason",
    "status",
    "draw_numbers",
    "prize_level",
    "cost",
    "payout",
    "generated_at",
    "run_id",
    "payout_basis",
]

DRAW_READY_TIME = datetime_time(22, 0)


def select_recommendation_window(
    draws: Sequence[Any],
    target_issue: str = "",
    history_until_issue: str = "",
) -> RecommendationWindow:
    ordered = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    if not ordered:
        raise ValueError("没有可用于生成推荐的历史开奖数据")

    if target_issue and history_until_issue and normalize_issue(history_until_issue) >= normalize_issue(target_issue):
        raise ValueError("历史截止期号必须早于目标期号，避免使用目标期开奖数据")

    if history_until_issue:
        history = tuple(draw for draw in ordered if normalize_issue(draw.issue) <= normalize_issue(history_until_issue))
    elif target_issue:
        history = tuple(draw for draw in ordered if normalize_issue(draw.issue) < normalize_issue(target_issue))
    else:
        history = ordered

    if not history:
        raise ValueError("推荐历史窗口为空，请检查目标期号或历史截止期号")

    latest_issue = history[-1].issue
    return RecommendationWindow(
        history=history,
        history_until_issue=latest_issue,
        target_issue=target_issue or _next_issue(latest_issue),
    )


def available_recommendation_draws(
    draws: Sequence[Any],
    as_of: Optional[datetime] = None,
) -> Tuple[Any, ...]:
    now = as_of or datetime.now()
    return tuple(draw for draw in draws if _draw_is_ready(draw, now))


def create_recommendation_records(
    game_code: str,
    game_name: str,
    candidates: Iterable[Any],
    target_issue: str,
    history_until_issue: str,
    ticket_cost: float,
    generated_at: Optional[str] = None,
    run_id: Optional[str] = None,
) -> List[RecommendationRecord]:
    batch_time = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_id = run_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
    return [
        RecommendationRecord(
            game_code=game_code,
            game_name=game_name,
            history_until_issue=history_until_issue,
            target_issue=target_issue,
            rank=candidate.rank,
            strategy_name=candidate.strategy_name,
            numbers=candidate.number_text,
            reason=candidate.reason,
            cost=ticket_cost,
            generated_at=batch_time,
            run_id=batch_id,
        )
        for candidate in candidates
    ]


def save_recommendation_records(records: Iterable[RecommendationRecord], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(path) as temporary, temporary.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({
                "game_code": record.game_code,
                "game_name": record.game_name,
                "history_until_issue": record.history_until_issue,
                "target_issue": record.target_issue,
                "rank": record.rank,
                "strategy_name": record.strategy_name,
                "numbers": record.numbers,
                "reason": record.reason,
                "status": record.status,
                "draw_numbers": record.draw_numbers,
                "prize_level": record.prize_level,
                "cost": _format_number(record.cost),
                "payout": _format_number(record.payout),
                "generated_at": record.generated_at,
                "run_id": record.run_id,
                "payout_basis": record.payout_basis,
            })


def load_recommendation_records(path: Path) -> List[RecommendationRecord]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            RecommendationRecord(
                game_code=row["game_code"],
                game_name=row["game_name"],
                history_until_issue=row["history_until_issue"],
                target_issue=row["target_issue"],
                rank=int(row["rank"]),
                strategy_name=row["strategy_name"],
                numbers=row["numbers"],
                reason=row["reason"],
                status=row.get("status") or "pending",
                draw_numbers=row.get("draw_numbers") or "",
                prize_level=row.get("prize_level") or "",
                cost=float(row.get("cost") or 2),
                payout=float(row.get("payout") or 0),
                generated_at=row.get("generated_at") or "",
                run_id=row.get("run_id") or "",
                payout_basis=row.get("payout_basis") or "estimated",
            )
            for row in rows
        ]


def evaluate_recommendation_records(
    records: Sequence[RecommendationRecord],
    draws: Sequence[Any],
    game: Any,
    pick_parser: Callable[[str], Any],
    as_of: Optional[datetime] = None,
) -> RecommendationVerificationResult:
    now = as_of or datetime.now()
    draw_by_issue = {normalize_issue(draw.issue): draw for draw in draws}
    evaluated: List[RecommendationRecord] = []

    for record in records:
        draw = draw_by_issue.get(normalize_issue(record.target_issue))
        if draw is None or not _draw_is_ready(draw, now):
            evaluated.append(RecommendationRecord(
                game_code=record.game_code,
                game_name=record.game_name,
                history_until_issue=record.history_until_issue,
                target_issue=record.target_issue,
                rank=record.rank,
                strategy_name=record.strategy_name,
                numbers=record.numbers,
                reason=record.reason,
                status="pending",
                draw_numbers="",
                prize_level="",
                cost=record.cost,
                payout=0,
                generated_at=record.generated_at,
                run_id=record.run_id,
            ))
            continue

        pick = game_for_draw(game, draw).validate_pick(pick_parser(record.numbers))
        level, payout, payout_basis = evaluate_draw_prize(game, draw, pick)
        evaluated.append(RecommendationRecord(
            game_code=record.game_code,
            game_name=record.game_name,
            history_until_issue=record.history_until_issue,
            target_issue=record.target_issue,
            rank=record.rank,
            strategy_name=record.strategy_name,
            numbers=record.numbers,
            reason=record.reason,
            status="checked",
            draw_numbers=_number_text(draw),
            prize_level=level,
            cost=record.cost,
            payout=payout,
            payout_basis=payout_basis,
            generated_at=record.generated_at,
            run_id=record.run_id,
        ))

    checked = [record for record in evaluated if record.status == "checked"]
    total_cost = sum(record.cost for record in checked)
    total_payout = sum(record.payout for record in checked)
    winning_count = sum(1 for record in checked if record.payout > 0)
    game_name = records[0].game_name if records else getattr(game, "name", "彩票")

    return RecommendationVerificationResult(
        game_name=game_name,
        records=tuple(evaluated),
        total_records=len(evaluated),
        checked_count=len(checked),
        pending_count=sum(1 for record in evaluated if record.status == "pending"),
        winning_count=winning_count,
        total_cost=total_cost,
        total_payout=total_payout,
    )


def render_recommendation_verification_report(result: RecommendationVerificationResult) -> str:
    lines = [
        f"{result.game_name} 推荐校验报告",
        "",
        f"推荐记录：{result.total_records}",
        f"已校验：{result.checked_count}",
        f"待开奖：{result.pending_count}",
        f"中奖记录：{result.winning_count}",
        f"总投入：{_format_number(result.total_cost)}",
        f"总奖金：{_format_number(result.total_payout)}",
        payout_basis_summary(record for record in result.records if record.status == "checked"),
        f"投资回报率：{result.roi:.2f}",
        "",
        "期号 | 批次 | 生成时间 | 排名 | 策略 | 推荐号码 | 开奖号码 | 奖级 | 奖金 | 奖金口径 | 状态",
        "--- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- | ---",
    ]
    for record in result.records:
        lines.append(
            f"{record.target_issue} | "
            f"{record.run_id or '-'} | "
            f"{record.generated_at or '-'} | "
            f"{record.rank} | "
            f"{record.strategy_name} | "
            f"{record.numbers} | "
            f"{record.draw_numbers or '-'} | "
            f"{record.prize_level or '-'} | "
            f"{_format_number(record.payout)} | "
            f"{PAYOUT_BASIS_LABELS.get(record.payout_basis, '估算奖金')} | "
            f"{record.status}"
        )

    lines.extend([
        "",
        "风险提示：推荐校验只衡量历史模拟结果，彩票具有强随机性，不能保证命中。",
    ])
    return "\n".join(lines)


def parse_pick_text(game_code: str, value: str) -> Any:
    if game_code in {"3d", "pl3"}:
        return _parse_direct_digits(value, 3)
    if game_code == "pl5":
        return _parse_direct_digits(value, 5)
    if game_code == "ssq":
        left, right = _split_compound(value)
        return SsqPick(red=_parse_int_tokens(left, 6), blue=int(right))
    if game_code == "dlt":
        left, right = _split_compound(value)
        return DltPick(front=_parse_int_tokens(left, 5), back=_parse_int_tokens(right, 2))
    if game_code == "qxc":
        left, right = _split_compound(value)
        return QxcPick(front=_parse_int_tokens(left, 6), special=int(right))
    if game_code == "qlc":
        return QlcPick(numbers=_parse_int_tokens(value, 7))
    if game_code == "kl8":
        return Kl8Pick(numbers=tuple(int(part) for part in value.split()))
    raise ValueError(f"不支持的彩种代码: {game_code}")


def _next_issue(issue: str) -> str:
    return str(int(issue) + 1).zfill(len(issue))


def _draw_is_ready(draw: Any, as_of: datetime) -> bool:
    try:
        draw_date = datetime.strptime(getattr(draw, "draw_date", ""), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    if draw_date < as_of.date():
        return True
    if draw_date > as_of.date():
        return False
    return as_of.time() >= DRAW_READY_TIME


def _parse_direct_digits(value: str, size: int) -> Tuple[int, ...]:
    parts = value.split()
    if len(parts) == size:
        return tuple(int(part) for part in parts)
    compact = "".join(ch for ch in value if ch.isdigit())
    if len(compact) != size:
        raise ValueError(f"直选号码必须是{size}位: {value}")
    return tuple(int(ch) for ch in compact)


def _split_compound(value: str) -> Tuple[str, str]:
    parts = [part.strip() for part in value.split("+")]
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"复合号码格式必须包含 + 分隔: {value}")
    return parts[0], parts[1]


def _parse_int_tokens(value: str, size: int) -> Tuple[int, ...]:
    parts = tuple(int(part) for part in value.split())
    if len(parts) != size:
        raise ValueError(f"号码数量必须是{size}个: {value}")
    return parts


def _number_text(value: Any) -> str:
    if hasattr(value, "number_text"):
        return value.number_text
    if hasattr(value, "numbers") and hasattr(value.numbers, "number_text"):
        return value.numbers.number_text
    if hasattr(value, "numbers") and hasattr(value, "number_text"):
        return value.number_text
    if hasattr(value, "numbers"):
        return _number_text(value.numbers)
    if isinstance(value, tuple):
        if value and all(isinstance(item, int) and 0 <= item <= 9 for item in value):
            return "".join(str(item) for item in value)
        return " ".join(f"{item:02d}" if isinstance(item, int) else str(item) for item in value)
    return str(value)


def _prize_level(game: Any, draw_numbers: Any, pick: Any, payout: float) -> str:
    if hasattr(game, "prize_level"):
        return game.prize_level(draw_numbers, pick)
    if payout > 0:
        return "直选命中"
    return "未中奖"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
