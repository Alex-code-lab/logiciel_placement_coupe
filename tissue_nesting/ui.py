from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .geometry import dimensions, iter_polygons
from .models import Fabric, Piece, Project, ShapeKind, new_piece_id
from .optimizer import (
    NestingOptimizer,
    OptimizationResult,
    build_result,
    rebuild_placements,
)
from .project_io import load_project, save_project

KIND_LABELS: dict[ShapeKind, str] = {
    "rectangle": "Rectangle",
    "triangle": "Triangle",
    "polygon": "Polygone",
    "circle": "Cercle",
    "oval": "Ovale",
}
DEFAULT_COLORS = [
    "#5b8def",
    "#62b36f",
    "#e3a546",
    "#d96c6c",
    "#8a70d6",
    "#4aa6a6",
    "#c478a6",
]


class PieceDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        piece: Piece | None = None,
        default_kind: ShapeKind = "rectangle",
        color_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Piece")
        self._piece_id = piece.id if piece else new_piece_id()
        self._color = piece.color if piece else DEFAULT_COLORS[color_index % len(DEFAULT_COLORS)]
        self._piece: Piece | None = None

        self.kind_combo = QComboBox()
        for kind, label in KIND_LABELS.items():
            self.kind_combo.addItem(label, kind)

        self.name_edit = QLineEdit()
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999)

        self.width_spin = dimension_spin()
        self.height_spin = dimension_spin()

        self.points_edit = QPlainTextEdit()
        self.points_edit.setFixedHeight(92)

        self.can_rotate_check = QCheckBox("Rotation autorisee")
        self.grain_check = QCheckBox("Respect du sens")
        self.rotations_edit = QLineEdit()
        self.rotations_edit.setPlaceholderText("Auto, ex: 0,90,180")

        self.color_button = QPushButton()
        self.color_button.setFixedWidth(92)
        self.color_button.clicked.connect(self._choose_color)

        form = QFormLayout(self)
        form.addRow("Type", self.kind_combo)
        form.addRow("Nom", self.name_edit)
        form.addRow("Quantite", self.quantity_spin)

        self.width_label = QLabel("Largeur")
        self.height_label = QLabel("Hauteur")
        form.addRow(self.width_label, self.width_spin)
        form.addRow(self.height_label, self.height_spin)

        self.points_label = QLabel("Points (cm)")
        form.addRow(self.points_label, self.points_edit)

        form.addRow("Rotation", self.can_rotate_check)
        form.addRow("Tissu", self.grain_check)
        form.addRow("Angles", self.rotations_edit)
        form.addRow("Couleur", self.color_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.kind_combo.currentIndexChanged.connect(self._update_fields)
        self._load_piece(piece, default_kind)
        self._update_color_button()
        self._update_fields()

    @property
    def piece(self) -> Piece:
        if self._piece is None:
            raise RuntimeError("Le dialogue n'a pas encore cree de piece.")
        return self._piece

    def accept(self) -> None:
        try:
            self._piece = self._build_piece()
        except ValueError as exc:
            QMessageBox.warning(self, "Piece invalide", str(exc))
            return
        super().accept()

    def _load_piece(self, piece: Piece | None, default_kind: ShapeKind) -> None:
        selected_kind = piece.kind if piece else default_kind
        index = self.kind_combo.findData(selected_kind)
        self.kind_combo.setCurrentIndex(max(index, 0))
        self.name_edit.setText(piece.name if piece else KIND_LABELS[selected_kind])
        self.quantity_spin.setValue(piece.quantity if piece else 1)
        self.width_spin.setValue(piece.width or 10.0 if piece else 10.0)
        self.height_spin.setValue(piece.height or 10.0 if piece else 10.0)
        self.points_edit.setPlainText(
            format_points(piece.points)
            if piece and piece.points
            else "0,0; 16,0; 12,8; 4,12"
        )
        self.can_rotate_check.setChecked(piece.can_rotate if piece else True)
        self.grain_check.setChecked(piece.respect_grain if piece else False)
        self.rotations_edit.setText(
            ", ".join(format_number(angle) for angle in piece.allowed_rotations)
            if piece and piece.allowed_rotations
            else ""
        )

    def _update_fields(self) -> None:
        kind = self.kind_combo.currentData()
        is_polygon = kind == "polygon"
        is_circle = kind == "circle"
        needs_height = kind in {"rectangle", "triangle", "oval"}

        self.width_label.setText("Diametre" if is_circle else "Largeur")
        self.height_label.setVisible(needs_height)
        self.height_spin.setVisible(needs_height)
        self.width_label.setVisible(not is_polygon)
        self.width_spin.setVisible(not is_polygon)
        self.points_label.setVisible(is_polygon)
        self.points_edit.setVisible(is_polygon)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Couleur de la piece")
        if color.isValid():
            self._color = color.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        self.color_button.setText(self._color)
        self.color_button.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #555; padding: 4px;"
        )

    def _build_piece(self) -> Piece:
        kind = self.kind_combo.currentData()
        name = self.name_edit.text().strip()
        width = self.width_spin.value() if kind != "polygon" else None
        height = self.height_spin.value() if kind in {"rectangle", "triangle", "oval"} else None
        points = parse_points(self.points_edit.toPlainText()) if kind == "polygon" else []
        piece = Piece(
            id=self._piece_id,
            name=name,
            kind=kind,
            quantity=self.quantity_spin.value(),
            width=width,
            height=height,
            points=points,
            can_rotate=self.can_rotate_check.isChecked(),
            respect_grain=self.grain_check.isChecked(),
            allowed_rotations=parse_rotations(self.rotations_edit.text()),
            color=self._color,
        )
        piece.validate()
        return piece


