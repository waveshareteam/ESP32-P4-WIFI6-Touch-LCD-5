[English](COMPONENTS.md) · [文档索引](README_ZH.md)

# 组件归属与依赖策略

任何名为 `components` 的目录都必须先按行为和维护归属分类，再决定是否迁移；仅凭目录位置
不能判断组件可以删除。

## 保留的本地内容

| 内容 | 分类 | 保留原因 |
| --- | --- | --- |
| 05_sdmmc 中的 `sd_card` | 示例测试支持 | 执行开发板 SD 引脚、上拉、电压和串扰检查 |
| 08 和 12 中的 `bsp_extra` | 产品板级 glue | 组合开发板音频、文件遍历、播放和录音行为 |
| 10 中的 `esp_extractor` | 预编译媒体适配器 | 包含目标相关静态库与格式注册；替换前必须取得 ABI、源码和许可证证据 |
| `brookesia_app_squareline_demo` | 产品演示功能 | 实现仓库中的 Brookesia 应用，不属于通用板级支持 |
| `brookesia_core` | 嵌入式上游集成 | 使用 release/v0.6 架构并包含仓库兼容性调整 |

两份 `bsp_extra` 可作为后续去重候选，但必须先证明其调用点以及 USB/音频行为等价。

## 托管组件版本

六个显示相关示例不再携带本地 `esp32_p4_wifi6_touch_lcd_5` BSP 或
`esp_lcd_hx8394` 驱动目录。它们的主 manifest 从 ESP Component Registry
（waveshare 命名空间）解析这两个组件：

- BSP [`esp32_p4_wifi6_touch_lcd_5`](https://components.espressif.com/components/waveshare/esp32_p4_wifi6_touch_lcd_5) `^1.0.3`。
- HX8394 驱动 [`esp_lcd_hx8394`](https://components.espressif.com/components/waveshare/esp_lcd_hx8394) `^2.1.0`。

示例 08 和 12 的 `bsp_extra` 封装使用相同的 BSP 范围 `^1.0.3`，不会覆盖示例中的
直接依赖。

## HX8394 初始化边界

HX8394 驱动在独立默认配置下会发送 I2C 命令序列；LCD5 BSP 为本开发板集成选择跳过
该行为。此源代码级约定不等于面板行为已获证明：变更或提升任一版本前，必须在目标开发板上
完成 HIL 验证。

## ESP32-P4 revision 默认配置

全部 12 个第一方示例的默认配置面向 ESP32-P4 pre-v3 芯片，并使用 revision-1.0 最低版本
符号；产品默认示例配置为 revision 1.3/pre-v3。USB 扩展屏的 ESP32-P4 配置也使用相同默认值。
本仓库没有受维护的 revision-3 产品固件源码，因此按 revision 区分的产品固件任务、artifact
和烧录器探测不属于此次示例迁移范围。

## Brookesia 依赖约定

仓库中的 Brookesia core 标识为 release/v0.6 集成。ESP-IDF 5 使用 esp-boost 0.3.*，
ESP-IDF 6 精确使用 0.6.0。LVGL 保持固定为 9.5.0，因为仓库的 ESP-IDF 6 兼容调整基于该版本。

旧版 AI framework 被有意隐藏并关闭，因为其依赖栈未包含在本产品集成中。重新启用它必须进行
明确的 Brookesia 架构升级，并通过完整 IDF 矩阵；这不是只改 menuconfig 即可完成的工作。

## MP4 音频编解码器边界

MP4 示例将 `espressif/esp_audio_codec` 精确固定在 2.5.0。2.6.0 及后续版本要求
ESP32-P4 revision 3 或更新芯片，而示例默认配置仍保留 pre-v3 支持。修改这一版本约束前，
必须取得硬件 revision 证据并通过完整 ESP-IDF 矩阵。

## 审查规则

- 不把嵌入式上游文档或许可证当作产品本地内容翻译修改。
- 在有单独审查的替代版本前，保留精确的临时源代码固定版本。
- 源代码级初始化选择和成功 CI 只代表编译证据；显示行为必须完成 HIL 验证。
- 在 manifest 附近保留版本范围的原因和重新评估条件。
