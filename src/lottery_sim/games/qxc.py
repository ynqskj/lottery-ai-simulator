from typing import Tuple

from lottery_sim.models import QxcPick


class QxcGame:
    name = "7星彩"
    ticket_cost = 2
    # 一、二等奖为浮动奖，这里使用估算值保证历史模拟可以统一比较。
    prize_amounts = {
        "一等奖": 5_000_000,
        "二等奖": 100_000,
        "三等奖": 3000,
        "四等奖": 500,
        "五等奖": 30,
        "六等奖": 5,
        "未中奖": 0,
    }

    def __init__(self, issue=None):
        from lottery_sim.issue_calendar import normalize_issue
        # https://www.sport.gov.cn/cpzx/n5656/c964843/content.html
        self.legacy = issue is not None and normalize_issue(issue) < 2020100
        self.prize_amounts = dict(type(self).prize_amounts)
        if self.legacy:
            self.prize_amounts.update({"三等奖": 1800, "四等奖": 300, "五等奖": 20})

    def validate_pick(self, pick: QxcPick) -> QxcPick:
        if len(pick.front) != 6:
            raise ValueError("7星彩前六位必须包含6个号码")
        if not all(isinstance(value, int) and 0 <= value <= 9 for value in pick.front):
            raise ValueError("7星彩前六位号码必须在0到9之间")
        maximum = 9 if self.legacy else 14
        if not isinstance(pick.special, int) or not 0 <= pick.special <= maximum:
            raise ValueError(f"7星彩最后一位号码必须在0到{maximum}之间")
        return pick

    def match_counts(self, draw_numbers: QxcPick, pick_numbers: QxcPick) -> Tuple[int, int]:
        draw = self.validate_pick(draw_numbers)
        pick = self.validate_pick(pick_numbers)
        front_hits = sum(
            1
            for draw_value, pick_value in zip(draw.front, pick.front)
            if draw_value == pick_value
        )
        special_hits = 1 if draw.special == pick.special else 0
        return front_hits, special_hits

    def prize_level(self, draw_numbers: QxcPick, pick_numbers: QxcPick) -> str:
        if self.legacy:
            draw = self.validate_pick(draw_numbers)
            pick = self.validate_pick(pick_numbers)
            longest = run = 0
            for drawn, chosen in zip((*draw.front, draw.special), (*pick.front, pick.special)):
                run = run + 1 if drawn == chosen else 0
                longest = max(longest, run)
            return {7: "一等奖", 6: "二等奖", 5: "三等奖", 4: "四等奖", 3: "五等奖", 2: "六等奖"}.get(longest, "未中奖")
        front_hits, special_hits = self.match_counts(draw_numbers, pick_numbers)
        if front_hits == 6 and special_hits == 1:
            return "一等奖"
        if front_hits == 6 and special_hits == 0:
            return "二等奖"
        if front_hits == 5 and special_hits == 1:
            return "三等奖"
        if (front_hits == 5 and special_hits == 0) or (front_hits == 4 and special_hits == 1):
            return "四等奖"
        if (front_hits == 4 and special_hits == 0) or (front_hits == 3 and special_hits == 1):
            return "五等奖"
        if (
            (front_hits == 3 and special_hits == 0)
            or (front_hits == 2 and special_hits == 1)
            or (front_hits == 1 and special_hits == 1)
            or (front_hits == 0 and special_hits == 1)
        ):
            return "六等奖"
        return "未中奖"

    def payout(self, draw_numbers: QxcPick, pick_numbers: QxcPick) -> int:
        return self.prize_amounts[self.prize_level(draw_numbers, pick_numbers)]
