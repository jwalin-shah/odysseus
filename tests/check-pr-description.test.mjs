import assert from 'node:assert/strict';
import test from 'node:test';
import checkPrDescription from '../.github/scripts/check-pr-description.js';

const { strip } = checkPrDescription;

test('strip() returns "" for null without throwing', () => {
  assert.equal(strip(null), '');
});

test('strip() returns "" for undefined without throwing', () => {
  assert.equal(strip(undefined), '');
});

test('strip() still removes HTML comments and trims whitespace', () => {
  assert.equal(strip('<!-- comment --> actual text'), 'actual text');
});
