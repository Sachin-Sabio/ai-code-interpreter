"""Verify the actual public endpoint; never guess a hostname."""
import json
import sys
import urllib.request
from urllib.parse import urlparse

url = sys.argv[1]
assert urlparse(url).scheme == 'https' and urlparse(url).path == '/code-interpreter'
for code, expected in [('print(5 + 10)', []), ('x = 10\ny = 0\nresult = x / y', [3])]:
    request = urllib.request.Request(url, data=json.dumps({'code': code}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
        assert response.status == 200
    assert set(payload) == {'error', 'result'}, payload
    assert payload['error'] == expected, payload
    if expected:
        assert 'ZeroDivisionError' in payload['result'], payload
    else:
        assert payload['result'] == '15\n', payload
    print(json.dumps(payload))
print('Verified submission URL:', url)
