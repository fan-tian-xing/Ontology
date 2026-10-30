
## 摘要

Terminal-Bench 4.0 是一套在终端和容器环境中评测 Agent 完成任务能力的 benchmark，任务完成情况由自动验证程序判定。其结果反映底层模型、Agent、工具权限、运行环境和任务配置的共同作用，不能简单等同于基础模型的问答能力。目前正式数据集为 4.0.0，共 66 个任务；所有任务的 Agent 超时上限为 8 小时。

Terminal-Bench 可用于拓展现有 Agent 经验利用研究，观察经验机制在多步工具使用和环境反馈场景中的作用。Harbor 已提供评测 Harness，支持任务调度、沙箱管理、Agent 调用、结果验证与轨迹记录，因此无需另行开发一套通用 Harness。主要适配工作是在 Harbor 现有框架中接入终端交互 Agent，并将经验读取与更新机制纳入其执行流程，同时统一工具权限、调用预算和经验数据隔离规则。建议先固定版本与模型，以少量代表性任务验证基础 Agent 的运行，再接入一种实现明确的经验方法。

## 1. Terminal-Bench 是什么

Terminal-Bench 旨在衡量 Agent 在多样且具有一定难度的终端任务中的完成能力。

普通问答 benchmark 通常以问题为输入、文本答案为输出，再与标准答案比较。Terminal-Bench 则在隔离环境中运行 Agent，要求其读取文件、执行命令、观察环境反馈，并根据执行结果继续采取行动，最终使环境状态或产物符合任务要求。任务覆盖代码与软件工程、机器学习与数据处理、科学计算、运维、安全、设计与媒体等终端工作流。因此，其评测对象是**Agent 系统整体**；若要分析模型本身的贡献，需要控制 Harness、工具和资源配置。

官网排行榜中的 Resolution Rate 表示任务解决率，图表提供 95% 置信区间；Tokens 表示运行记录中的 token 用量，Cost 表示记录或估算的模型/API 成本。这些指标会受到模型、Agent、推理设置、重试次数和统计口径影响。比较时应结合完整实验配置解读，不能将单一排行榜结果直接视为基础模型能力。

## 2. 任务设计与验证机制

Harbor 标准任务通常包含 `instruction.md`、`task.toml`、`environment/`（例如 Dockerfile）、`solution/`（参考解）和 `tests/`（验证脚本）。Agent 根据任务指令在配置的容器或沙箱中操作；任务可以包含多步操作、多个容器以及连续的环境反馈。任务结束后，verifier（自动验证程序）检查最终产物或环境状态，并生成数值 reward，常见结果为通过或失败。
评测侧重任务结果，而不是要求 Agent 遵循某条指定的操作路径。任务配置可以设置 Agent 与 verifier 的超时，以及 CPU、内存、存储和 GPU 等资源。Harbor 支持运行单个任务，也支持通过筛选参数选择数据集中的任务。运行错误、超时、模型拒答、输出 token 超限和 verifier 未通过属于不同的失败类型，结果分析时宜分别记录。

**真实任务示例：`layout-config-recreation2`。** Hub 中的指令要求 Agent 检查 `/app/data/layout.png` 及 `/app/data/components/` 中的图像素材，识别画布元素、层级、位置、文字和样式，并生成 `/app/output/config.json`；使用提供的渲染程序生成的结果须与原图达到至少 98% 的像素一致。任务配置声明了输出 artifact，Agent 超时上限为 8 小时，环境与 verifier 分别配置 CPU 和内存，verifier 在独立环境中运行。完成该任务涉及图像观察、文件检查、配置生成、渲染和调试，最终由自动程序验证结果。

Harbor 会保存 trial 的 Agent 输出、verifier 结果、运行配置和轨迹文件。Viewer 可按 trial 查看 reward、cost、耗时、轨迹及相关文本文件。若所用 Agent 输出 ATIF 轨迹，可检查其中序列化的消息、工具调用和工具结果；实际可见内容取决于对应 Agent 的记录能力，因此不应将轨迹查看能力等同于访问所有模型内部推理内容。

## 3. Harbor 的作用、运行与产物

Harbor 是 Agent 评测和优化框架，在本实验场景中承担 Harness 与调度层职责：加载任务或数据集、准备沙箱、启动预集成或自定义 Agent、运行 verifier、汇总 trial，并记录配置和轨迹。OpenHands、Gemini CLI、Qwen Coder、SWE-Agent、Terminus-2 等预集成 Agent；可用项会随 Harbor 版本及认证配置变化。

