#!/usr/bin/env python3
"""
Reference AI-agent client for the Board Design API (stdlib only).

It plays the role of an AI design agent and follows the controlled workflow:
  1. take a product requirement            6. inspect alignment / joint problems
  2. discover the API (contract, tools)    7. request corrections through the API
  3. analyse the requirement               8. let the server re-validate every change
  4. generate the 2D board components      9. repeat until valid and complete
  5. let the server validate them         10. fetch the final 3D model + production files

To prove the correction loop it deliberately makes realistic mistakes — a side panel placed
2 mm high, a duplicate part, the mast standing in the cockpit opening, an impossible joint —
and fixes them only from the structured feedback the API returns.

Usage:
  python tools/ai_agent_demo.py --url http://127.0.0.1:5000 --key <API key> [--out DIR]
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from board_engine.examples.boat import DEFAULTS, build_components, build_joints  # noqa: E402  (the agent's design knowledge)


class Client:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.key = key
        self.calls = 0

    def call(self, method, path, body=None, raw=False):
        self.calls += 1
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': f'Bearer {self.key}',
                                              **({'Content-Type': 'application/json'} if body is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                return r.status, (data if raw else json.loads(data))
        except urllib.error.HTTPError as e:
            data = e.read()
            try:
                return e.code, json.loads(data)
            except ValueError:
                return e.code, {'raw': data.decode(errors='replace')}


def log(step, msg):
    print(f'[{step:>8}] {msg}', flush=True)


def first_error(resp):
    issues = resp.get('error', {}).get('issues', [])
    return next((i for i in issues if i.get('severity') == 'error'), issues[0] if issues else {})


def run(url, key, out_dir=None, design_id='agent-boat'):
    c = Client(url, key)
    findings = {'rejections': {}, 'corrections': [], 'repairs': 0}

    # 1-2. requirement + discovery
    requirement = 'Design a small laser-cut sailing boat about 300 mm long from 3 mm birch plywood.'
    log('require', requirement)
    st, contract = c.call('GET', '/api/v1/')
    st, tools = c.call('GET', '/api/v1/tools')
    log('discover', f"{contract['name']} v{contract['version']}: {len(contract['endpoints'])} endpoints, "
                    f"{len(tools['tools'])} tools; units={contract['conventions']['units']}")
    st, who = c.call('GET', '/api/v1/whoami')
    assert st == 200, who
    log('discover', f"authenticated as {who['principal']['name']} ({who['principal']['role']})")

    # 3. analyse -> parameters
    params = dict(DEFAULTS, length=300.0, thickness=3.0)
    log('analyse', f"hull {params['length']} x {params['beam']} x {params['depth']} mm, mast {params['mast_height']} mm, "
                   f"t={params['thickness']} mm")

    # 4. generate components (with deliberate mistakes)
    comps = build_components(params)
    by_id = {x['id']: x for x in comps}
    by_id['SIDE-AFT-PORT']['placement']['position'][1] += 2.0          # mistake: 2 mm too high
    intended_mast_x = by_id['MAST']['placement']['position'][0]
    cockpit_x = next(f for f in by_id['DECK']['features'] if f['id'] == 'cockpit')['center'][0]
    by_id['MAST']['placement']['position'][0] = cockpit_x              # mistake: mast in the cockpit
    log('generate', f'{len(comps)} components generated')

    st, r = c.call('DELETE', f'/api/v1/designs/{design_id}')  # editor key: expected 403, harmless
    st, r = c.call('POST', '/api/v1/designs', {'id': design_id, 'name': 'Agent day sailer',
                                              'material': {'name': 'Birch plywood 3 mm', 'thickness': 3.0},
                                              'components': comps})
    if st == 409:
        design_id = f'{design_id}-{os.getpid()}'
        st, r = c.call('POST', '/api/v1/designs', {'id': design_id, 'name': 'Agent day sailer', 'components': comps})
    assert st == 201, r
    v = r['validation']
    log('validate', f"2D accepted; assembly has {v['summary']['errors']} errors, {v['summary']['warnings']} warnings "
                    f"(expected: tabs without slots collide)")

    # 5. duplicate detection
    dup = copy.deepcopy(by_id['BULKHEAD-1'])
    dup['id'] = 'BULKHEAD-1-COPY'
    st, r = c.call('POST', f'/api/v1/designs/{design_id}/components', {'component': dup})
    log('dup', f"adding an identical bulkhead -> HTTP {st} {first_error(r).get('code')}")
    findings['rejections']['duplicate'] = first_error(r).get('code')

    # 6-9. joint loop: check -> correct -> join
    pending = build_joints()
    for spec in pending:
        for attempt in range(4):
            st, chk = c.call('POST', f'/api/v1/designs/{design_id}/joints/check', {'joint': spec})
            errors = [i for i in chk['issues'] if i['severity'] == 'error']
            blocking = [i for i in errors if 'repair' not in i]
            if not blocking:
                st, r = c.call('POST', f'/api/v1/designs/{design_id}/joints',
                               {'joint': spec, 'auto_repair': bool(errors)})
                if st == 201:
                    findings['repairs'] += len(r['result']['repairs_applied'])
                    break
                blocking = [first_error(r)]
            issue = blocking[0]
            code = issue['code']
            findings['rejections'].setdefault(code, spec['id'])
            if code in ('UNINTENDED_GAP', 'PENETRATION', 'SLOT_MISALIGNED') and issue.get('suggestion'):
                s = issue['suggestion']
                log('correct', f"{spec['id']}: {code} -> translate {s['component']} by {s['delta']}")
                st, r = c.call('POST', f"/api/v1/designs/{design_id}/components/{s['component']}/translate",
                               {'delta': s['delta']})
                assert st == 200, r
                findings['corrections'].append((spec['id'], code))
            elif code == 'TAB_IN_OPENING':
                comp = spec['a']
                st, cur = c.call('GET', f'/api/v1/designs/{design_id}/components/{comp}')
                dx = intended_mast_x - cur['component']['placement']['position'][0]
                log('correct', f"{spec['id']}: tab lands in '{issue.get('feature')}' (intentional opening, preserved) "
                               f"-> move {comp} {dx:+.1f} mm along X")
                st, r = c.call('POST', f'/api/v1/designs/{design_id}/components/{comp}/translate', {'delta': [dx, 0, 0]})
                assert st == 200, r
                findings['corrections'].append((spec['id'], code))
            else:
                raise SystemExit(f"agent cannot resolve {spec['id']}: {code}: {issue.get('message')}")
        else:
            raise SystemExit(f"gave up on {spec['id']}")
    log('join', f"{len(pending)} joints joined, {findings['repairs']} slots generated by safe repair, "
                f"{len(findings['corrections'])} corrections")

    # Negative probe: components that must not be joined
    bad = {'id': 'J-BAD', 'type': 'edge_butt', 'a': 'KEEL', 'a_edge': 0, 'b': 'RUDDER'}
    st, r = c.call('POST', f'/api/v1/designs/{design_id}/joints', {'joint': bad, 'auto_repair': True})
    log('probe', f"KEEL edge -> RUDDER face: HTTP {st} {first_error(r).get('code')} (rejected as expected)")
    findings['rejections']['invalid_join'] = first_error(r).get('code')

    # 10. final state
    st, r = c.call('POST', f'/api/v1/designs/{design_id}/validate')
    v = r['validation']
    log('final', f"valid={v['valid']} complete={v['complete']} {v['summary']}")
    st, m = c.call('GET', f'/api/v1/designs/{design_id}/model3d')
    states = {x['state'] for x in m['components']}
    log('final', f"3D model: {len(m['components'])} components, states={sorted(states)}, bounds={m['bounds']['min']}..{m['bounds']['max']}")
    st, lay = c.call('GET', f'/api/v1/designs/{design_id}/layout2d?preset=A3&kerf=1')
    log('produce', f"A3 nesting: {lay['nesting']['sheet_count']} sheets, efficiency {lay['nesting']['stats']['efficiency_percent']}%, "
                   f"ready={lay['ready_for_production']}")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        st, pdf = c.call('GET', f'/api/v1/designs/{design_id}/export/pdf?preset=A3&kerf=1', raw=True)
        open(os.path.join(out_dir, f'{design_id}-booklet.pdf'), 'wb').write(pdf)
        for i in range(lay['nesting']['sheet_count']):
            for fmt in ('svg', 'dxf'):
                st, data = c.call('GET', f'/api/v1/designs/{design_id}/export/{fmt}?preset=A3&kerf=1&sheet={i + 1}', raw=True)
                open(os.path.join(out_dir, f'{design_id}-sheet{i + 1}.{fmt}'), 'wb').write(data)
        log('produce', f'production files written to {out_dir}')
    log('done', f'{c.calls} API calls')
    return {'design_id': design_id, 'validation': v, 'states': states, 'findings': findings,
            'ready': lay['ready_for_production']}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default='http://127.0.0.1:5000')
    ap.add_argument('--key', default=os.environ.get('BOARD_API_KEY'))
    ap.add_argument('--out')
    ap.add_argument('--design-id', default='agent-boat')
    a = ap.parse_args()
    if not a.key:
        sys.exit('pass --key or set BOARD_API_KEY (see instance/api_keys.json)')
    res = run(a.url, a.key, a.out, a.design_id)
    sys.exit(0 if res['validation']['valid'] and res['validation']['complete'] else 1)


if __name__ == '__main__':
    main()
