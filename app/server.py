#!/usr/bin/env python3
"""Local, single-company workspace backed directly by native CLI/ACP engines. No T3 dependency."""
import argparse
import concurrent.futures
import contextlib
import datetime as dt
import http.cookies
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent
VERSION = '0.5.1'
CATEGORIES = ['内容生产', '企业商单', '课程交付', '技能开发', '经营管理', '系统维护']
DEFAULT_PROVIDERS = {
    'codex': {
        'name': 'Codex',
        'models': [
            'gpt-6.2-sol', 'gpt-6.2-astra', 'gpt-6.1-terra', 'gpt-6.1-sol',
            'gpt-6-astra', 'gpt-6-sol', 'gpt-6-luna',
            'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna',
        ],
        'labels': {
            'gpt-6.2-sol': 'GPT-6.2 Sol', 'gpt-6.2-astra': 'GPT-6.2 Astra',
            'gpt-6.1-terra': 'GPT-6.1 Terra', 'gpt-6.1-sol': 'GPT-6.1 Sol',
            'gpt-6-astra': 'GPT-6 Astra', 'gpt-6-sol': 'GPT-6 Sol', 'gpt-6-luna': 'GPT-6 Luna',
            'gpt-5.6-sol': 'GPT-5.6 Sol', 'gpt-5.6-terra': 'GPT-5.6 Terra', 'gpt-5.6-luna': 'GPT-5.6 Luna',
        },
        'efforts': {
            'gpt-6.2-sol': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6.2-astra': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6.1-terra': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6.1-sol': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6-astra': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6-sol': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-6-luna': ['low', 'medium', 'high', 'xhigh', 'max'],
            'gpt-5.6-sol': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-5.6-terra': ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
            'gpt-5.6-luna': ['low', 'medium', 'high', 'xhigh', 'max'],
        },
    },
    'acpRegistry_antigravity_local': {
        'name': 'Antigravity',
        'models': [
            'gemini-4-neon-high', 'gemini-4-neon-xhigh', 'gemini-4-neon-medium', 'gemini-4-neon-low',
            'gemini-4-carbon-medium', 'gemini-4-carbon-high', 'gemini-4-carbon-low',
            'gemini-4-argon-medium', 'gemini-4-argon-high', 'gemini-4-argon-low',
            'gemini-4-hydrogen-high', 'gemini-4-hydrogen-xhigh', 'gemini-4-hydrogen-medium', 'gemini-4-hydrogen-low',
            'gemini-pro-orchestrator-neon', 'gemini-pro-orchestrator', 'gemini-pro-orchestrator-argon',
            'gemini-3.8-flash-high', 'gemini-3.8-flash-medium', 'gemini-3.8-flash-low',
            'claude-opus-5-5-low', 'claude-opus-5-5-medium', 'claude-opus-5-5-high',
            'claude-sonnet-5-5-low', 'claude-sonnet-5-5-medium', 'claude-sonnet-5-5-high',
            'gpt-oss-120b-medium',
        ],
        'labels': {
            'gemini-4-neon-high': 'Gemini 4 Neon (High)', 'gemini-4-neon-xhigh': 'Gemini 4 Neon (XHigh)',
            'gemini-4-neon-medium': 'Gemini 4 Neon (Medium)', 'gemini-4-neon-low': 'Gemini 4 Neon (Low)',
            'gemini-4-carbon-medium': 'Gemini 4 Carbon (Medium)', 'gemini-4-carbon-high': 'Gemini 4 Carbon (High)', 'gemini-4-carbon-low': 'Gemini 4 Carbon (Low)',
            'gemini-4-argon-medium': 'Gemini 4 Argon (Medium)', 'gemini-4-argon-high': 'Gemini 4 Argon (High)', 'gemini-4-argon-low': 'Gemini 4 Argon (Low)',
            'gemini-4-hydrogen-high': 'Gemini 4 Hydrogen (High)', 'gemini-4-hydrogen-xhigh': 'Gemini 4 Hydrogen (XHigh)',
            'gemini-4-hydrogen-medium': 'Gemini 4 Hydrogen (Medium)', 'gemini-4-hydrogen-low': 'Gemini 4 Hydrogen (Low)',
            'gemini-pro-orchestrator-neon': 'Orchestrator (Neon)', 'gemini-pro-orchestrator': 'Orchestrator (Carbon)', 'gemini-pro-orchestrator-argon': 'Orchestrator (Argon)',
            'gemini-3.8-flash-high': 'Gemini 3.8 Flash (High)', 'gemini-3.8-flash-medium': 'Gemini 3.8 Flash (Medium)', 'gemini-3.8-flash-low': 'Gemini 3.8 Flash (Low)',
            'claude-opus-5-5-low': 'Claude Opus 5.5 (Low)', 'claude-opus-5-5-medium': 'Claude Opus 5.5 (Medium)', 'claude-opus-5-5-high': 'Claude Opus 5.5 (High)',
            'claude-sonnet-5-5-low': 'Claude Sonnet 5.5 (Low)', 'claude-sonnet-5-5-medium': 'Claude Sonnet 5.5 (Medium)', 'claude-sonnet-5-5-high': 'Claude Sonnet 5.5 (High)',
            'gpt-oss-120b-medium': 'GPT-OSS 120B (Medium)',
        },
    },
    'Registry_workbuddy': {
        'name': 'WorkBuddy',
        'models': [
            'auto', 'hy4std', 'hy4flash-free', 'hy4flash',
            'deepseek-v4.1-flash', 'glm-5.3', 'glm-5.3-flash', 'glm-5.3-flashx', 'glm-5.2',
            'space-bunny', 'minimax-m3.1-flash', 'minimax-m3-pay',
            'kimi-k3.1-pro-highspeed', 'kimi-k3.1-pro', 'kimi-k3-2', 'kimi-k2.8-preview',
            'deepseek-v4-pro', 'step-5-preview', 'mimo-v2.6-pro',
            'custom-local:MiniMax-M2.5', 'custom-local:deepseek-v4-pro', 'custom-local:deepseek-v4-flash',
            'custom-local:kimi-k3', 'custom-local:kimi-k2.6',
        ],
        'labels': {
            'auto': 'Auto', 'hy4std': 'Hy4 (x0.29)', 'hy4flash-free': 'Hy4 flash (免费)', 'hy4flash': 'Hy4 flash (x0.03)',
            'deepseek-v4.1-flash': 'DeepSeek-V4.1-Flash (x0.11)', 'glm-5.3': 'GLM-5.3 (x0.69)',
            'glm-5.3-flash': 'GLM-5.3-Flash (x0.08)', 'glm-5.3-flashx': 'GLM-5.3-FlashX (x0.19)', 'glm-5.2': 'GLM-5.2 (x0.79)',
            'space-bunny': 'Space-Bunny (x0.08)', 'minimax-m3.1-flash': 'MiniMax-M3.1-Flash (x0.08)', 'minimax-m3-pay': 'MiniMax-M3 (x0.25)',
            'kimi-k3.1-pro-highspeed': 'Kimi-K3.1-Pro-Highspeed (x1.56)', 'kimi-k3.1-pro': 'Kimi-K3.1-Pro (x0.97)',
            'kimi-k3-2': 'Kimi-K3 (x1.62)', 'kimi-k2.8-preview': 'Kimi-K2.8-Preview (x0.77)',
            'deepseek-v4-pro': 'DeepSeek-V4-Pro (x0.51)', 'step-5-preview': 'Step-5-Preview (x0.33)', 'mimo-v2.6-pro': 'Xiaomi MiMo-V2.6-Pro (x0.13)',
            'custom-local:MiniMax-M2.5': 'MiniMax-M2.5 (本地)', 'custom-local:deepseek-v4-pro': 'DeepSeek-V4 Pro (本地)',
            'custom-local:deepseek-v4-flash': 'DeepSeek-V4 Flash (本地)', 'custom-local:kimi-k3': 'kimi-k3 (本地)', 'custom-local:kimi-k2.6': 'Kimi K2.6 (本地)',
        },
        'efforts': {
            'auto': ['low', 'medium', 'high', 'xhigh'],
            'hy4std': ['high'], 'hy4flash-free': ['high'], 'hy4flash': ['high'],
            'deepseek-v4.1-flash': ['low', 'high', 'max'],
            'glm-5.3': ['low', 'high', 'max'], 'glm-5.3-flash': ['low', 'high', 'max'], 'glm-5.3-flashx': ['low', 'high', 'max'],
            'glm-5.2': ['high', 'xhigh'],
            'space-bunny': ['low', 'medium', 'high', 'xhigh', 'max'],
            'minimax-m3.1-flash': ['low', 'medium', 'high', 'xhigh', 'max'],
            'minimax-m3-pay': ['low', 'medium', 'high', 'xhigh'],
            'kimi-k3.1-pro-highspeed': ['low', 'high', 'max'], 'kimi-k3.1-pro': ['low', 'high', 'max'],
            'kimi-k3-2': ['low', 'high', 'max'], 'kimi-k2.8-preview': ['low', 'high', 'max'],
            'deepseek-v4-pro': ['high', 'xhigh'],
            'step-5-preview': ['low', 'medium', 'high'],
            'mimo-v2.6-pro': ['low', 'medium', 'high', 'xhigh'],
            'custom-local:MiniMax-M2.5': ['low', 'medium', 'high', 'xhigh'],
            'custom-local:deepseek-v4-pro': ['high', 'max'], 'custom-local:deepseek-v4-flash': ['high', 'max'],
            'custom-local:kimi-k3': ['medium'], 'custom-local:kimi-k2.6': ['low', 'medium', 'high'],
        },
    },
    'Registry_grokbot': {
        'name': 'Grok Bot',
        'models': ['default'],
        'labels': {'default': 'Grok Bot（默认队友）'},
        'efforts': {},
    },
}
IGNORED_DIRS = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next'}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def scrub(value):
    return re.sub(r'\b(?:ck_|sk-)[A-Za-z0-9_-]{15,}', '[凭证已隐藏]', str(value))

