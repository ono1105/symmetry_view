import * as THREE from "/vendor/three/three.module.js";
import { TrackballControls } from "/vendor/three/addons/controls/TrackballControls.js";
import {
  applyBoundaryContext,
  evaluatePath,
  pathAppliesToDisplayInstance,
} from "/static/animation_path.js";


const CAMERA_FOV = 42;
const ORTHOGRAPHIC_HEIGHT = 10;
const BASE_ANIMATION_SECONDS = 3.15;


class StaticStructureView {
  constructor(container) {
    this.container = container;
    this.status = container.querySelector("[data-three-status]");
    this.canvas = container.querySelector("canvas");
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b0f14);
    this.content = new THREE.Group();
    this.scene.add(this.content);

    this.perspectiveCamera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 0.01, 10000);
    this.orthographicCamera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.01, 10000);
    this.activeCamera = this.perspectiveCamera;
    this.renderer = new THREE.WebGLRenderer({canvas: this.canvas, antialias: true});
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = null;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x263342, 2.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
    keyLight.position.set(5, -4, 7);
    this.scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x8ec5ff, 1.2);
    fillLight.position.set(-4, 3, -2);
    this.scene.add(fillLight);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
    this.lastStateSignature = "";
    this.state = {};
    this.atomInstances = new Map();
    this.instanceMeshes = new Set();
    this.animationPaths = new Map();
    this.boundaryContext = {mode: "continuous"};
    this.animationOperationIndex = null;
    this.symmetryOperationIndex = null;
    this.symmetryObjects = [];
    this.startMarkerObjects = [];
    this.animationProgress = 0;
    this.animationStartedAt = null;
    this.playing = false;
    this.playbackSpeedMultiplier = 1;
    this.baseStatus = "Three.js comparison";
    this.lastProgressBucket = -1;
    this.pathGeneration = 0;
    this.syncQueue = Promise.resolve();
    this.serverPlaying = false;
    this.tempMatrix = new THREE.Matrix4();
    this.tempPosition = new THREE.Vector3();
    this.tempScale = new THREE.Vector3();
    this.tempQuaternion = new THREE.Quaternion();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  async refresh() {
    this.setStatus("Loading Three.js view…");
    const response = await fetch("/api/render_data");
    if (!response.ok) {
      throw new Error(await response.text() || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    if (payload.coordinate_space !== "cartesian") {
      throw new Error(`Unsupported coordinate space: ${payload.coordinate_space}`);
    }
    this.setData(payload);
  }

  setData(payload) {
    this.clearContent();
    const renderData = payload.render_data || {};
    const atoms = payload.display_atoms || renderData.atoms || [];
    const styles = new Map((payload.atom_styles || []).map(style => [Number(style.index), style]));
    this.addAtoms(atoms, styles);
    if (payload.source_kind === "crystal" && payload.display_unit_cell) {
      this.addUnitCell(payload.display_unit_cell);
    }
    this.fitCamera(renderData);
    this.renderData = renderData;
    this.animationOperationIndex = null;
    this.symmetryOperationIndex = null;
    const kind = payload.source_kind === "molecule" ? "molecule" : "crystal";
    this.baseStatus = `Three.js comparison: ${atoms.length} atoms (${kind})`;
    this.setStatus(`${this.baseStatus}, animation ready`);
    this.render();
  }

  addAtoms(atoms, styles) {
    this.atomInstances.clear();
    const groups = new Map();
    for (const atom of atoms) {
      if (!Array.isArray(atom.cart) || atom.cart.length !== 3) continue;
      const sourceAtom = Number(atom.source_atom ?? atom.index);
      const style = styles.get(sourceAtom) || {color: "#9aa5b1", radius: 0.35};
      const radius = Math.max(Number(style.radius) || 0.35, 0.02);
      const key = `${style.color}|${radius.toFixed(8)}`;
      if (!groups.has(key)) groups.set(key, {style, radius, atoms: []});
      groups.get(key).atoms.push(atom);
    }

    const geometry = new THREE.SphereGeometry(1, 28, 18);
    const matrix = new THREE.Matrix4();
    for (const group of groups.values()) {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(group.style.color),
        roughness: 0.34,
        metalness: 0.04,
      });
      const mesh = new THREE.InstancedMesh(geometry, material, group.atoms.length);
      mesh.frustumCulled = false;
      this.instanceMeshes.add(mesh);
      group.atoms.forEach((atom, instanceIndex) => {
        matrix.compose(
          new THREE.Vector3(...atom.cart),
          new THREE.Quaternion(),
          new THREE.Vector3(group.radius, group.radius, group.radius),
        );
        mesh.setMatrixAt(instanceIndex, matrix);
        const instanceId = Number(atom.instance_id ?? atom.index);
        this.atomInstances.set(instanceId, {
          mesh,
          instanceIndex,
          sourceAtom: Number(atom.source_atom ?? atom.index),
          isPrimaryImage: atom.is_primary_image !== false,
          radius: group.radius,
          start: [...atom.cart],
        });
      });
      mesh.instanceMatrix.needsUpdate = true;
      this.content.add(mesh);
    }
  }

  addUnitCell(unitCell) {
    const vertices = unitCell.vertices_cart || [];
    const positions = [];
    for (const edge of unitCell.edges || []) {
      const start = vertices[edge[0]];
      const end = vertices[edge[1]];
      if (!start || !end) continue;
      positions.push(...start, ...end);
    }
    if (!positions.length) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const material = new THREE.LineBasicMaterial({color: 0xa8b5c5, transparent: true, opacity: 0.82});
    this.content.add(new THREE.LineSegments(geometry, material));
  }

  clearContent() {
    this.symmetryObjects = [];
    this.startMarkerObjects = [];
    this.atomInstances.clear();
    this.instanceMeshes.clear();
    for (const child of [...this.content.children]) {
      this.content.remove(child);
      child.traverse(object => {
        object.geometry?.dispose();
        if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
        else object.material?.dispose();
      });
    }
  }

  fitCamera(renderData) {
    const box = new THREE.Box3().setFromObject(this.content);
    if (box.isEmpty()) {
      const minimum = renderData.bounds_min || [-1, -1, -1];
      const maximum = renderData.bounds_max || [1, 1, 1];
      box.set(new THREE.Vector3(...minimum), new THREE.Vector3(...maximum));
    }
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const span = Math.max(size.x, size.y, size.z, 1);
    const distance = span / (2 * Math.tan(THREE.MathUtils.degToRad(CAMERA_FOV / 2))) * 1.45;
    const position = center.clone().add(new THREE.Vector3(1, -1.35, 0.9).normalize().multiplyScalar(distance));
    for (const camera of [this.perspectiveCamera, this.orthographicCamera]) {
      camera.position.copy(position);
      camera.up.set(0, 0, 1);
      camera.lookAt(center);
      camera.near = Math.max(distance / 1000, 0.001);
      camera.far = Math.max(distance * 20, 100);
      camera.updateProjectionMatrix();
    }
    this.orthographicSpan = span * 1.45;
    this.createControls(center);
    this.resize();
  }

  createControls(target) {
    this.controls?.dispose();
    this.controls = new TrackballControls(this.activeCamera, this.canvas);
    this.controls.rotateSpeed = 1.15;
    this.controls.zoomSpeed = 1.05;
    this.controls.panSpeed = 0.65;
    this.controls.staticMoving = false;
    this.controls.dynamicDampingFactor = 0.14;
    this.controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
    this.controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY;
    this.controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
    this.controls.target.copy(target);
    this.controls.addEventListener("change", () => this.render());
    this.controls.handleResize();
    this.controls.update();
  }

  setProjection(mode) {
    const nextCamera = mode === "orthographic" ? this.orthographicCamera : this.perspectiveCamera;
    if (nextCamera === this.activeCamera) return;
    nextCamera.position.copy(this.activeCamera.position);
    nextCamera.quaternion.copy(this.activeCamera.quaternion);
    const target = this.controls?.target.clone() || new THREE.Vector3();
    this.activeCamera = nextCamera;
    this.createControls(target);
    this.resize();
  }

  syncState(state, update = {}) {
    this.syncQueue = this.syncQueue
      .catch(() => {})
      .then(() => this.applyState(state, update));
    return this.syncQueue;
  }

  async applyState(state, update = {}) {
    const previousOperation = this.state.operation_index;
    const displayLayoutChanged = this.state.operation_index !== undefined && (
      state.display_mode !== this.state.display_mode
      || state.cell_origin_mode !== this.state.cell_origin_mode
    );
    this.state = {...state};
    if (displayLayoutChanged) await this.refresh();
    this.setProjection(state.projection_mode);
    const operationChanged = Number(state.operation_index) !== Number(previousOperation);
    const pathOptionsChanged = operationChanged || [
      "scope",
      "selected_atoms",
      "improper_mode",
      "display_mode",
      "cell_origin_mode",
      "animation_boundary_mode",
      "structure_reload",
    ].some(key => Object.prototype.hasOwnProperty.call(update, key));
    if (pathOptionsChanged || this.animationOperationIndex === null) {
      const generation = ++this.pathGeneration;
      await Promise.all([
        this.loadAnimationPaths(Number(state.operation_index), generation),
        this.loadSymmetryElements(Number(state.operation_index), generation),
      ]);
      if (generation !== this.pathGeneration) return;
      this.resetAnimation();
    }
    if (update.reset) {
      this.resetAnimation();
    }
    const nextServerPlaying = Boolean(state.playing) && state.active_mode !== "custom";
    const starting = nextServerPlaying && !this.serverPlaying;
    if (starting && this.animationProgress >= 1) {
      this.resetAnimation();
    }
    if (starting) this.showStartMarkers();
    this.serverPlaying = nextServerPlaying;
    this.playing = nextServerPlaying && this.animationProgress < 1;
    if (this.playing) {
      this.animationStartedAt = null;
    } else {
      this.animationStartedAt = null;
    }
  }

  async loadAnimationPaths(operationIndex, generation) {
    if (!Number.isInteger(operationIndex)) return;
    const response = await fetch(`/api/animation_path?operation_index=${operationIndex}`);
    if (!response.ok) {
      throw new Error(await response.text() || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    if (generation !== this.pathGeneration) return;
    this.animationPaths = new Map(
      (payload.paths || []).map(item => [Number(item.source_atom), item.path]),
    );
    this.boundaryContext = payload.boundary || {mode: "continuous"};
    this.animationOperationIndex = operationIndex;
    this.playbackSpeedMultiplier = Math.max(Number(payload.playback_speed_multiplier) || 1, 0.01);
  }

  async loadSymmetryElements(operationIndex, generation) {
    if (!Number.isInteger(operationIndex)) return;
    const response = await fetch(`/api/symmetry_elements?operation_index=${operationIndex}`);
    if (!response.ok) {
      throw new Error(await response.text() || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    if (generation !== this.pathGeneration) return;
    this.clearSymmetryElements();
    const span = this.sceneSpan();
    for (const axis of payload.axes || []) this.addAxis(axis, span);
    for (const plane of payload.planes || []) this.addPlane(plane, span);
    for (const center of payload.centers || []) this.addCenter(center, span);
    if ((payload.planes || []).length && Array.isArray(payload.glide_translation_cart)) {
      this.addGlideArrow(payload.planes[0], payload.glide_translation_cart, span);
    }
    this.symmetryOperationIndex = operationIndex;
  }

  addAxis(axis, span) {
    const point = new THREE.Vector3(...axis.point_cart);
    const direction = new THREE.Vector3(...axis.direction_cart).normalize();
    const length = span * 1.45;
    const geometry = new THREE.CylinderGeometry(span * 0.009, span * 0.009, length, 16);
    const material = new THREE.MeshBasicMaterial({color: 0x38bdf8, transparent: true, opacity: 0.92});
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(point);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    mesh.renderOrder = 3;
    this.addSymmetryObject(mesh);
  }

  addPlane(plane, span) {
    const point = new THREE.Vector3(...plane.point_cart);
    const basis1 = new THREE.Vector3(...plane.basis1_cart).normalize().multiplyScalar(span * 0.52);
    const basis2 = new THREE.Vector3(...plane.basis2_cart).normalize().multiplyScalar(span * 0.52);
    const corners = [
      point.clone().sub(basis1).sub(basis2),
      point.clone().add(basis1).sub(basis2),
      point.clone().add(basis1).add(basis2),
      point.clone().sub(basis1).add(basis2),
    ];
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute([
      ...corners[0].toArray(), ...corners[1].toArray(), ...corners[2].toArray(),
      ...corners[0].toArray(), ...corners[2].toArray(), ...corners[3].toArray(),
    ], 3));
    const material = new THREE.MeshBasicMaterial({
      color: 0xa78bfa,
      transparent: true,
      opacity: 0.24,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = 1;
    this.addSymmetryObject(mesh);

    const outlineGeometry = new THREE.BufferGeometry().setFromPoints([...corners, corners[0]]);
    const outline = new THREE.Line(
      outlineGeometry,
      new THREE.LineBasicMaterial({color: 0xc4b5fd, transparent: true, opacity: 0.9}),
    );
    outline.renderOrder = 2;
    this.addSymmetryObject(outline);
  }

  addCenter(center, span) {
    const size = Math.max(span * 0.09, 0.18);
    const boxGeometry = new THREE.BoxGeometry(size, size, size);
    const geometry = new THREE.EdgesGeometry(boxGeometry);
    boxGeometry.dispose();
    const material = new THREE.LineBasicMaterial({
      color: 0xef4444,
      transparent: true,
      opacity: 0.95,
      depthTest: false,
    });
    const cube = new THREE.LineSegments(geometry, material);
    cube.position.set(...center.point_cart);
    cube.renderOrder = 4;
    this.addSymmetryObject(cube);
  }

  addGlideArrow(plane, translation, span) {
    const vector = new THREE.Vector3(...translation);
    if (vector.lengthSq() < 1e-16) return;
    const direction = vector.normalize();
    const length = span * 0.42;
    const origin = new THREE.Vector3(...plane.point_cart).addScaledVector(direction, -length * 0.5);
    const arrow = new THREE.ArrowHelper(
      direction,
      origin,
      length,
      0xd6b65c,
      Math.max(span * 0.07, 0.12),
      Math.max(span * 0.028, 0.055),
    );
    arrow.line.material.transparent = true;
    arrow.line.material.opacity = 0.58;
    arrow.cone.material.transparent = true;
    arrow.cone.material.opacity = 0.62;
    arrow.renderOrder = 4;
    this.addSymmetryObject(arrow);
  }

  addSymmetryObject(object) {
    this.symmetryObjects.push(object);
    this.content.add(object);
  }

  clearSymmetryElements() {
    for (const object of this.symmetryObjects) {
      this.content.remove(object);
      object.traverse(child => {
        child.geometry?.dispose();
        if (Array.isArray(child.material)) child.material.forEach(material => material.dispose());
        else child.material?.dispose();
      });
    }
    this.symmetryObjects = [];
  }

  sceneSpan() {
    const minimum = this.renderData?.bounds_min || [-1, -1, -1];
    const maximum = this.renderData?.bounds_max || [1, 1, 1];
    const size = new THREE.Vector3(...maximum).sub(new THREE.Vector3(...minimum));
    return Math.max(size.x, size.y, size.z, 1);
  }

  resetAnimation() {
    this.animationProgress = 0;
    this.animationStartedAt = null;
    this.lastProgressBucket = -1;
    this.clearStartMarkers();
    for (const [instanceId, instance] of this.atomInstances) {
      this.setAtomPosition(instanceId, instance.start);
    }
    this.markInstanceMatricesDirty();
    if (this.baseStatus) this.setStatus(`${this.baseStatus}, animation ready`);
    this.render();
  }

  showStartMarkers() {
    this.clearStartMarkers();
    for (const instance of this.atomInstances.values()) {
      const path = this.animationPaths.get(instance.sourceAtom);
      if (!pathAppliesToDisplayInstance(path, instance)) continue;
      const geometry = new THREE.SphereGeometry(instance.radius * 0.98, 20, 12);
      const material = new THREE.MeshBasicMaterial({
        color: 0xf7dc6f,
        transparent: true,
        opacity: 0.3,
        depthWrite: false,
      });
      const marker = new THREE.Mesh(geometry, material);
      marker.position.fromArray(instance.start);
      marker.renderOrder = 2;
      this.startMarkerObjects.push(marker);
      this.content.add(marker);
    }
    this.container.dataset.startMarkerCount = String(this.startMarkerObjects.length);
    this.render();
  }

  clearStartMarkers() {
    for (const marker of this.startMarkerObjects) {
      this.content.remove(marker);
      marker.geometry.dispose();
      marker.material.dispose();
    }
    this.startMarkerObjects = [];
    this.container.dataset.startMarkerCount = "0";
  }

  updateAnimation(timestamp) {
    if (!this.playing || !this.animationPaths.size) return false;
    if (this.animationStartedAt === null) {
      this.animationStartedAt = timestamp - this.animationProgress * this.animationDurationMs();
    }
    this.animationProgress = Math.min(
      (timestamp - this.animationStartedAt) / this.animationDurationMs(),
      1,
    );
    for (const [instanceId, instance] of this.atomInstances) {
      const path = this.animationPaths.get(instance.sourceAtom);
      const applies = pathAppliesToDisplayInstance(path, instance);
      const evaluated = applies
        ? evaluatePath(path, this.animationProgress, instance.start)
        : instance.start;
      const position = applies
        ? applyBoundaryContext(evaluated, this.boundaryContext)
        : evaluated;
      this.setAtomPosition(instanceId, position);
    }
    this.markInstanceMatricesDirty();
    const progressBucket = Math.floor(this.animationProgress * 20);
    if (progressBucket !== this.lastProgressBucket) {
      this.lastProgressBucket = progressBucket;
      this.setStatus(`${this.baseStatus}, animation ${Math.round(this.animationProgress * 100)}%`);
    }
    if (this.animationProgress >= 1) {
      this.playing = false;
      this.animationStartedAt = null;
      this.setStatus(`${this.baseStatus}, animation complete`);
    }
    return true;
  }

  animationDurationMs() {
    const speed = Math.max(Number(this.state.speed) || 1, 0.1);
    return BASE_ANIMATION_SECONDS * 1000 / speed / this.playbackSpeedMultiplier;
  }

  setAtomPosition(instanceId, position) {
    const instance = this.atomInstances.get(Number(instanceId));
    if (!instance) return;
    this.tempPosition.fromArray(position);
    this.tempScale.setScalar(instance.radius);
    this.tempMatrix.compose(this.tempPosition, this.tempQuaternion, this.tempScale);
    instance.mesh.setMatrixAt(instance.instanceIndex, this.tempMatrix);
  }

  markInstanceMatricesDirty() {
    for (const mesh of this.instanceMeshes) {
      mesh.instanceMatrix.needsUpdate = true;
    }
  }

  resize() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.canvas.clientHeight, 1);
    this.renderer.setSize(width, height, false);
    this.perspectiveCamera.aspect = width / height;
    this.perspectiveCamera.updateProjectionMatrix();
    const span = this.orthographicSpan || ORTHOGRAPHIC_HEIGHT;
    this.orthographicCamera.left = -span * width / height / 2;
    this.orthographicCamera.right = span * width / height / 2;
    this.orthographicCamera.top = span / 2;
    this.orthographicCamera.bottom = -span / 2;
    this.orthographicCamera.updateProjectionMatrix();
    this.controls?.handleResize();
    this.render();
  }

  render() {
    this.renderer.render(this.scene, this.activeCamera);
  }

  animate(timestamp) {
    const animationChanged = this.updateAnimation(timestamp);
    this.controls?.update();
    if (animationChanged) this.render();
    requestAnimationFrame(this.animate);
  }

  setStatus(message) {
    if (this.status) this.status.textContent = message;
  }
}


async function initialize() {
  const container = document.getElementById("three-view");
  if (!container) return;
  const view = new StaticStructureView(container);
  window.symmetryThreeView = view;
  try {
    await view.refresh();
    const stateResponse = await fetch("/api/state");
    if (stateResponse.ok) {
      const initialState = await stateResponse.json();
      await view.syncState(initialState);
      view.lastStateSignature = `${initialState.json_path || ""}|${initialState.reload_request_id || 0}`;
    }
  } catch (error) {
    view.setStatus(`Three.js error: ${error.message}`);
  }

  let pollInProgress = false;
  setInterval(async () => {
    if (pollInProgress) return;
    pollInProgress = true;
    try {
      const response = await fetch("/api/state");
      if (!response.ok) return;
      const state = await response.json();
      const signature = `${state.json_path || ""}|${state.reload_request_id || 0}`;
      if (signature !== view.lastStateSignature) {
        await view.refresh();
        await view.syncState(state, {structure_reload: true});
      } else {
        await view.syncState(state);
      }
      view.lastStateSignature = signature;
    } catch (error) {
      view.setStatus(`Three.js refresh error: ${error.message}`);
    } finally {
      pollInProgress = false;
    }
  }, 1000);

  window.addEventListener("symmetry-state-update", event => {
    const detail = event.detail || {};
    view.syncState(detail.state || {}, detail.update || {}).catch(error => {
      view.setStatus(`Three.js animation error: ${error.message}`);
    });
  });
}


initialize().catch(error => {
  const status = document.querySelector("[data-three-status]");
  if (status) status.textContent = `Three.js initialization error: ${error.message}`;
  console.error("Three.js initialization failed", error);
});
