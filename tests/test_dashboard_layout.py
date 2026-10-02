import tempfile
import unittest
from pathlib import Path
from html.parser import HTMLParser
from lottery_sim.dashboard import load_dashboard_model, render_dashboard_html

class Elements(HTMLParser):
    def __init__(self):super().__init__();self.elements=[]
    def handle_starttag(self,tag,attrs):self.elements.append((tag,dict(attrs)))

class DashboardLayoutTests(unittest.TestCase):
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
