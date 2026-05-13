from machine import I2C, Pin
import time

MOTORA = 0
MOTORB = 1
MOTORC = 2
MOTORD = 3

CLOCKWISE = 0
ANTICLOCKWISE = 1

ADDR = 0x20


class QuadMotorDriver:
    def __init__(self, scl=1, sda=0):
        self.i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=100000)
        self._direction = 0x00
        self.stop()

    def _write(self, value):
        self.i2c.writeto(ADDR, bytes([value]))

    def rotate(self, direction, motor_id):
        new_val = 0x02 if direction == CLOCKWISE else 0x01
        shift = motor_id * 2
        mask = ~(0x03 << shift) & 0xFF
        self._direction = (self._direction & mask) | (new_val << shift)
        self._write(self._direction)

    def stop(self, motor_id=None):
        if motor_id is None:
            self._direction = 0x00
        else:
            shift = motor_id * 2
            mask = ~(0x03 << shift) & 0xFF
            self._direction &= mask
        self._write(self._direction)

    def go_forward(self):
        self.rotate(ANTICLOCKWISE, MOTORA)
        self.rotate(CLOCKWISE,     MOTORB)
        self.rotate(CLOCKWISE,     MOTORC)
        self.rotate(ANTICLOCKWISE, MOTORD)

    def go_backward(self):
        self.rotate(CLOCKWISE,     MOTORA)
        self.rotate(ANTICLOCKWISE, MOTORB)
        self.rotate(ANTICLOCKWISE, MOTORC)
        self.rotate(CLOCKWISE,     MOTORD)

    def turn_left(self, duration=0.4):
        # Nieuwe voorkant = oude achterkant; links/rechts wisselen mee
        # _ALL_FWD = A=ACW, B=CW, C=CW, D=ACW → 0x69
        # _OUTER_L = B=CW, C=CW, A=stop, D=stop → 0x28  (binnenkant A,D op 80%)
        # 80% duty: 8ms aan / 2ms uit @ 100Hz
        _ALL_FWD = 0x69
        _OUTER_L = 0x28
        end = time.ticks_add(time.ticks_ms(), int(duration * 1000))
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            self._write(_ALL_FWD)
            time.sleep_ms(8)
            self._write(_OUTER_L)
            time.sleep_ms(2)
        self._direction = _ALL_FWD
        self._write(_ALL_FWD)

    def turn_right(self, duration=0.4):
        # _ALL_FWD = A=ACW, B=CW, C=CW, D=ACW → 0x69
        # _OUTER_R = A=ACW, D=ACW, B=stop, C=stop → 0x41  (binnenkant B,C op 80%)
        # 80% duty: 8ms aan / 2ms uit @ 100Hz
        _ALL_FWD = 0x69
        _OUTER_R = 0x41
        end = time.ticks_add(time.ticks_ms(), int(duration * 1000))
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            self._write(_ALL_FWD)
            time.sleep_ms(8)
            self._write(_OUTER_R)
            time.sleep_ms(2)
        self._direction = _ALL_FWD
        self._write(_ALL_FWD)
