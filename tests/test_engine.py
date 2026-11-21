"""汇芯智能体中台 · 执行引擎回归测试（不调用真实模型）。

运行：python3 -m unittest discover -s tests -v
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
import server  # noqa: E402

FAKE = [sys.executable, str(ROOT / 'tests' / 'fake_acp.py')]
PROVIDER = 'Registry_workbuddy'
MODEL = 'hy4flash-free'


def wait_state(hub, task_id, states, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = hub.get(task_id)
        if t['state'] in states:
            return t
        time.sleep(0.1)
    raise AssertionError(f'等待状态 {states} 超时，当前 {hub.get(task_id)["state"]}')


class EngineTest(unittest.TestCase):
    def setUp(self):
        self._orig = server.find_provider_bin
        server.find_provider_bin = lambda p: list(FAKE)
        self.tmp = tempfile.TemporaryDirectory()
        self.hub = server.Hub(self.tmp.name)
        for _ in range(50):
            if self.hub.ready_error is not None:
                break
            time.sleep(0.05)
        self.assertEqual(self.hub.ready_error, '')

    def tearDown(self):
        server.find_provider_bin = self._orig
        self.tmp.cleanup()

    def create(self, prompt):
        return self.hub.create({'title': 't', 'category': '内容生产', 'provider': PROVIDER, 'model': MODEL, 'prompt': prompt})

    def test_new_task_completes(self):
        t = wait_state(self.hub, self.create('你好')['id'], ('completed', 'failed'))
        self.assertEqual(t['state'], 'completed', t['error'])
        self.assertEqual(t['messages'][-1], {'role': 'assistant', 'text': '新回复'})

    def test_followup_does_not_include_replayed_history(self):
        tid = self.create('你好')['id']
        wait_state(self.hub, tid, ('completed',))
        self.hub.followup(tid, '继续')
        t = wait_state(self.hub, tid, ('completed', 'failed'))
        self.assertEqual(t['state'], 'completed', t['error'])
        self.assertEqual(len(t['messages']), 4)
        self.assertEqual(t['messages'][-1]['text'], '新回复')  # 不能是“旧回复新回复”

    def test_permission_is_asked_and_allowed(self):
        tid = self.create('需要审批')['id']
        t = wait_state(self.hub, tid, ('needs_input',))
        self.assertEqual(t['permission']['title'], '删除文件 a.txt')
        self.assertEqual([o['id'] for o in t['permission']['options']], ['allow', 'reject'])
        with self.assertRaises(ValueError):
            self.hub.answer_permission(tid, 'not-an-option')
        self.hub.answer_permission(tid, 'allow')
        t = wait_state(self.hub, tid, ('completed', 'failed'))
        self.assertEqual(t['messages'][-1]['text'], '审批结果=allow')
        self.assertIsNone(t['permission'])

    def test_permission_cancel(self):
        tid = self.create('需要审批')['id']
        wait_state(self.hub, tid, ('needs_input',))
        self.hub.answer_permission(tid, None)
        t = wait_state(self.hub, tid, ('completed', 'failed'))
        self.assertEqual(t['messages'][-1]['text'], '审批结果=cancelled')

    def test_followup_blocked_while_running(self):
        tid = self.create('慢任务')['id']
        wait_state(self.hub, tid, ('running',))
        with self.assertRaises(ValueError):
            self.hub.followup(tid, '插队')
        self.hub.stop_task(tid)

    def test_stop_kills_process(self):
        tid = self.create('慢任务')['id']
        wait_state(self.hub, tid, ('running',))
        with self.hub.lock:
            proc = self.hub.active_procs[tid]
        self.hub.stop_task(tid)
        time.sleep(0.5)
        self.assertIsNotNone(proc.poll(), '进程未被结束')
        self.assertEqual(self.hub.get(tid)['state'], 'stopped')

    def test_stop_while_waiting_permission(self):
        tid = self.create('需要审批')['id']
        wait_state(self.hub, tid, ('needs_input',))
        self.hub.stop_task(tid)
        t = wait_state(self.hub, tid, ('stopped',))
        time.sleep(0.5)
        self.assertEqual(self.hub.get(tid)['state'], 'stopped')
        self.assertIsNone(t['permission'])

    def test_legacy_t3_session_falls_back_with_history(self):
        tid = self.create('你好')['id']
        wait_state(self.hub, tid, ('completed',))
        self.hub.update(tid, thread_id='mcp:a1fee1ee-old')
        self.hub.followup(tid, '继续')
        t = wait_state(self.hub, tid, ('completed', 'failed'))
        self.assertEqual(t['messages'][-1]['text'], '收到历史')
        self.assertEqual(t['thread_id'], 'sess-fake-1')

    def test_engine_log_written_and_hidden(self):
        tid = self.create('你好')['id']
        wait_state(self.hub, tid, ('completed',))
        log = Path(self.tmp.name) / 'workspace' / 'tasks' / tid / '.engine.log'
        self.assertTrue(log.exists())
        self.assertNotIn('.engine.log', [a['name'] for a in self.hub.get(tid)['artifacts']])

    def test_scrub_hides_keys(self):
        self.assertNotIn('ck_abcdefghijklmnopqrstu', server.scrub('key=ck_abcdefghijklmnopqrstu'))


if __name__ == '__main__':
    unittest.main()
