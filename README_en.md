# Matrix:bit (ESP32) — Pinout and Features via MicroPython

Documentation of the real pinout for the **Matrix:bit** board (a micro:bit-style clone built around an ESP32), obtained through **hardware reverse engineering/scanning**, since the manufacturer provides no public datasheet and the printed pinout diagram uses a virtual numbering scheme (`P0`-`P28`) that **does not correspond directly to the ESP32's real GPIOs**.

All code here runs on **generic MicroPython for ESP32** (it does not rely on any proprietary manufacturer library).

> ⚠️ **These pins were physically confirmed on one specific unit.** If you have a different board revision, test before trusting them blindly — see the [Discovery Methodology](#discovery-methodology) section.

---

## Table of Contents

- [Pin Summary](#pin-summary)
- [Prerequisites](#prerequisites)
- [OLED Display (SSD1306)](#oled-display-ssd1306)
- [Accelerometer / Gyroscope (QMI8658)](#accelerometer--gyroscope-qmi8658)
- [Magnetometer / Compass (MMC5983MA)](#magnetometer--compass-mmc5983ma)
- [Physical Buttons A and B](#physical-buttons-a-and-b)
- [Touch Pads (P Y T H O N)](#touch-pads-p-y-t-h-o-n)
- [RGB LEDs (NeoPixel)](#rgb-leds-neopixel)
- [Buzzer](#buzzer)
- [Light Sensor](#light-sensor)
- [Microphone](#microphone)
- [Full Example Script](#full-example-script)
- [Discovery Methodology](#discovery-methodology)

---

## Pin Summary

| Feature | GPIO(s) | Bus/Type | I2C Address |
|---|---|---|---|
| OLED display | 22 (SCL), 23 (SDA) | I2C0 | `0x3C` |
| Accelerometer/Gyroscope | 22 (SCL), 23 (SDA) | I2C0 (QMI8658) | `0x6B` |
| Magnetometer/Compass | 22 (SCL), 23 (SDA) | I2C0 (MMC5983MA) | `0x30` |
| Button A | 0 | Digital IN (pull-up) | — |
| Button B | 2 | Digital IN (pull-up) | — |
| Touch **P** | 33 | Touch (capacitive) | — |
| Touch **Y** | 14 | Touch (capacitive) | — |
| Touch **T** | 12 | Touch (capacitive) | — |
| Touch **H** | 13 | Touch (capacitive) | — |
| Touch **O** | 15 | Touch (capacitive) | — |
| Touch **N** | 4 | Touch (capacitive) | — |
| RGB LED (x3, chained) | 17 | NeoPixel (single wire) | — |
| Buzzer | 16 | PWM | — |
| Light sensor | 39 | ADC1 | — |
| Microphone | 36 | ADC1 | — |

**Single I2C bus:** all three I2C devices (display, accelerometer/gyroscope, magnetometer) share the same bus on `SCL=22` / `SDA=23`.

---

## Prerequisites

The `ssd1306.py` driver is **not built into generic MicroPython** — it needs to be copied manually onto the board (as a separate file, at the root of the filesystem):

```python
# Official MicroPython driver, available at:
# https://github.com/micropython/micropython-lib/tree/master/micropython/drivers/display/ssd1306
```

All examples below assume the I2C bus was already created like this:

```python
from machine import Pin, I2C

i2c = I2C(0, scl=Pin(22), sda=Pin(23), freq=400000)
```

---

## OLED Display (SSD1306)

- **Resolution:** 128x64
- **I2C address:** `0x3C`

```python
import ssd1306

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3c)

oled.fill(0)
oled.text("Hello, world!", 0, 0)
oled.show()
```

---

## Accelerometer / Gyroscope (QMI8658)

- **I2C address:** `0x6B`
- **Ranges configured in this example:** accelerometer ±8g, gyroscope ±256°/s

```python
import struct
import time

QMI_ADDR = 0x6b

def qmi_init():
    i2c.writeto_mem(QMI_ADDR, 0x02, bytes([0x60]))  # CTRL1
    i2c.writeto_mem(QMI_ADDR, 0x03, bytes([0x23]))  # CTRL2: accel +-8g
    i2c.writeto_mem(QMI_ADDR, 0x04, bytes([0x43]))  # CTRL3: gyro +-256dps
    i2c.writeto_mem(QMI_ADDR, 0x08, bytes([0x03]))  # CTRL7: enable accel+gyro
    time.sleep_ms(10)

def qmi_read():
    data = i2c.readfrom_mem(QMI_ADDR, 0x35, 12)
    ax, ay, az, gx, gy, gz = struct.unpack('<6h', data)
    accel_g = (ax / 4096, ay / 4096, az / 4096)     # in g
    gyro_dps = (gx / 128, gy / 128, gz / 128)        # in degrees/s
    return accel_g, gyro_dps

qmi_init()
accel, gyro = qmi_read()
print("Accel (g):", accel)
print("Gyro (dps):", gyro)
```

---

## Magnetometer / Compass (MMC5983MA)

- **I2C address:** `0x30`
- **Expected Product ID at register `0x2F`:** `0x30` (use this to confirm communication)

> ⚠️ **Important:** this sensor can saturate (getting "stuck" on one axis) when exposed to strong magnetic fields — including the board's own buzzer/speaker. You need to apply a **RESET pulse** periodically (every few seconds) to realign the internal magnetic domains and keep readings reliable.

```python
import math
import time

MMC_ADDR = 0x30
MMC_REG_CTRL0 = 0x09
MMC_REG_STATUS = 0x08
MMC_REG_XOUT0 = 0x00

def mmc_reset():
    # Realigns the internal magnetic domains - call this periodically
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x10]))
    time.sleep_ms(5)

def mmc_read():
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x01]))  # trigger measurement (TM_M)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 50:
        if i2c.readfrom_mem(MMC_ADDR, MMC_REG_STATUS, 1)[0] & 0x01:
            break
        time.sleep_ms(1)

    data = i2c.readfrom_mem(MMC_ADDR, MMC_REG_XOUT0, 7)
    x = (data[0] << 10) | (data[1] << 2) | ((data[6] & 0xC0) >> 6)
    y = (data[2] << 10) | (data[3] << 2) | ((data[6] & 0x30) >> 4)
    z = (data[4] << 10) | (data[5] << 2) | ((data[6] & 0x0C) >> 2)
    # Centered on 131072 (zero field, 18-bit), ~16384 counts/Gauss
    return (x - 131072) / 16384, (y - 131072) / 16384, (z - 131072) / 16384

mmc_reset()
gx, gy, gz = mmc_read()
heading = math.degrees(math.atan2(gy, gx))
if heading < 0:
    heading += 360
print("Approximate heading: %.1f degrees" % heading)
```

**Note on accuracy:** the calculated `heading` is an uncalibrated approximation with no tilt compensation — it works reasonably well with the board held flat, but it is not an industrial-precision compass.

---

## Physical Buttons A and B

- **Button A:** GPIO 0
- **Button B:** GPIO 2
- Both use internal pull-ups; pressed = `LOW` (`0`)

```python
from machine import Pin

btn_a = Pin(0, Pin.IN, Pin.PULL_UP)
btn_b = Pin(2, Pin.IN, Pin.PULL_UP)

if btn_a.value() == 0:
    print("Button A pressed")
if btn_b.value() == 0:
    print("Button B pressed")
```

---

## Touch Pads (P Y T H O N)

Six capacitive touch pads on the bottom of the board, spelling out "PYTHON".

| Letter | GPIO |
|---|---|
| P | 33 |
| Y | 14 |
| T | 12 |
| H | 13 |
| O | 15 |
| N | 4 |

> ⚠️ GPIO 33 also shows up as a candidate in light-sensor/ADC tests due to capacitive interference from nearby touch — if you're using ADC on nearby pins, avoid touching the board while reading.

```python
from machine import Pin, TouchPad

touch_pins = {'P': 33, 'Y': 14, 'T': 12, 'H': 13, 'O': 15, 'N': 4}
touchpads = {letter: TouchPad(Pin(gpio)) for letter, gpio in touch_pins.items()}

# Simple calibration: baseline reading without touching
baseline = {letter: t.read() for letter, t in touchpads.items()}

def touched_letter():
    for letter, t in touchpads.items():
        if t.read() < baseline[letter] * 0.6:
            return letter
    return None

print(touched_letter())
```

---

## RGB LEDs (NeoPixel)

- **GPIO:** 17
- **Count:** 3 addressable LEDs **chained on the same pin** (not 3 separate pins)

```python
from machine import Pin
import neopixel

NUM_PIXELS = 3
np = neopixel.NeoPixel(Pin(17), NUM_PIXELS)

def set_color(r, g, b):
    for i in range(NUM_PIXELS):
        np[i] = (r, g, b)
    np.write()

set_color(80, 0, 0)  # red on all 3 LEDs
```

---

## Buzzer

- **GPIO:** 16
- **Type:** PWM-driven (simple tone)

```python
from machine import Pin, PWM
import time

buzzer = PWM(Pin(16), freq=1000, duty=0)

def beep(ms=100, freq=1000):
    buzzer.freq(freq)
    buzzer.duty(512)
    time.sleep_ms(ms)
    buzzer.duty(0)

beep(100, 1500)
```

---

## Light Sensor

- **GPIO:** 39 (ADC1 — reliable even with WiFi active)

```python
from machine import Pin, ADC

light_sensor = ADC(Pin(39))
light_sensor.atten(ADC.ATTN_11DB)  # full reading range

print("Light:", light_sensor.read())  # higher value = more light
```

---

## Microphone

- **GPIO:** 36 (ADC1)
- Since this is an audio signal, what matters is the **fast oscillation amplitude**, not a fixed value

```python
from machine import Pin, ADC

mic = ADC(Pin(36))
mic.atten(ADC.ATTN_11DB)

def sound_level(samples=20):
    vmin, vmax = 99999, -99999
    for _ in range(samples):
        val = mic.read()
        vmin = min(vmin, val)
        vmax = max(vmax, val)
    return vmax - vmin

print("Sound level:", sound_level())
```

---

## Full Example Script

A complete example combining all of the features above (buttons, touch, LEDs, buzzer, accelerometer, light, microphone, and a graphical compass) is available in [`matrixbit_completo.py`](./matrixbit_completo.py).

---

## Discovery Methodology

Since there was no public datasheet or schematic for the board, every pin was identified through **empirical scanning and physical testing**:

1. **I2C:** brute-force scan of every valid GPIO pair using `SoftI2C`, looking for plausible responses (a handful of addresses, not the entire range — responses covering 100+ addresses indicate a floating/noisy bus, not a real device).
2. **Buttons/touch/digital pins:** simultaneous reading of multiple candidate GPIOs while physically pressing each button/touching each pad, watching for which pin reacts.
3. **LED/Buzzer:** sequential pin-by-pin sweep, driving a digital output or PWM signal and observing/listening for the physical reaction.
4. **Analog sensors (light/mic):** continuous reading of every ADC1 pin (more reliable than ADC2, which conflicts with the WiFi radio), identifying which pin varies when covering the sensor (light) or making noise (microphone — in this case measuring oscillation amplitude rather than an absolute value).
5. **I2C chip identification:** done by reading identification registers (Product ID / WHO_AM_I) and comparing them against public datasheets for the most likely candidates, based on the set of sensors visible in the board's silkscreen (accelerometer, gyroscope, magnetometer).

This process is replicable on any undocumented board — the scanning scripts used during discovery remain in the repository for reference.
