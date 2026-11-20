<!-- Generated from board_engine/canvas_prompt.spec_markdown(); tests keep it in sync. -->
# Board design format `board-design/v1` — specification

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
{
  "format": "board-design/v1",
  "product":  {"name": str, "description": str, "overall": {"length": mm, "height": mm, "depth": mm}},
  "material": {"name": str, "type": one of ['plywood', 'mdf', 'particle_board', 'solid_wood', 'hardboard', 'cardboard', 'other'], "thickness": mm, "kerf"?: mm, "clearance"?: mm},
  "joinery":  one of ['interlocking', 'glue_allowed']   (optional; "interlocking" = glue-free, tab_slot only),
  "sheet"?:   {"width": mm, "height": mm}   (stock sheet; chosen automatically when omitted),
  "boards":   [board, ...],
  "connections": [connection, ...]
}
```
- `thickness` between 0.5 and 50 mm. `clearance` = extra width of every slot over the
  tab board thickness (default 0.1); `kerf` defaults from the material catalogue below.
- At most 300 boards; coordinates within ±5000 mm.

## board
```
{"id": str, "name": str, "group": str, "position": [x, y, z], "size": [sx, sy, sz],
  "thickness"?: mm (default material.thickness), "material"?: {"name", "type"}, "grain"?: "x"|"y"|"z",
  "openings"?: [ {"id", "kind": "opening"|"hole", "shape": "circle", "center": [x, y, z], "diameter": mm}
               | {"id", "kind": "opening"|"hole", "shape": "rect", "center": [x, y, z], "size": [a, b]} ],
  "edge_banding"?: [{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm, "material"?: str}],
  "profile"?: shape, "engravings"?: [...], "rotate"?: {...}   (see "Complex cuts and tilted boards")}
```
- `id` must match `^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$` and be unique (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Openings and
  engravings may carry `"note"`: str (shown in the drawings). Keep ≥ 1.5 mm
  (recommended 3 mm) of material between any opening/slot and an edge, and ≥ 1 mm between cut-outs.

## Complex cuts and tilted boards (optional)
Face coordinates `[u, v]`: millimetres from the board box's **minimum corner**, along the board's two in-plane axes in
x, y, z order (a board with normal z uses u = x, v = y; normal y: u = x, v = z; normal x: u = y, v = z).
Shapes (used by `profile`, `openings` and `engravings`):
```
{"shape": "rect", "center": [u, v], "width", "height", "corner_radius"?, "angle"?}
{"shape": "circle", "center", "diameter"}            {"shape": "ellipse", "center", "width", "height"}
{"shape": "arch", "center", "width", "height"}       (straight sides, semicircular top; height ≥ width / 2)
{"shape": "regular_polygon", "center", "sides": 3..64, "diameter", "rotation"?: deg}
{"shape": "polygon", "points": [[u, v], ...], "corner_radius"?}
{"shape": "path", "start": [u, v], "segments": [{"line": [u, v]}
    | {"arc": {"to": [u, v], "radius": mm, "large"?: bool, "clockwise"?: bool}}
    | {"arc": {"to": [u, v], "center": [u, v], "clockwise"?: bool}}], "corner_radius"?}
