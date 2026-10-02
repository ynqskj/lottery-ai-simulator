import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from lottery_sim import llm_service


class LlmServiceTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append((self.path,self.headers.get('Authorization')))
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'data':[{'id':'model-b'},{'id':'model-a'},{'id':'model-b'}]}).encode())
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path,body))
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'message':{'content':'模拟报告总结'}}]},ensure_ascii=False).encode())
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.config={'llm_base_url':f'http://127.0.0.1:{self.server.server_port}/v1/','llm_api_key':'test-secret','llm_model':'manual-model'}

    def test_model_fetch_normalizes_and_deduplicates(self):
        self.assertEqual(llm_service.list_models(self.config),['model-a','model-b'])
        self.assertEqual(self.requests[0],('/v1/models','Bearer test-secret'))

    def test_manual_model_can_be_tested(self):
        result=llm_service.test_model(self.config)
        self.assertIn('成功',result)
        self.assertEqual(self.requests[0][0],'/v1/chat/completions')
        self.assertEqual(self.requests[0][1]['model'],'manual-model')

    def test_summary_saved_and_isolated(self):
        alice=Path(self.temp.name)/'alice.sqlite';bob=Path(self.temp.name)/'bob.sqlite'
        result=llm_service.generate_summary(alice,self.config,{'games':[{'code':'3d','checked':2}]})
        self.assertEqual(result['content'],'模拟报告总结')
        self.assertEqual(llm_service.latest_summary(alice)['content'],result['content'])
        self.assertIsNone(llm_service.latest_summary(bob))
        count=len(self.requests)
        llm_service.latest_summary(alice)
        self.assertEqual(len(self.requests),count)

    def test_invalid_url_and_blank_model(self):
        for override in ({'llm_base_url':'file:///tmp'},{'llm_model':''}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                llm_service.test_model({**self.config,**override})
