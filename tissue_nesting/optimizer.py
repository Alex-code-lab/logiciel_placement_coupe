from __future__ import annotations

from dataclasses import dataclass
from math import inf

from shapely.geometry.base import BaseGeometry

from .geometry import (
    EPSILON,
    base_geometry,
    dimensions,
    effective_rotations,
    oriented_geometry,
    transformed_geometry,
    violates_spacing,
    within_fabric,
)
from .models import Fabric, Piece, PlacementRecord, Project


@dataclass(slots=True)
class PieceInstance:
    piece: Piece
    instance: int
    area: float
    base_width: float
    base_height: float


@dataclass(slots=True)
class Placement:
    piece: Piece
    instance: int
    x: float
    y: float
    rotation: float
    geometry: BaseGeometry

    @property
    def record(self) -> PlacementRecord:
        return PlacementRecord(
            piece_id=self.piece.id,
            instance=self.instance,
            x=self.x,
            y=self.y,
            rotation=self.rotation,
        )


@dataclass(slots=True)
class UnplacedPiece:
    piece: Piece
    instance: int
    reason: str


@dataclass(slots=True)
class OptimizationResult:
    placements: list[Placement]
    unplaced: list[UnplacedPiece]
    used_length: float
    fabric_length: float
    utilization: float

    @property
    def placed_count(self) -> int:
        return len(self.placements)

    @property
    def total_count(self) -> int:
        return len(self.placements) + len(self.unplaced)


class NestingOptimizer:
    """Heuristique bottom-left avec collisions exactes Shapely.

    Le probleme de nesting 2D est NP-difficile. Cette classe privilegie donc une
    strategie deterministe et comprehensible: plusieurs ordres de pieces sont
    testes, puis chaque piece est placee sur des positions candidates issues des
    bords deja occupes.
    """

    def optimize(self, project: Project) -> OptimizationResult:
        project.validate()
        instances = expand_instances(project.pieces)
        if not instances:
            return OptimizationResult([], [], 0.0, project.fabric.fixed_length or 0.0, 0.0)

        ordered_runs = [
            sorted(instances, key=lambda item: (item.area, item.base_height), reverse=True),
            sorted(
                instances,
                key=lambda item: (max(item.base_width, item.base_height), item.area),
                reverse=True,
            ),
            sorted(instances, key=lambda item: (item.base_height, item.area), reverse=True),
            sorted(instances, key=lambda item: (item.base_width, item.area), reverse=True),
        ]

        results = [self._pack_order(project.fabric, ordered) for ordered in ordered_runs]
        return min(results, key=_result_score)

    def _pack_order(
        self, fabric: Fabric, instances: list[PieceInstance]
    ) -> OptimizationResult:
        placements: list[Placement] = []
        unplaced: list[UnplacedPiece] = []

        for instance in instances:
            placement = self._find_best_placement(fabric, instance, placements)
            if placement is None:
                unplaced.append(
                    UnplacedPiece(
                        piece=instance.piece,
                        instance=instance.instance,
                        reason="Aucun emplacement compatible avec la largeur, la longueur et l'espacement.",
                    )
                )
            else:
                placements.append(placement)

        return build_result(fabric, placements, unplaced)

    def _find_best_placement(
        self, fabric: Fabric, instance: PieceInstance, placements: list[Placement]
    ) -> Placement | None:
        placed_geometries = [placement.geometry for placement in placements]
        current_length = max((placement.geometry.bounds[2] for placement in placements), default=0.0)
        best_score: tuple[float, float, float, float] | None = None
        best: Placement | None = None

        for rotation in effective_rotations(instance.piece):
            oriented = oriented_geometry(instance.piece, rotation)
            width, height = dimensions(oriented)
            if height > fabric.width + EPSILON:
                continue
            if fabric.length_limit is not None and width > fabric.length_limit + EPSILON:
                continue

            for x in candidate_x_positions(placements, width, fabric):
                for y in candidate_y_positions(placements, height, fabric):
                    candidate = transformed_geometry(instance.piece, x, y, rotation)
                    if not within_fabric(candidate, fabric):
                        continue
                    if violates_spacing(candidate, placed_geometries, fabric.spacing):
                        continue

                    _, _, maxx, maxy = candidate.bounds
                    resulting_length = max(current_length, maxx)
                    score = (
                        resulting_length,
                        x,
                        y,
                        maxy,
                    )
                    if best_score is None or score < best_score:
                        best_score = score
                        best = Placement(
                            piece=instance.piece,
                            instance=instance.instance,
                            x=x,
                            y=y,
                            rotation=rotation,
                            geometry=candidate,
                        )
        return best


