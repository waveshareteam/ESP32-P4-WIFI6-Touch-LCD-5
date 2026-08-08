[简体中文](HARDWARE_ZH.md) · [Documentation index](README.md)

# Schematic-backed hardware validation

This page records the repository cross-check against
[the included schematic](../schematic/ESP32-P4-WIFI6-Touch-LCD-5-Schematic.pdf).
It is a source/configuration consistency audit, not a board runtime test.

## Confirmed mappings

| Surface | Schematic evidence | Repository configuration |
| --- | --- | --- |
| LCD | 720 × 1280, 2-lane MIPI-DSI | 720 × 1280, two lanes, 700 Mbit/s lane rate |
| LCD control | Reset GPIO27, backlight GPIO26 | BSP reset GPIO27 and backlight GPIO26 |
| Board I2C | SCL GPIO8, SDA GPIO7 | BSP and I2S example use GPIO8/GPIO7 |
| Audio | MCLK13, BCLK12, LRCK10, DOUT9, DIN11, PA53 | BSP and I2S example use the same GPIOs |
| microSD | D0–D3 GPIO39–42, CMD44, CLK43 | BSP uses the same SDMMC mapping |
| Flash | GD25Q256, 256 Mbit | Product documentation states 32 MB NOR Flash |
| PSRAM | ESP32-P4NRW32 package | Product documentation states 32 MB in-package PSRAM |
| Camera | Two CSI data lanes plus differential clock | Product documentation states a 2-lane MIPI-CSI interface |

## Evidence limits

- The schematic exposes touch RST and INT nets, but the local BSP passes no GPIO
  for either signal. The repository therefore does not claim a confirmed GPIO
  mapping for those two signals.
- The schematic contains ESP32-C6 transport nets, UART, and USB signals. The
  Wi-Fi example consumes hosted components but does not define the physical C6
  transport pin map, so source-to-schematic transport mapping remains
  unconfirmed.
- The camera uses a MIPI-CSI differential interface; no separate camera GPIO
  map is claimed by the product BSP.

Compilation in Actions cannot close these evidence limits. A hardware-facing
change to display, touch, audio, SD, USB, camera, or hosted transport must be
reviewed against the applicable schematic nets and validated on the board.
