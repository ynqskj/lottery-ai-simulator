"""Issue-aware single-ticket awards, preserving the legacy game APIs.

The third return value identifies official, fixed, or estimated payout amounts.
Historical floating awards require the draw's official prize_amounts metadata.
"""
from math import isfinite

from lottery_sim.games.dlt import DltGame
from lottery_sim.games.qxc import QxcGame
from lottery_sim.games.qlc import QlcGame
from lottery_sim.games.ssq import SsqGame
from lottery_sim.issue_calendar import normalize_issue


def game_for_draw(game, draw):
    if isinstance(game, DltGame):
        return DltGame(draw.issue, getattr(draw, "prize_pool", None))
    if isinstance(game, QxcGame):
        return QxcGame(draw.issue)
    if isinstance(game, SsqGame):
        active = getattr(draw, "special_prize_active", None) if normalize_issue(draw.issue) >= 2026014 else False
        return SsqGame(active)
    return game


def evaluate_draw_prize(game, draw, pick):
    contextual = game_for_draw(game, draw)
    if hasattr(contextual, "prize_level"):
        level = contextual.prize_level(draw.numbers, pick)
    else:
        level = "直选" if contextual.match(draw.numbers, pick) else "未中奖"
    official = getattr(draw, "prize_amounts", {}) or {}
    if level in official:
        amount = official[level]
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not isfinite(amount) or amount < 0:
            raise ValueError(f"Invalid official prize amount for {level}: {amount}")
        return level, amount, "official"
    payout = contextual.payout(draw.numbers, pick)
    basis = "estimated" if level in ("一等奖", "二等奖") else "fixed"
    if isinstance(contextual, QlcGame) and level == "三等奖":
        basis = "estimated"
    if isinstance(contextual, DltGame):
        if contextual.rule_version in ("old6", "old8") and level == "三等奖":
            basis = "estimated"
        if contextual.rule_version == "new7" and contextual.prize_pool is None and level != "未中奖":
            basis = "estimated"
    if isinstance(contextual, SsqGame) and contextual.special_prize_active is None:
        if contextual.match_counts(draw.numbers, pick) == (3, 0):
            basis = "estimated"
    return level, payout, basis
