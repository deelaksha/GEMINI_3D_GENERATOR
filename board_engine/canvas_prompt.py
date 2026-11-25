"""
Project-aware design specification and external-AI prompt for the AI Design Canvas.

Everything quoted in the spec is read from the engine at runtime (TOL, LIMITS, ID_RE, the material and
fastener catalogues, joint/connection types, joinery modes) so the prompt can never drift from the code.
The bundled example is compiled by the test-suite and must produce zero errors.
"""
import json

from .canvas import CONNECTION_TYPES, FORMAT, pretty_json
from .manufacturing import FASTENERS, MATERIALS
from .model import DEFAULT_MATERIAL, FASTENER_KINDS, ID_RE, JOINERY_MODES, LIMITS, MATERIAL_TYPES, MOUNTINGS
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
            "length": 240,
            "height": 231,
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
                220,
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
                        220
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
                220,
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
                        220
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
                142,
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
                78,
                156,
                -15
            ],
            "size": [
                142,
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
- **INTEGER DIMENSIONS RULE**: Because millimetres are small units (1mm, 2mm), all board sizes (`size`: [sx, sy, sz]), positions (`position`: [x, y, z]), and overall dimensions (`product.overall`) MUST be **integer numbers** (whole numbers like `30`, `38`, `150`, `60`, `12`), NEVER floating-point fractions (avoid `30.27`, `38.41`). The only numbers with decimals are material `thickness` (e.g. `1.0`, `2.0`, `3.0`) and manufacturing clearance (e.g. `0.1`).
- Every board is an **axis-aligned box**: `position` = its minimum corner [x, y, z], `size` = [size_x, size_y, size_z].
- A board is a flat panel: **exactly one** of `size` equals the board thickness — that axis is the board's normal.
  (Horizontal boards: size_y = thickness. Side panels: size_x = thickness. Back/front panels: size_z = thickness.)
- If two sizes equal the thickness (e.g. a square strip), add `"normal": "x"|"y"|"z"`.

## Top-level object
```
{{
  "format": "{FORMAT}",
  "product":  {{"name": str, "description": str, "overall": {{"length": mm, "height": mm, "depth": mm}},
               "mounting"?: one of {list(MOUNTINGS)} (default "floor"; "wall" = screwed to the wall behind it, z = 0 side)}},
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
- No fixed limit on the number of boards (very large designs take longer to check); coordinates within
  ±{LIMITS['max_coord']:g} mm.

## board
```
{{"id": str, "name": str, "group": str (sub-assembly, e.g. "Carcass", "Drawer 1", "Door"), "position": [x, y, z], "size": [sx, sy, sz],
  "thickness"?: mm (default material.thickness), "material"?: {{"name", "type"}}, "grain"?: "x"|"y"|"z",
  "openings"?: [ {{"id", "kind": "opening"|"hole", "shape": "circle", "center": [x, y, z], "diameter": mm}}
               | {{"id", "kind": "opening"|"hole", "shape": "rect", "center": [x, y, z], "size": [a, b]}} ],
  "edge_banding"?: [{{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm, "material"?: str}}],
  "profile"?: shape, "engravings"?: [...], "rotate"?: {{...}}   (see "Complex cuts and tilted boards")}}
```
- `id` must match `{ID_RE.pattern}`, be unique and at most 24 characters (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- `group` names the sub-assembly a board belongs to (product → group → board). Give every drawer, door, module or
  lid its own group so the parts list and assembly steps follow the product's structure.
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Openings and
  engravings may carry `"note"`: str (shown in the drawings). Keep ≥ {tol['min_edge_margin']:g} mm
  (recommended {tol['rec_edge_margin']:g} mm) of material between any opening/slot and an edge, and ≥ {tol['min_feature_spacing']:g} mm between cut-outs.
  Every opening and hole must be wider than the material's kerf (table below): at least twice the kerf is safe.

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
  Engraved text: `{{"kind": "engrave", "text": "Max 120 chars", "position": [u, v], "height": mm, "align"?: "left"|"center"|"right"}}`
  — single-stroke letters (capitals, digits, common punctuation) with the baseline starting at `position`; `height` is
  the capital height (each character is about `height` wide). Raster images (`"kind": "image"`, `"src": data URI`,
  `"position"`, `"size"`) are added by the user in the app; never write them yourself.
- `"living_hinge": {{"from": [u, v], "to": [u, v], "lines_along": "u"|"v", "spacing"?: mm, "cut"?: mm, "bridge"?: mm}}`
  (or a list) — a laser kerf-bending pattern: staggered through-cuts filling that face rectangle so the board can be
  bent across the cuts (rounded box corners, lamp shades). `lines_along` is the face axis the cuts run along (the bend
  axis). Defaults: spacing half the thickness, 20 mm cuts, bridges = thickness. Keep it at least one thickness inside
  the board edges. The board stays flat in this design (bending is not simulated): model the flat panel.
- `"repeat": {{"count": 2 or more, "step": [dx, dy, dz]}}` on a board builds an array of copies `"<id>-1"` .. `"<id>-n"`
  (shelves, slats, fins, ribs), each moved by `step` from the previous. A connection naming the board applies to every
  copy; two repeated boards with the same count connect copy by copy. Refer to a single copy by its generated id.
- `"mirror": {{"axis": "x"|"y"|"z", "at": mm}}` on a board also builds its mirror image `"<id>-M"` across the plane
  axis = at (left/right sides, symmetric gables). Profiles, openings, engravings and hinges are mirrored; text stays
  readable. Its connections are mirrored automatically: never write connections to `"<id>-M"` yourself.
- Top level `"assemblies": [{{"id", "boards": [...], "connections": [...]}}]` with `"instances": [{{"assembly", "id",
  "offset": [x, y, z], "repeat"?, "mirror"?}}]` reuses a sub-assembly (drawers, identical modules, legs): every instance
  gets copies of the assembly's boards named `"<instance id>-<board id>"`, moved by `offset`, with its internal
  connections; connect instance boards to the rest by those names under the top-level `"connections"`.
- Top level `"plan": {{"assemblies": [...], "steps": [...], "checks": [...], "reference"?: [...]}}` is your design plan,
  written before `"boards"` ("reference": what attached reference images show); the compiler ignores it.
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
- `mitre` — corner where two edges meet: `"edge"` (side of A) and `"into_edge"` (side of B), both required.
  **Draw each board up to the other board's mid-plane** (not to the outside corner): e.g. an 18 mm side
  `"position": [0, 0, 0], "size": [18, 141, 200]` and a top `"position": [9, 132, 0], "size": [291, 18, 200]` meet
  in a mitre with `"edge": "+y"` on the side and `"into_edge": "-x"` on the top. Drawn to the outside corner the two
  edges do not coincide and the joint is rejected. `"bevel"`
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

- Fasteners (`butt` / `mitre`): the screw, confirmat or dowel goes through B's face into A's **edge**, so A's edge must
  leave ≥ {min(v['edge_wall'] for v in MATERIALS.values() if v['edge_wall']):g}–{max(v['edge_wall'] for v in MATERIALS.values() if v['edge_wall']):g} mm of material each side of the bore (no fasteners into the edge of 6 mm boards or of hardboard /
  cardboard) and the fastener must be long enough to engage A after passing through B. Where two butt joints meet at
  the same corner their fasteners collide: stagger them with `"end"` (distance of the first/last fastener from the
  contact ends) or use a tab_slot / finger joint for one of them. Thin back panels are better as `tab_slot` / `finger`.
- Two boards must never tab into the same board at the same place from opposite sides (e.g. shelves on both sides
  of a centre divider, or a leg below and a riser above the same top): their tabs would need the same through-slot.
  Offset them by at least 60 mm (or 4 × the board thickness, whichever is larger).

### Joint names
Only the types above exist. A requested "dovetail" or "box joint" is made as a straight `finger` joint; "mortise and
tenon", "T-joint" and "interlocking" are a through `tab_slot`; "halving" / "cross lap" / "egg-crate" is `cross_lap`
(the word "lap" alone also means `cross_lap`); "screwed" / "dowelled" is `butt` with `"fasteners"`. Dado, rabbet
(rebate), blind mortise, sliding dovetail and knock-down fittings (cam locks) are **not available**: use `tab_slot` or
`finger`, or a `butt` with fasteners, and say so in the description.

## What this generator cannot build (do not attempt; use the alternative)
- Boards joined face to face (laminations, a guitar neck glued on a body, a tray hanging parallel under a table top):
  no connection joins two parallel faces. Join them through perpendicular boards instead (hangers, cleats, a frame).
- Boards meeting at an angle other than 90°, except (a) a tilted board resting on an edge cut to exactly its pitch
  (roof on a gable) and (b) `mitre`. A side tilted outwards cannot stand on a flat bottom; keep such sides vertical.
- Round or bent parts: dowels, axles, rods, wheels on axles, curved or kerf-bent panels. For a purchased dowel or axle,
  add a `"hole"` opening where it passes and leave the rod itself out of the design.
- Moving parts other than hinged doors: drawers on runners, sliding trays, wheels, folding mechanisms. Draw a drawer as
  a fixed box standing on its runner board; draw a folding product in its open position.

## Support and stability (checked)
- The product is ONE connected structure (checked): every board touches at least one other board and is joined to the
  main assembly by a chain of connections. Errors: ISOLATED_BOARD (touches nothing, floats in the air), DISCONNECTED
  (a group of boards apart from the main assembly), NOT_JOINED (touches the assembly but has no connection). The only
  exception is a flat board lying loose on top (a lift-off lid or tray), which is a warning.
- Every board must be held: joined to the product (directly or through others), or **resting on top of** a held board
  (a lift-off lid, a drawer standing on its runner, a stacked module). A board held by nothing is an error.
- Sizes written in the requirements ("length 1200 mm", "80 cm wide", "1200 x 600 x 750 mm" = length x depth x height)
  are checked against the built design (REQUIREMENT_MISMATCH).
- Every board must be ATTACHED by a connection that actually works, or it is an UNATTACHED_BOARD error (it would
  fall off). A tab_slot needs an EDGE of "board" lying on the broad FACE of "into": two boards lying flat on each other
  (both with their thickness along the same axis) cannot be joined; stand small parts (fittings, bollards, benches,
  funnels, hatches) upright on the face they sit on. The whole joining edge must lie inside the outline of "into". Two
  slots in one board must be >= 2 × thickness apart: never put a part exactly above / below another part that joins
  the same board from the other side, and keep repeated parts clear of the other joints in that board.
- The assembled model is also inspected by eye-like checks (warnings): VISIBLE_GAP (a 0.5-10 mm slit inside one
  structure), UNJOINED_CONTACT (a board resting on another with no connection), MISALIGNED (edges almost flush, off by
  0.5-5 mm), OFF_CENTRE (overhangs nearly but not exactly equal), MISMATCHED_PAIR (twin legs / sides / shelves that
  differ by 0.5-5 mm), UNEVEN_SPACING and ASYMMETRIC. Make edges exactly flush or clearly offset (>= 5 mm), twins
  exactly equal, symmetric parts exactly symmetric, and connect every board that rests on another.
- A floor-standing product must not tip over when empty: its centre of mass must lie inside its floor footprint.
  A horizontal board held on one side only (a cantilever) is reported. For shelves fixed to a wall set
  `"product": {{"mounting": "wall"}}` and give the product a back rail or back panel at z = 0.
- These checks are geometric only; they do not prove strength under load.

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
{pretty_json(COMPLEX_EXAMPLE)}
```

## Complete valid example with several structures (desk organiser: finger corners, egg-crate, tabs)
```json
{pretty_json(STRUCTURES_EXAMPLE)}
```
"""


# Every prompt's reply is pasted straight into the compiler, so each one states the same output contract at the start
# and repeats it as its last line (where chat models look last).
OUTPUT_CONTRACT = """OUTPUT CONTRACT (strict — your reply is pasted straight into a compiler, not read by a person):
- Reply with exactly ONE ```json code block that contains the COMPLETE design, and nothing else.
- No text before or after the code block: no greeting, explanation, summary, list of changes, notes or questions.
- Output every board and every connection in full. Never abbreviate: no "...", no "// unchanged", no "rest stays the
  same", no placeholders, no references to an earlier answer.
- Strict JSON: double quotes, no comments, no trailing commas, no formulas or expressions — only literal numbers.
- Anything you want to tell the user (assumptions, what changed, what could not be done) goes ONLY in the
  "product.description" string.
- Never ask a question or refuse: if something cannot be met exactly, return the best complete design and explain the
  limitation in "product.description"."""

FINAL_REMINDER = 'FINAL REMINDER: your entire reply is one ```json code block with the complete design — no other text.'

INTEGER_RULE = ('All sizes, positions, product.overall values and profile / opening / engraving coordinates are whole '
                'millimetres (integers such as 30, 38, 150 — never 30.27). Only the material thickness and clearance '
                'may have decimals.')


COLOR_SPEC = """## Colours (colouring is ON)
Give every board a colour. Write `"color"` on the board: one colour for the whole board, or
`{"front": ..., "back": ..., "edges": ...}` for different faces (front = the face on the +thickness side; a face left out
stays natural board). `"material": {..., "color": ...}` sets the default for boards without their own.
Accepted formats: "#rrggbb", "#rgb", "rgb(r, g, b)", "hsl(h, s%, l%)", CSS colour names ("tomato", "navy",
"forestgreen", ...), or [r, g, b] (0..255).
Rules: choose a coherent palette of 2-6 colours that suits the product; boards with the same role share a colour and
different roles get clearly different, unique colours (a roof, the walls, a door, the trim); paint only the visible
side with a front/back pair where that is how the product would be finished; keep every board's colour unchanged when
you change or fix the design unless asked to recolour."""


IMAGE_SPEC = """## Reference images (attached to this message)
The image(s) attached to this message ARE the specification. Reproduce the product they show on this platform as
exactly as flat boards allow — its shape, proportions, parts and details — not a generic product of the same kind.
1. STUDY FIRST: before anything else, look at every image and write what you see into "plan" as
   "reference": [...] — the overall silhouette, every visible part (count them), where each sits, how parts meet,
   openings, windows and cut-outs, surface lines, text and logos, and colours. If several images are attached, they
   show the same product from different sides or in detail: combine them.
2. SIZE AND PROPORTION: take absolute sizes from the requirements. Where none are given, estimate the real-world size
   from what the product is and record it as an assumption. Take every proportion from the image: measure ratios
   (height / length, part width / overall width, positions as fractions of the whole) and apply them to the chosen
   size. Write the main ratios you measured in "plan.reference".
3. MATCH EVERY VISIBLE PART: the same number of parts, at the same places, with the same proportions. Outlines and
   curves → "profile" (polygon points or arcs traced from the image); holes, windows and gaps → "openings"; surface
   lines, panels, text and logos → "engravings"; repeated parts → "repeat"; left / right twins → "mirror".
4. WHAT FLAT BOARDS CANNOT MAKE (curved surfaces, round solids, bends): build the closest flat-board version — stacked
   layers, ribs with a skin of panels, faceted panels, "living_hinge" for gentle bends — and say what was
   approximated in "product.description".
5. PARTS THE IMAGE DOES NOT SHOW (inside, back, underside): add only what the structure needs to stand and join
   (glue-free), keeping the visible look unchanged.
6. COMPARE BEFORE ANSWERING: view your design from the front, the side and the top and check it against the image:
   is every visible part present, in the right place, with the right proportions and outline? Fix any difference."""


def _coloring(machine):
    return bool(machine and machine.get('coloring'))


def build_prompt(title, requirements='', material=None, thickness=None, joinery=None, machine=None, images=False):
    """images: the user will attach reference image(s) to this prompt in their AI chat; they become the
    specification (see IMAGE_SPEC)."""
    title = (title or '').strip() or ('The product shown in the attached image(s)' if images else 'Board product')
    req = (requirements or '').strip()
    extra = []
    if images:
        extra.append('- Reproduce the product in the attached reference image(s) exactly (see "Reference images" below); '
                     'where the text and the image disagree on a size, follow the text, on anything else the image.')
    if _coloring(machine):
        extra.append('- Colour every board (see "Colours" below): a coherent palette, unique colours for different roles.')
    if machine and 'kerf' in machine:
        # nesting keeps a 10 mm margin all round and a 14 mm strip for the printed sheet label
        w, h = machine['sheet']['width'] - 20, machine['sheet']['height'] - 34
        extra.append(f"- Cut on a laser cutter with a {machine['sheet']['width']:g} × {machine['sheet']['height']:g} mm bed and a "
                     f"{machine['kerf']:g} mm kerf: write \"kerf\": {machine['kerf']:g} in \"material\".")
        extra.append(f"- Every board's flat cut shape (its two largest sizes, tabs included) must fit within "
                     f"{max(w, h):g} × {min(w, h):g} mm. Split anything larger into several boards joined together.")
    if material:
        extra.append(f'- Material type: {material}')
    if thickness:
        extra.append(f'- Board thickness: {thickness} mm')
    if joinery:
        extra.append(f"- Joinery: {joinery} ({'glue-free tab & slot only' if joinery == 'interlocking' else 'screws / dowels / hinges allowed'})")
    req_block = '\n'.join(filter(None, [req, *extra])) or '- Choose sensible standard dimensions for this product.'
    return f"""You are an expert furniture / product designer and CAD engineer working as the design step of an automated
board-design pipeline.

TASK: Design the product below as a flat-board design in the exact JSON format `{FORMAT}` specified further down.
It is compiled automatically: rendered in 3D, every joint, gap and overlap validated, boards nested on stock sheets
and cutting files produced. Invented fields are ignored and invalid geometry is rejected, so follow the
specification exactly.

{OUTPUT_CONTRACT}

PRODUCT: {title}

REQUIREMENTS:
{req_block}

INSTRUCTIONS (follow every one):
1. Read the requirements. If a dimension is missing, choose a standard value for this product; if two requirements
   conflict, follow the explicit number. Write every such decision in "product.description" as "Assumptions: …".
   If the product needs something listed under "What this generator cannot build", build the closest supported
   version and say what was left out in the description. Do not ask questions — decide and record the assumption.
2. PLAN FIRST: write a top-level "plan" before "boards": the sub-assemblies, the build steps and the checks you will
   run. Then decompose the product into every board it needs (nothing implied, nothing missing). Give each a short
   unique id (at most 24 characters) and put the boards of each sub-assembly in the same "group". For repeated or
   symmetric parts use "repeat", "mirror" and "assemblies"/"instances" instead of listing every copy.
3. Compute every position and size explicitly in millimetres — no formulas, variables or expressions in the JSON.
   CRITICAL INTEGER RULE: {INTEGER_RULE}
4. Account for board thickness everywhere so boards touch exactly and never overlap
   (leg height = overall height − top thickness; inner width = overall width − 2 × side thickness).
5. Choose each joint from the geometry: end face on a face away from the edges → "tab_slot" (inset at least the board
   thickness from the receiving board's edges); at an edge (box corner) → "finger"; boards crossing → "cross_lap".
   For curved or angled parts use a "profile" / shaped openings; tilt roof or sloped panels with "rotate".
6. Never let two boards tab into the same board at the same place from opposite sides: offset them by ≥ 60 mm.
7. Make every hole and opening at least twice the material's kerf across.
8. Define a connection for every place two boards meet, so every board is held (loose lids / drawers rest on top of
   a held board).
9. Use only the fields, types and values listed in the specification; do not invent functions or fields.
10. SELF-CHECK before answering and correct the JSON if any answer is "no":
    a. Does exactly one of each board's three sizes equal its thickness?
    b. For every connection, does the end face of "board" lie exactly on a face of "into" (gap 0)?
    c. Do the boards' combined extents equal product.overall in length, height and depth?
    d. Is any space occupied by two boards (other than boards joined with cross_lap)?
    e. Are all ids unique and at most 24 characters? Is every board held?
    e2. Walk the connections from the base board: is EVERY board reached? Does every board touch another one?
        Is every small part (fittings, details on a deck or panel) standing with an EDGE on that face, never lying
        flat on it, with its slot >= 2 × thickness from every other slot in that board?
    e3. Do the overall sizes match every size stated in the requirements?
    f. Is every size and position a whole number of millimetres?{chr(10) + '    g. Does every board have a colour, with one colour per role?' if _coloring(machine) else ''}{chr(10) + '    h. Does the design match the attached image(s) from the front, side and top: every visible part, its place, proportions and outline?' if images else ''}
11. Return ONLY one ```json code block with the complete design; write number arrays on one line ([x, y, z]).

{spec_markdown()}
{(chr(10) + COLOR_SPEC + chr(10)) if _coloring(machine) else ''}{(chr(10) + IMAGE_SPEC + chr(10)) if images else ''}
{FINAL_REMINDER}
"""


def _whole(v):
    """Numbers that are whole written as integers (1132, not 1132.0), as the prompts require."""
    if isinstance(v, list):
        return [_whole(x) for x in v]
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _fix_text(fix):
    """A suggested fix as the AI should apply it: its title plus the exact values the compiler computed."""
    parts = []
    for e in (fix.get('edits') or [])[:3]:
        v = e.get('value')
        if isinstance(v, list) and any(isinstance(x, dict) for x in v):
            continue                       # a whole rewritten list: the title says what to do
        where = f'boards["{e["board"]}"].' if e.get('board') else ''
        parts.append(f'{where}{e["field"]} = {json.dumps(_whole(v))}')
    return fix['title'] + (f" — set {'; '.join(parts)}" if parts else '')


def _problem_lines(diagnostics, limit=60):
    """One line per problem; repeats of the same code on the same board / connection are merged (with a count) so
    the AI sees every distinct problem instead of a truncated list."""
    groups = {}
    first = ('UNATTACHED_BOARD', 'ISOLATED_BOARD', 'DISCONNECTED', 'NOT_JOINED')    # loose parts lead the list
    for d in sorted(diagnostics, key=lambda d: d.get('code') not in first):
        if d.get('severity') not in ('error', 'warning'):
            continue
        key = (d['severity'], d['code'], d.get('board') or (d.get('components') or [None])[0], d.get('connection'))
        groups.setdefault(key, []).append(d)
    rows = []
    for (sev, code, board, conn), ds in groups.items():
        d = ds[0]
        where = ', '.join(x for x in (f"board {board}" if board else '', f"connection {conn}" if conn else '',
                                      f"line {d['line']}" if d.get('line') else '') if x)
        fix = (d.get('fixes') or [None])[0]
        rows.append(f"- [{sev.upper()} {code}] {d['message']}" + (f" ({where})" if where else '')
                    + (f" (and {len(ds) - 1} more like this)" if len(ds) > 1 else '')
                    + (f" Suggested fix: {_fix_text(fix)}." if fix and fix.get('kind') != 'repair_json' else '')
                    + (f" Calculation: {'; '.join(d['calc'])}." if d.get('calc') else ''))
    more = len(rows) - limit
    return '\n'.join(rows[:limit] + ([f'- … and {more} more distinct problems'] if more > 0 else [])) or '- (none)'


def build_repair_prompt(source, diagnostics, blocking=(), machine=None):
    """Follow-up prompt: hand the generator's diagnostics (and the production blockers: fasteners, stock, cut paths)
    back to the AI and ask for a minimal correction, returned as code only."""
    seen = {d['message'] for d in diagnostics}
    diagnostics = list(diagnostics) + [dict(b, severity='error') for b in blocking if b.get('message') not in seen]
    syntax = any(d.get('code') == 'JSON_SYNTAX' for d in diagnostics)
    floats = sum(1 for d in diagnostics if d.get('code') == 'NON_INTEGER_DIMENSION')
    return f"""You are the repair step of an automated board-design pipeline. The compiler checked the design below (format
`{FORMAT}`) and found the problems listed. Return the corrected design as code only.

{OUTPUT_CONTRACT}

REPAIR RULES (follow every one):
1. Fix every [ERROR]. Fix every [WARNING] too, unless the fix would change what the product is meant to be; then leave
   it and add one sentence about it to "product.description".
2. Where a problem gives a "Suggested fix", apply exactly those values — the compiler computed them.
3. Make the smallest change that fixes each problem: keep every other board, id, dimension and connection exactly as
   it is — same ids, same order, same names and groups. Do not add, remove or rename boards or connections unless a
   problem requires it.
4. When you move or resize a board, update the boards and connections that depend on it so every mating face still
   touches exactly (gap 0) and no two boards overlap.
5. Line numbers in the problems refer to YOUR PREVIOUS JSON below.
6. {INTEGER_RULE}{f" {floats} dimension(s) below break this rule: round each to the nearest whole millimetre and keep the boards that touch them touching." if floats else ''}
7. Every board reported as UNATTACHED_BOARD, ISOLATED_BOARD, DISCONNECTED or NOT_JOINED must be attached after your
   fix: give it a connection that works (an EDGE of it on the broad FACE of the other board, the whole joining edge
   inside that board's outline, its slot >= 2 × thickness from every other slot in that board) or remove the board.
   Apply the move the problem gives; it was checked against every other joint on that board.
{"8. The previous reply was not valid JSON: rewrite it as strict, complete JSON (every bracket closed, commas between items, double-quoted keys and strings) with the same content." + chr(10) if syntax else ''}
SELF-CHECK before answering: every problem below is resolved; each board has exactly one size equal to its
thickness; every connection's faces touch (gap 0); no two boards occupy the same space; ids are unique; all sizes and
positions are whole millimetres.

PROBLEMS:
{_problem_lines(diagnostics)}

YOUR PREVIOUS JSON:
```json
{(source or '').strip()}
```

SPECIFICATION (reference for every field and rule):
{spec_markdown()}
{(chr(10) + COLOR_SPEC + chr(10)) if _coloring(machine) else ''}
{FINAL_REMINDER}
"""


def build_integer_fix_prompt(source, non_integer_issues):
    """Follow-up prompt: the external AI updates ONLY the dimensions that have decimal fractions, to whole millimetres."""
    lines = []
    for issue in non_integer_issues:
        target = f'boards["{issue["board"]}"].{issue["field"]}' if issue.get('board') else issue.get('id') or issue.get('field')
        if 'value' in issue and 'suggested' in issue:
            lines.append(f"- {target}: {issue['value']:g} → {issue['suggested']:g}   ({issue.get('message', '')})")
        else:
            lines.append(f"- {issue.get('message', str(issue))}")
    problem_list = '\n'.join(lines) if lines else "- (no non-integer dimensions found)"
    return f"""You are the number-cleanup step of an automated board-design pipeline.
The values listed below do NOT meet the integer millimetre requirement because they contain decimal fractions.

{OUTPUT_CONTRACT}

VALUES TO CHANGE (current → required):
{problem_list}

RULES (follow every one):
1. Update the existing design ONLY for these specific dimensions: replace each listed value with the required whole
   number. Keep every other board, id, position, size and connection exactly as it is.
2. If rounding a size or position opens a gap or an overlap with a board it touches, move or resize that neighbouring
   board by the same whole-millimetre amount so the faces touch exactly again.
3. Update "product.overall" if the outer dimensions change.
4. {INTEGER_RULE}

CURRENT DESIGN:
```json
{(source or '').strip()}
```

{FINAL_REMINDER}
"""


def build_update_prompt(source, change, diagnostics=(), machine=None, images=False):
    """Follow-up prompt for an incremental change: modify only the affected boards of an existing design.
    images: the user attaches reference image(s) in their AI chat; the design is changed to match them."""
    change = (change or '').strip() or ('Make the design match the attached reference image(s) exactly.' if images else '')
    issues = [d for d in diagnostics if d.get('severity') == 'error']
    return f"""You are the change step of an automated board-design pipeline. Below is an existing, working design in the
`{FORMAT}` format. Apply the CHANGE REQUEST to it and return the updated design as code only.

{OUTPUT_CONTRACT}

CHANGE REQUEST:
{change}
{chr(10) + "REFERENCE IMAGES: the image(s) attached to this message show how the product must look after the change. "
 "Study them first, then change every board that differs from them (shape, proportions, parts, openings, engravings) "
 "and keep the rest. Rules 1-7 below still apply; see \"Reference images\" at the end." + chr(10) if images else ''}
RULES FOR THE UPDATE (follow every one):
1. Identify the boards and connections the change affects, including dependent ones (e.g. a wider product means
   longer tops, shelves and back panels, and moved side panels).
2. Change only those. Keep every unaffected board's id, position, size and every unaffected connection exactly as it
   is — do not rename, re-order or re-generate the rest of the design.
3. Recompute every dependent dimension explicitly (no formulas) so boards still touch exactly and never overlap.
   New boards get new unique ids (at most 24 characters) and a connection for every board they touch.
4. Update "product.overall" and the "Assumptions" in "product.description" if they change.
5. If the request is ambiguous or conflicts with the existing design, make the smallest reasonable interpretation
   and state it in "product.description".
6. {INTEGER_RULE}
7. SELF-CHECK before answering: each board has exactly one size equal to its thickness; every connection's faces touch
   (gap 0); no two boards occupy the same space; ids are unique; every board is held.
{chr(10) + "The current design still has these problems; fix them too:" + chr(10) + _problem_lines(issues) + chr(10) if issues else ''}
CURRENT DESIGN:
```json
{(source or '').strip()}
```

SPECIFICATION (reference for every field and rule):
{spec_markdown()}
{(chr(10) + COLOR_SPEC + chr(10)) if _coloring(machine) else ''}{(chr(10) + IMAGE_SPEC + chr(10)) if images else ''}
{FINAL_REMINDER}
"""
