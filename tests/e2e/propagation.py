"""Does one edit reach every representation? Adds a hole to a saved design via the API and re-reads 3D, 2D, cut list, SVG, DXF."""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def run():
    tmp = tempfile.mkdtemp(prefix='e2e-prop-')
    os.environ.update(BOARD_INSTANCE_DIR=tmp, BOARD_API_KEYS='k:editor', BOARD_SKIP_SEED='1', LOG_LEVEL='ERROR')
    import app as appmod
    from board_engine.canvas_prompt import EXAMPLE
    c, h = appmod.app.test_client(), {'Authorization': 'Bearer k'}
    try:
        did = c.post('/api/v1/canvas/save', headers=h, json={'source': json.dumps(EXAMPLE)}).get_json()['design_id']

        def snap():
            m = c.get(f'/api/v1/designs/{did}/model3d', headers=h).get_json()
            lay = c.get(f'/api/v1/designs/{did}/layout2d?kerf=1', headers=h).get_json()
            cl = c.get(f'/api/v1/designs/{did}/cutlist', headers=h).get_json()
            sheet = next(p['sheet'] for p in lay['nesting']['placements'] if p['id'] == 'TOP') + 1
            svg = c.get(f'/api/v1/designs/{did}/export/svg?kerf=1&sheet={sheet}', headers=h).get_data(as_text=True)
            dxf = c.get(f'/api/v1/designs/{did}/export/dxf?kerf=1&sheet={sheet}', headers=h).get_data(as_text=True)
            top = next(x for x in m['components'] if x['id'] == 'TOP')
            return {'revision_3d': m['revision'], 'revision_2d': lay['revision'], 'revision_cutlist': cl['revision'],
                    'top_features_3d': len(top['features']),
                    'top_inner_paths_2d': sum(1 for s in lay['cut']['sheets'] for p in s['paths'] if p['part'] == 'TOP' and p['type'] == 'inner'),
                    'hole_in_svg': 'TOP/grommet' in svg, 'hole_in_dxf_circles': dxf.count('CIRCLE\n8\nCUT_INNER'),
                    'ready': lay['ready_for_production']}
        before = snap()
        r = c.post(f'/api/v1/designs/{did}/components/TOP/features', headers=h,
                   json={'feature': {'id': 'grommet', 'kind': 'hole', 'shape': 'circle', 'center': [-500, 200], 'diameter': 60}})
        after = snap()
        ok = (r.status_code == 200 and after['revision_3d'] == after['revision_2d'] == after['revision_cutlist'] == before['revision_3d'] + 1
              and after['top_features_3d'] == before['top_features_3d'] + 1 and after['top_inner_paths_2d'] == before['top_inner_paths_2d'] + 1
              and after['hole_in_svg'] and after['hole_in_dxf_circles'] == before['hole_in_dxf_circles'] + 1)
        return {'edit': 'add a 60 mm grommet hole to TOP via POST /components/TOP/features', 'http': r.status_code,
                'before': before, 'after': after, 'pass': ok}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    print(json.dumps(run(), indent=1))
