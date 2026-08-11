[English](CI.md) · [文档索引](README_ZH.md)

# CI 发现与路由

ESP-IDF 工作流验证 [examples/esp-idf](../examples/esp-idf/) 直属的 12 个第一方工程。
嵌入组件的测试工程和仓库中的出厂固件会被单独盘点，不会被静默加入产品示例矩阵。

只有 `examples/esp-idf` 的直属子目录属于第一方矩阵条目。嵌套的
`components/**/test_apps` 仍是组件测试，不会被发现为产品示例，也不能通过手动工作流触发选择。

## 必需构建矩阵

| 框架版本线 | CI 精确版本 | 第一方工程数 | 构建任务数 |
| --- | --- | ---: | ---: |
| ESP-IDF 5.5 | v5.5.5 | 12 | 12 |
| ESP-IDF 6.0 | v6.0.2 | 12 | 12 |

更新工作流时需重新核对这些精确标签。构建成功只证明对应提交能够编译，不代表硬件行为
或出厂固件兼容性已经得到验证。

## 变更文件路由

仓库策略任务会在每个 Pull Request 上运行。耗时的示例构建由一份完整、识别重命名的
Git diff 决定。

| 变更路径类型 | 示例构建选择 |
| --- | --- |
| 根目录、docs、原理图、治理文件或示例中的 Markdown | 不构建 |
| 轻量策略/维护辅助脚本、其测试、Markdown 审计配置或 `.gitignore` | 不构建；运行轻量策略门禁，且 `docs_only=false` |
| 某个第一方示例内的源码或配置 | 仅该示例 |
| 共享构建配置或构建工作流/发现脚本 | 全部 12 个 |
| firmware 中的文档、源码、二进制或压缩包 | 不构建；单独报告固件/发布范围 |
| 完整 diff 中无法分类的非文档路径 | 全部 12 个，并报告该路径 |
| 空、缺失或不可读取的 diff | 策略任务失败 |

固件路由不会授权重新构建、重新打包或修改出厂镜像。二进制或压缩包变更必须经过明确的
发布审核。

## 手动选择

手动触发工作流时可输入：

- all；
- 唯一的示例目录名，例如 04_wifistation；
- 仓库相对示例路径。

## 稳定结果

每个构建任务都会检出策略任务报告的精确 Pull Request head SHA。即使纯文档变更正确地
不选择产品构建，最终的 ESP-IDF examples 汇总任务仍会显示。相同 Pull Request 的新提交
会取消旧运行，但不会影响其他分支或发布工作流。

路由、Markdown 和组件策略辅助脚本均配有合成测试，覆盖文档、直接源码、共享输入、
固件、重命名/删除、未知路径及不完整 diff。

## CI 固件包与人工硬件验证

每个必需的 ESP-IDF 构建还会创建一个名为
`firmware-esp-idf-<project-slug>-<version>` 的 artifact。12 个直属工程乘以两个
ESP-IDF 版本，共得到 24 个可独立追溯的固件包。包由该构建真实的
`flasher_args.json` 生成，保留实际 offset，不猜测固定的 ESP32-P4 offset；其中包含
`bin/**`、`manifest.json`、`metadata/flasher_args.json`、`flash.sh` 与 `flash.bat`。
包会将构建已验证的 flash mode、size、freq、reset 和 stub 设置作为结构化 manifest 数据
保留，并用于每个生成的烧录命令；未知或不安全的 esptool 参数会被拒绝。包内的
`flash.sh` 和 `flash.bat` 必须接收一个显式端口参数（`PORT` 或 `COMx`），绝不自动选择设备。

人工测试前，请安装 GitHub CLI 和带 esptool 的 Python，并执行 `gh auth login`。在
干净、非 detached 的分支且恰有一个已打开、非草稿 PR 时，从稳定的 Windows 入口运行：

```text
Flash-CI-Firmware.cmd -SelfTest
Flash-CI-Firmware.cmd -ListOnly
Flash-CI-Firmware.cmd -Port COMx [-Baud N]
```

`-SelfTest` 与 `-ListOnly` 是离线检查：不会访问 GitHub、串口设备或 artifact。普通模式
必须显式传入占位符 `COMx`，绝不猜测串口设备。它只接受最终 PR HEAD SHA 的成功工作流运行
及准确 artifact 名称，校验 manifest 身份、每个相对二进制路径、大小、SHA-256、offset、
重叠和 32 MiB flash 边界；之后还要求 esptool 成功退出并输出 `Hash of data verified`。
每次烧录后，用户必须实际检查硬件并输入 `PASS`；进度存放在用户本地应用数据中，final SHA
改变或保存状态无效时会自动重置。

这些 CI 固件包是测试输出，不是仓库内的出厂固件。CI 构建和完整性门禁不代表已完成物理
测试；24 项硬件验证仍须由用户逐项执行。
