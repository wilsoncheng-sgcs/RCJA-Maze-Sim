"""Standalone (extern) Webots controller for the winglander_v1 robot.

Unlike robot0Controller.py, this script is NOT launched by Webots. You run it
yourself from a terminal, and it connects to an already-running Webots
simulation over TCP. This lets you start/stop/edit/restart the controller
without touching the Webots process itself.

All interaction happens through a pygame window instead of the Webots 3D
view or the terminal:
  - WASD drives the robot (captured by pygame, so you click the pygame
    window for focus, not the Webots view).
  - The camera feed is rendered live, upscaled from its native 40x32.
  - Distance sensor readings (DS1-DS4, in meters) are shown as text.
  - Victim/target identification: type X, Z (meters), pick a type from the
    dropdown (H/S/U victims, F/P/C/O cognitive targets), or click "Pull
    from GPS" to fill X/Z from a GPS device (if you've added one - see
    GPS_DEVICE_NAME below), then click "Report Victim/Target" to send it.
    See https://v25.erebus.rcj.cloud/docs/tutorials/emitter-and-receiver/

Install the one extra dependency once:
    pip install pygame

--- One-time Erebus setup ---

1. In the Erebus config.txt (game/controllers/MainSupervisor/config.txt), set
   the 5th field ("Keep remote") to 1, e.g. `0,0,0,0,1,0,`. This makes Erebus
   set the robot's controller field to `<extern>` itself when it spawns the
   robot (it regenerates the robot node on every reset, so editing the field
   by hand in the scene tree won't stick).

2. Make the Webots Python controller library importable. Either:
   a) Set WEBOTS_HOME once in your shell profile:
        export WEBOTS_HOME=/Applications/Webots.app
      (this script also falls back to that default path automatically), or
   b) Rely on the fallback path baked into this script below.

--- Running ---

1. Start/keep running the Erebus world in Webots. It will pause and wait for
   an extern connection for the "Erebus_Bot" robot.
2. In a separate terminal, run:
        python3 winglander_v1_external.py
   Optionally point it at a specific robot name / non-default host or port:
        WEBOTS_CONTROLLER_URL=tcp://127.0.0.1:1234/Erebus_Bot python3 winglander_v1_external.py
3. Click into the pygame window and drive with WASD.
"""

import os
import struct
import sys

# --- Make the `controller` module importable without Webots launching us ---
# On macOS, WEBOTS_HOME must be the .app bundle root; Webots' own wb.py
# appends "Contents/lib/controller/..." to it when loading the native library.
WEBOTS_HOME = os.environ.setdefault("WEBOTS_HOME", "/Applications/Webots.app")
CONTROLLER_PYTHON_DIR = os.path.join(WEBOTS_HOME, "Contents", "lib", "controller", "python")
if CONTROLLER_PYTHON_DIR not in sys.path:
    sys.path.insert(0, CONTROLLER_PYTHON_DIR)

# Tell the controller library which simulation/robot to attach to.
os.environ.setdefault("WEBOTS_CONTROLLER_URL", "tcp://127.0.0.1:1234/Erebus_Bot")

from controller import Camera, Robot  # noqa: E402  (import must follow sys.path setup)

try:
    import pygame
except ImportError:
    sys.exit("pygame is required for the UI. Install it with: pip install pygame")

TIME_STEP = 32
MAX_SPEED = 6.28  # rad/s

CAMERA_DISPLAY_SIZE = 320  # camera feed is fit to this box, preserving aspect ratio
PANEL_WIDTH = 220
MARGIN = 12
BG_COLOR = (30, 30, 30)
TEXT_COLOR = (0, 255, 120)
LABEL_COLOR = (200, 200, 200)

robot = Robot()

wheel1 = robot.getDevice("wheel1 motor")  # right wheel (x=260)
wheel2 = robot.getDevice("wheel2 motor")  # left wheel (x=-260)
for wheel in (wheel1, wheel2):
    wheel.setPosition(float("inf"))
    wheel.setVelocity(0.0)

distance_sensors = [robot.getDevice(name) for name in ("DS1", "DS2", "DS3", "DS4")]
for ds in distance_sensors:
    ds.enable(TIME_STEP)

camera = robot.getDevice("camera1")
camera.enable(TIME_STEP)
cam_width = camera.getWidth()
cam_height = camera.getHeight()

# Erebus's Colour sensor is really a 1x1 Camera under the hood, named by
# whatever customName you gave it in winglander_v1.json.
colour_sensor = robot.getDevice("colour_sensor")
colour_sensor.enable(TIME_STEP)

# Fit the camera feed into a fixed-size box regardless of native resolution,
# so bumping the camera's resolution in winglander_v1.json doesn't blow up
# the window size. Upscales small cameras, downscales large ones.
cam_fit_scale = CAMERA_DISPLAY_SIZE / max(cam_width, cam_height)
cam_display_width = max(1, round(cam_width * cam_fit_scale))
cam_display_height = max(1, round(cam_height * cam_fit_scale))

