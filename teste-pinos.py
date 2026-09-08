from machine import Pin, I2C, PWM, TouchPad, ADC
import ssd1306
import neopixel
import struct
import math
import time

# ---------- Barramento I2C (display + sensores) ----------
i2c = I2C(0, scl=Pin(22), sda=Pin(23), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3c)

# ---------- Botoes fisicos ----------
btn_a = Pin(0, Pin.IN, Pin.PULL_UP)
btn_b = Pin(2, Pin.IN, Pin.PULL_UP)

# ---------- Touch pads (PYTHON) ----------
touch_pinos = {
    'P': 33,
    'Y': 14,
    'T': 12,
    'H': 13,
    'O': 15,
    'N': 4,
}
touchpads = {}
for letra, gpio in touch_pinos.items():
    try:
        touchpads[letra] = TouchPad(Pin(gpio))
    except Exception as e:
        print("Erro ao iniciar touch", letra, gpio, e)

baseline_touch = {}
for letra, t in touchpads.items():
    try:
        baseline_touch[letra] = t.read()
    except Exception:
        baseline_touch[letra] = None


def letra_tocada():
    for letra, t in touchpads.items():
        try:
            base = baseline_touch.get(letra)
            if base and t.read() < base * 0.6:
                return letra
        except Exception:
            pass
    return None


# ---------- LED RGB (3x NeoPixel em cadeia no GPIO 17) ----------
NUM_PIXELS = 3
np = neopixel.NeoPixel(Pin(17), NUM_PIXELS)


def led_cor(r, g, b):
    for i in range(NUM_PIXELS):
        np[i] = (r, g, b)
    np.write()


led_cor(0, 0, 0)

# ---------- Buzzer (PWM) ----------
buzzer = PWM(Pin(16), freq=1000, duty=0)


def beep(ms=80, freq=1000):
    buzzer.freq(freq)
    buzzer.duty(512)
    time.sleep_ms(ms)
    buzzer.duty(0)


# ---------- Sensor de luz (GPIO 39) ----------
sensor_luz = ADC(Pin(39))
try:
    sensor_luz.atten(ADC.ATTN_11DB)
except Exception:
    pass

# ---------- Microfone (GPIO 36) ----------
mic = ADC(Pin(36))
try:
    mic.atten(ADC.ATTN_11DB)
except Exception:
    pass


def nivel_som(amostras=20):
    vmin = 99999
    vmax = -99999
    for _ in range(amostras):
        try:
            val = mic.read()
        except Exception:
            continue
        if val < vmin:
            vmin = val
        if val > vmax:
            vmax = val
    return vmax - vmin


# ---------- Magnetometro / bussola MMC5983MA (0x30) ----------
MMC_ADDR = 0x30
MMC_REG_CTRL0 = 0x09
MMC_REG_STATUS = 0x08
MMC_REG_XOUT0 = 0x00


def mmc_trigger():
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x01]))  # TM_M


def mmc_wait_ready(timeout_ms=50):
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        status = i2c.readfrom_mem(MMC_ADDR, MMC_REG_STATUS, 1)[0]
        if status & 0x01:
            return True
        time.sleep_ms(1)
    return False


def mmc_reset():
    # Pulso de RESET: realinha os dominios magneticos internos.
    # Necessario periodicamente para evitar saturacao (ex: perto do buzzer).
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x10]))
    time.sleep_ms(5)


def mmc_read():
    mmc_trigger()
    mmc_wait_ready()
    data = i2c.readfrom_mem(MMC_ADDR, MMC_REG_XOUT0, 7)
    x = (data[0] << 10) | (data[1] << 2) | ((data[6] & 0xC0) >> 6)
    y = (data[2] << 10) | (data[3] << 2) | ((data[6] & 0x30) >> 4)
    z = (data[4] << 10) | (data[5] << 2) | ((data[6] & 0x0C) >> 2)
    # Centralizado em 131072 (campo zero, 18 bits), ~16384 contagens/Gauss
    gx = (x - 131072) / 16384
    gy = (y - 131072) / 16384
    gz = (z - 131072) / 16384
    return gx, gy, gz


try:
    mmc_reset()
    mmc_read()
    tem_mmc = True
except Exception as e:
    print("Erro ao iniciar MMC5983MA:", e)
    tem_mmc = False


def ang_para_xy(cx, cy, raio, angulo_graus):
    rad = math.radians(angulo_graus)
    x = cx + raio * math.sin(rad)
    y = cy - raio * math.cos(rad)
    return int(x), int(y)


def desenhar_bussola(heading_graus):
    oled.fill(0)
    cx, cy, raio = 64, 30, 24

    oled.ellipse(cx, cy, raio, raio, 1)

    # Agulha: ponta cheia aponta para o norte magnetico, cauda curta do lado oposto
    px, py = ang_para_xy(cx, cy, raio - 4, heading_graus)
    tx, ty = ang_para_xy(cx, cy, 8, heading_graus + 180)
    oled.line(cx, cy, px, py, 1)
    oled.line(cx, cy, tx, ty, 1)
    oled.fill_rect(px - 1, py - 1, 3, 3, 1)

    oled.text(str(int(heading_graus)) + " graus", 30, 56)
    oled.show()


