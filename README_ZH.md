<div align="center">
  <h1>ESP32-P4-WIFI6-Touch-LCD-5</h1>
  <p><strong>ESP32-P4 开发板，配备 5 英寸 720 × 1280 MIPI-DSI 显示屏、电容触摸、Wi-Fi 6、音频、MIPI-CSI 摄像头接口和 USB 扩展</strong></p>
  <p>
    <a href="https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5/actions/workflows/esp-idf-examples.yml"><img alt="ESP-IDF 示例构建" src="https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5/actions/workflows/esp-idf-examples.yml/badge.svg"></a>
    <a href="LICENSE.txt"><img alt="许可证" src="https://img.shields.io/github/license/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5"></a>
  </p>
  <p>
    <a href="README.md">English</a> ·
    <a href="https://www.waveshare.net/shop/ESP32-P4-WIFI6-Touch-LCD-5.htm">🌐 产品页面</a> ·
    <a href="https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-5/">📚 产品文档</a> ·
    <a href="firmware/">📦 出厂固件</a> ·
    <a href="examples/esp-idf/">🧩 ESP-IDF 示例</a>
    <a href="examples/arduino/">🔧 Arduino 示例</a>
  </p>
  <img src="assets/ESP32-P4-WIFI6-Touch-LCD-5-details-1.jpg" alt="微雪 ESP32-P4-WIFI6-Touch-LCD-5" width="500">
</div>

---

## ✨ 概述

本仓库提供适用于微雪 ESP32-P4-WIFI6-Touch-LCD-5 的 12 个第一方 ESP-IDF
示例、出厂烧录固件和产品原理图。

该开发板集成 ESP32-P4、5 英寸竖屏触摸显示器、ESP32-C6 无线协处理器、
音频输入输出、高速 USB、microSD 存储、MIPI-CSI 摄像头接口和 40PIN 扩展接口，
适用于人机交互、多媒体、边缘计算和联网设备等应用。

## 🖥️ 硬件概览

| 功能 | 器件 / 接口 |
| --- | --- |
| MCU | ESP32-P4NRW32，双核加低功耗单核 RISC-V 处理器 |
| 存储 | 芯片封装内 32 MB PSRAM，板载 32 MB NOR Flash |
| 无线连接 | ESP32-C6-MINI-1，通过 SDIO 提供 2.4 GHz Wi-Fi 6 和 Bluetooth 5 LE |
| 显示屏 | 5 英寸 720 × 1280 IPS LCD，2-lane MIPI-DSI，HX8394 控制器 |
| 触摸 | GT911 电容触摸控制器，最多支持五点触控 |
| 音频 | ES7210 音频输入、ES8311 编解码器、双麦克风和 8 Ω / 2 W 扬声器接口 |
| 存储扩展 | microSD / TF 卡槽，使用 SDIO 3.0 |
| 摄像头 | 2-lane MIPI-CSI 接口，可选配 OV5647 摄像头 |
| USB | USB 转 UART 和 USB OTG 2.0 High Speed Type-C 接口 |
| 扩展接口 | 40PIN GPIO 接口，可兼容部分树莓派 HAT；可能需要合适的排针转接 |
| 板级支持 | LCD5 BSP 与 HX8394 组件使用临时精确上游 Git 固定版本 |
| 硬件文件 | [产品原理图](schematic/ESP32-P4-WIFI6-Touch-LCD-5-Schematic.pdf) |

完整的产品规格、接口和硬件使用说明请参阅
[官方中文文档](https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-5/)。

## 🚀 快速开始

1. 安装受支持的 ESP-IDF 版本并激活其开发环境。
2. 打开 [`examples/esp-idf/`](examples/esp-idf/) 下的任一工程。
3. 设置目标芯片，然后构建、烧录并打开串口监视器：

   ```bash
   idf.py set-target esp32p4
   idf.py build
   idf.py flash monitor
   ```

完整的环境配置、连接方法和固件烧录步骤请参阅官方产品文档。

示例默认配置选择 ESP32-P4 revision-1.3/pre-v3 配置。显示示例 07–12 临时将 LCD5 BSP 固定到
验证头 `d9a93c0`，并将 HX8394 组件源码固定到 `fc6e6d2`（上游 PR #192）；两者均会保持临时
状态，直至各自发布到 registry。独立 HX8394 默认配置会发送 I2C 命令序列，而 LCD5 BSP 为本开发板
选择跳过该行为。依赖显示行为或变更任一固定版本前，必须在目标开发板上完成 HIL 验证。

> [!NOTE]
> 无线示例使用板载 ESP32-C6 协处理器。更新任一侧时，请保持 ESP32-P4 主机组件
> 与 ESP32-C6 从机固件兼容。请参阅
> [主机/从机兼容性约定](docs/P4_C6_HOSTED_WIFI_ZH.md)。

## 🔧 Arduino 示例

仓库在 [`examples/arduino/`](examples/arduino/) 下提供 9 个 Arduino 草图,覆盖 DSI 显示
(Arduino_GFX)、GT911 触摸画板、LVGL 9 界面、图形化 Wi-Fi 扫描、ES8311 音频播放、microSD
存储、OV5647 MIPI-CSI 摄像头预览与交互式 ISP/3A 调参。开发板设置与示例说明见
[`examples/arduino/README_ZH.md`](examples/arduino/README_ZH.md)。草图基于 Arduino-ESP32
core `3.3.11`(启用 PSRAM),发布为真实分段包(不含 merged/整片镜像)。

## 🧪 ESP-IDF 示例

