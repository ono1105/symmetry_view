const EPSILON = 1e-12;

function add(a, b) {
  return a.map((value, index) => value + b[index]);
}

function subtract(a, b) {
  return a.map((value, index) => value - b[index]);
}

function scale(vector, factor) {
  return vector.map(value => value * factor);
}

function dot(a, b) {
  return a.reduce((sum, value, index) => sum + value * b[index], 0);
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function normalize(vector) {
  const norm = Math.sqrt(dot(vector, vector));
  return norm < EPSILON ? [...vector] : scale(vector, 1 / norm);
}

function interpolate(start, target, s) {
  return start.map((value, index) => (1 - s) * value + s * target[index]);
}

function rotateAboutAxis(point, axisPoint, axisDirection, angleRad) {
  const direction = normalize(axisDirection);
  const relative = subtract(point, axisPoint);
  const cosAngle = Math.cos(angleRad);
  const sinAngle = Math.sin(angleRad);
  const rotated = add(
    add(scale(relative, cosAngle), scale(cross(direction, relative), sinAngle)),
    scale(direction, dot(direction, relative) * (1 - cosAngle)),
  );
  return add(axisPoint, rotated);
}

function reflectPoint(point, planePoint, planeNormal) {
  const normal = normalize(planeNormal);
  return subtract(point, scale(normal, 2 * dot(subtract(point, planePoint), normal)));
}

function multiplyMatrixVector(matrix, vector) {
  return matrix.map(row => dot(row, vector));
}

function angleRadians(path) {
  if (!Number.isFinite(path.angle_deg)) {
    throw new Error(`Path type ${path.type} requires angle_deg`);
  }
  return path.angle_deg * Math.PI / 180;
}

export function evaluatePath(path, progress, startOverride = null) {
  const s = Math.min(1, Math.max(0, Number(progress)));
  const pathType = path.type;

  if (pathType === "sequential") {
    const segments = path.segments;
    if (!segments.length) {
      throw new Error("Sequential path requires at least one segment");
    }
    const index = Math.min(Math.floor(s * segments.length), segments.length - 1);
    const localS = (s - index / segments.length) * segments.length;
    let segmentStart = startOverride;
    for (const segment of segments.slice(0, index)) {
      segmentStart = evaluatePath(segment, 1, segmentStart);
    }
    return evaluatePath(segments[index], localS, segmentStart);
  }

  const start = startOverride === null ? [...path.start] : [...startOverride];
  if (pathType === "affine_linear") {
    const target = startOverride === null
      ? path.target
      : add(multiplyMatrixVector(path.matrix_cart, start), path.translation_cart);
    return interpolate(start, target, s);
  }
  if (pathType === "rotation") {
    return rotateAboutAxis(start, path.axis_point, path.axis_direction, angleRadians(path) * s);
  }
  if (pathType === "screw") {
    if (s <= 0.5) {
      return rotateAboutAxis(start, path.axis_point, path.axis_direction, angleRadians(path) * 2 * s);
    }
    const rotatedEnd = rotateAboutAxis(start, path.axis_point, path.axis_direction, angleRadians(path));
    return add(rotatedEnd, scale(path.translation, 2 * s - 1));
  }
  if (pathType === "mirror" || pathType === "mirror_after_hold") {
    if (pathType === "mirror_after_hold") {
      const holdFraction = Number(path.hold_fraction ?? 0.3);
      if (s <= holdFraction) {
        return [...start];
      }
      const localS = (s - holdFraction) / Math.max(1 - holdFraction, 1e-9);
      return interpolate(start, reflectPoint(start, path.plane_point, path.plane_normal), localS);
    }
    return interpolate(start, reflectPoint(start, path.plane_point, path.plane_normal), s);
  }
  if (pathType === "glide") {
    const mirrored = reflectPoint(start, path.plane_point, path.plane_normal);
    return s <= 0.5
      ? interpolate(start, mirrored, 2 * s)
      : add(mirrored, scale(path.translation, 2 * s - 1));
  }
  if (pathType === "inversion") {
    return interpolate(start, subtract(scale(path.center, 2), start), s);
  }
  if (pathType === "rotoinversion" || pathType === "rotoreflection") {
    if (s <= 0.5) {
      return rotateAboutAxis(start, path.axis_point, path.axis_direction, angleRadians(path) * 2 * s);
    }
    const rotatedEnd = rotateAboutAxis(start, path.axis_point, path.axis_direction, angleRadians(path));
    const transformed = pathType === "rotoinversion"
      ? subtract(scale(path.center, 2), rotatedEnd)
      : reflectPoint(rotatedEnd, path.plane_point, path.plane_normal);
    return interpolate(rotatedEnd, transformed, 2 * s - 1);
  }

  let target = [...path.target];
  if (startOverride !== null) {
    target = add(target, subtract(start, path.start));
  }
  return interpolate(start, target, s);
}