class LayoutView(QGraphicsView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#eef1f4"))

    def wheelEvent(self, event) -> None:  # noqa: ANN001 - Qt event type varies by binding.
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def draw_layout(
        self,
        fabric: Fabric,
        result: OptimizationResult | None,
        display_length: float,
    ) -> None:
        self._scene.clear()
        display_length = max(display_length, 100.0)
        self._draw_fabric(fabric, display_length)

        if result is not None:
            for placement in result.placements:
                self._draw_piece(placement)

        margin = max(fabric.width, display_length) * 0.03
        self._scene.setSceneRect(
            -margin,
            -margin,
            display_length + margin * 2,
            fabric.width + margin * 2,
        )
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def fit_content(self) -> None:
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_fabric(self, fabric: Fabric, display_length: float) -> None:
        background = self._scene.addRect(
            0,
            0,
            display_length,
            fabric.width,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor("#ffffff")),
        )
        background.setZValue(-3)
        self._draw_background_image(fabric, display_length)

        grid_pen = QPen(QColor("#d7dde3"), 0)
        axis_pen = QPen(QColor("#9aa7b3"), 0)
        step = grid_step(max(display_length, fabric.width))

        x = step
        while x < display_length:
            line = self._scene.addLine(x, 0, x, fabric.width, grid_pen)
            line.setZValue(2)
            x += step

        y = step
        while y < fabric.width:
            line = self._scene.addLine(0, y, display_length, y, grid_pen)
            line.setZValue(2)
            y += step

        border = self._scene.addRect(
            0,
            0,
            display_length,
            fabric.width,
            QPen(QColor("#263238"), 1.6),
            QBrush(Qt.BrushStyle.NoBrush),
        )
        border.setZValue(3)

        arrow_y = -max(18.0, fabric.width * 0.025)
        arrow_length = min(40.0, display_length)
        axis = self._scene.addLine(0, arrow_y, arrow_length, arrow_y, axis_pen)
        axis.setZValue(4)
        head_top = self._scene.addLine(
            arrow_length,
            arrow_y,
            max(0.0, arrow_length - 4.0),
            arrow_y - 2.0,
            axis_pen,
        )
        head_bottom = self._scene.addLine(
            arrow_length,
            arrow_y,
            max(0.0, arrow_length - 4.0),
            arrow_y + 2.0,
            axis_pen,
        )
        head_top.setZValue(4)
        head_bottom.setZValue(4)
        label = self._scene.addSimpleText("sens longitudinal")
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        label.setBrush(QColor("#455a64"))
        label.setPos(0, arrow_y - 18)
        label.setZValue(5)

    def _draw_background_image(self, fabric: Fabric, display_length: float) -> None:
        if not fabric.background_image_path:
            return
        pixmap = QPixmap(str(Path(fabric.background_image_path).expanduser()))
        if pixmap.isNull():
            return
        item = self._scene.addPixmap(pixmap)
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        item.setOpacity(0.62)
        item.setZValue(-2)
        item.setTransform(
            QTransform.fromScale(
                display_length / pixmap.width(),
                fabric.width / pixmap.height(),
            )
        )

    def _draw_piece(self, placement) -> None:  # noqa: ANN001 - keeps UI decoupled.
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in iter_polygons(placement.geometry):
            add_ring(path, polygon.exterior.coords)
            for interior in polygon.interiors:
                add_ring(path, interior.coords)

        color = QColor(placement.piece.color)
        fill = QColor(color)
        fill.setAlpha(185)
        pen = QPen(color.darker(135), 1.2)
        item = self._scene.addPath(path, pen, QBrush(fill))
        item.setZValue(10)

        centroid = placement.geometry.centroid
        label = QGraphicsSimpleTextItem(f"{placement.piece.name} #{placement.instance}")
        label.setBrush(QColor("#102027"))
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self._scene.addItem(label)
        rect = label.boundingRect()
        label.setPos(QPointF(centroid.x - rect.width() / 2, centroid.y - rect.height() / 2))
        label.setZValue(11)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = default_project()
        self.optimizer = NestingOptimizer()
        self.current_result: OptimizationResult | None = None
        self.current_path: Path | None = None
        self._updating = False

        self.setWindowTitle("Optimisation de decoupe de tissu")
        self.resize(1240, 780)

        self._build_actions()
        self._build_ui()
        self._load_project_to_widgets()
        self._redraw()

    def _build_actions(self) -> None:
        toolbar = QToolBar("Actions", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("Nouveau", self)
        new_action.triggered.connect(self.new_project)
        toolbar.addAction(new_action)

        open_action = QAction("Ouvrir", self)
        open_action.triggered.connect(self.open_project)
        toolbar.addAction(open_action)

        save_action = QAction("Enregistrer", self)
        save_action.triggered.connect(self.save_project)
        toolbar.addAction(save_action)

        save_as_action = QAction("Enregistrer sous", self)
        save_as_action.triggered.connect(self.save_project_as)
        toolbar.addAction(save_as_action)

        toolbar.addSeparator()

        optimize_action = QAction("Optimiser", self)
        optimize_action.triggered.connect(self.optimize)
        toolbar.addAction(optimize_action)

        fit_action = QAction("Ajuster", self)
        fit_action.triggered.connect(lambda: self.view.fit_content())
        toolbar.addAction(fit_action)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        left = QWidget()
        left.setMinimumWidth(370)
        left.setMaximumWidth(470)
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(self._build_fabric_group())
        left_layout.addWidget(self._build_piece_group(), 1)

        optimize_button = QPushButton("Optimiser le placement")
        optimize_button.clicked.connect(self.optimize)
        left_layout.addWidget(optimize_button)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setFrameShape(QFrame.Shape.NoFrame)
        left_layout.addWidget(self.summary_label)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.view = LayoutView()
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.view)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([400, 840])

    def _build_fabric_group(self) -> QGroupBox:
        group = QGroupBox("Tissu")
        form = QFormLayout(group)

        self.fabric_width_spin = dimension_spin(maximum=1_000_000)
        self.spacing_spin = dimension_spin(maximum=10_000)

        self.max_length_check = QCheckBox("Longueur maximale")
        self.max_length_spin = dimension_spin(maximum=1_000_000)
        max_layout = QHBoxLayout()
        max_layout.addWidget(self.max_length_check)
        max_layout.addWidget(self.max_length_spin)

        self.fixed_length_check = QCheckBox("Longueur imposee")
        self.fixed_length_spin = dimension_spin(maximum=1_000_000)
        fixed_layout = QHBoxLayout()
        fixed_layout.addWidget(self.fixed_length_check)
        fixed_layout.addWidget(self.fixed_length_spin)

        self.grain_label = QLabel("Axe longitudinal du rouleau")
        self.background_label = QLabel()
        self.background_label.setWordWrap(True)
        choose_background_button = QPushButton("Choisir")
        choose_background_button.clicked.connect(self.choose_background_image)
        remove_background_button = QPushButton("Retirer")
        remove_background_button.clicked.connect(self.remove_background_image)
        background_layout = QHBoxLayout()
        background_layout.addWidget(self.background_label, 1)
        background_layout.addWidget(choose_background_button)
        background_layout.addWidget(remove_background_button)

        form.addRow("Largeur", self.fabric_width_spin)
        form.addRow("Marge", self.spacing_spin)
        form.addRow(max_layout)
        form.addRow(fixed_layout)
        form.addRow("Sens", self.grain_label)
        form.addRow("Photo", background_layout)

        for widget in (
            self.fabric_width_spin,
            self.spacing_spin,
            self.max_length_spin,
            self.fixed_length_spin,
        ):
            widget.valueChanged.connect(self._fabric_changed)
        self.max_length_check.stateChanged.connect(self._fabric_changed)
        self.fixed_length_check.stateChanged.connect(self._fabric_changed)

        return group

    def _build_piece_group(self) -> QGroupBox:
        group = QGroupBox("Pieces")
        layout = QVBoxLayout(group)

        self.piece_table = QTableWidget(0, 7)
        self.piece_table.setHorizontalHeaderLabels(
            ["Nom", "Type", "Qte", "Dimensions (cm)", "Angles", "Sens", "Couleur"]
        )
        self.piece_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.piece_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.piece_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.piece_table.verticalHeader().setVisible(False)
        self.piece_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.piece_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.piece_table.doubleClicked.connect(self.edit_selected_piece)
        layout.addWidget(self.piece_table, 1)

        add_row = QHBoxLayout()
        for kind in ("rectangle", "triangle", "polygon", "circle", "oval"):
            button = QPushButton(f"+ {KIND_LABELS[kind]}")
            button.clicked.connect(lambda checked=False, item=kind: self.add_piece(item))
            add_row.addWidget(button)
        layout.addLayout(add_row)

        edit_row = QHBoxLayout()
        edit_button = QPushButton("Modifier")
        edit_button.clicked.connect(self.edit_selected_piece)
        remove_button = QPushButton("Supprimer")
        remove_button.clicked.connect(self.remove_selected_piece)
        edit_row.addWidget(edit_button)
        edit_row.addWidget(remove_button)
        layout.addLayout(edit_row)

        return group

    def new_project(self) -> None:
        self.project = default_project()
        self.current_result = None
        self.current_path = None
        self._load_project_to_widgets()
        self._redraw()

    def open_project(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", "", "Projets JSON (*.json);;Tous les fichiers (*)"
        )
        if not file_name:
            return
        try:
            loaded = load_project(file_name)
            self.project = loaded.project
            placements = rebuild_placements(self.project, loaded.placements)
            self.current_result = build_result(self.project.fabric, placements) if placements else None
            self.current_path = Path(file_name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Ouverture impossible", str(exc))
            return

        self._load_project_to_widgets()
        self._redraw()

    def save_project(self) -> None:
        if self.current_path is None:
            self.save_project_as()
            return
        self._save_to_path(self.current_path)

    def save_project_as(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le projet", "", "Projets JSON (*.json)"
        )
        if not file_name:
            return
        path = Path(file_name)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        self._save_to_path(path)

    def optimize(self) -> None:
        try:
            self._sync_project_from_widgets()
            result = self.optimizer.optimize(self.project)
        except ValueError as exc:
            QMessageBox.warning(self, "Projet invalide", str(exc))
            return

        self.current_result = result
        self._redraw()

        if result.unplaced:
            names = ", ".join(
                f"{item.piece.name} #{item.instance}" for item in result.unplaced[:8]
            )
            suffix = "" if len(result.unplaced) <= 8 else "..."
            QMessageBox.warning(
                self,
                "Pieces non placees",
                f"{len(result.unplaced)} piece(s) n'ont pas trouve d'emplacement: {names}{suffix}",
            )

    def add_piece(self, kind: ShapeKind) -> None:
        dialog = PieceDialog(
            self,
            default_kind=kind,
            color_index=len(self.project.pieces),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.pieces.append(dialog.piece)
            self._invalidate_layout()
            self._populate_piece_table()

    def edit_selected_piece(self) -> None:
        row = self.piece_table.currentRow()
        if row < 0:
            return
        piece = self.project.pieces[row]
        dialog = PieceDialog(self, piece=piece)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.pieces[row] = dialog.piece
            self._invalidate_layout()
            self._populate_piece_table()

    def remove_selected_piece(self) -> None:
        row = self.piece_table.currentRow()
        if row < 0:
            return
        del self.project.pieces[row]
        self._invalidate_layout()
        self._populate_piece_table()

    def choose_background_image(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une photo de tissu",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;Tous les fichiers (*)",
        )
        if not file_name:
            return
        self.project.fabric.background_image_path = file_name
        self._update_background_label()
        self._redraw()

    def remove_background_image(self) -> None:
        self.project.fabric.background_image_path = None
        self._update_background_label()
        self._redraw()

    def _save_to_path(self, path: Path) -> None:
        try:
            self._sync_project_from_widgets()
            save_project(
                path,
                self.project,
                self.current_result.placements if self.current_result else None,
            )
            self.current_path = path
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))

    def _load_project_to_widgets(self) -> None:
        self._updating = True
        fabric = self.project.fabric
        self.fabric_width_spin.setValue(fabric.width)
        self.spacing_spin.setValue(fabric.spacing)
        self.max_length_check.setChecked(fabric.max_length is not None)
        self.max_length_spin.setValue(fabric.max_length or 500.0)
        self.max_length_spin.setEnabled(fabric.max_length is not None)
        self.fixed_length_check.setChecked(fabric.fixed_length is not None)
        self.fixed_length_spin.setValue(fabric.fixed_length or 500.0)
        self.fixed_length_spin.setEnabled(fabric.fixed_length is not None)
        self._updating = False
        self._update_background_label()
        self._populate_piece_table()

    def _populate_piece_table(self) -> None:
        self.piece_table.setRowCount(len(self.project.pieces))
        for row, piece in enumerate(self.project.pieces):
            values = [
                piece.name,
                KIND_LABELS[piece.kind],
                str(piece.quantity),
                piece_dimensions_label(piece),
                rotations_label(piece),
                "Oui" if piece.respect_grain else "Non",
                piece.color,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {2, 4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 6:
                    item.setBackground(QColor(piece.color))
                item.setData(Qt.ItemDataRole.UserRole, piece.id)
                self.piece_table.setItem(row, column, item)
        self.piece_table.resizeColumnsToContents()
        self.piece_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.piece_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

    def _fabric_changed(self, *args) -> None:  # noqa: ANN002 - Qt signal payloads.
        self.max_length_spin.setEnabled(self.max_length_check.isChecked())
        self.fixed_length_spin.setEnabled(self.fixed_length_check.isChecked())
        if self._updating:
            return
        try:
            self.project.fabric = self._fabric_from_widgets()
        except ValueError:
            return
        self._invalidate_layout()

    def _sync_project_from_widgets(self) -> None:
        self.project.fabric = self._fabric_from_widgets()
        self.project.validate()

    def _fabric_from_widgets(self) -> Fabric:
        fabric = Fabric(
            width=self.fabric_width_spin.value(),
            max_length=self.max_length_spin.value()
            if self.max_length_check.isChecked()
            else None,
            fixed_length=self.fixed_length_spin.value()
            if self.fixed_length_check.isChecked()
            else None,
            spacing=self.spacing_spin.value(),
            grain_axis="lengthwise",
            unit="cm",
            background_image_path=self.project.fabric.background_image_path,
        )
        fabric.validate()
        return fabric

    def _invalidate_layout(self) -> None:
        self.current_result = None
        self._redraw()

    def _redraw(self) -> None:
        self.view.draw_layout(
            self.project.fabric,
            self.current_result,
            self._display_length(),
        )
        self._update_summary()

    def _display_length(self) -> float:
        fabric = self.project.fabric
        if fabric.fixed_length is not None:
            return fabric.fixed_length
        if fabric.max_length is not None:
            return fabric.max_length
        used = self.current_result.used_length if self.current_result else 0.0
        return max(used * 1.08, fabric.width * 1.4, 100.0)

    def _update_summary(self) -> None:
        total = sum(piece.quantity for piece in self.project.pieces)
        if self.current_result is None:
            self.summary_label.setText(
                f"{total} piece(s). Largeur: {format_number(self.project.fabric.width)} cm."
            )
            return

        result = self.current_result
        self.summary_label.setText(
            "Placees: "
            f"{result.placed_count}/{result.total_count} | "
            f"Longueur utilisee: {format_number(result.used_length)} cm | "
            f"Rendement: {result.utilization * 100:.1f}%"
        )

    def _update_background_label(self) -> None:
        image_path = self.project.fabric.background_image_path
        if not image_path:
            self.background_label.setText("Aucune")
            return
        path = Path(image_path)
        self.background_label.setText(path.name if path.name else str(path))


def dimension_spin(maximum: float = 100_000.0) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.01, maximum)
    spin.setDecimals(2)
    spin.setSingleStep(1.0)
    spin.setSuffix(" cm")
    return spin


def default_project() -> Project:
    return Project(
        fabric=Fabric(width=140.0, max_length=500.0, fixed_length=None, spacing=0.5),
        pieces=[],
    )


def parse_points(text: str) -> list[tuple[float, float]]:
    chunks = text.replace("\n", ";").split(";")
    points: list[tuple[float, float]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.replace(",", " ").split()
        if len(parts) != 2:
            raise ValueError("Les points doivent etre saisis sous la forme x,y; x,y.")
        points.append((float(parts[0]), float(parts[1])))
    return points


def parse_rotations(text: str) -> list[float]:
    if not text.strip():
        return []
    normalized = text.replace(";", ",").replace(" ", ",")
    return [float(token) for token in normalized.split(",") if token.strip()]


def format_points(points: list[tuple[float, float]]) -> str:
    return "; ".join(f"{format_number(x)},{format_number(y)}" for x, y in points)


def piece_dimensions_label(piece: Piece) -> str:
    if piece.kind == "polygon":
        try:
            width, height = dimensions_from_piece(piece)
            return f"{format_number(width)} x {format_number(height)}"
        except ValueError:
            return "Polygone"
    if piece.kind == "circle":
        return f"D {format_number(piece.width or 0)}"
    return f"{format_number(piece.width or 0)} x {format_number(piece.height or 0)}"


def dimensions_from_piece(piece: Piece) -> tuple[float, float]:
    from .geometry import base_geometry

    return dimensions(base_geometry(piece))


def rotations_label(piece: Piece) -> str:
    if not piece.can_rotate:
        return "0"
    if piece.allowed_rotations:
        return ", ".join(format_number(angle) for angle in piece.allowed_rotations)
    if piece.respect_grain:
        return "0, 180"
    if piece.kind == "circle":
        return "0"
    return "0, 90, 180, 270"


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def grid_step(max_dimension: float) -> float:
    for step in (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0):
        if max_dimension / step <= 70:
            return step
    return 2500.0


def add_ring(path: QPainterPath, coords) -> None:  # noqa: ANN001 - Shapely coord sequence.
    points = list(coords)
    if not points:
        return
    path.moveTo(QPointF(points[0][0], points[0][1]))
    for x, y in points[1:]:
        path.lineTo(QPointF(x, y))
    path.closeSubpath()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
