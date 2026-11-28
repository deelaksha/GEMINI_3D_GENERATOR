# Offline: a fake 'anthropic' module is injected; nothing is sent anywhere.
import sys, types
sys.path.insert(0,'.')
fake=types.ModuleType('anthropic')
class E(Exception): pass
fake.RateLimitError=fake.APIStatusError=fake.APIConnectionError=E
class Msg: stop_reason='max_tokens'; content=[types.SimpleNamespace(type='text', text='{"format":"board-design/v1","boards":[{"id":"A"')]
class Stream:
    def __enter__(s): return s
    def __exit__(s,*a): return False
    def get_final_message(s): return Msg()
class Client:
    def __init__(s, **k): s.beta=types.SimpleNamespace(messages=types.SimpleNamespace(stream=lambda **kw: Stream()))
fake.Anthropic=Client; sys.modules['anthropic']=fake
from board_engine import ai_client
print('claude max_tokens reply returned as success:', repr(ai_client._claude('p','m')))
