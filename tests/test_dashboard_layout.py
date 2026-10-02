import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser
from lottery_sim.dashboard import load_dashboard_model, render_dashboard_html

class Elements(HTMLParser):
    def __init__(self):super().__init__();self.elements=[]
    def handle_starttag(self,tag,attrs):self.elements.append((tag,dict(attrs)))

class DashboardLayoutTests(unittest.TestCase):
    def test_plain_text_summary_is_preserved(self):
        from lottery_sim.dashboard_layout import _summary_markup
        with tempfile.TemporaryDirectory() as tmp:
            game=load_dashboard_model(Path(tmp)/'reports/latest').games[0]
        page=_summary_markup(game,game.name+' 长期统计\n记录数：12\n已校验：10')
        self.assertIn('记录数：12',page)
        self.assertIn('已校验：10',page)
        self.assertNotIn('暂无该彩种长期统计',page)

    def test_all_controls_survive_visible_workspace_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            page=render_dashboard_html(load_dashboard_model(Path(tmp)/'reports/latest'))
        parser=Elements();parser.feed(page)
        attrs=[attr for tag,attr in parser.elements]
        self.assertEqual({attr['data-workspace-page'] for attr in attrs if 'data-workspace-page' in attr},{'overview','generate','analysis','history','reports','settings'})
        self.assertFalse(any(tag=='details' for tag,attr in parser.elements))
        ids=[attr['id'] for attr in attrs if 'id' in attr]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(sum('data-action' in attr for attr in attrs),24)
        self.assertEqual(sum(attr.get('name')=='count' for attr in attrs),8)
        self.assertEqual(sum(attr.get('name')=='llm_api_key' for attr in attrs),1)
        self.assertIn('refresh-dashboard-data',ids)
        self.assertIn('workspace-game',ids)

    def test_report_and_history_readers_do_not_stack_long_sections(self):
        from dataclasses import replace
        from lottery_sim.dashboard_layout import render_workspace
        with tempfile.TemporaryDirectory() as tmp:
            model=load_dashboard_model(Path(tmp)/'reports/latest')
            game=replace(model.games[0],reports={'回测':'报告一','策略对比':'报告二'})
            model=replace(model,games=(game,))
            page=render_workspace(model)
        self.assertIn('data-report-tab',page)
        self.assertIn('data-report-panel',page)
        self.assertIn('data-batch-picker',page)
        self.assertIn('data-param-tab',page)
        self.assertIn('data-param-panel',page)
        self.assertLess(page.index('data-action="generate"'),page.index('name="count"'))