```
- `"profile": shape` replaces the board's rectangular outline (pitched gable, arched top, curved side, L/U shape,
  rounded corners). It must stay inside the box `[0..size_u] × [0..size_v]`; the box is still the board's bounding box.
  A tab_slot connection needs a **straight** profile edge on the touching side of the box.
- Openings may use any shape: `"center"` stays a world point [x, y, z] and the shape's own coordinates are relative to
  it (`"size": [a, b]` sets width/height of rect, ellipse and arch). Rect openings also accept `"corner_radius"`.
- `"engravings": [{"id", "kind": "engrave"|"pocket", "depth": mm, "points": [[u, v], ...], "closed"?: bool}
  | {"id", "kind", "depth", ...shape}]` — machined into the face, never through (default depth: engrave 0.5 mm,
  pocket half the board). Engrave depth ≤ half the board;
  pockets keep the material's minimum remaining thickness under them. Must lie fully on the board, off any cut-out.
- `"rotate": {"axis": "x"|"y"|"z", "angle": degrees, "pivot"?: [x, y, z]}` tilts a board (roof panels, sloped backs,
  lecterns). It is applied **last**: `position`/`size`, profile, openings, engravings and `"edge"` directions all describe
  the board before rotating; `pivot` defaults to the box centre. Positive angles turn counter-clockwise looking down
  the axis (about z: +x turns towards +y).
- Tilted tab_slot / butt: a straight edge of board A must lie flat on a broad face of board B — e.g. a gable's sloped
  top edge under a roof panel tilted to exactly the same pitch (within 0.5°) — and touch it (|gap| ≤ 0.25 mm).
  Tabs insert square to B's face. Two roof panels meeting at a ridge should each end where their lower faces meet
  (their end faces then only touch along the ridge line).

## connection
```
{"id": str, "type": one of ['tab_slot', 'butt', 'hinge', 'mitre'], "board": "<board A>", "into": "<board B>", ...}
```
- `tab_slot` (glue-free): an END FACE of board A sits flat against the BROAD FACE of board B. The generator adds tabs on A and
  cuts matching slots through B. Options: `"tabs"`: 1..12, `"tab_width"`: mm, `"tab_depth"`: mm (default B's thickness,
  i.e. flush with B's far face), `"edge"`: "+y" etc. to pick A's edge.
  A must be inset from B's edges by at least B's slot margin (1.5 mm, recommended ≥ 3 mm; use ≥ the
  board thickness for furniture), and the contact must be longer than 2 × A's thickness plus the tab width.
- `butt` (needs `"joinery": "glue_allowed"`): A's end face against B's face, held by `"fasteners": {"kind": one of
  ['screw', 'confirmat', 'dowel'], "count"?: n}`. Catalogue: `screw` (Ø4 × 40 mm), `confirmat` (Ø7 × 50 mm), `dowel` (Ø8 × 35 mm).
- `hinge` (needs glue_allowed): `"board"` = door, `"into"` = carcass board it hangs on, `"edge"` = the door edge carrying
  the hinges ("+x"/"-x"/...), optional `"count"`, `"gap"`.
- `mitre` (needs glue_allowed): `"edge"` on A and `"into_edge"` on B (directions), optional `"bevel": true`.
- Every board must be connected (directly or through others) to the rest of the product.

## Geometry rules the generator validates (violations are compile errors)
1. **Touching, not overlapping:** for every connection A's end face must lie exactly on B's face (|gap| ≤ 0.25 mm).
   Account for board thickness: e.g. leg height = overall height − top thickness; a shelf between two sides is
   (inner width) = overall width − 2 × side thickness long.
2. **No overlaps:** boards may not occupy the same space anywhere (tabs inside their slots are fine).
3. **No unintended gaps:** a board meant to sit on/against another must touch it.
4. Square to each other: boards are axis aligned unless they use `rotate`; tabs insert perpendicular to the receiving face.
5. Every board must fit on one stock sheet; standard thicknesses are preferred (table below).

## Material catalogue (type | standard thicknesses mm | kerf mm | grain | minimum part mm)
| type | thicknesses | kerf | grain | min part |
|---|---|---|---|---|
| `plywood` | 3, 4, 6, 9, 12, 15, 18, 21, 24, 27, 30 | 3.2 | yes | 25 |
| `mdf` | 3, 6, 9, 12, 15, 16, 18, 19, 22, 25, 30 | 3.2 | no | 25 |
| `particle_board` | 8, 10, 12, 16, 18, 19, 22, 25, 28, 30, 38 | 3.2 | no | 30 |
| `solid_wood` | 12, 15, 18, 20, 22, 25, 27, 30, 32, 38, 40, 45 | 3.2 | yes | 20 |
| `hardboard` | 2.5, 3, 3.2, 4, 5, 6 | 3.2 | no | 20 |
| `cardboard` | 1.5, 2, 3, 4, 5, 6 | 0.2 | no | 5 |

## Native engine format (advanced)
The canvas also accepts the engine's own design JSON (top-level `"components"` + `"joints"` instead of `"boards"`):
local 2D outlines with `arcs`, features (`rect` / `circle` / `polygon`), `marks`, tabs by edge index and placements with
Euler XYZ rotation. It is what the Studio and the REST API use; prefer `board-design/v1` for new designs.

## Output format
Return **one** fenced ```json code block containing only the design object — no comments outside it, no prose inside it.

