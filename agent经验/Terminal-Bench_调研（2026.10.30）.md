
## 摘要

Terminal-Bench 4.0 是一个以终端和容器环境为载体、由自动测试判断任务是否完成的 Agent benchmark。它考查的是“底层模型 + Agent Harness + 工具权限与环境 + 任务”的组合能力，不是脱离执行框架的纯模型问答分数。官方将其作为持续维护的 benchmark；目前，正式数据集为 4.0.0，包含 66 个任务，agent timeout 统一为 8 小时。

它适合扩展我们对多步工具使用的研究，Harbor 支持预集成和自定义 Agent，因而接入在工程上可行；真正工作量在于构建统一的终端 Agent 底座、接通经验读写、控制工具与预算、并防止测试轨迹泄漏。建议先固定版本和模型，使用少量代表性任务做基础 Agent 可行性验证，再接入一种实现明确的经验方法。

## 1. Terminal-Bench 是什么

Terminal-Bench 目标是衡量 Agent 在多样、困难的终端任务中的工作能力。

普通问答 benchmark 通常输入问题、生成文本答案，再与标准答案比较；Terminal-Bench 则把 Agent 放进隔离环境，要求它读取文件、运行命令、观察返回结果、根据错误继续修正，并通过环境状态满足 verifier。应用覆盖代码与软件工程、机器学习/数据处理、科学计算、运维、安全、设计与媒体等终端工作流。评测对象因此是**Agent 系统整体**；如要分析模型贡献，必须固定 Harness、工具和资源。

官网排行榜的 Resolution Rate 是任务通过率（图示含 95% 置信区间）；Tokens 表示运行记录的 token 用量，Cost 表示记录或估算的模型/API成本。它们受模型、Agent、推理设置、重试和各自记录口径共同影响，不能把某个榜单分数单独解释为基础模型能力。

## 2. 任务设计与验证机制

Harbor 的标准任务目录包含 `instruction.md`、`task.toml`、`environment/`（如 Dockerfile）、`solution/`（参考解）和 `tests/`（验证脚本）。Agent 接收任务指令并在被配置的容器/沙箱中执行命令；任务可有多步操作、多个容器及持续环境反馈。验证脚本针对最终产物或环境状态生成数值 reward（常见为通过/失败）；评测重心是结果，而不是是否采用某个指定过程。任务配置中可设 agent、verifier 超时和 CPU、内存、存储、GPU 等资源。单个任务可通过 Harbor 的 `-t/--task` 形式运行，也可用数据集筛选参数控制任务范围。失败由 verifier reward 判定；运行错误、超时、模型拒答、输出 token 超限和测试未通过是不同失败来源，分析时应分开记录。

