---
title: RCJ Maze Rescue Sim — Documentation
---

# RCJ Maze Rescue Sim

Documentation for setting up a custom robot and driving/testing it inside the RoboCupJunior (RCJ) Rescue Simulation platform (Erebus), using this repo's `winglander_v1` robot as the running example.

**Contents**

1. [What is RCJ Maze Rescue Sim](#1-what-is-rcj-maze-rescue-sim)
2. [Setup Instructions](#2-setup-instructions)
3. [Components That Work Together](#3-components-that-work-together)
4. [Quick Start — WASD Test Controller](#4-quick-start--wasd-test-controller)
5. [Scoring System](#5-scoring-system)
6. [Server/Client Connected Method (extern controller + scoring UI)](#6-serverclient-connected-method-extern-controller--scoring-ui)
7. [Note on ROS / ROS2](#7-note-on-ros--ros2)
8. [Links](#8-links)

---

## 1. What is RCJ Maze Rescue Sim

RCJ Maze Rescue Sim (branded **Erebus**) is the simulation sub-league of [RoboCupJunior Rescue](https://junior.robocup.org/), first introduced in 2021 and now a core part of RCJ Rescue internationally. Teams write autonomous Python (or C/C++/Java) controllers that pilot a customizable robot through a procedurally-assembled maze, mapping it while locating and correctly classifying **victims** (injured people) and **cognitive targets** (hazmat-style signs), all without any human input during a run.

Under the hood, Erebus is a rules/scoring layer (a Webots "Supervisor" controller) that runs on top of **Webots**, Cyberbotics' physics-accurate robot simulator. This repo customizes the robot itself (`winglander_v1.json`) and adds development-only tooling for driving and inspecting it outside of a real competition run.

---

## 2. Setup Instructions

1. **Install Python 3.9+** — required by both Erebus and your own controller code. Make sure `python3` is on your `PATH`.
2. **Install Webots** — Erebus targets a specific Webots release per season (v26.1 of Erebus targets a matching Webots release; check the [Erebus releases page](https://github.com/robocup-junior/erebus/releases) for the exact version pinned to the release you download). Get it from [cyberbotics.com](https://cyberbotics.com/).
3. **Download Erebus** — grab the [latest release](https://github.com/robocup-junior/erebus/releases) (a zip) and extract it. This repo assumes an extracted copy alongside your controller code (e.g. `~/Downloads/erebus-26.1/`).
4. **Open a world** — in Webots, open `game/worlds/world1.wbt` (or any world under `game/worlds/`) from your extracted Erebus folder.
5. **Build your robot** — use the [Robot Customizer](https://v25.robot.erebus.rcj.cloud/) web tool to design a robot (wheels, sensors, camera, etc.) and export it as a JSON file — that's what `winglander_v1.json` in this repo is.
6. **Generate/import a maze** — use the [Map Generator](https://osaka.rcj.cloud/service/editor/simulation/2025) if you need a custom maze layout, otherwise use one of the bundled `game/worlds/*.wbt` files.
7. **Load your robot into the simulation** — Erebus reads your robot's JSON through its robot window UI inside Webots and generates the matching Webots PROTO/device tree for it automatically (see [Section 3](#3-components-that-work-together)).

---

## 3. Components That Work Together

Four distinct pieces combine to make a working simulated robot:

| Component | Role |
|---|---|
| **Webots** | The underlying 3D physics simulator. Runs the world, the robot's rigid bodies/sensors/motors, and executes controller processes (your Python code). Erebus does not replace Webots — it runs *inside* it. |
| **Erebus** | The competition layer. Ships as a Webots project: a `MainSupervisor` controller that spawns the maze, tracks the game clock, scores victim/target identifications, enforces lack-of-progress relocations, and exposes a `robot0Controller`/`robot1Controller` slot for your code. Also ships example worlds and an example player controller. |
| **Robot Customizer** ([v25.robot.erebus.rcj.cloud](https://v25.robot.erebus.rcj.cloud/)) | A web app for visually placing wheels, distance sensors, a camera, a colour sensor, GPS, etc. on a robot chassis within a fixed points budget. Exports a JSON file (e.g. `winglander_v1.json`) describing every component's type, position, rotation, and custom name. Erebus's `ProtoGenerator.py` reads this JSON at runtime and generates the actual Webots PROTO node for your robot — including the exact device names your controller must use (e.g. a wheel named `wheel1` in the JSON becomes a Webots motor device named `"wheel1 motor"`). |
| **Map Generator** ([osaka.rcj.cloud](https://osaka.rcj.cloud/service/editor/simulation/2025)) | A web app for laying out maze tiles, walls, victims, and cognitive targets, exporting a Webots world file Erebus can load. |

The practical implication: **your JSON robot config is not itself a Webots file** — Erebus regenerates the robot's PROTO from it every time the world (re)loads, so device names follow Erebus's naming convention, not whatever you called things in the customizer verbatim (see the wheel-naming example above).

---

## 4. Quick Start — WASD Test Controller

The fastest way to confirm your robot config is wired up correctly (correct device names, sensors reading sane values, camera producing frames) is to drive it manually with the keyboard before writing any autonomous logic.

> [!WARNING]
> **This WASD controller is a platform-testing tool only.** Manual/keyboard-driven control is **not permitted in RCJ Rescue Simulation competition** — competition robots must operate fully autonomously, with no operator input during a run. Do not submit this file, or any code based on directly reading human keyboard input during a match, as your competition controller. Always check the current [official rules](#8-links) for exactly what's permitted.

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

Full file: [`controllers/winglander_v1/winglander_v1.py`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1.py).

---

## 5. Scoring System

Erebus's scoring engine (`MainSupervisor.py`) awards and deducts points for things like:

- **Victim identification** — correctly reporting a nearby victim's position and type (`H` harmed, `S` stable, `U` unharmed) via the emitter/receiver protocol (see [Section 6](#6-serverclient-connected-method-extern-controller--scoring-ui)). Correct type adds a bonus on top of a base identification score; a wrong-but-nearby report is still scored lower, and a report with nothing nearby is a **misidentification penalty**.
- **Cognitive target identification** — same mechanism, but for hazmat-style signs (`F` flammable gas, `P` poison, `C` corrosive, `O` organic peroxide), generally worth more points than victims.
- **Mapping score** — submitting a reconstructed map of the maze at the end of a run, scored against the ground-truth layout.
- **Exit bonus** — returning to the start tile before time runs out adds a percentage bonus to the final score, but only if at least one victim was identified.
- **Lack-of-progress penalty** — the robot is automatically relocated to its last checkpoint if stationary for too long (20s) or if it falls into a black-hole tile, resetting forward progress on that section.
- **Room/tile multipliers** — some rooms multiply the points scored for victims/targets found inside them.

These mechanics and their exact point values **change between rule seasons** and are governed by the official rulebook — this doc intentionally does not hardcode point totals. Always check the version-matched official rules PDF (a 2026 copy is bundled in this repo as [`RCJRescueSimulation2026-final.pdf`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/RCJRescueSimulation2026-final.pdf)) for authoritative scoring details, and cross-reference against whatever Erebus release you're actually running, since scoring logic lives in that release's `MainSupervisor.py`/`Victim.py`.

---

## 6. Server/Client Connected Method (extern controller + scoring UI)

Beyond simple WASD driving, Erebus's robot talks to the game engine (`MainSupervisor`, acting as the "server") over a pair of built-in `emitter`/`receiver` devices — this is the same channel your real autonomous controller uses to submit victim/target reports and query game state. You can run your controller as a **standalone ("extern") process**, connected to a live Webots simulation over TCP, instead of having Webots launch it for you — useful for iterating without restarting the sim each time.

This repo's [`controllers/winglander_v1/winglander_v1_extern.py`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1_extern.py) demonstrates the full loop in a single pygame window:

- WASD driving (again, **testing only** — see the warning in [Section 4](#4-quick-start--wasd-test-controller))
- Live camera feed and colour sensor RGB readout
- Distance sensor readings
- **Game info** — periodically sends a single `'G'` byte via the emitter, and unpacks the reply `(score, game_time_left, real_time_left)` from the receiver
- **Lack-of-progress** — passively watches for an unprompted single `'L'` byte the server sends whenever it relocates the robot
- **Victim/target reporting UI** — X/Z coordinate fields (with a "Pull from GPS" shortcut) and a dropdown of the 7 valid type codes (H/S/U/F/P/C/O), packed as `struct.pack("i i c", x_cm, z_cm, type_char)` and sent via the emitter on a button click

Setup summary (see the full docstring in the file for details):

1. In `game/controllers/MainSupervisor/config.txt`, set the 5th field ("Keep remote") to `1` so Erebus marks the robot's controller as `<extern>` instead of launching it itself.
2. Restart Webots so the config change takes effect, and load your world.
3. Run `python3 winglander_v1_extern.py` from a terminal — it connects to the running simulation over `WEBOTS_CONTROLLER_URL` (defaults to `tcp://127.0.0.1:1234/Erebus_Bot`).
4. Click into the pygame window (not the Webots view) to drive and use the reporting UI.

This mirrors, at a smaller scale, how Erebus's own judged-run infrastructure works: `MainSupervisor.py` can launch a team's submitted controller inside an isolated Docker container that connects back to the running Webots simulation the same way — as an extern TCP client talking to the local Webots "server." The difference is that a real competition controller must decide *when* and *what* to report autonomously, rather than from a human clicking buttons.

---

## 7. Note on ROS / ROS2

Erebus, as shipped, does **not** include a built-in ROS or ROS2 bridge — its official controller interface is Webots' native `controller` Python/C++/Java API talking directly to `MainSupervisor` over the emitter/receiver protocol described above. There is no ROS-specific tooling, message definitions, or launch files in the Erebus repository as of this writing.

That said, Webots itself has first-party ROS2 integration (`webots_ros2`) usable in *generic* Webots projects. If you want to control this robot via ROS2, you would need to bridge it yourself (e.g. a ROS2 node that wraps the `controller` API calls shown above), and you would be doing so entirely outside of what Erebus or the official rules provide or test against.

**Before building on ROS2 for competition use, check the current official rules** for whether ROS/ROS2-based controllers are permitted at all, since permitted languages/frameworks are explicitly defined by the rulebook and can change between seasons.

---

## 8. Links

- [Erebus Official Website](https://erebus.rcj.cloud/)
- [Erebus Documentation](https://v25.erebus.rcj.cloud/docs/)
- [Erebus GitHub (source, releases, issues)](https://github.com/robocup-junior/erebus)
- [Robot Customizer](https://v25.robot.erebus.rcj.cloud/) / [Robot Customizer issues](https://github.com/robocup-junior/erebus-robot-customisation/issues)
- [Map Generator](https://osaka.rcj.cloud/service/editor/simulation/2025)
- [Official Rules (RoboCupJunior)](https://junior.robocup.org/) — always check for the season-specific PDF; a 2026 copy is bundled in this repo at [`RCJRescueSimulation2026-final.pdf`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/RCJRescueSimulation2026-final.pdf)
- [RCJ Community Discord](https://discord.gg/5QQntAPg7K)
- [RCJ Official Forum](https://junior.forum.robocup.org/)
- This repo's sample controllers: [`winglander_v1.py`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1.py) (launched, WASD test only), [`winglander_v1_extern.py`](https://github.com/wilsoncheng-sgcs/RCJ-Maze-Sim/blob/main/controllers/winglander_v1/winglander_v1_extern.py) (extern/TCP, full telemetry + scoring UI)
