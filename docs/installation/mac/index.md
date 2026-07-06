---
title: macOS Installation — RCJA Maze Rescue Sim
---

# macOS Installation Guide

[← Back to Installation overview](../)

## Quick Installation Guide

**Step 1: Install Python**

Download and install Python **3.9.x or 3.10.x (64-bit)** from the [official website](https://www.python.org/downloads/macos/). Even if you already have Python via Homebrew, Anaconda, etc., install a fresh copy from python.org — Webots expects to find (and sometimes auto-detects) that specific install.

**Step 2: Install Webots**

Download and install **Webots version 2023.b** from [this direct link](https://github.com/cyberbotics/webots/releases/download/R2023b/webots-R2023b.dmg).

**Step 3: Clone this competition's Erebus fork**

Unlike the official guide, **don't download the official Erebus release zip.** Instead, clone this competition's fork at the `entry-level-floor-victims` branch. macOS ships with Git already installed, so just open Terminal and run:

```
git clone -b entry-level-floor-victims https://github.com/wilsoncheng-sgcs/erebus.git
```

This gives you a folder (e.g. `erebus/`) with the exact same layout as an extracted official release zip — `game/worlds/`, `game/controllers/`, etc. — just sourced from the right place.

## Run the Environment

Double-click the world file at `game/worlds/world1.wbt` inside the folder you just cloned to open it in Webots. The Competition Supervisor panel should appear automatically alongside the 3D view.

**The first time you run the simulator, it automatically installs the Python libraries it needs** — this can take a little while and looks like nothing is happening; let it finish before assuming something's wrong.

## Troubleshooting

**Competition Supervisor doesn't appear.** This is common enough that it's worth treating as an expected extra step, not just a fallback:

1. Go to **Tools → Scene Tree** in Webots' top menu.
2. Find **`DEF MAINSUPERVISOR Robot`** in the scene tree, right-click it, and choose **Show Robot Window**.
3. If that still shows nothing, open this URL directly in your browser while the simulation is running: `http://localhost:1234/robot_windows/MainSupervisorWindow/MainSupervisorWindow.html?name=robot`.

You'll need to repeat these steps any time you accidentally close the panel later in a session — it isn't a one-time popup.

**Webots warns it can't find Python, or the wrong Python is picked up.** In Terminal, run:

```
which python3
```

Copy the path it prints, then in Webots go to **Preferences → General** and paste it into the "Python command" field.

**Simulation runs slowly.** Go to **Preferences → OpenGL** and lower the graphics settings. Note that whatever performance settings you use for your own testing may not match what's used on the actual competition machines, so don't assume identical behavior across setups.