**真实任务示例：`layout-config-recreation2`。** Hub 中的指令要求 Agent 查看 `/app/data/layout.png` 和 `/app/data/components/` 下的图像素材，逆向还原画布上的元素、层级、位置、文字和样式，将配置写到 `/app/output/config.json`；渲染结果须与原图至少 98% 像素一致。其 task 配置声明了输出 artifact，agent timeout 为 8 小时，环境与 verifier 分别设置 CPU/内存，且 verifier 使用独立环境。这需要视觉观察、文件检查、生成配置、渲染与反复调试，评分来自自动验证，而非自由文本判断。([任务指令](https://hub.harborframework.com/tasks/terminal-bench/layout-config-recreation2/latest/files/instruction.md)、[任务配置](https://hub.harborframework.com/tasks/terminal-bench/layout-config-recreation2/latest/files/task.toml))

Harbor 会保存 trial 的 agent、verifier、配置及轨迹文件。Viewer 可逐 trial 查看 reward、cost、耗时、轨迹与文本文件；若 Agent 输出 ATIF 轨迹，可检查序列化的消息、工具调用和工具结果。可见性取决于 Agent 适配器实际记录的内容：不能假设每个 Agent 都提供完整、逐 token 的内部推理，也不应将“轨迹可查看”理解为所有私有推理链均可见。([任务格式](https://docs.harborframework.com/tasks/overview)、[结果查看](https://docs.harborframework.com/results/view-job-results)、[ATIF](https://docs.harborframework.com/agents/atif))


## 4. Harbor 的作用、运行与产物

Harbor 是 Agent 评测和优化框架，也承担 Harness/调度层职责：解析任务或数据集、准备沙箱、启动已集成或自定义 Agent、运行 verifier、聚合 trial、记录配置和轨迹。它不等于 Terminal-Bench 数据集，也不是 Agent 或 LLM 本身。当前文档列有 Claude Code、Codex、OpenHands、Gemini CLI、Qwen Coder、SWE-Agent、Terminus-2 等多种预集成 Agent；具体可用项随 Harbor 版本和认证要求变化。

Harbor 支持自定义 Agent。若 Agent CLI 可装入任务环境，可实现 `BaseInstalledAgent`；若 Agent 循环由 Harbor 进程在外部运行、通过 `BaseEnvironment` 操作沙箱，则实现 `BaseAgent`。类可通过 `module.path:ClassName` 注册式调用，需按接口实现安装/配置、执行和上下文处理。自定义 Agent 接入不是把现有问答脚本名称传给 CLI 就能完成，必须实现终端循环并适配日志/轨迹格式。

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

`-d` 选择并固定数据集版本，`-e modal` 指定运行沙箱，`-a` 指定 Agent，`-m` 指定模型，`-k 5` 请求每任务 5 次尝试；`harbor view jobs` 打开本地结果查看器。运行指南明确写了 4.0 数据含 GPU 任务，并建议使用有 GPU 的沙箱；其排行榜实验采用 Modal。Hub 数据集页同时展示了 `--agent/--model/--n-concurrent` 形式且推荐 Modal 或 Daytona，说明网页示例存在版本/更新差异。应以选定 Harbor CLI 的 `harbor run --help`、锁定的数据集版本和 4.0 官网指南为准，勿混用不兼容的旧命令。若只试少数任务，使用任务选择参数，或 Harbor Hub 的单任务 selector，并先将并发和尝试数设低；具体筛选旗标按安装版本 CLI 校验。([4.0 运行指南](https://www.tbench.ai/run)、[Harbor 运行作业文档](https://docs.harborframework.com/jobs/run-a-job))

Harbor 支持本地 Docker/Podman，也支持 Modal、Daytona 等远程沙箱；框架兼容 GPU 的环境并不意味着每个 benchmark 的每项任务都可在任意本机 Docker 配置运行。4.0 的 GPU 与多容器任务是重要限制，Windows 本机不是推荐基准环境；实验室 Linux GPU 服务器可作为候选，但需先验证 Docker daemon/容器权限、Compose 或多容器能力、GPU runtime/驱动、镜像构建和挂载、网络策略及并发资源。官方网页没有提供完整任务级 GPU 清单在静态页面上，必须在选中数据集中检查 task 配置。GPU 需求是沙箱侧任务环境要求，不等于 Agent 模型必须本地跑 GPU。([沙箱能力矩阵](https://docs.harborframework.com/sandboxes/pre-integrated-sandboxes))

调用 API 模型需要相应供应商凭据和网络连接；运行 Modal/Daytona 还需其账户与 sandbox 凭据。密钥应通过环境变量或 Harbor secret 机制注入，不应写在报告、任务或公开配置中。本地部署模型可以避免逐 token 供应商费用，但需要推理服务、显存和模型兼容适配；API 方案减少模型运维，但成本与速率限制取决于模型和使用量。不能根据官方榜单倒推我们自己的费用。估算可用：`总费用 ≈ Σ任务 trial 的输入/输出 token 费用 + Σ沙箱运行时长 × 对应资源单价 + 构建/存储费用`。先跑少量任务记录 token、运行时长和失败分类，再估完整矩阵；8 小时是上限配置，不是每项任务的预计耗时。

## 6. 经验机制接入与信息泄漏控制

经验可以在任务开始时检索一次，也可以根据步骤数、失败信号或环境状态再检索；还可以先从成功历史提炼策略，再在行动时提供简短操作建议。这些是设计选项，不代表 ReasoningBank、AdaMem 或其他方法当前实现已经如此。Harbor 可查看并保存轨迹，ATIF 提供跨 Agent 的结构化轨迹格式；但经验库应保存经筛选的任务状态、动作、结果、失败教训和适用条件，而非盲目拼接整段长轨迹。

原来为 GPQA/AIME 等问答任务构建的经验，多是题目理解、解题提示或文本答案，不包含 shell 命令语义、目录结构、进程反馈、依赖安装和错误恢复信息，不能默认适用于终端任务。要研究终端经验，应先运行基础 Agent 并保存成功与失败 trial，再从训练/经验构建任务的交互轨迹抽取可复用经验。按任务或相似模板划分经验构建集与最终测试集；测试任务的标准解、参考 solution、verifier 内容和测试成功轨迹不得进入经验库。对可能存在的相似任务还需审查近重复，确保不是泄漏具体输出。

经验库可从训练任务的人工策略、公开通用操作经验或已完成的构建集 trial 初始化，并清楚标注来源。对比组应控制额外上下文 token、模型调用次数与成本，报告检索内容；增加“等 token 的无关/随机经验”或“不相关经验”对照，可判断收益来自信息相关性，而非单纯多给上下文。另测错误经验干扰和跨任务泛化。构建该评测协议有研究价值，但不应阻塞当前 baseline 复现。

## 7. 分阶段实验路线

| 阶段            | 工作与产出                                                                              |
| ------------- | ---------------------------------------------------------------------------------- |
| 一：环境验证        | 核对 Harbor/容器/GPU/账户要求，锁定 Harbor 与 TB 4.0.0；根据 task 配置挑少量 CPU 与 GPU/多容器代表任务，形成环境清单。 |
| 二：基础 Agent    | 选一个团队能稳定调用的 Agent 与模型，在小任务子集运行低并发、少量重复；保存每 trial reward、轨迹、成本和失败分类。                |
| 三：适配一个经验方法    | 优先选代码可读、已有实现、可在同一 Agent 决策回路读经验的方法；通过 Harbor 自定义 Agent 或统一底座接入，先做固定模型/任务的对照。       |
| 四：扩大 baseline | 在前期接口稳定后，逐项迁移余下方法；统一配置开展正式评测与重复试验。                                                 |


## 9. 汇报结论与待导师确认

1. **是否适合研究？** 适合，尤其可把经验利用从静态问答推进到终端工具使用和多步反馈场景；它测的是系统级能力。
2. **是否纳入新 benchmark？** 建议纳入小规模探索性实验，锁定 Terminal-Bench 4.0.0；待基础 Agent 和服务器环境可行后再决定是否作为正式主 benchmark。
3. **问答 baseline 是否容易迁移？** 不容易直接迁移。当前可见 CoT/Self-Refine 代码是文本问答管线，没有终端交互层；经验方法代码还需逐一核对。
4. **最大技术难点？** 在相同 Agent/Harness 下实现可控的终端行动循环，并把经验读取/更新嵌入其中，同时避免经验泄漏、成本差异和基础 Agent 差异造成混淆。
5. **现阶段先做什么？** 确认可用 Linux/GPU 沙箱和预算，锁定 Harbor 版本与数据集，在少数任务先检查 Oracle，再跑一个基础 Agent 并留存轨迹；不启动完整 benchmark。
6. **需导师确认？** 选择 API 还是本地模型；允许的云端沙箱与预算；Terminal-Bench 是探索集还是正式对比集；先迁移哪种已实现经验方法；经验库是否仅使用 TB 训练划分，及目标重复次数/成本边界。

