"""Score AI-written designs: same products, same engine, different prompts.

    python tests/e2e/score_ai_outputs.py <outputs-dir> [<outputs-dir> ...] --out scores.json

Every <outputs-dir>/<K>.json is compiled and run through the whole pipeline (tests/e2e/pipeline.py). An update round
(<K>2.json, the design after a change request) is compared with <K>.json board by board to measure preservation.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_engine.canvas import compile_source, parse_source  # noqa: E402
from pipeline import run_case  # noqa: E402


def score(path):
    text = open(path).read()
    data, _src, _off, perr = parse_source(text)
    out = {'file': os.path.basename(path), 'chars': len(text), 'json_ok': data is not None}
    if data is None:
        out['parse_error'] = perr[0]['message']
        return out
    rec = run_case({'id': os.path.basename(path), 'title': '', 'categories': [], 'prompt': '', 'design': data,
                    'expect': {}, 'source': 'AI output'})
    r = compile_source(text, run_production=False)
    ids = [b.get('id', '') for b in data.get('boards', []) if isinstance(b, dict)]
    desc = str((data.get('product') or {}).get('description', ''))
    out.update({'compiled': rec.get('compiled'), 'errors': rec['diagnostics']['errors'], 'warnings': rec['diagnostics']['warnings'],
                'first_errors': rec['diagnostics']['first_errors'][:3], 'boards': len(ids), 'max_id_len': max(map(len, ids), default=0),
                'joints': rec.get('joints'), 'joined': rec.get('joined'), 'ready': rec.get('ready_for_production'),
                'consistent_2d_3d': (rec.get('consistency_2d_3d') or {}).get('ok'),
                'stable': (rec.get('support') or {}).get('stable') if isinstance(rec.get('support'), dict) else None,
                'support_issues': (rec.get('support') or {}).get('issues') if isinstance(rec.get('support'), dict) else None,
                'states_assumptions': 'assumption' in desc.lower(), 'mounting': (data.get('product') or {}).get('mounting'),
                'groups': len({b.get('group') for b in data.get('boards', []) if isinstance(b, dict)}),
                'error_count': sum(1 for d in r['diagnostics'] if d['severity'] == 'error'),
                'warning_count': sum(1 for d in r['diagnostics'] if d['severity'] == 'warning')})
    return out


def preservation(before_path, after_path):
    """Boards kept identical / changed / added / removed between a design and its update."""
    try:
        a = {b['id']: b for b in json.loads(open(before_path).read())['boards']}
        b = {x['id']: x for x in json.loads(open(after_path).read())['boards']}
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {'error': str(e)}
    same = [k for k in a if k in b and all(a[k].get(f) == b[k].get(f) for f in ('position', 'size', 'thickness', 'profile', 'rotate', 'openings'))]
    changed = [k for k in a if k in b and k not in same]
    return {'kept_identical': len(same), 'changed': sorted(changed), 'added': sorted(set(b) - set(a)), 'removed': sorted(set(a) - set(b))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--out')
    args = ap.parse_args()
    res = {}
    for d in args.dirs:
        rows = {}
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                rows[f[:-5]] = score(os.path.join(d, f))
        for k in list(rows):
            if k.endswith('2') and k[:-1] in rows:
                rows[k]['preservation'] = preservation(os.path.join(d, k[:-1] + '.json'), os.path.join(d, k + '.json'))
        res[os.path.basename(os.path.normpath(d))] = rows
    text = json.dumps(res, indent=1, default=str)
    if args.out:
        open(args.out, 'w').write(text)
    print(text)


if __name__ == '__main__':
    main()
