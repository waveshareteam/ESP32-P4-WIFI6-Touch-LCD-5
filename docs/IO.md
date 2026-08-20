[简体中文](IO_ZH.md) · [Documentation index](README.md)

# ESP32-P4-WIFI6-Touch-LCD-5 I/O list

This page is a repository-maintained I/O reference cross-checked against the
LCD-5 BSP source and the included schematic. It is not a replacement for the
official product manual and does not claim that every interface has completed
hardware-in-the-loop validation.

## Confirmed board mappings

| Function | Mapping | Evidence / notes |
|---|---|---|
| Board I2C SDA | GPIO7 | Shared board I2C bus; used by codec and GT911 |
| Board I2C SCL | GPIO8 | Shared board I2C bus; used by codec and GT911 |
| LCD backlight | GPIO26 | LEDC PWM, 5 kHz, 10-bit |
| LCD reset | GPIO27 | HX8394 MIPI-DSI panel reset |
| LCD | 720 × 1280, 2-lane MIPI-DSI | HX8394, 700 Mbit/s lane rate |
| I2S MCLK | GPIO13 | ES8311 / ES7210 audio bus |
| I2S BCLK | GPIO12 | ES8311 / ES7210 audio bus |
| I2S LRCK / WS | GPIO10 | ES8311 / ES7210 audio bus |
| I2S DOUT | GPIO9 | ES8311 playback |
| I2S DIN | GPIO11 | ES7210 capture |
| Speaker amplifier enable | GPIO53 | Active-high board amplifier control |
| microSD D0..D3 | GPIO39..GPIO42 | 4-bit SDMMC |
| microSD CMD | GPIO44 | SDMMC command |
| microSD CLK | GPIO43 | SDMMC clock |

## I2C devices

The board I2C bus uses GPIO7/GPIO8. The relevant device addresses currently
used by the repository are:

| Device | Address | Note |
|---|---:|---|
| GT911 touch | `0x5D` or `0x14` | The controller selects its address from the INT level during reset. The Arduino example probes both addresses. |
| ES8311 codec | `0x18` | Codec configuration address |
| ES7210 codec | `0x40` | Microphone codec address |

The schematic routes `TP_RST` through R37 (0 ohm) to GPIO23. It routes `TP_INT`
through the optional R108 (`NC/0R`) footprint to GPIO2, so the interrupt path
depends on the assembled resistor population. The repository driver and BSP
currently leave both pins as `GPIO_NUM_NC`; the Arduino driver therefore probes
both legal GT911 addresses instead of claiming active reset/interrupt control.

## Other interfaces

- The ESP32-C6 is the board's hosted Wi-Fi/Bluetooth coprocessor. The exact
  P4-to-C6 transport pin map is intentionally not repeated here until it is
  fully cross-checked against the schematic and matching slave firmware.
- The OV5647 camera uses the MIPI-CSI connector and differential interface;
  this page does not invent a separate camera GPIO list.
- USB-to-UART, USB OTG, and the 40-pin expansion header are connector-level
  interfaces. Consult the schematic and official manual before assigning
  application GPIOs.

## Revision note

ESP32-P4 rev1.3 and rev3.x use different silicon profiles. The board I/O map
above is unchanged; revision-specific CPU, PSRAM, and MIPI-DSI clock settings
are described in the repository CI and firmware documentation.
