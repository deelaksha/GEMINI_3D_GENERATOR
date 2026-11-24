<!-- Automatically generated from spec_markdown() -->
# Board design format `board-design/v1` — specification

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
{
  "format": "board-design/v1",
  "product":  {"name": str, "description": str, "overall": {"length": mm, "height": mm, "depth": mm},
               "mounting"?: one of ['floor', 'wall'] (default "floor"; "wall" = screwed to the wall behind it, z = 0 side)},
  "material": {"name": str, "type": one of ['plywood', 'mdf', 'particle_board', 'solid_wood', 'hardboard', 'cardboard', 'other'], "thickness": mm, "kerf"?: mm, "clearance"?: mm},
  "joinery":  one of ['interlocking', 'glue_allowed']   (optional; "interlocking" = glue-free: tab_slot, finger and cross_lap
              only; "glue_allowed" also permits butt, hinge and mitre. Derived from the connections when omitted),
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
{"id": str, "name": str, "group": str (sub-assembly, e.g. "Carcass", "Drawer 1", "Door"), "position": [x, y, z], "size": [sx, sy, sz],
  "thickness"?: mm (default material.thickness), "material"?: {"name", "type"}, "grain"?: "x"|"y"|"z",
  "openings"?: [ {"id", "kind": "opening"|"hole", "shape": "circle", "center": [x, y, z], "diameter": mm}
               | {"id", "kind": "opening"|"hole", "shape": "rect", "center": [x, y, z], "size": [a, b]} ],
  "edge_banding"?: [{"edge": "+x"|"-x"|"+y"|"-y"|"+z"|"-z", "thickness": mm, "material"?: str}],
  "profile"?: shape, "engravings"?: [...], "rotate"?: {...}   (see "Complex cuts and tilted boards")}
```
- `id` must match `^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$`, be unique and at most 24 characters (e.g. `TOP`, `SIDE-L`, `SHELF-2`).
- `group` names the sub-assembly a board belongs to (product → group → board). Give every drawer, door, module or
  lid its own group so the parts list and assembly steps follow the product's structure.
- Opening `center` is a world point inside the board; rect `size` is along the board's two in-plane axes in x, y, z order.
  `opening` = intentional design opening (never filled), `hole` = functional hole (cable, dowel). Openings and
  engravings may carry `"note"`: str (shown in the drawings). Keep ≥ 1.5 mm
  (recommended 3 mm) of material between any opening/slot and an edge, and ≥ 1 mm between cut-outs.
  Every opening and hole must be wider than the material's kerf (table below): at least twice the kerf is safe.

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
{"id": str, "type": one of ['tab_slot', 'finger', 'cross_lap', 'butt', 'hinge', 'mitre'], "board": "<board A>", "into": "<board B>", ...}
```
Board A is `"board"`, board B is `"into"`. Edge directions (`"+x"`, `"-y"`, …) name a side of the board's (unrotated) box.

**Glue-free joints** (allowed with `"joinery": "interlocking"`):
- `tab_slot` — T-junction: an END FACE of A sits flat on the BROAD FACE of B, **away from B's edges**. The generator adds
  tabs on A's edge and cuts matching slots through B (slot = A's thickness + `clearance`). Options:
  `"tabs"`: 1..12 (default one per ~250 mm of contact, max 6), `"tab_width"`: mm (default about half the tab spacing,
  at least max(3 mm, A's thickness)), `"tab_depth"`: mm (default B's thickness = flush with B's far face; larger
  makes the tab stand proud on purpose), `"edge"`: which side of A carries the tabs (default: the side touching B).
  Across A's thickness, A must be inset from B's edges by ≥ 1.5 mm (recommended ≥ 3 mm; use ≥ the board
  thickness for furniture) — at the edge it is a `finger` corner instead. Along the contact A may run right up to B's
  edges (a shelf can be as deep as the sides): tabs stay A's thickness away from both ends automatically, so the contact must be longer than
  2 × A's thickness + max(3 mm, A's thickness).
