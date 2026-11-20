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
from .validation import HINGE, NEAR_MISS as NEAR, TOL

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

# Complex cuts: curved / pitched profiles, shaped openings, engravings and a roof tilted 35 deg (6 mm plywood)
COMPLEX_EXAMPLE = {
    "format": FORMAT,
    "product": {
        "name": "Gabled cottage",
        "description": "Glue-free cottage: pitched gables, 35 deg roof, arched door",
        "overall": {
            "length": 239.6,
            "height": 230.9,
            "depth": 190
        }
    },
    "material": {
        "name": "Birch plywood 6 mm",
        "type": "plywood",
        "thickness": 6
    },
    "boards": [
        {
            "id": "FLOOR",
            "name": "Floor",
            "group": "Base",
            "position": [
                -10,
                0,
                -10
            ],
            "size": [
                220,
                6,
                180
            ],
            "profile": {
                "shape": "rect",
                "center": [
                    110,
                    90
                ],
                "width": 220,
                "height": 180,
                "corner_radius": 12
            }
        },
        {
            "id": "GABLE-B",
            "name": "Back gable",
            "group": "Walls",
            "position": [
                0,
                6,
                0
            ],
            "size": [
                200,
                220.02,
                6
            ],
            "profile": {
                "shape": "polygon",
                "points": [
                    [
                        0,
                        0
                    ],
                    [
                        200,
                        0
                    ],
                    [
                        200,
                        150
                    ],
                    [
                        100,
                        220.02
                    ],
                    [
                        0,
                        150
                    ]
                ]
            },
            "openings": [
                {
                    "id": "heart",
                    "kind": "opening",
                    "shape": "path",
                    "center": [
                        100,
                        165,
                        3
                    ],
                    "start": [
                        0,
                        -14
                    ],
                    "segments": [
                        {
                            "line": [
                                16,
                                2
                            ]
                        },
                        {
                            "arc": {
                                "to": [
                                    0,
                                    10
                                ],
                                "radius": 9,
                                "large": True
                            }
                        },
                        {
                            "arc": {
                                "to": [
                                    -16,
                                    2
                                ],
                                "radius": 9,
                                "large": True
                            }
                        }
                    ]
                }
            ]
        },
        {
            "id": "GABLE-F",
            "name": "Front gable",
            "group": "Walls",
            "position": [
                0,
                6,
                154
            ],
            "size": [
                200,
                220.02,
                6
            ],
            "profile": {
                "shape": "polygon",
                "points": [
                    [
                        0,
                        0
                    ],
                    [
                        200,
                        0
                    ],
                    [
                        200,
                        150
                    ],
                    [
                        100,
                        220.02
                    ],
                    [
                        0,
                        150
                    ]
                ]
            },
            "openings": [
                {
                    "id": "door",
                    "kind": "opening",
                    "shape": "arch",
                    "center": [
                        100,
                        62,
                        157
                    ],
                    "size": [
                        50,
                        80
                    ]
                },
                {
                    "id": "window",
                    "kind": "opening",
                    "shape": "circle",
                    "center": [
                        155,
                        120,
                        157
                    ],
                    "diameter": 30
                },
                {
                    "id": "vent",
                    "kind": "opening",
                    "shape": "regular_polygon",
                    "center": [
                        100,
                        175,
                        157
                    ],
                    "sides": 6,
                    "diameter": 24
                }
            ],
            "engravings": [
                {
                    "id": "name",
                    "kind": "engrave",
                    "depth": 0.5,
                    "points": [
                        [
                            60,
                            135
                        ],
                        [
                            140,
                            135
                        ]
                    ]
                }
            ]
        },
        {
            "id": "SIDE-L",
            "name": "Left wall",
            "group": "Walls",
            "position": [
                10,
                6,
                6
            ],
            "size": [
                6,
                150,
                148
            ],
            "openings": [
                {
                    "id": "win-l",
                    "kind": "opening",
                    "shape": "rect",
                    "center": [
                        13,
                        90,
                        80
                    ],
                    "size": [
                        40,
                        50
                    ],
                    "corner_radius": 8
                }
            ]
        },
        {
            "id": "SIDE-R",
            "name": "Right wall",
            "group": "Walls",
            "position": [
                184,
                6,
                6
            ],
            "size": [
                6,
                150,
                148
            ],
            "engravings": [
                {
                    "id": "planter",
                    "kind": "pocket",
                    "depth": 2,
                    "shape": "rect",
                    "center": [
                        74,
                        40
                    ],
                    "width": 60,
                    "height": 20,
                    "corner_radius": 4
                }
            ]
        },
        {
            "id": "ROOF-L",
            "name": "Roof left",
            "group": "Roof",
            "position": [
                -20,
                156,
                -15
            ],
            "size": [
                142.0775,
                6,
                190
            ],
            "rotate": {
                "axis": "z",
                "angle": 35,
                "pivot": [
                    0,
                    156,
                    0
                ]
            }
        },
        {
            "id": "ROOF-R",
            "name": "Roof right",
            "group": "Roof",
            "position": [
                77.9225,
                156,
                -15
            ],
            "size": [
                142.0775,
                6,
                190
            ],
            "rotate": {
                "axis": "z",
                "angle": -35,
                "pivot": [
                    200,
                    156,
                    0
                ]
            }
        }
    ],
    "connections": [
        {
            "id": "gb-floor",
            "type": "tab_slot",
            "board": "GABLE-B",
            "into": "FLOOR"
        },
        {
            "id": "gf-floor",
            "type": "tab_slot",
            "board": "GABLE-F",
            "into": "FLOOR"
        },
        {
            "id": "sl-floor",
            "type": "tab_slot",
            "board": "SIDE-L",
            "into": "FLOOR"
        },
        {
            "id": "sr-floor",
            "type": "tab_slot",
            "board": "SIDE-R",
            "into": "FLOOR"
        },
        {
            "id": "sl-gb",
            "type": "tab_slot",
            "board": "SIDE-L",
            "into": "GABLE-B"
        },
        {
            "id": "sl-gf",
            "type": "tab_slot",
            "board": "SIDE-L",
            "into": "GABLE-F"
        },
        {
            "id": "sr-gb",
            "type": "tab_slot",
            "board": "SIDE-R",
            "into": "GABLE-B"
        },
        {
            "id": "sr-gf",
            "type": "tab_slot",
            "board": "SIDE-R",
            "into": "GABLE-F"
        },
        {
            "id": "gb-roofl",
            "type": "tab_slot",
            "board": "GABLE-B",
            "into": "ROOF-L"
        },
        {
            "id": "gb-roofr",
            "type": "tab_slot",
            "board": "GABLE-B",
            "into": "ROOF-R"
        },
        {
            "id": "gf-roofl",
            "type": "tab_slot",
            "board": "GABLE-F",
            "into": "ROOF-L"
        },
        {
            "id": "gf-roofr",
            "type": "tab_slot",
            "board": "GABLE-F",
            "into": "ROOF-R"
        }
    ]
}

