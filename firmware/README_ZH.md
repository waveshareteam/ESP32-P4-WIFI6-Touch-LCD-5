# ESP32-P4-WIFI6-Touch-LCD-5 固件

[English](README.md)

本目录提供已实测的 ESP32-P4-WIFI6-Touch-LCD-5 出厂固件，请根据产品版本选择对应固件。

## 固件文件

| 文件 | 用途 |
| --- | --- |
| `ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261119.bin` | V1.3 出厂固件，用于恢复开箱演示。 |
| `ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261110.bin` | V3.2 出厂固件，用于恢复开箱演示。 |

固件中心默认选择日期最新的 `20261119`，它适用于 V1.3；V3.2 请选择 `20261110`。两份固件适用的产品版本不同。

每份出厂 BIN 都是合并镜像，请将整个文件从 **0x0** 地址烧录。

## 烧录方法

**整片擦除 Flash 会清除设备中原有的固件、设置和用户数据，请提前备份需要保留的数据。**

1. 安装 Python 和最新版 esptool：

   ```sh
   python -m pip install --upgrade esptool
   ```

2. 使用 USB 数据线连接开发板，关闭占用设备串口的串口监视器。
3. 在本 `firmware/` 目录中打开终端，将以下命令中的 `<PORT>` 替换为设备实际串口号，例如 Windows 下的 `COM5` 或 Linux 下的 `/dev/ttyACM0`。
4. 先整片擦除 Flash，再根据产品版本烧录对应 BIN：

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> erase-flash

   ```

   V1.3：

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> write-flash 0x0 ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261119.bin

   ```

   V3.2：

   ```sh
   python -m esptool --chip esp32p4 --port <PORT> write-flash 0x0 ESP32-P4-WIFI6-Touch-LCD-5_FactoryOnly_20261110.bin
   ```

5. 烧录成功后，复位或重新上电，确认出厂演示正常启动，并检查各项功能是否符合预期。

如果工具无法连接，请按照产品说明让开发板进入下载模式，再重试。

命令详情请参考 [esptool 官方文档](https://docs.espressif.com/projects/esptool/en/latest/esp32p4/esptool/basic-commands.html)。
