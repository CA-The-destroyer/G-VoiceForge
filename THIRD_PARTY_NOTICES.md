# Third-party components

This repository contains application source and dependency declarations. Installed
libraries, model weights, and system tools retain their respective upstream terms.
No bundled third-party binaries or weights are covered by the project's reserved rights.

| Component | Upstream / licensing reference |
| --- | --- |
| Qwen3-TTS code and selected model weights | [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), Apache-2.0; check each selected model card |
| PyTorch and torchaudio | [PyTorch license](https://github.com/pytorch/pytorch/blob/main/LICENSE), BSD-style with additional notices; CUDA dependencies have separate terms |
| FastAPI | [FastAPI](https://github.com/fastapi/fastapi), MIT |
| SQLAlchemy | [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy), MIT |
| React | [React](https://github.com/facebook/react), MIT |
| Vite | [Vite](https://github.com/vitejs/vite), MIT |
| Lucide | [Lucide](https://github.com/lucide-icons/lucide), ISC |
| TypeScript and Playwright | [TypeScript](https://github.com/microsoft/TypeScript), [Playwright](https://github.com/microsoft/playwright), Apache-2.0 |
| NumPy and SciPy | [NumPy](https://github.com/numpy/numpy), [SciPy](https://github.com/scipy/scipy), BSD-3-Clause |
| SoundFile / libsndfile | [SoundFile](https://github.com/bastibe/python-soundfile), BSD-3-Clause wrapper; libsndfile LGPL terms |
| imageio-ffmpeg | [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg), BSD-2-Clause wrapper; included FFmpeg binaries have their own terms |
| FFmpeg | [FFmpeg licensing](https://ffmpeg.org/legal.html), LGPL/GPL depending on build configuration |

This is a component guide, not an exhaustive transitive dependency license bundle.
Inspect installed distribution metadata and bundled notices for the exact environment.
Redistributing installed packages or binaries can create additional obligations.
Unreal Engine is obtained separately under Epic's terms; no engine implementation
or game assets are bundled here.
