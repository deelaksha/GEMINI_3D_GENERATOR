"""End-to-end corpus and joint matrix as regression tests (tests/e2e). Each product runs the whole pipeline:
compile -> validation -> support -> nesting -> kerf-compensated cut paths -> exports, with 2D/3D consistency checks."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'e2e'))

from joint_matrix import negatives, positives  # noqa: E402
from pipeline import run_case, verdict  # noqa: E402
from products import CASES  # noqa: E402


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_product_pipeline(case):
    rec = run_case(case)
    assert not verdict(rec), verdict(rec)


def test_joint_matrix_positive_cases():
    bad = [(r['joint'], r['actual']) for r in positives() if not r['pass']]
    assert not bad, bad


def test_joint_matrix_negative_cases_are_all_detected():
    bad = [(r['defect'], r['actual']) for r in negatives() if not r['pass']]
    assert not bad, bad
