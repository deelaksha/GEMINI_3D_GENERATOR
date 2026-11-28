import json, copy, os, sys
S = os.path.dirname(os.path.abspath(__file__)) + '/cases'
M = {"name": "Ply 6", "type": "plywood", "thickness": 6}
def W(name, boards, conns=None, mat=M, **kw):
    d = {"format": "board-design/v1", "product": {"name": name}, "material": mat, "boards": boards}
    if conns is not None: d["connections"] = conns
    d.update(kw)
    json.dump(d, open(f"{S}/{name}.json", "w"), indent=1)
FLOOR = {"id": "FLOOR", "position": [0, 0, 0], "size": [200, 6, 200]}
WALL = {"id": "WALL", "position": [50, 6, 97], "size": [100, 100, 6]}
# --- geometry / transforms
W("T01_baseline_tabslot", [FLOOR, WALL], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
# free-standing rotated boards (no conns) to check transforms
W("T02_rotations", [
  {"id": "R1", "position": [0, 0, 0], "size": [100, 50, 6], "rotate": {"axis": "z", "angle": 30}},
  {"id": "R2", "position": [300, 0, 0], "size": [100, 50, 6], "rotate": [{"axis": "x", "angle": 90}, {"axis": "z", "angle": 90}]},
  {"id": "R3", "position": [600, 0, 0], "size": [100, 50, 6], "rotate": [{"axis": "z", "angle": 90}, {"axis": "x", "angle": 90}]},
  {"id": "R4", "position": [900, 0, 0], "size": [6, 50, 100], "rotate": {"axis": "y", "angle": 37, "pivot": [900, 0, 0]}},
  {"id": "R5", "position": [1200, 0, 0], "size": [100, 6, 80], "rotate": [{"axis": "x", "angle": 20}, {"axis": "y", "angle": 33}, {"axis": "z", "angle": -71}]},
  {"id": "R6", "position": [1500, 0, 0], "size": [6, 80, 100], "profile": {"shape": "polygon", "points": [[0,0],[80,0],[80,60],[40,100],[0,60]]}, "rotate": {"axis": "x", "angle": 25}}
], "auto")
W("T03_concave_L_profile", [{"id": "L", "position": [0, 0, 0], "size": [200, 6, 200],
   "profile": {"shape": "polygon", "points": [[0,0],[200,0],[200,100],[100,100],[100,200],[0,200]]}}])
W("T04_selfintersect_profile", [{"id": "BOW", "position": [0, 0, 0], "size": [100, 6, 100],
   "profile": {"shape": "polygon", "points": [[0,0],[100,100],[100,0],[0,100]]}}])
W("T05_profile_cw_winding", [{"id": "CW", "position": [0, 0, 0], "size": [200, 6, 200],
   "profile": {"shape": "polygon", "points": [[0,200],[100,200],[100,100],[200,100],[200,0],[0,0]]}}])
W("T06_profile_outside_box", [{"id": "OUT", "position": [0, 0, 0], "size": [100, 6, 100],
   "profile": {"shape": "polygon", "points": [[0,0],[120,0],[120,100],[0,100]]}}])
W("T07_opening_crosses_outline", [{"id": "P", "position": [0, 0, 0], "size": [200, 6, 200],
   "openings": [{"id": "o", "shape": "circle", "center": [190, 3, 100], "diameter": 40}]}])
W("T08_opening_touches_edge", [{"id": "P", "position": [0, 0, 0], "size": [200, 6, 200],
   "openings": [{"id": "o", "shape": "circle", "center": [180, 3, 100], "diameter": 40}]}])
W("T09_opening_in_L_notch", [{"id": "L", "position": [0, 0, 0], "size": [200, 6, 200],
   "profile": {"shape": "polygon", "points": [[0,0],[200,0],[200,100],[100,100],[100,200],[0,200]]},
   "openings": [{"id": "o", "shape": "circle", "center": [150, 3, 150], "diameter": 30}]}])
W("T10_opening_offplane", [{"id": "P", "position": [0, 0, 0], "size": [200, 6, 200],
   "openings": [{"id": "o", "shape": "circle", "center": [100, 50, 100], "diameter": 30}]}])
W("T11_selfintersect_opening", [{"id": "P", "position": [0, 0, 0], "size": [200, 6, 200],
   "openings": [{"id": "o", "shape": "polygon", "center": [100, 3, 100], "points": [[-20,-20],[20,20],[20,-20],[-20,20]]}]}])
W("T12_opening_on_rotated_board", [{"id": "P", "position": [0, 0, 0], "size": [200, 6, 200], "rotate": {"axis": "x", "angle": 30},
   "openings": [{"id": "o", "shape": "circle", "center": [100, 3, 100], "diameter": 30}]}])
# --- collisions
W("C1_rotated_parallel_aabb_overlap_no_solid", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}},
  {"id": "B", "position": [14, 0, -14], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}}], [])
