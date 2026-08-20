[English](IO.md) · [文档索引](README_ZH.md)

# ESP32-P4-WIFI6-Touch-LCD-5 IO 列表

本文档是仓库维护的 IO 参考，依据 LCD5 BSP 源码和仓库内原理图交叉核对。
它不能替代官方产品手册，也不代表所有接口都已经完成实物 HIL 验证。

## 已确认的板级映射

| 功能 | 映射 | 说明 / 证据 |
|---|---|---|
| 板级 I2C SDA | GPIO7 | 共享板级 I2C，总线连接编解码器和 GT911 |
| 板级 I2C SCL | GPIO8 | 共享板级 I2C，总线连接编解码器和 GT911 |
| LCD 背光 | GPIO26 | LEDC PWM，5 kHz，10-bit |
| LCD 复位 | GPIO27 | HX8394 MIPI-DSI 面板复位 |
| LCD | 720 × 1280，2-lane MIPI-DSI | HX8394，lane 速率 700 Mbit/s |
| I2S MCLK | GPIO13 | ES8311 / ES7210 音频总线 |
| I2S BCLK | GPIO12 | ES8311 / ES7210 音频总线 |
| I2S LRCK / WS | GPIO10 | ES8311 / ES7210 音频总线 |
| I2S DOUT | GPIO9 | ES8311 播放 |
| I2S DIN | GPIO11 | ES7210 录音 |
| 扬声器功放使能 | GPIO53 | 板级功放控制，高电平有效 |
| microSD D0..D3 | GPIO39..GPIO42 | 4-bit SDMMC |
| microSD CMD | GPIO44 | SDMMC 命令线 |
| microSD CLK | GPIO43 | SDMMC 时钟线 |

## I2C 设备

板级 I2C 使用 GPIO7/GPIO8。当前仓库使用的相关设备地址如下：

| 设备 | 地址 | 说明 |
|---|---:|---|
| GT911 触摸 | `0x5D` 或 `0x14` | 控制器在复位时根据 INT 电平选择地址；Arduino 示例会探测两个地址 |
| ES8311 编解码器 | `0x18` | 编解码器配置地址 |
| ES7210 编解码器 | `0x40` | 麦克风编解码器地址 |

原理图中 `TP_RST` 通过 0 欧姆电阻 R37 连接 GPIO23；`TP_INT` 则通过可选的
R108（`NC/0R`）连接 GPIO2，因此中断线路是否导通取决于实际贴装情况。当前仓库
驱动和 BSP 仍将两个引脚配置为 `GPIO_NUM_NC`；Arduino 驱动会探测 GT911 的两个
合法地址，不宣称已经主动控制复位或中断信号。

## 其他接口

- ESP32-C6 是板载 Wi-Fi/Bluetooth Hosted 协处理器。在 P4 到 C6 的传输引脚
  与配套从机固件完成完整交叉核对前，本文不重复声明未经确认的传输 GPIO 表。
- OV5647 摄像头使用 MIPI-CSI 连接器和差分接口；本文不虚构额外的摄像头 GPIO 列表。
- USB 转 UART、USB OTG 和 40PIN 扩展接口属于连接器级接口。分配应用 GPIO
  前请以原理图和官方手册为准。

## Revision 说明

ESP32-P4 rev1.3 与 rev3.x 使用不同的芯片 profile，但上面的板级 IO 映射不变。
CPU、PSRAM 和 MIPI-DSI 时钟的 revision 差异见仓库 CI 与固件文档。