# Erebus's own game protocol: the robot's default "emitter"/"receiver"
# devices talk to MainSupervisor. Sending a single 'G' byte requests game
# info back as (tag, score, game_time_left_s, real_time_left_s).
emitter = robot.getDevice("emitter")
receiver = robot.getDevice("receiver")
receiver.enable(TIME_STEP)

GAME_INFO_FORMAT = "c f i i"
GAME_INFO_SIZE = struct.calcsize(GAME_INFO_FORMAT)
GAME_INFO_QUERY_STEPS = 32  # ~1s at TIME_STEP=32ms
game_info = None  # (score, game_time_left, real_time_left)

# Unprompted "lack of progress" notice: MainSupervisor sends a single 'L'
# byte whenever it relocates the robot (20s stationary, or fell into a
# black hole). No request needed - just watch for it.
LOP_FORMAT = "c"
LOP_SIZE = struct.calcsize(LOP_FORMAT)
lop_count = 0
last_lop_step = None

# Victim/target identification report, per
# https://v25.erebus.rcj.cloud/docs/tutorials/emitter-and-receiver/ :
# send (est_x_cm: int, est_z_cm: int, victim_type: char) as struct "i i c".
# Valid victim_type chars: H/U/S (victims), F/P/C/O (cognitive targets).
VICTIM_REPORT_FORMAT = "i i c"

# GPS is optional - only present if you've added one to winglander_v1.json.
# Rename this to match whatever customName you gave it there.
GPS_DEVICE_NAME = "gps"
gps = robot.getDevice(GPS_DEVICE_NAME)
if gps is not None:
    gps.enable(TIME_STEP)


class InputBox:
    """A minimal single-line text input box for pygame (click to focus)."""

    INACTIVE_COLOR = (100, 100, 100)
    ACTIVE_COLOR = (0, 200, 255)

    def __init__(self, rect, numeric=False, max_len=None):
        self.rect = pygame.Rect(rect)
        self.numeric = numeric
        self.max_len = max_len
        self.text = ""
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN or event.key == pygame.K_TAB:
                self.active = False
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                ch = event.unicode
                if not ch:
                    return
                if self.numeric and not (
                    ch.isdigit()
                    or (ch == "-" and not self.text)
                    or (ch == "." and "." not in self.text)
                ):
                    return
                if self.max_len is not None and len(self.text) >= self.max_len:
                    return
                self.text += ch if self.numeric else ch.upper()

    def draw(self, screen, font):
        color = self.ACTIVE_COLOR if self.active else self.INACTIVE_COLOR
        pygame.draw.rect(screen, color, self.rect, 2)
        screen.blit(font.render(self.text, True, (255, 255, 255)), (self.rect.x + 6, self.rect.y + 4))


class Button:
    """A minimal clickable button for pygame."""

    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def handle_event(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)

    def draw(self, screen, font):
        pygame.draw.rect(screen, (60, 60, 60), self.rect)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 1)
        text_surf = font.render(self.label, True, (255, 255, 255))
        screen.blit(text_surf, text_surf.get_rect(center=self.rect.center))


