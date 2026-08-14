# Documentation Index

Start here when checking project direction.

## Current Docs

- `CLAUDE_HANDOFF.md` — **start here when resuming work.** Ready-to-paste prompt, environment
  traps, and the list of known gaps.
- `PROJECT_SPEC.md` — current purpose, priorities, scope, architecture, and non-goals.
- `PUZZLE_SPEC.md` — the implemented puzzle spec. §10 records what was decided *against*.
- `REPORT_OUTLINE.md` — structure and content plan for the write-up, plus the remaining work.
- `VIEWER_GUIDE.md` — JSON schema, viewer usage, browser controls, animation rules, and validation commands.
- `REVIEW_NOTES.md` — chronological review log from Codex/Claude checks.
- `sessions/` — session reports kept as durable handoff history.

`PUZZLE_CONCEPT.md` is a brainstorming memo, not a spec. It still contains ideas that were
deliberately not built, so do not read an unimplemented section there as a to-do.

## Status (2026-08-15)

Feature work is finished. The quiz set is closed at four (axis order, operation identify,
composition, atom mapping) and what remains is verification and the write-up — see
`REPORT_OUTLINE.md`.

## External Review Entry Point

For a quick external review, read these in order:

1. `docs/README.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/VIEWER_GUIDE.md`
4. `docs/REVIEW_NOTES.md` only as needed for detailed history

Useful review prompt:

```text
This project is a staged rebuild of a crystal/molecular symmetry viewer.
The current goal is to stabilize analysis, shared renderer data, PyVista/browser viewing, and operation animation before building puzzle UI.
Please review whether the current implementation still follows docs/PROJECT_SPEC.md and docs/VIEWER_GUIDE.md, and call out bugs, stale docs, or design risks.
```

## Historical Archive

Older design memos, original implementation specs, and one-off review requests live in:

```text
docs/archive/
```

Use those files as background only. The active project direction is `PROJECT_SPEC.md`.
