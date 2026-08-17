[简体中文](README_ZH.md) ·
[Repository compatibility note](../../../docs/P4_C6_HOSTED_WIFI.md)

# Wi-Fi station through the onboard ESP32-C6

This first-party ESP-IDF example runs on the ESP32-P4 and uses the onboard
ESP32-C6 wireless coprocessor through Espressif hosted components.

The component ranges differ between the ESP-IDF 5.5 and 6.0 lines. Before
changing them or the C6 slave image, read the
[host/slave compatibility contract](../../../docs/P4_C6_HOSTED_WIFI.md).

Actions validates both required host build lines. Hardware validation is still
required for association, traffic, reconnect, and restart behavior.
