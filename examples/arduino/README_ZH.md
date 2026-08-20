[English](README.md) · [仓库主页](../../README_ZH.md)

# Arduino 示例

Waveshare ESP32-P4-WIFI6-Touch-LCD-5(720 × 1280 MIPI-DSI IPS 屏、GT911 电容触摸、
OV5647 MIPI-CSI 摄像头)的 Arduino 草图与随仓库。

## 开发板设置(Arduino IDE)

- Arduino-ESP32 core `3.3.11`(或更新 3.x)。
- 开发板:`ESP32P4 Dev Module`(`esp32:esp32:esp32p4`)。
- 菜单选项:
  - `Chip Variant`:`v3.00 or newer`(rev3.x 板,默认)
  - `PSRAM`:`Enabled`
  - `Flash Size`:`32 MB`
  - `Flash Mode`:`QIO`
  - `Flash Frequency`:`80 MHz`
  - `Partition Scheme`:`13M APP / 7M data (32 MB)`
  - `Upload Mode`:`Default (USB-UART 桥接)`
- 显示类草图要求启用 PSRAM。
- 对于已确认的 rev1.x ESP32-P4 芯片（包括 rev1.3），请选择
  `Chip Variant: Before v3.00`；该旧 profile 使用 200 MHz PSRAM。这是芯片设置，
  不是 PCB revision。两个 profile 不能混用。

## 示例

| 草图 | 说明 |
| --- | --- |
| `01_HelloWorld` | Arduino_GFX DSI 显示最小点亮 |
| `02_AsciiTable` | Arduino_GFX 能力/基准表 |
| `03_Drawing_board` | GT911 五点电容触摸画板 |
| `04_LVGLV9_Arduino` | LVGL 9 控件界面 + 触摸 |
| `05_GFX_ESPWiFiAnalyzer` | 图形化 Wi-Fi 扫描(板载 ESP32-C6 协处理器) |
| `06_Camera_Preview` | OV5647 MIPI-CSI 摄像头实时上屏 |
| `07_Camera_ISP_Tuning` | 实时预览 + 串口交互 ISP/3A 调参 |
| `08_SD_Card` | microSD SDIO 3.0 读写 |
| `09_Audio_Playback` | ES8311 编解码器以不同频率音色演奏《致爱丽丝》开篇 |
| `10_Mic_Record` | ES7210 四麦克风采集,串口打印峰值/RMS/抽样数据 |

## 音频说明

`09_Audio_Playback` 通过纯发送 I2S(MCLK 13、BCLK 12、LRCK 10、DOUT 9)驱动
ES8311 编解码器(I2C 0x18),并经 GPIO 53 使能 2 W 扬声器。`10_Mic_Record` 通过
纯接收 I2S(DIN 11)以 16 kHz/16 位采集板载 ES7210(I2C 0x40)麦克风,并把帧数据
打印到串口监视器。

## 摄像头说明

`06_Camera_Preview` 与 `07_Camera_ISP_Tuning` 使用 Arduino-ESP32 core 自带的 `ESP_Video`
库(MIPI-CSI 设备)。需将 OV5647 模组接到板载 MIPI-CSI 连接器。默认传感器模式输出
RAW8,由 ISP 管线转换为 RGB565 上屏。`07_Camera_ISP_Tuning` 支持串口交互调参:
`g` 增益、`e` 曝光(µs)、`a` AE 目标、`v/h` 翻转、`t` 测试图案、`s` 状态。

## 触摸说明

当前 Arduino 配置不主动驱动触摸 RST/INT，因此随仓库的 GT911 驱动会探测两个合法
I2C 地址：`0x5D` 和 `0x14`。若两个地址均无响应，触摸示例会报告该状态并在无触摸模式
下继续运行，不会直接终止。坐标行为仍须使用实物开发板验证。

## 随仓库

- `displays/` — 板级显示/触摸/I2C 配置与驱动(HX8394 DSI 初始化、GT911 触摸、非阻塞串口日志)
- `GFX_Library_for_Arduino` — 支持 ESP32-P4 MIPI-DSI 的 Arduino_GFX
- `lvgl` + `lv_conf.h` — `04_LVGLV9_Arduino` 使用的 LVGL 9

硬件细节见[主 README](../../README_ZH.md)与[官方产品文档]
(https://docs.waveshare.com/ESP32-P4-WIFI6-Touch-LCD-5)。
