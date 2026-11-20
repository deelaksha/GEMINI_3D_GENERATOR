"""Machine-readable API contract and LLM tool definitions served at /api/v1 and /api/v1/tools."""

_VEC2 = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2}
_VEC3 = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3}
FEATURE = {'type': 'object', 'required': ['id', 'kind', 'shape', 'center'], 'properties': {
    'id': {'type': 'string'}, 'kind': {'enum': ['slot', 'hole', 'opening']},
    'shape': {'enum': ['rect', 'circle']}, 'center': _VEC2, 'width': {'type': 'number'},
    'height': {'type': 'number'}, 'angle': {'type': 'number', 'description': 'degrees'},
    'diameter': {'type': 'number'}, 'note': {'type': 'string'}}}
TAB = {'type': 'object', 'required': ['id', 'edge', 'offset', 'width', 'depth'], 'properties': {
    'id': {'type': 'string'}, 'edge': {'type': 'integer', 'description': 'index into the CCW base outline'},
    'offset': {'type': 'number', 'description': 'mm from edge start to tab centre'},
    'width': {'type': 'number'}, 'depth': {'type': 'number', 'description': 'usually the receiver thickness'}}}
COMPONENT = {'type': 'object', 'required': ['id', 'outline'], 'properties': {
    'id': {'type': 'string'}, 'name': {'type': 'string'}, 'group': {'type': 'string'},
    'thickness': {'type': 'number'}, 'color': {'type': 'string'},
    'grain_locked': {'type': 'boolean', 'description': 'nesting may not rotate this part'},
    'outline': {'type': 'array', 'items': _VEC2, 'description': 'CCW polygon in local mm (plate lies in local XY)'},
    'features': {'type': 'array', 'items': FEATURE}, 'tabs': {'type': 'array', 'items': TAB},
    'placement': {'type': 'object', 'properties': {'position': _VEC3, 'rotation': {
        **_VEC3, 'description': 'degrees, Euler XYZ (THREE.js order)'}}}}}
JOINT = {'type': 'object', 'required': ['id', 'type', 'a', 'b'], 'properties': {
    'id': {'type': 'string'}, 'type': {'enum': ['tab_slot', 'edge_butt', 'edge_mitre', 'face_lap']},
    'a': {'type': 'string', 'description': 'tab_slot: part with the tab; edge_*: part whose edge mates'},
    'b': {'type': 'string', 'description': 'receiving part'},
    'tab': {'type': 'string'}, 'slot': {'type': 'string', 'description': 'optional; found or generated otherwise'},
    'a_edge': {'type': 'integer'}, 'b_edge': {'type': 'integer'}}}


def _tool(name, desc, method, path, props=None, required=()):
    return {'name': name, 'description': desc, 'http': {'method': method, 'path': path},
            'input_schema': {'type': 'object', 'properties': props or {}, 'required': list(required)}}


_D = {'design_id': {'type': 'string'}}
TOOLS = [
    _tool('list_designs', 'List designs.', 'GET', '/api/v1/designs'),
    _tool('get_design', 'Full design JSON (components, joints) and a validation summary.', 'GET',
          '/api/v1/designs/{design_id}', _D, ['design_id']),
    _tool('list_components', 'All components with dimensions, edges (indices, world coordinates), tabs and '
                             'features. Use edge indices for tabs and edge joints.', 'GET',
          '/api/v1/designs/{design_id}/components', _D, ['design_id']),
    _tool('get_model3d', 'World matrices, bounds and per-component state (error/joined/cut).', 'GET',
          '/api/v1/designs/{design_id}/model3d', _D, ['design_id']),
    _tool('validate_design', 'Run full 2D + joint + 3D interference validation. Returns structured issues with '
                             'codes, components, locations, and suggestions (e.g. translate deltas).', 'POST',
          '/api/v1/designs/{design_id}/validate', _D, ['design_id']),
    _tool('add_component', 'Add a board component (validated; rejected if its 2D profile is invalid or a duplicate).',
          'POST', '/api/v1/designs/{design_id}/components', dict(_D, component=COMPONENT), ['design_id', 'component']),
    _tool('update_component', 'Patch a component (outline, features, tabs, placement, thickness...). Rejected if '
                              'it breaks joined connections unless detach_broken_joints=true.', 'PATCH',
          '/api/v1/designs/{design_id}/components/{component_id}',
          dict(_D, component_id={'type': 'string'}, patch={'type': 'object'},
               detach_broken_joints={'type': 'boolean'}), ['design_id', 'component_id', 'patch']),
    _tool('translate_component', 'Move a component by [dx, dy, dz] mm (apply suggestion.delta from issues).', 'POST',
          '/api/v1/designs/{design_id}/components/{component_id}/translate',
          dict(_D, component_id={'type': 'string'}, delta=_VEC3), ['design_id', 'component_id', 'delta']),
    _tool('add_feature', 'Add a slot / hole / opening to a component.', 'POST',
          '/api/v1/designs/{design_id}/components/{component_id}/features',
          dict(_D, component_id={'type': 'string'}, feature=FEATURE), ['design_id', 'component_id', 'feature']),
    _tool('add_tab', 'Add a tab (tenon) on an outline edge.', 'POST',
          '/api/v1/designs/{design_id}/components/{component_id}/tabs',
          dict(_D, component_id={'type': 'string'}, tab=TAB), ['design_id', 'component_id', 'tab']),
    _tool('check_joint', 'Dry-run: evaluate a joint without changing anything. Returns fits (bool), issues and safe repairs.',
          'POST', '/api/v1/designs/{design_id}/joints/check', dict(_D, joint=JOINT), ['design_id', 'joint']),
    _tool('join', 'Join two components. Validated; missing/wrongly sized slots are generated only when '
                  'auto_repair=true; gaps, overlaps, bad orientation or intentional openings reject the join.',
          'POST', '/api/v1/designs/{design_id}/joints',
          dict(_D, joint=JOINT, auto_repair={'type': 'boolean'}), ['design_id', 'joint']),
    _tool('unjoin', 'Remove a joint (and the slots it generated).', 'DELETE',
          '/api/v1/designs/{design_id}/joints/{joint_id}', dict(_D, joint_id={'type': 'string'}),
          ['design_id', 'joint_id']),
    _tool('apply_operations', 'Atomic batch of operations (all-or-nothing): add_component, update_component, '
                              'translate, delete_component, add_feature, remove_feature, add_tab, remove_tab, '
                              'join, unjoin, set_material, apply_fix, auto_fix.', 'POST', '/api/v1/designs/{design_id}/operations',
          dict(_D, operations={'type': 'array', 'items': {'type': 'object'}},
               expected_revision={'type': 'integer'}), ['design_id', 'operations']),
    _tool('list_fixes', 'Deterministic fixes the engine can apply (gap/penetration/misalignment moves, slot '
                        'repairs, re-joins) and problems that need a design decision.', 'GET',
          '/api/v1/designs/{design_id}/fixes', _D, ['design_id']),
    _tool('apply_fix', 'Apply one planned fix by fix_id (re-validated; refused if it would add errors or break '
                       'other joints).', 'POST', '/api/v1/designs/{design_id}/fixes/apply',
          dict(_D, fix_id={'type': 'string'}), ['design_id', 'fix_id']),
    _tool('auto_fix', 'Apply every safely fixable correction repeatedly until none remain; returns steps and '
                      'what still needs a decision.', 'POST', '/api/v1/designs/{design_id}/fixes/auto',
          dict(_D, max_steps={'type': 'integer'}), ['design_id']),
    _tool('get_layout2d', 'Nest parts on sheets and return cutting paths + material statistics.', 'GET',
          '/api/v1/designs/{design_id}/layout2d', dict(_D, preset={'type': 'string'}), ['design_id']),
]

