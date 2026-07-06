---
title: Linux Installation — RCJA Maze Rescue Sim
---

# Linux (Ubuntu) Installation Guide

[← Back to Installation overview](../)

## Quick Installation Guide

**Step 1: Install pip3 and required libraries**

Open a terminal and run:

```
sudo apt install python3-pip
python3 -m pip install numpy termcolor requests
```

**Step 2: Install Webots version 2023.b**

```
wget https://github.com/cyberbotics/webots/releases/download/R2023b/webots_2023b_amd64.deb
sudo apt install ./webots_2023b_amd64.deb
```

**Step 3: Clone this competition's Erebus fork**

Unlike the official guide, **don't download the official Erebus release zip.** Instead, clone this competition's fork at the `entry-level-floor-victims` branch:

```
git clone -b entry-level-floor-victims https://github.com/wilsoncheng-sgcs/erebus.git
```

This gives you a folder (e.g. `erebus/`) with the exact same layout as an extracted official release zip — `game/worlds/`, `game/controllers/`, etc. — just sourced from the right place.

## Run the Environment

Run the world file from a terminal, e.g. if you cloned into your home directory:

```
webots '/home/USER_NAME/erebus/game/worlds/world1.wbt'
```

The Competition Supervisor panel should appear automatically alongside the 3D view. **The first time you run the simulator, it automatically installs the Python libraries it needs** — this can take a little while; let it finish before assuming something's wrong.

## Troubleshooting

**Competition Supervisor doesn't appear.** This is common enough that it's worth treating as an expected extra step, not just a fallback:

1. Go to **Tools → Scene Tree** in Webots' top menu.
2. Find **`DEF MAINSUPERVISOR Robot`** in the scene tree, right-click it, and choose **Show Robot Window**.
3. If that still shows nothing, open this URL directly in your browser while the simulation is running: `http://localhost:1234/robot_windows/MainSupervisorWindow/MainSupervisorWindow.html?name=robot`.

You'll need to repeat these steps any time you accidentally close the panel later in a session — it isn't a one-time popup.

**Webots shows a blank/black screen.** Make sure you extracted/cloned into a clean folder before opening the world file rather than opening it in place inside a zip or a read-only mount.

**Simulation runs slowly.** Go to **Tools → Preferences → OpenGL** and lower the graphics accuracy settings.

**Competition Controller / robot window doesn't appear after a while.** Give it a few minutes — this can be slow on first load — and otherwise work through the Competition Supervisor troubleshooting steps above.
