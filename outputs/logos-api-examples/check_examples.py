import json
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
cli = [str(root / "logos/bin/logoscore"), "--json", "--config-dir", str(root / ".logoscore")]

def command(*args):
    result = subprocess.run(cli + list(args), text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f"{args}: {result.stdout} {result.stderr}")
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    return json.loads(lines[-1]) if lines else {}

def call(module, method, *args):
    reply = command("call", module, method, *args)
    assert reply.get("status") == "ok", reply
    return reply["result"]

cases = [['echoString', 'hello Logos'],
 ['echoBytes', {'_bytes': 'AAH_'}],
 ['echoInt', -42],
 ['echoUint', 42],
 ['echoDouble', 2.5],
 ['echoBool', False],
 ['echoAny', {'mixed': [1, False, 'text']}],
 ['echoStringList', ['one', 'two']],
 ['echoIntList', [-2, 0, 3]],
 ['echoUintList', [0, 3]],
 ['echoDoubleList', [1.5, 2.5]],
 ['echoBoolList', [True, False]],
 ['echoList', [1, 'text', None]],
 ['echoMap', {'count': 3, 'label': 'sample'}],
 ['echoBytesList', [{'_bytes': 'AAH_'}, {'_bytes': ''}]],
 ['echoBytesMap', {'data': {'_bytes': 'AAH_'}}],
 ['echoIntMap', {'first': -2, 'second': 3}],
 ['echoUnorderedMap', {'first': -2, 'second': 3}],
 ['echoNested', [[1, 2], [], [3]]],
 ['echoEntry', {'label': 'sample', 'payload': {'_bytes': 'AAH_'}, 'count': 7}],
 ['echoEntries', [{'label': 'empty', 'payload': {'_bytes': ''}}]],
 ['echoEntryMap', {'one': {'label': 'first', 'payload': {'_bytes': 'AAH_'}}}],
 ['echoBatch',
  {'entry': {'label': 'nested', 'payload': {'_bytes': 'AAH_'}}, 'tags': ['tag']}],
 ['echoOptional', None],
 ['echoOptional', ''],
 ['echoOptional', 'present'],
 ['echoInt', 0],
 ['echoString', ''],
 ['echoStringList', []],
 ['echoBytes', {'_bytes': ''}],
 ['echoEntry', {'label': 'absent', 'payload': {'_bytes': ''}}]]

with (root / "daemon.log").open("w") as log:
    daemon = subprocess.Popen(cli + ["-D", "-m", str(root / "modules")],
                              stdout=log, stderr=subprocess.STDOUT)
    try:
        for attempt in range(100):
            try:
                command("status")
                break
            except (RuntimeError, subprocess.TimeoutExpired):
                if daemon.poll() is not None:
                    raise RuntimeError("daemon exited; read daemon.log")
                time.sleep(0.2)
        else:
            raise RuntimeError("daemon did not become ready")
        for module in ("api_cpp", "api_rust"):
            command("load-module", module)
        for module in ("api_cpp", "api_rust"):
            for method, value in cases:
                arg = "json:" + json.dumps(value, separators=(",", ":"))
                actual = call(module, method, arg)
                assert actual == value, (module, method, value, actual)
            print(f"{module}: {len(cases)} type round trips passed")
        # Each caller runs against the provider written in the OTHER language.
        for caller, provider in (("api_cpp", "api_rust"), ("api_rust", "api_cpp")):
            assert call(caller, "checkCalls", provider) == "sync checks passed"
            assert call(caller, "startAsync", provider) == "started"
            for attempt in range(100):
                status = call(caller, "asyncStatus")
                if status != "pending":
                    break
                time.sleep(0.1)
            assert status == "async checks passed", (caller, status)
            print(f"{caller} -> {provider}: sync and async checks passed")
    finally:
        try:
            command("stop")
        finally:
            try:
                daemon.wait(timeout=10)
            except subprocess.TimeoutExpired:
                daemon.terminate()
                daemon.wait(timeout=10)
