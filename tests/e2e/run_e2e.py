"""Run the end-to-end product corpus and write machine-readable results.

    python tests/e2e/run_e2e.py [--out results.json] [--only E2E-03,E2E-07] [--no-design]
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import run_case, summary_row, verdict  # noqa: E402
from products import CASES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'PROJECT_AUDIT', 'END_TO_END_VALIDATION', 'e2e_results.json'))
    ap.add_argument('--only', default='')
    ap.add_argument('--no-design', action='store_true', help='omit the full compiled design JSON from the output')
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(',') if x.strip()}
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--', 'board_engine', 'board_api'], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    records = []
    for c in CASES:
        if only and c['id'] not in only:
            continue
        rec = run_case(c)
        rec['failed_expectations'] = verdict(rec)
        rec['result'] = 'PASS' if not rec['failed_expectations'] else 'FAIL'
        if a.no_design:
            rec.pop('design_json', None)
        records.append(rec)
        print(f"{rec['result']}  {c['id']:7} {rec.get('duration_s', 0):7.2f}s  {summary_row(rec)}"
              + ('' if rec['result'] == 'PASS' else f"\n        -> {rec['failed_expectations']}"), flush=True)
    out = {'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'commit': commit,
           'engine_modified_since_commit': dirty, 'python': platform.python_version(),
           'executed': 'all records are actual executions of the engine; designs are hand-written AI-style inputs, not Gemini output',
           'passed': sum(r['result'] == 'PASS' for r in records), 'failed': sum(r['result'] == 'FAIL' for r in records),
           'records': records}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n{out['passed']} passed, {out['failed']} failed -> {a.out}")


if __name__ == '__main__':
    main()
