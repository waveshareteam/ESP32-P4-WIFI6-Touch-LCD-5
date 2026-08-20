[English](CI.md) · [文档索引](README_ZH.md)

# CI 发现与路由

ESP-IDF 工作流验证 [examples/esp-idf](../examples/esp-idf/) 直属的 12 个第一方工程。
嵌入组件的测试工程和仓库中的出厂固件会被单独盘点，不会被静默加入产品示例矩阵。

只有 `examples/esp-idf` 的直属子目录属于第一方矩阵条目。嵌套的
`components/**/test_apps` 仍是组件测试，不会被发现为产品示例，也不能通过手动工作流触发选择。

## 必需构建矩阵

| 框架版本线 | CI 精确版本 | 第一方工程数 | 构建任务数 |
| --- | --- | ---: | ---: |
| ESP-IDF 5.5 | v5.5.5 | 12 | 24（12 × 2 profile） |
| ESP-IDF 6.0 | v6.0.2 | 12 | 24（12 × 2 profile） |

更新工作流时需重新核对这些精确标签。构建成功只证明对应提交能够编译，不代表硬件行为
或出厂固件兼容性已经得到验证。显示、触摸、音频、摄像头、无线和烧录行为必须在目标开发板
上完成 HIL 验证。

## 变更文件路由

仓库策略任务会在每个 Pull Request 上运行。耗时的示例构建由一份完整、识别重命名的
Git diff 决定。

| 变更路径类型 | 示例构建选择 |
| --- | --- |
| 根目录、docs、原理图、治理文件或示例中的 Markdown | 不构建 |
| 轻量策略/维护辅助脚本、其测试、Markdown 审计配置或 `.gitignore` | 不构建；运行轻量策略门禁，且 `docs_only=false` |
| 某个第一方示例内的源码或配置 | 仅该示例 |
| 共享构建配置或构建工作流/发现脚本 | 全部 12 个 |
| firmware 中的文档或源码 | 不构建；单独报告固件/发布范围 |
| firmware 中的 `.bin` 或 `.zip` artifact（包括重命名或删除） | 不构建；设为 `release_review=true`，并使稳定示例 CI 结果失败 |
| 完整 diff 中无法分类的非文档路径 | 全部 12 个，并报告该路径 |
| 空、缺失或不可读取的 diff | 策略任务失败 |

固件路由不会授权重新构建、重新打包或修改出厂镜像。此示例 CI 不提供 artifact 发布旁路：每个
计算得到的 `release_review=true` 都会使稳定的 `ESP-IDF examples` 结果以失败关闭方式结束，
即使没有选择任何示例构建也一样。受控发布更新需要具备明确维护者范围的独立受保护流程；本仓库
目前未定义此流程。

## 手动选择

手动触发工作流时可输入：

- all；
- 唯一的示例目录名，例如 04_wifistation；
- 仓库相对示例路径。

手动触发时，汇总任务名为 `ESP-IDF examples (manual)`；Pull Request 和 push 则保持
`ESP-IDF examples`，从而避免同一 SHA 出现无法区分的汇总 check context。

## 稳定结果

每个构建任务都会检出策略任务报告的精确 Pull Request head SHA。即使纯文档变更正确地
不选择产品构建，最终的 ESP-IDF examples 汇总任务仍会显示。相同 Pull Request 的新提交
会取消旧运行，但不会影响其他分支或发布工作流。

路由、Markdown 和组件策略辅助脚本均配有合成测试，覆盖文档、直接源码、共享输入、
固件、重命名/删除、未知路径及不完整 diff。

## 托管组件版本

显示示例 07–12 从 ESP Component Registry（waveshare 命名空间）解析 LCD5 BSP `^1.0.3`
与 HX8394 驱动 `^2.1.0`。默认源码配置选择 rev3.x。独立的板级产品固件
revision 任务不属于本次示例 CI 变更。

## ESP32-P4 芯片 revision profile

`rev1_3` 与 `rev3_x` 表示的是通过芯片探测得到的 **ESP32-P4 芯片 revision**，
不是 Waveshare PCB 或产品硬件 revision。不要只根据 PCB 丝印选择
profile；应使用烧录器的只读探测或其他可信芯片信息确认芯片 revision。

| Profile | 支持的 ESP32-P4 芯片 | Revision 配置 | PSRAM 配置 | 仓库中的用途 |
| --- | --- | --- | --- | --- |
| `rev3_x` | `[3.0, 4.0)` | `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=n` 与 `CONFIG_ESP32P4_REV_MIN_300=y` | `CONFIG_SPIRAM_SPEED_250M=y`，250 MHz | 全部 12 个第一方示例的默认值，也是 CI 的当前芯片显式 profile |
| `rev1_3` | `[1.0, 2.0)`（rev1.x，包括 rev1.3） | `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` 与 `CONFIG_ESP32P4_REV_MIN_100=y` | `CONFIG_SPIRAM_SPEED_200M=y`，200 MHz | 兼容 profile；仅用于已确认的 rev1.x 芯片 |