# ---------- Acelerometro/Giroscopio QMI8658 (0x6b) ----------
QMI_ADDR = 0x6b


def qmi_init():
    i2c.writeto_mem(QMI_ADDR, 0x02, bytes([0x60]))  # CTRL1
    i2c.writeto_mem(QMI_ADDR, 0x03, bytes([0x23]))  # CTRL2: accel +-8g
    i2c.writeto_mem(QMI_ADDR, 0x04, bytes([0x43]))  # CTRL3: gyro +-256dps
    i2c.writeto_mem(QMI_ADDR, 0x08, bytes([0x03]))  # CTRL7: liga accel+gyro
    time.sleep_ms(10)


def qmi_read():
    data = i2c.readfrom_mem(QMI_ADDR, 0x35, 12)
    ax, ay, az, gx, gy, gz = struct.unpack('<6h', data)
    return (ax / 4096, ay / 4096, az / 4096), (gx / 128, gy / 128, gz / 128)


try:
    qmi_init()
    tem_qmi = True
except Exception as e:
    print("Erro ao iniciar QMI8658:", e)
    tem_qmi = False


# ---------- Loop principal ----------
estado_a_anterior = 1
estado_b_anterior = 1

pagina = 0  # 0 = sensores (texto), 1 = bussola grafica
contador_reset_mmc = 0
INTERVALO_RESET_MMC = 25  # a cada ~5s (25 * 200ms), reaplica o RESET do magnetometro

ultima_troca_pagina = time.ticks_ms()
INTERVALO_PAGINA_MS = 4000  # troca de pagina a cada 4 segundos

while True:
    a_pressionado = btn_a.value() == 0
    b_pressionado = btn_b.value() == 0
    letra = letra_tocada()

    if a_pressionado:
        led_cor(80, 0, 0)
    elif b_pressionado:
        led_cor(0, 0, 80)
    elif letra:
        led_cor(0, 80, 0)
    else:
        led_cor(0, 0, 0)

    # Troca automatica de pagina
    if time.ticks_diff(time.ticks_ms(), ultima_troca_pagina) > INTERVALO_PAGINA_MS:
        pagina = 1 - pagina
        ultima_troca_pagina = time.ticks_ms()

    if pagina == 0:
        # ---------- Pagina de sensores (texto) ----------
        linhas = []

        if a_pressionado:
            linhas.append("Botao A")
        elif b_pressionado:
            linhas.append("Botao B")
        elif letra:
            linhas.append("Touch: " + letra)
        else:
            linhas.append("Aguardando...")

        if tem_qmi:
            try:
                accel, gyro = qmi_read()
                linhas.append("Ax:%+.2f Ay:%+.2f" % (accel[0], accel[1]))
                linhas.append("Az:%+.2f" % accel[2])
            except Exception:
                linhas.append("Erro accel")

        try:
            linhas.append("Luz: " + str(sensor_luz.read()))
        except Exception:
            linhas.append("Erro luz")

        try:
            nivel = nivel_som()
        except Exception:
            nivel = 0

        oled.fill(0)
        y = 0
        for l in linhas:
            oled.text(l, 0, y)
            y += 10

        # Barra grafica de amplitude do som, na parte inferior da tela
        y_barra = 56
        altura_barra = 7
        largura_max = 128
        NIVEL_MAXIMO_ESPERADO = 300  # ajuste esse valor se a barra saturar facil ou nunca encher
        comprimento = min(int(nivel / NIVEL_MAXIMO_ESPERADO * largura_max), largura_max)
        oled.rect(0, y_barra, largura_max, altura_barra, 1)
        if comprimento > 0:
            oled.fill_rect(0, y_barra, comprimento, altura_barra, 1)

        oled.show()

    else:
        # ---------- Pagina da bussola grafica ----------
        if tem_mmc:
            try:
                if contador_reset_mmc % INTERVALO_RESET_MMC == 0:
                    mmc_reset()
                contador_reset_mmc += 1

                gx, gy, gz = mmc_read()
                heading = math.degrees(math.atan2(gy, gx))
                if heading < 0:
                    heading += 360
                desenhar_bussola(heading)
            except Exception:
                oled.fill(0)
                oled.text("Erro bussola", 0, 0)
                oled.show()

    # Bipe curto quando os botoes forem pressionados (so na borda de subida)
    if a_pressionado and estado_a_anterior == 1:
        beep(80, 1500)
    if b_pressionado and estado_b_anterior == 1:
        beep(80, 800)

    estado_a_anterior = 0 if a_pressionado else 1
    estado_b_anterior = 0 if b_pressionado else 1

    time.sleep_ms(100)
