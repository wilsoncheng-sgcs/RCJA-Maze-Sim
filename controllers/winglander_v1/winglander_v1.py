"""Webots controller for the winglander_v1 custom robot (Erebus/RCJ Maze Sim).

Drives the two wheel motors (wheel1, wheel2) using WASD keys:
    W - forward
    S - backward
    A - turn/strafe left
    D - turn/strafe right
Release all keys to stop. Press Q/ESC-equivalent isn't needed; just stop pressing keys.

Keyboard input only reaches this controller while the Webots 3D view has
focus - click into that window (not a terminal, not this file) before
pressing WASD, or nothing will happen.
"""

from controller import Robot

TIME_STEP = 32
MAX_SPEED = 6.28  # rad/s, typical Webots wheel motor max velocity

robot = Robot()

wheel1 = robot.getDevice("wheel1 motor")  # right wheel (x=260)
wheel2 = robot.getDevice("wheel2 motor")  # left wheel (x=-260)

for wheel in (wheel1, wheel2):
    wheel.setPosition(float("inf"))
    wheel.setVelocity(0.0)

keyboard = robot.getKeyboard()
keyboard.enable(TIME_STEP)

while robot.step(TIME_STEP) != -1:
    left_speed = 0.0
    right_speed = 0.0

    pressed = set()
    key = keyboard.getKey()
    while key != -1:
        pressed.add(key)
        key = keyboard.getKey()

    forward = ord("W") in pressed
    backward = ord("S") in pressed
    left = ord("A") in pressed
    right = ord("D") in pressed

    if forward:
        left_speed += MAX_SPEED
        right_speed += MAX_SPEED
    if backward:
        left_speed -= MAX_SPEED
        right_speed -= MAX_SPEED
    if left:
        left_speed -= MAX_SPEED
        right_speed += MAX_SPEED
    if right:
        left_speed += MAX_SPEED
        right_speed -= MAX_SPEED

    left_speed = max(-MAX_SPEED, min(MAX_SPEED, left_speed))
    right_speed = max(-MAX_SPEED, min(MAX_SPEED, right_speed))

    wheel2.setVelocity(left_speed)
    wheel1.setVelocity(right_speed)
