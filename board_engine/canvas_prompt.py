"""
Project-aware design specification and external-AI prompt for the AI Design Canvas.

Everything quoted in the spec is read from the engine at runtime (TOL, LIMITS, ID_RE, the material and
fastener catalogues, joint/connection types, joinery modes) so the prompt can never drift from the code.
The bundled example is compiled by the test-suite and must produce zero errors.
"""
import json

from .canvas import CONNECTION_TYPES, FORMAT
from .manufacturing import FASTENERS, MATERIALS
from .model import DEFAULT_MATERIAL, FASTENER_KINDS, ID_RE, JOINERY_MODES, LIMITS, MATERIAL_TYPES
from .validation import TOL

# A complete, valid study table (1200 x 600 x 750, 18 mm plywood, glue-free tab & slot)
EXAMPLE = {
    "format": FORMAT,
    "product": {"name": "Modern Study Table", "description": "Glue-free plywood desk with a modesty panel and a shelf.",
                "overall": {"length": 1200, "height": 750, "depth": 600}},
    "material": {"name": "Birch plywood 18 mm", "type": "plywood", "thickness": 18, "clearance": 0.2},
    "joinery": "interlocking",
    "boards": [
        {"id": "TOP", "name": "Table top", "group": "Top", "position": [0, 732, 0], "size": [1200, 18, 600], "grain": "x"},
        {"id": "LEG-L", "name": "Left leg panel", "group": "Legs", "position": [50, 0, 20], "size": [18, 732, 560],
         "openings": [{"id": "cable", "kind": "hole", "shape": "circle", "center": [59, 600, 300], "diameter": 40}]},
        {"id": "LEG-R", "name": "Right leg panel", "group": "Legs", "position": [1132, 0, 20], "size": [18, 732, 560]},
        {"id": "MODESTY", "name": "Modesty panel", "group": "Frame", "position": [68, 432, 480], "size": [1064, 300, 18]},
        {"id": "SHELF", "name": "Lower shelf", "group": "Shelves", "position": [68, 150, 60], "size": [1064, 18, 400]}
    ],
    "connections": [
        {"id": "LEG-L-TOP", "type": "tab_slot", "board": "LEG-L", "into": "TOP", "tabs": 2},
        {"id": "LEG-R-TOP", "type": "tab_slot", "board": "LEG-R", "into": "TOP", "tabs": 2},
        {"id": "MOD-TOP", "type": "tab_slot", "board": "MODESTY", "into": "TOP", "tabs": 3},
        {"id": "MOD-L", "type": "tab_slot", "board": "MODESTY", "into": "LEG-L", "tabs": 1},
        {"id": "MOD-R", "type": "tab_slot", "board": "MODESTY", "into": "LEG-R", "tabs": 1},
        {"id": "SHELF-L", "type": "tab_slot", "board": "SHELF", "into": "LEG-L", "tabs": 2},
        {"id": "SHELF-R", "type": "tab_slot", "board": "SHELF", "into": "LEG-R", "tabs": 2}
    ]
}


def material_table():
    rows = []
    for k, m in MATERIALS.items():
        rows.append(f"| `{k}` | {', '.join(f'{t:g}' for t in m['thicknesses'])} | {m['kerf']:g} | "
                    f"{'yes' if m['grain'] else 'no'} | {m['min_part']:g} |")
    return '\n'.join(rows)


