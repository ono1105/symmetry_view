from __future__ import annotations

import numpy as np
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkLine, vtkPolyData, vtkPolygon
from vtkmodules.vtkFiltersCore import vtkTubeFilter
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from .models import CrystalStructureData, RenderAxis, RenderCenter, RenderPlane


ELEMENT_COLORS = {
    "H": "#f4f4f4",
    "C": "#444444",
    "N": "#3050f8",
    "O": "#ff0d0d",
    "F": "#90e050",
    "P": "#ff8000",
    "S": "#ffff30",
    "Cl": "#1ff01f",
    "Na": "#ab5cf2",
    "Mg": "#8aff00",
    "Al": "#bfa6a6",
    "Si": "#f0c8a0",
    "K": "#8f40d4",
    "Ca": "#3dff00",
    "Fe": "#e06633",
    "Cu": "#c88033",
    "Zn": "#7d80b0",
    "Ga": "#c28f8f",
    "As": "#bd80e3",
}


class CrystalViewer:
    def __init__(self, interactor: QVTKRenderWindowInteractor):
        self.widget = interactor
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.062, 0.071, 0.086)
        self.widget.GetRenderWindow().AddRenderer(self.renderer)
        self.widget.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self.initialized = False

        self.structure: CrystalStructureData | None = None
        self.show_atoms = True
        self.show_unit_cell = True
        self.show_symmetry = True
        self.atom_actors: dict[int, vtkActor] = {}
        self.atom_centers: dict[int, np.ndarray] = {}
        self.cell_actors: list[vtkActor] = []
        self.symmetry_actors: list[vtkActor] = []

    def set_structure(self, structure: CrystalStructureData) -> None:
        self.structure = structure
        self.atom_centers = {atom.index: np.asarray(atom.cart, dtype=float) for atom in structure.atoms}
        self.clear_scene()
        self.draw_structure()
        self.reset_view()

    def clear_scene(self) -> None:
        self.renderer.RemoveAllViewProps()
        self.atom_actors.clear()
        self.cell_actors.clear()
        self.symmetry_actors.clear()

    def draw_structure(self) -> None:
        if self.structure is None:
            return
        if self.show_atoms:
            self.draw_atoms()
        if self.show_unit_cell:
            self.draw_unit_cell()
        self.render()

    def redraw_structure(self) -> None:
        self.clear_scene()
        self.draw_structure()

    def draw_atoms(self) -> None:
        if self.structure is None:
            return

        for atom in self.structure.atoms:
            color = ELEMENT_COLORS.get(atom.element, "#9aa5b1")
            radius = atom_radius(atom.atomic_number)
            actor = make_sphere_actor(
                self.atom_centers[atom.index],
                radius,
                "#f7d774" if atom.selected else color,
                theta_resolution=24,
                phi_resolution=16,
            )
            self.renderer.AddActor(actor)
            self.atom_actors[atom.index] = actor

    def draw_unit_cell(self) -> None:
        if self.structure is None:
            return

        lattice = self.structure.lattice
        a, b, c = lattice[0], lattice[1], lattice[2]
        vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                a,
                b,
                c,
                a + b,
                a + c,
                b + c,
                a + b + c,
            ]
        )
        edges = [
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 4),
            (1, 5),
            (2, 4),
            (2, 6),
            (3, 5),
            (3, 6),
            (4, 7),
            (5, 7),
            (6, 7),
        ]
        points = vtkPoints()
        for vertex in vertices:
            points.InsertNextPoint(*vertex)
        cells = vtkCellArray()
        for start, end in edges:
            line = vtkLine()
            line.GetPointIds().SetId(0, start)
            line.GetPointIds().SetId(1, end)
            cells.InsertNextCell(line)
        poly = vtkPolyData()
        poly.SetPoints(points)
        poly.SetLines(cells)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*hex_to_rgb("#d6dde6"))
        actor.GetProperty().SetLineWidth(2)
        self.renderer.AddActor(actor)
        self.cell_actors.append(actor)

    def draw_symmetry_elements(
        self,
        axes: list[RenderAxis],
        planes: list[RenderPlane],
        centers: list[RenderCenter],
        operation_index: int | None = None,
    ) -> None:
        self.clear_symmetry_elements()
        if not self.show_symmetry:
            return

        axes = filter_by_operation(axes, operation_index)
        planes = filter_by_operation(planes, operation_index)
        centers = filter_by_operation(centers, operation_index)

        length = self.scene_length()
        for axis in axes:
            direction = axis.direction_cart / max(np.linalg.norm(axis.direction_cart), 1e-12)
            actor = make_line_actor(
                axis.point_cart - length * direction,
                axis.point_cart + length * direction,
                "#58d68d",
                width=5,
            )
            self.renderer.AddActor(actor)
            self.symmetry_actors.append(actor)

        scale = max(length * 0.35, 0.3)
        for plane in planes:
            v1 = normalized(plane.basis1_cart) * scale
            v2 = normalized(plane.basis2_cart) * scale
            plane_points = np.array(
                [
                    plane.point_cart - v1 - v2,
                    plane.point_cart + v1 - v2,
                    plane.point_cart + v1 + v2,
                    plane.point_cart - v1 + v2,
                ]
            )
            actor = make_plane_actor(plane_points, "#5dade2", opacity=0.35)
            self.renderer.AddActor(actor)
            self.symmetry_actors.append(actor)

        for center in centers:
            actor = make_sphere_actor(center.point_cart, max(length * 0.035, 0.08), "#ff5f57")
            self.renderer.AddActor(actor)
            self.symmetry_actors.append(actor)

        self.render()

    def clear_symmetry_elements(self) -> None:
        for actor in self.symmetry_actors:
            self.renderer.RemoveActor(actor)
        self.symmetry_actors.clear()
        self.render()

    def set_atom_positions(self, positions: dict[int, np.ndarray]) -> None:
        for atom_index, position in positions.items():
            actor = self.atom_actors.get(atom_index)
            original = self.atom_centers.get(atom_index)
            if actor is not None and original is not None:
                actor.SetPosition(*(np.asarray(position) - original))
        self.render()

    def commit_atom_positions(self, positions: dict[int, np.ndarray]) -> None:
        if self.structure is None:
            return
        inverse_lattice = np.linalg.inv(self.structure.lattice)
        for atom in self.structure.atoms:
            if atom.index in positions:
                cart = np.asarray(positions[atom.index], dtype=float)
                atom.cart = cart
                atom.frac = np.mod(cart @ inverse_lattice, 1.0)
                self.atom_centers[atom.index] = cart
                actor = self.atom_actors.get(atom.index)
                if actor is not None:
                    actor.SetPosition(0.0, 0.0, 0.0)
        self.redraw_structure()

    def set_selected_atoms(self, selected_indices: set[int]) -> None:
        if self.structure is None:
            return
        for atom in self.structure.atoms:
            atom.selected = atom.index in selected_indices
        self.redraw_structure()

    def scene_length(self) -> float:
        if self.structure is None:
            return 1.0
        return float(max(np.linalg.norm(v) for v in self.structure.lattice))

    def reset_view(self) -> None:
        self.renderer.ResetCamera()
        self.render()

    def initialize_interactor(self) -> None:
        if self.initialized:
            return
        self.widget.Initialize()
        self.widget.GetRenderWindow().GetInteractor().Enable()
        self.initialized = True
        self.render()

    def render(self) -> None:
        if not self.initialized:
            return
        self.widget.GetRenderWindow().Render()


