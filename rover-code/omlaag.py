from machine import Pin
import time

IN1 = Pin(12, Pin.OUT)
IN2 = Pin(13, Pin.OUT)
IN3 = Pin(14, Pin.OUT)
IN4 = Pin(15, Pin.OUT)

pins = [IN1, IN2, IN3, IN4]

seq = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]


def step(i):
    for j in range(4):
        pins[j].value(seq[i][j])


def rotate_down(steps=512):
    for i in range(steps):
        step(i % 8)
        time.sleep(0.005)
