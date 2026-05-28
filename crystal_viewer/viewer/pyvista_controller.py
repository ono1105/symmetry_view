from __future__ import annotations

import datetime as dt
import os
import threading
import time
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pyvista as pv
from PIL import Image, ImageDraw, ImageFont

from crystal_viewer.geometry import normalize, signed_rotation_angle_from_matrix
from crystal_viewer.viewer.native_gui import NativePyVistaViewer
from crystal_viewer.viewer.animation import custom_operation_speed_multiplier, operation_speed_multiplier
from crystal_viewer.viewer.animation_context import display_equivalent_operation_context
from crystal_viewer.viewer.animation_path import build_operation_path
from crystal_viewer.viewer.atom_style import HIGHLIGHT_RADIUS_SCALE, atom_color, color_to_rgb
from crystal_viewer.viewer.display_atoms import (
    display_atom_instances,
    display_mode_margin,
    display_scene_center,
    display_scene_span,
)
from crystal_viewer.viewer.operation_labels import (
    camera_up_vector,
    custom_focus_point_cart,
    is_pure_translation_operation,
    operation_focus_point_cart,
    operation_view_direction_cart,
    rotate_vector,
    visual_translation_direction_cart,
)
from crystal_viewer.viewer.render_state import pop_render_state_snapshot
from crystal_viewer.viewer.scene_rendering import (
    add_atom_legend,
    add_orientation_axes,
    add_unit_cell,
    setup_viewer_lighting,
    viewer_background_color,
)
from crystal_viewer.viewer.symmetry_elements import (
    add_symmetry_element_actors,
    add_symmetry_elements,
    display_symmetry_elements,
)