- `finger` — box corner: A's end face sits on B's face **flush with one of B's edges** (within 0.25 mm), e.g. walls
  meeting at a box corner or a wall standing on the edge of a base. Draw both as plain boxes that just meet (A ends at
  B's face); the generator cuts alternating fingers into both along the corner: A's fingers are B's thickness deep, B's
  notches are A's thickness deep and `clearance` wider. Options: `"fingers"`: odd count 3..41 (an even count is rounded up;
  default: fingers about 3 × the thicker board long, at least 10 mm), `"edge"`: A's side at the corner. Each finger must
  be at least max(3 mm, half of A's thickness) long, or the corner is too short. Which board is
  `"board"` and which `"into"` does not matter (a reversed pair is swapped with a warning). Three boards meeting at one
  corner (e.g. side + top + back of a cabinet) are fine: give each pair its own finger connection; the overlapping cuts
  are resolved exactly.
- `cross_lap` — egg-crate / halving: two perpendicular boards drawn **passing through each other** (dividers in a grid).
  Each gets a notch half the crossing height deep and the other board's thickness + `clearance` wide, cut from opposite
  edges. One board must end at the top of the crossing and the other at its bottom (within 0.25 mm), e.g. both the
  same height; each must stick out > 1.5 mm past the other's faces. The order of the two boards does not matter.
- `finger` and `cross_lap` boards must be plain rectangles (no `profile`, no `rotate`). Profiled or tilted boards join
  with `tab_slot`: e.g. inset the walls from a pitched gable's edges and tab them into its face (as in the cottage
  example), and tab the gables' sloped edges into the roof panels.

**Joints that need `"joinery": "glue_allowed"`:**
- `butt` — A's end face against B's face, glued and/or held by `"fasteners"`: `{"kind": one of ['screw', 'confirmat', 'dowel'],
  "count"?: 1..20, "diameter"?: 2..20 mm, "length"?: 5..200 mm}` or just the kind as a string (`"fasteners": "screw"`).
  Catalogue: `screw` (Ø4 × 40 mm), `confirmat` (Ø7 × 50 mm), `dowel` (Ø8 × 35 mm).