# Several glue-free structures in one product: finger-jointed box corners, an egg-crate of crossing dividers
# (cross_lap) and dividers tabbed into the base (6 mm plywood)
STRUCTURES_EXAMPLE = {
    "format": FORMAT,
    "product": {
        "name": "Desk organiser",
        "description": "Glue-free box with finger-jointed corners and an egg-crate of dividers",
        "overall": {
            "length": 300,
            "height": 100,
            "depth": 200
        }
    },
    "material": {
        "name": "Birch plywood 6 mm",
        "type": "plywood",
        "thickness": 6
    },
    "boards": [
        {
            "id": "BASE",
            "name": "Base",
            "group": "Box",
            "position": [
                0,
                0,
                0
            ],
            "size": [
                300,
                6,
                200
            ]
        },
        {
            "id": "FRONT",
            "name": "Front wall",
            "group": "Box",
            "position": [
                0,
                6,
                194
            ],
            "size": [
                300,
                94,
                6
            ]
        },
        {
            "id": "BACK",
            "name": "Back wall",
            "group": "Box",
            "position": [
                0,
                6,
                0
            ],
            "size": [
                300,
                94,
                6
            ]
        },
        {
            "id": "LEFT",
            "name": "Left wall",
            "group": "Box",
            "position": [
                0,
                6,
                6
            ],
            "size": [
                6,
                94,
                188
            ]
        },
        {
            "id": "RIGHT",
            "name": "Right wall",
            "group": "Box",
            "position": [
                294,
                6,
                6
            ],
            "size": [
                6,
                94,
                188
            ]
        },
        {
            "id": "DIV-X",
            "name": "Long divider",
            "group": "Dividers",
            "position": [
                10,
                6,
                97
            ],
            "size": [
                280,
                70,
                6
            ]
        },
        {
            "id": "DIV-Z1",
            "name": "Cross divider 1",
            "group": "Dividers",
            "position": [
                97,
                6,
                10
            ],
            "size": [
                6,
                70,
                180
            ]
        },
        {
            "id": "DIV-Z2",
            "name": "Cross divider 2",
            "group": "Dividers",
            "position": [
                197,
                6,
                10
            ],
            "size": [
                6,
                70,
                180
            ]
        }
    ],
    "connections": [
        {
            "id": "front-base",
            "type": "finger",
            "board": "FRONT",
            "into": "BASE"
        },
        {
            "id": "back-base",
            "type": "finger",
            "board": "BACK",
            "into": "BASE"
        },
        {
            "id": "left-base",
            "type": "finger",
            "board": "LEFT",
            "into": "BASE"
        },
        {
            "id": "right-base",
            "type": "finger",
            "board": "RIGHT",
            "into": "BASE"
        },
        {
            "id": "left-back",
            "type": "finger",
            "board": "LEFT",
            "into": "BACK"
        },
        {
            "id": "left-front",
            "type": "finger",
            "board": "LEFT",
            "into": "FRONT"
        },
        {
            "id": "right-back",
            "type": "finger",
            "board": "RIGHT",
            "into": "BACK"
        },
        {
            "id": "right-front",
            "type": "finger",
            "board": "RIGHT",
            "into": "FRONT"
        },
        {
            "id": "x-z1",
            "type": "cross_lap",
            "board": "DIV-X",
            "into": "DIV-Z1"
        },
        {
            "id": "x-z2",
            "type": "cross_lap",
            "board": "DIV-X",
            "into": "DIV-Z2"
        },
        {
            "id": "x-base",
            "type": "tab_slot",
            "board": "DIV-X",
            "into": "BASE"
        },
        {
            "id": "z1-base",
            "type": "tab_slot",
            "board": "DIV-Z1",
            "into": "BASE"
        },
        {
            "id": "z2-base",
            "type": "tab_slot",
            "board": "DIV-Z2",
            "into": "BASE"
        }
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
  "joinery":  one of {list(JOINERY_MODES)}   (optional; "interlocking" = glue-free: tab_slot, finger and cross_lap
              only; "glue_allowed" also permits butt, hinge and mitre. Derived from the connections when omitted),
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
  "edge_banding"?: [{{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm, "material"?: str}}],
  "profile"?: shape, "engravings"?: [...], "rotate"?: {{...}}   (see "Complex cuts and tilted boards")}}
