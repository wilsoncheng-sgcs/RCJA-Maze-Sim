"""Standalone (extern) Webots controller for the winglander_v2 robot.

winglander_v2.json swapped the v1 robot's DS1-DS4 distance sensors for a
360-degree LiDAR, and added an IMU (InertialUnit) and GPS. This script is
NOT launched by Webots - you run it yourself from a terminal, and it
connects to an already-running Webots simulation over TCP. This lets you
start/stop/edit/restart the controller without touching the Webots process
itself.

All interaction happens through a pygame window instead of the Webots 3D
view or the terminal:
  - A "Mode: MANUAL / AUTONOMOUS" toggle button (top of the right-hand
    panel) switches between WASD driving and a clearly marked block in
    the main loop below (search for "AUTONOMOUS MODE") where you add your
    own control code - it runs every step while autonomous mode is on,
    with WASD ignored.
  - WASD drives the robot in manual mode (captured by pygame, so you click
    the pygame window for focus, not the Webots view).
  - The camera feed is rendered live, upscaled from its native resolution.
  - Wheel motion data: each wheel's encoder position (rad) and measured
    velocity (rad/s, from differentiating position over time), next to the
    commanded velocity for comparison.
  - LiDAR readings sampled every 30 degrees around a full circle, drawn as
    a radar-style clock face (12 = straight ahead, 3 = right, 6 = behind,
    9 = left) with a connecting polygon plus the exact numeric value at
    each hour.
  - Victim/target identification: type X, Z (meters), pick a type from the
    dropdown (H/S/U victims, F/P/C/O cognitive targets), or click "Pull
    from GPS" to fill X/Z from the robot's GPS device, then click
    "Report Victim/Target" to send it.
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
        python3 winglander_v2_external.py
   Optionally point it at a specific robot name / non-default host or port:
        WEBOTS_CONTROLLER_URL=tcp://127.0.0.1:1234/Erebus_Bot python3 winglander_v2_external.py
3. Click into the pygame window (not the Webots view) and drive with WASD.
"""

import math
import os
import struct
import sys
import colorsys

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
DT = TIME_STEP / 1000.0  # seconds per simulation step, for velocity from position deltas
MAX_SPEED = 6.28  # rad/s

CAMERA_DISPLAY_SIZE = 320  # camera feed is fit to this box, preserving aspect ratio
PANEL_WIDTH = 260  # wide enough for a 2-column, 6-row LiDAR clock readout
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

# Wheel motion telemetry: each wheel motor has a matching PositionSensor
# device, named "<customName> sensor" by Erebus's ProtoGenerator. Velocity
# isn't directly exposed, so it's derived from the change in position
# between steps.
wheel1_sensor = robot.getDevice("wheel1 sensor")
wheel2_sensor = robot.getDevice("wheel2 sensor")
wheel1_sensor.enable(TIME_STEP)
wheel2_sensor.enable(TIME_STEP)
wheel1_prev_pos = None
wheel2_prev_pos = None

camera = robot.getDevice("camera1")
camera.enable(TIME_STEP)
cam_width = camera.getWidth()
cam_height = camera.getHeight()

# Erebus's Colour sensor is really a 1x1 Camera under the hood, named by
# whatever customName you gave it in winglander_v2.json.
colour_sensor = robot.getDevice("colour_sensor")
colour_sensor.enable(TIME_STEP)

# Calibrate these against actual in-sim readings (print raw HSV once and
# look at real values) rather than assuming pure theoretical primaries -
# textures + lighting shift things a bit.
BLACK_MAX_VALUE = 0.25      # anything darker than this is "black", hue ignored
COLOUR_MIN_SATURATION = 0.35  # below this, treat as unsaturated/floor, not a marker

HUE_BUCKETS = [
    ("red", 0),
    ("yellow", 60),
    ("green", 120),
]
HUE_TOLERANCE = 35  # degrees; widen/narrow after checking real samples

