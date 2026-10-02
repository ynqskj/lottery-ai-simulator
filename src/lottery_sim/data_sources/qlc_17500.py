import csv

from lottery_sim.draw_metadata import METADATA_FIELDS, metadata_from_row, metadata_to_row
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from lottery_sim.data_sources.fucai3d_17500 import fetch_17500_text
from lottery_sim.models import DrawQLC, QlcDrawNumbers


DEFAULT_17500_QLC_ASC_URL = "http://data.17500.cn/7lc_asc.txt"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISSUE_RE = re.compile(r"^\d{5,8}$")


def fetch_17500_qlc_text(url: str = DEFAULT_17500_QLC_ASC_URL, timeout: int = 20) -> str:
    return fetch_17500_text(url=url, timeout=timeout)


def parse_17500_qlc_text(text: str) -> List[DrawQLC]:
    by_issue = {}
    for raw_line in text.splitlines():
        draw = _parse_line(raw_line)
        if draw is None:
            continue
        by_issue.setdefault(draw.issue, draw)
    return sorted(by_issue.values(), key=lambda draw: int(draw.issue))


def save_qlc_draws_csv(draws: Iterable[DrawQLC], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["issue", "draw_date", "basic", "special", "source"] + METADATA_FIELDS)
        writer.writeheader()
        for draw in draws:
            writer.writerow({
                "issue": draw.issue,
                "draw_date": draw.draw_date,
                "basic": draw.numbers.basic_text,
                "special": f"{draw.numbers.special:02d}",
                "source": draw.source,
                **metadata_to_row(draw),
            })


def load_qlc_draws_csv(path: Path) -> List[DrawQLC]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            DrawQLC(
                issue=row["issue"],
                draw_date=row["draw_date"],
                numbers=QlcDrawNumbers(
                    basic=_parse_basic_text(row["basic"]),
                    special=int(row["special"]),
                ),
                source=row.get("source") or "local",
                **metadata_from_row(row),
            )
            for row in rows
        ]


def _parse_line(raw_line: str) -> Optional[DrawQLC]:
    line = raw_line.strip()
    if not line or "期号" in line or "鏈熷彿" in line:
        return None

    tokens = re.split(r"[\s,\t]+", line)
    issue_index = _find_issue_index(tokens)
    if issue_index is None:
        return None

    issue = tokens[issue_index]
    date_index = _find_date_index(tokens, issue_index + 1)
    if date_index is None:
        return None

    draw_date = tokens[date_index]
    if not _valid_date(draw_date):
        return None

    numbers = _find_numbers_after_date(tokens, date_index + 1)
    if numbers is None:
        return None

    return DrawQLC(issue=issue, draw_date=draw_date, numbers=numbers)


def _find_issue_index(tokens: List[str]) -> Optional[int]:
    for index, token in enumerate(tokens):
        if _ISSUE_RE.match(token):
            return index
    return None


def _find_date_index(tokens: List[str], start: int) -> Optional[int]:
    for index in range(start, len(tokens)):
        if _DATE_RE.match(tokens[index]):
            return index
    return None


def _find_numbers_after_date(tokens: List[str], start: int) -> Optional[QlcDrawNumbers]:
    values = []
    for token in tokens[start:]:
        if re.fullmatch(r"\d{1,2}", token):
            values.append(int(token))
        else:
            break
        if len(values) == 8:
            break

    if len(values) != 8:
        return None

    basic = tuple(values[:7])
    special = values[7]
    if not _valid_basic(basic) or not _valid_special(special, basic):
        return None
    return QlcDrawNumbers(basic=basic, special=special)  # type: ignore[arg-type]


def _parse_basic_text(value: str) -> Tuple[int, int, int, int, int, int, int]:
    parts = tuple(int(part) for part in value.split())
    if not _valid_basic(parts):
        raise ValueError(f"七乐彩基本号码格式不合法: {value}")
    return parts  # type: ignore[return-value]


def _valid_basic(basic: Tuple[int, ...]) -> bool:
    return len(basic) == 7 and len(set(basic)) == 7 and all(1 <= value <= 30 for value in basic)


def _valid_special(value: int, basic: Tuple[int, ...]) -> bool:
    return 1 <= value <= 30 and value not in set(basic)


def _valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
