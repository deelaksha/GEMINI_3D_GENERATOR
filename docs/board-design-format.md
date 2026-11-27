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
  "connections": [connection, ...],
  "motions"?: [motion, ...]   (moving parts, see "Moving parts")
}
```
- `thickness` between 0.5 and 50 mm. `clearance` = extra width of every slot over the
  tab board thickness (default 0.1); `kerf` defaults from the material catalogue below.
- No fixed limit on the number of boards (very large designs take longer to check); coordinates within
  ±5000 mm.

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
{"shape": "gear", "center", "teeth": 6..100, "module": mm, "rotation"?: deg}   (involute spur gear, see "Gears")
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
  Engraved text: `{"kind": "engrave", "text": "Max 120 chars", "position": [u, v], "height": mm, "align"?: "left"|"center"|"right"}`
  — single-stroke letters (capitals, digits, common punctuation) with the baseline starting at `position`; `height` is
  the capital height (each character is about `height` wide). Raster images (`"kind": "image"`, `"src": data URI`,
  `"position"`, `"size"`) are added by the user in the app; never write them yourself.
- `"living_hinge": {"from": [u, v], "to": [u, v], "lines_along": "u"|"v", "spacing"?: mm, "cut"?: mm, "bridge"?: mm}`
  (or a list) — a laser kerf-bending pattern: staggered through-cuts filling that face rectangle so the board can be
  bent across the cuts (rounded box corners, lamp shades). `lines_along` is the face axis the cuts run along (the bend
  axis). Defaults: spacing half the thickness, 20 mm cuts, bridges = thickness. Keep it at least one thickness inside
  the board edges. The board stays flat in this design (bending is not simulated): model the flat panel.
- `"repeat": {"count": 2 or more, "step": [dx, dy, dz]}` on a board builds an array of copies `"<id>-1"` .. `"<id>-n"`
  (shelves, slats, fins, ribs), each moved by `step` from the previous. A connection naming the board applies to every
  copy; two repeated boards with the same count connect copy by copy. Refer to a single copy by its generated id.
- `"mirror": {"axis": "x"|"y"|"z", "at": mm}` on a board also builds its mirror image `"<id>-M"` across the plane
  axis = at (left/right sides, symmetric gables). Profiles, openings, engravings, hinges and tilts are mirrored; text
  stays readable. Its connections are mirrored automatically: never write connections to `"<id>-M"` yourself.
- Top level `"assemblies": [{"id", "boards": [...], "connections": [...], "motions"?: [...]}]` with `"instances":
  [{"assembly", "id", "offset": [x, y, z], "flip"?, "rotate"?, "repeat"?, "mirror"?}]` reuses a sub-assembly (seats,
  drawers, window bays, modules, legs): every instance gets copies of the assembly's boards named
  `"<instance id>-<board id>"`, with its internal connections and motions; connect instance boards to the rest by those
  names under the top-level `"connections"`. Design the assembly around its own origin [0, 0, 0]; each instance is
  flipped, then turned, then moved by `offset`:
  - `"flip": "x"|"y"|"z"` (or a list): a mirror-image copy in place (a left-hand version of a right-hand module).
  - `"rotate": {"axis", "angle"}` (or a list of steps): multiples of 90° are exact - every board stays square and
    every joint type works (seats facing a stage from all four sides: angles 0, 90, 180, 270 about y). Any other angle
    tilts the whole copy about its origin (a fan of seats around a circle); finger and cross_lap joints inside it cannot
    follow a tilt, so use tab_slot there. An assembly with motions can only be turned by multiples of 90°.
- Top level `"plan": {"reference"?: [...], "datums"?: [...], "concept"?: str, "economy"?: str, "joints"?: [...], "audit"?: [...], "assemblies": [...], "steps": [...], "checks": [...],
  "reference"?: [...]}` is your design plan, written before `"boards"` ("reference": what attached reference images
  show); the compiler ignores it.
- `"rotate": {"axis": "x"|"y"|"z", "angle": degrees, "pivot"?: [x, y, z]}` tilts a board (roof panels, sloped backs,
  lecterns). It is applied **last**: `position`/`size`, profile, openings, engravings and `"edge"` directions all describe
  the board before rotating; `pivot` defaults to the box centre. Positive angles turn counter-clockwise looking down
  the axis (about z: +x turns towards +y).
- A compound tilt is a LIST of 1-3 such steps applied in order, each about its own pivot (default: the board's centre
  at that moment): `"rotate": [{"axis": "x", "angle": 28, "pivot": [...]}, {"axis": "z", "angle": 8, "pivot": [...]}]`
  - a roof corner that lifts (flared eaves), a hip piece, a canted panel. Everything else about tilted boards applies.
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

## Fewer, smarter boards (consolidation) - visual detail is not piece count
Judge a design by realism, strength, function and ease of assembly - NOT by how many boards it has. Detail that lies
in one plane belongs in ONE board: its outline, its cut-out openings and its engravings carry the detail.
- A fence or railing = one panel per straight run: a top and bottom rail with the posts between them, the gaps as
  openings (a pointed or shaped picket top = the panel's polygon "profile"). Never 30 separate posts.
- A lattice / shoji window or a grille = one panel with a grid of openings; a decorative wall panel, border or
  frieze = one board with openings and engravings; repeated roof-edge ornaments = one strip per roof edge; a tree
  or bush = a few interlocking silhouette boards (cross_lap them for volume), not dozens of twigs.
- Write repeated cut-outs once: an opening with `"repeat": {"count": n, "step": [dx, dy, dz]}` (and
  `"rows": {"count": m, "step": [dx, dy, dz]}` for a grid) is cut n (x m) times, ids "<id>-1".. ("<id>-<row>-<n>").
- Keep separate only what must be: parts in another plane (real 3D depth - roof layers, overlapping tiers, bracket
  stacks), moving parts, different colours / materials / thickness, and a run too big for the stock board (split it
  into a few modules, joined to the structure - not into hundreds of pieces).
- The compiler consolidates for you as a safety net (`"consolidate"`, on by default; `false` only reports): flat
  boards (plain or shaped with a "profile" - pickets, arches, discs, silhouettes; not tilted, not gears) of one
  thickness, material and colour that lie in one plane and share an edge are cut as one board - their united
  outline, enclosed gaps as openings - and the connections between them are dropped (CONSOLIDATED, with the counts).
  A repeated board joins only as a whole; pieces meeting only at a point stay apart. Better: draw the panel yourself.
```jsonc
{"id": "FENCE-N", "position": [0, 6, 0], "size": [400, 110, 6],
 "profile": {"shape": "polygon", "points": [[0, 0], [400, 0], [400, 100], [390, 110], [380, 100], [10, 100], [0, 110]]},
 "openings": [{"id": "gap", "kind": "opening", "shape": "rect", "center": [30, 55, 3], "size": [24, 70],
               "repeat": {"count": 12, "step": [31, 0, 0]}}]}
