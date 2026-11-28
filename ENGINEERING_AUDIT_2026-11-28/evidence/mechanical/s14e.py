from lib import *
BASE = {'id': 'BASE', 'position': [-200, 0, -200], 'size': [600, 6, 400]}
A = {'id': 'ARM-A', 'position': [-160, 6, -8], 'size': [170, 6, 16]}     # pivot (0,0), points -x
B = {'id': 'ARM-B', 'position': [190, 6, -8], 'size': [170, 6, 16]}      # pivot (200,0), points +x
run('s14e_two_independent_arms_meet', design([BASE, A, B], [rot('a', ['ARM-A'], [0, 6, 0], rng=(0, 180)),
                                                            rot('b', ['ARM-B'], [200, 6, 0], rng=(-180, 0))]))
