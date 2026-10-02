from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple


@dataclass(frozen=True)
class IssueRule:
    game_code: str
    draw_weekdays: Tuple[int, ...]
    year_digits: int
    sequence_digits: int
    note: str


@dataclass(frozen=True)
class NextIssue:
    issue: str
    draw_date: date
    basis: str = "estimated"


# Ministry of Finance annual lottery market closure notices:
# https://zhs.mof.gov.cn/zhengcefabu/202412/t20241206_3949123.htm
# https://www.mof.gov.cn/gp/xxgkml/zhs/202512/t20251225_3980248.htm
_CLOSURES = {
    2025: ((date(2025, 1, 27), date(2025, 2, 5)), (date(2025, 10, 1), date(2025, 10, 4))),
    2026: ((date(2026, 2, 14), date(2026, 2, 23)), (date(2026, 10, 1), date(2026, 10, 4))),
}


def normalize_issue(issue: str) -> int:
    """Return YYYYNNN for the supported YYNNN and YYYYNNN formats."""
    if not isinstance(issue, str) or not issue.isascii() or not issue.isdigit() or len(issue) not in (5, 7):
        raise ValueError(f"Invalid issue: {issue}")
    year = int(issue[:-3]) + (2000 if len(issue) == 5 else 0)
    sequence = int(issue[-3:])
    if not 1900 <= year <= 2099 or sequence == 0 or sequence > 366:
        raise ValueError(f"Invalid issue: {issue}")
    return year * 1000 + sequence


_RULES: Dict[str, IssueRule] = {
    "3d": IssueRule("3d", (0, 1, 2, 3, 4, 5, 6), 4, 3, "daily"),
    "pl3": IssueRule("pl3", (0, 1, 2, 3, 4, 5, 6), 4, 3, "daily"),
    "pl5": IssueRule("pl5", (0, 1, 2, 3, 4, 5, 6), 4, 3, "daily"),
    "kl8": IssueRule("kl8", (0, 1, 2, 3, 4, 5, 6), 4, 3, "daily"),
    "ssq": IssueRule("ssq", (1, 3, 6), 4, 3, "Tue/Thu/Sun"),
    "qlc": IssueRule("qlc", (0, 2, 4), 4, 3, "Mon/Wed/Fri"),
    "dlt": IssueRule("dlt", (0, 2, 5), 2, 3, "Mon/Wed/Sat"),
    "qxc": IssueRule("qxc", (1, 4, 6), 2, 3, "Tue/Fri/Sun"),
}


def get_issue_rule(game_code: str) -> IssueRule:
    try:
        return _RULES[game_code]
    except KeyError as exc:
        raise ValueError(f"Unsupported game code: {game_code}") from exc


def is_scheduled_draw_date(game_code: str, value: date) -> bool:
    return (value.weekday() in get_issue_rule(game_code).draw_weekdays
            and not any(start <= value <= end for start, end in _CLOSURES.get(value.year, ())))


def next_scheduled_draw_date(game_code: str, after_date: date) -> date:
    current = after_date + timedelta(days=1)
    for _ in range(32):
        if is_scheduled_draw_date(game_code, current):
            return current
        current += timedelta(days=1)
    raise ValueError(f"No scheduled draw date found for {game_code} after {after_date}")


def next_issue_from_latest_draw(game_code: str, latest_issue: str, latest_draw_date: str) -> NextIssue:
    latest_date = _parse_date(latest_draw_date)
    normalized = normalize_issue(latest_issue)
    if normalized // 1000 != latest_date.year:
        raise ValueError("Issue year does not match draw date")
    target_date = next_scheduled_draw_date(game_code, latest_date)
    return NextIssue(
        issue=_next_issue_number(get_issue_rule(game_code), latest_issue, latest_date, target_date),
        draw_date=target_date,
        basis="scheduled" if latest_date.year in _CLOSURES and target_date.year in _CLOSURES else "estimated",
    )


def _next_issue_number(rule: IssueRule, latest_issue: str, latest_date: date, target_date: date) -> str:
    normalize_issue(latest_issue)
    year_digits = len(latest_issue) - rule.sequence_digits

    if target_date.year != latest_date.year:
        sequence = 1
    else:
        sequence = int(latest_issue[year_digits:]) + 1
    if sequence > 366:
        raise ValueError("Issue sequence exceeds annual limit")

    year_prefix = str(target_date.year)[-year_digits:]
    return f"{year_prefix}{sequence:0{rule.sequence_digits}d}"


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
