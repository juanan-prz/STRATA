"""What the test suites share. Not a test itself.

Checks            the checks of one suite: each prints PASS or FAIL as it runs,
                  and finish() prints the SUMMARY line and sets the exit code
fresh_framework   a separate copy of the framework module, with its own globals
                  and ledger, as a second instance of SIRISYS would have
FakeModel         a local stand-in for an Ollama model
scratch, quiet, environment, raises, read_jsonl   small helpers
"""
import atexit
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sirisys_loader import find_framework  # noqa: E402

FRAMEWORK = find_framework(HERE)[1]          # the newest, or the one SIRISYS_FRAMEWORK pins


class Checks:
    """The checks of one suite, in the order they run."""

    def __init__(self):
        self.results = []

    def section(self, title):
        print(f"\n== {title}")

    def __call__(self, name, ok, detail=""):
        ok = bool(ok)
        self.results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        return ok

    def finish(self):
        """The SUMMARY line, then what failed, if anything; exit code 0 only if all passed."""
        failed = [(name, detail) for name, ok, detail in self.results if not ok]
        print(f"\nSUMMARY: {len(self.results) - len(failed)}/{len(self.results)} passed")
        for name, detail in failed:
            print(f"  FAIL: {name}" + (f" — {detail}" if detail else ""))
        sys.exit(1 if failed else 0)


class _Discard(io.TextIOBase):
    def write(self, s):
        return len(s)


def quiet():
    """Silence the framework's own printing."""
    return contextlib.redirect_stdout(_Discard())


def fresh_framework(**overrides):
    """A separate copy of the framework module: its own globals and ledger, so two
    copies can live side by side. `overrides` set module constants after loading."""
    spec = importlib.util.spec_from_file_location(f"sirisys_copy_{time.time_ns()}", FRAMEWORK)
    module = importlib.util.module_from_spec(spec)
    with quiet():
        spec.loader.exec_module(module)
    for name, value in overrides.items():
        setattr(module, name, value)
    return module


def scratch():
    """A new temporary folder, removed when the suite ends."""
    folder = Path(tempfile.mkdtemp(prefix="sirisys_test_"))
    atexit.register(shutil.rmtree, folder, True)
    return folder


@contextlib.contextmanager
def environment(**values):
    """Set environment variables for the duration of a block."""
    saved = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def raises(action, error=Exception, text=""):
    """True if action() raises `error` with `text` in its message."""
    try:
        action()
    except error as ex:
        return text in str(ex)
    return False


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class FakeModel:
    """A local stand-in for Ollama: GET /api/tags lists one model, POST /api/chat answers.

    mode "alike"    the answer depends only on the request and its seed: a model
                    with no randomness of its own
         "counter"  "Name <n>", n counting every call: a model whose answers carry state
         "empty"    after `after` answers as "counter", empty answers
         "error"    after `after` answers as "counter", HTTP 500
    Every request body is kept in `requests`. Use it in a `with` block, or close()."""

    MODEL = "fake-model:latest"

    def __init__(self, mode="alike", after=0):
        self._lock = threading.Lock()
        self.reset(mode, after)
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send({"models": [{"name": FakeModel.MODEL}]})

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                answer = fake._answer(request)
                if answer is None:
                    self._send({"error": "model crashed"}, 500)
                else:
                    self._send({"message": {"role": "assistant", "content": answer}})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self._server.server_port}"

    def reset(self, mode, after=0):
        """A new behaviour, with the call count and the recorded requests cleared."""
        with self._lock:
            self.mode, self.after, self.calls, self.requests = mode, after, 0, []

    def _answer(self, request):
        with self._lock:
            self.calls += 1
            n = self.calls
            self.requests.append(request)
        if self.mode == "alike":
            key = f"{request['messages'][-1]['content']}::{request.get('options', {}).get('seed')}"
            return "Name " + hashlib.sha256(key.encode()).hexdigest()[:8]
        if n > self.after and self.mode == "error":
            return None
        if n > self.after and self.mode == "empty":
            return ""
        return f"Name {n}"

    @property
    def seeds(self):
        return [r.get("options", {}).get("seed") for r in self.requests]

    def close(self):
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