- `hinge` — `"board"` = the door, `"into"` = the carcass board it hangs on, `"edge"` (required) = the door side that carries
  the hinges, optional `"count"`: 1..8 hinges, `"gap"`: 0..5 mm. Doors are **overlay** doors: draw the door in front of the
  carcass, its back face 0..`gap` mm (default 2) from the carcass front edges, covering the front edge of the board it
  hangs on (flush with that board's outer face; overhanging it is a warning). The door must be ≥
  16 mm thick for the 35 mm hinge cups. Do not connect the door to anything else.
- `mitre` — corner where two edges meet: `"edge"` (side of A) and `"into_edge"` (side of B), both required.
  **Draw each board up to the other board's mid-plane** (not to the outside corner): e.g. an 18 mm side
  `"position": [0, 0, 0], "size": [18, 141, 200]` and a top `"position": [9, 132, 0], "size": [291, 18, 200]` meet
  in a mitre with `"edge": "+y"` on the side and `"into_edge": "-x"` on the top. Drawn to the outside corner the two
  edges do not coincide and the joint is rejected. `"bevel"`
  defaults to **true** (both edges cut at half the corner angle, saw / CNC only); set `"bevel": false` for a plain corner.
  Optional `"fasteners"` as for butt.

One valid line per type:
```
{"id": "SIDE-TOP",  "type": "tab_slot",  "board": "SIDE-L", "into": "TOP", "tabs": 2}
{"id": "BOX-CORN",  "type": "finger",    "board": "LEFT",   "into": "BACK", "fingers": 5}
{"id": "GRID-1",    "type": "cross_lap", "board": "DIV-X",  "into": "DIV-Z1"}
{"id": "SHELF-FIX", "type": "butt",      "board": "SHELF",  "into": "SIDE-L", "fasteners": {"kind": "confirmat", "count": 2}}
{"id": "DOOR-HNG",  "type": "hinge",     "board": "DOOR",   "into": "SIDE-R", "edge": "+x", "count": 2, "gap": 2}
{"id": "FRAME-MT",  "type": "mitre",     "board": "RAIL",   "into": "STILE", "edge": "-x", "into_edge": "+y", "bevel": true}
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
  leave ≥ 3–4 mm of material each side of the bore (no fasteners into the edge of 6 mm boards or of hardboard /
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
- Every board must be held: joined to the product (directly or through others), or **resting on top of** a held board
  (a lift-off lid, a drawer standing on its runner, a stacked module). A board held by nothing is an error.
- A floor-standing product must not tip over when empty: its centre of mass must lie inside its floor footprint.
  A horizontal board held on one side only (a cantilever) is reported. For shelves fixed to a wall set
  `"product": {"mounting": "wall"}` and give the product a back rail or back panel at z = 0.
- These checks are geometric only; they do not prove strength under load.

## Geometry rules the generator validates (violations are compile errors)
1. **Touching, not overlapping:** for every connection A's end face must lie exactly on B's face (|gap| ≤ 0.25 mm).
   Account for board thickness: e.g. leg height = overall height − top thickness; a shelf between two sides is
   (inner width) = overall width − 2 × side thickness long.
2. **No overlaps:** boards may not occupy the same space anywhere (tabs inside their slots are fine).
3. **No unintended gaps:** a board meant to sit on/against another must touch it. Faces of unconnected boards that
   come within 2 mm of each other without touching are reported as a likely mistake (NEAR_MISS_GAP).
   Slots are cut 0.1 mm (material `clearance`) wider than the tab board; more than
   0.3 mm of extra play is rejected as a rattling joint.
4. Square to each other: boards are axis aligned unless they use `rotate`; tabs insert perpendicular to the receiving face.
5. Every board must fit on one stock sheet; standard thicknesses are preferred (table below).

## Material catalogue (type | standard thicknesses mm | kerf mm | grain | minimum part mm)
| type | thicknesses | kerf | grain | min part |
|---|---|---|---|---|
| `plywood` | 1, 2, 3, 4, 6, 9, 12, 15, 18, 21, 24, 27, 30 | 3.2 | yes | 15 |
| `mdf` | 1, 2, 3, 6, 9, 12, 15, 16, 18, 19, 22, 25, 30 | 3.2 | no | 15 |
| `particle_board` | 8, 10, 12, 16, 18, 19, 22, 25, 28, 30, 38 | 3.2 | no | 30 |
| `solid_wood` | 12, 15, 18, 20, 22, 25, 27, 30, 32, 38, 40, 45 | 3.2 | yes | 20 |
| `hardboard` | 1, 2, 2.5, 3, 3.2, 4, 5, 6 | 3.2 | no | 15 |
| `cardboard` | 1, 1.5, 2, 3, 4, 5, 6 | 0.2 | no | 5 |

## Native engine format (advanced)
The canvas also accepts the engine's own design JSON (top-level `"components"` + `"joints"` instead of `"boards"`):
local 2D outlines with `arcs`, features (`rect` / `circle` / `polygon`), `marks`, tabs by edge index and placements with
Euler XYZ rotation. It is what the Studio and the REST API use; prefer `board-design/v1` for new designs. Its joint types are `tab_slot`, `finger`,
`cross_lap`, `edge_butt`, `edge_mitre`, `face_lap` and `hinge` (`a`, `b`, plus `tab` for tab_slot and `a_edge` / `b_edge`
edge indices for the edge joints).

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
      "position": [-10, 0, -10],
      "size": [220, 6, 180],
      "profile": {
        "shape": "rect",
        "center": [110, 90],
        "width": 220,
        "height": 180,
        "corner_radius": 12
      }
    },
    {
      "id": "GABLE-B",
      "name": "Back gable",
      "group": "Walls",
      "position": [0, 6, 0],
      "size": [200, 220.02, 6],
      "profile": {
        "shape": "polygon",
        "points": [
          [0, 0],
          [200, 0],
          [200, 150],
          [100, 220.02],
          [0, 150]
        ]
      },
      "openings": [
        {
          "id": "heart",
          "kind": "opening",
          "shape": "path",
          "center": [100, 165, 3],
          "start": [0, -14],
          "segments": [
            {
              "line": [16, 2]
            },
            {
              "arc": {
                "to": [0, 10],
                "radius": 9,
                "large": true
              }
            },
            {
              "arc": {
                "to": [-16, 2],
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
      "position": [0, 6, 154],
      "size": [200, 220.02, 6],
      "profile": {
        "shape": "polygon",
        "points": [
          [0, 0],
          [200, 0],
          [200, 150],
          [100, 220.02],
          [0, 150]
        ]
      },
      "openings": [
        {
          "id": "door",
          "kind": "opening",
          "shape": "arch",
          "center": [100, 62, 157],
          "size": [50, 80]
        },
        {
          "id": "window",
          "kind": "opening",
          "shape": "circle",
          "center": [155, 120, 157],
          "diameter": 30
        },
        {
          "id": "vent",
          "kind": "opening",
          "shape": "regular_polygon",
          "center": [100, 175, 157],
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
            [60, 135],
            [140, 135]
          ]
        }
      ]
    },
    {
      "id": "SIDE-L",
      "name": "Left wall",
      "group": "Walls",
      "position": [10, 6, 6],
      "size": [6, 150, 148],
      "openings": [
        {
          "id": "win-l",
          "kind": "opening",
          "shape": "rect",
          "center": [13, 90, 80],
          "size": [40, 50],
          "corner_radius": 8
        }
      ]
    },
    {
      "id": "SIDE-R",
      "name": "Right wall",
      "group": "Walls",
      "position": [184, 6, 6],
      "size": [6, 150, 148],
      "engravings": [
        {
          "id": "planter",
          "kind": "pocket",
          "depth": 2,
          "shape": "rect",
          "center": [74, 40],
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
      "position": [-20, 156, -15],
      "size": [142.0775, 6, 190],
      "rotate": {
        "axis": "z",
        "angle": 35,
        "pivot": [0, 156, 0]
      }
    },
    {
      "id": "ROOF-R",
      "name": "Roof right",
      "group": "Roof",
      "position": [77.9225, 156, -15],
      "size": [142.0775, 6, 190],
      "rotate": {
        "axis": "z",
        "angle": -35,
        "pivot": [200, 156, 0]
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

## Complete valid example with several structures (desk organiser: finger corners, egg-crate, tabs)
```json
{
  "format": "board-design/v1",
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
      "position": [0, 0, 0],
      "size": [300, 6, 200]
    },
    {
      "id": "FRONT",
      "name": "Front wall",
      "group": "Box",
      "position": [0, 6, 194],
      "size": [300, 94, 6]
    },
    {
      "id": "BACK",
      "name": "Back wall",
      "group": "Box",
      "position": [0, 6, 0],
      "size": [300, 94, 6]
    },
    {
      "id": "LEFT",
      "name": "Left wall",
      "group": "Box",
      "position": [0, 6, 6],
      "size": [6, 94, 188]
    },
    {
      "id": "RIGHT",
      "name": "Right wall",
      "group": "Box",
      "position": [294, 6, 6],
      "size": [6, 94, 188]
    },
    {
      "id": "DIV-X",
      "name": "Long divider",
      "group": "Dividers",
      "position": [10, 6, 97],
      "size": [280, 70, 6]
    },
    {
      "id": "DIV-Z1",
      "name": "Cross divider 1",
      "group": "Dividers",
      "position": [97, 6, 10],
      "size": [6, 70, 180]
    },
    {
      "id": "DIV-Z2",
      "name": "Cross divider 2",
      "group": "Dividers",
      "position": [197, 6, 10],
      "size": [6, 70, 180]
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
```
