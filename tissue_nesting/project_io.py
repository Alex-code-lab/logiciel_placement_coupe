from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Fabric, Piece, PlacementRecord, Project, new_piece_id
from .optimizer import Placement

PROJECT_FORMAT_VERSION = 1


@dataclass(slots=True)
class LoadedProject:
    project: Project
    placements: list[PlacementRecord]


def save_project(
    path: str | Path, project: Project, placements: list[Placement] | None = None
) -> None:
    project.validate()
    payload = project_to_dict(project)
    if placements:
        payload["placements"] = [placement_record_to_dict(item.record) for item in placements]
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> LoadedProject:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    project = project_from_dict(payload)
    placements = [
        placement_record_from_dict(item) for item in payload.get("placements", [])
    ]
    return LoadedProject(project=project, placements=placements)


def project_to_dict(project: Project) -> dict[str, Any]:
    return {
        "version": PROJECT_FORMAT_VERSION,
        "fabric": fabric_to_dict(project.fabric),
        "pieces": [piece_to_dict(piece) for piece in project.pieces],
    }


def project_from_dict(payload: dict[str, Any]) -> Project:
    if "fabric" not in payload:
        raise ValueError("Le fichier JSON ne contient pas de section fabric.")
    pieces_data = payload.get("pieces", [])
    project = Project(
        fabric=fabric_from_dict(payload["fabric"]),
        pieces=[piece_from_dict(item) for item in pieces_data],
    )
    project.validate()
    return project


def fabric_to_dict(fabric: Fabric) -> dict[str, Any]:
    return {
        "width": fabric.width,
        "max_length": fabric.max_length,
        "fixed_length": fabric.fixed_length,
        "spacing": fabric.spacing,
        "grain_axis": fabric.grain_axis,
        "unit": fabric.unit,
        "background_image_path": fabric.background_image_path,
    }


def fabric_from_dict(payload: dict[str, Any]) -> Fabric:
    return Fabric(
        width=float(payload["width"]),
        max_length=_optional_float(payload.get("max_length")),
        fixed_length=_optional_float(payload.get("fixed_length")),
        spacing=float(payload.get("spacing", 0.0)),
        grain_axis=payload.get("grain_axis", "lengthwise"),
        unit=payload.get("unit", "cm"),
        background_image_path=payload.get("background_image_path"),
    )


def piece_to_dict(piece: Piece) -> dict[str, Any]:
    return {
        "id": piece.id,
        "name": piece.name,
        "kind": piece.kind,
        "quantity": piece.quantity,
        "width": piece.width,
        "height": piece.height,
        "points": piece.points,
        "can_rotate": piece.can_rotate,
        "respect_grain": piece.respect_grain,
        "allowed_rotations": piece.allowed_rotations,
        "color": piece.color,
    }


def piece_from_dict(payload: dict[str, Any]) -> Piece:
    points = [tuple(map(float, point)) for point in payload.get("points", [])]
    piece = Piece(
        id=str(payload.get("id") or new_piece_id()),
        name=str(payload.get("name", "Piece")),
        kind=payload["kind"],
        quantity=int(payload.get("quantity", 1)),
        width=_optional_float(payload.get("width")),
        height=_optional_float(payload.get("height")),
        points=points,
        can_rotate=bool(payload.get("can_rotate", True)),
        respect_grain=bool(payload.get("respect_grain", False)),
        allowed_rotations=[float(angle) for angle in payload.get("allowed_rotations", [])],
        color=str(payload.get("color", "#5b8def")),
    )
    piece.validate()
    return piece


def placement_record_to_dict(record: PlacementRecord) -> dict[str, Any]:
    return {
        "piece_id": record.piece_id,
        "instance": record.instance,
        "x": record.x,
        "y": record.y,
        "rotation": record.rotation,
    }


def placement_record_from_dict(payload: dict[str, Any]) -> PlacementRecord:
    return PlacementRecord(
        piece_id=str(payload["piece_id"]),
        instance=int(payload.get("instance", 1)),
        x=float(payload["x"]),
        y=float(payload["y"]),
        rotation=float(payload.get("rotation", 0.0)),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
