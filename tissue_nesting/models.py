from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

ShapeKind = Literal["rectangle", "triangle", "polygon", "circle", "oval"]
FabricUnit = Literal["cm"]


def new_piece_id() -> str:
    return uuid4().hex[:12]


@dataclass(slots=True)
class Fabric:
    width: float
    max_length: float | None = None
    fixed_length: float | None = None
    spacing: float = 0.0
    grain_axis: Literal["lengthwise"] = "lengthwise"
    unit: FabricUnit = "cm"
    background_image_path: str | None = None

    @property
    def length_limit(self) -> float | None:
        return self.fixed_length if self.fixed_length is not None else self.max_length

    def validate(self) -> None:
        if self.width <= 0:
            raise ValueError("La largeur du tissu doit etre strictement positive.")
        if self.max_length is not None and self.max_length <= 0:
            raise ValueError("La longueur maximale doit etre strictement positive.")
        if self.fixed_length is not None and self.fixed_length <= 0:
            raise ValueError("La longueur imposee doit etre strictement positive.")
        if (
            self.fixed_length is not None
            and self.max_length is not None
            and self.fixed_length > self.max_length
        ):
            raise ValueError(
                "La longueur imposee ne peut pas depasser la longueur maximale."
            )
        if self.spacing < 0:
            raise ValueError("La marge entre les pieces ne peut pas etre negative.")
        if self.unit != "cm":
            raise ValueError("L'application utilise uniquement les centimetres.")


@dataclass(slots=True)
class Piece:
    id: str
    name: str
    kind: ShapeKind
    quantity: int = 1
    width: float | None = None
    height: float | None = None
    points: list[tuple[float, float]] = field(default_factory=list)
    can_rotate: bool = True
    respect_grain: bool = False
    allowed_rotations: list[float] = field(default_factory=list)
    color: str = "#5b8def"

    def validate(self) -> None:
        if not self.id:
            raise ValueError("Chaque piece doit avoir un identifiant.")
        if not self.name.strip():
            raise ValueError("Chaque piece doit avoir un nom.")
        if self.quantity < 1:
            raise ValueError("La quantite doit etre au moins egale a 1.")
        if self.kind not in {"rectangle", "triangle", "polygon", "circle", "oval"}:
            raise ValueError(f"Type de piece inconnu: {self.kind}")

        if self.kind in {"rectangle", "triangle", "oval"}:
            _require_positive(self.width, "largeur")
            _require_positive(self.height, "hauteur")
        elif self.kind == "circle":
            _require_positive(self.width, "diametre")
        elif self.kind == "polygon":
            if len(self.points) < 3:
                raise ValueError("Un polygone doit contenir au moins trois points.")
            for x, y in self.points:
                if x < 0 or y < 0:
                    raise ValueError(
                        "Les points d'un polygone doivent etre dans le repere positif."
                    )


@dataclass(slots=True)
class Project:
    fabric: Fabric
    pieces: list[Piece] = field(default_factory=list)

    def validate(self) -> None:
        self.fabric.validate()
        seen_ids: set[str] = set()
        for piece in self.pieces:
            piece.validate()
            if piece.id in seen_ids:
                raise ValueError(f"Identifiant de piece duplique: {piece.id}")
            seen_ids.add(piece.id)


@dataclass(slots=True)
class PlacementRecord:
    piece_id: str
    instance: int
    x: float
    y: float
    rotation: float


def _require_positive(value: float | None, label: str) -> None:
    if value is None or value <= 0:
        raise ValueError(f"La {label} doit etre strictement positive.")
