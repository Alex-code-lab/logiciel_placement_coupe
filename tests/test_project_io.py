from __future__ import annotations

from tissue_nesting.models import Fabric, Piece, Project
from tissue_nesting.optimizer import NestingOptimizer
from tissue_nesting.project_io import load_project, save_project


def test_project_json_round_trip(tmp_path) -> None:
    project = Project(
        fabric=Fabric(
            width=140,
            max_length=500,
            spacing=0.5,
            background_image_path="/tmp/tissu.jpg",
        ),
        pieces=[
            Piece(
                id="poly",
                name="Empiecement",
                kind="polygon",
                points=[(0, 0), (20, 0), (12, 18), (0, 12)],
                quantity=2,
                allowed_rotations=[0, 180],
                color="#62b36f",
            )
        ],
    )
    result = NestingOptimizer().optimize(project)
    path = tmp_path / "projet.json"

    save_project(path, project, result.placements)
    loaded = load_project(path)

    assert loaded.project.fabric.width == 140
    assert loaded.project.fabric.spacing == 0.5
    assert loaded.project.fabric.unit == "cm"
    assert loaded.project.fabric.background_image_path == "/tmp/tissu.jpg"
    assert loaded.project.pieces[0].points == project.pieces[0].points
    assert len(loaded.placements) == 2
