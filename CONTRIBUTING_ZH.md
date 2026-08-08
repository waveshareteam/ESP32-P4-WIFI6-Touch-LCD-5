[English](CONTRIBUTING.md) · [返回仓库首页](README_ZH.md)

# 贡献指南

欢迎提交能够保持本产品已有硬件和框架范围的贡献。

## 提交 Pull Request 前

1. 从当前默认分支开始，避免混入无关修改。
2. 明确所有受影响的第一方示例和框架版本线。
3. 不为仓库中不存在的功能新增 Arduino、固件构建或硬件特性。
4. 除非变更属于明确审核的发布更新，否则把仓库中的出厂二进制视为不可变产物。
5. 修改引脚、BSP、显示、触摸、音频、SD、USB、摄像头或 Hosted 传输时，必须核对
   本地原理图或产品硬件资料。
6. 产品自有的人类可读文档必须提供英文和简体中文配对；不要改写嵌入式上游文档。
7. 从日志和公开文本中删除凭据、账户数据、真实设备标识和机器专用路径。

## 静态检查

提交前请运行仓库的轻量检查：

~~~text
python .github/scripts/test_discover_esp_idf_examples.py
python .github/scripts/test_repository_policy.py
python .github/scripts/test_component_contracts.py
python .github/scripts/check_repository_policy.py
python .github/scripts/check_component_contracts.py
~~~

必需的 ESP-IDF 产品构建会在 GitHub Actions 中针对精确的 Pull Request head 运行。
矩阵覆盖 [CI 约定](docs/CI_ZH.md)中记录的两个版本以及全部第一方示例。

## Pull Request 描述

请说明：

- 问题与预期结果；
- 受影响的示例、组件和文档；
- 预期 ESP-IDF 矩阵覆盖；
- 硬件行为变化对应的硬件/原理图证据；
- 对出厂固件或发布产物的影响；
- 任何兼容性范围及其重新评估条件。

请使用仓库 Pull Request 模板，并保留尚未解决且有证据支持的限制。