W("C2_board_in_L_notch", [
  {"id": "L", "position": [0, 0, 0], "size": [200, 6, 200], "profile": {"shape": "polygon", "points": [[0,0],[200,0],[200,100],[100,100],[100,200],[0,200]]}},
  {"id": "POST", "position": [150, -40, 130], "size": [6, 80, 40]}], [])
W("C3_tilted_X_cross", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": 30}},
  {"id": "B", "position": [0, 0, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": -30}}], [])
W("C4a_discs_coplanar_corner_boxes", [
  {"id": "D1", "position": [0, 0, 0], "size": [100, 6, 100], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}},
  {"id": "D2", "position": [90, 0, 90], "size": [100, 6, 100], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}}], [])
W("C4b_disc_perp_corner", [
  {"id": "D1", "position": [0, 0, 0], "size": [100, 6, 100], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}},
  {"id": "D2", "position": [-50, -47, 5], "size": [100, 100, 6], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}}], [])
W("C5_axis_aligned_true_overlap", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 200]},
  {"id": "B", "position": [50, -20, 50], "size": [6, 100, 100]}], [])
W("C6_tilted_thin_sliver", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100]},
  {"id": "B", "position": [0, 5, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": 1, "pivot": [0, 5, 0]}}], [])
# --- joints
W("J01_finger_corner", [{"id": "BASE", "position": [0,0,0], "size": [200,6,100]}, {"id": "SIDE", "position": [0,6,0], "size": [6,100,100]}],
  [{"id": "F", "type": "finger", "board": "SIDE", "into": "BASE"}])
W("J02_cross_lap", [{"id": "A", "position": [0,0,47], "size": [200,60,6]}, {"id": "B", "position": [97,0,0], "size": [6,60,100]}],
  [{"id": "X", "type": "cross_lap", "board": "A", "into": "B"}])
W("J03_butt", [FLOOR, WALL], [{"id": "B", "type": "butt", "board": "WALL", "into": "FLOOR", "fasteners": "screw"}], joinery="glue_allowed")
W("J04_hinge", [
  {"id": "SIDE", "position": [0,0,0], "size": [18,400,300]},
  {"id": "DOOR", "position": [0,0,302], "size": [300,400,18]}],
  [{"id": "H", "type": "hinge", "board": "DOOR", "into": "SIDE", "edge": "-x", "count": 2, "gap": 2}],
  mat={"name": "Ply 18", "type": "plywood", "thickness": 18}, joinery="glue_allowed")
W("J05_mitre", [{"id": "SIDE", "position": [0,0,0], "size": [18,141,200]}, {"id": "TOP", "position": [9,132,0], "size": [291,18,200]}],
  [{"id": "M", "type": "mitre", "board": "SIDE", "into": "TOP", "edge": "+y", "into_edge": "-x"}],
  mat={"name": "Ply 18", "type": "plywood", "thickness": 18}, joinery="glue_allowed")
W("J06_duplicate_slot_opposite_sides", [
  {"id": "FLOOR", "position": [0,0,0], "size": [300,6,200]},
  {"id": "L", "position": [0,6,0], "size": [6,200,200]},
  {"id": "SHELF", "position": [6,100,0], "size": [200,6,200]},
  {"id": "BELOW", "position": [100,6,40], "size": [6,94,120]},
  {"id": "ABOVE", "position": [100,106,40], "size": [6,94,120]}],
  [{"id": "L-F", "type": "tab_slot", "board": "L", "into": "FLOOR"},
   {"id": "S-L", "type": "tab_slot", "board": "SHELF", "into": "L"},
   {"id": "BEL-F", "type": "tab_slot", "board": "BELOW", "into": "FLOOR"},
   {"id": "BEL-S", "type": "tab_slot", "board": "BELOW", "into": "SHELF"},
   {"id": "ABV-S", "type": "tab_slot", "board": "ABOVE", "into": "SHELF"}])
W("J07_tab_edge_outside_receiver_profile", [
  {"id": "DISC", "position": [0,0,0], "size": [200,6,200], "profile": {"shape": "circle", "center": [100,100], "diameter": 200}},
  {"id": "WALL", "position": [10,6,97], "size": [180,80,6]}],
  [{"id": "W-D", "type": "tab_slot", "board": "WALL", "into": "DISC", "tabs": 3}])
W("J07b_wall_over_L_notch", [
  {"id": "L", "position": [0,0,0], "size": [200,6,200], "profile": {"shape": "polygon", "points": [[0,0],[200,0],[200,100],[100,100],[100,200],[0,200]]}},
  {"id": "WALL", "position": [20,6,150], "size": [160,80,6]}],
  [{"id": "W-L", "type": "tab_slot", "board": "WALL", "into": "L", "tabs": 3}])
W("J08_tab_on_opening", [
  {"id": "FLOOR", "position": [0,0,0], "size": [200,6,200], "openings": [{"id": "big", "shape": "rect", "center": [100,3,100], "size": [120, 60]}]},
  dict(WALL)], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR", "tabs": 1}])
W("J09_slot_near_edge", [FLOOR, {"id": "WALL", "position": [50,6,193], "size": [100,100,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
W("J10_unknown_board", [FLOOR, WALL], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOR2"}])
W("J11_duplicate_board_id", [FLOOR, WALL, dict(WALL, position=[50,6,40])], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
W("J12_duplicate_conn_id", [FLOOR, WALL, {"id": "WALL2", "position": [50,6,40], "size": [100,100,6]}],
  [{"id": "C", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "C", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}])
W("J12b_duplicate_conn_id_finger", [{"id": "BASE", "position": [0,0,0], "size": [200,6,100]},
  {"id": "SIDE", "position": [0,6,0], "size": [6,100,100]}, {"id": "SIDE2", "position": [194,6,0], "size": [6,100,100]}],
  [{"id": "C", "type": "finger", "board": "SIDE", "into": "BASE"}, {"id": "C", "type": "finger", "board": "SIDE2", "into": "BASE"}])
W("J13_self_connection", [FLOOR, WALL], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "SELF", "type": "tab_slot", "board": "WALL", "into": "WALL"}])
W("J14_gap_5mm", [FLOOR, {"id": "WALL", "position": [50,11,97], "size": [100,100,6]}], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
W("J15_same_pair_two_types", [FLOOR, WALL], [{"id": "A1", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "A2", "type": "butt", "board": "WALL", "into": "FLOOR"}], joinery="glue_allowed")
W("J16_two_walls_same_place_same_side", [FLOOR, WALL, dict(WALL, id="WALL2")],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}])
W("J17_tilted_tabslot_gap", [
  {"id": "BASE", "position": [0,0,0], "size": [200,6,200]},
  {"id": "T", "position": [50,6,97], "size": [100,100,6], "rotate": {"axis": "x", "angle": 20, "pivot": [100, 6, 100]}}],
  [{"id": "T-B", "type": "tab_slot", "board": "T", "into": "BASE"}])
W("J18_tabs_close_together", [FLOOR, WALL, {"id": "WALL2", "position": [50,6,106], "size": [100,100,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}])
# --- assembly feasibility: closed box, all tab_slots / fingers
box = [{"id": "BOT", "position": [0,0,0], "size": [120,6,120]}, {"id": "TOP", "position": [0,106,0], "size": [120,6,120]},
       {"id": "LFT", "position": [10,6,10], "size": [6,100,100]}, {"id": "RGT", "position": [104,6,10], "size": [6,100,100]},
       {"id": "BCK", "position": [16,6,10], "size": [88,100,6]}, {"id": "FRT", "position": [16,6,104], "size": [88,100,6]}]
cn = [{"id": f"{a}-{b}", "type": "tab_slot", "board": a, "into": b} for a in ("LFT","RGT","BCK","FRT") for b in ("BOT","TOP")] + \
     [{"id": f"{a}-{b}", "type": "tab_slot", "board": a, "into": b} for a in ("BCK","FRT") for b in ("LFT","RGT")]
W("A1_closed_box_all_tabslot", box, cn)
W("A2_box_with_trapped_inner", box + [{"id": "INNER", "position": [40,6,40], "size": [40,40,6]}],
  cn + [{"id": "IN-B", "type": "tab_slot", "board": "INNER", "into": "BOT"}])
# --- connectivity
W("N1_isolated", [FLOOR, WALL, {"id": "FLOAT", "position": [500,200,0], "size": [50,6,50]}], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
W("N2_disconnected_group", [FLOOR, WALL, {"id": "G1", "position": [500,0,0], "size": [100,6,100]}, {"id": "G2", "position": [520,6,47], "size": [60,50,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "G", "type": "tab_slot", "board": "G2", "into": "G1"}])
W("N3_not_joined_touching", [FLOOR, WALL, {"id": "W2", "position": [50,6,40], "size": [100,100,6]}], [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
W("N4_unattached_failed_conn", [FLOOR, WALL, {"id": "W2", "position": [50,10,40], "size": [100,100,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "W2", "into": "FLOOR"}])
W("N5_tilted_aabb_touch_not_solid", [
  {"id": "FLOOR", "position": [0,0,0], "size": [300,6,300]},
  {"id": "WALL", "position": [50,6,147], "size": [100,100,6]},
  {"id": "TILT", "position": [160,60,100], "size": [100,6,100], "rotate": {"axis": "z", "angle": 45}}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}])
print("ok")
W("C1_rotated_parallel_aabb_overlap_no_solid", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}},
  {"id": "B", "position": [14, 0, 14], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}}], [])
W("C1b_rotated_parallel_coplanar_overlap", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}},
  {"id": "B", "position": [14, 0, -14], "size": [200, 100, 6], "rotate": {"axis": "y", "angle": 45}}], [])
W("C4b_disc_perp_corner", [
  {"id": "D1", "position": [0, 0, 0], "size": [100, 6, 100], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}},
  {"id": "D2", "position": [-80, -47, 0], "size": [100, 100, 6], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}}], [])
W("C4c_disc_perp_true_overlap", [
  {"id": "D1", "position": [0, 0, 0], "size": [100, 6, 100], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}},
  {"id": "D2", "position": [-50, -47, 5], "size": [100, 100, 6], "profile": {"shape": "circle", "center": [50, 50], "diameter": 100}}], [])
W("C6b_shallow_tilt_3mm_penetration", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100]},
  {"id": "B", "position": [0, 3, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": 2, "pivot": [0, 3, 0]}}], [])
W("C6c_tilt_10deg_3mm_penetration", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100]},
  {"id": "B", "position": [0, 3, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": 10, "pivot": [0, 3, 0]}}], [])
W("C6d_tilt_30deg_3mm_penetration", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100]},
  {"id": "B", "position": [0, 3, 0], "size": [200, 6, 100], "rotate": {"axis": "z", "angle": 30, "pivot": [0, 3, 0]}}], [])