```
- `id` must match `{ID_RE.pattern}` and be unique (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Openings and
  engravings may carry `"note"`: str (shown in the drawings). Keep ≥ {tol['min_edge_margin']:g} mm
  (recommended {tol['rec_edge_margin']:g} mm) of material between any opening/slot and an edge, and ≥ {tol['min_feature_spacing']:g} mm between cut-outs.

## Complex cuts and tilted boards (optional)
Face coordinates `[u, v]`: millimetres from the board box's **minimum corner**, along the board's two in-plane axes in
x, y, z order (a board with normal z uses u = x, v = y; normal y: u = x, v = z; normal x: u = y, v = z).
Shapes (used by `profile`, `openings` and `engravings`):
```
{{"shape": "rect", "center": [u, v], "width", "height", "corner_radius"?, "angle"?}}
{{"shape": "circle", "center", "diameter"}}            {{"shape": "ellipse", "center", "width", "height"}}
{{"shape": "arch", "center", "width", "height"}}       (straight sides, semicircular top; height ≥ width / 2)
{{"shape": "regular_polygon", "center", "sides": 3..64, "diameter", "rotation"?: deg}}
{{"shape": "polygon", "points": [[u, v], ...], "corner_radius"?}}
{{"shape": "path", "start": [u, v], "segments": [{{"line": [u, v]}}
    | {{"arc": {{"to": [u, v], "radius": mm, "large"?: bool, "clockwise"?: bool}}}}
    | {{"arc": {{"to": [u, v], "center": [u, v], "clockwise"?: bool}}}}], "corner_radius"?}}
