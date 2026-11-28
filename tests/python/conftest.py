import copy
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from board_engine.model import normalize_design  # noqa: E402


def base_plate(**kw):
    """Horizontal 100 x 60 base: top face at y = 3 (rotation -90 => local (x, y) = world (x, -z))."""
    c = {'id': 'BASE', 'name': 'Base', 'outline': [[-50, -30], [50, -30], [50, 30], [-50, 30]],
         'placement': {'position': [0, 1.5, 0], 'rotation': [-90, 0, 0]}}
    c.update(kw)
    return c


def wall(**kw):
    """Vertical 80 x 40 wall in the world XY plane standing on the base, one 20 mm tab into it."""
    c = {'id': 'WALL', 'name': 'Wall', 'outline': [[-40, -20], [40, -20], [40, 20], [-40, 20]],
         'tabs': [{'id': 't1', 'edge': 0, 'offset': 40, 'width': 20, 'depth': 3}],
         'placement': {'position': [0, 23, 0], 'rotation': [0, 0, 0]}}
    c.update(kw)
    return c


def make(*comps, joints=()):
    return normalize_design({'id': 'test', 'name': 'Test', 'components': list(comps), 'joints': list(joints)})


TAB_JOINT = {'id': 'J1', 'type': 'tab_slot', 'a': 'WALL', 'tab': 't1', 'b': 'BASE'}
GOOD_SLOT = {'id': 's1', 'kind': 'slot', 'shape': 'rect', 'center': [0, 0], 'width': 20.1, 'height': 3.1, 'angle': 0}


@pytest.fixture
def pair():
    return make(base_plate(), wall())


@pytest.fixture
def pair_with_slot():
    return make(base_plate(features=[copy.deepcopy(GOOD_SLOT)]), wall())


@pytest.fixture(scope='session')
def boat():
    from board_engine.examples.boat import build_design
    design, failures = build_design()
    assert failures == []
    return design


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: long benchmark-style tests (deselect with -m "not slow")')
