# Design

Project creator, product direction, and original application design:
**[@CA-The-destroyer](https://github.com/CA-The-destroyer)**.
Copyright (c) 2026 CA-The-destroyer. All rights reserved for original project work.

The studio keeps voice production local. A React/TypeScript frontend talks to a
FastAPI API. SQLite stores character profiles, reference versions, jobs, approvals,
and sound metadata. Audio and model files live outside the source tree's tracked files.

A serial worker snapshots job settings and voice references, uses the selected
Qwen engine, and retains synthesis sources separately from processed masters.
Model capabilities determine which reference and delivery controls are meaningful.
GPU admission leaves a configurable reserve and can fall back to CPU.

Scene planning splits narration into manageable units and assembles speech with
explicit segment pauses and tempo changes. FFmpeg performs processing and exports.
Long clauses and synthesis artifacts still need human review and replacement takes.

Approved dialogue exports carry stable character/dialogue identifiers, subtitles,
and import metadata. The reusable Unreal examples handle import and lookup;
project-specific event routing belongs to the consuming game.

No project-specific cast, narrative, identity recordings, game assets, or production
performances form part of this source publication.