虽然历史符号名称为 `SELECTS_REV_LESS_V3`，但两条受支持的 IDF 版本线都会为该
profile 生成 `CONFIG_ESP32P4_REV_MAX_FULL=199`，因此 `rev1_3` 不支持 2.x revision。

示例固件包同时使用 `rev1_3` 与 `rev3_x` 两个显式 profile 构建并发布。
未显式加载 profile overlay 时，每个顶层 `sdkconfig.defaults` 都会选择上表的
`rev3_x`；命名 overlay 则用于 CI 与可重复的本地构建。

本地切换 profile 时，请在选定示例的工程目录中执行，并隔离构建目录与
生成的 `sdkconfig`：

```bash
profile=rev3_x  # 或 rev1_3
idf.py -B "build/$profile" \
  -D "SDKCONFIG=$PWD/build/$profile/sdkconfig" \
  -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.$profile" \
  build
idf.py -B "build/$profile" -p PORT flash monitor
```

普通构建中，工程目录里既有的 `sdkconfig` 优先级高于 defaults，因此切换 profile
时不能复用。上述命令为每个 profile 指定独立的生成配置，从而避免此优先级问题。

## CI 固件包与人工硬件验证

每个必需的 ESP-IDF 构建会按 profile 创建名为
`firmware-esp-idf-<project-slug>-<version>-<profile>` 的 artifact。12 个直属工程乘以两个
ESP-IDF 版本和两个 profile，共得到 48 个可独立追溯的固件包。包由该构建真实的
`flasher_args.json` 生成，保留实际 offset，不猜测固定的 ESP32-P4 offset；其中包含
`bin/**`、`manifest.json` 与 `metadata/flasher_args.json`。
包会将构建已验证的 flash mode、size、freq、reset 和 stub 设置作为结构化 manifest 数据
保留；未知或不安全的 esptool 参数会被拒绝。包内不提供可直接绕过检查的烧录 helper 或命令；
只能使用仓库根目录的 `Flash-CI-Firmware.cmd` 入口，它会调用受版本控制的 PowerShell
编排脚本，并要求显式传入 `COMx` 端口。
打包必须读取实际生成的构建配置（`build/config/sdkconfig.json`，或生成的
`build/sdkconfig` 回退），并确认所选 profile 的符号（`rev1_3` 为 `SELECTS_REV_LESS_V3=y`、
`REV_MIN_100=y`；`rev3_x` 为 `SELECTS_REV_LESS_V3=n`、`REV_MIN_300=y`）；源码 defaults
不能作为证据。内部 ZIP 文件名和 manifest 会包含所选 `board_profile`、对应 revision 范围以及
`c6_firmware_included: false`。

人工测试前，请安装 GitHub CLI 和带 esptool 的 Python，并执行 `gh auth login`。在
干净、非 detached 的分支且恰有一个已打开、非草稿 PR 时，从稳定的 Windows 入口运行：

```text
Flash-CI-Firmware.cmd -SelfTest
Flash-CI-Firmware.cmd -ListOnly
Flash-CI-Firmware.cmd -Port COMx [-Baud N]
```

`-SelfTest` 与 `-ListOnly` 是离线检查：不会访问 GitHub、串口设备或 artifact。普通模式
必须显式传入占位符 `COMx`，绝不猜测串口设备。它只接受最终 PR HEAD SHA 的成功工作流运行，
且该运行必须报告完整的 48 个预期、唯一且未过期的 firmware artifact；部分 dispatch 运行
会被拒绝。随后它只下载选定的准确 artifact，校验 manifest 身份、每个相对二进制路径、大小、
SHA-256、offset、重叠和 32 MiB flash 边界；之后还要求 esptool 成功退出并输出
`Hash of data verified`。
在下载 artifact 或烧录之前，它会执行只读 `esptool chip_id` ESP32-P4 探测（仅在兼容性需要时
回退到 `chip-id`），解析芯片 revision，并为 `[1.0, 2.0)` 选择 `rev1_3`、为
`[3.0, 4.0)` 选择 `rev3_x`。范围外的 revision（包括 0.x、2.x 以及 4.x 或更新版本）
会在查找、下载或烧录 artifact 前被拒绝；随后的 manifest 范围检查会拒绝任何
profile 不匹配。芯片 revision 检查不能替代
PCB/电气 revision 确认。每次烧录后，用户必须实际检查硬件并输入 `PASS`；进度按 profile
隔离地存放在用户本地应用数据中，final SHA、选定 workflow run、profile 改变、保存状态截断/格式错误
或旧 schema 时会自动重置。状态写入会先在同一目录创建临时文件，再原子替换或移动到状态文件。

这些 CI 固件包是测试输出，不是仓库内的出厂固件。CI 构建和完整性门禁不代表已完成物理
测试。每块板只执行与探测所得 profile 匹配的 24 项；若要覆盖两个 profile，需要使用适配的
开发板完成总计 48 项显式硬件验证。