def probe_acp_models(cmd, timeout=8):
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        p.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':1,'clientCapabilities':{},'clientInfo':{'name':'huixin-hub','version':VERSION}}})+'\n')
        p.stdin.flush()
        time.sleep(0.35)
        p.stdin.write(json.dumps({'jsonrpc':'2.0','id':2,'method':'session/new','params':{'cwd':'/tmp','mcpServers':[]}})+'\n')
        p.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = p.stdout.readline()
            if not line:
                break
            try:
                obj = json.loads(line)
                if obj.get('id') == 2 and 'result' in obj:
                    return obj['result'].get('models', {}).get('availableModels', [])
            except Exception:
                pass
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            p.terminate()
    return []

def load_providers(data_dir):
    cfg = Path(data_dir) / 'providers.json'
    if not cfg.exists():
        cfg.write_text(json.dumps(DEFAULT_PROVIDERS, ensure_ascii=False, indent=2) + '\n')
        return DEFAULT_PROVIDERS
    try:
        loaded = json.loads(cfg.read_text())
        if isinstance(loaded, dict) and loaded:
            return loaded
    except Exception:
        pass
    return DEFAULT_PROVIDERS

def find_provider_bin(provider):
    if provider == 'codex':
        for candidate in [shutil.which('codex'), '/opt/homebrew/bin/codex', '/usr/local/bin/codex', str(Path.home() / '.local/bin/codex')]:
            if candidate and Path(candidate).is_file():
                return [candidate]
        return None
    if provider == 'acpRegistry_antigravity_local':
        for candidate in [str(Path.home() / '.local/bin/agy'), shutil.which('agy'), '/opt/homebrew/bin/agy']:
            if candidate and Path(candidate).is_file():
                return [candidate, 'acp']
        return None
    if provider == 'Registry_workbuddy':
        for candidate in [ROOT / 'bin/workbuddy-acp', ROOT.parent / 'bin/workbuddy-acp']:
            if candidate.is_file():
                return [str(candidate)]
        return None
    if provider == 'Registry_grokbot':
        for candidate in [ROOT / 'bin/grokbot-acp', ROOT.parent / 'bin/grokbot-acp']:
            if candidate.is_file():
                return [str(candidate)]
        return None
    return None