| 示例 | 功能 |
| --- | --- |
| [`01_HowToCreateProject`](examples/esp-idf/01_HowToCreateProject/) | 最小 ESP-IDF 工程模板 |
| [`02_HelloWorld`](examples/esp-idf/02_HelloWorld/) | 基础应用与控制台输出 |
| [`03_i2c_tools`](examples/esp-idf/03_i2c_tools/) | I2C 总线扫描与诊断 |
| [`04_wifistation`](examples/esp-idf/04_wifistation/) | 通过 ESP32-C6 协处理器连接 Wi-Fi Station |
| [`05_sdmmc`](examples/esp-idf/05_sdmmc/) | 使用 SD/MMC 访问 microSD 存储 |
| [`06_I2SCodec`](examples/esp-idf/06_I2SCodec/) | ES8311 I2S 音频播放与回声测试 |
| [`07_Displaycolorbar`](examples/esp-idf/07_Displaycolorbar/) | MIPI-DSI LCD 彩条测试 |
| [`08_lvgl_demo_v9`](examples/esp-idf/08_lvgl_demo_v9/) | LVGL 9 显示与触摸演示 |
| [`09_video_lcd_display`](examples/esp-idf/09_video_lcd_display/) | 在 LCD 上预览 MIPI-CSI 摄像头画面 |
| [`10_mp4_player`](examples/esp-idf/10_mp4_player/) | MP4 视频播放 |
| [`11_esp_brookesia_phone`](examples/esp-idf/11_esp_brookesia_phone/) | ESP-Brookesia 手机风格界面 |
| [`12_usb_extend_screen`](examples/esp-idf/12_usb_extend_screen/) | USB 扩展屏应用 |

## 🛠️ CI 矩阵

| 开发框架 | 版本 | 矩阵构建数 |
| --- | --- | ---: |
| ESP-IDF | `v5.5.5` | 12 |
| ESP-IDF | `v6.0.2` | 12 |

[ESP-IDF 示例工作流](https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5/actions/workflows/esp-idf-examples.yml)
会始终运行轻量仓库策略任务，再根据完整 diff 只选择受影响的第一方工程。共享构建输入
会选择完整 24 项矩阵，纯文档或仅固件变更不会消耗产品构建资源；最终汇总状态在所有
情况下均可见。详情请参阅 [CI 发现与路由](docs/CI_ZH.md)。

CI 只验证精确 Pull Request head SHA 的编译兼容性；硬件行为仍需结合开发板、原理图和
产品文档进行验证。仓库没有受维护的 revision-3 产品固件源码，因此本次示例迁移不包含按
revision 区分的产品固件任务、artifact 和烧录器探测。

## 🗂️ 仓库结构

| 路径 | 用途 |
| --- | --- |
| [`.github/`](.github/) | ESP-IDF 工程发现脚本和 GitHub Actions 工作流 |
| [`assets/`](assets/) | 文档使用的产品图片 |
| [`docs/`](docs/) | CI、组件、硬件和 Hosted Wi-Fi 维护约定 |
| [`examples/esp-idf/`](examples/esp-idf/) | 第一方 ESP-IDF 工程 |
| [`firmware/`](firmware/) | 出厂烧录固件 |
| [`schematic/`](schematic/) | 产品原理图 |
| [`CONTRIBUTING_ZH.md`](CONTRIBUTING_ZH.md) | 贡献与验证流程 |
| [`SUPPORT_ZH.md`](SUPPORT_ZH.md) | 支持范围与公开日志隐私说明 |
| [`LICENSE.txt`](LICENSE.txt) | Apache License 2.0 许可证 |

## 📦 出厂固件

[`firmware/ESP32-P4-WIFI6-Touch-LCD-5-FactoryOnly-260127.bin`](firmware/ESP32-P4-WIFI6-Touch-LCD-5-FactoryOnly-260127.bin)
是仓库中保存的出厂烧录镜像，不属于 CI 构建产物，也不是源码工程。该出厂镜像的源码和
构建说明目前尚未包含在本仓库中，后续可能补充。使用前请先阅读
[官方固件烧录文档](https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-5/Firmware-Flashing)。

## 📚 文档

- [产品页面](https://www.waveshare.net/shop/ESP32-P4-WIFI6-Touch-LCD-5.htm)
- [产品文档](https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-5/)
- [产品原理图](schematic/ESP32-P4-WIFI6-Touch-LCD-5-Schematic.pdf)
- [ESP-IDF 示例](examples/esp-idf/)
- [仓库文档](docs/README_ZH.md)
- [CI 发现与路由](docs/CI_ZH.md)
- [组件策略](docs/COMPONENTS_ZH.md)
- [基于原理图的硬件核验](docs/HARDWARE_ZH.md)
- [P4/C6 Hosted Wi-Fi 兼容性](docs/P4_C6_HOSTED_WIFI_ZH.md)

## 🤝 支持与贡献

欢迎提交贡献和可复现的问题报告。请提供开发板和硬件版本、示例路径、ESP-IDF 版本、
复现步骤、预期与实际行为，以及相关的构建日志或串口日志。公开日志前请删除凭据、
网络密钥、个人数据、真实设备标识和机器专用路径。

- [提交 Issue](https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5/issues/new)
- [贡献指南](CONTRIBUTING_ZH.md)
- [支持指南](SUPPORT_ZH.md)
- [官方技术支持](https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-5/Technical-Support)

## 📄 许可证

本仓库基于 Apache License 2.0 许可。详情请参阅
[`LICENSE.txt`](LICENSE.txt)。