## Complete valid example (study table, glue-free)
```json
{
  "format": "board-design/v1",
  "product": {
    "name": "Modern Study Table",
    "description": "Glue-free plywood desk with a modesty panel and a shelf.",
    "overall": {
      "length": 1200,
      "height": 750,
      "depth": 600
    }
  },
  "material": {
    "name": "Birch plywood 18 mm",
    "type": "plywood",
    "thickness": 18,
    "clearance": 0.2
  },
  "joinery": "interlocking",
  "boards": [
    {
      "id": "TOP",
      "name": "Table top",
      "group": "Top",
      "position": [
        0,
        732,
        0
      ],
      "size": [
        1200,
        18,
        600
      ],
      "grain": "x"
    },
    {
      "id": "LEG-L",
      "name": "Left leg panel",
      "group": "Legs",
      "position": [
        50,
        0,
        20
      ],
      "size": [
        18,
        732,
        560
      ],
      "openings": [
        {
          "id": "cable",
          "kind": "hole",
          "shape": "circle",
          "center": [
            59,
            600,
            300
          ],
          "diameter": 40
        }
      ]
    },
    {
      "id": "LEG-R",
      "name": "Right leg panel",
      "group": "Legs",
      "position": [
        1132,
        0,
        20
      ],
      "size": [
        18,
        732,
        560
      ]
    },
    {
      "id": "MODESTY",
      "name": "Modesty panel",
      "group": "Frame",
      "position": [
        68,
        432,
        480
      ],
      "size": [
        1064,
        300,
        18
      ]
    },
    {
      "id": "SHELF",
      "name": "Lower shelf",
      "group": "Shelves",
      "position": [
        68,
        150,
        60
      ],
      "size": [
        1064,
        18,
        400
      ]
    }
  ],
  "connections": [
    {
      "id": "LEG-L-TOP",
      "type": "tab_slot",
      "board": "LEG-L",
      "into": "TOP",
      "tabs": 2
    },
    {
      "id": "LEG-R-TOP",
      "type": "tab_slot",
      "board": "LEG-R",
      "into": "TOP",
      "tabs": 2
    },
    {
      "id": "MOD-TOP",
      "type": "tab_slot",
      "board": "MODESTY",
      "into": "TOP",
      "tabs": 3
    },
    {
      "id": "MOD-L",
      "type": "tab_slot",
      "board": "MODESTY",
      "into": "LEG-L",
      "tabs": 1
    },
    {
      "id": "MOD-R",
      "type": "tab_slot",
      "board": "MODESTY",
      "into": "LEG-R",
      "tabs": 1
    },
    {
      "id": "SHELF-L",
      "type": "tab_slot",
      "board": "SHELF",
      "into": "LEG-L",
      "tabs": 2
    },
    {
      "id": "SHELF-R",
      "type": "tab_slot",
      "board": "SHELF",
      "into": "LEG-R",
      "tabs": 2
    }
  ]
}
```

## Complete valid example with complex cuts (gabled cottage: pitched profiles, arched door, heart, 35° roof)
```json
{
  "format": "board-design/v1",
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
                "large": true
              }
            },
            {
              "arc": {
                "to": [
                  -16,
                  2
                ],
                "radius": 9,
                "large": true
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
```
