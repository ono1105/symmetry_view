import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { evaluatePath } from "../../crystal_viewer/web/animation_path.js";

const fixtureUrl = new URL("../fixtures/animation_path_golden.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"));
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
