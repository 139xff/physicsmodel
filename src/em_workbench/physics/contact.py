"""Finite-radius contact constraints for visual charge particles.

The far-field model remains the ideal point-charge Coulomb law. These radii are
only used to prevent trajectory particles from numerically passing through the
visible metal-sphere charge markers at very small separations.
"""

STATIC_POINT_CHARGE_RADIUS_M = 0.005
MOVING_CHARGE_RADIUS_M = 0.001
POINT_CHARGE_CONTACT_RADIUS_M = STATIC_POINT_CHARGE_RADIUS_M + MOVING_CHARGE_RADIUS_M