```
- `"profile": shape` replaces the board's rectangular outline (pitched gable, arched top, curved side, L/U shape,
  rounded corners). It must stay inside the box `[0..size_u] × [0..size_v]`; the box is still the board's bounding box.
  A tab_slot connection needs a **straight** profile edge on the touching side of the box.
- Openings may use any shape: `"center"` stays a world point [x, y, z] and the shape's own coordinates are relative to
  it (`"size": [a, b]` sets width/height of rect, ellipse and arch). Rect openings also accept `"corner_radius"`.
- `"engravings": [{{"id", "kind": "engrave"|"pocket", "depth": mm, "points": [[u, v], ...], "closed"?: bool}}
  | {{"id", "kind", "depth", ...shape}}]` — machined into the face, never through (default depth: engrave 0.5 mm,
  pocket half the board). Engrave depth ≤ half the board;
  pockets keep the material's minimum remaining thickness under them. Must lie fully on the board, off any cut-out.
- `"rotate": {{"axis": "x"|"y"|"z", "angle": degrees, "pivot"?: [x, y, z]}}` tilts a board (roof panels, sloped backs,
  lecterns). It is applied **last**: `position`/`size`, profile, openings, engravings and `"edge"` directions all describe
  the board before rotating; `pivot` defaults to the box centre. Positive angles turn counter-clockwise looking down
  the axis (about z: +x turns towards +y).
- Tilted tab_slot / butt: a straight edge of board A must lie flat on a broad face of board B — e.g. a gable's sloped
  top edge under a roof panel tilted to exactly the same pitch (within 0.5°) — and touch it (|gap| ≤ {tol['contact']:g} mm).
  Tabs insert square to B's face. Two roof panels meeting at a ridge should each end where their lower faces meet
  (their end faces then only touch along the ridge line).

## connection
```
{{"id": str, "type": one of {list(CONNECTION_TYPES)}, "board": "<board A>", "into": "<board B>", ...}}
```
Board A is `"board"`, board B is `"into"`. Edge directions (`"+x"`, `"-y"`, …) name a side of the board's (unrotated) box.

**Glue-free joints** (allowed with `"joinery": "interlocking"`):
- `tab_slot` — T-junction: an END FACE of A sits flat on the BROAD FACE of B, **away from B's edges**. The generator adds
  tabs on A's edge and cuts matching slots through B (slot = A's thickness + `clearance`). Options:
  `"tabs"`: 1..12 (default one per ~250 mm of contact, max 6), `"tab_width"`: mm (default about half the tab spacing,
  at least max({tol['min_tab_width']:g} mm, A's thickness)), `"tab_depth"`: mm (default B's thickness = flush with B's far face; larger
  makes the tab stand proud on purpose), `"edge"`: which side of A carries the tabs (default: the side touching B).
  Across A's thickness, A must be inset from B's edges by ≥ {tol['min_edge_margin']:g} mm (recommended ≥ {tol['rec_edge_margin']:g} mm; use ≥ the board
  thickness for furniture) — at the edge it is a `finger` corner instead. Along the contact A may run right up to B's
  edges (a shelf can be as deep as the sides): tabs stay A's thickness away from both ends automatically, so the contact must be longer than
  2 × A's thickness + max({tol['min_tab_width']:g} mm, A's thickness).
- `finger` — box corner: A's end face sits on B's face **flush with one of B's edges** (within {tol['contact']:g} mm), e.g. walls
  meeting at a box corner or a wall standing on the edge of a base. Draw both as plain boxes that just meet (A ends at
  B's face); the generator cuts alternating fingers into both along the corner: A's fingers are B's thickness deep, B's
  notches are A's thickness deep and `clearance` wider. Options: `"fingers"`: odd count 3..41 (an even count is rounded up;
  default: fingers about 3 × the thicker board long, at least 10 mm), `"edge"`: A's side at the corner. Each finger must
  be at least max({tol['min_tab_width']:g} mm, half of A's thickness) long, or the corner is too short. Which board is
  `"board"` and which `"into"` does not matter (a reversed pair is swapped with a warning). Three boards meeting at one
  corner (e.g. side + top + back of a cabinet) are fine: give each pair its own finger connection; the overlapping cuts
  are resolved exactly.
- `cross_lap` — egg-crate / halving: two perpendicular boards drawn **passing through each other** (dividers in a grid).
  Each gets a notch half the crossing height deep and the other board's thickness + `clearance` wide, cut from opposite
  edges. One board must end at the top of the crossing and the other at its bottom (within {tol['contact']:g} mm), e.g. both the
  same height; each must stick out > {tol['min_edge_margin']:g} mm past the other's faces. The order of the two boards does not matter.
- `finger` and `cross_lap` boards must be plain rectangles (no `profile`, no `rotate`). Profiled or tilted boards join
  with `tab_slot`: e.g. inset the walls from a pitched gable's edges and tab them into its face (as in the cottage
  example), and tab the gables' sloped edges into the roof panels.

**Joints that need `"joinery": "glue_allowed"`:**
- `butt` — A's end face against B's face, glued and/or held by `"fasteners"`: `{{"kind": one of {list(FASTENER_KINDS)},
  "count"?: 1..20, "diameter"?: 2..20 mm, "length"?: 5..200 mm}}` or just the kind as a string (`"fasteners": "screw"`).
  Catalogue: {fasteners}.
- `hinge` — `"board"` = the door, `"into"` = the carcass board it hangs on, `"edge"` (required) = the door side that carries
  the hinges, optional `"count"`: 1..8 hinges, `"gap"`: 0..5 mm. Doors are **overlay** doors: draw the door in front of the
  carcass, its back face 0..`gap` mm (default {HINGE['default_gap']:g}) from the carcass front edges, covering the front edge of the board it
  hangs on (flush with that board's outer face; overhanging it is a warning). The door must be ≥
  {HINGE['cup_depth'] + HINGE['min_remaining']:g} mm thick for the {HINGE['cup_diameter']:g} mm hinge cups. Do not connect the door to anything else.
- `mitre` — corner where two edges meet: `"edge"` (side of A) and `"into_edge"` (side of B), both required. `"bevel"`
  defaults to **true** (both edges cut at half the corner angle, saw / CNC only); set `"bevel": false` for a plain corner.
  Optional `"fasteners"` as for butt.

One valid line per type:
```
{{"id": "SIDE-TOP",  "type": "tab_slot",  "board": "SIDE-L", "into": "TOP", "tabs": 2}}
{{"id": "BOX-CORN",  "type": "finger",    "board": "LEFT",   "into": "BACK", "fingers": 5}}
{{"id": "GRID-1",    "type": "cross_lap", "board": "DIV-X",  "into": "DIV-Z1"}}
{{"id": "SHELF-FIX", "type": "butt",      "board": "SHELF",  "into": "SIDE-L", "fasteners": {{"kind": "confirmat", "count": 2}}}}
{{"id": "DOOR-HNG",  "type": "hinge",     "board": "DOOR",   "into": "SIDE-R", "edge": "+x", "count": 2, "gap": 2}}
{{"id": "FRAME-MT",  "type": "mitre",     "board": "RAIL",   "into": "STILE", "edge": "-x", "into_edge": "+y", "bevel": true}}
```
- Every board must be connected (directly or through others) to the rest of the product.
- Choosing the joint: end face on a face away from the edges → `tab_slot`; at the edge (corner) → `finger`; boards
  crossing → `cross_lap`. Back panels: either recess the back inside the carcass (its edges tab into the sides, top and
  bottom: `tab_slot`), or make it full size behind the carcass with the sides, top and bottom ending on its face flush
  with its edges (`finger` at each of its edges). A `tab_slot` written for a corner or a crossing is converted automatically (with a warning).
- `"connections": "auto"` (or leaving it out) infers every connection from where boards touch or cross; with a list,
  `"auto_connect": true` adds the ones you missed. Listing them yourself gives control over tabs and edges.
- Use the exact keys `"board"` / `"into"`, exact type names and exact board ids: near-misses are accepted but reported.

## Geometry rules the generator validates (violations are compile errors)
1. **Touching, not overlapping:** for every connection A's end face must lie exactly on B's face (|gap| ≤ {tol['contact']:g} mm).
   Account for board thickness: e.g. leg height = overall height − top thickness; a shelf between two sides is
   (inner width) = overall width − 2 × side thickness long.
2. **No overlaps:** boards may not occupy the same space anywhere (tabs inside their slots are fine).
3. **No unintended gaps:** a board meant to sit on/against another must touch it. Faces of unconnected boards that
   come within {NEAR:g} mm of each other without touching are reported as a likely mistake (NEAR_MISS_GAP).
   Slots are cut {DEFAULT_MATERIAL['clearance']:g} mm (material `clearance`) wider than the tab board; more than
   {tol['slot_loose']:g} mm of extra play is rejected as a rattling joint.
4. Square to each other: boards are axis aligned unless they use `rotate`; tabs insert perpendicular to the receiving face.
5. Every board must fit on one stock sheet; standard thicknesses are preferred (table below).

## Material catalogue (type | standard thicknesses mm | kerf mm | grain | minimum part mm)
| type | thicknesses | kerf | grain | min part |
|---|---|---|---|---|
{material_table()}

## Native engine format (advanced)
The canvas also accepts the engine's own design JSON (top-level `"components"` + `"joints"` instead of `"boards"`):
local 2D outlines with `arcs`, features (`rect` / `circle` / `polygon`), `marks`, tabs by edge index and placements with
Euler XYZ rotation. It is what the Studio and the REST API use; prefer `{FORMAT}` for new designs. Its joint types are `tab_slot`, `finger`,
`cross_lap`, `edge_butt`, `edge_mitre`, `face_lap` and `hinge` (`a`, `b`, plus `tab` for tab_slot and `a_edge` / `b_edge`
edge indices for the edge joints).

## Output format
Return **one** fenced ```json code block containing only the design object — no comments outside it, no prose inside it.

## Complete valid example (study table, glue-free)
```json
{json.dumps(EXAMPLE, indent=2)}
```

## Complete valid example with complex cuts (gabled cottage: pitched profiles, arched door, heart, 35° roof)
```json
{json.dumps(COMPLEX_EXAMPLE, indent=2)}
```

## Complete valid example with several structures (desk organiser: finger corners, egg-crate, tabs)
```json
{json.dumps(STRUCTURES_EXAMPLE, indent=2)}
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
4. Inset boards that tab into another board by at least the board thickness from that board's edges; where two
   boards meet at an edge (box corner) use "finger", and boards that cross each other use "cross_lap".
   For curved or angled parts use a "profile" / shaped openings; tilt roof or sloped panels with "rotate".
5. Define a connection for every place two boards meet, so the whole product is connected.
6. Use only the fields, types and values listed in the specification; do not invent functions or fields.
7. Check overall dimensions against the requirements before answering.
8. Return ONLY one ```json code block with the complete design.

{spec_markdown()}

HOW THIS WILL BE USED: the user pastes your JSON into the "AI Design Canvas" of their board generator and clicks
Compile. The generator reports any error with the board id and an exact correction, so precise dimensions matter.
"""
