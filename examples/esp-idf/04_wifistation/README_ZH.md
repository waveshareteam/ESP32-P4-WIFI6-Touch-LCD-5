[English](README.md) ·
[仓库兼容性说明](../../../docs/P4_C6_HOSTED_WIFI_ZH.md)

# 通过板载 ESP32-C6 连接 Wi-Fi Station

该第一方 ESP-IDF 示例运行在 ESP32-P4 上，并通过 Espressif Hosted 组件使用板载
ESP32-C6 无线协处理器。

ESP-IDF 5.5 与 6.0 版本线使用不同的组件范围。修改这些范围或 C6 从机镜像前，请先阅读
[主机/从机兼容性约定](../../../docs/P4_C6_HOSTED_WIFI_ZH.md)。

Actions 会验证两条必需的主机构建版本线；连接、数据传输、重连和重启行为仍需在硬件上验证。
