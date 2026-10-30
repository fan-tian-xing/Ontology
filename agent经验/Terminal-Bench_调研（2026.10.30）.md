
## 摘要

Terminal-Bench 4.0 是一个以终端和容器环境为载体、由自动测试判断任务是否完成的 Agent benchmark。它考查的是“底层模型 + Agent Harness + 工具权限与环境 + 任务”的组合能力，不是脱离执行框架的纯模型问答分数。官方将其作为持续维护的 benchmark；目前，正式数据集为 4.0.0，包含 66 个任务，agent timeout 统一为 8 小时。

它适合扩展我们对多步工具使用的研究，Harbor 支持预集成和自定义 Agent，因而接入在工程上可行；真正工作量在于构建统一的终端 Agent 底座、接通经验读写、控制工具与预算、并防止测试轨迹泄漏。建议先固定版本和模型，使用少量代表性任务做基础 Agent 可行性验证，再接入一种实现明确的经验方法。

## 1. Terminal-Bench 是什么

Terminal-Bench 由 Harbor 团队维护，项目由 Stanford、Harbor 和 Laude Institute 托管，任务由多位研究者和组织贡献。其目标是衡量 Agent 在多样、困难的终端任务中的工作能力。这里几个概念应分开：

| 概念 | 在本项目中的含义 |
|---|---|
| Benchmark | Terminal-Bench：任务指令、初始文件与容器环境、资源配置及验证程序组成的固定评测集。 |
| Agent | 接收指令并决定如何使用工具的软件系统，可以包含提示、循环、状态管理和策略。 |
| LLM | Agent 可调用的语言模型，负责理解、规划、生成工具动作等；模型本身不等同于完整 Agent。 |
| Harness | 运行 Agent、提供工具与环境、调度任务、保存轨迹并执行评测的框架。Terminal-Bench 4.0 以 Harbor 为官方 Harness。 |

普通问答 benchmark 通常输入问题、生成文本答案，再与标准答案比较；Terminal-Bench 则把 Agent 放进隔离环境，要求它读取文件、运行命令、观察返回结果、根据错误继续修正，并通过环境状态满足 verifier。应用覆盖代码与软件工程、机器学习/数据处理、科学计算、运维、安全、设计与媒体等终端工作流。评测对象因此是**Agent 系统整体**；如要分析模型贡献，必须固定 Harness、工具和资源。

