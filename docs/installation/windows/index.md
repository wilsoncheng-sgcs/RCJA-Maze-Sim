---
title: Windows Installation — RCJA Maze Rescue Sim
---

# Windows Installation Guide

[← Back to Installation overview](../)

## Quick Installation Guide

**Step 1: Install Python**

Download and install Python **3.9.x or 3.10.x (64-bit)** from the [official website](https://www.python.org/downloads/windows/). During installation, make sure **"Add Python to PATH"** is checked — this is the single most common thing people miss, and it breaks controller loading later.

**Step 2: Install Webots**

Download and install **Webots version 2023.b** from [this direct link](https://github.com/cyberbotics/webots/releases/download/R2023b/webots-R2023b_setup.exe).

**Step 3: Clone this competition's Erebus fork**

Unlike the official guide, **don't download the official Erebus release zip.** Instead, clone this competition's fork at the `entry-level-floor-victims` branch. If you don't already have Git for Windows, install it from [git-scm.com](https://git-scm.com/download/win) first, then open a terminal (Command Prompt or PowerShell) and run:

```
git clone -b entry-level-floor-victims https://github.com/wilsoncheng-sgcs/erebus.git
```

This gives you a folder (e.g. `erebus\`) with the exact same layout as an extracted official release zip — `game\worlds\`, `game\controllers\`, etc. — just sourced from the right place.

## Run the Environment

Double-click the world file at `game\worlds\world1.wbt` inside the folder you just cloned to open it in Webots. The Competition Supervisor panel should appear automatically alongside the 3D view.

**The first time you run the simulator, it automatically installs the Python libraries it needs** — this can take a little while and looks like nothing is happening; let it finish before assuming something's wrong.

## Troubleshooting

**Competition Supervisor doesn't appear.** This is common enough that it's worth treating as an expected extra step, not just a fallback:

1. Go to **Tools → Scene Tree** in Webots' top menu.
2. Find **`DEF MAINSUPERVISOR Robot`** in the scene tree, right-click it, and choose **Show Robot Window**.
3. If that still shows nothing, open this URL directly in your browser while the simulation is running: `http://localhost:1234/robot_windows/MainSupervisorWindow/MainSupervisorWindow.html?name=robot`.

You'll need to repeat these steps any time you accidentally close the panel later in a session — it isn't a one-time popup.

**Simulation seems to hang on first launch / nothing happens.** Check the Webots console for errors. If it's missing Python packages, install them manually:

```
python3 -m pip install numpy termcolor requests
```

**Controller won't load / Webots can't find Python.** Confirm Python is on your `PATH` ([guide](https://datatofish.com/add-python-to-windows-path/) if you're not sure), then in Webots go to **Tools → Preferences → General**, and set the "Python command" field to your Python executable if it isn't already picked up automatically.

**Simulation runs slowly.** Go to **Tools → Preferences → OpenGL** and lower the graphics settings.
