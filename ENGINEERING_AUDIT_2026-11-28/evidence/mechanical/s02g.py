from lib import *
import json
d = json.load(open('json/s02b_gears_ok_phased.json'))
d['boards'][2]['profile']['pressure_angle'] = 28
run('s02g_gears_pressure_angle_mismatch', d)
d = json.load(open('json/s02b_gears_ok_phased.json'))
d['boards'][1] = gear_xz('G1', 6, 3, 0, 0); d['boards'][2] = gear_xz('G2', 30, 3, 54, 0)
d['motions'][1]['pivot'] = [54, 6, 0]
run('s02h_gears_6_teeth_pinion', d)
