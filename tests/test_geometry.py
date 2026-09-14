from __future__ import annotations

from tissue_nesting.geometry import (
    dimensions,
    effective_rotations,
    transformed_geometry,
    violates_spacing,
    within_fabric,
)
from tissue_nesting.models import Fabric, Piece


def test_respect_grain_filters_quarter_turns() -> None:
    piece = Piece(
        id="p1",
        name="Piece",
        kind="rectangle",
        width=100,
        height=50,
        respect_grain=True,
        allowed_rotations=[0, 90, 180, 270],
    )

    assert effective_rotations(piece) == [0.0, 180.0]


def test_explicit_rotations_are_not_replaced_when_grain_filters_all() -> None:
    piece = Piece(
        id="p1",
        name="Piece",
        kind="rectangle",
        width=100,
        height=50,
        respect_grain=True,
        allowed_rotations=[90, 270],
    )

    assert effective_rotations(piece) == []


def test_circle_uses_single_rotation_and_expected_bounds() -> None:
    piece = Piece(id="c1", name="Cercle", kind="circle", width=80)
    geometry = transformed_geometry(piece, 10, 20, 90)

    width, height = dimensions(geometry)
    assert round(width, 3) == 80
    assert round(height, 3) == 80
    assert effective_rotations(piece) == [0.0]


def test_spacing_detection_allows_touching_when_spacing_zero() -> None:
    first = transformed_geometry(
        Piece(id="a", name="A", kind="rectangle", width=100, height=100), 0, 0, 0
    )
    second = transformed_geometry(
        Piece(id="b", name="B", kind="rectangle", width=100, height=100), 100, 0, 0
    )

    assert not violates_spacing(second, [first], spacing=0)
    assert violates_spacing(second, [first], spacing=5)


def test_within_fabric_checks_width_and_length_limit() -> None:
    fabric = Fabric(width=100, max_length=200)
    piece = Piece(id="p", name="P", kind="rectangle", width=210, height=50)
    geometry = transformed_geometry(piece, 0, 0, 0)

    assert not within_fabric(geometry, fabric)
