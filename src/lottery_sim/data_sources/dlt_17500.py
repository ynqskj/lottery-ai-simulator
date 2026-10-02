import csv

from lottery_sim.draw_metadata import METADATA_FIELDS, metadata_from_row, metadata_to_row
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from lottery_sim.data_sources.fucai3d_17500 import fetch_17500_text
from lottery_sim.models import DltPick, DrawDLT


DEFAULT_17500_DLT_ASC_URL = "http://data.17500.cn/dlt_asc.txt"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISSUE_RE = re.compile(r"^\d{5,8}$")


def fetch_17500_dlt_text(url: str = DEFAULT_17500_DLT_ASC_URL, timeout: int = 20) -> str:
    return fetch_17500_text(url=url, timeout=timeout)


def parse_17500_dlt_text(text: str) -> List[DrawDLT]:
    by_issue = {}
    for raw_line in text.splitlines():
        draw = _parse_line(raw_line)
        if draw is None:
            continue
        by_issue.setdefault(draw.issue, draw)
    return sorted(by_issue.values(), key=lambda draw: int(draw.issue))


def save_dlt_draws_csv(draws: Iterable[DrawDLT], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["issue", "draw_date", "front", "back", "source"] + METADATA_FIELDS)
        writer.writeheader()
        for draw in draws:
            writer.writerow({
                "issue": draw.issue,
                "draw_date": draw.draw_date,
                "front": draw.numbers.front_text,
                "back": draw.numbers.back_text,
                "source": draw.source,
                **metadata_to_row(draw),
            })


def load_dlt_draws_csv(path: Path) -> List[DrawDLT]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            DrawDLT(
                issue=row["issue"],
                draw_date=row["draw_date"],
                numbers=DltPick(
                    front=_parse_front_text(row["front"]),
                    back=_parse_back_text(row["back"]),
                ),
                source=row.get("source") or "local",
                **metadata_from_row(row),
            )
            for row in rows
        ]


def _parse_line(raw_line: str) -> Optional[DrawDLT]:
    line = raw_line.strip()
    if not line or "期号" in line:
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

    return DrawDLT(issue=issue, draw_date=draw_date, numbers=numbers)


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


def _find_numbers_after_date(tokens: List[str], start: int) -> Optional[DltPick]:
    values = []
    for token in tokens[start:]:
        if re.fullmatch(r"\d{1,2}", token):
            values.append(int(token))
        else:
            break
        if len(values) == 7:
            break

    if len(values) != 7:
        return None

    front = tuple(values[:5])
    back = tuple(values[5:7])
    if not _valid_front(front) or not _valid_back(back):
        return None
    return DltPick(front=front, back=back)  # type: ignore[arg-type]


def _parse_front_text(value: str) -> Tuple[int, int, int, int, int]:
    parts = tuple(int(part) for part in value.split())
    if not _valid_front(parts):
        raise ValueError(f"大乐透前区格式不合法: {value}")
    return parts  # type: ignore[return-value]


def _parse_back_text(value: str) -> Tuple[int, int]:
    parts = tuple(int(part) for part in value.split())
    if not _valid_back(parts):
        raise ValueError(f"大乐透后区格式不合法: {value}")
    return parts  # type: ignore[return-value]


def _valid_front(front: Tuple[int, ...]) -> bool:
    return len(front) == 5 and len(set(front)) == 5 and all(1 <= value <= 35 for value in front)


def _valid_back(back: Tuple[int, ...]) -> bool:
    return len(back) == 2 and len(set(back)) == 2 and all(1 <= value <= 12 for value in back)


def _valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
