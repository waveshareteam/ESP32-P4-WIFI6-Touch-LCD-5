# ESP32-P4-WIFI6-Touch-LCD-5 Firmware

[中文说明](README_ZH.md)

This directory contains tested factory firmware for the ESP32-P4-WIFI6-Touch-LCD-5. Use the firmware appropriate for your product version.

## Firmware files

| File | Purpose |
| --- | --- |
| `ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261119.bin` | V1.3 factory firmware, restores the out-of-box demonstration. |
| `ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261110.bin` | V3.2 factory firmware, restores the out-of-box demonstration. |

The firmware center selects the newest date by default: `20261119` is for V1.3. For V3.2, select `20261110` instead. The two images are for different product versions.

Each factory BIN is a merged image; flash the entire file at **0x0**.

## Flashing

**Erasing Flash deletes all existing firmware, settings, and user data on the device. Back up any data you need before proceeding.**

1. Install Python and the latest esptool:

   ```sh
   python -m pip install --upgrade esptool
   ```

2. Connect the board with a USB data cable and close any serial monitor using its port.
3. Open a terminal in this `firmware/` directory. Replace `<PORT>` with the device's actual serial port, such as `COM5` on Windows or `/dev/ttyACM0` on Linux.
4. Erase the entire Flash, then write the BIN for your product version:

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> erase-flash

   ```

   For V1.3:

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> write-flash 0x0 ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261119.bin

   ```

   For V3.2:

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> write-flash 0x0 ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261110.bin
   ```

5. After flashing completes successfully, reset or power-cycle the board. Confirm that the factory demonstration starts and its functions work as expected.

If the tool cannot connect, put the board into download mode following the product's instructions, then retry.

For command details, see the [official esptool documentation](https://docs.espressif.com/projects/esptool/en/latest/esp32p4/esptool/basic-commands.html).
