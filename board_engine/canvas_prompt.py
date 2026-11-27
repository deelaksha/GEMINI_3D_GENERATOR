"""
Project-aware design specification and external-AI prompt for the AI Design Canvas.

Everything quoted in the spec is read from the engine at runtime (TOL, LIMITS, ID_RE, the material and
fastener catalogues, joint/connection types, joinery modes) so the prompt can never drift from the code.
The bundled example is compiled by the test-suite and must produce zero errors.
"""
import json
import math
import re

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


# The working method in practice: a reference clone with the plan filled in (scale, grid readings, inventory, datums,
# dimension chain, tick-off), the whole front silhouette as ONE traced panel with its gaps cut out, and depth layers.
ADVANCED_EXAMPLE = {
    "format": "board-design/v1",
    "plan": {
        "reference": [
            "scale: anchor = requested width 300 mm; real torii ~7.8 m wide -> model 1:26",
            "front view grid: pillars x 0.21-0.28 and 0.72-0.79, nuki y 0.63-0.69, kasagi tips y 0.94-1.00",
            "P1 pillars | front | 2 | round, vermilion | layer 0 + front piece for depth",
            "K1 kasagi | front | 1 | upswept lintel, black top | traced curve, 9 points per side",
            "N1 nuki, S1 shimaki, G1 gakuzuka | front | 1 each | in the frame plane"
        ],
        "datums": [
            "origin: x 0 left of base, y 0 base bottom, z 0 back",
            "base top y = 3",
            "frame plane z = 54..57, pillar fronts z = 57..66 (frame centred on the base: 54 + 3 + 54 = 111)",
            "pillar centre lines x = 70, 230 (symmetric about x = 150)",
            "nuki y = 123..135, shimaki y = 153..165",
            "chain x: 20 margin + 260 frame + 20 margin = 300"
        ],
        "concept": "Reference clone: one frame panel carries the whole front silhouette, front pieces give the pillars depth",
        "joints": [
            "FRAME: tabs into BASE from both pillar feet (the pillar fronts lock it: locked every way)",
            "PILLAR-L-F, PILLAR-R-F: tabs into BASE and into FRAME - two directions, locked every way"
        ],
        "audit": [
            "BASE: [0, 0, 0], size [300, 3, 54 + 3 + 54 = 111]",
            "FRAME: [margin 20, base top 3, frame plane 54] = [20, 3, 54], size [260, kasagi tip 193 - 3 = 190, 3]",
            "PILLAR-L-F: [pillar centre 70 - 2 = 68, 3, frame front 57], size [3, 110, 66 - 57 = 9]",
            "PILLAR-R-F: mirror about x = 150: 300 - 68 - 3 = 229 -> [229, 3, 57]",
            "bay-l: centre x (80 + 144) / 2 = 112, y (135 + 153) / 2 = 144, size [144 - 80 = 64, 153 - 135 = 18]",
            "bay-r: mirror of bay-l: x = 300 - 112 = 188"
        ],
        "assemblies": [
            "base",
            "frame panel",
            "pillar front pieces"
        ],
        "checks": [
            "P1 -> FRAME pillars, PILLAR-L-F, PILLAR-R-F",
            "K1 -> FRAME profile top edge",
            "N1, S1, G1 -> FRAME",
            "front projection: 6 / 6 elements within 2%, counts exact"
        ]
    },
    "product": {
        "name": "Torii gate",
        "overall": {
            "length": 300,
            "height": 193,
            "depth": 111
        },
        "description": "Assumptions: 1:26 scale clone of a standard myojin torii; round pillars given depth by a front piece each."
    },
    "material": {
        "type": "plywood",
        "thickness": 3,
        "kerf": 0.15
    },
    "boards": [
        {
            "id": "BASE",
            "group": "Base",
            "position": [0, 0, 0],
            "size": [300, 3, 111],
            "color": "#b9b4a8"
        },
        {
            "id": "FRAME",
            "group": "Gate",
            "position": [20, 3, 54],
            "size": [260, 190, 3],
            "color": "#c3272b",
            "profile": {
                "shape": "polygon",
                "points": [
                    [40, 0],
                    [60, 0],
                    [60, 120],
                    [200, 120],
                    [200, 0],
                    [220, 0],
                    [220, 120],
                    [235, 120],
                    [235, 132],
                    [220, 132],
                    [220, 150],
                    [240, 150],
                    [240, 162],
                    [260, 178],
                    [260, 190],
                    [240, 182],
                    [200, 177],
                    [160, 175],
                    [130, 174],
                    [100, 175],
                    [60, 177],
                    [20, 182],
                    [0, 190],
                    [0, 178],
                    [20, 162],
                    [20, 150],
                    [40, 150],
                    [40, 132],
                    [25, 132],
                    [25, 120],
                    [40, 120]
                ]
            },
            "openings": [
                {
                    "id": "bay-l",
                    "kind": "opening",
                    "shape": "rect",
                    "center": [112, 144, 55],
                    "size": [64, 18]
                },
                {
                    "id": "bay-r",
                    "kind": "opening",
                    "shape": "rect",
                    "center": [188, 144, 55],
                    "size": [64, 18]
                }
            ]
        },
        {
            "id": "PILLAR-L-F",
            "group": "Gate",
            "position": [68, 3, 57],
            "size": [3, 110, 9],
            "color": "#c3272b"
        },
        {
            "id": "PILLAR-R-F",
            "group": "Gate",
            "position": [229, 3, 57],
            "size": [3, 110, 9],
            "color": "#c3272b"
        }
    ],
    "connections": [
        {
            "type": "tab_slot",
            "board": "FRAME",
            "into": "BASE"
        },
        {
            "type": "tab_slot",
            "board": "PILLAR-L-F",
            "into": "BASE"
        },
        {
            "type": "tab_slot",
            "board": "PILLAR-R-F",
            "into": "BASE"
        },
        {
            "type": "tab_slot",
            "board": "PILLAR-L-F",
            "into": "FRAME"
        },
        {
            "type": "tab_slot",
            "board": "PILLAR-R-F",
            "into": "FRAME"
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
  "connections": [connection, ...],
  "motions"?: [motion, ...]   (moving parts, see "Moving parts")
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
{{"shape": "gear", "center", "teeth": 6..100, "module": mm, "rotation"?: deg}}   (involute spur gear, see "Gears")
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
  axis = at (left/right sides, symmetric gables). Profiles, openings, engravings, hinges and tilts are mirrored; text
  stays readable. Its connections are mirrored automatically: never write connections to `"<id>-M"` yourself.
- Top level `"assemblies": [{{"id", "boards": [...], "connections": [...], "motions"?: [...]}}]` with `"instances":
  [{{"assembly", "id", "offset": [x, y, z], "flip"?, "rotate"?, "repeat"?, "mirror"?}}]` reuses a sub-assembly (seats,
  drawers, window bays, modules, legs): every instance gets copies of the assembly's boards named
  `"<instance id>-<board id>"`, with its internal connections and motions; connect instance boards to the rest by those
  names under the top-level `"connections"`. Design the assembly around its own origin [0, 0, 0]; each instance is
  flipped, then turned, then moved by `offset`:
  - `"flip": "x"|"y"|"z"` (or a list): a mirror-image copy in place (a left-hand version of a right-hand module).
  - `"rotate": {{"axis", "angle"}}` (or a list of steps): multiples of 90° are exact - every board stays square and
    every joint type works (seats facing a stage from all four sides: angles 0, 90, 180, 270 about y). Any other angle
    tilts the whole copy about its origin (a fan of seats around a circle); finger and cross_lap joints inside it cannot
    follow a tilt, so use tab_slot there. An assembly with motions can only be turned by multiples of 90°.
- Top level `"plan": {{"reference"?: [...], "datums"?: [...], "concept"?: str, "economy"?: str, "joints"?: [...], "audit"?: [...], "assemblies": [...], "steps": [...], "checks": [...],
  "reference"?: [...]}}` is your design plan, written before `"boards"` ("reference": what attached reference images
  show); the compiler ignores it.
- `"rotate": {{"axis": "x"|"y"|"z", "angle": degrees, "pivot"?: [x, y, z]}}` tilts a board (roof panels, sloped backs,
  lecterns). It is applied **last**: `position`/`size`, profile, openings, engravings and `"edge"` directions all describe
  the board before rotating; `pivot` defaults to the box centre. Positive angles turn counter-clockwise looking down
  the axis (about z: +x turns towards +y).
- A compound tilt is a LIST of 1-3 such steps applied in order, each about its own pivot (default: the board's centre
  at that moment): `"rotate": [{{"axis": "x", "angle": 28, "pivot": [...]}}, {{"axis": "z", "angle": 8, "pivot": [...]}}]`
  - a roof corner that lifts (flared eaves), a hip piece, a canted panel. Everything else about tilted boards applies.
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

## Fewer, smarter boards (consolidation) - visual detail is not piece count
Judge a design by realism, strength, function and ease of assembly - NOT by how many boards it has. Detail that lies
in one plane belongs in ONE board: its outline, its cut-out openings and its engravings carry the detail.
- A fence or railing = one panel per straight run: a top and bottom rail with the posts between them, the gaps as
  openings (a pointed or shaped picket top = the panel's polygon "profile"). Never 30 separate posts.
- A lattice / shoji window or a grille = one panel with a grid of openings; a decorative wall panel, border or
  frieze = one board with openings and engravings; repeated roof-edge ornaments = one strip per roof edge; a tree
  or bush = a few interlocking silhouette boards (cross_lap them for volume), not dozens of twigs.
- Write repeated cut-outs once: an opening with `"repeat": {{"count": n, "step": [dx, dy, dz]}}` (and
  `"rows": {{"count": m, "step": [dx, dy, dz]}}` for a grid) is cut n (x m) times, ids "<id>-1".. ("<id>-<row>-<n>").
- Keep separate only what must be: parts in another plane (real 3D depth - roof layers, overlapping tiers, bracket
  stacks), moving parts, different colours / materials / thickness, and a run too big for the stock board (split it
  into a few modules, joined to the structure - not into hundreds of pieces).
- The compiler consolidates for you as a safety net (`"consolidate"`, on by default; `false` only reports): flat
  boards (plain or shaped with a "profile" - pickets, arches, discs, silhouettes; not tilted, not gears) of one
  thickness, material and colour that lie in one plane and share an edge are cut as one board - their united
  outline, enclosed gaps as openings - and the connections between them are dropped (CONSOLIDATED, with the counts).
  A repeated board joins only as a whole; pieces meeting only at a point stay apart. Better: draw the panel yourself.
```jsonc
{{"id": "FENCE-N", "position": [0, 6, 0], "size": [400, 110, 6],
 "profile": {{"shape": "polygon", "points": [[0, 0], [400, 0], [400, 100], [390, 110], [380, 100], [10, 100], [0, 110]]}},
 "openings": [{{"id": "gap", "kind": "opening", "shape": "rect", "center": [30, 55, 3], "size": [24, 70],
               "repeat": {{"count": 12, "step": [31, 0, 0]}}}}]}}
```

## Moving parts (motions) - checked through their whole travel and animated in 3D
```
"motions": [
  {{"id": str, "type": "rotate", "boards": [ids that turn together], "on": board id, "axis": "x"|"y"|"z",
   "pivot": [x, y, z], "range": [from, to] (degrees), "axle"?: {{"diameter": mm}}}},
  {{"id": str, "type": "slide", "boards": [ids], "on": board id, "direction": "x"|"y"|"z", "range": [from, to] (mm)}}
]
```
- The design is drawn at position 0 of every motion (closed lid, drawer in); `range` must include where it goes. Angles
  turn counter-clockwise looking down the axis (as `rotate`); the pivot is a point on the turning line.
- The moving boards move rigidly together: join them to each other as usual, but NEVER fix them to a static board with
  tab_slot / finger / cross_lap / butt / mitre (they could not move - MOTION_LOCKED). A `hinge` connection may hold a
  moving board (needs "joinery": "glue_allowed"); otherwise the motion itself mounts the group on `"on"`.
- The group must touch its `"on"` board (it rests on it or turns on its axle). A slide runs along the contact - a
  drawer resting on a runner board (contact across y) slides along x or z - or straight off it: a lid or roof lifted
  off (`"direction": "y"`, `"range": [0, 120]`), a plug pulled out. Never into it.
- `"axle"`: the compiler cuts a dowel hole of that diameter through every board the pivot line passes square through
  (each must be thin along the axis, with the pivot inside it and room for the hole), and reports the dowel length:
  a real, glue-free pivot for turntables, wheels, swing arms, flaps and rotating signs.
- The compiler turns / slides the group every 5° (or about 1/48 of a slide) through the whole range and reports every
  board it would run into (MOTION_COLLISION) with the last clear position: put a lid's pivot on the OUTER edge it opens
  about and keep the range within what really clears.
- Running gap: every moving part needs at least 1 mm (2 mm is safer) to everything it passes except the board it rests
  or runs on - a drawer between its sides, a wheel beside a wall, a flap past a frame. Less is an error
  (MOTION_CLEARANCE: it would rub and bind), even when nothing overlaps. Draw moving parts that much smaller.
- A repeated / mirrored / instanced board may be named by its source id: every copy moves (all blades of a fan).
- A motion written inside an assembly is copied into every instance (its own ids, pivot and direction, turned and
  flipped with it): one animated door module, placed a hundred times, gives a hundred working doors.
- Nested motions: `"on"` may be a board that another motion moves - a jaw on a head, a head on a neck, a wing tip on a
  wing, each tail segment on the one before. The child rides on its parent and moves relative to it (pivot and axis
  written as drawn, at rest); every child is checked through its own travel, and carried along when its parent moves.
Mechanisms that work well in flat boards: a turntable (a round disk on a base, axis y, axle), a wheel on a wall
(round board thin along x, axis x, axle), a swinging flap or arm on a pin, a rotating sign or vane, a hinged lid, a
drawer or tray sliding on runners, a sliding panel between two rails.
```jsonc
{{"id": "spin", "type": "rotate", "boards": ["DISK", "DISK-RIM"], "on": "BASE", "axis": "y", "pivot": [150, 6, 150],
 "range": [0, 360], "axle": {{"diameter": 8}}}},
{{"id": "drawer", "type": "slide", "boards": ["DR-FRONT", "DR-BOTTOM", "DR-SIDE-L", "DR-SIDE-R", "DR-BACK"], "on": "RUNNER",
 "direction": "z", "range": [0, 250]}}
```

## Gears (gear trains, clocks, music boxes, kinetic sculptures)
A gear is a board whose `"profile"` is `{{"shape": "gear", "center": [u, v], "teeth": z, "module": m, "rotation"?: deg}}`:
pitch diameter = m x z, outside diameter = m x (z + 2); make the board's box exactly the outside diameter square with the
centre in its middle. Each gear turns on its own axle: a `rotate` motion whose `pivot` is the gear centre, `axis`
across the gear, with an `"axle"`. A gear that is turned by another one has `"driven_by": "<driver motion id>"` and no
`"range"`: it follows its driver at -z_driver / z_driven (the opposite way), and its travel is checked from that. Chains
(A drives B drives C) work; a belt or pulley pair without teeth gives `"ratio"` instead.
Two gears mesh only when (the compiler checks every one, with the calculation):
- the same `"module"`, both thin along the same axis and on the same level (one plane);
- centre distance = m x (z1 + z2) / 2 exactly (module 3, 20 and 30 teeth: 75 mm);
- the driven gear's `"rotation"` puts its gaps where the driver's teeth are. Write 0 if unsure: the compiler reports the
  exact value as a fix (GEAR_PHASE), and it never changes the ratio.
Gears stay gears when an instance is turned or flipped, so a reused gearbox module meshes in every copy.
```jsonc
{{"id": "G1", "position": [47, 6, 67], "size": [66, 6, 66], "profile": {{"shape": "gear", "center": [33, 33], "teeth": 20, "module": 3}}}},
{{"id": "G2", "position": [107, 6, 52], "size": [96, 6, 96], "profile": {{"shape": "gear", "center": [48, 48], "teeth": 30, "module": 3, "rotation": 6}}}},
"motions": [
  {{"id": "drive", "type": "rotate", "boards": ["G1"], "on": "BASE", "axis": "y", "pivot": [80, 6, 100], "range": [0, 360], "axle": {{"diameter": 6}}}},
  {{"id": "follow", "type": "rotate", "boards": ["G2"], "on": "BASE", "axis": "y", "pivot": [155, 6, 100], "driven_by": "drive", "axle": {{"diameter": 6}}}}
]
```

## Linkages: one crank drives everything (connecting rods, rockers, sliders)
A real mechanism has ONE input - a hand crank or a motor shaft - and every other movement is pushed by actual parts.
A motion driven through a connecting rod has `"driven_by": "<crank motion id>"` and, instead of a ratio, a `"link"`:
`{{"rod": "<rod board id>", "from": [x, y, z] (pin on the crank), "to": [x, y, z] (pin on this motion's boards),
"pin"?: {{"diameter": mm, default 4}}}}`. The rod is an ordinary board (a bar with a "polygon" or rounded profile) that
no motion lists; the compiler pins it at both ends (cuts the pin holes), solves the linkage exactly at every crank
position (the follower's travel comes from that, give it no "range") and animates crank, rod and follower together.
- Four-bar / crank-rocker (a wing flapping, a jaw, a leg swinging, a head nodding): the follower turns about the SAME
  axis as the crank. It works all the way round only when the crank is the shortest link and shortest + longest <=
  the other two (Grashof); otherwise the compiler reports where it locks (LINKAGE_JAM).
- Slider-crank (a piston, a pecking head, a pump): the follower slides across the crank's axis; its stroke is twice
  the crank radius when the rod points at the crank's axle.
- Build it in layers: frame, then crank and follower (both thin along the axis, on their axles), then the rod in the
  next layer so it passes over them. Every part of the mechanism is posed together through the whole cycle and any
  two that meet are reported (MOTION_COLLISION "Mechanism driven by ..."). A rod pushing almost along the arm it
  drives (transmission angle under 30°) is warned about: it would stall.
- Chain stages from one input: a gear driven by the crank, a rocker driven through a rod from that gear, a jaw riding
  on that rocker... (a cam: a disk crank with the rod's pin off centre is an eccentric).
```jsonc
{{"id": "BASE", "position": [0, 0, 0], "size": [420, 320, 6]}},
{{"id": "CRANK", "position": [70, 120, 6], "size": [60, 60, 6], "profile": {{"shape": "circle", "center": [30, 30], "diameter": 60}}}},
{{"id": "ARM", "position": [290, 140, 6], "size": [20, 90, 6]}},
{{"id": "ROD", "position": [106, 137, 12], "size": [208, 96, 6], "profile": {{"shape": "polygon", "points": [[7.6, 1.9], [206.2, 79.2], [200.4, 94.1], [1.8, 16.8]]}}}},
"motions": [
  {{"id": "crank", "type": "rotate", "boards": ["CRANK"], "on": "BASE", "axis": "z", "pivot": [100, 150, 6], "range": [0, 360], "axle": {{"diameter": 6}}}},
  {{"id": "flap", "type": "rotate", "boards": ["ARM"], "on": "BASE", "axis": "z", "pivot": [300, 150, 6], "axle": {{"diameter": 6}},
   "driven_by": "crank", "link": {{"rod": "ROD", "from": [120, 150, 12], "to": [300, 220, 12]}}}}
]
```

## What this generator cannot build (do not attempt; use the alternative)
- Boards joined face to face (laminations, a guitar neck glued on a body, a tray hanging parallel under a table top):
  no connection joins two parallel faces. Join them through perpendicular boards instead (hangers, cleats, a frame).
- Boards meeting at an angle other than 90°, except (a) a tilted board resting on an edge cut to exactly its pitch
  (roof on a gable) and (b) `mitre`. A side tilted outwards cannot stand on a flat bottom; keep such sides vertical.
- Round rods and bent panels as parts: a dowel or axle is not modelled (a motion's `"axle"` cuts its holes and the
  compiler gives its length); curved or kerf-bent panels stay flat. Round flat parts (wheels, disks) are fine.
- Springs, ratchets and cams with a shaped (non-round) lobe: not solved. Gears and belts link with `"driven_by"`
  (see "Gears"), cranks with rods with `"link"` (see "Linkages"); a rack can follow a gear with
  `"ratio": pi x module x teeth / 360` (mm per degree).

## Strength and retention (checked, from the geometry alone)
- Webs: no part may narrow below its own thickness (at least 3 mm, never more than 8 mm asked) anywhere a real piece
  could break off - a waist, a slender arm, the bridge between a cut-out and the edge or between two cut-outs
  (WEAK_SECTION). Pointed tips (teeth, horns, leaves, claws) are fine.
- What holds each part, with its neighbours in place: a tab only pulls straight out of its slot, a face stops a part
  moving into what it rests on. Best: LOCKED (blocked every way - tabs into boards on two different sides, a
  cross-lap). Fine: lifts straight off (its weight holds it). Info: held only by friction sideways
  (PART_HELD_BY_FRICTION - e.g. sides whose only joints are tabs coming INTO them can spread apart; add a back or
  rails with tabs into the sides, or tab the sides into the top). Warning: free downwards - its joints hold it only
  from above and it would drop out (PART_CAN_FALL_OUT); tab hanging parts in from above or sideways, or rest them on
  something.

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

## Detailed models (buildings, vehicles, scale models) — how to build them so they compile first time
A detailed model is many simple, well-joined parts (hundreds are fine; there is no part limit), organised by "group"
and numbered ids (RAF-F1, RAF-F2, ...). Build it in layers, each part standing on or locking into the layer below:
1. Ground board (the display base) -> raised floor / plinth (walls under a floor board, floor 5-6 mm wider all round)
   -> walls (plain rectangles, `finger` at the corners, `tab_slot` into the floor and up into a ceiling board)
   -> ceiling / eave soffit board (it overhangs the walls: the eaves) -> roof structure -> roof skin -> surface detail
   -> fittings -> surroundings (plants, yard items: each tabbed into the ground).
2. Sloped roofs: tilt the panels with `rotate` about the eave line (pivot on the lower face at the eave). Pick a pitch
   from a whole-number triangle so every length is whole millimetres: 8-15-17 (28.07 deg: run 15 -> rise 8, slope 17),
   3-4-5 (36.87 deg) or 5-12-13 (22.62 deg). Panels end where their lower faces meet (ridge, hips): cut hip panels as
   trapezoids / triangles with a polygon `profile`. Support them with vertical trusses standing on the ceiling whose
   `profile` top edges follow the panels' lower faces exactly; tab the trusses into the ceiling and into each panel.
3. Surface detail on a tilted panel (tile courses, battens, solar cells, planks): build each piece flat, standing on
   the panel's top face as if the panel were not tilted, then give it the SAME `rotate` (axis, angle, pivot - or the
   same list of steps) as the panel - it then stands square on the panel and `tab_slot` joins it.
   Flared / upswept roofs (temples, pagodas, gates): build the sweep from 2-3 bands of flat panels - steep near the
   ridge, shallower towards the eave - each band tilted to its own whole-number pitch. Support them on rafters whose
   `profile` top edge is a polyline with one straight segment per band at exactly that band's pitch, and tab each band
   into the rafters (a band never joins the next band: leave 1 mm between them). Lift the corners with corner pieces
   tilted by a list (the band's pitch, then a few degrees about the eave line), resting on a hip rafter whose top edge
   lies in that tilted plane. Split long courses into pieces (about 40 mm)
   with 1 mm gaps, and put gaps where trusses or other joints meet the panel so no two slots share a place.
4. Two colours on one wall (a painted band, a plinth stripe): a separate board standing on the floor in front of the
   wall, tabbed into the floor. Door / window frames: an opening in the wall plus a coloured lining board behind it
   with its own smaller openings (the frame, mullions, a grill); a dark inner wall further in makes openings read as
   a dark interior.
5. Nothing may hang: a part whose only joints are tabs pushing UP into a board above it falls out (HELD_FROM_ABOVE).
   Give it something to sit on - e.g. rafter ends under the eaves sit on a wall plate (a strip tabbed sideways into
   the wall) and tab up into the soffit - or tab it sideways into a wall.
6. Slots: keep slots in one board >= 2 x thickness apart and never at the same place from both faces; tabs into a
   wall must land on solid wall clear of its openings (tabs are spread evenly along the contact, one thickness in
   from each end - choose the board length and "tabs" so they miss the openings); small parts use small `tab_width`.
7. Texture and visibility: per-face `color`s (colouring on) with slightly varied shades for repeated parts,
   `engravings` for stone courses, planks and outlines, wavy `profile` tops for tile courses, dark undersides for
   eaves. Small parts are fine on a laser: write the laser kerf in "material" (e.g. "kerf": 0.15); with a kerf below
   1 mm the minimum part width is 3 mm instead of the router minimum in the table below.
8. Very large models (thousands of parts - a stadium, a village, a ship with every rib and plank): design a module
   once as an assembly (a seat row, a window bay, a truss, a house) and place it with "instances" (and their
   "repeat" / "mirror"); the compiler expands them, so the JSON stays short while the model has 5,000-10,000+ parts.
   Connect the modules to each other and to the base under the top-level "connections" by their expanded ids
   ("<instance id>-<board id>"). Turn and flip instances to face every way (quarter turns stay exact): one seat module
   fills all four sides of a stadium, one gallery bay runs round a courtyard.
Snippet (front roof slope, one truss, one tile piece - all whole millimetres, pitch 8-15-17, panel 3 mm):
```jsonc
{{"id": "R-F", "position": [30, 81, 141], "size": [300, 3, 102],
  "rotate": {{"axis": "x", "angle": 28.0725, "pivot": [30, 81, 243]}},
  "profile": {{"shape": "polygon", "points": [[0, 102], [300, 102], [210, 0], [90, 0]]}}}},
{{"id": "TRUSS-1", "position": [150, 81, 78], "size": [3, 48, 150],
  "profile": {{"shape": "polygon", "points": [[0, 0], [0, 150], [8, 150], [48, 75], [8, 0]]}}}},
{{"id": "TILE-F1", "position": [70, 84, 236], "size": [40, 4, 3],
  "rotate": {{"axis": "x", "angle": 28.0725, "pivot": [30, 81, 243]}},
  "profile": {{"shape": "polygon", "points": [[0, 0], [40, 0], [40, 3], [38, 4], [36, 3], [34, 4], [32, 3], [0, 3]]}}}}
```
(connections: TRUSS-1 -> CEILING, TRUSS-1 -> R-F, TILE-F1 -> R-F, all `tab_slot`; the truss's profile is [height,
depth] because it is thin along x: face coordinates follow the in-plane axes in x, y, z order.)

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
This first example only shows the syntax and is deliberately plain. The cottage example after it shows the least
shaping a finished design needs (profiles, arches, tilted roof); DESIGN QUALITY asks for more.
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

## Complete valid example of the working method (torii gate cloned from a reference)
How a finished answer looks: "plan" holds the scale calibration, grid readings, the counted inventory, the datums with
a dimension chain and the tick-off; the whole front silhouette (pillars, tie beam, plaque strut, lintels with the
upswept tips traced point by point) is ONE panel whose enclosed gaps are openings; front pieces give the pillars depth.
```json
{pretty_json(ADVANCED_EXAMPLE)}
```
"""


# Every prompt's reply is pasted straight into the compiler, so each one states the same output contract at the start
# and repeats it as its last line (where chat models look last).
OUTPUT_CONTRACT = """OUTPUT CONTRACT (strict — your reply is pasted straight into a compiler, not read by a person):
- Reply with exactly ONE ```json code block that contains the COMPLETE design, and nothing else.
- No text before or after the code block: no greeting, explanation, summary, list of changes, notes or questions.
- Output every board and every connection in full. Never abbreviate: no "...", no "// unchanged", no "rest stays the
  same", no placeholders, no references to an earlier answer.
- NO SIZE LIMIT: there is no maximum number of boards or lines. Never simplify or leave out visible detail to keep the
  answer short — a faithful model of a complex object often needs hundreds or thousands of boards. But detail that
  lies in one plane goes into ONE board's outline, openings and engravings (see "Fewer, smarter boards"). Keep it compact
  instead: write each board and each connection on ONE line, and use "repeat", "mirror" and "assemblies" /
  "instances" for repeated parts (one line can make a whole row of tiles, rafters or slats).
- MULTI-PART REPLIES: if the complete design will not fit in one reply, split it - never shorten it. Decide the number
  of parts N first (about 250 boards per part). Each reply is ONE ```json block: part 1 is
  {"part": {"index": 1, "of": N}, "format": ..., "plan": ..., "product": ..., "material": ..., "joinery": ...,
  "boards": [the first boards], "connections": [their connections]}; every later part k is
  {"part": {"index": k, "of": N}, "boards": [...], "connections": [...]}. End each reply after its code block; the
  user answers "continue" for the next part. Ids are unique across all parts; a connection may name boards of any
  part. The user pastes all parts together and the compiler merges them.
- Strict JSON: double quotes, no comments, no trailing commas, no formulas or expressions — only literal numbers.
- Anything you want to tell the user (assumptions, what changed, what could not be done) goes ONLY in the
  "product.description" string.
- Never ask a question or refuse: if something cannot be met exactly, return the best complete design and explain the
  limitation in "product.description"."""

FINAL_REMINDER = ('FINAL REMINDER: your entire reply is one ```json code block with the complete design (or, for a design '
                  'too large for one reply, the next part of it) — no other text, nothing simplified or left out.')

DESIGN_TEAM = """YOUR ROLE - a design team of five specialists working one after another inside this single reply (do the
work in your head; the only output is the JSON):
1. ANALYST - reads the product, the requirements (and any reference images) and lists every part, size and feature
   that must exist. With images this is the METROLOGIST: views, scale calibration, grid measurements, counted
   inventory and traced outlines (REFERENCE CLONING PROTOCOL). Writes "plan.reference".
2. DESIGNER - the creative director: rejects the obvious form, chooses a surprising but buildable concept with one
   signature feature, a style and motifs carried through every part, and decides where the curves, layers, openings,
   rhythm and detail go - richness from shape, not extra material (see DESIGN QUALITY). Writes "plan.concept" and
   "plan.economy".
3. ARCHITECT - splits the product into sub-assemblies and layers (base -> structure -> skin -> details -> fittings),
   fixes the overall size, the scale, the DATUMS (origin, levels, planes, centre lines - PRECISION PROTOCOL) and every
   board's role. Writes "plan.datums", "plan.assemblies" and "plan.steps".
4. JOINERY ENGINEER - places every board in whole millimetres computed from the datums with thickness accounted for,
   computes curves from their equations, chooses each joint from the geometry, keeps slots apart and tabs on solid
   material, makes every part sit or lock (nothing hangs). Writes "boards", "connections" and "motions".
5. INSPECTOR - checks the finished JSON against the SUCCESS CRITERIA, DESIGN QUALITY, the PRECISION PROTOCOL, the
   COMMON MISTAKES and the SELF-CHECK (with images: the projection check against every view) and has every problem
   fixed before handing over. Writes "plan.checks" (what was verified, with board ids and numbers).
Each specialist builds on the previous one's result without undoing it; when the Inspector finds a problem, the
specialist responsible fixes it before the reply is written."""

SUCCESS_CRITERIA = """SUCCESS CRITERIA (the compiler measures every one of these):
- 0 errors and 0 warnings; every connection joined;
- one connected structure: every board touches and is joined into it - nothing floats, nothing hangs on upward tabs;
- every requirement (size, count, feature) and every inventory item present at the right place and size;
- whole millimetres everywhere, a standard thickness, every part fits on a stock sheet."""

DESIGN_QUALITY = """DESIGN QUALITY (compiling is the minimum - the design must be creative AND economical; never a stack of boxes):
- Creative concept: do not build the first obvious form. Pick a buildable but surprising idea and give the product one
  signature feature someone would remember. Flat-board construction is good at: waffle / egg-crate frames, stacked
  contour slices (a curved form cut as a series of profiled ribs), radial ribs and fins, folding living-hinge skins,
  interlocking lattices, cantilevers and tiers, layered relief facades. Pick a style (art deco, Japanese joinery,
  streamlined, gothic, parametric, organic ...) and carry its motifs through every part. Write it in "plan.concept".
- Creative techniques (use several): exaggerate the signature feature slightly so it reads; contrast solid against
  lattice and plain against ornate; gradual rhythm (fins, ribs or slats that grow or turn step by step - computed
  sizes); a reveal (a lid, door or roof that opens to show a hidden interior or mechanism); a story (a small scene or
  vignette the object belongs to, only if it adds); negative space (the cut-outs draw the motif); layered depth so
  light and shadow model the form.
- Richness from shape, not from material: openings, lattices and shaped profiles remove material while adding
  detail; a ribbed skeleton or a thin skin over ribs replaces a solid block; never add a hidden or filler board.
- Silhouette: shape outlines with "profile" - arched or pitched tops, curved sides (path arcs), tapered legs, stepped
  or scalloped edges, rounded corners ("corner_radius"). Depth: 2-3 layers on visible faces (a frame or lining board
  with its own openings), recessed doors and windows, plinths, cornices and trims.
- Movement: bring the product to life with moving parts where they suit it - a lid that opens, a turning top or
  sign, a wheel, a swinging flap or arm, a sliding drawer or panel, a gear train turning a dial - declared in "motions" (see "Moving parts"): each is
  checked through its whole travel and animated in the 3D view. A static product is the dull default.
- Rhythm: fins, slats, ribs, columns, balusters and rafters as "repeat" arrays or assembly instances; "mirror" for
  symmetric halves; tilted planes ("rotate") and "living_hinge" for curves and angles; engraved lines, panels,
  planks, lettering and contrasting colours (colouring on) for surface detail.
- Economy (measured by the compiler: part count, sheets, waste): every part does structural AND visual work; reuse
  identical parts (assemblies, repeat, mirror) so there are few unique shapes to cut; prefer shapes that nest well
  (straight edges where they do not show); keep the part count and the number of sheets as low as the concept allows.
  Write the estimate in "plan.economy" (unique parts, total parts, sheets).
- Effort budget: at least half of the visible boards carry a profile, a shaped opening, an engraving or detail parts;
  plain rectangles only where they are hidden or structural (a base, an internal floor).
All of this still follows the joint rules: straight profile edges where tabs go, tabs on solid material, every part
joined - creativity that does not compile is worth nothing."""

COMMON_MISTAKES = """COMMON MISTAKES (each is a compile error or warning - avoid them up front):
1. Forgetting thickness: leg height = overall height - top thickness; a shelf between two sides is the inner width.
2. A board with two sizes (or none) equal to its thickness: ambiguous orientation / thickness mismatch.
3. tab_slot onto the receiving board's EDGE: "board" must sit on the broad FACE of "into", inset >= one thickness
   from its edges (at an edge it is a finger corner).
4. Two boards lying flat face to face (parallel faces): they cannot be joined - stand one of them upright.
5. Two boards tabbing into one board at the same place from opposite faces, or slots closer than 2 x thickness.
6. A tab landing in an opening or beyond the receiving board's outline (shaped profiles, windows, doors).
7. A part held only by tabs pushing UP into a board above it (it falls out) - give it something to sit on.
8. Edges almost flush (0.5-5 mm off), twins that differ slightly, overhangs nearly but not exactly equal - make
   them exact.
9. Profile / engraving points outside the board's box or on the wrong axes: face coordinates follow the board's
   in-plane axes in x, y, z order (a board thin along x uses [y, z]).
10. Tilted boards: a straight edge must lie flat on the other board's face at the same pitch; pivot on the lower face.
11. Abbreviating or shrinking the design to fit a reply - use the compact style or multi-part replies instead.
12. A moving part fixed to the static part with tab_slot / finger / cross_lap (it cannot move), or a pivot / angle sign
    that swings it through another board - mount it with "motions" (pivot on the outer edge, an axle, the right sign)."""

PRECISION_PROTOCOL = """PRECISION PROTOCOL (exact placement is what makes a model look real - and compile first time):
1. DATUMS FIRST. Before any board, fix the reference lines and write them in "plan.datums" as `name = value` mm:
   the origin (x = 0 left, y = 0 ground, z = 0 back), every level (base top, floor top, sill, lintel, eave, ridge),
   every wall / face plane, every column, bay and post centre line, and the centre line of symmetry. Compute every
   board's position and size from these datums (plus or minus thicknesses) - never estimate a board on its own.
   Parts that line up in the real object use the SAME datum number.
2. DIMENSION CHAINS: in each direction the parts must add up (overall = parts + gaps). Write the main chains in
   "plan.datums", e.g. "x: 6 wall + 4 x 150 bay + 6 wall = 612". A chain that does not add up is a gap or an
   overlap in the model.
3. MODULE AND RHYTHM: pick a module (bay, post spacing, tile pitch) and place repeated parts on it with "repeat"
   (step = module) or repeated openings, so spacing is perfectly even. n parts of width w over length L:
   step = (L - w) / (n - 1) - choose L or n so the step is whole.
4. SYMMETRY: build one half and "mirror" it about the centre datum; never retype the other half.
5. CURVES BY EQUATION, NOT BY EYE: arches, eave sweeps, hulls, body sections, wheel arches, domes - compute the
   points from the curve (circle u = cx + r cos t, v = cy + r sin t; ellipse a cos t, b sin t; superellipse;
   parabola v = k u^2; catenary; a smooth spline through measured points) every 5-10 degrees or 5-20 mm, round to
   whole mm, and put the ends exactly on the datums they meet. Use "arc" path segments for true circular arcs.
   Parts that rest on each other (a rib and its skin, a truss top and its roof panel) use the SAME points.
   Worked example - a body rib, superellipse half-width a = 60, half-height b = 40, exponent n = 2.5, centred on
   (60, 40) of its board: u = 60 + 60 sgn(cos t) |cos t|^(2/n), v = 40 + 40 sgn(sin t) |sin t|^(2/n), t every 15 deg:
   t 0 -> (120, 40), 15 -> (118, 54), 30 -> (113, 63), 45 -> (105, 70), 60 -> (94, 76), 75 -> (80, 79), 90 -> (60, 80),
   then mirrored to the other three quarters - 24 whole-mm points the next rib repeats with its own a and b.
6. ANGLES FROM WHOLE-NUMBER TRIANGLES (3-4-5, 5-12-13, 8-15-17, 7-24-25, 20-21-29) so slopes and lengths stay whole.
7. TOLERANCE BUDGET: joints touch at gap 0; moving parts keep 1-2 mm running clearance; layers sit exactly on each
   other; nothing is 1-5 mm off a neighbour it should line up with (that reads as a mistake, not a design).
8. NUMERIC SELF-AUDIT: before answering, recompute at least 10 boards (the largest, the most connected, a curved one,
   a repeated one) from the datums and confirm every number in the JSON."""

REALISM_PLAYBOOK = """REALISM PLAYBOOK (universal - for any object: a building, a machine, a creature, a product, a scene):
- IDENTITY FIRST: before anything else write in "plan.reference" the 3-5 features that make THIS object recognisable -
  the ones a person would draw first (an outline, a proportion, a rhythm of parts, a characteristic detail). They get
  the most care; everything else supports them.
- Order of work: SILHOUETTE first (most of the recognition is the outline seen from the front and the side), then the
  big masses and their proportions, then the layers of depth, then the details. Never detail a wrong silhouette.
- Scale and level of detail: fix the model scale (real size / model size) and write it in "plan.reference". Work down
  the detail ladder and stop only at the level the brief asks for (default: level 4):
  1 masses (silhouette and proportions) -> 2 structure (every visible member: frames, posts, ribs, spars, beams) ->
  3 openings and layers (every opening, panel and recess, with its frame and depth) -> 4 surface detail (repeated
  elements, trims, fittings, ornament, lettering) -> 5 fine detail (engraved texture, decals, tiny fittings). Model
  every real element larger than about 2 x the board thickness at that scale as a shape, opening, layer or part;
  smaller ones as engravings or decals (colouring on).
- Real proportions: take every size from the real object at the chosen scale (its standard parts - an opening a person
  passes through, a step, a seat, a wheel, a limb - set the scale for the rest); never invent proportions.
- Depth: real faces are never flat. Give every visible face 2-5 layers, each one thickness forward (base surface ->
  frame -> trim -> projecting parts -> ornament); recesses get a dark inner board; overhangs throw shadow.
- Detail in one plane belongs to one board (Fewer, smarter boards); detail with real depth is separate layered parts.
- Context: a base just larger than the footprint; surroundings only where the brief or the reference shows them."""

UNIVERSAL_METHOD = """UNIVERSAL CONSTRUCTION METHOD (the same method builds anything - break the object into the FORM TYPES it is made of
and build each one with its technique; most objects mix several):
- FLAT PARTS (walls, panels, plates, fins, wings, signs, blades): one board each, shaped by "profile", pierced by
  openings, detailed by engravings, given depth by layered trim boards.
- BOX VOLUMES (rooms, cases, cabinets, bodies, housings): walls with finger corners, top and bottom tabbed in, a back
  or rails to lock them square; openings recessed over a dark inner board.
- FRAMES AND SKELETONS (structures, trusses, stands, legs, cages, spars): members as boards, crossing members
  cross_lapped, end-on members tabbed; triangulate where it must not rack; joints placed where the real ones are.
- SMOOTH AND ORGANIC VOLUMES (bodies, hulls, heads, domes, fruit, terrain, sculpture): contour slicing - either
  stacked layers (horizontal sections at equal heights) or a spine carrying the side profile with cross-section ribs
  at equal stations (cross_lap); every outline computed from the measured width and height curves (superellipse,
  ellipse, spline); successive sections change by at most about 15%; skin panels only where nearly flat.
- ROUND AND CYLINDRICAL PARTS (columns, wheels, towers, trunks, pipes, lenses): stacked discs, cross-lapped pairs,
  radial fins or a faceted polygon - chosen by how the part is seen.
- TAPERING AND SEGMENTED PARTS (necks, tails, limbs, branches, spires, chains): segments whose size changes by a
  fixed ratio, each riding on the previous one (nested motions where it should move).
- REPEATED ELEMENTS (tiles, scales, slats, windows, teeth, feathers, seats, spokes): one module placed with
  "repeat" / "instances", or ONE board with repeated openings when they share a plane; let them vary gradually where
  the real thing varies (sizes growing along a row, rows offset by half a module).
- SHELLS AND SWEEPS (roofs, canopies, sails, fenders, hoods): bands of flat panels at stepped angles on supports
  whose profiled edges carry them exactly; "living_hinge" for gentle single curves.
- SURFACE DETAIL (texture, seams, lettering, patterns, markings): engravings and decals - never extra boards.
- MOVING PARTS: real motions with axles, pins, gears and rods; several movements from one input (Linkages).
Build in layers from the ground up: base -> structure -> enclosure / skin -> depth layers -> details -> moving parts
-> colour, each layer standing on or locking into the one below."""

SIGNS_OF_LIFE = """SIGNS OF LIFE (universal - what makes a model feel alive instead of a dead diagram):
- GESTURE: what can lean, turn or open in the real object is caught in a natural moment, not stiff at attention - a head
  turned, a lid or door slightly open, wheels steered, weight on one side, a stem leaning, a flag mid-wave.
- PURPOSEFUL ASYMMETRY: keep structure symmetric where the object is, and break symmetry in pose and use (one window
  open, one drawer pulled, one arm raised).
- MOTION: whatever moves in reality moves in the model ("motions") - and the most expressive movement is the centre
  of the design; several movements from one input, phased so one follows another.
- NATURAL VARIATION: repeated natural or hand-made elements vary slightly (shades, sizes, angles within a few
  percent); machine-made elements stay exact. Never a perfect grid where nature or craft would show variation.
- FOCUS: one focal point carries the most detail and the strongest contrast; the rest is quieter and supports it.
- LIGHT AND SHADOW: depth layers, recesses over dark boards and overhangs make the form read under light.
- SIGNS OF USE AND STORY: one or two small details that show the object belongs to a world (something placed on it,
  a door left open, a lamp by an entrance) - only where they add, always joined to the structure.
- COLOUR WITH INTENT (colouring on): a palette taken from the real object or the chosen style, with the focal part in
  contrast."""

UNIVERSAL_STYLES = ['Art Deco - stepped forms, sunburst and chevron cut-outs, vertical fins',
                    'Japanese joinery - exposed joints, lattices, restraint, natural wood',
                    'Streamline Moderne - teardrop forms, speed lines, rounded corners',
                    'Gothic - pointed arches, tracery, vertical rhythm, pinnacles',
                    'Parametric - ribbed waffle structure, gradually changing slats',
                    'Organic - flowing curves, branching and leaf-like openings',
                    'Steampunk - exposed gears, rivet engravings, brass and dark tones',
                    'Scandinavian - simple planes, warm wood, soft corners, one accent colour',
                    'Storybook fantasy - exaggerated proportions, crooked lines, round openings',
                    'Brutalist - bold stacked masses, deep coffers, rhythmic fins',
                    'Biomechanical - visible mechanism inside a ribbed body',
                    'Folk ornament - filigree cut-outs and patterned decals',
                    'Low-poly faceted - crisp planes and sharp creases',
                    'Industrial - frame plates with lightening holes, bolt-head engravings',
                    'Art Nouveau - whiplash curves, floral cut-outs',
                    'Mid-century - tapered splayed legs, rounded corners, two-tone']
BOARDS_PER_PART = 250


def creative_brief(title='', requirements='', images=False):
    """A universal CREATIVE BRIEF for any object: the AI names the object's identity features and its most alive
    moment, and chooses from three style directions picked per title (the same title gets the same three). None with
    reference images: then the reference is the brief."""
    if images:
        return ''
    import hashlib
    seed = int(hashlib.sha256((title or 'design').strip().lower().encode()).hexdigest(), 16)
    n = len(UNIVERSAL_STYLES)
    pick = list(dict.fromkeys(UNIVERSAL_STYLES[(seed // (n ** k)) % n] for k in range(4)))[:3]
    return '\n'.join([
        'CREATIVE BRIEF (the brief is short, so make it rich - never build the average version of the object):',
        '- Identity: name the 3-5 features that make this object recognisable and give each the most care.',
        '- Life: name its most alive moment (a movement, a gesture, a reveal) and make it the centre of the design.',
        '- Style: the requirements\' style first; otherwise the object\'s OWN real style (its period, culture or '
        'make) - identity and precision come before novelty. Only when the object has no fixed style, or as an accent '
        f"that does not change its identity, choose or fuse from: {' | '.join(pick)}; carry the motifs through every "
        'part.',
        '- Concept line: write in "plan.concept" the sentence a visitor would say on seeing the model, and the style '
        'chosen and why.'])


def scope(title='', requirements='', images=False, machine=None):
    """Universal size planning: the AI counts its own inventory and decides the delivery before writing boards."""
    file = bool(machine and machine.get('file'))
    return ('SCOPE: before the first board, count the boards your inventory needs (after consolidation, with '
            'assemblies / instances / repeat keeping the JSON short) and write the count in "plan.economy". '
            + ('Generate the file with a script (loops for repeated parts) whatever the count.' if file else
               f'Up to about {BOARDS_PER_PART} boards fit in one reply; above that decide the number of multi-part '
               f'replies NOW (count / {BOARDS_PER_PART}, rounded up) - never shorten the design instead.')
            + ' Fewer boards is fine when one panel carries the detail - never by leaving visible parts out.')


FIDELITY_OVERRIDE = """FIDELITY OVERRIDES CREATIVITY (reference images are attached): reproduce the object in the images - do not
reinterpret, restyle, "improve", simplify or add features they do not show. DESIGN QUALITY's creativity applies only to
what the images cannot show (hidden structure, joints, the way parts lock); its economy and detail rules still apply.
The same silhouette, proportions, counts, layering and colours as the reference are the measure of success."""

ANTI_PATTERNS = """FAILURES THAT MAKE A MODEL LOOK FAKE (the reviewer rejects a design that shows any of them):
- The generic version: a box house, a rectangle car, a blob animal instead of THIS object's silhouette.
- Wrong counts: 4 columns where there are 6, 3 windows where there are 5, the wrong number of storeys or roof tiers.
- Flattened depth: everything in one plane, no eave overhang, no recessed openings, no layered trim.
- Guessed curves: a straight roof where it sweeps, a polygon of 4 points where a smooth arch or hull is.
- Drifting alignment: windows of one row at slightly different heights, unequal bays, a symmetric object that is not.
- Wrong proportions: roof too low or too high, doors too big for the storey, legs too thick, the head too small.
- Colour off: a different palette from the reference, every part the same colour, or random colours per part.
- Fragmentation: thirty separate posts or bars where one panel with cut-outs looks the same.
- Floating or held-from-above parts, decorations stuck on without a joint, parts that would fall out."""

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
you change or fix the design unless asked to recolour.
Printed artwork ("decals", on any board): coloured shapes and lettering printed on a face - never cut, so they cost no
material and no cutting time. Use them for ornament a flat board cannot carry by shape alone: gilded trims and bands,
painted panels, lattice and wave patterns, crests and medallions, signs and lettering, window frames, tile and brick
patterns. They show in the 3D view and come out as print sheets lined up with the cut sheets.
```jsonc
"decals": [
  {"face": "front", "color": "#c9a227", "shape": "rect", "center": [300, 150], "width": 560, "height": 260, "corner_radius": 12},
  {"face": "front", "color": "#1b1b1b", "shape": "polygon", "points": [[60, 40], [540, 40], [300, 260]]},
  {"face": "back", "color": "white", "text": "GATE 1", "position": [300, 150], "height": 40}
]
```
- Shapes use the same face coordinates `[u, v]` and shape types as profiles and openings (rect, circle, ellipse, arch,
  regular_polygon, polygon, path); they must lie on the face. Later decals are drawn on top of earlier ones: build a
  motif from a background shape and smaller shapes over it.
- Lettering: `"text"`, `"height"` (capital height, mm) and `"position"` = the CENTRE of the text; it is turned to read
  upright on that face automatically.
- The face's own `"color"` is the background printed under the decals."""


IMAGE_SPEC = """## Reference images (attached to this message) - REFERENCE CLONING PROTOCOL
The image(s) ARE the specification. The goal is a CLONE: someone looking at the image and the 3D model side by side
must see the same object - the same silhouette, proportions, parts, counts, layering and colours - not a generic
product of the same kind and not a reinterpretation. Take as long as you need: accuracy matters far more than speed.
1. READ THE VIEWS: for each image decide the viewpoint (front elevation, side, back, top, three-quarter perspective,
   detail). A straight-on elevation can be measured directly. In a perspective view measure on faces parallel to the
   picture and correct the rest: parts further away look smaller, and parallel edges meet at vanishing points - use
   them to recover right angles and true depth ratios. Combine all views into one 3D understanding: a size seen in
   two views (the height in the front and the side view) must agree - where they differ trust the straighter view,
   and record the decision. When images disagree on a detail, follow the clearest, closest image of that detail.
2. CALIBRATE THE SCALE: choose a scale anchor - a size from the requirements, else a real standard visible in the
   image (door about 2000 mm, step rise about 170 mm, person about 1700 mm, car wheel about 650 mm, brick course 75 mm)
   - and work out mm per image unit; then the model scale that gives the requested size. Write
   "scale: anchor ..., 1.00 of width = ... mm, model 1:..." in "plan.reference".
3. MEASURE ON A GRID: lay a 20 x 20 grid over each view (0.00-1.00 from the object's left and bottom edges). Read the
   key lines first - ground, podium top, floor, every eave and ridge, column centres, wall corners, the axis of
   symmetry - then every element's box, to 0.01. Convert them through the calibration into the datums
   (PRECISION PROTOCOL) and the element sizes. Write the main ratios (height / width, eave overhang / width, ...).
4. INVENTORY EVERYTHING in "plan.reference", one line per element:
   "id | view | box x 0.22-0.30 y 0.40-0.70 | size mm | count | shape | layer | colour",
   layer = depth order (0 the main face, +1 one step in front, -1 recessed). Count repeated elements one by one -
   columns, bays, rafter tails, bracket sets, tiles per course and courses, balusters, panes, steps, windows per
   floor. A wrong count is the most visible error of a clone.
5. TRACE THE OUTLINES: the silhouette and every shaped part become polygon / path points read off the grid - a point
   at every visible corner and about every 5% of length along curves; trace symmetric curves once and mirror them.
   Never replace a traced curve by a rectangle or a generic arc.
6. COLOURS: pick one hex colour per role from the image (roof, walls, columns, trim, ornament, ground) and use exactly
   those (colouring on); vary repeated parts slightly only where the image shows variation.
7. DEPTH: rebuild what stands in front of what and by how much (eave overhang, column projection, recessed doors and
   windows, stacked brackets, layered trims) - one thickness per step of shallow relief.
8. PARTS THE IMAGE DOES NOT SHOW (inside, back, underside): only what the structure needs to stand and lock, in the
   visible style; the hidden back of a symmetric object mirrors its front unless an image shows otherwise.
9. WHAT FLAT BOARDS CANNOT MAKE (curved surfaces, round solids, bends): the closest flat construction - stacked
   contour layers, ribs with a skin of panels, faceted panels, "living_hinge" - and record each approximation in
   "product.description".
10. BUILD AND TICK OFF: build the inventory element by element; in "plan.checks" write one line per inventory id with
    the board ids that make it ("W1 -> W-F opening win-l, LINING g00..g23"). Every line must be ticked off - nothing
    visible may be missing, merged into a plain board or left out to save space.
11. PROJECTION CHECK BEFORE ANSWERING: project your design onto each reference view (front view: every board's x and
    y extents; side: z and y; top: x and z) and compare with your measurements - silhouette points, datums, element
    boxes and counts. Every position must be within 2% of the overall size and every count exact; fix every
    difference. Write the result in "plan.checks" (e.g. "front: 41 / 41 elements within 2%, counts exact").
    If the result is large, use the compact style and the multi-part replies of the output contract."""


def _coloring(machine):
    return bool(machine and machine.get('coloring'))


def _file_name(text, suffix=''):
    """A file name for the design: the product name (or title) as a slug."""
    name = text
    try:
        name = (json.loads(text).get('product') or {}).get('name') or 'design'
    except (ValueError, TypeError, AttributeError):
        pass
    slug = re.sub(r'[^a-z0-9]+', '_', str(name or 'design').lower()).strip('_')[:50] or 'design'
    return f'{slug}{suffix}.json'


def _contract(machine, fname):
    """The output contract: a downloadable .json file (the user's choice, default) or code in the chat."""
    if not (machine and machine.get('file')):
        return OUTPUT_CONTRACT
    return f"""OUTPUT CONTRACT (strict — deliver a FILE: the user downloads it and opens it in the compiler):
- Deliver the COMPLETE design as ONE downloadable file named `{fname}` (UTF-8, strict JSON, nothing else in it).
  Use your code / file tool: write a short script that BUILDS the design - loops for rows of tiles, rafters, slats
  and other repeated parts, exact whole-millimetre arithmetic - then saves the file. Do NOT paste the JSON in the
  chat. There is no size limit: the file may hold thousands of boards; never simplify to keep it small.
- Before saving, the script must CHECK the design and fix anything that fails: it parses as JSON; every board id is
  unique; every connection's "board" and "into" exist; every size, position and profile / opening coordinate is a
  whole number; exactly one of each board's three sizes equals its thickness; every board appears in at least one
  connection. Run the script, then attach the file.
- Your chat reply is only the file (its download link) - no explanation. Anything for the user goes into
  "product.description" inside the file.
- Only if you cannot create files: reply with the complete design as ONE ```json code block instead (if it is too
  long for one reply, use the multi-part replies below - never shorten it).
- Never ask a question or refuse: if something cannot be met exactly, deliver the best complete design and explain
  the limitation in "product.description".

{_SHARED_RULES}"""


# the rules both contracts share: no size limit, multi-part replies, strict JSON
_SHARED_RULES = OUTPUT_CONTRACT[OUTPUT_CONTRACT.index('- NO SIZE LIMIT'):OUTPUT_CONTRACT.index('- Anything you want to tell')].rstrip()


def _final(machine, fname):
    if not (machine and machine.get('file')):
        return FINAL_REMINDER
    return (f'FINAL REMINDER: deliver the complete design as the downloadable file `{fname}` built and checked by your '
            f'script (only if you cannot create files: one ```json code block) — no other text, nothing left out.')


def build_prompt(title, requirements='', material=None, thickness=None, joinery=None, machine=None, images=False):
    """images: the user will attach reference image(s) to this prompt in their AI chat; they become the
    specification (see IMAGE_SPEC)."""
    title = (title or '').strip() or ('The product shown in the attached image(s)' if images else 'Board product')
    req = (requirements or '').strip()
    fname = _file_name(title)
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
    return f"""You are a world-class design team - industrial designer, master model maker, structural engineer and CAD
engineer - working as the design step of an automated board-design pipeline. Your models are museum quality: the
object is recognisable at a glance, real in its proportions and depth, rich in detail where it shows, clever in how it
is built, and alive where movement suits it. A plain, generic or box-like answer is a failure even if it compiles.

TASK: Design the product below as a flat-board design in the exact JSON format `{FORMAT}` specified further down.
It is compiled automatically: rendered in 3D, every joint, gap and overlap validated, boards nested on stock sheets
and cutting files produced. Invented fields are ignored and invalid geometry is rejected, so follow the
specification exactly.

{_contract(machine, fname)}

{DESIGN_TEAM}

{SUCCESS_CRITERIA}

{DESIGN_QUALITY}
{(chr(10) + FIDELITY_OVERRIDE + chr(10)) if images else ''}
{PRECISION_PROTOCOL}

{REALISM_PLAYBOOK}

{UNIVERSAL_METHOD}

{SIGNS_OF_LIFE}

{ANTI_PATTERNS}

{COMMON_MISTAKES}

PRODUCT: {title}

REQUIREMENTS:
{req_block}

{hard_constraints(req)}

{scope(title, req, images, machine)}

{creative_brief(title, req, images)}

INSTRUCTIONS (follow every one):
1. Read the requirements. If a dimension is missing, choose a standard value for this product; if two requirements
   conflict, follow the explicit number. Write every such decision in "product.description" as "Assumptions: …".
   If the product needs something listed under "What this generator cannot build", build the closest supported
   version and say what was left out in the description. Do not ask questions — decide and record the assumption.
2. PLAN FIRST: write a top-level "plan" before "boards" (lists of short strings, as in the torii example):
   "reference": the scale line, grid readings and one inventory line per element (with images: REFERENCE CLONING
     PROTOCOL; without: the identity features and every part the brief and the object need, with counts);
   "datums": origin, levels, planes, centre lines and one dimension chain per direction that adds up;
   "concept" and "economy"; "assemblies" and "steps" (the build passes);
   "joints": one line per sub-assembly saying what holds it and which way it is locked, e.g. "SHELF: tabs into SIDE-L
     and SIDE-R (locked every way)", "ROOF-L: tabs into TRUSS-1..4 (lifts straight off: held by its weight)" - no part
     may be held only from above or slide out sideways (Strength and retention);
   "audit": at least 10 boards recomputed from the datums, each "ID: position = datum + ... = [x, y, z], size = ...";
   "checks": the tick-off of the inventory and hard constraints, the red-team findings and their fixes.
   CONCEPT (free design, no reference image): sketch three different concepts in your head, score each 1-5 for
   recognisability, structural sense, detail richness and economy, build the best and name the runners-up in
   "plan.concept" with one line each.
   BUILD IN PASSES, each one finished and checked before the next: (P1) datums and silhouette boards; (P2) structure -
   every load path to the ground, every board joined; (P3) openings and layers of depth; (P4) surface detail and
   repeated elements; (P5) motions and mechanisms; (P6) colours and decals. After each pass re-check the dimension
   chains and that nothing floats or overlaps; a later pass never moves an earlier datum.
   Then decompose the product into every board it needs (nothing implied, nothing missing). Give each a short
   unique id (at most 24 characters) and put the boards of each sub-assembly in the same "group". For repeated or
   symmetric parts use "repeat", "mirror" and "assemblies"/"instances" instead of listing every copy.
   For a building, vehicle or scale model, build a DETAILED model (see "Detailed models"): structure first, then
   surface detail (tile courses, rafters, frames, planks), every visible feature present: as separate joined parts
   where it has real depth, as one board's profile / openings / engravings where it lies in one plane.
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
10. SELF-CHECK (the INSPECTOR) before answering and correct the JSON if any answer is "no":
    a. Does exactly one of each board's three sizes equal its thickness?
    b. For every connection, does the end face of "board" lie exactly on a face of "into" (gap 0)?
    c. Do the boards' combined extents equal product.overall in length, height and depth?
    d. Is any space occupied by two boards (other than boards joined with cross_lap)?
    e. Are all ids unique and at most 24 characters? Is every board held?
    e2. Walk the connections from the base board: is EVERY board reached? Does every board touch another one?
        Is every small part (fittings, details on a deck or panel) standing with an EDGE on that face, never lying
        flat on it, with its slot >= 2 × thickness from every other slot in that board?
        Does every part SIT on something or lock sideways (no part held only by tabs pushing up into a board above)?
    e3. Do the overall sizes match every size stated in the requirements?
    f. Is every size and position a whole number of millimetres, computed from a datum in "plan.datums"? Do the
       dimension chains add up? Did you recompute 10 boards from the datums (PRECISION PROTOCOL 8)?
    f0. RED TEAM: name the five biggest differences between your design and the brief (with images: the reference)
        - silhouette, counts, proportions, depth, curves, colours (FAILURES THAT MAKE A MODEL LOOK FAKE) - and fix
        each before answering; write them and their fixes in "plan.checks".
    f1. Realism: is the silhouette right, are real proportions kept, do visible faces have layers of depth, are
        curves computed rather than guessed (REALISM PLAYBOOK)?
    f2. Is it creative and economical? Check DESIGN QUALITY: a surprising concept with a signature feature, a shaped
        silhouette, layered faces, shaped openings, rhythm and detail; at least half of the visible boards shaped,
        pierced or detailed; identical parts reused, no filler boards, few sheets.{chr(10) + '    g. Does every board have a colour, with one colour per role?' if _coloring(machine) else ''}{chr(10) + '    h. PROJECTION CHECK: does the design match the attached image(s) from the front, side and top - every inventory line ticked off, every count exact, every position within 2% of the overall size, the same colours?' if images else ''}
11. Return ONLY one ```json code block with the complete design; write number arrays on one line ([x, y, z]).

{spec_markdown()}
{(chr(10) + COLOR_SPEC + chr(10)) if _coloring(machine) else ''}{(chr(10) + IMAGE_SPEC + chr(10)) if images else ''}
{_final(machine, fname)}
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


def _root_causes(diagnostics, limit=8):
    """The boards behind the most problems: one misplaced board usually causes several, so it is fixed first."""
    count = {}
    for d in diagnostics:
        if d.get('severity') in ('error', 'warning'):
            for b in set([d['board']] if d.get('board') else (d.get('components') or [])[:2]):
                count[b] = count.get(b, 0) + 1
    top = sorted(((n, b) for b, n in count.items() if n >= 2), key=lambda x: (-x[0], x[1]))[:limit]
    if not top:
        return ''
    return ('LIKELY ROOT CAUSES (boards involved in the most problems - check their position, size and joints first; '
            'fixing one often clears several problems):\n' + '\n'.join(f"- {b}: {n} problems" for n, b in top) + '\n')


_DIM = re.compile(r'(?P<label>[a-z][a-z /-]{0,30}?)?\s*[:=]?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m)\b', re.I)


def hard_constraints(requirements):
    """Explicit numbers and demands in the requirements, restated as a checklist the design must tick off: sizes with
    their labels (converted to mm), a model scale, counts, the thickness, the detail level and movement."""
    req = requirements or ''
    out = []
    for m in _DIM.finditer(req):
        v = float(m['num']) * {'mm': 1, 'cm': 10, 'm': 1000}[m['unit'].lower()]
        label = (m['label'] or '').strip(' :-=').split(',')[-1].strip() or 'a size'
        out.append(f"{label}: {v:g} mm")
    for m in re.finditer(r'\b1\s*:\s*(\d{1,4})\b', req):
        out.append(f"model scale 1:{m[1]}")
    for m in re.finditer(r'\b(\d{1,4})\s+([a-z]{3,}s)\b', req, re.I):
        if m[2].lower() not in ('mms', 'cms'):
            out.append(f"{m[2]}: exactly {m[1]}")
    low = req.lower()
    if re.search(r'\b(highly detailed|very detailed|ultra|realistic|exact|replica|clone|museum)', low):
        out.append('detail level: 5 (every visible element, fine detail included)')
    elif re.search(r'\b(simple|minimal|basic|low detail)', low):
        out.append('detail level: 2-3 (silhouette, structure, main openings)')
    if re.search(r'\b(mov(e|es|ing|able)|kinetic|animat|flap|rotat|spin|crank|motor|open(s|ing)?)\b', low):
        out.append('movement: the moving parts asked for must be real motions driven as described (see Linkages)')
    seen, uniq = set(), []
    for x in out:
        if x.lower() not in seen:
            seen.add(x.lower())
            uniq.append(x)
    if not uniq:
        return ''
    return ('HARD CONSTRAINTS (read from the requirements - each must hold in the finished design; tick every one off '
            'in "plan.checks"):\n' + '\n'.join(f"- {x}" for x in uniq))


def build_repair_prompt(source, diagnostics, blocking=(), machine=None):
    """Follow-up prompt: hand the generator's diagnostics (and the production blockers: fasteners, stock, cut paths)
    back to the AI and ask for a minimal correction, returned as code only."""
    seen = {d['message'] for d in diagnostics}
    diagnostics = list(diagnostics) + [dict(b, severity='error') for b in blocking if b.get('message') not in seen]
    syntax = any(d.get('code') == 'JSON_SYNTAX' for d in diagnostics)
    fname = _file_name(source or '', '_fixed')
    floats = sum(1 for d in diagnostics if d.get('code') == 'NON_INTEGER_DIMENSION')
    return f"""You are the repair step of an automated board-design pipeline. The compiler checked the design below (format
`{FORMAT}`) and found the problems listed. Return the corrected design as code only.

{_contract(machine, fname)}

YOUR ROLE - three specialists one after another inside this single reply (the only output is the JSON):
1. DIAGNOSTICIAN - reads every problem with its calculation and finds the root cause: one misplaced or mis-sized
   board often causes several problems; boards that are NOT ATTACHED come first.
2. REPAIR ENGINEER - applies every "Suggested fix" exactly, makes the smallest change for the rest and updates the
   boards and connections that depend on a changed board.
3. INSPECTOR - confirms each listed problem is gone and nothing new broke, against the SUCCESS CRITERIA and the
   COMMON MISTAKES below, before handing over.

{SUCCESS_CRITERIA}

{COMMON_MISTAKES}

REPAIR RULES (follow every one):
1. Fix every [ERROR]. Fix every [WARNING] too, unless the fix would change what the product is meant to be; then leave
   it and add one sentence about it to "product.description".
2. Where a problem gives a "Suggested fix", apply exactly those values — the compiler computed them.
3. Make the smallest change that fixes each problem: keep every other board, id, dimension and connection exactly as
   it is — same ids, same order, same names and groups. Do not add, remove or rename boards or connections unless a
   problem requires it. Never simplify to make a problem go away: keep every profile, shaped opening, engraving,
   tilt and detail part and fix its position, size or joint instead - a shaped board stays shaped.
4. When you move or resize a board, update the boards and connections that depend on it so every mating face still
   touches exactly (gap 0) and no two boards overlap. Work from the datums in "plan.datums" when the design has them:
   a part that lines up with others keeps sharing their datum number.
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

{_root_causes(diagnostics)}
PROBLEMS:
{_problem_lines(diagnostics)}

YOUR PREVIOUS JSON:
```json
{(source or '').strip()}
```

SPECIFICATION (reference for every field and rule):
{spec_markdown()}
{(chr(10) + COLOR_SPEC + chr(10)) if _coloring(machine) else ''}
{_final(machine, fname)}
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
    fname = _file_name(source or '', '_updated')
    return f"""You are the change step of an automated board-design pipeline. Below is an existing, working design in the
`{FORMAT}` format. Apply the CHANGE REQUEST to it and return the updated design as code only.

{_contract(machine, fname)}

YOUR ROLE - three specialists one after another inside this single reply (the only output is the JSON):
1. CHANGE ANALYST - works out exactly what the request changes and every board and connection that depends on it.
2. ENGINEER - makes that change, recomputes the dependent sizes and positions, keeps everything else identical.
3. INSPECTOR - checks the result against the SUCCESS CRITERIA, DESIGN QUALITY and the COMMON MISTAKES below before
   handing over.

{SUCCESS_CRITERIA}

{DESIGN_QUALITY}
{(chr(10) + FIDELITY_OVERRIDE + chr(10)) if images else ''}
{PRECISION_PROTOCOL}

{REALISM_PLAYBOOK}

{UNIVERSAL_METHOD}

{SIGNS_OF_LIFE}

{COMMON_MISTAKES}

CHANGE REQUEST:
{change}
{(chr(10) + hard_constraints(change) + chr(10)) if hard_constraints(change) else ''}{chr(10) + "REFERENCE IMAGES: the image(s) attached to this message show how the product must look after the change. "
 "Study them first, then change every board that differs from them (shape, proportions, parts, openings, engravings) "
 "and keep the rest. Rules 1-7 below still apply; see \"Reference images\" at the end." + chr(10) if images else ''}
RULES FOR THE UPDATE (follow every one):
1. Identify the boards and connections the change affects, including dependent ones (e.g. a wider product means
   longer tops, shelves and back panels, and moved side panels).
2. Change only those. Keep every unaffected board's id, position, size and every unaffected connection exactly as it
   is — do not rename, re-order or re-generate the rest of the design. New or changed parts follow DESIGN QUALITY; a
   request to make the design nicer, more detailed or more elegant means applying DESIGN QUALITY to the parts it
   names (to the whole design when it names none), never simplifying what is already shaped.
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
{_final(machine, fname)}
"""
