---
title: RCJA Maze Rescue Sim — Documentation
---

# RCJA Maze Rescue Sim

**This guide is for people who are new to RCJA Rescue Simulation** - adapted from RCJ Rescue Simulation - and want to get from "never opened Webots before" to "have a custom robot driving around a maze." It walks through installing the platform, understanding how the pieces fit together, and testing a robot — using this repo's `winglander_v1` robot as the running example.

**Contents**

1. [What is RCJA Maze Rescue Sim](#1-what-is-rcja-maze-rescue-sim)
2. [Setup Instructions](#2-setup-instructions)
3. [Components That Work Together](#3-components-that-work-together)
4. [Quick Start — WASD Test Controller](#4-quick-start--wasd-test-controller)
5. [Scoring System](#5-scoring-system)
6. [Server/Client Connected Method (extern controller + scoring UI)](#6-serverclient-connected-method-extern-controller--scoring-ui)
7. [Note on ROS / ROS2](#7-note-on-ros--ros2)
8. [Links](#8-links)

---

## 1. What is RCJA Maze Rescue Sim

**RCJA Maze Rescue Sim** is this project's name for RCJA's local adaptation of **Erebus**, the official simulation sub-league of [RoboCupJunior Rescue](https://junior.robocup.org/) (first introduced in 2021, now a core part of RCJ Rescue internationally). The underlying platform, rules, and general gameplay are all inherited from official Erebus — teams write autonomous Python (or C/C++/Java) controllers that pilot a customizable robot through a procedurally-assembled maze, mapping it while locating and correctly classifying **victims** (injured people) and **cognitive targets** (hazmat-style signs), all without any human input during a run. What's RCJA-specific is an additional **Entry Level** difficulty tier and matching tooling, covered throughout this guide.

Under the hood, Erebus is a rules/scoring layer (a Webots "Supervisor" controller) that runs on top of **Webots**, Cyberbotics' physics-accurate robot simulator. This repo uses the customised robot (`winglander_v1.json`) and adds development-only tooling (`winglander_v1.py`) and (`winglander_v1_external.py`) for driving and inspecting it outside of a real competition run as proof of concept.

---

## 2. Setup Instructions

**This competition runs on a fork of Erebus, not the official release** — see below for why — so follow **[our own installation guide](installation/)** rather than the official one. It mirrors the official guide's structure (same Python/Webots versions, same Windows/macOS/Linux split) but swaps in the right source to download/clone at every step that matters, so you don't end up with a working Webots setup pointed at the wrong simulator:

- [Installation overview](installation/)
- [Windows](installation/windows/)
- [macOS](installation/mac/)
- [Linux (Ubuntu)](installation/linux/)

Once you've followed that guide and the Competition Supervisor is visible, come back here for the parts specific to customizing and testing your own robot.

### Why a fork, and the matching map editor

This document supports a local RCJA-run tier (name TBD) that sits *below* the standard difficulty, aimed at genuinely first-time teams. It works by swapping wall-mounted victim signs for simple floor-mounted colour markers, which removes the orientation/facing check beginners tend to find hardest. That change lives in [`wilsoncheng-sgcs/erebus`](https://github.com/wilsoncheng-sgcs/erebus) (branch [`entry-level-floor-victims`](https://github.com/wilsoncheng-sgcs/erebus/tree/entry-level-floor-victims)) — which the installation guide above already has you clone — plus a matching map editor: [erebus-map-editor-RCJA](https://wilsoncheng-sgcs.github.io/erebus-map-editor-RCJA/) ([repo](https://github.com/wilsoncheng-sgcs/erebus-map-editor-RCJA)), a standalone fork of the official map editor with a **Ruleset tier** selector. **Original** and **Intermediate** export identically to the official tool (safe to use for other tiers too), while **Entry Level** emits the floor-marker maps this fork's engine expects. It's a plain static site — nothing to install, just open the link.

Colour legend for Entry Level floor markers: **red = harmed**, **green = unharmed**, **yellow = stable** — the same H/U/S categories used everywhere else in Erebus, just represented as a floor colour instead of a wall sign (see [Section 5](#5-scoring-system)). If you want the full technical rationale (why floor markers instead of wall signs, how detection was adapted), it's written up in [`docs/entry-level-plan.md`](https://github.com/wilsoncheng-sgcs/erebus/blob/entry-level-floor-victims/docs/entry-level-plan.md) on the simulator fork.

### Customizing and testing your robot

1. **Build your robot** — use the RCJ Official [Robot Customizer](https://v25.robot.erebus.rcj.cloud/) web tool to design a robot (wheels, sensors, camera, etc.) and export it as a JSON file — that's what `winglander_v1.json` in this repo is. This tool is unaffected by the RCJA local customisation; use it as-is.
2. **Generate/import a maze** — use the [erebus-map-editor-RCJA](https://wilsoncheng-sgcs.github.io/erebus-map-editor-RCJA/) app above (pick your ruleset tier), or one of the bundled `game/worlds/*.wbt` files from whichever Erebus source you're running. For your convenience, there is a (`RCJA-Entry test.wbt`) world file for the Entry Level competition map.
3. **Load your robot into the simulation** — Erebus reads your robot's JSON through the Competition Supervisor's "load custom robot" option and generates the matching Webots PROTO/device tree for it automatically (see [Section 3](#3-components-that-work-together)).

---

## 3. Components That Work Together

Four distinct pieces combine to make a working simulated robot:

| Component | Role |
|---|---|
| **Webots** | The underlying 3D physics simulator. Runs the world, the robot's rigid bodies/sensors/motors, and executes controller processes (your Python code). Erebus does not replace Webots — it runs *inside* it. Erebus ties to Webots R2023b verion.|
| **Erebus** | The competition layer. Ships as a Webots project: a `MainSupervisor` controller that spawns the maze, tracks the game clock, scores victim/target identifications, enforces lack-of-progress relocations, and exposes a `robot0Controller`/`robot1Controller` slot for your code. Also ships example worlds and an example player controller. |
| **Robot Customizer** ([v25.robot.erebus.rcj.cloud](https://v25.robot.erebus.rcj.cloud/)) | A web app for visually placing wheels, distance sensors, a camera, a colour sensor, GPS, etc. on a robot chassis within a fixed points budget. Exports a JSON file (e.g. `winglander_v1.json`) describing every component's type, position, rotation, and custom name. Erebus's `ProtoGenerator.py` reads this JSON at runtime and generates the actual Webots PROTO node for your robot — including the exact device names your controller must use (e.g. a wheel named `wheel1` in the JSON becomes a Webots motor device named `"wheel1 motor"`). |
| **Map Editor** ([erebus-map-editor-RCJA](https://wilsoncheng-sgcs.github.io/erebus-map-editor-RCJA/), used by this doc) | A web app for laying out maze tiles, walls, victims, and cognitive targets, exporting a Webots world file Erebus can load. This is a standalone fork of the official [rcj-rescue-cms](https://github.com/robocup-junior/rcj-rescue-cms) map editor (MIT-licensed, attribution preserved), with an added **Ruleset tier** selector so it can also export the Entry Level floor-marker maps the `entry-level-floor-victims` Erebus fork expects. |

The practical implication: **your JSON robot config is not itself a Webots file** — Erebus regenerates the robot's PROTO from it every time the world (re)loads, so device names follow Erebus's naming convention, not whatever you called things in the customizer verbatim (see the wheel-naming example above).

---

## 4. Quick Start — WASD Test Controller

The fastest way to confirm your robot config is wired up correctly (correct device names, sensors reading sane values, camera producing frames) is to drive it manually with the keyboard before writing any autonomous logic.

> [!WARNING]
> **This WASD controller is a platform-testing tool only.** Manual/keyboard-driven control is **not permitted in RCJ Rescue Simulation competition** — competition robots must operate fully autonomously, with no operator input during a run. Do not submit this file, or any code based on directly reading human keyboard input during a match, as your competition controller. Always check the current [official rules](#8-links) for exactly what's permitted.

**Dependencies: none to install.** `from controller import Robot` is Webots' own bundled Python API — it's only importable because Webots launches this script itself and injects it onto the path; you don't `pip install` anything for this one.

**Keyboard focus: click the Webots 3D view.** This controller reads keys through Webots' own `Keyboard` device, which only receives input while the **Webots 3D view window itself** has focus — not your terminal, not an editor, not this webpage. If WASD does nothing, click directly into the simulation view first.

Save the following as `controllers/winglander_v1/winglander_v1.py` inside your Erebus install (so the folder name matches the Python filename, per Webots convention), set the robot's `controller` field to `winglander_v1`, then run the simulation and click into the 3D view before pressing keys:

```python
from controller import Robot

TIME_STEP = 32
MAX_SPEED = 6.28  # rad/s

robot = Robot()

# Erebus generates wheel motor device names as "<customName> motor"
wheel1 = robot.getDevice("wheel1 motor")
wheel2 = robot.getDevice("wheel2 motor")
for wheel in (wheel1, wheel2):
    wheel.setPosition(float("inf"))  # velocity control mode
    wheel.setVelocity(0.0)

keyboard = robot.getKeyboard()
keyboard.enable(TIME_STEP)

while robot.step(TIME_STEP) != -1:
    left_speed = right_speed = 0.0
    pressed = set()
    key = keyboard.getKey()
    while key != -1:
        pressed.add(key)
        key = keyboard.getKey()

    if ord("W") in pressed:
        left_speed += MAX_SPEED; right_speed += MAX_SPEED
    if ord("S") in pressed:
        left_speed -= MAX_SPEED; right_speed -= MAX_SPEED
    if ord("A") in pressed:
        left_speed -= MAX_SPEED; right_speed += MAX_SPEED
    if ord("D") in pressed:
        left_speed += MAX_SPEED; right_speed -= MAX_SPEED

    left_speed = max(-MAX_SPEED, min(MAX_SPEED, left_speed))
    right_speed = max(-MAX_SPEED, min(MAX_SPEED, right_speed))
    wheel2.setVelocity(left_speed)
    wheel1.setVelocity(right_speed)
```

Full file: [`controllers/winglander_v1/winglander_v1.py`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1.py).

---

## 5. Scoring System

Erebus's scoring engine (`MainSupervisor.py`) awards and deducts points for things like:

- **Victim identification** — correctly reporting a nearby victim's position and type (`H` harmed, `S` stable, `U` unharmed) via the emitter/receiver protocol (see [Section 6](#6-serverclient-connected-method-extern-controller--scoring-ui)). Correct type adds a bonus on top of a base identification score; a wrong-but-nearby report is still scored lower, and a report with nothing nearby is a **misidentification penalty**.
- **Cognitive target identification** — same mechanism, but for hazmat-style signs (`F` flammable gas, `P` poison, `C` corrosive, `O` organic peroxide), generally worth more points than victims. Cognitive targets are only present in the original RCJ International level comp.
- **Mapping score** — submitting a reconstructed map of the maze at the end of a run, scored against the ground-truth layout.
- **Exit bonus** — returning to the start tile before time runs out adds a percentage bonus to the final score, but only if at least one victim was identified.
- **Lack-of-progress penalty** — the robot is automatically relocated to its last checkpoint if stationary for too long (20s) or if it falls into a black-hole tile, resetting forward progress on that section.
- **Room/tile multipliers** — some rooms multiply the points scored for victims/targets found inside them. Only present in the original RCJ International level comp.

If you're running the Entry Level tier ([Section 2](#2-setup-instructions)), floor-marker victims reuse this exact same `H`/`U`/`S` scoring path unchanged — only how the marker is presented to the robot (a floor colour instead of a wall sign) differs, not how it's scored.

These mechanics and their exact point values **change between rule seasons** and are governed by the official rulebook — this doc intentionally does not hardcode point totals. Always check the version-matched official rules PDF (a 2026 copy is bundled in this repo as [`RCJRescueSimulation2026-final.pdf`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/RCJRescueSimulation2026-final.pdf)) for authoritative scoring details, and cross-reference against whatever Erebus release you're actually running, since scoring logic lives in that release's `MainSupervisor.py`/`Victim.py`.

---

## 6. Server/Client Connected Method (extern controller + scoring UI)

Beyond simple WASD driving, Erebus's robot talks to the game engine (`MainSupervisor`, acting as the "server") over a pair of built-in `emitter`/`receiver` devices — this is the same channel your real autonomous controller uses to submit victim/target reports and query game state. You can run your controller as a **standalone ("extern") process**, connected to a live Webots simulation over TCP, instead of having Webots launch it for you — useful for iterating without restarting the sim each time.

This repo's [`controllers/winglander_v1/winglander_v1_external.py`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1_external.py) demonstrates the full loop in a single pygame window:

- WASD driving (again, **testing only** — see the warning in [Section 4](#4-quick-start--wasd-test-controller))
- Live camera feed and colour sensor RGB readout
- Distance sensor readings
- **Game info** — periodically sends a single `'G'` byte via the emitter, and unpacks the reply `(score, game_time_left, real_time_left)` from the receiver
- **Lack-of-progress** — passively watches for an unprompted single `'L'` byte the server sends whenever it relocates the robot
- **Victim/target reporting UI** — X/Z coordinate fields (with a "Pull from GPS" shortcut) and a dropdown of the 7 valid type codes (H/S/U/F/P/C/O), packed as `struct.pack("i i c", x_cm, z_cm, type_char)` and sent via the emitter on a button click

**Dependency: `pip install pygame`** — the only third-party package this script needs (everything else it imports is either Python stdlib or Webots' own `controller` API, located manually via a `sys.path`/`WEBOTS_HOME` lookup since Webots isn't the one launching this script).

**Keyboard focus: click the pygame window, not Webots.** Unlike Section 4's controller, this script builds its own window and reads keys through pygame's own event loop — Webots' 3D view has nothing to do with input here. Clicking into the Webots view will do nothing; click into the pygame window that pops up when you run the script.

Setup summary (see the full docstring in the file for details):

1. `pip install pygame`, if you haven't already.
2. In `game/controllers/MainSupervisor/config.txt`, set the 5th field ("Keep remote") to `1` so Erebus marks the robot's controller as `<extern>` instead of launching it itself.
3. Restart Webots so the config change takes effect, and load your world.
4. Run `python3 winglander_v1_external.py` from a terminal — it connects to the running simulation over `WEBOTS_CONTROLLER_URL` (defaults to `tcp://127.0.0.1:1234/Erebus_Bot`).
5. Click into the pygame window (not the Webots view) to drive and use the reporting UI.

This mirrors, at a smaller scale, how Erebus's own judged-run infrastructure works: `MainSupervisor.py` can launch a team's submitted controller inside an isolated Docker container that connects back to the running Webots simulation the same way — as an extern TCP client talking to the local Webots "server." The difference is that a real competition controller must decide *when* and *what* to report autonomously, rather than from a human clicking buttons.

---

## 7. Note on ROS / ROS2

Erebus, as shipped, does **not** include a built-in ROS or ROS2 bridge — its official controller interface is Webots' native `controller` Python/C++/Java API talking directly to `MainSupervisor` over the emitter/receiver protocol described above. There is no ROS-specific tooling, message definitions, or launch files in the Erebus repository itself; you'd be bridging it yourself (e.g. wrapping the `controller` API calls shown above inside a ROS2 node), most likely via Webots' own `webots_ros2` integration.

**ROS2 and Docker are both explicitly permitted for the 2026 competition**, per an official ruling from an RCJ moderator on the forum: [Clarification about ROS 2, Docker, and controller startup](https://junior.forum.robocup.org/t/clarification-about-ros-2-docker-and-controller-startup/5350). The key points from that thread:

- **ROS2 middleware is allowed** — "Yes, no problem" — but you should credit it in your Technical Description Paper, poster, and repository README, same as any external library.
- **Custom Docker images are allowed**, including any Ubuntu version, package selection, or ROS2 distribution — teams aren't restricted to a stock image.
- **A bash script (or similar wrapper) launching your Docker-based controller is permitted**, as long as the controller it ultimately starts connects via Webots' remote/extern controller protocol (the same TCP mechanism used in [Section 6](#6-serverclient-connected-method-extern-controller--scoring-ui)) and runs fully autonomously — no internet access and no human oversight during a run.
- The overarching constraint, in the moderator's words, is that execution **"must respect the spirit of the competition"** — no human control, and the problem-solving code must genuinely be the team's own work.

Rulings like this can be season-specific and are easy to miss if you only read the PDF rulebook — when in doubt, search or ask on the [official forum](https://junior.forum.robocup.org/c/robocupjunior-rescue/6) before committing your team's architecture to an assumption.

---

## 8. Links

**This competition's forks (use these to actually set up and play):**

- [Our installation guide](installation/) — start here, not the official installation docs.
- [RCJA Erebus fork, `entry-level-floor-victims` branch](https://github.com/wilsoncheng-sgcs/erebus/tree/entry-level-floor-victims) — the simulator this doc's Entry Level tier runs on; clone this instead of the official release.
- [RCJA Map Editor (live app)](https://wilsoncheng-sgcs.github.io/erebus-map-editor-RCJA/) / [repo](https://github.com/wilsoncheng-sgcs/erebus-map-editor-RCJA) — the map editor with the Entry Level ruleset tier.
- [Entry Level design rationale](https://github.com/wilsoncheng-sgcs/erebus/blob/entry-level-floor-victims/docs/entry-level-plan.md) — full technical write-up of what changed and why.

**Upstream/official (what the forks above are based on):**

- [Erebus Official Website](https://erebus.rcj.cloud/)
- [Erebus Documentation](https://v25.erebus.rcj.cloud/docs/)
- [Erebus GitHub (source, releases, issues)](https://github.com/robocup-junior/erebus)
- [Robot Customizer](https://v25.robot.erebus.rcj.cloud/) / [Robot Customizer issues](https://github.com/robocup-junior/erebus-robot-customisation/issues)
- [Official Map Generator](https://osaka.rcj.cloud/service/editor/simulation/2026) / [source (rcj-rescue-cms)](https://github.com/robocup-junior/rcj-rescue-cms) — what the RCJA map editor above was forked from
- [Official Rules (RoboCupJunior)](https://junior.robocup.org/) — always check for the season-specific PDF; a 2026 copy is bundled in this repo at [`RCJRescueSimulation2026-final.pdf`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/RCJRescueSimulation2026-final.pdf)
- [RCJ Community Discord](https://discord.gg/5QQntAPg7K)
- [RCJ Official Forum — Rescue category](https://junior.forum.robocup.org/c/robocupjunior-rescue/6)

**This repo:**

- Sample controllers: [`winglander_v1.py`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1.py) (launched, WASD test only), [`winglander_v1_external.py`](https://github.com/wilsoncheng-sgcs/RCJA-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1_external.py) (extern/TCP, full telemetry + scoring UI)
