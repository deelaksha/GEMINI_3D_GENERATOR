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
  "edge_banding"?: [{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm}]}
```
- `id` must match `^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$` and be unique (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Keep ≥ 1.5 mm
  (recommended 3 mm) of material between any opening/slot and an edge, and ≥ 1 mm between cut-outs.

## connection
```
{"id": str, "type": one of ['tab_slot', 'butt', 'hinge', 'mitre'], "board": "<board A>", "into": "<board B>", ...}
```
- `tab_slot` (glue-free): an END FACE of board A sits flat against the BROAD FACE of board B. The generator adds tabs on A and
  cuts matching slots through B. Options: `"tabs"`: 1..12, `"tab_width"`: mm, `"edge"`: "+y" etc. to pick A's edge.
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
4. Square to each other: every board is axis aligned; tabs insert perpendicular to the receiving face.
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
