from __future__ import annotations

from tissue_nesting.geometry import violates_spacing, within_fabric
from tissue_nesting.models import Fabric, Piece, Project
from tissue_nesting.optimizer import NestingOptimizer


def test_optimizer_places_rectangles_with_spacing() -> None:
    project = Project(
        fabric=Fabric(width=100, spacing=5),
        pieces=[
            Piece(
                id="r",
                name="Rectangle",
                kind="rectangle",
                width=50,
                height=100,
                quantity=2,
                can_rotate=False,
            )
        ],
    )

    result = NestingOptimizer().optimize(project)

    assert result.total_count == 2
    assert result.placed_count == 2
    assert result.used_length == 105
    for placement in result.placements:
        assert within_fabric(placement.geometry, project.fabric)
    assert not violates_spacing(
        result.placements[1].geometry,
        [result.placements[0].geometry],
        project.fabric.spacing,
    )


def test_optimizer_can_nest_two_complementary_triangles() -> None:
    project = Project(
        fabric=Fabric(width=100, spacing=0),
        pieces=[
            Piece(
                id="t",
                name="Triangle",
                kind="triangle",
                width=100,
                height=100,
                quantity=2,
                can_rotate=True,
            )
        ],
    )

    result = NestingOptimizer().optimize(project)

    assert result.placed_count == 2
    assert result.used_length == 100


def test_optimizer_reports_unplaced_when_width_is_impossible() -> None:
    project = Project(
        fabric=Fabric(width=80, max_length=200),
        pieces=[
            Piece(
                id="wide",
                name="Trop large",
                kind="rectangle",
                width=120,
                height=90,
                can_rotate=False,
            )
        ],
    )

    result = NestingOptimizer().optimize(project)

    assert result.placed_count == 0
    assert len(result.unplaced) == 1
