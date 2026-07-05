import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  applyBoundaryContext,
  evaluatePath,
  pathBreakpoints,
  pathAppliesToDisplayInstance,
  sequentialSegmentIndex,
} from "../../crystal_viewer/web/animation_path.js";

const fixtureUrl = new URL("../fixtures/animation_path_golden.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"));
const boundaryFixtureUrl = new URL("../fixtures/boundary_wrap_golden.json", import.meta.url);
const boundaryFixture = JSON.parse(await readFile(boundaryFixtureUrl, "utf8"));
const tolerance = 1e-6;

function assertVectorClose(actual, expected, message) {
  assert.equal(actual.length, expected.length, message);
  actual.forEach((value, index) => {
    assert.ok(
      Math.abs(value - expected[index]) <= tolerance,
      `${message}: component ${index}, expected ${expected[index]}, got ${value}`,
    );
  });
}

test("evaluatePath matches Python golden samples", () => {
  assert.equal(fixture.schema_version, 1);
  assert.equal(fixture.coordinate_space, "cartesian");
  for (const testCase of fixture.cases) {
    for (const sample of testCase.samples) {
      assertVectorClose(
        evaluatePath(testCase.path, sample.s),
        sample.position,
        `${testCase.name} at s=${sample.s}`,
      );
    }
  }
});

test("compound path breakpoint follows phase travel distance", () => {
  const screw = fixture.cases.find(item => item.name === "screw_rotation_then_translation").path;
  const expected = (Math.PI / 2) / (Math.PI / 2 + 2);
  const breakpoints = pathBreakpoints(screw);
  assert.ok(Math.abs(breakpoints[1] - expected) <= tolerance);
  assertVectorClose(evaluatePath(screw, breakpoints[1]), [0, 1, 0], "screw phase boundary");
});

test("explicit compound phase boundary controls evaluation and UI breakpoint", () => {
  const source = fixture.cases.find(item => item.name === "screw_rotation_then_translation").path;
  const screw = {...source, phase_fraction: 0.75};
  const breakpoints = pathBreakpoints(screw);
  assert.ok(Math.abs(breakpoints[1] - 0.75) <= tolerance);
  assertVectorClose(evaluatePath(screw, 0.75), [0, 1, 0], "shared screw phase boundary");
});

test("compound path keeps Python parity for a periodic start override", () => {
  const screw = fixture.cases.find(item => item.name === "screw_rotation_then_translation").path;
  assertVectorClose(
    evaluatePath(screw, 0.5, [2, 0, 0]),
    [0.5630790622854015, 1.9190992599695809, 0],
    "screw periodic image at s=0.5",
  );
});

test("sequential breakpoints retain nested compound phase boundaries", () => {
  const screw = fixture.cases.find(item => item.name === "screw_rotation_then_translation").path;
  const linear = {
    type: "linear",
    start: [0, 1, 2],
    target: [0, 1, 3],
  };
  const screwLength = Math.PI / 2 + 2;
  const totalLength = screwLength + 1;
  const breakpoints = pathBreakpoints({type: "sequential", segments: [screw, linear]});
  assert.ok(breakpoints.some(value => Math.abs(value - (Math.PI / 2) / totalLength) <= tolerance));
  assert.ok(breakpoints.some(value => Math.abs(value - screwLength / totalLength) <= tolerance));
});

test("sequential segment index follows length-weighted timing", () => {
  const path = {
    type: "sequential",
    segments: [
      {type: "linear", start: [0, 0, 0], target: [1, 0, 0]},
      {type: "linear", start: [1, 0, 0], target: [1, 3, 0]},
    ],
  };
  assert.equal(sequentialSegmentIndex(path, 0.2), 0);
  assert.equal(sequentialSegmentIndex(path, 0.3), 1);
});

test("sequential paths honor shared server segment weights", () => {
  const path = {
    type: "sequential",
    segment_weights: [0.75, 0.25],
    segments: [
      {type: "linear", start: [0, 0, 0], target: [0, 0, 0]},
      {type: "linear", start: [0, 0, 0], target: [0, 0, 1]},
    ],
  };
  assert.equal(sequentialSegmentIndex(path, 0.7), 0);
  assert.equal(sequentialSegmentIndex(path, 0.8), 1);
  assertVectorClose(evaluatePath(path, 0.75), [0, 0, 0], "shared segment boundary");
  assert.ok(pathBreakpoints(path).some(value => Math.abs(value - 0.75) <= tolerance));
});

test("applyBoundaryContext matches Python wrap samples", () => {
  assert.equal(boundaryFixture.schema_version, 1);
  assert.equal(boundaryFixture.coordinate_space, "cartesian");
  for (const testCase of boundaryFixture.cases) {
    for (const sample of testCase.samples) {
      assertVectorClose(
        applyBoundaryContext(sample.position, testCase.context),
        sample.wrapped,
        `${testCase.name} at ${JSON.stringify(sample.position)}`,
      );
    }
  }
});

test("continuous boundary mode leaves Cartesian positions unchanged", () => {
  assert.deepEqual(applyBoundaryContext([2.1, -0.6, 1.5], {mode: "continuous"}), [2.1, -0.6, 1.5]);
});

test("displayed scope moves periodic copies and unit-cell scope leaves them fixed", () => {
  const primary = {isPrimaryImage: true};
  const periodicCopy = {isPrimaryImage: false};
  assert.equal(pathAppliesToDisplayInstance({type: "rotation"}, primary), true);
  assert.equal(pathAppliesToDisplayInstance({type: "rotation"}, periodicCopy), true);
  assert.equal(pathAppliesToDisplayInstance({type: "rotation", unit_cell_only: true}, primary), true);
  assert.equal(pathAppliesToDisplayInstance({type: "rotation", unit_cell_only: true}, periodicCopy), false);
});
