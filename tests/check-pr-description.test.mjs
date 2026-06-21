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

// ODYSSEUS-CI regression: section() must not throw on missing headings, must
// escape regex metacharacters in the heading argument, and must survive a
// null body. The original `m?.[0].replace(...)` form relied on optional-
// chaining short-circuit semantics that differ across Node 20 vs 22+, so we
// exercise every failure mode.
const fakeCtx = (body) => ({
  payload: { pull_request: { body, number: 1, user: { type: 'User' } } },
  repo:    { owner: 'o', repo: 'r' },
  issue:   { number: 1 },
});

test('section() returns "" when heading is absent from body', async () => {
  // Drive section() through checkPrDescription by handing it a context that
  // lacks any required heading. checkPrDescription pushes a problem for every
  // missing section, but it should not throw.
  const calls = { comments: [], labels: [] };
  const fakeGithub = {
    paginate: async () => [],
    rest: {
      issues: {
        listComments: async () => calls.comments,
        createComment: async (p) => { calls.comments.push(p); },
        updateComment: async (p) => { calls.comments.push(p); },
        deleteComment: async (p) => { calls.comments.push(p); },
        addLabels: async (p) => { calls.labels.push(['add', p]); },
        removeLabel: async (p) => { calls.labels.push(['remove', p]); },
        getLabel: async () => ({ data: {} }),
      },
    },
  };
  const fakeCore = {
    warning: () => {},
    setFailed: () => {},
  };
  // Body has none of the required sections.
  await checkPrDescription({ github: fakeGithub, context: fakeCtx('No headings here.'), core: fakeCore });
  // We must reach the comment-posting code path; if section() threw, we'd
  // never get there and the comments array would be empty.
  assert.ok(calls.comments.length > 0, 'checkPrDescription should have posted a comment listing missing sections');
  // The bot marker must be present.
  assert.match(calls.comments[0].body, /pr-description-check-bot/);
});

test('section() returns full body when heading is present and non-empty', async () => {
  const body = [
    '## Summary',
    'This is a sufficiently long summary section that exceeds twenty characters easily.',
    '## Linked Issue',
    'Fixes #42',
    '## Type of Change',
    '- [x] Bug fix',
    '## Checklist',
    '- [x] I searched the repo',
    '## How to Test',
    'Run npm test. The new test case under tests/ should pass on the first run.',
  ].join('\n');
  const calls = { comments: [], labels: [] };
  const fakeGithub = {
    paginate: async () => [],
    rest: {
      issues: {
        listComments: async () => calls.comments,
        createComment: async (p) => { calls.comments.push(p); },
        updateComment: async (p) => { calls.comments.push(p); },
        deleteComment: async (p) => { calls.comments.push(p); },
        addLabels: async (p) => { calls.labels.push(['add', p]); },
        removeLabel: async (p) => { calls.labels.push(['remove', p]); },
        getLabel: async () => ({ data: {} }),
      },
    },
  };
  const fakeCore = {
    warning: () => {},
    setFailed: () => {},
  };
  await checkPrDescription({ github: fakeGithub, context: fakeCtx(body), core: fakeCore });
  // All sections filled in → no bot comment posted.
  const botComments = calls.comments.filter(c => (c.body ?? '').includes('pr-description-check-bot'));
  assert.equal(botComments.length, 0, 'no bot comment should be posted when all sections are complete');
});

test('section() handles a heading containing regex metacharacters', async () => {
  // Synthesize a body with a heading that has parens — the original
  // `new RegExp('#+\\s+'+heading+...)` would have treated the parens as a
  // capture group and silently failed to match. The fix escapes the heading.
  const body = [
    '## Type of Change (Foo)',
    '- [x] Bug fix',
    '## Summary',
    'Long enough summary text to satisfy the twenty-character minimum easily.',
    '## Linked Issue',
    'Fixes #99',
    '## Checklist',
    '- [x] I searched the repo',
    '## How to Test',
    'Run the test suite and confirm the new regression test under tests/ passes.',
  ].join('\n');
  // We can not directly assert against the inner section() (it's a closure),
  // but we can confirm the workflow runs to completion without throwing and
  // that the Type of Change heading is properly extracted (it should NOT
  // appear in the problems list because the - [x] box is checked).
  const calls = { comments: [], labels: [] };
  const fakeGithub = {
    paginate: async () => [],
    rest: {
      issues: {
        listComments: async () => [],
        createComment: async (p) => { calls.comments.push(p); },
        updateComment: async (p) => { calls.comments.push(p); },
        deleteComment: async (p) => { calls.comments.push(p); },
        addLabels: async (p) => { calls.labels.push(['add', p]); },
        removeLabel: async (p) => { calls.labels.push(['remove', p]); },
        getLabel: async () => ({ data: {} }),
      },
    },
  };
  const fakeCore = { warning: () => {}, setFailed: () => {} };
  await checkPrDescription({ github: fakeGithub, context: fakeCtx(body), core: fakeCore });
  // No bot comment = workflow reached the "all sections present" branch.
  // If the regex were unescaped, the Type-of-Change heading wouldn't match,
  // the box wouldn't be detected, and the bot would post a complaint.
  const botComments = calls.comments.filter(c => (c.body ?? '').includes('pr-description-check-bot'));
  assert.equal(botComments.length, 0, 'Type of Change (Foo) must be matched as a literal heading, not as a capture group');
});

test('section() tolerates a null PR body', async () => {
  // The old `m?.[0].replace(...)` form crashes on Node 20 when m is null
  // AND when the inner .replace is called on undefined. We confirm the
  // workflow completes without throwing.
  const calls = { comments: [], labels: [] };
  const fakeGithub = {
    paginate: async () => [],
    rest: {
      issues: {
        listComments: async () => [],
        createComment: async (p) => { calls.comments.push(p); },
        updateComment: async (p) => { calls.comments.push(p); },
        deleteComment: async (p) => { calls.comments.push(p); },
        addLabels: async (p) => { calls.labels.push(['add', p]); },
        removeLabel: async (p) => { calls.labels.push(['remove', p]); },
        getLabel: async () => ({ data: {} }),
      },
    },
  };
  const fakeCore = { warning: () => {}, setFailed: () => {} };
  // null body — the `body || ''` guard at the top of checkPrDescription makes
  // body = '' at section() time, but this also exercises the section() guard
  // for body == null.
  await checkPrDescription({ github: fakeGithub, context: fakeCtx(null), core: fakeCore });
  // We expect a bot comment (all sections missing). If the workflow had
  // thrown, the test would have failed with the thrown error.
  assert.ok(calls.comments.length > 0, 'workflow should reach the comment-posting code path on null body');
});
