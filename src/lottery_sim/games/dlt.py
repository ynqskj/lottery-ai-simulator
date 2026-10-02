from typing import Tuple

from lottery_sim.models import DltPick


class DltGame:
    name = "大乐透"
    ticket_cost = 2
    # 一、二等奖为浮动奖，这里用固定估算值保持历史模拟口径可比较。
    prize_amounts = {
        "一等奖": 10_000_000,
        "二等奖": 100_000,
        "三等奖": 10_000,
        "四等奖": 3000,
        "五等奖": 300,
        "六等奖": 200,
        "七等奖": 100,
        "八等奖": 15,
        "九等奖": 5,
        "未中奖": 0,
    }

    def __init__(self, issue=None, prize_pool=None):
        from lottery_sim.issue_calendar import normalize_issue
        # The nine-tier rules started at 19019, per the sports authority:
        # https://www.sport.gov.cn/n20001280/n20745751/n20767297/c21153433/content.html
        # Seven-tier amounts: https://m.lottery.gov.cn/ksjz/m/yxgz_dlt/
        normalized = normalize_issue(issue) if issue is not None else 2020001
        # Eight tiers ended at 14051; 14052 introduced six tiers:
        # https://www.sport.gov.cn/n20001280/n20745751/n20767297/c21183449/content.html
        # https://zhs.mof.gov.cn/zhengcefabu/201312/t20131219_1026921.htm
        self.rule_version = "new7" if normalized >= 2026014 else "old9" if normalized >= 2019019 else "old6" if normalized >= 2014052 else "old8"
        self.prize_pool = prize_pool
        self.prize_amounts = dict(type(self).prize_amounts)
        if self.rule_version == "old6":
            self.prize_amounts.update({"四等奖": 200, "五等奖": 10, "六等奖": 5})
        elif self.rule_version == "old8":
            self.prize_amounts.update({"四等奖": 3000, "五等奖": 600, "六等奖": 100, "七等奖": 10, "八等奖": 5})
        elif self.rule_version == "new7":
            amounts = (6666, 380, 200, 18, 7) if prize_pool is not None and prize_pool >= 800_000_000 else (5000, 300, 150, 15, 5)
            self.prize_amounts.update(zip(("三等奖", "四等奖", "五等奖", "六等奖", "七等奖"), amounts))

    def validate_pick(self, pick: DltPick) -> DltPick:
        if len(pick.front) != 5:
            raise ValueError("大乐透前区必须包含5个号码")
        if len(set(pick.front)) != 5:
            raise ValueError("大乐透前区不能重复")
        if not all(isinstance(value, int) and 1 <= value <= 35 for value in pick.front):
            raise ValueError("大乐透前区必须在1到35之间")
        if len(pick.back) != 2:
            raise ValueError("大乐透后区必须包含2个号码")
        if len(set(pick.back)) != 2:
            raise ValueError("大乐透后区不能重复")
        if not all(isinstance(value, int) and 1 <= value <= 12 for value in pick.back):
            raise ValueError("大乐透后区必须在1到12之间")
        return DltPick(
            front=tuple(sorted(pick.front)),
            back=tuple(sorted(pick.back)),
        )  # type: ignore[arg-type]

    def match_counts(self, draw_numbers: DltPick, pick_numbers: DltPick) -> Tuple[int, int]:
        draw = self.validate_pick(draw_numbers)
        pick = self.validate_pick(pick_numbers)
        front_hits = len(set(draw.front) & set(pick.front))
        back_hits = len(set(draw.back) & set(pick.back))
        return front_hits, back_hits

    def prize_level(self, draw_numbers: DltPick, pick_numbers: DltPick) -> str:
        front_hits, back_hits = self.match_counts(draw_numbers, pick_numbers)
        if self.rule_version == "old8":
            levels = {(5, 2): "一等奖", (5, 1): "二等奖", (5, 0): "三等奖", (4, 2): "四等奖", (4, 1): "五等奖", (4, 0): "六等奖", (3, 2): "六等奖", (3, 1): "七等奖", (2, 2): "七等奖"}
            levels.update({pair: "八等奖" for pair in ((3, 0), (2, 1), (1, 2), (0, 2))})
            return levels.get((front_hits, back_hits), "未中奖")
        if self.rule_version != "old9":
            levels = {(5, 2): "一等奖", (5, 1): "二等奖", (5, 0): "三等奖", (4, 2): "三等奖"}
            if self.rule_version == "old6":
                levels.update({(4, 1): "四等奖", (3, 2): "四等奖", (4, 0): "五等奖", (3, 1): "五等奖", (2, 2): "五等奖"})
                lowest = "六等奖"
            else:
                levels.update({(4, 1): "四等奖", (4, 0): "五等奖", (3, 2): "五等奖", (3, 1): "六等奖", (2, 2): "六等奖"})
                lowest = "七等奖"
            levels.update({pair: lowest for pair in ((3, 0), (2, 1), (1, 2), (0, 2))})
            return levels.get((front_hits, back_hits), "未中奖")
        if front_hits == 5 and back_hits == 2:
            return "一等奖"
        if front_hits == 5 and back_hits == 1:
            return "二等奖"
        if front_hits == 5 and back_hits == 0:
            return "三等奖"
        if front_hits == 4 and back_hits == 2:
            return "四等奖"
        if front_hits == 4 and back_hits == 1:
            return "五等奖"
        if front_hits == 3 and back_hits == 2:
            return "六等奖"
        if front_hits == 4 and back_hits == 0:
            return "七等奖"
        if (front_hits == 3 and back_hits == 1) or (front_hits == 2 and back_hits == 2):
            return "八等奖"
        if (
            (front_hits == 3 and back_hits == 0)
            or (front_hits == 2 and back_hits == 1)
            or (front_hits == 1 and back_hits == 2)
            or (front_hits == 0 and back_hits == 2)
        ):
            return "九等奖"
        return "未中奖"

    def payout(self, draw_numbers: DltPick, pick_numbers: DltPick) -> int:
        return self.prize_amounts[self.prize_level(draw_numbers, pick_numbers)]
