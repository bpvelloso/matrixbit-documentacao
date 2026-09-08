# Matrix:bit (ESP32) — Pinagem e Recursos via MicroPython

Documentação da pinagem real da placa **Matrix:bit** (clone estilo micro:bit com ESP32), obtida por **engenharia reversa/varredura de hardware**, já que o fabricante não disponibiliza datasheet público e o diagrama de pinos impresso usa uma numeração virtual (`P0`-`P28`) que **não corresponde diretamente aos GPIOs reais** do ESP32.

Todo o código aqui roda em **MicroPython genérico para ESP32** (não usa nenhuma biblioteca proprietária do fabricante).

> ⚠️ **Estes pinos foram confirmados fisicamente em uma unidade específica.** Se você tem outra revisão da placa, teste antes de confiar cegamente — veja a seção [Metodologia](#metodologia-de-descoberta).

---

## Índice

- [Resumo dos pinos](#resumo-dos-pinos)
- [Pré-requisitos](#pré-requisitos)
- [Display OLED (SSD1306)](#display-oled-ssd1306)
- [Acelerômetro / Giroscópio (QMI8658)](#acelerômetro--giroscópio-qmi8658)
- [Magnetômetro / Bússola (MMC5983MA)](#magnetômetro--bússola-mmc5983ma)
- [Botões físicos A e B](#botões-físicos-a-e-b)
- [Touch pads (P Y T H O N)](#touch-pads-p-y-t-h-o-n)
- [LEDs RGB (NeoPixel)](#leds-rgb-neopixel)
- [Buzzer](#buzzer)
- [Sensor de luminosidade](#sensor-de-luminosidade)
- [Microfone](#microfone)
- [Script completo de exemplo](#script-completo-de-exemplo)
- [Metodologia de descoberta](#metodologia-de-descoberta)

---

## Resumo dos pinos

| Recurso | GPIO(s) | Barramento/Tipo | Endereço I2C |
|---|---|---|---|
| Display OLED | 22 (SCL), 23 (SDA) | I2C0 | `0x3C` |
| Acelerômetro/Giroscópio | 22 (SCL), 23 (SDA) | I2C0 (QMI8658) | `0x6B` |
| Magnetômetro/Bússola | 22 (SCL), 23 (SDA) | I2C0 (MMC5983MA) | `0x30` |
| Botão A | 0 | Digital IN (pull-up) | — |
| Botão B | 2 | Digital IN (pull-up) | — |
| Touch **P** | 33 | Touch (capacitivo) | — |
| Touch **Y** | 14 | Touch (capacitivo) | — |
| Touch **T** | 12 | Touch (capacitivo) | — |
| Touch **H** | 13 | Touch (capacitivo) | — |
| Touch **O** | 15 | Touch (capacitivo) | — |
| Touch **N** | 4 | Touch (capacitivo) | — |
| LED RGB (x3, em cadeia) | 17 | NeoPixel (1 fio) | — |
| Buzzer | 16 | PWM | — |
| Sensor de luminosidade | 39 | ADC1 | — |
| Microfone | 36 | ADC1 | — |

**Bus I2C único:** todos os três dispositivos I2C (display, accel/gyro, magnetômetro) compartilham o mesmo barramento em `SCL=22` / `SDA=23`.

---

## Pré-requisitos

O driver `ssd1306.py` **não vem embutido** no MicroPython genérico — precisa ser copiado manualmente para a placa (arquivo separado, na raiz do sistema de arquivos):

```python
# Driver oficial do MicroPython, disponível em:
# https://github.com/micropython/micropython-lib/tree/master/micropython/drivers/display/ssd1306
```

Todos os exemplos abaixo assumem que o barramento I2C já foi criado assim:

```python
from machine import Pin, I2C

i2c = I2C(0, scl=Pin(22), sda=Pin(23), freq=400000)
```

---

## Display OLED (SSD1306)

- **Resolução:** 128x64
- **Endereço I2C:** `0x3C`

```python
import ssd1306

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3c)

oled.fill(0)
oled.text("Ola, mundo!", 0, 0)
oled.show()
```

---

## Acelerômetro / Giroscópio (QMI8658)

- **Endereço I2C:** `0x6B`
- **Faixas configuradas no exemplo:** acelerômetro ±8g, giroscópio ±256°/s

```python
import struct
import time

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
    accel_g = (ax / 4096, ay / 4096, az / 4096)     # em g
    gyro_dps = (gx / 128, gy / 128, gz / 128)        # em graus/s
    return accel_g, gyro_dps

qmi_init()
accel, gyro = qmi_read()
print("Accel (g):", accel)
print("Gyro (dps):", gyro)
```

---

## Magnetômetro / Bússola (MMC5983MA)

- **Endereço I2C:** `0x30`
- **Product ID esperado no registrador `0x2F`:** `0x30` (use para confirmar comunicação)

> ⚠️ **Importante:** este sensor pode saturar (ficar "travado" em um eixo) quando exposto a campos magnéticos fortes — inclusive o do próprio buzzer/alto-falante da placa. É necessário aplicar um **pulso de RESET** periodicamente (a cada poucos segundos) para realinhar os domínios magnéticos internos e manter leituras confiáveis.

```python
import math
import time

MMC_ADDR = 0x30
MMC_REG_CTRL0 = 0x09
MMC_REG_STATUS = 0x08
MMC_REG_XOUT0 = 0x00

def mmc_reset():
    # Realinha os dominios magneticos internos - chame periodicamente
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x10]))
    time.sleep_ms(5)

def mmc_read():
    i2c.writeto_mem(MMC_ADDR, MMC_REG_CTRL0, bytes([0x01]))  # dispara medicao (TM_M)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 50:
        if i2c.readfrom_mem(MMC_ADDR, MMC_REG_STATUS, 1)[0] & 0x01:
            break
        time.sleep_ms(1)

    data = i2c.readfrom_mem(MMC_ADDR, MMC_REG_XOUT0, 7)
    x = (data[0] << 10) | (data[1] << 2) | ((data[6] & 0xC0) >> 6)
    y = (data[2] << 10) | (data[3] << 2) | ((data[6] & 0x30) >> 4)
    z = (data[4] << 10) | (data[5] << 2) | ((data[6] & 0x0C) >> 2)
    # Centralizado em 131072 (campo zero, 18 bits), ~16384 contagens/Gauss
    return (x - 131072) / 16384, (y - 131072) / 16384, (z - 131072) / 16384

mmc_reset()
gx, gy, gz = mmc_read()
heading = math.degrees(math.atan2(gy, gx))
if heading < 0:
    heading += 360
print("Heading aproximado: %.1f graus" % heading)
```

**Nota sobre precisão:** o `heading` calculado é uma aproximação sem calibração nem compensação de inclinação (tilt compensation) — funciona bem com a placa na horizontal, mas não é uma bússola de precisão industrial.

---

## Botões físicos A e B

- **Botão A:** GPIO 0
- **Botão B:** GPIO 2
- Ambos com pull-up interno; pressionado = nível `LOW` (`0`)

```python
from machine import Pin

btn_a = Pin(0, Pin.IN, Pin.PULL_UP)
btn_b = Pin(2, Pin.IN, Pin.PULL_UP)

if btn_a.value() == 0:
    print("Botao A pressionado")
if btn_b.value() == 0:
    print("Botao B pressionado")
```

---

## Touch pads (P Y T H O N)

Seis pads capacitivos na parte inferior da placa, formando a palavra "PYTHON".

| Letra | GPIO |
|---|---|
| P | 33 |
| Y | 14 |
| T | 12 |
| H | 13 |
| O | 15 |
| N | 4 |

> ⚠️ GPIO 33 também aparece como candidato em testes de sensor de luminosidade/ADC devido a interferência capacitiva por proximidade — se for usar ADC em pinos próximos, evite tocar a placa durante a leitura.

```python
from machine import Pin, TouchPad

touch_pinos = {'P': 33, 'Y': 14, 'T': 12, 'H': 13, 'O': 15, 'N': 4}
touchpads = {letra: TouchPad(Pin(gpio)) for letra, gpio in touch_pinos.items()}

# Calibracao simples: leitura de referencia sem tocar
baseline = {letra: t.read() for letra, t in touchpads.items()}

def letra_tocada():
    for letra, t in touchpads.items():
        if t.read() < baseline[letra] * 0.6:
            return letra
    return None

print(letra_tocada())
```

---

## LEDs RGB (NeoPixel)

- **GPIO:** 17
- **Quantidade:** 3 LEDs endereçáveis **em cadeia no mesmo pino** (não são 3 pinos separados)

```python
from machine import Pin
import neopixel

NUM_PIXELS = 3
np = neopixel.NeoPixel(Pin(17), NUM_PIXELS)

def led_cor(r, g, b):
    for i in range(NUM_PIXELS):
        np[i] = (r, g, b)
    np.write()

led_cor(80, 0, 0)  # vermelho nos 3 LEDs
```

---

## Buzzer

- **GPIO:** 16
- **Tipo:** controlado por PWM (tom sonoro simples)

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

## Sensor de luminosidade

- **GPIO:** 39 (ADC1 — confiável mesmo com WiFi ativo)

```python
from machine import Pin, ADC

sensor_luz = ADC(Pin(39))
sensor_luz.atten(ADC.ATTN_11DB)  # faixa completa de leitura

print("Luz:", sensor_luz.read())  # valor maior = mais luz
```

---

## Microfone

- **GPIO:** 36 (ADC1)
- Como é um sinal de áudio, o que importa é a **amplitude de variação rápida**, não um valor fixo

```python
from machine import Pin, ADC

mic = ADC(Pin(36))
mic.atten(ADC.ATTN_11DB)

def nivel_som(amostras=20):
    vmin, vmax = 99999, -99999
    for _ in range(amostras):
        val = mic.read()
        vmin = min(vmin, val)
        vmax = max(vmax, val)
    return vmax - vmin

print("Nivel de som:", nivel_som())
```

---

## Script completo de exemplo

Um exemplo integrando todos os recursos acima (botões, touch, LEDs, buzzer, acelerômetro, luz, microfone e bússola gráfica) está disponível em [`matrixbit_completo.py`](./teste-pinos.py).

---

## Metodologia de descoberta

Como não havia datasheet nem schematic público da placa, cada pino foi identificado por **varredura e teste físico empírico**:

1. **I2C:** varredura por força bruta de todos os pares de GPIO válidos usando `SoftI2C`, procurando por respostas plausíveis (poucos endereços, não a faixa toda — respostas com 100+ endereços indicam ruído de barramento flutuante, não um dispositivo real).
2. **Botões/touch/pinos digitais:** leitura simultânea de múltiplos GPIOs candidatos enquanto o usuário pressiona fisicamente cada botão/toca cada pad, observando qual pino reage.
3. **LED/Buzzer:** varredura sequencial pino a pino, acionando saída digital ou PWM e observando/ouvindo a reação física.
4. **Sensores analógicos (luz/mic):** leitura contínua de todos os pinos ADC1 (mais confiáveis que ADC2, que conflita com o rádio WiFi), identificando qual pino varia ao cobrir o sensor (luz) ou ao fazer barulho (microfone — nesse caso medindo amplitude de oscilação, não valor absoluto).
5. **Identificação de chips I2C:** feita lendo registradores de identificação (Product ID / WHO_AM_I) e comparando com datasheets públicos dos candidatos mais prováveis, dado o conjunto de sensores visíveis na serigrafia da placa (acelerômetro, giroscópio, magnetômetro).

Esse processo é replicável em qualquer placa sem documentação — os scripts de varredura usados durante a descoberta continuam no repositório para referência.
