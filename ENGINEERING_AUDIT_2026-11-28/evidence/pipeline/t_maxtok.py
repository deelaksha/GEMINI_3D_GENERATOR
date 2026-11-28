# Offline: requests.post is replaced by a stub BEFORE any call, so no network / paid API call happens.
import os, sys, json
S=sys.argv[1]
os.environ['BOARD_INSTANCE_DIR']=S+'/inst'; os.environ['BOARD_SKIP_SEED']='1'
os.environ.pop('ANTHROPIC_API_KEY',None)
os.environ['GEMINI_API_KEY']='dummy-offline-not-a-key'
sys.path.insert(0,'.')
import requests
calls=[]
trunc=open(S+'/truncated.json').read()
class R:
    status_code=200
    def json(self): return {'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':trunc}]}}]}
def fake_post(url, **kw):
    calls.append((url, len(json.dumps(kw.get('json')))))
    return R()
requests.post=fake_post
import app as A
c=A.app.test_client(); c.get('/canvas'); H={'X-Board-Client':'studio'}
r=c.post('/api/v1/canvas/ai-generate',json={'title':'Study table','requirements':'5 boards: top, two legs, modesty panel, shelf'},headers=H)
print('ai-generate status', r.status_code, 'keys', list(r.json), 'finishReason surfaced?', 'MAX_TOKENS' in json.dumps(r.json))
print('stub called:', calls[0][0].split('/models/')[1], 'payload chars', calls[0][1])
src=r.json['source']
r1=c.post('/api/v1/canvas/compile',json={'source':src,'production':False},headers=H).json
print('compile #1 compiled', r1['compiled'], [d['code'] for d in r1['diagnostics']][:3])
fix=[f for d in r1['diagnostics'] for f in (d.get('fixes') or []) if f.get('kind')=='repair_json'][0]
r2=c.post('/api/v1/canvas/compile',json={'source':fix['source'],'production':True},headers=H).json
print('compile #2 (after the UI auto-applies repair_json once) compiled', r2['compiled'], 'boards', r2['summary'].get('boards') if r2.get('summary') else None,
      'diag', [(d['severity'],d['code']) for d in r2['diagnostics']])
