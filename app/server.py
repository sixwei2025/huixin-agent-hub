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
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent
VERSION = '0.4.0'
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
        self.ready_error = None
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT, category TEXT, provider TEXT, model TEXT, prompt TEXT, thread_id TEXT, state TEXT, error TEXT, snapshot TEXT, created_at TEXT, updated_at TEXT, archived INTEGER DEFAULT 0, effort TEXT DEFAULT "")')
            cols = {r['name'] for r in db.execute('PRAGMA table_info(tasks)').fetchall()}
            if 'archived' not in cols:
                db.execute('ALTER TABLE tasks ADD COLUMN archived INTEGER DEFAULT 0')
            if 'effort' not in cols:
                db.execute('ALTER TABLE tasks ADD COLUMN effort TEXT DEFAULT ""')
            db.execute("UPDATE tasks SET state='failed',error='上次执行因应用退出而中断，可点击“重新发起”继续。' WHERE state IN ('queued','submitting','starting','running','working')")
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

    def get(self, task_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=? AND COALESCE(archived,0)=0',(task_id,)).fetchone()
        if not row:
            raise ValueError('任务不存在')
        task = dict(row)
        snapshot = json.loads(task.pop('snapshot') or '{}')
        task['messages'] = snapshot.get('messages', [])
        task['pending'] = snapshot.get('thread',{}).get('pendingRequestCount',0)
        task['artifacts'] = self.artifacts(task_id)
        return task

    def tasks(self):
        with self.db() as db:
            rows = db.execute('SELECT id,title,category,provider,model,COALESCE(effort,"") AS effort,prompt,thread_id,state,error,snapshot,created_at,updated_at FROM tasks WHERE COALESCE(archived,0)=0 ORDER BY created_at DESC LIMIT 200').fetchall()
        out = []
        for row in rows:
            t = dict(row)
            snap = json.loads(t.pop('snapshot') or '{}')
            t['pending'] = snap.get('thread', {}).get('pendingRequestCount', 0)
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

    def _execute(self, task_id, task, prompt_text, messages, session_id=None):
        cmd = find_provider_bin(task['provider'])
        if not cmd:
            self.update(task_id, state='failed', error=f"未找到本机 {self.providers.get(task['provider'], {}).get('name', task['provider'])} 可执行程序")
            return
        with self.lock:
            self.stopped_tasks.discard(task_id)
        try:
            if task['provider'] == 'codex':
                self._run_codex(task_id, cmd, task, prompt_text, messages, session_id)
            else:
                self._run_acp(task_id, cmd, task, prompt_text, messages, session_id)
        except Exception as e:
            with self.lock:
                was_stopped = task_id in self.stopped_tasks
            if was_stopped:
                self._save_messages(task_id, messages, state='stopped', error=None)
            else:
                self._save_messages(task_id, messages, state='failed', error=scrub(e))
        finally:
            with self.lock:
                self.active_procs.pop(task_id, None)

    def _run_codex(self, task_id, base_cmd, task, prompt_text, messages, session_id=None):
        args = list(base_cmd)
        if session_id:
            args += ['exec', 'resume', '--json', '--skip-git-repo-check', '-m', task['model']]
            if task.get('effort'):
                args += ['-c', f"model_reasoning_effort={task['effort']}"]
            args += [session_id, '-']
        else:
            args += ['exec', '--json', '--skip-git-repo-check', '-s', 'workspace-write', '-C', str(self.workspace), '-m', task['model']]
            if task.get('effort'):
                args += ['-c', f"model_reasoning_effort={task['effort']}"]
            args += ['-']
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(self.workspace))
        with self.lock:
            self.active_procs[task_id] = proc
        proc.stdin.write(prompt_text)
        proc.stdin.close()
        self.update(task_id, state='running', error=None)
        reply_parts = []
        last_err = None
        new_sid = session_id
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            etype = ev.get('type')
            if etype == 'thread.started' and ev.get('thread_id'):
                new_sid = ev['thread_id']
                self.update(task_id, thread_id=new_sid)
            elif etype == 'item.completed':
                item = ev.get('item') or {}
                if item.get('type') == 'agent_message' and item.get('text'):
                    reply_parts.append(item['text'])
                    cur = list(messages) + [{'role': 'assistant', 'text': '\n\n'.join(reply_parts)}]
                    self._save_messages(task_id, cur, thread_id=new_sid)
            elif etype == 'turn.failed':
                last_err = (ev.get('error') or {}).get('message') or '执行失败'
            elif etype == 'error' and ev.get('message'):
                last_err = ev['message']
        rc = proc.wait()
        with self.lock:
            was_stopped = task_id in self.stopped_tasks
        final_msgs = list(messages)
        if reply_parts:
            final_msgs.append({'role': 'assistant', 'text': '\n\n'.join(reply_parts)})
        if was_stopped:
            self._save_messages(task_id, final_msgs, state='stopped', thread_id=new_sid, error=None)
        elif rc == 0 and not last_err:
            self._save_messages(task_id, final_msgs, state='completed', thread_id=new_sid, error=None)
        else:
            self._save_messages(task_id, final_msgs, state='failed', thread_id=new_sid, error=scrub(last_err or f'Codex 退出码 {rc}'))

    def _run_acp(self, task_id, base_cmd, task, prompt_text, messages, session_id=None):
        proc = subprocess.Popen(list(base_cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, cwd=str(self.workspace))
        with self.lock:
            self.active_procs[task_id] = proc
        rpc_seq = 0

        def send_rpc(method, params):
            nonlocal rpc_seq
            rpc_seq += 1
            rid = rpc_seq
            proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params}, ensure_ascii=False) + '\n')
            proc.stdin.flush()
            return rid

        def reply_permission(req_id, params):
            options = params.get('options') or []
            chosen = None
            for opt in options:
                if opt.get('kind') in ('allow_once', 'allow_always') or 'allow' in str(opt.get('optionId', '')).lower():
                    chosen = opt.get('optionId')
                    break
            if not chosen and options:
                chosen = options[0].get('optionId')
            if chosen:
                proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': {'outcome': {'outcome': 'selected', 'optionId': chosen}}}) + '\n')
            else:
                proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'result': {'outcome': {'outcome': 'cancelled'}}}) + '\n')
            proc.stdin.flush()

        reply_chunks = []
        last_flush = time.monotonic()

        def wait_rpc(target_id):
            nonlocal last_flush
            while True:
                line = proc.stdout.readline()
                if not line:
                    return None
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get('id') == target_id and ('result' in obj or 'error' in obj):
                    return obj
                if 'id' in obj and obj.get('method') == 'session/request_permission':
                    reply_permission(obj['id'], obj.get('params') or {})
                elif obj.get('method') == 'session/update':
                    upd = (obj.get('params') or {}).get('update') or {}
                    if upd.get('sessionUpdate') == 'agent_message_chunk':
                        chunk = (upd.get('content') or {}).get('text')
                        if chunk:
                            reply_chunks.append(chunk)
                            if time.monotonic() - last_flush > 0.4:
                                cur = list(messages) + [{'role': 'assistant', 'text': ''.join(reply_chunks)}]
                                self._save_messages(task_id, cur)
                                last_flush = time.monotonic()

        try:
            init_res = wait_rpc(send_rpc('initialize', {'protocolVersion': 1, 'clientCapabilities': {}, 'clientInfo': {'name': 'huixin-hub', 'version': VERSION}}))
            if not init_res or 'error' in init_res:
                raise RuntimeError((init_res or {}).get('error', {}).get('message', 'ACP 初始化失败'))
            if session_id:
                sess_res = wait_rpc(send_rpc('session/load', {'sessionId': session_id, 'cwd': str(self.workspace), 'mcpServers': []}))
                sid = session_id
            else:
                sess_res = wait_rpc(send_rpc('session/new', {'cwd': str(self.workspace), 'mcpServers': []}))
                sid = (sess_res or {}).get('result', {}).get('sessionId')
            if not sess_res or 'error' in sess_res or not sid:
                raise RuntimeError((sess_res or {}).get('error', {}).get('message', '创建会话失败'))
            self.update(task_id, thread_id=sid, state='running', error=None)
            wait_rpc(send_rpc('session/set_mode', {'sessionId': sid, 'modeId': 'auto'}))
            wait_rpc(send_rpc('session/set_model', {'sessionId': sid, 'modelId': task['model']}))
            if task.get('effort'):
                cfg_opts = (sess_res.get('result') or {}).get('configOptions') or []
                for opt in cfg_opts:
                    if opt.get('id') in ('thought_level', 'reasoning_effort', 'effort'):
                        wait_rpc(send_rpc('session/set_config_option', {'sessionId': sid, 'configId': opt['id'], 'value': task['effort']}))
                        break
            prompt_res = wait_rpc(send_rpc('session/prompt', {'sessionId': sid, 'prompt': [{'type': 'text', 'text': prompt_text}]}))
            with self.lock:
                was_stopped = task_id in self.stopped_tasks
            final_msgs = list(messages)
            if reply_chunks:
                final_msgs.append({'role': 'assistant', 'text': ''.join(reply_chunks)})
            if was_stopped:
                self._save_messages(task_id, final_msgs, state='stopped', thread_id=sid, error=None)
            elif prompt_res and 'result' in prompt_res:
                self._save_messages(task_id, final_msgs, state='completed', thread_id=sid, error=None)
            else:
                err_msg = ((prompt_res or {}).get('error') or {}).get('message') or '智能体执行未返回结果'
                self._save_messages(task_id, final_msgs, state='failed', thread_id=sid, error=scrub(err_msg))
        finally:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=3)

    def launch(self,task_id):
        task=self.get(task_id)
        self.update(task_id,state='starting')
        prompt = task['prompt']+'\n\n【工作要求】默认用简体中文。需要生成文件时，请将最终交付物写入 tasks/'+task_id+'/交付物/。最终回复列明实际生成的文件与检查结果；没有生成文件请如实说明。不要输出任何账号凭证。'
        self._execute(task_id, task, prompt, [{'role': 'user', 'text': task['prompt']}], session_id=None)

    def refresh(self,task_id):
        return self.get(task_id)

    def schedule_refresh(self,task_id,force=False):
        pass

    def stop_task(self, task_id):
        self.get(task_id)
        with self.lock:
            self.stopped_tasks.add(task_id)
            proc = self.active_procs.get(task_id)
        if proc and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
        self.update(task_id, state='stopped', error=None)
        return self.get(task_id)

    def followup(self,task_id,message):
        task=self.get(task_id)
        if not task['thread_id']:
            raise ValueError('任务尚未创建成功，请稍候或重新发起')
        if task['state'] in ('queued', 'submitting', 'starting', 'running', 'working'):
            raise ValueError('当前任务正在执行中，请等待完成或先停止任务')
        message=str(message).strip()
        if not message or len(message)>30000:
            raise ValueError('请输入后续需求，最多 30,000 字')
        messages = list(task.get('messages') or [{'role': 'user', 'text': task['prompt']}])
        messages.append({'role': 'user', 'text': message})
        self._save_messages(task_id, messages, state='starting', error=None)
        self.launch_pool.submit(self._execute, task_id, task, message, messages, task['thread_id'])
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
                    return self.send({'tasks':tasks,'providers':hub.providers,'categories':CATEGORIES,'ready':hub.ready_error=='','error':hub.ready_error,'workspace':str(hub.workspace),'company':'汇芯','version':VERSION})
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
                        return self.send(hub.followup(task_id,body.get('message','')))
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
                if path=='/api/providers/sync':
                    return self.send(hub.sync_providers())
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
