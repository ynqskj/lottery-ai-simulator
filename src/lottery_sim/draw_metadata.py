"""Optional CSV award context; absent values never imply official amounts."""
import json
from math import isfinite


METADATA_FIELDS = ["prize_amounts", "special_prize_active", "prize_pool"]
PAYOUT_BASIS_LABELS = {"official": "官方公布单注奖金", "fixed": "规则固定奖金", "estimated": "估算奖金"}


def _amount(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value) or value < 0:
        raise ValueError("奖金或奖池必须是有限的非负数")
    return value


def metadata_from_row(row):
    prizes = json.loads(row.get("prize_amounts") or "{}")
    if not isinstance(prizes, dict) or not all(isinstance(key, str) for key in prizes):
        raise ValueError("prize_amounts 必须是奖级到单注奖金的 JSON 对象")
    prizes = {key: _amount(value) for key, value in prizes.items()}
    raw_active = (row.get("special_prize_active") or "").strip().lower()
    if raw_active not in ("", "true", "false", "1", "0"):
        raise ValueError("special_prize_active 必须是 true、false 或空值")
    active = None if not raw_active else raw_active in ("true", "1")
    raw_pool = row.get("prize_pool") or ""
    pool = _amount(float(raw_pool)) if raw_pool else None
    return dict(prize_amounts=prizes, special_prize_active=active, prize_pool=pool)


def metadata_to_row(draw):
    active = getattr(draw, "special_prize_active", None)
    return {
        "prize_amounts": json.dumps(getattr(draw, "prize_amounts", {}) or {}, ensure_ascii=False, allow_nan=False),
        "special_prize_active": "" if active is None else "true" if active else "false",
        "prize_pool": "" if getattr(draw, "prize_pool", None) is None else draw.prize_pool,
    }


def payout_basis_summary(records):
    counts = {}
    for record in records:
        basis = getattr(record, "payout_basis", "estimated")
        label = PAYOUT_BASIS_LABELS.get(basis, PAYOUT_BASIS_LABELS["estimated"])
        counts[label] = counts.get(label, 0) + 1
    detail = "；".join(f"{label} {count} 注" for label, count in counts.items()) or "暂无投注"
    return f"奖金口径：{detail}。金额为模拟票面奖金，未扣税，不代表实际领取收益。"
