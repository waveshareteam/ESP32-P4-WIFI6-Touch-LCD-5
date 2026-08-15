# Arduino Examples

Arduino sketches and bundled libraries for the Waveshare ESP32-P4-WIFI6-Touch-LCD-5
(720 × 1280 MIPI-DSI IPS display, GT911 capacitive touch, OV5647 MIPI-CSI camera).

## Board settings (Arduino IDE)

- Arduino-ESP32 core `3.3.11` (or newer 3.x).
- Board: `ESP32P4 Dev Module` (`esp32:esp32:esp32p4`).
- Menu options:
  - `Chip Variant`: `Before v3.00` (rev 1.3 boards)
  - `PSRAM`: `Enabled`
  - `Flash Size`: `32 MB`
  - `Flash Mode`: `QIO`
  - `Flash Frequency`: `80 MHz`
  - `Partition Scheme`: `13M APP / 7M data (32 MB)`
  - `Upload Mode`: `Default (USB-UART bridge)`
- Enable PSRAM in the board settings; the display sketches require it.

## Examples

| Sketch | Description |
| --- | --- |
| `01_HelloWorld` | Minimal Arduino_GFX DSI display bring-up |
| `02_AsciiTable` | Arduino_GFX capability/benchmark table |
| `03_Drawing_board` | GT911 five-point capacitive touch drawing |
| `04_LVGLV9_Arduino` | LVGL 9 widgets UI with touch input |
| `05_GFX_ESPWiFiAnalyzer` | Graphical Wi-Fi scan (on-board ESP32-C6 coprocessor) |
| `09_Audio_Playback` | ES8311 codec I2S tone playback (experimental) |
| `08_SD_Card` | microSD read/write over the SDIO 3.0 slot |
| `06_Camera_Preview` | OV5647 MIPI-CSI camera preview on the display |
| `07_Camera_ISP_Tuning` | Live preview with interactive ISP/3A tuning over serial |

## Camera notes

The `06_Camera_Preview` and `07_Camera_ISP_Tuning` sketches use the `ESP_Video` library
bundled with the Arduino-ESP32 core (MIPI-CSI device). An OV5647 module must be
connected to the board MIPI-CSI connector. The default sensor mode streams RAW8
frames which the ISP pipeline converts to RGB565 for the display. `07_Camera_ISP_Tuning`
adds interactive controls over the serial monitor: `g` gain, `e` exposure (µs),
`a` AE target level, `v/h` flip, `t` test pattern, `s` status.

## Bundled libraries

- `displays/` — board display/touch/I2C configuration and drivers (HX8394 DSI init,
  GT911 touch, non-blocking serial log)
- `GFX_Library_for_Arduino` — Arduino_GFX with ESP32-P4 MIPI-DSI panel support
- `lvgl` + `lv_conf.h` — LVGL 9 for the `04_LVGLV9_Arduino` sketch

See the [main README](../README.md) and the [official product documentation]
(https://docs.waveshare.com/ESP32-P4-WIFI6-Touch-LCD-5) for hardware details.
