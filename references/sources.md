# Sources

Read before adding a library, model or service to a project, or before shipping this skill's
pipeline inside a product. Licences as of 2026-10; recheck before shipping. "Product" means code
other people install or pay for (Chockstone), where copyleft and per-seat licences matter.

## In use

| Tool | Does | Licence | Product notes |
|---|---|---|---|
| ffmpeg 8.1 | Probe, conform, cut, xfade, mix, encode | LGPL-2.1+; GPL with libx264 | Call the user's ffmpeg as a process; a bundled GPL build makes the bundle GPL |
| Remotion 4.0.5xx | Captions, titles, overlays, transitions | Remotion License | Free up to 3 people; Company License above (references/motion.md) |
| WhisperX | Word-aligned transcripts, VAD | BSD-2 | Model weights carry their own terms |
| silero-vad | Voice detection | MIT | |
| Apple Vision (`faces.swift`, `matte.swift`) | Face boxes, person matte, macOS | OS framework | Cross-platform: MediaPipe Face Detector, Image Segmenter (Apache-2.0) |
| Blender 5.2 LTS | 3D titles, product shots | GPL-3.0 | bpy scripts are GPL; renders belong to their maker; run as a separate process |

## Options by job

| Job | Tool | Licence |
|---|---|---|
| ASR, Apple Silicon | mlx-whisper; parakeet-mlx | MIT; Apache-2.0 code, check weights |
| ASR, Linux/CUDA | faster-whisper; whisper.cpp | MIT; MIT |
| ASR, cloud | Deepgram, AssemblyAI | Paid; the voice leaves the machine |
| Motion, agent-first | HyperFrames (heygen-com) | Apache-2.0, 0.x: pin |
| Motion, TS scenes | Revideo | MIT |
| Timelines | GSAP (`@remotion/gsap`) | GSAP Standard: free incl. commercial, bars no-code builders |
| Vector motion | Lottie (`@remotion/lottie`, dotlottie-web); Rive (`@remotion/rive`) | MIT runtimes |
| Explainers | Manim Community | MIT |
| Shader transitions | gl-transitions, `@gl-transitions/remotion`; xfade-easing | MIT (two shaders BSD); MIT |
| Beats | librosa; beat_this | ISC; MIT |
| Voice clean-up | Auphonic; Adobe Podcast Enhance; ElevenLabs Audio Isolation | Paid, cloud |
| Music | Epidemic Sound or another subscription library | Per-plan terms (references/audio.md) |
| 3D assets | Poly Haven; Blender Studio | CC0; mostly CC BY |
| Patterns to read | `remotion-dev/template-tiktok`, `template-overlay`, `remotion-dev/skills` | Remotion's; link, don't copy |

## Dropped

| Tool | Why |
|---|---|
| Motion Canvas | No release since 2024-12 |
| lightning-whisper-mlx, editly, ffmpeg-python | No release in over 18 months |
| whisper-timestamped | GPL |
| CrisperWhisper | Weights are non-commercial |
| InsightFace models | Non-commercial |
| DeepFilterNet, resemble-enhance | No release in over 18 months |
| pedalboard | GPL |
| RNNoise models for `arnndn` | The common model repo has no licence |
| captacity | Superseded by `captions.py` plus Remotion |