Harbor 也支持自定义 Agent。若 Agent 命令行程序运行在任务环境中，可实现 `BaseInstalledAgent`；若 Agent 循环运行于 Harbor 进程外部，并通过 `BaseEnvironment` 操作沙箱，则可实现 `BaseAgent`。Harbor 通过 `module.path:ClassName` 等方式调用自定义实现。对于现有问答流程，适配重点是让 Agent 能在 Harbor 的执行框架中与终端环境交互，并按需接入经验机制；任务调度、沙箱和 verifier 等 Harness 能力由 Harbor 提供。([自定义 Agent 接口](https://docs.harborframework.com/agents/custom-agents))

**官方基础命令：**

```bash
uv tool install 'harbor[modal]'
harbor run -d terminal-bench/terminal-bench@4.0.0 \
  -e modal \
  -a claude-code \
  -m anthropic/claude-sonnet-5 \
  -k 5
harbor view jobs
```

其中，`-d` 选择并固定数据集版本，`-e modal` 指定运行沙箱，`-a` 指定 Agent，`-m` 指定模型，`-k 5` 表示每项任务进行 5 次尝试；`harbor view jobs` 用于查看本地结果。Terminal-Bench 4.0 运行指南指出数据集包含 GPU 任务，并建议使用具备 GPU 能力的沙箱；官方实验采用 Modal。Hub 数据集页展示了另一种长参数形式并推荐 Modal 或 Daytona。由于命令示例可能随文档或 CLI 版本更新，实际运行前应以所安装 Harbor 版本的 `harbor run --help`、锁定的数据集版本及对应运行指南为准。小规模验证可选择单个任务，并先设置较低并发数和尝试次数；筛选参数应按目标 CLI 版本确认。([4.0 运行指南](https://www.tbench.ai/run)、[Harbor 作业运行文档](https://docs.harborframework.com/jobs/run-a-job))

Harbor 支持本地 Docker/Podman 和 Modal、Daytona 等远程沙箱。框架支持某项能力，并不意味着每个任务都能在任意本地配置下运行。4.0 包含 GPU 与多容器任务，实验室 Linux GPU 服务器可作为候选环境，但应事先确认 Docker daemon 与容器权限、Compose 或多容器能力、GPU runtime 与驱动、镜像构建和文件挂载、网络策略及可用并发资源。Windows 本机环境的 GPU 和多容器支持情况也需单独核实。GPU 任务对沙箱执行环境提出要求，并不意味着 Agent 所用模型必须部署在本地 GPU 上。([Harbor 沙箱能力矩阵](https://docs.harborframework.com/sandboxes/pre-integrated-sandboxes))

调用 API 模型需要相应供应商的凭据和网络连接；使用 Modal/Daytona 等远程沙箱也需配置对应账户。凭据应通过环境变量或 Harbor secret 机制注入。本地部署模型可减少逐 token 的供应商费用，但需要模型服务、显存和接口适配；API 方案减少模型运维工作，实际费用与速率限制则取决于模型和调用量。实验成本可按下式估算：`总费用 ≈ 各 trial 的输入/输出 token 费用之和 + 沙箱运行时长 × 资源单价 + 构建与存储费用`。建议先以少量任务记录 token 用量、运行时长和失败类型，再估算完整实验成本。8 小时是任务超时上限，不代表单个任务的预期运行时间。

## 4. 经验机制接入与信息隔离

经验机制可以在任务开始时检索一次，也可以根据执行步数、失败信号或环境状态重新检索；还可以先从历史轨迹中提炼策略，再将其用于后续行动。这些属于可供实验比较的设计选项，不代表 ReasoningBank、AdaMem 或其他方法的现有实现已经采用了这些机制。Harbor 可以记录和查看运行轨迹，ATIF 提供结构化轨迹格式。经验库可保存经筛选的任务状态、动作、结果、失败原因和适用条件，以便评估其复用价值及上下文成本。([Harbor ATIF 轨迹格式](https://docs.harborframework.com/agents/atif)、[轨迹加载文档](https://docs.harborframework.com/jobs/loading-trajectories))

面向 GPQA/AIME 等问答任务形成的经验，主要是解题提示或文本结论，通常不包含 shell 命令、目录结构、进程反馈、依赖处理和错误恢复等信息。因此，迁移时需要评估这些经验与终端任务的匹配程度；终端经验可由经验构建任务上的 Agent 交互轨迹提取，轨迹中既可包括成功过程，也可记录失败与恢复经验。

实验设计应将经验构建任务与最终测试任务分开。测试任务的参考解、verifier 内容和成功轨迹不应进入经验库；对于高度相似的任务，也应检查经验是否包含测试任务特有的答案或操作细节。经验条目宜记录来源，以便追溯其构建依据。方法比较时，除报告成功率外，还应记录检索内容，并控制额外上下文 token、模型调用次数和成本。设置 token 量相近的无关经验对照，有助于判断提升是否来自相关经验，而非仅来自额外上下文；同时可观察错误经验对执行结果的影响及跨任务泛化情况。

## 5. 分阶段实验路线

| 阶段 | 工作与产出 |
|---|---|
| 一：环境验证 | 核对 Harbor、容器、GPU 和账户要求，固定 Harbor 与 Terminal-Bench 4.0.0 版本；根据任务配置选择少量 CPU、GPU 或多容器任务，整理环境清单。 |
| 二：基础 Agent | 选择团队可稳定调用的 Agent 与模型，在小规模任务集上以低并发、少量重复运行；保存各 trial 的 reward、轨迹、成本和失败类型。 |
| 三：适配一种经验方法 | 优先选择实现清楚且能够在同一 Agent 执行流程中接入经验的方法；固定模型和任务，通过 Harbor 的 Agent 接口或现有 Agent 扩展能力接入，并开展控制变量比较。 |
| 四：扩大 baseline 对比 | 基础 Agent 与一种经验方法验证可行后，再逐项迁移其他 baseline，统一实验配置并开展正式评测和重复试验。 |


