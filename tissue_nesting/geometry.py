from __future__ import annotations

from collections.abc import Iterable
from math import isclose

from shapely import affinity
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from .models import Fabric, Piece

EPSILON = 1e-7
CIRCLE_RESOLUTION = 48


def base_geometry(piece: Piece) -> BaseGeometry:
    piece.validate()
    if piece.kind == "rectangle":
        return box(0, 0, float(piece.width), float(piece.height))
    if piece.kind == "triangle":
        return Polygon([(0, 0), (float(piece.width), 0), (0, float(piece.height))])
    if piece.kind == "polygon":
        polygon = Polygon(piece.points)
        if not polygon.is_valid or polygon.area <= EPSILON:
            raise ValueError("Le polygone est invalide ou son aire est nulle.")
        return normalize_geometry(polygon)
    if piece.kind == "circle":
        radius = float(piece.width) / 2.0
        return normalize_geometry(Point(0, 0).buffer(radius, quad_segs=CIRCLE_RESOLUTION))
    if piece.kind == "oval":
        ellipse = affinity.scale(
            Point(0, 0).buffer(1, quad_segs=CIRCLE_RESOLUTION),
            xfact=float(piece.width) / 2.0,
            yfact=float(piece.height) / 2.0,
            origin=(0, 0),
        )
        return normalize_geometry(ellipse)
    raise ValueError(f"Type de piece inconnu: {piece.kind}")


def normalize_geometry(geometry: BaseGeometry) -> BaseGeometry:
    minx, miny, _, _ = geometry.bounds
    return affinity.translate(geometry, xoff=-minx, yoff=-miny)


def oriented_geometry(piece: Piece, rotation: float) -> BaseGeometry:
    geometry = base_geometry(piece)
    angle = normalized_angle(rotation)
    if not isclose(angle, 0.0, abs_tol=EPSILON):
        geometry = affinity.rotate(geometry, angle, origin=(0, 0), use_radians=False)
    return normalize_geometry(geometry)


def transformed_geometry(piece: Piece, x: float, y: float, rotation: float) -> BaseGeometry:
    geometry = oriented_geometry(piece, rotation)
    return affinity.translate(geometry, xoff=x, yoff=y)


def dimensions(geometry: BaseGeometry) -> tuple[float, float]:
    minx, miny, maxx, maxy = geometry.bounds
    return maxx - minx, maxy - miny


def effective_rotations(piece: Piece) -> list[float]:
    if piece.kind == "circle":
        return [0.0]

    has_explicit_rotations = bool(piece.allowed_rotations)
    if not piece.can_rotate:
        rotations = [0.0]
    elif has_explicit_rotations:
        rotations = [normalized_angle(angle) for angle in piece.allowed_rotations]
    elif piece.respect_grain:
        rotations = [0.0, 180.0]
    else:
        rotations = [0.0, 90.0, 180.0, 270.0]

    if piece.respect_grain:
        rotations = [
            angle for angle in rotations if isclose(angle % 180.0, 0.0, abs_tol=EPSILON)
        ]
    unique = unique_angles(rotations)
    if not unique and not has_explicit_rotations:
        return [0.0]
    return unique


def unique_angles(angles: Iterable[float]) -> list[float]:
    unique: list[float] = []
    for angle in angles:
        normalized = normalized_angle(angle)
        if not any(isclose(normalized, existing, abs_tol=EPSILON) for existing in unique):
            unique.append(normalized)
    return unique


def normalized_angle(angle: float) -> float:
    normalized = float(angle) % 360.0
    if isclose(normalized, 360.0, abs_tol=EPSILON) or isclose(
        normalized, 0.0, abs_tol=EPSILON
    ):
        return 0.0
    return normalized


def within_fabric(geometry: BaseGeometry, fabric: Fabric) -> bool:
    minx, miny, maxx, maxy = geometry.bounds
    if minx < -EPSILON or miny < -EPSILON:
        return False
    if maxy > fabric.width + EPSILON:
        return False
    if fabric.length_limit is not None and maxx > fabric.length_limit + EPSILON:
        return False
    return True


def violates_spacing(
    candidate: BaseGeometry, placed_geometries: Iterable[BaseGeometry], spacing: float
) -> bool:
    for other in placed_geometries:
        if candidate.intersection(other).area > EPSILON:
            return True
        if spacing > EPSILON and candidate.distance(other) < spacing - EPSILON:
            return True
    return False


def iter_polygons(geometry: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for geom in geometry.geoms:
            yield from iter_polygons(geom)