def classify_colour(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if v < BLACK_MAX_VALUE:
        return "black"
    if s < COLOUR_MIN_SATURATION:
        return "floor"  # grey/white/unsaturated - not a marker
    hue_deg = h * 360
    best_label, best_dist = "unknown", 999
    for label, ref_hue in HUE_BUCKETS:
        dist = min(abs(hue_deg - ref_hue), 360 - abs(hue_deg - ref_hue))  # wraparound-aware
        if dist < best_dist:
            best_label, best_dist = label, dist
    return best_label if best_dist <= HUE_TOLERANCE else "unknown"

# LiDAR: winglander_v2.json's "lidar" component is generated with a full
# 360-degree fieldOfView (see ProtoGenerator.py). Read one horizontal layer
# and sample it every 30 degrees, labelled like a clock face.
lidar = robot.getDevice("lidar")
lidar.enable(TIME_STEP)
LIDAR_RESOLUTION = lidar.getHorizontalResolution()
LIDAR_LAYERS = lidar.getNumberOfLayers()
print("LIDAR_LAYERS=",LIDAR_LAYERS)
LIDAR_LAYER = LIDAR_LAYERS // 2  # a near-horizontal layer (default vertical FOV is small)

# Calibrated empirically with three independent single-wall tests (far more
# reliable than reasoning about Webots' internal sweep convention from
# docs alone, which led to two wrong guesses before this):
#   - wall at true front (0)         -> was showing at radar hour 6
#   - wall at true right (3 o'clock) -> was showing at radar hour 3
#   - wall at true behind (6 o'clock)-> was showing at radar hour 0
# All three are consistent with a single simple rule: raw LiDAR array index
# 0 IS true straight-ahead, and index increases clockwise with no offset
# (true_bearing_hour = index * 12 / horizontal_resolution). So the index for
# a desired display hour h is just h * resolution / 12 - no forward-index
# offset, no direction flip.
LIDAR_FORWARD_INDEX = 0
LIDAR_CLOCKWISE = True
CLOCK_HOURS = list(range(12))  # 0 = 12 o'clock (front), 1..11 clockwise from there
LIDAR_MAX_RANGE = lidar.getMaxRange()

# The radar diagram's outer rim represents this distance, not the sensor's
# full LIDAR_MAX_RANGE (typically 1m) - real readings in this maze cluster
# within a few centimeters of the robot, so scaling against the full range
# left every dot bunched near the center. Readings at or beyond this are
# still real detections (drawn+connected), just capped at the rim.
LIDAR_RADAR_SCALE_M = 0.075  # 75cm


def lidar_reading_at_hour(range_image, hour):
    angle_deg = hour * 30
    steps = round(angle_deg / 360 * LIDAR_RESOLUTION)
    if LIDAR_CLOCKWISE:
        index = (LIDAR_FORWARD_INDEX + steps) % LIDAR_RESOLUTION
    else:
        index = (LIDAR_FORWARD_INDEX - steps) % LIDAR_RESOLUTION
    return range_image[index]


def draw_lidar_clock(screen, font, small_font, center, radius, range_image):
    """Draws readings arranged on a clock face: 12 at top (straight ahead),
    going clockwise, matching the physical layout the hour labels refer to.
    A radar-style polygon connects only hours with an actual detection
    (capped at LIDAR_MAX_RANGE for what counts as "no detection", but scaled
    for drawing against LIDAR_RADAR_SCALE_M, since real readings cluster
    within a few centimeters and get lost near the center if scaled against
    the sensor's full 1m max range) - hours reading "open" (no detection)
    get no point and no connecting line, rather than being drawn out at the
    rim as if a wall were there. Values are shown in millimeters, matching
    the LiDAR's underlying precision (Webots' default Lidar has no distance
    quantization - the "resolution" field is -1, i.e. unlimited)."""
    pygame.draw.circle(screen, LABEL_COLOR, center, radius, 1)
    pygame.draw.circle(screen, LABEL_COLOR, center, radius // 2, 1)

    points = [None] * 12  # None where there's no detection, else (px, py)
    for hour in CLOCK_HOURS:
        angle = math.radians(hour * 30)
        reading = lidar_reading_at_hour(range_image, hour)
        no_detection = reading == float("inf") or reading > LIDAR_MAX_RANGE

        if not no_detection:
            r_px = min(reading, LIDAR_RADAR_SCALE_M) / LIDAR_RADAR_SCALE_M * radius
            px = center[0] + r_px * math.sin(angle)
            py = center[1] - r_px * math.cos(angle)
            points[hour] = (px, py)

        clock_label = "12" if hour == 0 else str(hour)
        value_text = "-" if no_detection else f"{reading * 1000:.0f}cm"
        label_pos = (
            center[0] + (radius + 22) * math.sin(angle),
            center[1] - (radius + 22) * math.cos(angle),
        )
        label_surf = small_font.render(f"{clock_label}:{value_text}", True, LABEL_COLOR)
        screen.blit(label_surf, label_surf.get_rect(center=label_pos))

    # Connect only consecutive hours that both have a real detection, so a
    # gap in coverage shows as a gap in the polygon, not a false wall.
    for hour in CLOCK_HOURS:
        a, b = points[hour], points[(hour + 1) % 12]
        if a is not None and b is not None:
            pygame.draw.aaline(screen, TEXT_COLOR, a, b)
    for point in points:
        if point is not None:
            pygame.draw.circle(screen, TEXT_COLOR, (round(point[0]), round(point[1])), 3)

    # Robot marker at center, small triangle pointing "forward" (12 o'clock).
    pygame.draw.polygon(
        screen,
        (255, 255, 255),
        [(center[0], center[1] - 6), (center[0] - 4, center[1] + 4), (center[0] + 4, center[1] + 4)],
    )


# Fit the camera feed into a fixed-size box regardless of native resolution,
# so bumping the camera's resolution in winglander_v2.json doesn't blow up
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

# winglander_v2.json includes a GPS component named "gps".
GPS_DEVICE_NAME = "gps"
gps = robot.getDevice(GPS_DEVICE_NAME)
if gps is not None:
    gps.enable(TIME_STEP)

# winglander_v2.json includes an IMU (InertialUnit) component named
# "inertial_unit". getRollPitchYaw() returns radians; displayed in degrees.
imu = robot.getDevice("inertial_unit")
if imu is not None:
    imu.enable(TIME_STEP)


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
small_font = pygame.font.SysFont("monospace", 13)

TOP_CONTENT_HEIGHT = 660
# Extra headroom so the type dropdown's open option list (7 entries) never
# overlaps the report button/status line below it.
BOTTOM_PANEL_HEIGHT = 170 + Dropdown.OPTION_HEIGHT * 7

window_width = max(cam_display_width + PANEL_WIDTH + MARGIN * 3, 600)
window_height = max(cam_display_height, TOP_CONTENT_HEIGHT) + BOTTOM_PANEL_HEIGHT + MARGIN * 3
screen = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("winglander_v2 - WASD to drive")
clock = pygame.time.Clock()

panel_x = cam_display_width + MARGIN * 2

# --- Manual/autonomous mode toggle, top of the right column ---
autonomous_mode = False
mode_button = Button((panel_x, MARGIN, PANEL_WIDTH, 28), "")


def mode_button_label():
    return "Mode: AUTONOMOUS (click)" if autonomous_mode else "Mode: MANUAL (click)"


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
state = "forward"

while running and robot.step(TIME_STEP) != -1:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if mode_button.handle_event(event):
            autonomous_mode = not autonomous_mode

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

    # --- Sense: read every sensor once per step. Both the drive logic
    # below and the render section further down reuse these same values -
    # neither re-reads a device that's already been read this step. ---
    image_bytes = camera.getImage()
    lidar_range_image = lidar.getLayerRangeImage(LIDAR_LAYER)
    colour_image = colour_sensor.getImage()

    roll = pitch = yaw = None
    if imu is not None:
        roll, pitch, yaw = imu.getRollPitchYaw()

    gps_x = gps_y = gps_z = None
    if gps is not None:
        gps_x, gps_y, gps_z = gps.getValues()

    # Wheel motion telemetry: measured velocity is derived from the change
    # in encoder position since the previous step, not just echoing back
    # the commanded speed set below.
    wheel1_pos = wheel1_sensor.getValue()
    wheel2_pos = wheel2_sensor.getValue()
    wheel1_vel = 0.0 if wheel1_prev_pos is None else (wheel1_pos - wheel1_prev_pos) / DT
    wheel2_vel = 0.0 if wheel2_prev_pos is None else (wheel2_pos - wheel2_prev_pos) / DT
    wheel1_prev_pos = wheel1_pos
    wheel2_prev_pos = wheel2_pos

    # --- Decide: drive logic, using the sensor values read just above ---
    left_speed = 0.0
    right_speed = 0.0


    if autonomous_mode:
        # ================================================================
        # AUTONOMOUS MODE - ADD YOUR OWN CONTROL CODE BELOW THIS LINE.
        #
        # Runs every simulation step (every TIME_STEP ms) while autonomous
        # mode is enabled (toggle button, top of the right-hand panel).
        # WASD is ignored entirely in this branch.
        #
        # Already read this step by the "Sense" block just above - use
        # these directly, no need to call the device getters again:
        #   lidar_range_image - pass to lidar_reading_at_hour(lidar_range_image,
        #       hour) for a clock-style reading (0 = straight ahead,
        #       clockwise - see that function and the LIDAR_* constants
        #       above for the calibrated mapping)
        #   roll, pitch, yaw - radians (None if no IMU device found)
        #   gps_x, gps_y, gps_z - meters (None if no GPS device found)
        #   colour_image - pass to Camera.imageGetRed/Green/Blue(colour_image, 1, 0, 0)
        #   image_bytes - raw BGRA camera frame (cam_width x cam_height)
        #   wheel1_pos, wheel2_pos - wheel encoder positions, radians
        #
        # Set left_speed/right_speed (rad/s) below - they get clamped to
        # +/-MAX_SPEED and applied to the wheels right after this block,
        # same as manual mode:
        #   left_speed  -> wheel2 (left wheel)
        #   right_speed -> wheel1 (right wheel)



        if state == "forward":
            left_speed = MAX_SPEED
            right_speed = MAX_SPEED

        if state == "stop":
            left_speed = 0.0
            right_speed = 0.0

        wheel1.setVelocity(left_speed)
        wheel2.setVelocity(right_speed)


        if colour_image:
            r = Camera.imageGetRed(colour_image, 1, 0, 0)
            g = Camera.imageGetGreen(colour_image, 1, 0, 0)
            b = Camera.imageGetBlue(colour_image, 1, 0, 0)
        else:
            print("No colour sensor reading")
        #h,s,v = colorsys.rgb_to_hls(r / 255 ,g /255 ,b / 255)
        colour_name = classify_colour(r, g, b)
        print(colour_name)
        if colour_name == "black":
            state = "stop"


        # ================================================================
        # END AUTONOMOUS MODE - YOUR CONTROL CODE ABOVE THIS LINE.
        # ================================================================
    elif not typing:
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

    # --- Act: clamp and apply to the wheels ---
    left_speed = max(-MAX_SPEED, min(MAX_SPEED, left_speed))
    right_speed = max(-MAX_SPEED, min(MAX_SPEED, right_speed))
    wheel2.setVelocity(left_speed)
    wheel1.setVelocity(right_speed)

    # --- Render (reuses the sensor values read in the "Sense" step above -
    # nothing here re-fetches a device) ---
    screen.fill(BG_COLOR)

    if image_bytes:
        cam_surface = pygame.image.frombuffer(image_bytes, (cam_width, cam_height), "BGRA")
        cam_surface = pygame.transform.scale(cam_surface, (cam_display_width, cam_display_height))
        screen.blit(cam_surface, (MARGIN, MARGIN))

    # --- Left column: camera above, LiDAR clock below ---
    left_y = MARGIN + cam_display_height + 16
    screen.blit(font.render("LiDAR (m), clock from front:", True, LABEL_COLOR), (MARGIN, left_y))
    left_y += 24
    lidar_clock_radius = 76
    lidar_label_margin = 30  # radial space beyond the circle for "hour:value" text
    lidar_clock_center = (MARGIN + cam_display_width // 2, left_y + lidar_clock_radius + lidar_label_margin)
    draw_lidar_clock(screen, font, small_font, lidar_clock_center, lidar_clock_radius, lidar_range_image)
    left_y += 2 * (lidar_clock_radius + lidar_label_margin) + 10

    # --- Right column: mode toggle, then everything else ---
    mode_button.label = mode_button_label()
    mode_button.draw(screen, small_font)
    y = MARGIN + 28 + 12
    screen.blit(font.render("Wheel motion:", True, LABEL_COLOR), (panel_x, y))
    y += 24
    for label, pos, vel, cmd in (
        ("wheel1 (R)", wheel1_pos, wheel1_vel, right_speed),
        ("wheel2 (L)", wheel2_pos, wheel2_vel, left_speed),
    ):
        line = f"{label}: {pos:6.2f} rad  {vel:6.2f} rad/s (cmd {cmd:.2f})"
        screen.blit(font.render(line, True, TEXT_COLOR), (panel_x, y))
        y += 20

    y += 16
    screen.blit(font.render("IMU (roll/pitch/yaw, deg):", True, LABEL_COLOR), (panel_x, y))
    y += 24
    if imu is not None:
        line = (
            f"r{math.degrees(roll):6.1f} p{math.degrees(pitch):6.1f} y{math.degrees(yaw):6.1f}"
        )
        screen.blit(font.render(line, True, TEXT_COLOR), (panel_x, y))
    else:
        screen.blit(font.render("(not found)", True, TEXT_COLOR), (panel_x, y))
    y += 22

    y += 16
    screen.blit(font.render("GPS (x, y, z), meters:", True, LABEL_COLOR), (panel_x, y))
    y += 24
    if gps is not None:
        line = f"x{gps_x:6.3f} y{gps_y:6.3f} z{gps_z:6.3f}"
        screen.blit(font.render(line, True, TEXT_COLOR), (panel_x, y))
    else:
        screen.blit(font.render("(not found)", True, TEXT_COLOR), (panel_x, y))
    y += 22

    y += 16
    screen.blit(font.render("Colour sensor (RGB):", True, LABEL_COLOR), (panel_x, y))
    y += 24
    if colour_image:
        r = Camera.imageGetRed(colour_image, 1, 0, 0)
        g = Camera.imageGetGreen(colour_image, 1, 0, 0)
        b = Camera.imageGetBlue(colour_image, 1, 0, 0)
        screen.blit(font.render(f"({r}, {g}, {b})", True, TEXT_COLOR), (panel_x, y))
        y += 22
        swatch_rect = pygame.Rect(panel_x, y, 40, 20)
        pygame.draw.rect(screen, (r, g, b), swatch_rect)
        pygame.draw.rect(screen, LABEL_COLOR, swatch_rect, 1)
        detected_label = classify_colour(r, g, b)
        screen.blit(font.render(detected_label, True, TEXT_COLOR), (panel_x + 50, y + 2))
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
