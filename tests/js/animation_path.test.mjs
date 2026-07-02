import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  applyBoundaryContext,
  evaluatePath,
  pathAppliesToDisplayInstance,
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
