[简体中文](P4_C6_HOSTED_WIFI_ZH.md) · [Documentation index](README.md)

# ESP32-P4 and ESP32-C6 hosted Wi-Fi compatibility

The [Wi-Fi station example](../examples/esp-idf/04_wifistation/README.md) runs on
the ESP32-P4 and uses the onboard ESP32-C6 as its wireless coprocessor. The host
component line and the C6 slave firmware must remain interoperable.

## Host dependency ranges

| ESP-IDF line | esp_wifi_remote | esp_hosted |
| --- | --- | --- |
| Earlier than 6.0, including v5.5.5 | 0.14.* | 1.4.* |
| 6.0 and later, including v6.0.2 | >=1.6,<2.0 | >=2.12,<3.0 |

These ranges are declared in the example manifest and compile-validated by the
required Actions matrix. Compile success does not prove communication with
every C6 slave image.

## Firmware boundary

This repository does not currently include source or build instructions for the
onboard C6 slave firmware. They may be added in a later update. The checked-in
factory image is a separate immutable delivery artifact and is not rebuilt by
the example workflow.

When changing either host dependency range:

1. identify the exact C6 slave firmware paired with the board;
2. run both required ESP-IDF host builds;
3. validate association, IP traffic, reconnect, and restart behavior on hardware;
4. update this table only with matching host/slave evidence.

The physical P4-to-C6 transport signals are visible in the schematic, but the
example does not maintain a source-level transport pin table. Do not infer one
from another board.

## Revisit condition

When matching old and new C6 slave images, source, or build instructions become
available, validate them end to end and replace broad compatibility assumptions
with an explicit host/slave matrix.
