import * as THREE from "/vendor/three/three.module.js";
import { TrackballControls } from "/vendor/three/addons/controls/TrackballControls.js";

// A small, self-contained 3D view for the puzzle: it draws the molecule, one
// highlighted rotation axis, faint markers at the atoms' start positions, and
// can spin the molecule about the axis (by a slider or an animation) so a valid
// order visibly lands each atom back on a start marker. It deliberately does
// not share state with the analysis viewer (StaticStructureView).

const CAMERA_FOV = 42;

export class PuzzleView {
  constructor(container) {
    this.container = container;
    this.canvas = container.querySelector("canvas");
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf4fbff);
    this.spin = new THREE.Group(); // rotates about the axis
    this.spin.matrixAutoUpdate = false;
    this.content = new THREE.Group(); // atoms + axis, child of spin
    this.spin.add(this.content);
    this.scene.add(this.spin);
    this.markerGroup = new THREE.Group(); // start markers, fixed (never rotate)
    this.scene.add(this.markerGroup);

    this.camera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 0.01, 10000);
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xb8c6d6, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.4);
    key.position.set(5, -4, 7);
    this.scene.add(key);

    this.controls = null;
    this.atomObjects = [];
    this.markerObjects = [];
    this.axisObject = null;
    this.maxAtomRadius = 0.4;
    this.spinAxis = new THREE.Vector3(0, 0, 1);
    this.rotationAnim = null;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  setMolecule(payload) {
    this.clearAxis();
    this.clearAtoms();
    this.clearMarkers();
    this.setRotation(0);
    const renderData = payload.render_data || {};
    const atoms = payload.display_atoms || renderData.atoms || [];
    const styles = new Map((payload.atom_styles || []).map((s) => [Number(s.index), s]));
    this.addAtoms(atoms, styles);
    this.fitCamera(renderData);
    this.render();
  }

  addAtoms(atoms, styles) {
    let maxRadius = 0.2;
    const geometry = new THREE.SphereGeometry(1, 28, 18);
    for (const atom of atoms) {
      if (!Array.isArray(atom.cart) || atom.cart.length !== 3) continue;
      const style = styles.get(Number(atom.source_atom ?? atom.index)) || { color: "#9aa5b1", radius: 0.35 };
      const radius = Math.max(Number(style.radius) || 0.35, 0.05);
      maxRadius = Math.max(maxRadius, radius);
      const color = new THREE.Color(style.color);
      const material = new THREE.MeshStandardMaterial({ color, roughness: 0.4, metalness: 0.03 });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.fromArray(atom.cart);
      mesh.scale.setScalar(radius);
      this.content.add(mesh);
      this.atomObjects.push(mesh);

      // A faint marker left at the start position; the atoms move over it.
      const markerMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.28,
        depthWrite: false,
      });
      const marker = new THREE.Mesh(geometry, markerMaterial);
      marker.position.fromArray(atom.cart);
      marker.scale.setScalar(radius * 1.02);
      this.markerGroup.add(marker);
      this.markerObjects.push(marker);
    }
    this.maxAtomRadius = maxRadius;
  }

  clearAtoms() {
    for (const mesh of this.atomObjects) {
      this.content.remove(mesh);
      mesh.geometry.dispose();
      mesh.material.dispose();
    }
    this.atomObjects = [];
  }

  clearMarkers() {
    for (const marker of this.markerObjects) {
      this.markerGroup.remove(marker);
      marker.material.dispose();
    }
    this.markerObjects = [];
  }

  showAxis(directionCart, pointCart, span) {
    this.clearAxis();
    const direction = new THREE.Vector3(...directionCart).normalize();
    this.spinAxis = direction.clone();
    const length = Math.max(span * 1.8, span + 4 * this.maxAtomRadius);
    const radius = Math.max(span * 0.012, this.maxAtomRadius * 0.12);
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 20);
    const material = new THREE.MeshStandardMaterial({ color: 0x2f80ed, roughness: 0.4 });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.fromArray(pointCart || [0, 0, 0]);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    this.content.add(mesh);
    this.axisObject = mesh;
    this.render();
  }

  clearAxis() {
    if (!this.axisObject) return;
    this.content.remove(this.axisObject);
    this.axisObject.geometry.dispose();
    this.axisObject.material.dispose();
    this.axisObject = null;
  }

  sceneSpan(renderData) {
    const min = renderData.bounds_min || [-1, -1, -1];
    const max = renderData.bounds_max || [1, 1, 1];
    const size = new THREE.Vector3(...max).sub(new THREE.Vector3(...min));
    return Math.max(size.x, size.y, size.z, 1);
  }

  fitCamera(renderData) {
    const box = new THREE.Box3().setFromObject(this.content);
    const center = box.isEmpty() ? new THREE.Vector3() : box.getCenter(new THREE.Vector3());
    const span = box.isEmpty() ? 4 : Math.max(...box.getSize(new THREE.Vector3()).toArray(), 1);
    const distance = (span / (2 * Math.tan(THREE.MathUtils.degToRad(CAMERA_FOV / 2)))) * 1.6;
    this.camera.position.copy(center).add(new THREE.Vector3(1, -1.2, 0.9).normalize().multiplyScalar(distance));
    this.camera.up.set(0, 0, 1);
    this.camera.near = Math.max(distance / 1000, 0.001);
    this.camera.far = distance * 20;
    this.camera.lookAt(center);
    this.camera.updateProjectionMatrix();
    this.createControls(center);
    this.resize();
  }

  createControls(target) {
    this.controls?.dispose();
    this.controls = new TrackballControls(this.camera, this.canvas);
    this.controls.rotateSpeed = 2.2;
    this.controls.staticMoving = false;
    this.controls.dynamicDampingFactor = 0.16;
    this.controls.target.copy(target);
    this.controls.addEventListener("change", () => this.render());
    this.controls.handleResize();
    this.controls.update();
  }

  // Resolve and drop any running animation so its awaiter (playActive) is not
  // left hanging when the slider or a new question interrupts it.
  cancelRotation() {
    const anim = this.rotationAnim;
    this.rotationAnim = null;
    if (anim && anim.resolve) anim.resolve();
  }

  // Rotate the molecule to an absolute angle (radians) about the highlighted
  // axis. Cancels any running animation so the slider takes over.
  setRotation(angleRad, { fromAnimation = false } = {}) {
    if (!fromAnimation) this.cancelRotation();
    this.spin.matrix.makeRotationAxis(this.spinAxis, angleRad);
    this.spin.matrixWorldNeedsUpdate = true;
    this.render();
  }

  // Animate from 0 to targetAngleRad; onProgress(fraction) drives the slider.
  playRotation(targetAngleRad, durationMs = 1600, onProgress = null) {
    this.cancelRotation();
    this.rotationAnim = { resolve: null, start: performance.now(), durationMs, onProgress, target: targetAngleRad };
    return new Promise((resolve) => {
      this.rotationAnim.resolve = resolve;
    });
  }

  updateAnimation(now) {
    if (!this.rotationAnim) return false;
    const { start, durationMs, onProgress, resolve, target } = this.rotationAnim;
    const t = Math.min((now - start) / durationMs, 1);
    this.setRotation(target * t, { fromAnimation: true });
    if (onProgress) onProgress(t);
    if (t >= 1) {
      this.rotationAnim = null;
      if (resolve) resolve();
    }
    return true;
  }

  resize() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.canvas.clientHeight || this.container.clientHeight, 1);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.controls?.handleResize();
    this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  animate(now) {
    const animating = this.updateAnimation(now);
    this.controls?.update();
    if (animating || this.controls) this.render();
    requestAnimationFrame(this.animate);
  }
}
