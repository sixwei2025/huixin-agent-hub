#!/usr/bin/python3
"""Keep vendor startup banners off the ACP JSON-RPC channel."""
import json
import signal
import subprocess
import sys
import threading

p = subprocess.Popen(sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

def forward_input():
    try:
        for line in sys.stdin.buffer:
            p.stdin.write(line)
            p.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass

def stop(signum, frame):
    if p.poll() is None:
        p.terminate()

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
threading.Thread(target=forward_input, daemon=True).start()
try:
    for line in p.stdout:
        try:
            value = json.loads(line)
            is_rpc = isinstance(value, dict) and value.get('jsonrpc') == '2.0'
        except (ValueError, UnicodeError):
            is_rpc = False
        if is_rpc:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
        else:
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()
finally:
    if p.poll() is None:
        p.terminate()
sys.exit(p.wait())
