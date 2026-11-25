"""
Living hinge (kerf bending) pattern: rows of through-cuts with bridges, alternate rows offset by half a step, so a
flat board bends across the rows. Bending itself is not simulated: the board stays flat in 3D and in every check.
"""


def hinge_defaults(t):
    """Spacing between rows, cut length and bridge length (mm) that suit a board of thickness t."""
    return {'spacing': max(1.0, round(0.5 * t, 2)), 'cut': 20.0, 'bridge': max(2.0, float(t))}


def hinge_lines(u0, v0, u1, v1, along, spacing, cut, bridge):
    """Cut segments [[u, v], [u, v]] (face mm) filling the rectangle u0..u1 x v0..v1, cuts running along `along`."""
    (a0, a1), (b0, b1) = ((u0, u1), (v0, v1)) if along == 'u' else ((v0, v1), (u0, u1))
    step = cut + bridge
    lines, row, b = [], 0, b0
    while b <= b1 + 1e-9:
        pos = a0 - (step / 2 if row % 2 else 0.0)
        while pos < a1 - 1e-9:
            s, e = max(pos, a0), min(pos + cut, a1)
            if e - s > bridge / 2:          # no slivers at the row ends
                lines.append([[s, b], [e, b]] if along == 'u' else [[b, s], [b, e]])
            pos += step
        row += 1
        b += spacing
    return lines
