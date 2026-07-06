---
title: Installation — RCJA Maze Rescue Sim
---

# Installation

[← Back to the main guide](../)

This competition runs on a **fork** of Erebus (see [the main guide's setup section](../#2-setup-instructions) for why), not the official release. The official installation guide at [v25.erebus.rcj.cloud/docs/installation](https://v25.erebus.rcj.cloud/docs/installation/) tells you to download the official release zip — **don't do that for this competition**, or your world files, robot, and Entry Level maps won't match what your simulator expects. This page mirrors that guide's structure but swaps in the right source everywhere it matters.

## What you need

- **Webots Robot Simulator**, version **2023.b** — the underlying 3D physics simulator.
- **This competition's Erebus fork** — [`wilsoncheng-sgcs/erebus`](https://github.com/wilsoncheng-sgcs/erebus), branch [`entry-level-floor-victims`](https://github.com/wilsoncheng-sgcs/erebus/tree/entry-level-floor-victims). This bundles the Competition Supervisor (rules/scoring engine) plus the Entry Level tier's `FloorVictim` support — it is a drop-in replacement for the official release, cloned from source instead of downloaded as a zip.
- **Python 3.9.x or 3.10.x** (64-bit) — for writing your own robot controller. C/C++ is also supported by Webots if you'd rather use that.

## Minimum system requirements

| | Requirement |
|---|---|
| OS | Ubuntu 20.04/22.04 LTS, Windows 10/11 (64-bit), or macOS 11-12 |
| CPU | Dual Core, 2 GHz minimum |
| RAM | 2 GB minimum |
| GPU | Nvidia or AMD, OpenGL, 512 MB minimum |

These are unchanged from the official platform — hardware needs come from Webots itself, not from which Erebus fork you run.

## Pick your platform

- [Windows](windows/)
- [macOS](mac/)
- [Linux (Ubuntu 20.04/22.04 LTS)](linux/)

Each guide covers: installing Python, installing Webots, cloning this competition's Erebus fork, running the simulator for the first time, and the most common first-run problems.
