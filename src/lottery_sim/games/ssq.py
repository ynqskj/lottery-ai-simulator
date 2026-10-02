from typing import Tuple

from lottery_sim.models import SsqPick


class SsqGame:
    name = "双色球"
    ticket_cost = 2
    prize_amounts = {
        "一等奖": 5_000_000,
        "二等奖": 100_000,
        "三等奖": 3000,
        "四等奖": 200,
        "五等奖": 10,
        "六等奖": 5,
        "未中奖": 0,
    }

    def __init__(self, special_prize_active=False):
        self.special_prize_active = special_prize_active
        self.prize_amounts = dict(type(self).prize_amounts)
        self.prize_amounts["福运奖"] = 5

    def validate_pick(self, pick: SsqPick) -> SsqPick:
        if len(pick.red) != 6:
            raise ValueError("双色球红球必须包含6个号码")
        if len(set(pick.red)) != 6:
            raise ValueError("双色球红球不能重复")
        if not all(isinstance(value, int) and 1 <= value <= 33 for value in pick.red):
            raise ValueError("双色球红球必须在1到33之间")
        if not isinstance(pick.blue, int) or not (1 <= pick.blue <= 16):
            raise ValueError("双色球蓝球必须在1到16之间")
        return SsqPick(red=tuple(sorted(pick.red)), blue=pick.blue)  # type: ignore[arg-type]

    def match_counts(self, draw_numbers: SsqPick, pick_numbers: SsqPick) -> Tuple[int, int]:
        draw = self.validate_pick(draw_numbers)
        pick = self.validate_pick(pick_numbers)
        red_hits = len(set(draw.red) & set(pick.red))
        blue_hit = 1 if draw.blue == pick.blue else 0
        return red_hits, blue_hit

    def prize_level(self, draw_numbers: SsqPick, pick_numbers: SsqPick) -> str:
        red_hits, blue_hit = self.match_counts(draw_numbers, pick_numbers)
        if red_hits == 6 and blue_hit == 1:
            return "一等奖"
        if red_hits == 6 and blue_hit == 0:
            return "二等奖"
        if red_hits == 5 and blue_hit == 1:
            return "三等奖"
        if (red_hits == 5 and blue_hit == 0) or (red_hits == 4 and blue_hit == 1):
            return "四等奖"
        if (red_hits == 4 and blue_hit == 0) or (red_hits == 3 and blue_hit == 1):
            return "五等奖"
        if blue_hit == 1 and red_hits <= 2:
            return "六等奖"
        if red_hits == 3 and blue_hit == 0 and self.special_prize_active is True:
            return "福运奖"
        return "未中奖"

    def payout(self, draw_numbers: SsqPick, pick_numbers: SsqPick) -> int:
        return self.prize_amounts[self.prize_level(draw_numbers, pick_numbers)]
