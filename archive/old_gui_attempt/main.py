from __future__ import annotations

import sys
from pathlib import Path

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QFileDialog,
        QGroupBox,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QFileDialog,
        QGroupBox,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

from .animation import build_animation_paths
from .models import CrystalAxis, SymmetryAnalysisResult
from .structure_loader import load_crystal_from_cif
from .symmetry_analyzer import (
    analyze_crystal_symmetry,
    render_axes,
    render_centers,
    render_planes,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crystal Symmetry Viewer")
        self.resize(1320, 860)

        self.structure = None
        self.analysis: SymmetryAnalysisResult | None = None
        self.render_axes = []
        self.render_planes = []
        self.render_centers = []
        self.viewer = None
        self.plotter = None
        self.selected_atom_indices: set[int] = set()
        self.animation_paths = []
        self.animation_circular = False
        self.animation_step = 0
        self.animation_frames = 72

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_animation)

        self.root = QSplitter()
        self.controls = self.build_controls()
        self.viewport_placeholder = QLabel("Open a CIF file to start the 3D viewer.")
        self.viewport_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewport_placeholder.setStyleSheet("background: #101216; color: #d6dde6;")

        self.root.addWidget(self.controls)
        self.root.addWidget(self.viewport_placeholder)
        self.root.setSizes([330, 990])
        self.setCentralWidget(self.root)

    def build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.open_button = QPushButton("Open CIF")
        self.open_button.clicked.connect(self.open_cif)
        layout.addWidget(self.open_button)

        self.analyze_button = QPushButton("Analyze Symmetry")
        self.analyze_button.clicked.connect(self.analyze_symmetry)
        layout.addWidget(self.analyze_button)

        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout(display_group)
        self.show_atoms_check = QCheckBox("Show atoms")
        self.show_atoms_check.setChecked(True)
        self.show_atoms_check.toggled.connect(self.toggle_display)
        self.show_unit_cell_check = QCheckBox("Show unit cell")
        self.show_unit_cell_check.setChecked(True)
        self.show_unit_cell_check.toggled.connect(self.toggle_display)
        self.show_symmetry_check = QCheckBox("Show symmetry elements")
        self.show_symmetry_check.setChecked(True)
        self.show_symmetry_check.toggled.connect(self.refresh_selected_operation)
        display_layout.addWidget(self.show_atoms_check)
        display_layout.addWidget(self.show_unit_cell_check)
        display_layout.addWidget(self.show_symmetry_check)
        layout.addWidget(display_group)

        target_group = QGroupBox("Animation target")
        target_layout = QVBoxLayout(target_group)
        self.target_group = QButtonGroup(self)
        self.selected_radio = QRadioButton("Selected atoms")
        self.all_radio = QRadioButton("All atoms")
        self.selected_radio.setChecked(True)
        self.target_group.addButton(self.selected_radio)
        self.target_group.addButton(self.all_radio)
        target_layout.addWidget(self.selected_radio)
        target_layout.addWidget(self.all_radio)
        layout.addWidget(target_group)

        self.play_button = QPushButton("Play selected operation")
        self.play_button.clicked.connect(self.play_selected_operation)
        layout.addWidget(self.play_button)

        self.clear_button = QPushButton("Clear selection")
        self.clear_button.clicked.connect(self.clear_selection)
        layout.addWidget(self.clear_button)

        self.reset_button = QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_view)
        layout.addWidget(self.reset_button)

        self.status_label = QLabel("Open a CIF file to begin.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Operations"))
        self.operation_list = QListWidget()
        self.operation_list.currentRowChanged.connect(self.refresh_selected_operation)
        layout.addWidget(self.operation_list, 2)

        layout.addWidget(QLabel("Atoms"))
        self.atom_list = QListWidget()
        self.atom_list.itemChanged.connect(self.atom_selection_changed)
        layout.addWidget(self.atom_list, 3)

        return panel

    def open_cif(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open CIF",
            str(Path.cwd()),
            "CIF files (*.cif);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        try:
            self.structure = load_crystal_from_cif(path)
        except Exception as exc:
            self.show_error("Could not load CIF", exc)
            return

        self.analysis = None
        self.selected_atom_indices.clear()
        self.operation_list.clear()
        self.populate_atom_list()
        self.ensure_viewer()
        self.viewer.set_structure(self.structure)
        self.status_label.setText(f"Loaded {Path(path).name}: {len(self.structure.atoms)} atoms.")

    def ensure_viewer(self) -> None:
        if self.viewer is not None:
            return

        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

        from .viewer import CrystalViewer

        self.plotter = QVTKRenderWindowInteractor()
        self.viewer = CrystalViewer(self.plotter)
        self.root.replaceWidget(1, self.plotter)
        self.viewport_placeholder.deleteLater()
        self.root.setSizes([330, 990])
        self.plotter.show()
        QTimer.singleShot(0, self.viewer.initialize_interactor)

    def populate_atom_list(self) -> None:
        self.atom_list.blockSignals(True)
        self.atom_list.clear()
        if self.structure is not None:
            for atom in self.structure.atoms:
                item = QListWidgetItem(f"Atom {atom.index}: {atom.element}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, atom.index)
                self.atom_list.addItem(item)
        self.atom_list.blockSignals(False)

    def analyze_symmetry(self) -> None:
        if self.structure is None:
            self.status_label.setText("Open a CIF file first.")
            return
        try:
            self.analysis = analyze_crystal_symmetry(self.structure)
        except Exception as exc:
            self.show_error("Could not analyze symmetry", exc)
            return

        self.render_axes = render_axes(self.analysis.axes, self.structure.lattice)
        self.render_planes = render_planes(self.analysis.planes, self.structure.lattice)
        self.render_centers = render_centers(self.analysis.centers, self.structure.lattice)
        self.operation_list.clear()
        for operation in self.analysis.operations:
            self.operation_list.addItem(operation.label)
        if self.analysis.operations:
            self.operation_list.setCurrentRow(0)

        sg = self.analysis.international_symbol or "unknown"
        pg = self.analysis.point_group or "unknown"
        self.status_label.setText(
            f"Space group {self.analysis.space_group_number} {sg}; point group {pg}; "
            f"{len(self.analysis.operations)} operations."
        )

    def toggle_display(self) -> None:
        if self.viewer is None:
            return
        self.viewer.show_atoms = self.show_atoms_check.isChecked()
        self.viewer.show_unit_cell = self.show_unit_cell_check.isChecked()
        self.viewer.redraw_structure()
        self.refresh_selected_operation()

    def refresh_selected_operation(self) -> None:
        if self.viewer is None:
            return
        self.viewer.show_symmetry = self.show_symmetry_check.isChecked()
        operation_index = self.current_operation_index()
        self.viewer.draw_symmetry_elements(
            self.render_axes,
            self.render_planes,
            self.render_centers,
            operation_index=operation_index,
        )

    def atom_selection_changed(self, item: QListWidgetItem) -> None:
        atom_index = int(item.data(Qt.ItemDataRole.UserRole))
        if item.checkState() == Qt.CheckState.Checked:
            self.selected_atom_indices.add(atom_index)
        else:
            self.selected_atom_indices.discard(atom_index)
        if self.viewer is not None:
            self.viewer.set_selected_atoms(self.selected_atom_indices)

    def clear_selection(self) -> None:
        self.selected_atom_indices.clear()
        self.atom_list.blockSignals(True)
        for i in range(self.atom_list.count()):
            self.atom_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.atom_list.blockSignals(False)
        if self.viewer is not None:
            self.viewer.set_selected_atoms(set())

    def reset_view(self) -> None:
        if self.viewer is not None:
            self.viewer.reset_view()

    def play_selected_operation(self) -> None:
        if self.structure is None or self.analysis is None:
            self.status_label.setText("Open a CIF and analyze symmetry first.")
            return
        operation = self.current_operation()
        if operation is None:
            self.status_label.setText("Select an operation first.")
            return

        mode = "all" if self.all_radio.isChecked() else "selected"
        if mode == "selected" and not self.selected_atom_indices:
            self.status_label.setText("Select at least one atom, or use All atoms mode.")
            return

        axis = self.axis_for_operation(operation.index)
        self.animation_paths, self.animation_circular = build_animation_paths(
            self.structure.atoms,
            self.selected_atom_indices,
            operation,
            self.structure.lattice,
            mode,
            axis=axis,
        )
        if not self.animation_paths:
            self.status_label.setText("No atoms available for animation.")
            return
        self.animation_step = 0
        self.play_button.setEnabled(False)
        self.timer.start(16)

    def advance_animation(self) -> None:
        if self.viewer is None:
            self.timer.stop()
            return
        self.animation_step += 1
        s = min(self.animation_step / self.animation_frames, 1.0)
        positions = {
            path.atom_index: path.position_at(s, self.animation_circular)
            for path in self.animation_paths
        }
        self.viewer.set_atom_positions(positions)
        if s >= 1.0:
            self.timer.stop()
            self.viewer.commit_atom_positions(positions)
            self.play_button.setEnabled(True)

    def current_operation_index(self) -> int | None:
        row = self.operation_list.currentRow()
        if row < 0 or self.analysis is None or row >= len(self.analysis.operations):
            return None
        return self.analysis.operations[row].index

    def current_operation(self):
        row = self.operation_list.currentRow()
        if row < 0 or self.analysis is None or row >= len(self.analysis.operations):
            return None
        return self.analysis.operations[row]

    def axis_for_operation(self, operation_index: int) -> CrystalAxis | None:
        if self.analysis is None:
            return None
        for axis in self.analysis.axes:
            if operation_index in axis.operations:
                return axis
        return None

    def show_error(self, title: str, exc: Exception) -> None:
        QMessageBox.critical(self, title, str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
