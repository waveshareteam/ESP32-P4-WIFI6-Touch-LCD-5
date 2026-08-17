[English](HARDWARE.md) · [文档索引](README_ZH.md)

# 基于原理图的硬件核验

本页记录仓库配置与
[随仓库提供的原理图](../schematic/ESP32-P4-WIFI6-Touch-LCD-5-Schematic.pdf)
之间的交叉核对结果。它属于源码/配置一致性审计，不代表已经完成开发板运行测试。

## 已确认映射

| 功能 | 原理图证据 | 仓库配置 |
| --- | --- | --- |
| LCD | 720 × 1280、2-lane MIPI-DSI | 720 × 1280、两条数据 lane、700 Mbit/s lane 速率 |
| LCD 控制 | 复位 GPIO27、背光 GPIO26 | BSP 使用复位 GPIO27 和背光 GPIO26 |
| 板级 I2C | SCL GPIO8、SDA GPIO7 | BSP 和 I2S 示例均使用 GPIO8/GPIO7 |
| 音频 | MCLK13、BCLK12、LRCK10、DOUT9、DIN11、PA53 | BSP 和 I2S 示例使用相同 GPIO |
| microSD | D0–D3 GPIO39–42、CMD44、CLK43 | BSP 使用相同 SDMMC 映射 |
| Flash | GD25Q256，256 Mbit | 产品文档标注 32 MB NOR Flash |
| PSRAM | ESP32-P4NRW32 封装 | 产品文档标注封装内 32 MB PSRAM |
| 摄像头 | 两条 CSI 数据 lane 和差分时钟 | 产品文档标注 2-lane MIPI-CSI 接口 |

## 证据边界

- 原理图提供触摸 RST 和 INT 网络，但本地 BSP 没有为这两个信号传入 GPIO。因此仓库
  不声明已经确认这两个信号的 GPIO 映射。
- 原理图包含 ESP32-C6 传输网络、UART 和 USB 信号。Wi-Fi 示例使用 Hosted 组件，但
  没有定义 C6 物理传输引脚表，因此源码与原理图之间的传输映射尚未确认。
- 摄像头使用 MIPI-CSI 差分接口；产品 BSP 不声明额外的摄像头 GPIO 映射。

Actions 编译不能消除以上证据边界。任何涉及显示、触摸、音频、SD、USB、摄像头或 Hosted
传输的硬件相关修改，都必须重新核对对应原理图网络并在开发板上验证。
