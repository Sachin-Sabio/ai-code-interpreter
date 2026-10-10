from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock
import time

from fastapi.testclient import TestClient
import pytest
import main

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def ai_mock(monkeypatch):
    mock = Mock(side_effect=lambda code, tb: main.traceback_lines(tb, code))
    monkeypatch.setattr(main, 'analyze_error_with_ai', mock)
    return mock


def post(code):
    response = client.post('/code-interpreter', json={'code': code})
    assert response.status_code == 200, response.text
    assert set(response.json()) == {'error', 'result'}
    return response.json()


def test_success_no_llm(ai_mock):
    assert post('print(5 + 10)') == {'error': [], 'result': '15\n'}
    ai_mock.assert_not_called()

@pytest.mark.parametrize('code,line', [
    ('x = 10\ny = 0\nresult = x / y', 3),
    ('x = 1\nif True print(x)', 2),
    ('a = 1\nb = 2\nc = 3\nprint(missing)', 4),
    ('def f():\n    return 1 / 0\nf()', 2),
])
def test_errors(code, line, ai_mock):
    result = post(code)
    assert result['error'] == [line]
    assert 'Traceback' in result['result']
    assert result['result'].endswith('\n')
    ai_mock.assert_called_once_with(code, result['result'])


def test_exact_whitespace():
    assert post("print('  hi  '); print(); print('\\tend', end='  ')")['result'] == '  hi  \n\n\tend  '


def test_stderr_not_stdout():
    assert post("import sys; print('err', file=sys.stderr); print('ok')")['result'] == 'ok\n'


def test_exact_traceback_passthrough(monkeypatch):
    exact = 'Traceback...\n  spacing  \n'
    monkeypatch.setattr(main, 'execute_python_code', lambda code: {'success': False, 'output': exact})
    assert post('1/0')['result'] == exact


def test_concurrency():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: post(f"print('  {n}  ')")['result'], range(4)))
    assert results == [f'  {n}  \n' for n in range(4)]


def test_infinite_loop():
    start = time.monotonic()
    result = post('while True: pass')
    assert time.monotonic() - start < 6
    assert result['error'] == []
    assert 'TimeoutError' in result['result']


def test_llm_failure_fallback(ai_mock):
    ai_mock.side_effect = ValueError('malformed')
    assert post('1/0')['error'] == [1]

@pytest.mark.parametrize('content', ['not json', '{}', '{"error_lines":[true]}', '{"error_lines":["1"]}', '{"error_lines":[1],"extra":0}'])
def test_malformed_llm(monkeypatch, content):
    # Undo autouse mock to exercise real Pydantic parsing without a network call.
    from importlib import reload
    real = reload(main).analyze_error_with_ai
    fake = Mock()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    monkeypatch.setattr(main, 'OpenAI', Mock(return_value=fake))
    monkeypatch.setenv('AIPIPE_TOKEN', 'test-token')
    with pytest.raises(ValueError):
        real('1/0', 'File "<submitted>", line 1\n')
    assert post('1/0')['error'] == [1]


def test_llm_lines_validated(monkeypatch):
    from importlib import reload
    real = reload(main).analyze_error_with_ai
    fake = Mock()
    fake.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"error_lines":[1,2,999,-1]}'))])
    monkeypatch.setattr(main, 'OpenAI', Mock(return_value=fake))
    monkeypatch.setenv('AIPIPE_TOKEN', 'test-token')
    assert real('x=1\n1/0', 'File "<submitted>", line 2\n') == [2]
    args = fake.chat.completions.create.call_args.kwargs
    assert 'x=1' in args['messages'][1]['content']
    assert 'traceback' in args['messages'][1]['content']

@pytest.mark.parametrize('code', [
    "open('/etc/passwd').read()",
    "import socket; socket.socket().connect(('example.com', 80))",
    "import os; os.fork()",
])
def test_sandbox_denies_host_access(code):
    result = post(code)
    assert result['error']
    assert 'Error' in result['result']


def test_worker_has_no_credentials(monkeypatch):
    monkeypatch.setenv('AIPIPE_TOKEN', 'do-not-expose')
    assert post("import os; print(os.environ.get('AIPIPE_TOKEN'))")['result'] == 'None\n'


def test_validation():
    assert client.post('/code-interpreter', json={'code': 12}).status_code == 422