官网排行榜的 Resolution Rate 是任务通过率（官网图示含 95% 置信区间）；Tokens 表示运行记录的 token 用量，Cost 表示记录或估算的模型/API成本。它们受模型、Agent、推理设置、重试和各自记录口径共同影响，不能把某个榜单分数单独解释为基础模型能力。([官网](https://www.tbench.ai/)、[Terminal-Bench 仓库](https://github.com/harbor-framework/terminal-bench)、[Harbor 仓库](https://github.com/harbor-framework/harbor))

## 2. 任务设计与验证机制

Harbor 的标准任务目录包含 `instruction.md`、`task.toml`、`environment/`（如 Dockerfile）、`solution/`（参考解）和 `tests/`（验证脚本）。Agent 接收任务指令并在被配置的容器/沙箱中执行命令；任务可有多步操作、多个容器及持续环境反馈。验证脚本针对最终产物或环境状态生成数值 reward（常见为通过/失败）；评测重心是结果，而不是是否采用某个指定过程。任务配置中可设 agent、verifier 超时和 CPU、内存、存储、GPU 等资源。单个任务可通过 Harbor 的 `-t/--task` 形式运行，也可用数据集筛选参数控制任务范围。失败由 verifier reward 判定；运行错误、超时、模型拒答、输出 token 超限和测试未通过是不同失败来源，分析时应分开记录。

**真实任务示例：`layout-config-recreation2`。** Hub 中的指令要求 Agent 查看 `/app/data/layout.png` 和 `/app/data/components/` 下的图像素材，逆向还原画布上的元素、层级、位置、文字和样式，将配置写到 `/app/output/config.json`；渲染结果须与原图至少 98% 像素一致。其 task 配置声明了输出 artifact，agent timeout 为 8 小时，环境与 verifier 分别设置 CPU/内存，且 verifier 使用独立环境。这需要视觉观察、文件检查、生成配置、渲染与反复调试，评分来自自动验证，而非自由文本判断。([任务指令](https://hub.harborframework.com/tasks/terminal-bench/layout-config-recreation2/latest/files/instruction.md)、[任务配置](https://hub.harborframework.com/tasks/terminal-bench/layout-config-recreation2/latest/files/task.toml))

Harbor 会保存 trial 的 agent、verifier、配置及轨迹文件。Viewer 可逐 trial 查看 reward、cost、耗时、轨迹与文本文件；若 Agent 输出 ATIF 轨迹，可检查序列化的消息、工具调用和工具结果。可见性取决于 Agent 适配器实际记录的内容：不能假设每个 Agent 都提供完整、逐 token 的内部推理，也不应将“轨迹可查看”理解为所有私有推理链均可见。([任务格式](https://docs.harborframework.com/tasks/overview)、[结果查看](https://docs.harborframework.com/results/view-job-results)、[ATIF](https://docs.harborframework.com/agents/atif))

## 3. 4.0 版本及实验可信度

截至调研日期，官网新闻页、Harbor Hub 4.0 页面和 GitHub release 均指向 Terminal-Bench 4.0/4.0.0；Hub 显示 66 个任务。4.0 从 3.0 删除 8 项任务：2 项已饱和、2 项拒答、2 项公开解法、2 项质量或平台兼容性未解决；修复了 19 项任务。官方将所有任务 agent timeout 调至 8 小时，并校准时间、CPU、内存资源。所谓“饱和”是最新一代模型各类模型家族对某项任务均达到 5/5 成功，任务不再有区分度。([4.0 说明](https://www.tbench.ai/news/terminal-bench-4-0)、[4.0 release](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0)、[Harbor Hub 数据集](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4))

资源校准降低了 Agent 只是因为容器资源不足而失败的概率，但不能保证环境完全确定。环境不稳定是镜像依赖、沙箱实现、GPU 可用性、外部服务、网络或测试脚本造成的波动；Agent 随机性则来自模型采样、工具决策及执行差异。二者需要分别通过 Oracle/参考解稳定性检查、多次 trial 和错误分类来识别。即使路线正确，资源不足、GPU 型号不兼容、构建失败、超时或 verifier 缺陷也可能导致失败。4.0 修改了任务集合和资源配置，属于可能改变成绩的变更；比较结果应固定 `@4.0.0`、Harbor 版本、模型及参数。后续主版本/任务与 agent 环境变更需要重跑；verifier 修订也可能改变评分。不要混比 2.x、3.0 与 4.0 的绝对分数。

## 4. Harbor 的作用、运行与产物

Harbor 是 Agent 评测和优化框架，也承担 Harness/调度层职责：解析任务或数据集、准备沙箱、启动已集成或自定义 Agent、运行 verifier、聚合 trial、记录配置和轨迹。它不等于 Terminal-Bench 数据集，也不是 Agent 或 LLM 本身。当前文档列有 Claude Code、Codex、OpenHands、Gemini CLI、Qwen Coder、SWE-Agent、Terminus-2 等多种预集成 Agent；具体可用项随 Harbor 版本和认证要求变化。([预集成 Agent 清单](https://docs.harborframework.com/agents/pre-integrated-agents))

Harbor 支持自定义 Agent。若 Agent CLI 可装入任务环境，可实现 `BaseInstalledAgent`；若 Agent 循环由 Harbor 进程在外部运行、通过 `BaseEnvironment` 操作沙箱，则实现 `BaseAgent`。类可通过 `module.path:ClassName` 注册式调用，需按接口实现安装/配置、执行和上下文处理。自定义 Agent 接入不是把现有问答脚本名称传给 CLI 就能完成，必须实现终端循环并适配日志/轨迹格式。([自定义 Agent 接口](https://docs.harborframework.com/agents/custom-agents))

**官方基础命令（本报告不执行）：**

```bash
uv tool install 'harbor[modal]'
harbor run -d terminal-bench/terminal-bench@4.0.0 \
  -e modal \
  -a claude-code \
  -m anthropic/claude-sonnet-5 \
  -k 5
harbor view jobs
```

`-d` 选择并固定数据集版本，`-e modal` 指定运行沙箱，`-a` 指定 Agent，`-m` 指定模型，`-k 5` 请求每任务 5 次尝试；`harbor view jobs` 打开本地结果查看器。运行指南明确写了 4.0 数据含 GPU 任务，并建议使用有 GPU 的沙箱；其排行榜实验采用 Modal。Hub 数据集页同时展示了 `--agent/--model/--n-concurrent` 形式且推荐 Modal 或 Daytona，说明网页示例存在版本/更新差异。应以选定 Harbor CLI 的 `harbor run --help`、锁定的数据集版本和 4.0 官网指南为准，勿混用不兼容的旧命令。若只试少数任务，使用任务选择参数，或 Harbor Hub 的单任务 selector，并先将并发和尝试数设低；具体筛选旗标按安装版本 CLI 校验。([4.0 运行指南](https://www.tbench.ai/run)、[Harbor 运行作业文档](https://docs.harborframework.com/jobs/run-a-job))

Harbor 支持本地 Docker/Podman，也支持 Modal、Daytona 等远程沙箱；框架兼容 GPU 的环境并不意味着每个 benchmark 的每项任务都可在任意本机 Docker 配置运行。4.0 的 GPU 与多容器任务是重要限制，Windows 本机不是推荐基准环境；实验室 Linux GPU 服务器可作为候选，但需先验证 Docker daemon/容器权限、Compose 或多容器能力、GPU runtime/驱动、镜像构建和挂载、网络策略及并发资源。官方网页没有提供完整任务级 GPU 清单在静态页面上，必须在选中数据集中检查 task 配置。GPU 需求是沙箱侧任务环境要求，不等于 Agent 模型必须本地跑 GPU。([沙箱能力矩阵](https://docs.harborframework.com/sandboxes/pre-integrated-sandboxes))

调用 API 模型需要相应供应商凭据和网络连接；运行 Modal/Daytona 还需其账户与 sandbox 凭据。密钥应通过环境变量或 Harbor secret 机制注入，不应写在报告、任务或公开配置中。本地部署模型可以避免逐 token 供应商费用，但需要推理服务、显存和模型兼容适配；API 方案减少模型运维，但成本与速率限制取决于模型和使用量。不能根据官方榜单倒推我们自己的费用。估算可用：`总费用 ≈ Σ任务 trial 的输入/输出 token 费用 + Σ沙箱运行时长 × 对应资源单价 + 构建/存储费用`。先跑少量任务记录 token、运行时长和失败分类，再估完整矩阵；8 小时是上限配置，不是每项任务的预计耗时。

## 5. 与问答 baseline 的差异和迁移

当前可见代码抽查范围是工作区内的 `qwen3.5-9b`、`qwen3.5-27b` 问答实现。CoT 的 GPQA 模块负责构造问题提示、解析最终 A—D 答案并统计准确率；Self-Refine 将流程分成 initial、feedback、refinement 阶段，反馈后至多再生成一次答案。可见代码没有环境观察、终端工具调用、任务持续状态或 Harbor 适配接口。该检查只能描述这两个可读实现，不能代表所有 baseline，也不声称做过运行实验。代码位置：`D:\经验（利用）\第一次复现\ysc_experience_learning\qwen3.5-9b\cot\gpqa\src\gpqa_cot.py` 与 `D:\经验（利用）\第一次复现\ysc_experience_learning\qwen3.5-9b\self_refine\gpqa\src\gpqa_self_refine.py`。

| 方法名称 | 对终端任务的迁移判断 |
|---|---|
| Vanilla | 若指无额外方法的单轮问答，可作 prompt 基线但不能独立完成终端交互；需放入统一 Agent 循环。具体实现需核对。 |
| CoT | 可作为 Agent 决策提示策略之一；现有可见问答实现只产出答案，不等于能调用终端。 |
| Self-Refine | 可见版本是答案反馈/改写管线，不管理终端状态；需重新定义反馈来源、迭代边界并控制多次调用预算。 |
| Trajectory Exp. | 需核实轨迹格式、经验抽取与注入接口；名称不足以判断能否处理工具轨迹。 |
| AWM | 需核实本地实现与论文/配置；不能由缩写推定 Agent 接口。 |
| ReasoningBank | 需核实其经验读写机制、轨迹表示和调用时机；名字不证明可直接接入 Harbor。 |
| DC-Cu、DC-RS | 两者均需核实具体代码和算法边界；不得据名称推断其行动或检索能力。 |
| CA3Mem | 需核实记忆更新、检索所需字段和任务粒度；不能确认可直接迁移。 |
| AdaMem-Low、AdaMem-High | 需核实 Low/High 在现有实验中具体控制什么，以及其与多步状态的连接方式；不能仅按名称解释算法。 |

其余方法实现在当前读取范围中没有找到足以确认的代码证据，建议在后续迁移前逐一映射到可执行入口、提示模板、记忆读写点、模型调用数和输入/输出字段。基础 Agent 系统需要提供终端执行、观察—决策—执行循环、状态与任务终止管理、超时/错误处理、轨迹记录、Harbor 生命周期接口和 verifier 结果处理。经验方法层只负责经验表示、构建、检索、过滤、注入或更新策略；不能把这些职责混为“方法本身”。

公平比较应共用模型版本与推理参数、Agent Harness、系统提示（除方法变量）、工具权限、任务/数据集版本、初始镜像、CPU/GPU/内存、超时、并发及重试。只改变预先声明的经验机制。多次 trial 后报告成功率、区间、token/API 调用数、耗时和成本。不同模型、Harness、沙箱或工具配置的排行榜成绩不能归因为经验策略带来的收益。

## 6. 经验机制接入与信息泄漏控制

经验可以在任务开始时检索一次，也可以根据步骤数、失败信号或环境状态再检索；还可以先从成功历史提炼策略，再在行动时提供简短操作建议。这些是设计选项，不代表 ReasoningBank、AdaMem 或其他方法当前实现已经如此。Harbor 可查看并保存轨迹，ATIF 提供跨 Agent 的结构化轨迹格式；但经验库应保存经筛选的任务状态、动作、结果、失败教训和适用条件，而非盲目拼接整段长轨迹。([Harbor 轨迹格式](https://docs.harborframework.com/agents/atif)、[轨迹加载](https://docs.harborframework.com/jobs/loading-trajectories))

原来为 GPQA/AIME 等问答任务构建的经验，多是题目理解、解题提示或文本答案，不包含 shell 命令语义、目录结构、进程反馈、依赖安装和错误恢复信息，不能默认适用于终端任务。要研究终端经验，应先运行基础 Agent 并保存成功与失败 trial，再从训练/经验构建任务的交互轨迹抽取可复用经验。按任务或相似模板划分经验构建集与最终测试集；测试任务的标准解、参考 solution、verifier 内容和测试成功轨迹不得进入经验库。对可能存在的相似任务还需审查近重复，确保不是泄漏具体输出。

经验库可从训练任务的人工策略、公开通用操作经验或已完成的构建集 trial 初始化，并清楚标注来源。对比组应控制额外上下文 token、模型调用次数与成本，报告检索内容；增加“等 token 的无关/随机经验”或“不相关经验”对照，可判断收益来自信息相关性，而非单纯多给上下文。另测错误经验干扰和跨任务泛化。构建该评测协议有研究价值，但不应阻塞当前 baseline 复现。

## 7. 分阶段实验路线

| 阶段 | 工作与产出 | 前置确认、困难与进入标准 |
|---|---|---|
| 一：环境验证 | 核对 Harbor/容器/GPU/账户要求，锁定 Harbor 与 TB 4.0.0；根据 task 配置挑少量 CPU 与 GPU/多容器代表任务，形成环境清单。 | 确认服务器 Docker/Compose、GPU runtime、沙箱权限和 API/云端预算；先运行 Oracle/参考解检查环境可用。Oracle 可重复通过、镜像成功构建并确认轨迹输出后进入下一步。 |
| 二：基础 Agent | 选一个团队能稳定调用的 Agent 与模型，在小任务子集运行低并发、少量重复；保存每 trial reward、轨迹、成本和失败分类。 | 预先固定模型、权限和预算；成本随调用和沙箱增长。能够稳定生成可检查结果，且主要失败可归类后再接记忆机制。 |
| 三：适配一个经验方法 | 优先选代码可读、已有实现、可在同一 Agent 决策回路读经验的方法；通过 Harbor 自定义 Agent 或统一底座接入，先做固定模型/任务的对照。 | 前置确认方法实现与许可证、经验格式和构建集隔离。关键判据是没有测试泄漏，能按设计检索并记录成本，且对照只改变经验机制。 |
| 四：扩大 baseline | 在前期接口稳定后，逐项迁移余下方法；统一配置开展正式评测与重复试验。 | 各方法需有可复核实现和消融定义；若 Harness、模型或预算不一致，先暂停跨方法归因。 |

本路线不设无依据的工期。阶段三选哪个方法，应根据本地代码核查结果和导师对研究主张的优先级决定，而不是先按名称选定。

## 8. 对后续 benchmark 构造研究的启发

Terminal-Bench 的隔离环境、任务级资源声明、结果导向 verifier、版本发布与任务维护流程可作为未来构造 benchmark 的工程参考。我们的研究问题还要分层：一是 Agent 是否完成任务；二是其是否从历史经验获益；三是经验能否跨任务泛化；四是错误或无关经验是否造成干扰。后续可在基础任务集上设置经验构建/测试划分、关联与不相关经验条件，并保证 verifier 不泄漏参考解。该方向值得保留，但当前重点仍是既有 baseline 的复现与适配。

## 9. 汇报结论与待导师确认

1. **是否适合研究？** 适合，尤其可把经验利用从静态问答推进到终端工具使用和多步反馈场景；它测的是系统级能力。
2. **是否纳入新 benchmark？** 建议纳入小规模探索性实验，锁定 Terminal-Bench 4.0.0；待基础 Agent 和服务器环境可行后再决定是否作为正式主 benchmark。
3. **问答 baseline 是否容易迁移？** 不容易直接迁移。当前可见 CoT/Self-Refine 代码是文本问答管线，没有终端交互层；经验方法代码还需逐一核对。
4. **最大技术难点？** 在相同 Agent/Harness 下实现可控的终端行动循环，并把经验读取/更新嵌入其中，同时避免经验泄漏、成本差异和基础 Agent 差异造成混淆。
5. **现阶段先做什么？** 确认可用 Linux/GPU 沙箱和预算，锁定 Harbor 版本与数据集，在少数任务先检查 Oracle，再跑一个基础 Agent 并留存轨迹；不启动完整 benchmark。
6. **需导师确认？** 选择 API 还是本地模型；允许的云端沙箱与预算；Terminal-Bench 是探索集还是正式对比集；先迁移哪种已实现经验方法；经验库是否仅使用 TB 训练划分，及目标重复次数/成本边界。

## 参考资料

- [Terminal-Bench 官网](https://www.tbench.ai/)
- [Terminal-Bench 4.0 运行指南](https://www.tbench.ai/run)
- [Terminal-Bench 4.0 版本说明](https://www.tbench.ai/news/terminal-bench-4-0)
- [Terminal-Bench GitHub 仓库](https://github.com/harbor-framework/terminal-bench)
- [Terminal-Bench v4.0.0 Release](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0)
- [Harbor GitHub 仓库](https://github.com/harbor-framework/harbor)
- [Harbor Hub：Terminal-Bench 4](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4)
- [Harbor 任务格式](https://docs.harborframework.com/tasks/overview)、[作业运行](https://docs.harborframework.com/jobs/run-a-job)、[自定义 Agent](https://docs.harborframework.com/agents/custom-agents)、[结果查看](https://docs.harborframework.com/results/view-job-results)、[预集成沙箱](https://docs.harborframework.com/sandboxes/pre-integrated-sandboxes)
- [Harbor ATIF 轨迹规范](https://docs.harborframework.com/agents/atif)

> 本报告基于上述公开资料与工作区只读代码抽查整理；未运行 Terminal-Bench、未调用付费模型，也未修改现有项目代码。文中引用官网对版本/命令的记录；实际执行前应以固定版本 Harbor CLI 的 `--help` 和任务配置复核。