CONTRACT = {
    'name': 'PuzzleCore Board Design API',
    'version': '1.0',
    'conventions': {
        'units': 'millimetres', 'world': 'right-handed, +Y up',
        'component_local': 'plate in local XY, thickness along local Z centred on 0',
        'rotation': 'degrees, Euler XYZ (matrix = Rx*Ry*Rz, same as THREE.Euler default)',
        'outline_winding': 'counter-clockwise (clockwise input is reversed and reported)',
        'feature_kinds': {'slot': 'receives a tab; must be used by a joint',
                          'hole': 'functional hole, never modified',
                          'opening': 'intentional design opening; never filled, joints may not land in it'},
    },
    'auth': {'api_key': 'Authorization: Bearer <key> (or X-API-Key)',
             'roles': {'viewer': 'read, validate, check, export', 'editor': '+ modify designs', 'admin': '+ delete'},
             'browser': 'studio session cookie + X-Board-Client: studio header'},
    'envelope': {'success': {'ok': True, 'revision': 'int', 'result': '...', 'validation': '...'},
                 'error': {'ok': False, 'error': {'status': 'code', 'message': 'text', 'issues': '[...]'}}},
    'http_status': {'400': 'schema error', '401': 'unauthenticated', '403': 'role too low', '404': 'not found',
                    '409': 'revision conflict / not ready for production', '422': 'rejected by validation',
                    '429': 'rate limited'},
    'concurrency': "send expected_revision in mutation bodies to reject stale writes (409)",
    'endpoints': [
        'GET  /api/v1/', 'GET  /api/v1/tools', 'GET  /api/v1/whoami', 'GET  /api/v1/sheet-presets',
        'GET  /api/v1/designs', 'POST /api/v1/designs', 'POST /api/v1/designs/examples/boat',
        'GET  /api/v1/designs/{id}', 'DELETE /api/v1/designs/{id}', 'GET  /api/v1/designs/{id}/history',
        'POST /api/v1/designs/{id}/validate', 'GET  /api/v1/designs/{id}/model3d',
        'PUT  /api/v1/designs/{id}/material', 'POST /api/v1/designs/{id}/operations',
        'GET  /api/v1/designs/{id}/components', 'POST /api/v1/designs/{id}/components',
        'GET  /api/v1/designs/{id}/components/{cid}', 'PATCH /api/v1/designs/{id}/components/{cid}',
        'DELETE /api/v1/designs/{id}/components/{cid}?cascade=1',
        'POST /api/v1/designs/{id}/components/{cid}/translate',
        'POST /api/v1/designs/{id}/components/{cid}/features', 'DELETE /api/v1/designs/{id}/components/{cid}/features/{fid}',
        'POST /api/v1/designs/{id}/components/{cid}/tabs', 'DELETE /api/v1/designs/{id}/components/{cid}/tabs/{tid}',
        'GET  /api/v1/designs/{id}/joints', 'POST /api/v1/designs/{id}/joints', 'POST /api/v1/designs/{id}/joints/check',
        'DELETE /api/v1/designs/{id}/joints/{jid}',
        'GET  /api/v1/designs/{id}/fixes', 'POST /api/v1/designs/{id}/fixes/apply', 'POST /api/v1/designs/{id}/fixes/auto',
        'GET  /api/v1/designs/{id}/layout2d?preset=A3&margin=10&spacing=5&rotation=orthogonal&kerf=1',
        'GET  /api/v1/designs/{id}/export/pdf|svg|dxf?sheet=1&preset=A3&paper=A4&kerf=1&force=0',
    ],
    'docs': '/docs/board-api.md',
}