def expand_instances(pieces: list[Piece]) -> list[PieceInstance]:
    instances: list[PieceInstance] = []
    for piece in pieces:
        geometry = base_geometry(piece)
        width, height = dimensions(geometry)
        for instance in range(1, piece.quantity + 1):
            instances.append(
                PieceInstance(
                    piece=piece,
                    instance=instance,
                    area=geometry.area,
                    base_width=width,
                    base_height=height,
                )
            )
    return instances


def candidate_x_positions(
    placements: list[Placement], piece_width: float, fabric: Fabric
) -> list[float]:
    limit = fabric.length_limit
    spacing = fabric.spacing
    values = {0.0}
    if limit is not None:
        values.add(max(0.0, limit - piece_width))

    for placement in placements:
        minx, _, maxx, _ = placement.geometry.bounds
        values.add(max(0.0, minx))
        values.add(max(0.0, maxx))
        values.add(max(0.0, maxx + spacing))
        values.add(max(0.0, minx - piece_width - spacing))

    return sorted(value for value in values if value >= -EPSILON)


def candidate_y_positions(
    placements: list[Placement], piece_height: float, fabric: Fabric
) -> list[float]:
    spacing = fabric.spacing
    values = {0.0, max(0.0, fabric.width - piece_height)}
    for placement in placements:
        _, miny, _, maxy = placement.geometry.bounds
        values.add(max(0.0, miny))
        values.add(max(0.0, maxy))
        values.add(max(0.0, maxy + spacing))
        values.add(max(0.0, miny - piece_height - spacing))

    return sorted(value for value in values if value >= -EPSILON)


def build_result(
    fabric: Fabric, placements: list[Placement], unplaced: list[UnplacedPiece] | None = None
) -> OptimizationResult:
    unplaced = unplaced or []
    used_length = max((placement.geometry.bounds[2] for placement in placements), default=0.0)
    if fabric.fixed_length is not None:
        fabric_length = fabric.fixed_length
    else:
        fabric_length = used_length

    area = sum(placement.geometry.area for placement in placements)
    usable_area = fabric.width * fabric_length if fabric_length > EPSILON else 0.0
    utilization = area / usable_area if usable_area else 0.0
    return OptimizationResult(
        placements=placements,
        unplaced=unplaced,
        used_length=used_length,
        fabric_length=fabric_length,
        utilization=utilization,
    )


def rebuild_placements(project: Project, records: list[PlacementRecord]) -> list[Placement]:
    project.validate()
    pieces_by_id = {piece.id: piece for piece in project.pieces}
    placements: list[Placement] = []
    for record in records:
        piece = pieces_by_id.get(record.piece_id)
        if piece is None:
            continue
        geometry = transformed_geometry(piece, record.x, record.y, record.rotation)
        placements.append(
            Placement(
                piece=piece,
                instance=record.instance,
                x=record.x,
                y=record.y,
                rotation=record.rotation,
                geometry=geometry,
            )
        )
    return placements


def _result_score(result: OptimizationResult) -> tuple[int, float, float]:
    if result.total_count == 0:
        return (0, 0.0, 0.0)
    missing = result.total_count - result.placed_count
    used_length = result.used_length if result.placements else inf
    return (missing, used_length, -result.utilization)
