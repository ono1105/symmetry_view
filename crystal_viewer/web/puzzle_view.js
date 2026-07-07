import * as THREE from "/vendor/three/three.module.js";
import { TrackballControls } from "/vendor/three/addons/controls/TrackballControls.js";

// A small, self-contained 3D view for the puzzle: it draws the molecule, one
// highlighted rotation axis, and can spin the whole molecule about that axis to
// reveal whether a candidate order maps it onto itself. It deliberately does
// not share state with the analysis viewer (StaticStructureView).

const CAMERA_FOV = 42;

export class PuzzleView {
  constructor(container) {
    this.container = container;
    this.canvas = container.querySelector("canvas");
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf4fbff);
    this.spin = new THREE.Group(); // transforms for the reveal (rotation or Sn)
    this.spin.matrixAutoUpdate = false;
    this.content = new THREE.Group(); // atoms + axis, child of spin
    this.spin.add(this.content);
    this.scene.add(this.spin);

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
    this.axisObject = null;
    this.maxAtomRadius = 0.4;
    this.spinAxis = new THREE.Vector3(0, 0, 1);
    this.reveal = null;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  setMolecule(payload) {
    this.clearAxis();
    this.clearAtoms();
    this.resetSpin();
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
      const material = new THREE.MeshStandardMaterial({ color: new THREE.Color(style.color), roughness: 0.4, metalness: 0.03 });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.fromArray(atom.cart);
      mesh.scale.setScalar(radius);
      this.content.add(mesh);
      this.atomObjects.push(mesh);
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

  resetSpin() {
    this.spin.matrix.identity();
    this.spin.matrixWorldNeedsUpdate = true;
    this.reveal = null;
  }

  rotationMatrix(angle) {
    return new THREE.Matrix4().makeRotationAxis(this.spinAxis, angle);
  }

  // Reflection through the plane perpendicular to the axis, faded in by s in
  // [0,1] (I - 2s·nnᵀ). At s=1 it is a full mirror; the pass through s=0.5
  // reads as folding the molecule through the plane.
  reflectionMatrix(s) {
    const { x, y, z } = this.spinAxis;
    return new THREE.Matrix4().set(
      1 - 2 * s * x * x, -2 * s * x * y, -2 * s * x * z, 0,
      -2 * s * x * y, 1 - 2 * s * y * y, -2 * s * y * z, 0,
      -2 * s * x * z, -2 * s * y * z, 1 - 2 * s * z * z, 0,
      0, 0, 0, 1,
    );
  }

  // Play the operation once about the highlighted axis: a rotation by angleDeg,
  // or (improper) that rotation followed by a reflection through the
  // perpendicular plane. A valid order lands the molecule back on itself.
  playReveal(angleDeg, improper = false, durationMs = 1700) {
    return new Promise((resolve) => {
      this.reveal = {
        resolve,
        start: performance.now(),
        durationMs,
        angle: (angleDeg * Math.PI) / 180,
        improper,
      };
    }).then(() => {
      this.spin.matrix.identity();
      this.spin.matrixWorldNeedsUpdate = true;
      this.render();
    });
  }

  updateAnimation(now) {
    if (!this.reveal) return false;
    const { start, durationMs, angle, improper } = this.reveal;
    const t = Math.min((now - start) / durationMs, 1);
    const ease = (u) => (u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2);
    let matrix;
    if (!improper) {
      matrix = this.rotationMatrix(angle * ease(t));
    } else if (t < 0.5) {
      matrix = this.rotationMatrix(angle * ease(t / 0.5));
    } else {
      matrix = this.reflectionMatrix((t - 0.5) / 0.5).multiply(this.rotationMatrix(angle));
    }
    this.spin.matrix.copy(matrix);
    this.spin.matrixWorldNeedsUpdate = true;
    if (t >= 1) {
      const resolve = this.reveal.resolve;
      this.reveal = null;
      resolve();
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