W("C7_board_in_slot_gap_parallel_close", [
  {"id": "A", "position": [0, 0, 0], "size": [200, 6, 100]},
  {"id": "B", "position": [50, 5, 20], "size": [100, 6, 60]}], [])
W("K1_coplanar_overlap_consolidated", [FLOOR, WALL, {"id": "WALL2", "position": [100,6,97], "size": [100,80,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}])
W("K2_coplanar_overlap_no_consolidate", [FLOOR, WALL, {"id": "WALL2", "position": [100,6,97], "size": [100,80,6]}],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}], consolidate=False)
W("K3_identical_dup_no_consolidate", [FLOOR, WALL, dict(WALL, id="WALL2")],
  [{"id": "W-F", "type": "tab_slot", "board": "WALL", "into": "FLOOR"}, {"id": "W2-F", "type": "tab_slot", "board": "WALL2", "into": "FLOOR"}], consolidate=False)
W("J07c_wall_edge_partly_off_disc_1tab", [
  {"id": "DISC", "position": [0,0,0], "size": [200,6,200], "profile": {"shape": "circle", "center": [100,100], "diameter": 200}},
  {"id": "WALL", "position": [10,6,20], "size": [180,80,6]}],
  [{"id": "W-D", "type": "tab_slot", "board": "WALL", "into": "DISC", "tabs": 1}])
