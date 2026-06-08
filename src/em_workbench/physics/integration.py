from __future__ import annotations

import math
from dataclasses import dataclass

from em_workbench.models import DiskSource, LineSegmentSource, RingSource
from em_workbench.physics.vectors import Vector3, orthonormal_basis_from_normal


@dataclass(frozen=True)
class IntegratedChargeElement:
    position: Vector3
    charge_c: float


def line_charge_c(source: LineSegmentSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.linear_charge_density_c_per_m * source.length_m


def ring_charge_c(source: RingSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.linear_charge_density_c_per_m * (2.0 * math.pi * source.radius_m)


def disk_charge_c(source: DiskSource) -> float:
    if source.charge_c is not None:
        return source.charge_c
    return source.surface_charge_density_c_per_m2 * math.pi * source.radius_m**2


def gauss_legendre_nodes_weights(count: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if count < 1:
        raise ValueError("Gauss-Legendre quadrature requires at least one node.")
    nodes = [0.0] * count
    weights = [0.0] * count
    midpoint = (count + 1) // 2
    tolerance = 1.0e-15
    for index in range(midpoint):
        root = math.cos(math.pi * (index + 0.75) / (count + 0.5))
        derivative = 0.0
        while True:
            p_previous = 1.0
            p_current = root
            for order in range(2, count + 1):
                p_next = (
                    (2.0 * order - 1.0) * root * p_current
                    - (order - 1.0) * p_previous
                ) / order
                p_previous = p_current
                p_current = p_next
            derivative = count * (root * p_current - p_previous) / (root * root - 1.0)
            previous_root = root
            root = previous_root - p_current / derivative
            if abs(root - previous_root) <= tolerance:
                break
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        left = index
        right = count - 1 - index
        nodes[left] = -root
        nodes[right] = root
        weights[left] = weight
        weights[right] = weight
    return tuple(nodes), tuple(weights)


def line_segment_elements(
    source: LineSegmentSource,
    node_count: int,
) -> list[IntegratedChargeElement]:
    total_charge = line_charge_c(source)
    start = Vector3.from_position(source.position)
    axis = Vector3.from_position(source.orientation).normalized()
    nodes, weights = gauss_legendre_nodes_weights(node_count)
    return [
        IntegratedChargeElement(
            position=start + axis.scale(0.5 * source.length_m * (node + 1.0)),
            charge_c=0.5 * total_charge * weight,
        )
        for node, weight in zip(nodes, weights, strict=True)
    ]


def ring_elements(source: RingSource, segment_count: int) -> list[IntegratedChargeElement]:
    if segment_count < 1:
        raise ValueError("Ring quadrature requires at least one segment.")
    total_charge = ring_charge_c(source)
    center = Vector3.from_position(source.position)
    axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
        Vector3.from_position(source.normal)
    )
    dq = total_charge / segment_count
    elements: list[IntegratedChargeElement] = []
    for index in range(segment_count):
        angle = 2.0 * math.pi * (index + 0.5) / segment_count
        point = center + axis_u.scale(math.cos(angle) * source.radius_m)
        point = point + axis_v.scale(math.sin(angle) * source.radius_m)
        elements.append(IntegratedChargeElement(position=point, charge_c=dq))
    return elements


def disk_elements(
    source: DiskSource,
    radial_segments: int,
    angular_segments: int,
) -> list[IntegratedChargeElement]:
    if radial_segments < 1 or angular_segments < 1:
        raise ValueError("Disk quadrature requires positive radial and angular counts.")
    total_charge = disk_charge_c(source)
    surface_density = total_charge / (math.pi * source.radius_m**2)
    center = Vector3.from_position(source.position)
    axis_u, axis_v, _unit_normal = orthonormal_basis_from_normal(
        Vector3.from_position(source.normal)
    )
    radial_nodes, radial_weights = gauss_legendre_nodes_weights(radial_segments)
    dtheta = 2.0 * math.pi / angular_segments
    elements: list[IntegratedChargeElement] = []
    for radial_node, radial_weight in zip(radial_nodes, radial_weights, strict=True):
        radius = 0.5 * source.radius_m * (radial_node + 1.0)
        radial_weight_m = 0.5 * source.radius_m * radial_weight
        dq = surface_density * radius * radial_weight_m * dtheta
        for angular_index in range(angular_segments):
            angle = (angular_index + 0.5) * dtheta
            point = center + axis_u.scale(math.cos(angle) * radius)
            point = point + axis_v.scale(math.sin(angle) * radius)
            elements.append(IntegratedChargeElement(position=point, charge_c=dq))
    return elements
