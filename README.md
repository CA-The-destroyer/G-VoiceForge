# G-VoiceForge

A local character voice studio with a React interface and a Python/FastAPI backend.
Create voice profiles, audition takes, pace narration scenes, organize sound
samples, and export approved dialogue for Unreal Engine.

## Design and ownership

Created and directed by **[@CA-The-destroyer](https://github.com/CA-The-destroyer)**,
who owns the original project and provides its product and design direction.
Implementation was developed with assistance from OpenAI Codex.
See [DESIGN.md](DESIGN.md) for the application architecture.

## Licensing

**Copyright (c) 2026 CA-The-destroyer. All rights reserved.**
This is source-available software, not an open-source license grant. Publication
does not grant general reuse rights. See [LICENSE](LICENSE),
[licensing details](docs/LICENSING.md), and
[third-party notices](THIRD_PARTY_NOTICES.md).

No recordings, character libraries, project scripts, generated performances,
databases, model weights, or game assets are included. The tests use synthetic
signals and demonstration text. Generic voice archetypes are built-in app presets.

## Windows setup

Prerequisites: Python 3.11 with the Windows `py` launcher, Node.js 22 with npm,
and Git. An NVIDIA GPU is recommended; CPU generation is supported but slower.
Installation requires internet access and enough disk space for PyTorch and models.

```powershell
git clone https://github.com/CA-The-destroyer/G-VoiceForge.git
cd G-VoiceForge
.\Install.ps1
```

The installer creates `.venv`, installs the CUDA-enabled PyTorch build, downloads
the default Qwen models, builds the frontend, and opens http://127.0.0.1:8765/.
If PowerShell blocks scripts, use an execution policy appropriate for your system.

To build without downloading weights or starting the application:

```powershell
.\Install.ps1 -SkipModels -NoLaunch
```

Launch with `Launch.ps1` or `Launch.cmd`; stop with `Stop.ps1`.
`Manage.ps1` provides local maintenance and model download options.
Models, recordings, exports, and the SQLite database stay in ignored local folders.
The studio binds to localhost; do not expose this unauthenticated local tool publicly.

## Workflow

1. Create a character with an original voice description or a rights-cleared reference.
2. Download the desired engine before selecting it. The 0.6B Base and CustomVoice
   models are the default downloads; 1.7B VoiceDesign and CustomVoice are optional.
3. Generate and compare takes, then approve a performance or save it as a voice reference.
4. Import CSV/JSON dialogue or paced scene JSON. Scene speech speed and explicit
   pauses are applied; scene acting and ambience notes are metadata, not an automatic mix.
5. Remaster from preserved source audio and export approved lines with subtitles.

Base cloning uses the saved reference identity and performance; it does not accept
actor instructions. The larger engines support delivery direction. VoiceDesign
creates identities; save an approved reference when continuity matters.
Generation runs one job at a time, with conservative GPU admission and CPU fallback.
Very long speech can still require shorter lines. Listen to every approved take.

The Sound Library imports samples with provenance and approval metadata. Unreal
exports include manifests and an Editor Python importer. The C++ lookup example
requires integration into your game's module and cooked asset configuration;
it does not automatically wire game events.

## Development and checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm ci
npm run build
cd ..
```

Tests mock synthesis and use synthetic audio; they do not require downloaded weights.
They do not measure real model voice quality or GPU performance.
`requirements-windows.lock.txt` records one Windows dependency environment;
`requirements.txt` is the installer's dependency specification.
Docker users can build `compose.yaml` with a compatible NVIDIA container runtime.

## Source packaging

After reviewing and committing source files, run:

```powershell
.\.venv\Scripts\python.exe scripts/package_source.py
```

The packager includes only Git-tracked files, rejects runtime/media paths, and
writes an ignored source ZIP under `releases`. Always review changes before
committing or publishing; the ignore file alone is not a content review.