class BrowserControlledViewer(NativePyVistaViewer):
    def __init__(
        self,
        *args,
        shared_state: dict,
        state_lock: threading.Lock,
        viewer_session=None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.shared_state = shared_state
        self.state_lock = state_lock
        self.viewer_session = viewer_session
        self.timer_interval_ms = 100
        # Disable VTK depth peeling to prevent transparency-related warning loops
        # on WSL/Mesa drivers. Translucent objects render without correct sorting
        # but without recursive PyVista→logging→VTK→PyVista error floods.
        try:
            for renderer in self.plotter.renderers:
                renderer.UseDepthPeelingOff()
        except Exception:
            pass
        self.last_operation_index: int | None = None
        self.last_scope: str | None = None
        self.last_selected_atoms: tuple[int, ...] | None = None
        self.last_element_colors: dict[str, str] | None = None
        self.last_atom_colors: dict[str, str] | None = None
        self.last_element_hidden: dict[str, bool] | None = None
        self.last_atom_hidden: dict[str, bool] | None = None
        self.last_display_mode: str | None = self.display_mode
        self.last_projection_mode: str | None = None
        self.last_background_mode: str | None = None
        self.last_improper_mode: str | None = None
        self.improper_mode = str(shared_state.get("improper_mode", "auto"))
        self.last_reload_request_id: int | None = shared_state.get("reload_request_id")
        self.last_active_mode: str | None = None
        self.last_view_request_id: int | None = None
        self.last_reset_view_request_id: int | None = None
        self.last_view_center_request_id: int | None = None
        self.last_camera_request_id: int | None = None
        self.last_gif_request_id: int | None = None
        self.last_gif_3view_request_id: int | None = None
        self.last_custom_op_check_id: object = None
        self.custom_check_actors: list = []
        self.legend_actor = None
        self.custom_view_direction_cart: np.ndarray | None = None
        self.custom_focus_cart: np.ndarray | None = None
        self.custom_speed_multiplier: float = 1.0
        self.last_custom_op_animate_id: object = None
        self.using_custom_paths: bool = False
        self.debug_timer = os.environ.get("CRYSTAL_VIEWER_DEBUG_TIMER") == "1"
        self.debug_tick_count = 0
        self.debug_render_count = 0
        self.debug_last_report = time.monotonic()

    def add_controls(self) -> None:
        self.plotter.add_key_event("space", self.toggle_play_from_keyboard)
        self.plotter.add_key_event("r", self.reset_from_keyboard)

    def on_timer(self, step: int) -> None:
        self._on_timer_inner(step)

    def _on_timer_inner(self, step: int) -> None:
        del step
        should_render = False
        should_update_status = False
        with self.state_lock:
            if self.shared_state.get("import_in_progress"):
                return
            snapshot = pop_render_state_snapshot(self.shared_state)

        reset = snapshot.reset
        self.speed = max(snapshot.speed, 0.1)
        operation_index = snapshot.operation_index
        requested_playing = snapshot.playing
        scope = snapshot.scope
        selected_atoms = snapshot.selected_atoms
        element_colors = snapshot.element_colors
        atom_colors = snapshot.atom_colors
        element_hidden = snapshot.element_hidden
        atom_hidden = snapshot.atom_hidden
        display_mode = snapshot.display_mode
        active_mode = snapshot.active_mode
        background_mode = "light" if snapshot.background_mode == "light" else "dark"

        if snapshot.reload_request_id is not None and snapshot.reload_request_id != self.last_reload_request_id:
            self.reload_from_session(
                display_mode=snapshot.display_mode,
                operation_index=snapshot.operation_index,
                scope=snapshot.scope,
                selected_atoms=snapshot.selected_atoms,
            )
            self.last_reload_request_id = snapshot.reload_request_id
            self.last_operation_index = snapshot.operation_index
            self.last_scope = snapshot.scope
            self.last_selected_atoms = snapshot.selected_atoms
            self.last_display_mode = snapshot.display_mode
            self.last_active_mode = snapshot.active_mode
            self.last_background_mode = background_mode
            self.last_custom_op_check_id = None
            should_render = True

        if background_mode != self.last_background_mode:
            self.background_mode = background_mode
            self.plotter.set_background(viewer_background_color(background_mode))
            self.update_atom_legend()
            self.last_background_mode = background_mode
            should_update_status = True
            should_render = True

        projection_mode = "orthographic" if snapshot.projection_mode == "orthographic" else "perspective"
        if projection_mode != self.last_projection_mode:
            self.set_projection_mode(projection_mode)
            self.last_projection_mode = projection_mode
            should_render = True

        if snapshot.improper_mode != self.last_improper_mode:
            self.improper_mode = snapshot.improper_mode
            self.last_improper_mode = snapshot.improper_mode
            self.clear_element_actor_cache()
            self.build_paths()
            reset = True
            should_render = True

        if element_colors != self.last_element_colors or atom_colors != self.last_atom_colors:
            self.element_colors = element_colors
            self.atom_colors = atom_colors
            if self.use_glyph_atom_rendering() != bool(self.atom_glyph_groups):
                current_display_mode = self.display_mode
                self.display_mode = ""
                self.rebuild_display_atoms(current_display_mode)
            else:
                self.apply_atom_colors()
            self.last_element_colors = dict(element_colors)
            self.last_atom_colors = dict(atom_colors)
            self.update_atom_legend()
            should_render = True

        if element_hidden != self.last_element_hidden or atom_hidden != self.last_atom_hidden:
            self.element_hidden = element_hidden
            self.atom_hidden = atom_hidden
            self.clear_glyph_atom_cache()
            current_display_mode = self.display_mode
            self.display_mode = ""
            self.rebuild_display_atoms(current_display_mode)
            self.build_paths()
            self.update_start_markers()
            self.last_element_hidden = dict(element_hidden)
            self.last_atom_hidden = dict(atom_hidden)
            reset = True
            should_render = True
            should_update_status = True

        if active_mode != self.last_active_mode:
            if active_mode == "custom":
                self.hide_element_actors()
                self.hide_start_markers()
            else:
                self.clear_custom_check_actors()
                if self.using_custom_paths:
                    self.using_custom_paths = False
                    self.build_paths()
                    reset = True
                self.show_element_actors(self.current_operation()["index"])
                self.update_start_markers()
            self.last_active_mode = active_mode
            should_render = True

        if operation_index != self.last_operation_index:
            self.set_operation_index(operation_index)
            self.last_operation_index = operation_index
            self.using_custom_paths = False
            if active_mode == "custom":
                self.hide_element_actors()
            reset = True
            should_render = True
            should_update_status = True

        if scope != self.last_scope or selected_atoms != self.last_selected_atoms:
            self.using_custom_paths = False
            self.scope = scope
            self.selected_atoms = selected_atoms
            self.build_paths()
            self.update_start_markers()
            self.last_scope = scope
            self.last_selected_atoms = selected_atoms
            reset = True
            should_render = True
            should_update_status = True

        if display_mode != self.last_display_mode:
            self.playing = False
            self.hide_element_actors()
            self.clear_element_actor_cache()
            old_display_mode = self.display_mode
            self.rebuild_display_atoms(display_mode)
            self.last_display_mode = display_mode
            self.recenter_camera_for_display_mode(old_display_mode, display_mode)
            if active_mode == "standard":
                self.show_element_actors(self.current_operation()["index"])
            reset = True
            should_render = True
            should_update_status = True

        if reset:
            self.frame_position = 0.0
            self.update_atoms(0.0)
            should_render = True

        if snapshot.view_request_id is not None and snapshot.view_request_id != self.last_view_request_id:
            self.view_along_current_operation()
            self.last_view_request_id = snapshot.view_request_id
            should_render = True

        if snapshot.reset_view_request_id is not None and snapshot.reset_view_request_id != self.last_reset_view_request_id:
            self.reset_view_center()
            self.last_reset_view_request_id = snapshot.reset_view_request_id
            should_render = True

        if snapshot.view_center_request_id is not None and snapshot.view_center_request_id != self.last_view_center_request_id:
            try:
                self.set_manual_view_center(snapshot.view_center_frac)
            except Exception as exc:
                self.set_gif_status(f"view center failed: {exc}")
                should_update_status = True
            self.last_view_center_request_id = snapshot.view_center_request_id
            should_render = True

        if snapshot.camera_request_id is not None and snapshot.camera_request_id != self.last_camera_request_id:
            self.rotate_current_camera(snapshot.camera_direction, snapshot.camera_angle)
            self.last_camera_request_id = snapshot.camera_request_id
            should_render = True

        if snapshot.gif_request_id is not None and snapshot.gif_request_id != self.last_gif_request_id:
            self.playing = False
            self.save_current_gif()
            self.last_gif_request_id = snapshot.gif_request_id
            should_update_status = True
            should_render = True

        if snapshot.gif_3view_request_id is not None and snapshot.gif_3view_request_id != self.last_gif_3view_request_id:
            self.playing = False
            self.save_three_view_gifs()
            self.last_gif_3view_request_id = snapshot.gif_3view_request_id
            should_update_status = True
            should_render = True

        if snapshot.clear_custom_check:
            self.clear_custom_check_actors()
            self.using_custom_paths = False
            self.build_paths()
            with self.state_lock:
                self.shared_state["custom_op_result"] = None
                self.shared_state["custom_op_animate"] = None
            reset = True
            should_render = True
        elif snapshot.custom_op_check_id is not None and snapshot.custom_op_check_id != self.last_custom_op_check_id:
            self.last_custom_op_check_id = snapshot.custom_op_check_id  # update first to prevent exception loops
            try:
                self.apply_custom_check(snapshot.custom_op_result)
            except Exception as exc:
                self.clear_custom_check_actors()
                self.set_gif_status(f"check highlight failed: {exc}")
                should_update_status = True
            # New check discards any previous custom animation paths
            if self.using_custom_paths:
                self.using_custom_paths = False
                self.build_paths()
                reset = True
            should_render = True

        if snapshot.custom_op_animate is not None:
            animate_id = snapshot.custom_op_animate.get("animate_id")
            if animate_id != self.last_custom_op_animate_id:
                atom_indices = snapshot.custom_op_animate.get("atom_indices", [])
                W_frac = np.asarray(snapshot.custom_op_animate.get("W_frac"), dtype=float)
                t_frac = np.asarray(snapshot.custom_op_animate.get("t_frac"), dtype=float)
                op_type = str(snapshot.custom_op_animate.get("op_type", "matrix"))
                op_params = snapshot.custom_op_animate.get("op_params") or {}
                unit_cell_only = bool(snapshot.custom_op_animate.get("unit_cell_only", False))
                self.paths = self.build_custom_animation_paths(
                    atom_indices,
                    W_frac,
                    t_frac,
                    op_type=op_type,
                    op_params=op_params,
                    unit_cell_only=unit_cell_only,
                )
                self.using_custom_paths = True
                self.custom_speed_multiplier = custom_operation_speed_multiplier(op_type)
                self.last_custom_op_animate_id = animate_id
                self.update_start_markers()
                reset = True
                should_render = True

        if requested_playing != self.playing:
            should_update_status = True
        self.playing = requested_playing
        if self.playing and self.paths:
            if self.frame_position >= self.frame_count - 1:
                self.frame_position = 0.0
            multiplier = self.custom_speed_multiplier if self.using_custom_paths else operation_speed_multiplier(self.current_operation())
            frame_step = self.speed * multiplier * (self.timer_interval_ms / 33.0)
            self.frame_position = min(self.frame_position + frame_step, self.frame_count - 1)
            self.update_atoms(self.frame_position / max(self.frame_count - 1, 1))
            should_render = True
            if self.frame_position >= self.frame_count - 1:
                self.playing = False
                should_update_status = True

        with self.state_lock:
            self.shared_state["playing"] = self.playing

        if should_update_status:
            self.update_status()
            should_render = True
        if should_render:
            self.plotter.render()
        if self.debug_timer:
            self.debug_tick_count += 1
            if should_render:
                self.debug_render_count += 1
            now = time.monotonic()
            if now - self.debug_last_report >= 5.0:
                print(
                    "viewer timer:",
                    f"ticks={self.debug_tick_count}",
                    f"renders={self.debug_render_count}",
                    f"playing={self.playing}",
                    flush=True,
                )
                self.debug_tick_count = 0
                self.debug_render_count = 0
                self.debug_last_report = now

    def set_operation_index(self, operation_index: int) -> None:
        for position, operation in enumerate(self.operations):
            if operation["index"] == operation_index:
                self.set_operation_position(position)
                return

    def show_element_actors(self, operation_index: int) -> None:
        cache_key = (operation_index, self.display_mode, self.improper_mode)
        if cache_key not in self.element_actor_cache:
            actors = add_symmetry_elements(
                self.plotter,
                self.render_data,
                self.atom_mappings,
                operation_index=operation_index,
                element_index=None,
                display_mode=self.display_mode,
                improper_mode=self.improper_mode,
            )
            self.element_actor_cache[cache_key] = actors
        self.element_actors = self.element_actor_cache[cache_key]
        for actor in self.element_actors:
            try:
                actor.SetVisibility(True)
            except Exception:
                pass

    def clear_element_actor_cache(self) -> None:
        for actors in self.element_actor_cache.values():
            for actor in actors:
                try:
                    self.plotter.remove_actor(actor)
                except Exception:
                    pass
        self.element_actor_cache = {}
        self.element_actors = []

    def reload_from_session(
        self,
        *,
        display_mode: str,
        operation_index: int,
        scope: str,
        selected_atoms: tuple[int, ...],
    ) -> None:
        if self.viewer_session is None:
            return
        debug_start = time.monotonic() if self.debug_timer else None
        self.playing = False
        self.frame_position = 0.0
        self.custom_check_actors = []
        self.custom_view_direction_cart = None
        self.custom_focus_cart = None
        self.custom_speed_multiplier = 1.0
        self.last_custom_op_animate_id = None
        self.using_custom_paths = False

        self.json_path = self.viewer_session.json_path
        self.payload = self.viewer_session.payload
        self.render_data = self.viewer_session.render_data
        self.atom_mappings = self.payload.get("atom_mappings")
        self.operations = self.render_data["operations"]
        self.operation_position = 0
        self.scope = scope
        self.selected_atoms = selected_atoms
        self.display_mode = display_mode

        self.element_actors = []
        self.element_actor_cache = {}
        self.start_marker_actors = []
        self.animated_atoms = []
        self.atom_actor_cache = {}
        self.atom_glyph_cache = {}
        self.atom_glyph_groups = []
        self.sphere_mesh_cache = {}
        self.paths = {}
        self.status_actor = None
        self.legend_actor = None

        self.plotter.clear()
        if self.debug_timer:
            print(f"[viewer] reload clear {time.monotonic() - debug_start:.3f}s", flush=True)
        self.background_mode = "light" if self.shared_state.get("background_mode") == "light" else "dark"
        setup_viewer_lighting(self.plotter, background_mode=self.background_mode)
        self.display_mode = ""
        self.rebuild_display_atoms(display_mode)
        if self.debug_timer:
            print(f"[viewer] reload atoms {time.monotonic() - debug_start:.3f}s", flush=True)
        if self.render_data.get("unit_cell"):
            add_unit_cell(self.plotter, self.render_data["unit_cell"])
        add_orientation_axes(self.plotter, unit_cell=bool(self.render_data.get("unit_cell")))
        self.update_atom_legend()
        if self.debug_timer:
            print(f"[viewer] reload axes {time.monotonic() - debug_start:.3f}s", flush=True)
        self.set_operation_index(operation_index)
        if self.debug_timer:
            print(f"[viewer] reload operation {time.monotonic() - debug_start:.3f}s", flush=True)
        self.plotter.reset_camera()
        self.set_projection_mode(str(self.shared_state.get("projection_mode", "perspective")))
        self.update_status()
        if self.debug_timer:
            print(f"[viewer] reload done {time.monotonic() - debug_start:.3f}s", flush=True)

    def atom_color(self, atom: dict) -> str:
        return atom_color(
            atom,
            element_colors=getattr(self, "element_colors", {}),
            atom_colors=getattr(self, "atom_colors", {}),
        )

    def display_atom_visible(self, display_item: dict) -> bool:
        atom = display_item["atom"]
        if getattr(self, "element_hidden", {}).get(str(atom.get("element", ""))):
            return False
        if getattr(self, "atom_hidden", {}).get(str(atom.get("index", ""))):
            return False
        return True

    def apply_atom_colors(self) -> None:
        if self.use_glyph_atom_rendering():
            for group in self.atom_glyph_groups:
                actor = group.get("actor")
                if actor is None:
                    continue
                color = self.atom_color({"element": group.get("element", ""), "atomic_number": 0})
                try:
                    actor.GetProperty().SetColor(*color_to_rgb(color))
                except Exception:
                    pass
            return
        for item in self.animated_atoms:
            actor = item.get("actor")
            if actor is None:
                continue
            color = self.atom_color(item["atom"])
            try:
                actor.GetProperty().SetColor(*color_to_rgb(color))
            except Exception:
                pass

    def update_atom_legend(self) -> None:
        if self.legend_actor is not None:
            try:
                self.plotter.remove_actor(self.legend_actor)
            except Exception:
                pass
        self.legend_actor = add_atom_legend(
            self.plotter,
            self.render_data,
            element_colors=getattr(self, "element_colors", {}),
            background_mode=getattr(self, "background_mode", "dark"),
        )

    def use_glyph_atom_rendering(self) -> bool:
        return not bool(getattr(self, "atom_colors", {}))

    def set_projection_mode(self, projection_mode: str) -> None:
        if projection_mode == "orthographic":
            self.plotter.camera.ParallelProjectionOn()
        else:
            self.plotter.camera.ParallelProjectionOff()
        self.plotter.reset_camera_clipping_range()

    def toggle_play_from_keyboard(self) -> None:
        with self.state_lock:
            self.shared_state["playing"] = not bool(self.shared_state["playing"])

    def reset_from_keyboard(self) -> None:
        with self.state_lock:
            self.shared_state["playing"] = False
            self.shared_state["reset"] = True

    def view_along_current_operation(self) -> None:
        basis = self.operation_camera_basis()
        if basis is None:
            return
        center, direction, up, distance = basis
        self.set_camera_view(center, direction, up, distance)

    def operation_camera_basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, float] | None:
        if self.custom_view_direction_cart is not None:
            direction = self.custom_view_direction_cart
            if np.linalg.norm(direction) < 1e-10:
                return None
            direction = normalize(direction)
            center = self.custom_focus_cart if self.custom_focus_cart is not None else self.display_center()
            distance = self.camera_distance_for_view(center, direction)
            up = camera_up_vector(direction)
            return center, direction, up, distance

        operation = self.current_operation()
        axes, planes, centers = display_symmetry_elements(
            self.render_data,
            self.atom_mappings,
            operation["index"],
            element_index=None,
            improper_mode=self.improper_mode,
        )
        direction = None
        if is_pure_translation_operation(operation):
            direction = visual_translation_direction_cart(self.render_data, operation, self.atom_mappings)
        if direction is None:
            direction = operation_view_direction_cart(self.render_data, operation, axes, planes, centers)
        if direction is None:
            return None
        direction = normalize(direction)
        center = operation_focus_point_cart(self.render_data, operation, axes, planes, centers, self.display_mode)
        distance = self.camera_distance_for_view(center, direction)
        up = camera_up_vector(direction)
        return center, direction, up, distance

    def set_camera_view(self, center: np.ndarray, direction: np.ndarray, up: np.ndarray, distance: float) -> None:
        scale = self.camera_parallel_scale_for_view(center, direction)
        self.plotter.camera_position = [
            tuple(center + direction * distance),
            tuple(center),
            tuple(up),
        ]
        if self.plotter.camera.GetParallelProjection():
            self.plotter.camera.SetParallelScale(scale)
        self.plotter.reset_camera_clipping_range()

    def camera_distance_for_view(self, center: np.ndarray, direction: np.ndarray) -> float:
        radius, depth = self.camera_view_extent(center, direction)
        angle = np.deg2rad(float(self.plotter.camera.GetViewAngle()))
        angle = float(np.clip(angle, np.deg2rad(12.0), np.deg2rad(70.0)))
        perspective_distance = radius / max(np.tan(angle * 0.5), 1e-6)
        depth_margin = min(depth * 0.2, radius * 1.5)
        return max(perspective_distance * 1.15 + depth_margin, radius * 2.2, 2.0)

    def camera_parallel_scale_for_view(self, center: np.ndarray, direction: np.ndarray) -> float:
        radius, _ = self.camera_view_extent(center, direction)
        return max(radius * 1.15, 0.8)

    def camera_view_extent(self, center: np.ndarray, direction: np.ndarray) -> tuple[float, float]:
        points = self.camera_reference_points()
        if points.size == 0:
            span = display_scene_span(self.render_data, self.display_mode)
            radius = max(span * 0.35, 1.0)
            return radius, span

        center = np.asarray(center, dtype=float)
        direction = normalize(np.asarray(direction, dtype=float))
        offsets = points - center
        depths = offsets @ direction
        projected = offsets - np.outer(depths, direction)
        projected_radii = np.linalg.norm(projected, axis=1)
        full_radius = float(np.max(projected_radii)) if len(projected_radii) else 1.0
        robust_radius = float(np.percentile(projected_radii, 85)) if len(projected_radii) > 4 else full_radius
        scene_span = display_scene_span(self.render_data, self.display_mode)

        source_kind = str(self.render_data.get("metadata", {}).get("mode", "crystal"))
        if source_kind == "molecule":
            radius = full_radius
        else:
            local_cap = max(scene_span * 0.22, robust_radius * 1.35, 1.0)
            radius = min(full_radius, local_cap)

        radius = max(radius, min(scene_span * 0.18, 2.0), 0.8)
        depth = float(np.max(depths) - np.min(depths)) if len(depths) else scene_span
        return radius, max(depth, 1.0)

    def camera_reference_points(self) -> np.ndarray:
        points = []
        try:
            points.extend(item["cart"] for item in display_atom_instances(self.render_data, display_mode=self.display_mode))
        except Exception:
            points.extend(np.asarray(atom["cart"], dtype=float) for atom in self.render_data.get("atoms", []))

        unit_cell = self.render_data.get("unit_cell")
        if unit_cell is not None:
            lattice = np.asarray(unit_cell["lattice"], dtype=float)
            margin = display_mode_margin(self.display_mode)
            lower = -0.5 - margin
            upper = 0.5 + margin
            corners = np.asarray(
                [
                    [x, y, z]
                    for x in (lower, upper)
                    for y in (lower, upper)
                    for z in (lower, upper)
                ],
                dtype=float,
            )
            points.extend(corners @ lattice)

        if not points:
            return np.empty((0, 3), dtype=float)
        return np.asarray(points, dtype=float)

    def rotate_current_camera(self, direction: str, angle_deg: float) -> None:
        angle = float(np.clip(angle_deg, 0.0, 180.0))
        if angle <= 1e-8:
            return
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        radius_vector = position - focal_point
        if np.linalg.norm(radius_vector) < 1e-10:
            return
        view_direction = normalize(focal_point - position)
        screen_right = normalize(np.cross(view_direction, up))
        if direction == "right":
            axis = up
            signed_angle = angle
        elif direction == "left":
            axis = up
            signed_angle = -angle
        elif direction == "up":
            axis = screen_right
            signed_angle = -angle
        elif direction == "down":
            axis = screen_right
            signed_angle = angle
        else:
            return

        rotated_radius = rotate_vector(radius_vector, axis, np.deg2rad(signed_angle))
        rotated_up = rotate_vector(up, axis, np.deg2rad(signed_angle))
        self.plotter.camera_position = [
            tuple(focal_point + rotated_radius),
            tuple(focal_point),
            tuple(normalize(rotated_up)),
        ]
        self.plotter.reset_camera_clipping_range()

    def display_center(self) -> np.ndarray:
        return display_scene_center(self.render_data, self.display_mode)

    def reset_view_center(self) -> None:
        self.set_camera_center(self.display_center())

    def set_manual_view_center(self, center_frac: list[float] | tuple[float, ...] | None) -> None:
        if center_frac is None or len(center_frac) != 3:
            coordinate_label = "fractional" if self.render_data.get("unit_cell") else "Cartesian Å"
            raise ValueError(f"enter three {coordinate_label} coordinates")
        center_frac_array = np.asarray(center_frac, dtype=float)
        if not np.all(np.isfinite(center_frac_array)):
            raise ValueError("view center must contain finite numbers")
        unit_cell = self.render_data.get("unit_cell")
        if unit_cell is None:
            new_center = center_frac_array
        else:
            lattice = np.asarray(unit_cell["lattice"], dtype=float)
            new_center = center_frac_array @ lattice
        self.set_camera_center(new_center)

    def set_camera_center(self, new_center: np.ndarray) -> None:
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        shift = new_center - focal_point
        self.plotter.camera_position = [
            tuple(position + shift),
            tuple(new_center),
            tuple(up),
        ]
        self.plotter.reset_camera_clipping_range()

    def recenter_camera_for_display_mode(self, old_display_mode: str, new_display_mode: str) -> None:
        old_center = display_scene_center(self.render_data, old_display_mode)
        new_center = display_scene_center(self.render_data, new_display_mode)
        shift = new_center - old_center
        if np.linalg.norm(shift) < 1e-10:
            return
        position = np.asarray(self.plotter.camera.GetPosition(), dtype=float)
        focal_point = np.asarray(self.plotter.camera.GetFocalPoint(), dtype=float)
        up = normalize(np.asarray(self.plotter.camera.GetViewUp(), dtype=float))
        self.plotter.camera_position = [
            tuple(position + shift),
            tuple(focal_point + shift),
            tuple(up),
        ]
        self.plotter.reset_camera_clipping_range()

    def save_current_gif(
        self,
        *,
        suffix: str | None = None,
        timestamp: str | None = None,
        label_text: str | None = None,
    ) -> bool:
        if not self.paths:
            self.set_gif_status("skipped: no animation path")
            return False
        operation = self.current_operation()
        output_path = self.gif_output_path(operation, custom=self.using_custom_paths, suffix=suffix, timestamp=timestamp)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        original_frame = float(self.frame_position)
        frames = max(self.frame_count // 2, 24)
        multiplier = self.custom_speed_multiplier if self.using_custom_paths else operation_speed_multiplier(operation)
        fps = 10.0 * max(self.speed, 0.1) * multiplier
        last_image = None
        saved = False
        self.set_gif_status(f"writing {output_path}")
        try:
            with imageio.get_writer(output_path, fps=fps, loop=0) as writer:
                for frame in range(frames):
                    s = frame / max(frames - 1, 1)
                    self.update_atoms(s)
                    self.plotter.render()
                    image = self.plotter.screenshot(return_img=True)
                    if image is not None:
                        if label_text:
                            image = add_gif_label(image, label_text)
                        writer.append_data(image)
                        last_image = image
                if last_image is not None:
                    hold_frames = max(1, int(round(fps)))
                    for _ in range(hold_frames):
                        writer.append_data(last_image)
            if last_image is not None:
                self.set_gif_status(f"saved {output_path}")
                saved = True
            else:
                self.set_gif_status("failed: no frames captured")
        except Exception as exc:
            self.set_gif_status(f"failed: {exc}")
        finally:
            self.frame_position = original_frame
            self.update_atoms(original_frame / max(self.frame_count - 1, 1))
        return saved

    def save_three_view_gifs(self) -> None:
        if not self.paths:
            self.set_gif_status("skipped: no animation path")
            return
        basis = self.operation_camera_basis()
        if basis is None:
            self.set_gif_status("skipped: no view direction")
            return

        center, front_direction, front_up, distance = basis
        front_direction = normalize(front_direction)
        front_up = normalize(front_up)
        right_direction = normalize(np.cross(front_direction, front_up))
        top_direction = front_up
        top_up = normalize(-front_direction)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        original_camera_position = self.plotter.camera_position
        views = [
            ("front", front_direction, front_up),
            ("right", right_direction, front_up),
            ("top", top_direction, top_up),
        ]
        failed_labels = []
        try:
            for label, direction, up in views:
                self.set_camera_view(center, direction, up, distance)
                if not self.save_current_gif(suffix=label, timestamp=timestamp, label_text=label):
                    failed_labels.append(label)
            if failed_labels:
                self.set_gif_status(f"3-view GIF incomplete; failed: {', '.join(failed_labels)}")
            else:
                self.set_gif_status(f"saved 3-view GIFs ({timestamp})")
        finally:
            self.plotter.camera_position = original_camera_position
            self.plotter.reset_camera_clipping_range()

    def gif_output_path(
        self,
        operation: dict,
        *,
        custom: bool = False,
        suffix: str | None = None,
        timestamp: str | None = None,
    ) -> Path:
        stem = self.json_path.stem
        scope = self.scope or "representative"
        timestamp = timestamp or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        op_label = "custom" if custom else f"op{int(operation['index']):03d}"
        suffix_part = f"_{suffix}" if suffix else ""
        filename = f"{stem}_{op_label}_{scope}{suffix_part}_{timestamp}.gif"
        return export_gif_dir(self.json_path) / stem / filename

    def set_gif_status(self, status: str) -> None:
        with self.state_lock:
            self.shared_state["gif_status"] = status

    def build_custom_animation_paths(
        self,
        atom_indices: list[int],
        W_frac: np.ndarray,
        t_frac: np.ndarray,
        *,
        op_type: str = "matrix",
        op_params: dict | None = None,
        unit_cell_only: bool = False,
    ) -> dict[int, dict]:
        """Build operation-aware animation paths for a user-supplied (W|t) operation."""
        unit_cell = self.render_data.get("unit_cell")
        if unit_cell is None:
            return {}
        lattice = np.asarray(unit_cell["lattice"], dtype=float)
        W_cart = lattice.T @ W_frac @ np.linalg.inv(lattice.T)
        t_cart = t_frac @ lattice
        op_params = op_params or {}

        # Build symmetry element dicts so build_operation_path can use arcs/reflections
        axis_dict: dict | None = None
        plane_dict: dict | None = None
        center_dict: dict | None = None

        if op_type in ("rotation", "screw"):
            uvw = np.asarray(op_params.get("axis", [0, 0, 1]), dtype=float)
            d_cart = normalize(uvw @ lattice)
            p_cart = np.asarray(op_params.get("point", [0, 0, 0]), dtype=float) @ lattice
            axis_dict = {"point_cart": p_cart.tolist(), "direction_cart": d_cart.tolist()}
        elif op_type in ("mirror", "glide"):
            hkl = np.asarray(op_params.get("normal", [0, 0, 1]), dtype=float)
            n_cart = normalize(np.linalg.inv(lattice) @ hkl)
            p_cart = np.asarray(op_params.get("point", [0, 0, 0]), dtype=float) @ lattice
            plane_dict = {"point_cart": p_cart.tolist(), "normal_cart": n_cart.tolist()}
        elif op_type == "inversion":
            c_cart = np.asarray(op_params.get("center", [0, 0, 0]), dtype=float) @ lattice
            center_dict = {"point_cart": c_cart.tolist()}
        elif op_type == "rotoinversion":
            uvw = np.asarray(op_params.get("axis", [0, 0, 1]), dtype=float)
            d_cart = normalize(uvw @ lattice)
            c_cart = np.asarray(op_params.get("center", [0, 0, 0]), dtype=float) @ lattice
            axis_dict = {"point_cart": c_cart.tolist(), "direction_cart": d_cart.tolist()}
            center_dict = {"point_cart": c_cart.tolist()}

        # Map to kind strings expected by build_operation_path
        _kind_map = {
            "rotation": "rotation_n",
            "screw": "screw_n",
            "mirror": "mirror",
            "glide": "glide",
            "inversion": "inversion",
            "rotoinversion": "rotoinversion_or_improper_n",
        }
        kind = _kind_map.get(op_type, "identity")
        angle_deg = float(op_params.get("angle", 90)) if op_params else 90.0
        fake_op = {
            "kind": kind,
            "angle_deg": angle_deg,
            "order": None,
            "matrix_cart": W_cart.tolist(),
            "translation_cart": t_cart.tolist(),
        }
        fake_op, axis_dict, plane_dict, center_dict = display_equivalent_operation_context(
            self.render_data,
            fake_op,
            axis_dict,
            plane_dict,
            center_dict,
            self.display_mode,
        )
        path_matrix = np.asarray(fake_op["matrix_cart"], dtype=float)
        path_translation = np.asarray(fake_op["translation_cart"], dtype=float)
        angle_override = None
        if op_type in ("rotation", "screw") and axis_dict is not None:
            angle_override = signed_rotation_angle_from_matrix(
                path_matrix,
                np.asarray(axis_dict["direction_cart"], dtype=float),
            )

        idx_set = set(int(i) for i in atom_indices)
        paths = {}
        for item in self.animated_atoms:
            atom = item["atom"]
            if atom["index"] not in idx_set:
                continue
            start = np.asarray(atom["cart"], dtype=float)
            target = path_matrix @ start + path_translation
            path = build_operation_path(
                start, target, fake_op,
                axis=axis_dict, plane=plane_dict, center=center_dict,
                angle_override=angle_override,
                improper_mode=self.improper_mode,
                source_kind=str(self.render_data.get("metadata", {}).get("mode", "")),
            )
            if unit_cell_only:
                path["unit_cell_only"] = True
            paths[atom["index"]] = path
        return paths

    def apply_custom_check(self, result: dict | None) -> None:
        self.clear_custom_check_actors()
        if not result or result.get("error"):
            return

        elements = result.get("elements") or {}
        axes = elements.get("axes") or []
        planes = elements.get("planes") or []
        centers = elements.get("centers") or []
        if axes or planes or centers:
            self.custom_check_actors.extend(
                add_symmetry_element_actors(
                    self.plotter,
                    self.render_data,
                    axes,
                    planes,
                    centers,
                    display_mode=self.display_mode,
                )
            )
        direction = result.get("view_direction_cart")
        if direction is not None:
            self.custom_view_direction_cart = np.asarray(direction, dtype=float)
        self.custom_focus_cart = custom_focus_point_cart(result, self.render_data, self.display_mode)

        if not result.get("unmapped"):
            return
        unmapped_set = {item["source"] for item in result["unmapped"]}
        for item in self.animated_atoms:
            atom = item["atom"]
            if atom["index"] not in unmapped_set:
                continue
            center = np.asarray(atom["cart"], dtype=float) + np.asarray(item["display_shift_cart"], dtype=float)
            radius = self.atom_radius(atom["atomic_number"]) * HIGHLIGHT_RADIUS_SCALE
            sphere = pv.Sphere(radius=radius, center=center, theta_resolution=24, phi_resolution=14)
            actor = self.plotter.add_mesh(
                sphere,
                color="#ff8a80",
                style="wireframe",
                line_width=1,
                opacity=0.55,
                lighting=False,
            )
            self.custom_check_actors.append(actor)

    def clear_custom_check_actors(self) -> None:
        for actor in self.custom_check_actors:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass
        self.custom_check_actors = []
        self.custom_view_direction_cart = None
        self.custom_focus_cart = None
        self.custom_speed_multiplier = 1.0





def export_gif_dir(json_path: Path) -> Path:
    for parent in json_path.parents:
        if parent.name == "json" and parent.parent.name == "exports":
            return parent.parent / "gifs"
    if json_path.parent.name == "exports":
        return json_path.parent / "gifs"
    return json_path.parent / "gifs"


def add_gif_label(image: np.ndarray, label: str) -> np.ndarray:
    pil_image = Image.fromarray(np.asarray(image))
    draw = ImageDraw.Draw(pil_image, "RGBA")
    text = str(label).lower()
    width, height = pil_image.size
    font_size = max(24, min(width, height) // 12)
    font = gif_label_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    padding_x = max(12, font_size // 2)
    padding_y = max(8, font_size // 3)
    box_width = bbox[2] - bbox[0] + padding_x * 2
    box_height = bbox[3] - bbox[1] + padding_y * 2
    x = 14
    y = 14
    draw.rectangle(
        (x, y, x + box_width, y + box_height),
        fill=(0, 0, 0, 185),
        outline=(255, 255, 255, 230),
        width=max(2, font_size // 14),
    )
    draw.text(
        (x + padding_x, y + padding_y - bbox[1]),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return np.asarray(pil_image)


def gif_label_font(font_size: int):
    for font_name in (
        "Inter-Bold.otf",
        "NotoSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()