def spec_markdown():
    tol = TOL
    fasteners = ', '.join(f"`{k}` (Ø{v['diameter']:g} × {v['length']:g} mm)" for k, v in FASTENERS.items())
    return f"""# Board design format `{FORMAT}` — specification

You are writing a design for a flat-board product generator (CNC / laser cut boards, assembled into a 3D product).
The design is ONE JSON object. It is data only — never JavaScript, functions or expressions.

## Coordinate system and units
- Units: millimetres. World axes: **X = length (left → right)**, **Y = height (floor y = 0, up)**, **Z = depth (back → front)**.
- Every board is an **axis-aligned box**: `position` = its minimum corner [x, y, z], `size` = [size_x, size_y, size_z].
- A board is a flat panel: **exactly one** of `size` equals the board thickness — that axis is the board's normal.
  (Horizontal boards: size_y = thickness. Side panels: size_x = thickness. Back/front panels: size_z = thickness.)
- If two sizes equal the thickness (e.g. a square strip), add `"normal": "x"|"y"|"z"`.

## Top-level object
```
{{
  "format": "{FORMAT}",
  "product":  {{"name": str, "description": str, "overall": {{"length": mm, "height": mm, "depth": mm}}}},
  "material": {{"name": str, "type": one of {list(MATERIAL_TYPES)}, "thickness": mm, "kerf"?: mm, "clearance"?: mm}},
  "joinery":  one of {list(JOINERY_MODES)}   (optional; "interlocking" = glue-free, tab_slot only),
  "sheet"?:   {{"width": mm, "height": mm}}   (stock sheet; chosen automatically when omitted),
  "boards":   [board, ...],
  "connections": [connection, ...]
}}
```
- `thickness` between {LIMITS['min_thickness']:g} and {LIMITS['max_thickness']:g} mm. `clearance` = extra width of every slot over the
  tab board thickness (default {DEFAULT_MATERIAL['clearance']:g}); `kerf` defaults from the material catalogue below.
- At most {LIMITS['max_components']} boards; coordinates within ±{LIMITS['max_coord']:g} mm.

## board
```
{{"id": str, "name": str, "group": str, "position": [x, y, z], "size": [sx, sy, sz],
  "thickness"?: mm (default material.thickness), "material"?: {{"name", "type"}}, "grain"?: "x"|"y"|"z",
  "openings"?: [ {{"id", "kind": "opening"|"hole", "shape": "circle", "center": [x, y, z], "diameter": mm}}
               | {{"id", "kind": "opening"|"hole", "shape": "rect", "center": [x, y, z], "size": [a, b]}} ],
  "edge_banding"?: [{{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm}}]}}
```
- `id` must match `{ID_RE.pattern}` and be unique (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Keep ≥ {tol['min_edge_margin']:g} mm
  (recommended {tol['rec_edge_margin']:g} mm) of material between any opening/slot and an edge, and ≥ {tol['min_feature_spacing']:g} mm between cut-outs.

## connection
```
{{"id": str, "type": one of {list(CONNECTION_TYPES)}, "board": "<board A>", "into": "<board B>", ...}}
```
- `tab_slot` (glue-free): an END FACE of board A sits flat against the BROAD FACE of board B. The generator adds tabs on A and
  cuts matching slots through B. Options: `"tabs"`: 1..12, `"tab_width"`: mm, `"edge"`: "+y" etc. to pick A's edge.
  A must be inset from B's edges by at least B's slot margin ({tol['min_edge_margin']:g} mm, recommended ≥ {tol['rec_edge_margin']:g} mm; use ≥ the
  board thickness for furniture), and the contact must be longer than 2 × A's thickness plus the tab width.
- `butt` (needs `"joinery": "glue_allowed"`): A's end face against B's face, held by `"fasteners": {{"kind": one of
  {list(FASTENER_KINDS)}, "count"?: n}}`. Catalogue: {fasteners}.
- `hinge` (needs glue_allowed): `"board"` = door, `"into"` = carcass board it hangs on, `"edge"` = the door edge carrying
  the hinges ("+x"/"-x"/...), optional `"count"`, `"gap"`.
- `mitre` (needs glue_allowed): `"edge"` on A and `"into_edge"` on B (directions), optional `"bevel": true`.
- Every board must be connected (directly or through others) to the rest of the product.

## Geometry rules the generator validates (violations are compile errors)
1. **Touching, not overlapping:** for every connection A's end face must lie exactly on B's face (|gap| ≤ {tol['contact']:g} mm).
   Account for board thickness: e.g. leg height = overall height − top thickness; a shelf between two sides is
   (inner width) = overall width − 2 × side thickness long.
2. **No overlaps:** boards may not occupy the same space anywhere (tabs inside their slots are fine).
3. **No unintended gaps:** a board meant to sit on/against another must touch it.
4. Square to each other: every board is axis aligned; tabs insert perpendicular to the receiving face.
5. Every board must fit on one stock sheet; standard thicknesses are preferred (table below).

## Material catalogue (type | standard thicknesses mm | kerf mm | grain | minimum part mm)
| type | thicknesses | kerf | grain | min part |
|---|---|---|---|---|
{material_table()}

## Output format
Return **one** fenced ```json code block containing only the design object — no comments outside it, no prose inside it.

## Complete valid example (study table, glue-free)
```json
{json.dumps(EXAMPLE, indent=2)}
```
"""


def build_prompt(title, requirements='', material=None, thickness=None, joinery=None):
    title = (title or '').strip() or 'Board product'
    req = (requirements or '').strip()
    extra = []
    if material:
        extra.append(f'- Material type: {material}')
    if thickness:
        extra.append(f'- Board thickness: {thickness} mm')
    if joinery:
        extra.append(f"- Joinery: {joinery} ({'glue-free tab & slot only' if joinery == 'interlocking' else 'screws / dowels / hinges allowed'})")
    req_block = '\n'.join(filter(None, [req, *extra])) or '- Choose sensible standard dimensions for this product.'
    return f"""You are an expert furniture / product designer and CAD engineer.

TASK: Design the product below as a flat-board design in the exact JSON format specified further down.
It will be pasted into a board design generator that compiles it, renders it in 3D, validates every joint,
gap and overlap, nests the boards on stock sheets and produces cutting files. Invented fields are ignored and
invalid geometry is rejected, so follow the specification exactly.

PRODUCT: {title}

REQUIREMENTS:
{req_block}

INSTRUCTIONS:
1. Decide the boards (panels) the product needs and give each a unique, readable id.
2. Compute every position and size explicitly in millimetres — no formulas, variables or expressions in the JSON.
3. Account for board thickness everywhere so boards touch exactly and never overlap.
4. Inset boards that tab into another board by at least the board thickness from that board's edges.
5. Define a connection for every place two boards meet, so the whole product is connected.
6. Use only the fields, types and values listed in the specification; do not invent functions or fields.
7. Check overall dimensions against the requirements before answering.
8. Return ONLY one ```json code block with the complete design.

{spec_markdown()}

HOW THIS WILL BE USED: the user pastes your JSON into the "AI Design Canvas" of their board generator and clicks
Compile. The generator reports any error with the board id and an exact correction, so precise dimensions matter.
"""