class Hub:
    def __init__(self, data_dir):
        self.data = Path(data_dir).expanduser().resolve()
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.workspace = self.data / 'workspace'
        self.workspace.mkdir(exist_ok=True)
        self.db_path = self.data / 'hub.sqlite'
        self.providers = load_providers(self.data)
        self.launch_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.refresh_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.lock = threading.Lock()
        self.active_procs = {}
        self.stopped_tasks = set()
        self.permissions = {}
        self.ready_error = None
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT, category TEXT, provider TEXT, model TEXT, prompt TEXT, thread_id TEXT, state TEXT, error TEXT, snapshot TEXT, created_at TEXT, updated_at TEXT, archived INTEGER DEFAULT 0, effort TEXT DEFAULT "")')
            cols = {r['name'] for r in db.execute('PRAGMA table_info(tasks)').fetchall()}
            if 'archived' not in cols:
                db.execute('ALTER TABLE tasks ADD COLUMN archived INTEGER DEFAULT 0')
            if 'effort' not in cols:
                db.execute('ALTER TABLE tasks ADD COLUMN effort TEXT DEFAULT ""')
            db.execute("UPDATE tasks SET state='failed',error='上次执行因应用退出而中断，可点击“重新发起”继续。' WHERE state IN ('queued','submitting','starting','running','working','needs_input')")
        self.launch_pool.submit(self.initialize)

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        try:
            rules = self.workspace / 'AGENTS.md'
            if not rules.exists():
                rules.write_text('# 业务工作区\n默认用简体中文。读取需求后完成真实产物。仅在任务指定目录写入交付物。不得编造数据、调用结果或验收结论。对外发布、删除、远程修改须获得明确授权。不得读取或输出任何账号密钥。\n')
            available = [p for p in self.providers if find_provider_bin(p)]
            if not available:
                self.ready_error = '未检测到可用的本机执行引擎（Codex / Antigravity / WorkBuddy）'
                return
            self.ready_error = ''
        except Exception as e:
            self.ready_error = scrub(e)

    def _permission_view(self, task_id):
        with self.lock:
            req = self.permissions.get(task_id)
        if not req:
            return None
        return {'title': req['title'], 'detail': req['detail'], 'options': req['options']}

    def get(self, task_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=? AND COALESCE(archived,0)=0',(task_id,)).fetchone()
        if not row:
            raise ValueError('任务不存在')
        task = dict(row)
        snapshot = json.loads(task.pop('snapshot') or '{}')
        task['messages'] = snapshot.get('messages', [])
        task['permission'] = self._permission_view(task_id)
        task['pending'] = 1 if task['permission'] else 0
        task['artifacts'] = self.artifacts(task_id)
        return task

    def tasks(self):
        with self.db() as db:
            rows = db.execute('SELECT id,title,category,provider,model,COALESCE(effort,"") AS effort,prompt,thread_id,state,error,snapshot,created_at,updated_at FROM tasks WHERE COALESCE(archived,0)=0 ORDER BY created_at DESC LIMIT 200').fetchall()
        out = []
        for row in rows:
            t = dict(row)
            t.pop('snapshot', None)
            t['pending'] = 1 if self._permission_view(t['id']) else 0
            out.append(t)
        return out

    def create(self, body):
        if self.ready_error is None:
            raise ValueError('本机执行引擎正在初始化，请稍后再试')
        if self.ready_error:
            self.launch_pool.submit(self.initialize)
            raise ValueError(self.ready_error)
        provider, model = body.get('provider'), body.get('model')
        if provider not in self.providers or model not in self.providers[provider]['models']:
            raise ValueError('请选择已配置的工具和模型')
        effort = str(body.get('effort', '') or '').strip()
        allowed_efforts = self.providers[provider].get('efforts', {}).get(model, [])
        if effort and effort not in allowed_efforts:
            raise ValueError('所选思考档位不支持该模型')
        prompt = str(body.get('prompt','')).strip()
        if not prompt or len(prompt)>30000:
            raise ValueError('请输入需求，最多 30,000 字')
        title = str(body.get('title','')).strip() or prompt.splitlines()[0][:36]
        category = body.get('category','内容生产')
        if category not in CATEGORIES or len(title)>100:
            raise ValueError('任务分类或标题不正确')
        task_id = secrets.token_hex(8)
        folder = self.workspace/'tasks'/task_id
        folder.mkdir(parents=True)
        (folder/'需求.md').write_text('# '+title+'\n\n'+prompt+'\n')
        init_snap = json.dumps({'messages': [{'role': 'user', 'text': prompt}]}, ensure_ascii=False)
        with self.db() as db:
            db.execute('INSERT INTO tasks (id,title,category,provider,model,effort,prompt,thread_id,state,error,snapshot,created_at,updated_at,archived) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)',
                       (task_id,title,category,provider,model,effort,prompt,None,'queued',None,init_snap,now(),now()))
        self.launch_pool.submit(self.launch,task_id)
        return self.get(task_id)

    def update(self,task_id,**fields):
        fields['updated_at']=now()
        with self.db() as db:
            db.execute('UPDATE tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[task_id])

    def _save_messages(self, task_id, messages, state=None, thread_id=None, error=None):
        fields = {'snapshot': json.dumps({'messages': messages}, ensure_ascii=False)}
        if state is not None:
            fields['state'] = state
        if thread_id is not None:
            fields['thread_id'] = thread_id
        if error is not None or state == 'completed':
            fields['error'] = error
        self.update(task_id, **fields)

    # ------------------------------------------------------------------
    # 执行引擎：Codex（codex exec --json）与 ACP（agy / WorkBuddy）
    # ------------------------------------------------------------------
    RUNNING_STATES = ('queued', 'submitting', 'starting', 'running', 'working', 'needs_input')
    PERMISSION_TIMEOUT = 30 * 60

    def _engine_log(self, task_id):
        folder = self.workspace / 'tasks' / task_id
        folder.mkdir(parents=True, exist_ok=True)
        return open(folder / '.engine.log', 'a', encoding='utf-8')

    def _spawn(self, task_id, args, log):
        # 独立进程组：停止时整组结束，避免子进程残留
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True,
                                cwd=str(self.workspace), start_new_session=True)
        with self.lock:
            self.active_procs[task_id] = proc
        return proc

    @staticmethod
    def _kill(proc):
        if not proc:
            return
        if proc.poll() is not None:
            for pipe in (proc.stdin, proc.stdout):
                with contextlib.suppress(Exception):
                    pipe.close()
            return
        with contextlib.suppress(Exception):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except Exception:
            with contextlib.suppress(Exception):
                os.killpg(proc.pid, signal.SIGKILL)
        for pipe in (proc.stdin, proc.stdout):
            with contextlib.suppress(Exception):
                pipe.close()

    def _was_stopped(self, task_id):
        with self.lock:
            return task_id in self.stopped_tasks

    @staticmethod
    def _is_legacy_session(session_id):
        # 0.3.0 及更早由 T3 创建的会话编号（如 mcp:xxxx），新引擎无法续接
        return bool(session_id) and ':' in str(session_id)

    @staticmethod
    def _history_prompt(messages, new_text):
        lines = ['以下是本任务此前的对话记录（原会话已无法续接，请据此继续）：']
        for m in messages[:-1][-12:]:
            who = '用户' if m.get('role') == 'user' else '智能体'
            lines.append(f"【{who}】{str(m.get('text', ''))[:4000]}")
        lines.append('【本次新需求】' + new_text)
        return '\n\n'.join(lines)

    def _finish(self, task_id, messages, reply, ok, sid, err):
        final = list(messages)
        if reply:
            final.append({'role': 'assistant', 'text': reply})
        if self._was_stopped(task_id):
            self._save_messages(task_id, final, state='stopped', thread_id=sid, error=None)
        elif ok:
            self._save_messages(task_id, final, state='completed', thread_id=sid, error=None)
        else:
            self._save_messages(task_id, final, state='failed', thread_id=sid, error=scrub(err or '执行失败'))

    def _execute(self, task_id, task, prompt_text, messages, session_id=None):
        cmd = find_provider_bin(task['provider'])
        if not cmd:
            self.update(task_id, state='failed', error=f"未找到本机 {self.providers.get(task['provider'], {}).get('name', task['provider'])} 可执行程序")
            return
        with self.lock:
            self.stopped_tasks.discard(task_id)
        if self._is_legacy_session(session_id) or (not session_id and len(messages) > 1):
            prompt_text = self._history_prompt(messages, prompt_text)
            session_id = None
        log = self._engine_log(task_id)
        log.write(f"\n===== {now()} {task['provider']} / {task['model']} session={session_id or 'new'} =====\n")
        log.flush()
        try:
            if task['provider'] == 'codex':
                self._run_codex(task_id, cmd, task, prompt_text, messages, session_id, log)
            else:
                self._run_acp(task_id, cmd, task, prompt_text, messages, session_id, log)
        except Exception as e:
            log.write(f'[huixin] 异常：{scrub(e)}\n')
            self._finish(task_id, messages, None, False, None, e)
        finally:
            with self.lock:
                proc = self.active_procs.pop(task_id, None)
                self.permissions.pop(task_id, None)
            self._kill(proc)
            with contextlib.suppress(Exception):
                log.close()

    def _run_codex(self, task_id, base_cmd, task, prompt_text, messages, session_id, log):
        args = list(base_cmd) + ['exec']
        if session_id:
            args += ['resume']
        args += ['--json', '--skip-git-repo-check', '-m', task['model']]
        if not session_id:
            # 工作区可写沙箱：越界命令会失败而不是被自动放行
            args += ['-s', 'workspace-write', '-C', str(self.workspace)]
        if task.get('effort'):
            args += ['-c', f"model_reasoning_effort={task['effort']}"]
        args += ([session_id, '-'] if session_id else ['-'])
        proc = self._spawn(task_id, args, log)
        proc.stdin.write(prompt_text)
        proc.stdin.close()
        self.update(task_id, state='running', error=None)
        parts, last_err, sid = [], None, session_id
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                log.write(line + '\n')
                continue
            etype = ev.get('type')
            if etype == 'thread.started' and ev.get('thread_id'):
                sid = ev['thread_id']
                self.update(task_id, thread_id=sid)
            elif etype == 'item.completed':
                item = ev.get('item') or {}
                if item.get('type') == 'agent_message' and item.get('text'):
                    parts.append(item['text'])
                    self._save_messages(task_id, list(messages) + [{'role': 'assistant', 'text': '\n\n'.join(parts)}], thread_id=sid)
                elif item.get('type') == 'error' and item.get('message'):
                    log.write('[codex] ' + item['message'] + '\n')
            elif etype == 'turn.failed':
                last_err = (ev.get('error') or {}).get('message') or '执行失败'
            elif etype == 'error' and ev.get('message'):
                last_err = ev['message']
        rc = proc.wait()
        if last_err:
            log.write('[codex] 失败：' + last_err + '\n')
        self._finish(task_id, messages, '\n\n'.join(parts), rc == 0 and not last_err, sid, last_err or f'Codex 退出码 {rc}')

    def _ask_permission(self, task_id, params):
        """把智能体的审批请求交给用户，阻塞等待选择；超时或停止时取消。"""
        tool = params.get('toolCall') or {}
        options = [{'id': o.get('optionId'), 'name': o.get('name') or o.get('optionId'), 'kind': o.get('kind', '')}
                   for o in (params.get('options') or []) if o.get('optionId')]
        detail = tool.get('rawInput')
        req = {'title': tool.get('title') or tool.get('kind') or '智能体请求执行操作',
               'detail': json.dumps(detail, ensure_ascii=False)[:1500] if detail else '',
               'options': options, 'event': threading.Event(), 'choice': None}
        with self.lock:
            self.permissions[task_id] = req
        self.update(task_id, state='needs_input')
        req['event'].wait(self.PERMISSION_TIMEOUT)
        with self.lock:
            self.permissions.pop(task_id, None)
        if not self._was_stopped(task_id):
            self.update(task_id, state='running')
        return req['choice']

    def answer_permission(self, task_id, option_id):
        self.get(task_id)
        with self.lock:
            req = self.permissions.get(task_id)
        if not req:
            raise ValueError('该任务当前没有待审批的操作')
        if option_id is not None and option_id not in {o['id'] for o in req['options']}:
            raise ValueError('无效的审批选项')
        req['choice'] = option_id
        req['event'].set()
        return self.get(task_id)

    def _run_acp(self, task_id, base_cmd, task, prompt_text, messages, session_id, log):
        proc = self._spawn(task_id, list(base_cmd), log)
        seq = 0
        chunks = []
        collect = {'on': False}
        last_flush = [time.monotonic()]

        def write(obj):
            proc.stdin.write(json.dumps(obj, ensure_ascii=False) + '\n')
            proc.stdin.flush()

        def send(method, params):
            nonlocal seq
            seq += 1
            write({'jsonrpc': '2.0', 'id': seq, 'method': method, 'params': params})
            return seq

        def wait(target):
            while True:
                line = proc.stdout.readline()
                if not line:
                    return None
                try:
                    obj = json.loads(line)
                except ValueError:
                    log.write(line)
                    continue
                if obj.get('id') == target and ('result' in obj or 'error' in obj) and 'method' not in obj:
                    return obj
                method = obj.get('method')
                if method == 'session/request_permission' and 'id' in obj:
                    params = obj.get('params') or {}
                    log.write('[huixin] 审批请求：' + json.dumps(params.get('toolCall') or {}, ensure_ascii=False)[:500] + '\n')
                    choice = self._ask_permission(task_id, params)
                    log.write(f'[huixin] 审批结果：{choice or "取消"}\n')
                    outcome = {'outcome': 'selected', 'optionId': choice} if choice else {'outcome': 'cancelled'}
                    write({'jsonrpc': '2.0', 'id': obj['id'], 'result': {'outcome': outcome}})
                elif 'id' in obj and method:
                    # 未支持的客户端能力（读写文件、终端等）明确拒绝，避免引擎卡死
                    write({'jsonrpc': '2.0', 'id': obj['id'], 'error': {'code': -32601, 'message': 'Method not supported by client'}})
                elif method == 'session/update' and collect['on']:
                    upd = (obj.get('params') or {}).get('update') or {}
                    if upd.get('sessionUpdate') == 'agent_message_chunk':
                        text = (upd.get('content') or {}).get('text')
                        if text:
                            chunks.append(text)
                            if time.monotonic() - last_flush[0] > 0.4:
                                self._save_messages(task_id, list(messages) + [{'role': 'assistant', 'text': ''.join(chunks)}])
                                last_flush[0] = time.monotonic()

        def err_of(res, default):
            return ((res or {}).get('error') or {}).get('message') or default

        init = wait(send('initialize', {'protocolVersion': 1, 'clientCapabilities': {}, 'clientInfo': {'name': 'huixin-hub', 'version': VERSION}}))
        if not init or 'error' in init:
            raise RuntimeError(err_of(init, 'ACP 初始化失败'))
        sess, sid = None, None
        if session_id:
            # session/load 会重放历史消息；此时不收集，避免旧回复拼进新回复
            sess = wait(send('session/load', {'sessionId': session_id, 'cwd': str(self.workspace), 'mcpServers': []}))
            if sess and 'result' in sess:
                sid = session_id
            else:
                log.write('[huixin] 会话续接失败，改为带历史新建：' + err_of(sess, '未知') + '\n')
                prompt_text = self._history_prompt(messages, prompt_text)
        if not sid:
            sess = wait(send('session/new', {'cwd': str(self.workspace), 'mcpServers': []}))
            sid = ((sess or {}).get('result') or {}).get('sessionId')
            if not sid:
                raise RuntimeError(err_of(sess, '创建会话失败'))
        self.update(task_id, thread_id=sid, state='running', error=None)
        # auto：常规编辑与安全命令自动执行，高风险/不可逆操作会发起审批交由用户决定
        wait(send('session/set_mode', {'sessionId': sid, 'modeId': 'auto'}))
        wait(send('session/set_model', {'sessionId': sid, 'modelId': task['model']}))
        if task.get('effort'):
            res = wait(send('session/set_config_option', {'sessionId': sid, 'configId': 'thought_level', 'value': task['effort']}))
            if not res or 'error' in res:
                log.write('[huixin] 思考档位设置失败：' + err_of(res, '未知') + '\n')
        collect['on'] = True
        res = wait(send('session/prompt', {'sessionId': sid, 'prompt': [{'type': 'text', 'text': prompt_text}]}))
        ok = bool(res and 'result' in res)
        self._finish(task_id, messages, ''.join(chunks), ok, sid, err_of(res, '智能体执行未返回结果'))

    def _obsidian_config_path(self):
        return self.data / 'obsidian.json'

    def get_obsidian_config(self):
        p = self._obsidian_config_path()
        cfg = {'enabled': False, 'vault_path': '', 'context_file': '', 'max_chars': 3000}
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    cfg.update({k: raw[k] for k in cfg if k in raw})
            except Exception:
                pass
        ctx_path = self._resolve_obsidian_context_path(cfg)
        cfg['context_exists'] = bool(ctx_path and ctx_path.is_file())
        cfg['resolved_context_path'] = str(ctx_path) if ctx_path else ''
        return cfg

    def save_obsidian_config(self, body):
        if not isinstance(body, dict):
            raise ValueError('配置格式无效')
        vault_path = str(body.get('vault_path') or '').strip()
        context_file = str(body.get('context_file') or '').strip()
        enabled = bool(body.get('enabled', bool(vault_path or context_file)))
        max_chars = int(body.get('max_chars') or 3000)
        max_chars = max(500, min(max_chars, 12000))
        data = {'enabled': enabled, 'vault_path': vault_path, 'context_file': context_file, 'max_chars': max_chars}
        self._obsidian_config_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.get_obsidian_config()

    @staticmethod
    def _resolve_obsidian_context_path(cfg):
        ctx = str(cfg.get('context_file') or '').strip()
        vault = str(cfg.get('vault_path') or '').strip()
        if not ctx and not vault:
            return None
        if ctx:
            cp = Path(ctx).expanduser()
            if cp.is_absolute():
                return cp
            if vault:
                return Path(vault).expanduser() / cp
        return None

    def _obsidian_context_block(self):
        cfg = self.get_obsidian_config()
        if not cfg.get('enabled'):
            return ''
        ctx_path = self._resolve_obsidian_context_path(cfg)
        if not ctx_path or not ctx_path.is_file():
            return ''
        try:
            text = ctx_path.read_text(encoding='utf-8').strip()
        except Exception:
            return ''
        if not text:
            return ''
        limit = int(cfg.get('max_chars') or 3000)
        if len(text) > limit:
            text = text[:limit].rstrip() + '\n...（已截断，完整内容请按需读取原文件）'
        return (
            '\n\n【Obsidian 共享工作记忆】\n'
            f'路径：{ctx_path}\n'
            '说明：以下为跨平台最新活跃上下文，供衔接进度使用；请勿改写原始知识库笔记，完工后如需跨平台接力，仅在该文件「跨平台接力记录」顶部追加 1 行摘要。\n'
            f'{text}'
        )

    def launch(self, task_id):
        task = self.get(task_id)
        self.update(task_id, state='starting')
        prompt = (
            task['prompt']
            + self._obsidian_context_block()
            + '\n\n【工作要求】默认用简体中文。需要生成文件时，请将最终交付物写入 tasks/'
            + task_id
            + '/交付物/。最终回复列明实际生成的文件与检查结果；没有生成文件请如实说明。不要输出任何账号凭证。'
        )
        self._execute(task_id, task, prompt, [{'role': 'user', 'text': task['prompt']}], session_id=None)

    def refresh(self, task_id):
        return self.get(task_id)

    def schedule_refresh(self, task_id, force=False):
        pass

    def stop_task(self, task_id):
        self.get(task_id)
        with self.lock:
            self.stopped_tasks.add(task_id)
            proc = self.active_procs.get(task_id)
            req = self.permissions.get(task_id)
        if req:
            req['choice'] = None
            req['event'].set()
        self._kill(proc)
        self.update(task_id, state='stopped', error=None)
        return self.get(task_id)

    def followup(self, task_id, message, provider=None, model=None, effort=None):
        task = self.get(task_id)
        if task['state'] in self.RUNNING_STATES:
            raise ValueError('当前任务正在执行中，请等待完成或先停止任务')
        message = str(message).strip()
        if not message or len(message) > 30000:
            raise ValueError('请输入后续需求，最多 30,000 字')
        next_provider = str(provider).strip() if provider else task['provider']
        if next_provider not in self.providers:
            raise ValueError('所选执行工具不可用')
        allowed_models = self.providers[next_provider].get('models') or []
        next_model = str(model).strip() if model else (task['model'] if next_provider == task['provider'] else (allowed_models[0] if allowed_models else ''))
        if allowed_models and next_model not in allowed_models:
            raise ValueError('所选模型不可用')
        next_effort = str(effort or '').strip() if (effort is not None or next_provider != task['provider'] or next_model != task['model']) else (task.get('effort') or '')
        session_id = task['thread_id'] if next_provider == task['provider'] else None
        if next_provider != task['provider'] or next_model != task['model'] or next_effort != (task.get('effort') or ''):
            self.update(task_id, provider=next_provider, model=next_model, effort=next_effort, thread_id=session_id)
            task = self.get(task_id)
        messages = list(task.get('messages') or [{'role': 'user', 'text': task['prompt']}])
        messages.append({'role': 'user', 'text': message})
        self._save_messages(task_id, messages, state='starting', error=None)
        self.launch_pool.submit(self._execute, task_id, task, message, messages, session_id)
        return self.get(task_id)

    def archive(self,task_id):
        self.get(task_id)
        self.update(task_id,archived=1)
        return {'ok':True,'id':task_id}

    def retry(self,task_id):
        task=self.get(task_id)
        return self.create({'title':task['title'],'category':task['category'],'provider':task['provider'],'model':task['model'],'effort':task.get('effort',''),'prompt':task['prompt']})

    def open_folder(self,task_id):
        self.get(task_id)
        folder=(self.workspace/'tasks'/task_id).resolve()
        deliverables=folder/'交付物'
        target=deliverables if deliverables.is_dir() else folder
        target.mkdir(parents=True,exist_ok=True)
        subprocess.Popen(['/usr/bin/open',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return {'ok':True,'path':str(target)}

    def sync_providers(self):
        updated = json.loads(json.dumps(self.providers, ensure_ascii=False))
        codex_cache = Path.home() / '.codex/models_cache.json'
        if codex_cache.exists():
            try:
                cm = json.loads(codex_cache.read_text())
                items = [m for m in cm.get('models', []) if m.get('visibility') != 'hide' and m.get('slug')]
                if items:
                    updated.setdefault('codex', {'name': 'Codex'})
                    updated['codex']['models'] = [m['slug'] for m in items]
                    updated['codex']['labels'] = {m['slug']: m.get('display_name') or m['slug'] for m in items}
                    updated['codex']['efforts'] = {m['slug']: [x.get('effort') for x in m.get('supported_reasoning_levels', []) if x.get('effort')] for m in items}
            except Exception:
                pass
        agy_cmd = find_provider_bin('acpRegistry_antigravity_local')
        if agy_cmd:
            agy_models = probe_acp_models(agy_cmd)
            if agy_models:
                updated.setdefault('acpRegistry_antigravity_local', {'name': 'Antigravity'})
                updated['acpRegistry_antigravity_local']['models'] = [m['modelId'] for m in agy_models]
                updated['acpRegistry_antigravity_local']['labels'] = {m['modelId']: m.get('name') or m['modelId'] for m in agy_models}
        wb_cmd = find_provider_bin('Registry_workbuddy')
        if wb_cmd:
            wb_models = probe_acp_models(wb_cmd)
            if wb_models:
                updated.setdefault('Registry_workbuddy', {'name': 'WorkBuddy'})
                updated['Registry_workbuddy']['models'] = [m['modelId'] for m in wb_models]
                labels = {}
                efforts = {}
                for m in wb_models:
                    desc = f" ({m['description']})" if m.get('description') else ''
                    labels[m['modelId']] = f"{m.get('name') or m['modelId']}{desc}"
                    efforts[m['modelId']] = [e['value'] for e in m.get('_meta', {}).get('effortOptions', []) if e.get('value')]
                updated['Registry_workbuddy']['labels'] = labels
                updated['Registry_workbuddy']['efforts'] = efforts
        grok_cmd = find_provider_bin('Registry_grokbot')
        if grok_cmd:
            grok_models = probe_acp_models(grok_cmd)
            if grok_models:
                updated.setdefault('Registry_grokbot', {'name': 'Grok Bot'})
                updated['Registry_grokbot']['models'] = [m['modelId'] for m in grok_models]
                labels = {}
                for m in grok_models:
                    desc = f" ({m['description']})" if m.get('description') else ''
                    labels[m['modelId']] = f"{m.get('name') or m['modelId']}{desc}"
                updated['Registry_grokbot']['labels'] = labels
                updated['Registry_grokbot']['efforts'] = {}
        self.providers = updated
        (self.data / 'providers.json').write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
        return {'ok': True, 'providers': updated}

    def artifact_path(self,task_id,name):
        if not re.fullmatch('[a-f0-9]{16}',task_id):
            raise ValueError('无效任务')
        root=(self.workspace/'tasks'/task_id).resolve()
        p=(root/name).resolve()
        if root not in p.parents or not p.is_file() or p.stat().st_size>200*1024*1024 or any(x.startswith('.') for x in Path(name).parts):
            raise ValueError('文件不存在')
        return p

    def artifacts(self,task_id):
        root=self.workspace/'tasks'/task_id
        if not root.exists():
            return []
        result=[]
        for dirpath,dirnames,filenames in os.walk(root):
            dirnames[:]=[d for d in dirnames if not d.startswith('.') and d not in IGNORED_DIRS]
            for fn in filenames:
                if fn.startswith('.'):
                    continue
                p=Path(dirpath)/fn
                if not p.is_file() or p.is_symlink():
                    continue
                if p.stat().st_size>200*1024*1024:
                    continue
                name=str(p.relative_to(root))
                result.append({'name':name,'size':p.stat().st_size})
                if len(result)>=100:
                    return sorted(result,key=lambda x:(x['name']=='需求.md',x['name']))
        return sorted(result,key=lambda x:(x['name']=='需求.md',x['name']))

def make_handler(hub,port,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}

        def authorized(self):
            cookie=http.cookies.SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie',''))
            except http.cookies.CookieError:
                return False
            return (cookie.get('huixin_session') and secrets.compare_digest(cookie['huixin_session'].value,token)) or secrets.compare_digest(self.headers.get('X-Huixin-Token',''),token)

        def send(self,data,status=200,mime='application/json; charset=utf-8',cookie=False):
            if not isinstance(data,bytes):
                data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            if cookie:
                self.send_header('Set-Cookie',f'huixin_session={token}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.valid_host():
                return self.send({'error':'仅允许本机访问'},403)
            path=unquote(urlparse(self.path).path)
            if path=='/':
                if 'HuixinDesktop/' not in self.headers.get('User-Agent',''):
                    return self.send({'error':'请从“应用程序”打开“汇芯智能体中台”。本产品仅提供桌面入口。'},403)
                page=(ROOT/'web/index.html').read_text().replace('__CSRF_TOKEN__',token)
                return self.send(page.encode(),mime='text/html; charset=utf-8',cookie=True)
            if path=='/api/health':
                return self.send({'ok':True,'version':VERSION,'pid':os.getpid()})
            if path=='/brand.svg':
                return self.send((ROOT/'web/brand.svg').read_bytes(),mime='image/svg+xml')
            if not self.authorized():
                return self.send({'error':'请从本机工作台重新打开'},403)
            try:
                if path=='/api/state':
                    tasks=hub.tasks()
                    for t in tasks:
                        if t['state'] not in ['completed','failed','interrupted','stopped'] and t['thread_id']:
                            hub.schedule_refresh(t['id'])
                    return self.send({'tasks':tasks,'providers':hub.providers,'categories':CATEGORIES,'ready':hub.ready_error=='','error':hub.ready_error,'workspace':str(hub.workspace),'obsidian':hub.get_obsidian_config(),'company':'汇芯','version':VERSION})
                if path=='/api/obsidian':
                    return self.send(hub.get_obsidian_config())
                if path.startswith('/api/tasks/'):
                    task_id=path.split('/')[3]
                    hub.schedule_refresh(task_id)
                    return self.send(hub.get(task_id))
                if path.startswith('/files/'):
                    _,_,task_id,name=path.split('/',3)
                    p=hub.artifact_path(task_id,name)
                    mime=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
                    if mime in ['text/html','image/svg+xml','application/javascript']:
                        mime='text/plain; charset=utf-8'
                    if (mime.startswith('text/') or mime=='application/json') and 'charset=' not in mime:
                        mime+='; charset=utf-8'
                    return self.send(p.read_bytes(),mime=mime)
                return self.send({'error':'页面不存在'},404)
            except (ValueError,IndexError):
                return self.send({'error':'任务或文件不存在'},404)

        def do_POST(self):
            origin=self.headers.get('Origin','')
            if not self.valid_host() or not self.authorized() or origin not in {f'http://127.0.0.1:{port}',f'http://localhost:{port}'} or not secrets.compare_digest(self.headers.get('X-Huixin-Token',''),token):
                return self.send({'error':'请求未获授权'},403)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n<0 or n>131072:
                    raise ValueError('请求过大')
                body=json.loads(self.rfile.read(n)) if n>0 else {}
                path=urlparse(self.path).path
                parts=[p for p in path.split('/') if p]
                if path=='/api/tasks':
                    return self.send(hub.create(body),201)
                if len(parts)==4 and parts[:2]==['api','tasks']:
                    task_id,action=parts[2],parts[3]
                    if action=='message':
                        return self.send(hub.followup(task_id,body.get('message',''),body.get('provider'),body.get('model'),body.get('effort')))
                    if action=='refresh':
                        hub.refresh(task_id)
                        return self.send(hub.get(task_id))
                    if action=='archive':
                        return self.send(hub.archive(task_id))
                    if action=='open-folder':
                        return self.send(hub.open_folder(task_id))
                    if action=='retry':
                        return self.send(hub.retry(task_id),201)
                    if action=='stop':
                        return self.send(hub.stop_task(task_id))
                    if action=='permission':
                        return self.send(hub.answer_permission(task_id,body.get('option')))
                if path=='/api/providers/sync':
                    return self.send(hub.sync_providers())
                if path=='/api/obsidian':
                    return self.send(hub.save_obsidian_config(body))
                return self.send({'error':'接口不存在'},404)
            except (ValueError,RuntimeError,json.JSONDecodeError) as e:
                return self.send({'error':scrub(e)},400)
            except Exception:
                return self.send({'error':'操作未完成，请稍后重试'},500)
    return Handler

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=39261)
    parser.add_argument('--data-dir',default=str(Path.home()/'.local/share/huixin-agent-hub'))
    args=parser.parse_args()
    hub=Hub(args.data_dir)
    token=secrets.token_urlsafe(32)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(hub,args.port,token))
    print(f'汇芯智能体中台 http://127.0.0.1:{args.port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    main()