class Dropdown:
    """A minimal clickable dropdown for pygame - closed shows the current
    selection, click to open a list of options below it."""

    OPTION_HEIGHT = 24

    def __init__(self, rect, options, labels=None):
        self.rect = pygame.Rect(rect)
        self.options = options
        self.labels = labels or options
        self.selected_index = 0
        self.open = False

    @property
    def value(self):
        return self.options[self.selected_index]

    def option_rect(self, i):
        return pygame.Rect(self.rect.x, self.rect.bottom + i * self.OPTION_HEIGHT,
                            self.rect.width, self.OPTION_HEIGHT)

    def handle_event(self, event):
        """Returns True if this event was consumed (so callers can avoid
        also triggering whatever UI element is visually underneath)."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False
        if self.rect.collidepoint(event.pos):
            self.open = not self.open
            return True
        if self.open:
            for i in range(len(self.options)):
                if self.option_rect(i).collidepoint(event.pos):
                    self.selected_index = i
                    break
            self.open = False
            return True
        return False

    def draw_closed(self, screen, font):
        pygame.draw.rect(screen, (60, 60, 60), self.rect)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 1)
        text_surf = font.render(f"{self.labels[self.selected_index]} ▾", True, (255, 255, 255))
        screen.blit(text_surf, (self.rect.x + 6, self.rect.y + 4))

    def draw_open(self, screen, font):
        if not self.open:
            return
        for i, label in enumerate(self.labels):
            rect = self.option_rect(i)
            pygame.draw.rect(screen, (80, 80, 80), rect)
            pygame.draw.rect(screen, (150, 150, 150), rect, 1)
            screen.blit(font.render(label, True, (255, 255, 255)), (rect.x + 6, rect.y + 4))


pygame.init()
font = pygame.font.SysFont("monospace", 16)

TOP_CONTENT_HEIGHT = 480
# Extra headroom so the type dropdown's open option list (7 entries) never
# overlaps the report button/status line below it.
BOTTOM_PANEL_HEIGHT = 170 + Dropdown.OPTION_HEIGHT * 7

window_width = max(cam_display_width + PANEL_WIDTH + MARGIN * 3, 600)
window_height = max(cam_display_height, TOP_CONTENT_HEIGHT) + BOTTOM_PANEL_HEIGHT + MARGIN * 3
screen = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("winglander_v1 - WASD to drive")
clock = pygame.time.Clock()

# --- Victim/target report UI, laid out along the bottom of the window ---
# Victim types: Harmed/Stable/Unharmed. Cognitive target ("hazmat") types:
# Flammable Gas/Poison/Corrosive/Organic Peroxide. Confirmed against
# RCJRescueSimulation2026-final.pdf and Victim.py's VICTIM_TYPES/TARGET_TYPES.
VICTIM_TYPE_OPTIONS = ["H", "S", "U", "F", "P", "C", "O"]
VICTIM_TYPE_LABELS = [
    "H - Harmed victim",
    "S - Stable victim",
    "U - Unharmed victim",
    "F - Flammable Gas",
    "P - Poison",
    "C - Corrosive",
    "O - Organic Peroxide",
]

bottom_y = max(cam_display_height, TOP_CONTENT_HEIGHT) + MARGIN * 2
x_box = InputBox((MARGIN + 30, bottom_y + 28, 70, 26), numeric=True)
z_box = InputBox((MARGIN + 160, bottom_y + 28, 70, 26), numeric=True)
type_dropdown = Dropdown((MARGIN + 305, bottom_y + 28, 190, 26),
                          VICTIM_TYPE_OPTIONS, VICTIM_TYPE_LABELS)
gps_button = Button((MARGIN, bottom_y + 70, 130, 26), "Pull from GPS")
report_button = Button((MARGIN + 150, bottom_y + 70, 160, 30), "Report Victim/Target")
report_status = "" if gps is not None else f"GPS device '{GPS_DEVICE_NAME}' not found - type X/Z manually"

print("Connected to Webots. Click the pygame window and drive with WASD.")

running = True
step_count = 0
while running and robot.step(TIME_STEP) != -1:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        for box in (x_box, z_box):
            box.handle_event(event)

        # If the dropdown was open, it owns this click (either to pick an
        # option or to close itself) - don't let it also fall through to
        # whatever button is visually underneath the option list.
        dropdown_was_open = type_dropdown.open
        dropdown_consumed = type_dropdown.handle_event(event)
        if dropdown_was_open and dropdown_consumed:
            continue

        if gps_button.handle_event(event):
            if gps is None:
                report_status = f"GPS device '{GPS_DEVICE_NAME}' not found"
            else:
                gps_x, _gps_y, gps_z = gps.getValues()
                x_box.text = f"{gps_x:.3f}"
                z_box.text = f"{gps_z:.3f}"
                report_status = "Pulled X/Z from GPS"

        if report_button.handle_event(event):
            try:
                est_x_cm = round(float(x_box.text) * 100)
                est_z_cm = round(float(z_box.text) * 100)
                victim_type = type_dropdown.value
                emitter.send(
                    struct.pack(
                        VICTIM_REPORT_FORMAT,
                        est_x_cm,
                        est_z_cm,
                        victim_type.encode("utf-8"),
                    )
                )
                report_status = f"Sent report: type={victim_type} x={x_box.text} z={z_box.text}"
            except ValueError:
                report_status = "Invalid input: X and Z must be numbers"

    typing = x_box.active or z_box.active

    if step_count % GAME_INFO_QUERY_STEPS == 0:
        emitter.send(struct.pack("c", b"G"))

    while receiver.getQueueLength() > 0:
        data = receiver.getBytes()
        if len(data) == GAME_INFO_SIZE:
            tag, score, game_time_left, real_time_left = struct.unpack(GAME_INFO_FORMAT, data)
            if tag == b"G":
                game_info = (score, game_time_left, real_time_left)
        elif len(data) == LOP_SIZE:
            (tag,) = struct.unpack(LOP_FORMAT, data)
            if tag == b"L":
                lop_count += 1
                last_lop_step = step_count
        receiver.nextPacket()

    step_count += 1

    left_speed = 0.0
    right_speed = 0.0

    if not typing:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            left_speed += MAX_SPEED
            right_speed += MAX_SPEED
        if keys[pygame.K_s]:
            left_speed -= MAX_SPEED
            right_speed -= MAX_SPEED
        if keys[pygame.K_a]:
            left_speed -= MAX_SPEED
            right_speed += MAX_SPEED
        if keys[pygame.K_d]:
            left_speed += MAX_SPEED
            right_speed -= MAX_SPEED

    left_speed = max(-MAX_SPEED, min(MAX_SPEED, left_speed))
    right_speed = max(-MAX_SPEED, min(MAX_SPEED, right_speed))
    wheel2.setVelocity(left_speed)
    wheel1.setVelocity(right_speed)

    # --- Render ---
    screen.fill(BG_COLOR)

    image_bytes = camera.getImage()
    if image_bytes:
        cam_surface = pygame.image.frombuffer(image_bytes, (cam_width, cam_height), "BGRA")
        cam_surface = pygame.transform.scale(cam_surface, (cam_display_width, cam_display_height))
        screen.blit(cam_surface, (MARGIN, MARGIN))

    panel_x = cam_display_width + MARGIN * 2
    y = MARGIN
    screen.blit(font.render("Distance sensors (m):", True, LABEL_COLOR), (panel_x, y))
    y += 24
    for ds in distance_sensors:
        line = f"{ds.getName()}: {ds.getValue():.2f}"
        screen.blit(font.render(line, True, TEXT_COLOR), (panel_x, y))
        y += 22

    y += 16
    screen.blit(font.render("Colour sensor (RGB):", True, LABEL_COLOR), (panel_x, y))
    y += 24
    colour_image = colour_sensor.getImage()
    if colour_image:
        r = Camera.imageGetRed(colour_image, 1, 0, 0)
        g = Camera.imageGetGreen(colour_image, 1, 0, 0)
        b = Camera.imageGetBlue(colour_image, 1, 0, 0)
        screen.blit(font.render(f"({r}, {g}, {b})", True, TEXT_COLOR), (panel_x, y))
        y += 22
        swatch_rect = pygame.Rect(panel_x, y, 40, 20)
        pygame.draw.rect(screen, (r, g, b), swatch_rect)
        pygame.draw.rect(screen, LABEL_COLOR, swatch_rect, 1)
        y += 28
    else:
        screen.blit(font.render("(no reading)", True, TEXT_COLOR), (panel_x, y))
        y += 22

    y += 16
    screen.blit(font.render("Game info (receiver):", True, LABEL_COLOR), (panel_x, y))
    y += 24
    if game_info is not None:
        score, game_time_left, real_time_left = game_info
        for line in (
            f"score: {score:.2f}",
            f"game time left: {game_time_left}s",
            f"real time left: {real_time_left}s",
        ):
            screen.blit(font.render(line, True, TEXT_COLOR), (panel_x, y))
            y += 22
    else:
        screen.blit(font.render("(waiting for reply...)", True, TEXT_COLOR), (panel_x, y))
        y += 22

    y += 16
    screen.blit(font.render("Lack of progress:", True, LABEL_COLOR), (panel_x, y))
    y += 24
    recent_lop = last_lop_step is not None and (step_count - last_lop_step) < GAME_INFO_QUERY_STEPS * 3
    lop_color = (255, 80, 80) if recent_lop else TEXT_COLOR
    screen.blit(font.render(f"relocations: {lop_count}", True, lop_color), (panel_x, y))
    y += 22

    y += 16
    for line in ("W: forward", "S: backward", "A: turn left", "D: turn right"):
        screen.blit(font.render(line, True, LABEL_COLOR), (panel_x, y))
        y += 20

    # --- Victim/target report panel ---
    pygame.draw.line(
        screen, LABEL_COLOR, (MARGIN, bottom_y - 6), (window_width - MARGIN, bottom_y - 6)
    )
    screen.blit(
        font.render("Victim/Target report (X, Z in meters):", True, LABEL_COLOR),
        (MARGIN, bottom_y),
    )
    screen.blit(font.render("X:", True, LABEL_COLOR), (MARGIN, bottom_y + 34))
    screen.blit(font.render("Z:", True, LABEL_COLOR), (MARGIN + 130, bottom_y + 34))
    screen.blit(font.render("Type:", True, LABEL_COLOR), (MARGIN + 260, bottom_y + 34))
    x_box.draw(screen, font)
    z_box.draw(screen, font)
    type_dropdown.draw_closed(screen, font)
    gps_button.draw(screen, font)
    report_button.draw(screen, font)
    screen.blit(font.render(report_status, True, TEXT_COLOR), (MARGIN, bottom_y + 108))
    # Drawn last so the open option list renders on top of everything else.
    type_dropdown.draw_open(screen, font)

    pygame.display.flip()
    clock.tick(1000 // TIME_STEP)

pygame.quit()
