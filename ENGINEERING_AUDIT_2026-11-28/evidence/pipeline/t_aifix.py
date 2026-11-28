# Offline: requests.post stubbed before use; no network / paid call.
import os, sys, json, copy
S=sys.argv[1]
os.environ['BOARD_INSTANCE_DIR']=S+'/inst'; os.environ['BOARD_SKIP_SEED']='1'; os.environ.pop('ANTHROPIC_API_KEY',None)
os.environ['GEMINI_API_KEY']='dummy-offline-not-a-key'
sys.path.insert(0,'.')
import requests
from board_engine.canvas import pretty_json
D=json.load(open(S+'/example.json'))
bad=copy.deepcopy(D); bad['boards'][4]['position'][0]=69
worse={'format':'board-design/v1','material':{'thickness':18},'boards':[{'id':'X','position':[0,0,0],'size':[100,18,5]}]}
sent=[]
class R:
    status_code=200
    def json(self): return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'```json\n'+pretty_json(worse)+'\n```'}]}}]}
requests.post=lambda url, **kw: (sent.append(kw['json']['contents'][0]['parts'][0]['text']), R())[1]
import app as A
c=A.app.test_client(); c.get('/canvas'); H={'X-Board-Client':'studio'}
r=c.post('/api/v1/canvas/ai-fix',json={'source':pretty_json(bad)},headers=H).json
print('ai-fix response:', {k:v for k,v in r.items() if k!='source'})
print('returned source boards:', [b['id'] for b in json.loads(r['source'])['boards']], '(input had', [b['id'] for b in bad['boards']],')')
print('repair prompt chars sent:', len(sent[0]), '| contains requirements text? no requirements param accepted by /ai-fix')
rc=c.post('/api/v1/canvas/compile',json={'source':r['source'],'production':False},headers=H).json
print('compile of AI reply: compiled', rc['compiled'], [d['code'] for d in rc['diagnostics'] if d['severity']=='error'][:4])