def normalized(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        return vec
    return vec / norm


def filter_by_operation(elements, operation_index: int | None):
    if operation_index is None:
        return elements
    return [element for element in elements if operation_index in element.operations]


def atom_radius(atomic_number: int) -> float:
    if atomic_number <= 2:
        return 0.22
    if atomic_number <= 10:
        return 0.32
    if atomic_number <= 18:
        return 0.38
    return 0.45


def make_sphere_actor(
    center: np.ndarray,
    radius: float,
    color: str,
    theta_resolution: int = 24,
    phi_resolution: int = 16,
) -> vtkActor:
    source = vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(theta_resolution)
    source.SetPhiResolution(phi_resolution)
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*hex_to_rgb(color))
    actor.GetProperty().SetSpecular(0.25)
    actor.GetProperty().SetSpecularPower(20)
    return actor


def make_line_actor(start: np.ndarray, end: np.ndarray, color: str, width: float = 3.0) -> vtkActor:
    points = vtkPoints()
    points.InsertNextPoint(*start)
    points.InsertNextPoint(*end)
    line = vtkLine()
    line.GetPointIds().SetId(0, 0)
    line.GetPointIds().SetId(1, 1)
    cells = vtkCellArray()
    cells.InsertNextCell(line)
    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(cells)
    tube = vtkTubeFilter()
    tube.SetInputData(poly)
    tube.SetRadius(width * 0.01)
    tube.SetNumberOfSides(12)
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(tube.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*hex_to_rgb(color))
    return actor


def make_plane_actor(points_array: np.ndarray, color: str, opacity: float) -> vtkActor:
    points = vtkPoints()
    for point in points_array:
        points.InsertNextPoint(*point)
    polygon = vtkPolygon()
    polygon.GetPointIds().SetNumberOfIds(4)
    for i in range(4):
        polygon.GetPointIds().SetId(i, i)
    cells = vtkCellArray()
    cells.InsertNextCell(polygon)
    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(poly)
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*hex_to_rgb(color))
    actor.GetProperty().SetOpacity(opacity)
    actor.GetProperty().SetEdgeVisibility(True)
    actor.GetProperty().SetLineWidth(1)
    return actor


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
