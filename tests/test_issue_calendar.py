from datetime import date

import pytest

from lottery_sim.issue_calendar import next_issue_from_latest_draw, is_scheduled_draw_date


@pytest.mark.parametrize('game,issue,last,target,expected', [('ssq','2026018','2026-02-12','2026-02-24','2026019'),('dlt','26018','2026-02-11','2026-02-25','26019'),('pl5','25026','2025-01-26','2025-02-06','25027'),('3d','2025273','2025-09-30','2025-10-05','2025274'),('ssq','26001','2026-01-01','2026-01-04','26002'),('qxc','25150','2025-12-30','2026-01-02','26001'),('dlt','2025150','2025-12-31','2026-01-03','2026001')])
def test_issue_calendar_skips_official_holidays_and_preserves_format(game,issue,last,target,expected):
    result = next_issue_from_latest_draw(game,issue,last)
    assert (result.issue,str(result.draw_date)) == (expected,target)


def test_holiday_draw_is_not_scheduled():
    assert not is_scheduled_draw_date('ssq',date(2026,10,4))


def test_unknown_year_calendar_is_explicitly_estimated():
    result = next_issue_from_latest_draw('ssq','2027001','2027-01-03')
    assert result.basis == 'estimated'


@pytest.mark.parametrize('issue,draw_date', [('garbage','2026-01-01'),('2026000','2026-01-01'),('2025001','2026-01-01'),('2026001','bad'),('2026001','2026-02-30')])
def test_invalid_issue_or_date_fails(issue,draw_date):
    with pytest.raises(ValueError):
        next_issue_from_latest_draw('ssq',issue,draw_date)