W("J07d_wall_edge_partly_off_disc_3tab", [
  {"id": "DISC", "position": [0,0,0], "size": [200,6,200], "profile": {"shape": "circle", "center": [100,100], "diameter": 200}},
  {"id": "WALL", "position": [10,6,20], "size": [180,80,6]}],
  [{"id": "W-D", "type": "tab_slot", "board": "WALL", "into": "DISC", "tabs": 3}])
W("J07e_wall_over_L_notch_1tab", [
  {"id": "L", "position": [0,0,0], "size": [200,6,200], "profile": {"shape": "polygon", "points": [[0,0],[200,0],[200,100],[100,100],[100,200],[0,200]]}},
  {"id": "WALL", "position": [20,6,150], "size": [160,80,6]}],
  [{"id": "W-L", "type": "tab_slot", "board": "WALL", "into": "L", "tabs": 1, "tab_width": 20}])
fb = [{"id": "BOT", "position": [0,0,0], "size": [120,6,120]}, {"id": "TOP", "position": [0,106,0], "size": [120,6,120]},
      {"id": "LFT", "position": [0,6,0], "size": [6,100,120]}, {"id": "RGT", "position": [114,6,0], "size": [6,100,120]},
      {"id": "BCK", "position": [6,6,0], "size": [108,100,6]}, {"id": "FRT", "position": [6,6,114], "size": [108,100,6]}]
