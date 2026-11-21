#!/usr/bin/env python3
"""测试用的假 ACP 智能体：不调用任何模型，按提示词触发不同行为。"""
import json
import sys
import time

HISTORY = {}


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def chunk(sid, text):
    send({'jsonrpc': '2.0', 'method': 'session/update',
          'params': {'sessionId': sid, 'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': text}}}})


def read():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return json.loads(line)


while True:
    msg = read()
    mid, method, p = msg.get('id'), msg.get('method'), msg.get('params') or {}
    if method == 'initialize':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'protocolVersion': 1}})
    elif method == 'session/new':
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'sessionId': 'sess-fake-1'}})
    elif method == 'session/load':
        if p.get('sessionId') == 'sess-fake-1':
            chunk(p['sessionId'], '旧回复')  # 模拟历史重放
            send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
        else:
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32000, 'message': 'session not found'}})
    elif method in ('session/set_mode', 'session/set_model', 'session/set_config_option'):
        send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
    elif method == 'session/prompt':
        sid = p['sessionId']
        text = ''.join(x.get('text', '') for x in p.get('prompt', []))
        if '需要审批' in text:
            send({'jsonrpc': '2.0', 'id': 900, 'method': 'session/request_permission', 'params': {
                'sessionId': sid, 'toolCall': {'title': '删除文件 a.txt', 'rawInput': {'path': 'a.txt'}},
                'options': [{'optionId': 'allow', 'name': '允许', 'kind': 'allow_once'},
                            {'optionId': 'reject', 'name': '拒绝', 'kind': 'reject_once'}]}})
            ans = read()
            outcome = (ans.get('result') or {}).get('outcome') or {}
            chunk(sid, '审批结果=' + (outcome.get('optionId') or outcome.get('outcome', '')))
        elif '慢任务' in text:
            time.sleep(60)
        elif '对话记录' in text:
            chunk(sid, '收到历史')
        else:
            chunk(sid, '新回复')
        send({'jsonrpc': '2.0', 'id': mid, 'result': {'stopReason': 'end_turn'}})