```

## Moving parts (motions) - checked through their whole travel and animated in 3D
```
"motions": [
  {"id": str, "type": "rotate", "boards": [ids that turn together], "on": board id, "axis": "x"|"y"|"z",
   "pivot": [x, y, z], "range": [from, to] (degrees), "axle"?: {"diameter": mm}},
  {"id": str, "type": "slide", "boards": [ids], "on": board id, "direction": "x"|"y"|"z", "range": [from, to] (mm)}
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
{"id": "spin", "type": "rotate", "boards": ["DISK", "DISK-RIM"], "on": "BASE", "axis": "y", "pivot": [150, 6, 150],
 "range": [0, 360], "axle": {"diameter": 8}},
{"id": "drawer", "type": "slide", "boards": ["DR-FRONT", "DR-BOTTOM", "DR-SIDE-L", "DR-SIDE-R", "DR-BACK"], "on": "RUNNER",
 "direction": "z", "range": [0, 250]}
```

## Gears (gear trains, clocks, music boxes, kinetic sculptures)
A gear is a board whose `"profile"` is `{"shape": "gear", "center": [u, v], "teeth": z, "module": m, "rotation"?: deg}`:
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
{"id": "G1", "position": [47, 6, 67], "size": [66, 6, 66], "profile": {"shape": "gear", "center": [33, 33], "teeth": 20, "module": 3}},
{"id": "G2", "position": [107, 6, 52], "size": [96, 6, 96], "profile": {"shape": "gear", "center": [48, 48], "teeth": 30, "module": 3, "rotation": 6}},
"motions": [
  {"id": "drive", "type": "rotate", "boards": ["G1"], "on": "BASE", "axis": "y", "pivot": [80, 6, 100], "range": [0, 360], "axle": {"diameter": 6}},
  {"id": "follow", "type": "rotate", "boards": ["G2"], "on": "BASE", "axis": "y", "pivot": [155, 6, 100], "driven_by": "drive", "axle": {"diameter": 6}}
]
```

## Linkages: one crank drives everything (connecting rods, rockers, sliders)
A real mechanism has ONE input - a hand crank or a motor shaft - and every other movement is pushed by actual parts.
A motion driven through a connecting rod has `"driven_by": "<crank motion id>"` and, instead of a ratio, a `"link"`:
`{"rod": "<rod board id>", "from": [x, y, z] (pin on the crank), "to": [x, y, z] (pin on this motion's boards),
"pin"?: {"diameter": mm, default 4}}`. The rod is an ordinary board (a bar with a "polygon" or rounded profile) that
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
{"id": "BASE", "position": [0, 0, 0], "size": [420, 320, 6]},
{"id": "CRANK", "position": [70, 120, 6], "size": [60, 60, 6], "profile": {"shape": "circle", "center": [30, 30], "diameter": 60}},
{"id": "ARM", "position": [290, 140, 6], "size": [20, 90, 6]},
{"id": "ROD", "position": [106, 137, 12], "size": [208, 96, 6], "profile": {"shape": "polygon", "points": [[7.6, 1.9], [206.2, 79.2], [200.4, 94.1], [1.8, 16.8]]}},
"motions": [
  {"id": "crank", "type": "rotate", "boards": ["CRANK"], "on": "BASE", "axis": "z", "pivot": [100, 150, 6], "range": [0, 360], "axle": {"diameter": 6}},
  {"id": "flap", "type": "rotate", "boards": ["ARM"], "on": "BASE", "axis": "z", "pivot": [300, 150, 6], "axle": {"diameter": 6},
   "driven_by": "crank", "link": {"rod": "ROD", "from": [120, 150, 12], "to": [300, 220, 12]}}
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
{"id": "R-F", "position": [30, 81, 141], "size": [300, 3, 102],
  "rotate": {"axis": "x", "angle": 28.0725, "pivot": [30, 81, 243]},
  "profile": {"shape": "polygon", "points": [[0, 102], [300, 102], [210, 0], [90, 0]]}},
{"id": "TRUSS-1", "position": [150, 81, 78], "size": [3, 48, 150],
  "profile": {"shape": "polygon", "points": [[0, 0], [0, 150], [8, 150], [48, 75], [8, 0]]}},
{"id": "TILE-F1", "position": [70, 84, 236], "size": [40, 4, 3],
  "rotate": {"axis": "x", "angle": 28.0725, "pivot": [30, 81, 243]},
  "profile": {"shape": "polygon", "points": [[0, 0], [40, 0], [40, 3], [38, 4], [36, 3], [34, 4], [32, 3], [0, 3]]}}
```
(connections: TRUSS-1 -> CEILING, TRUSS-1 -> R-F, TILE-F1 -> R-F, all `tab_slot`; the truss's profile is [height,
depth] because it is thin along x: face coordinates follow the in-plane axes in x, y, z order.)

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
This first example only shows the syntax and is deliberately plain. The cottage example after it shows the least
shaping a finished design needs (profiles, arches, tilted roof); DESIGN QUALITY asks for more.
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
      "size": [200, 220, 6],
      "profile": {
        "shape": "polygon",
        "points": [
          [0, 0],
          [200, 0],
          [200, 150],
          [100, 220],
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
      "size": [200, 220, 6],
      "profile": {
        "shape": "polygon",
        "points": [
          [0, 0],
          [200, 0],
          [200, 150],
          [100, 220],
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
      "size": [142, 6, 190],
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
      "position": [78, 156, -15],
      "size": [142, 6, 190],
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

## Complete valid example of the working method (torii gate cloned from a reference)
How a finished answer looks: "plan" holds the scale calibration, grid readings, the counted inventory, the datums with
a dimension chain and the tick-off; the whole front silhouette (pillars, tie beam, plaque strut, lintels with the
upswept tips traced point by point) is ONE panel whose enclosed gaps are openings; front pieces give the pillars depth.
```json
{
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
```