W("A3_six_sided_finger_box", fb, "auto")
# X locked between two tabs from opposite directions plus top/bottom
W("A4_cross_tabs_lock", [
  {"id": "BASE", "position": [0,0,0], "size": [200,6,200]},
  {"id": "LFT", "position": [40,6,40], "size": [6,100,120]},
  {"id": "RGT", "position": [154,6,40], "size": [6,100,120]},
  {"id": "MID", "position": [46,50,40], "size": [108,6,120]},
  {"id": "CAP", "position": [20,106,20], "size": [160,6,160]}],
  [{"id": "L-B", "type": "tab_slot", "board": "LFT", "into": "BASE"}, {"id": "R-B", "type": "tab_slot", "board": "RGT", "into": "BASE"},
   {"id": "M-L", "type": "tab_slot", "board": "MID", "into": "LFT"}, {"id": "M-R", "type": "tab_slot", "board": "MID", "into": "RGT"},
   {"id": "L-C", "type": "tab_slot", "board": "LFT", "into": "CAP"}, {"id": "R-C", "type": "tab_slot", "board": "RGT", "into": "CAP"}])
W("E1_radial_spokes_hub_overlap", [
  {"id": "BASE", "position": [-150,0,-150], "size": [300,6,300]},
  {"id": "SPOKE", "position": [-3,6,-100], "size": [6,80,200], "radial": {"count": 3, "axis": "y", "center": [0,6,0]}}], "auto")
W("E2_mirror_profile", [
  {"id": "BASE", "position": [0,0,0], "size": [300,6,200]},
  {"id": "SIDE", "position": [20,6,20], "size": [6,100,160], "profile": {"shape": "polygon", "points": [[0,0],[160,0],[160,60],[0,100]]},
   "mirror": {"axis": "x", "at": 150}}],
  [{"id": "S-B", "type": "tab_slot", "board": "SIDE", "into": "BASE"}])
M18 = {"name": "Ply 18", "type": "plywood", "thickness": 18}
for w in (5, 10, 15, 25):
    W(f"C8_large_parallel_strip_{w}mm", [
      {"id": "A", "position": [0,0,0], "size": [2400,18,1200]},
      {"id": "B", "position": [0,9,1200 - w], "size": [2400,18,300]}], [], mat=M18, consolidate=False)
