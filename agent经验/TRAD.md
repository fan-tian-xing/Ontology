# TRAD 在 ALFWorld 的方法复现

目标是在现有长程纯文字 benchmark 框架中加入 TRAD，分别测量 Qwen3.5-27B 和 Qwen3.5-9B 在 ALFWorld seen、unseen 上的任务成功率和 token 开销，并与同设置下的 No-Exp、Self-Refine 比较。正文约定项目实验口径，末尾列出沿用的 TRAD 方法细节和参数。

## 1. 论文笔记核对

原总结对主流程的理解是正确的。TRAD 离线用专家动作标注 Pseudo-Golden Thought，在线先生成当前 Thought，再以 Thought 为键做步骤级检索，最后用带时间信息的专家片段辅助动作决策。决策 LLM 通过上下文示例使用经验，无需微调。以下几点会直接影响实现。

| 核对项 | 复现时的口径 |
| --- | --- |
| 轨迹级检索 | 官方 ALFWorld 实现在 reset 后检索一次，查询包含初始 Observation 和任务指令，返回的完整专家轨迹用于每一步的 Thought 生成。 |
| 步骤级检索 | 每步将当前 Thought 单独编码，按与历史 Thought 的余弦相似度选 Top-K，命中来自不同轨迹。官方 ALFWorld 的两级检索都在同任务类型的经验子库内进行。 |
| 动作输入 | 论文框架允许最终决策携带当前 Thought，官方 ALFWorld 实际携带。扩展片段可包含命中后发生的**专家**动作和观察，在线任务只能使用当前观察与已执行的历史。 |
| 历史对齐 | 最近 B+F 步用于 Action 阶段。Thought 阶段的官方实现使用当前 episode 的完整已有历史，两阶段的窗口不同。 |
| 消融范围 | 论文第 4.4 节的 TE、ROM、HA 和 B/F 消融来自 Mind2Web，向后续步骤扩展更有利的观察也来自该实验。 |
| 论文结果 | ALFWorld 的 96.77% 是 GPT-4、两个上下文示例、134 个 OOD 任务上的三次平均。Synapse 为 89.55%，Synapse + ReAct 为 93.78%。Mind2Web 的 GPT-3.5-turbo 总体任务成功率为 2.1%，Synapse 为 1.6%。WebShop 在本项目的 benchmark 范围内，论文未在 WebShop 报告 TRAD 成绩。 |

依据见论文第 3.1–3.3 节、图 2、4.1–4.4 节、表 1–3，以及官方 ALFWorld 运行代码。[SIGIR 2024 论文](https://doi.org/10.1145/3626772.3657788) · [可读论文](https://openreview.net/pdf/91133b4e8ef389a01a6bb5719c9154639f083ef3.pdf) · [官方运行脚本](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/run_trad.py)

## 2. 项目统一实验设置

| 项目 | 设置 |
| --- | --- |
| 环境 | ALFWorld 用 TextWorld PDDL 纯文字版，WebShop 用 text 模式。 |
| 模型 | Qwen3.5-27B、Qwen3.5-9B 各自独立比较。相同模型下各方法使用同一服务配置。 |
| 生成设置 | `temperature=0.0`、`top_p=1.0`、`enable_thinking=false`。沿用现有代码的 `max_tokens=4096` **每次生成请求**口径，TRAD 的 Thought 和 Action 各是一个请求。关闭模型思考模式时，TRAD 的 Thought 仍由普通文本生成。 |
| 环境步数 | ALFWorld 每个 episode 最多 50 个环境动作，WebShop 最多 15 个。TRAD 的 Thought 与检索都在同一次环境动作之前完成。Self-Refine 的两轮各有自己的上限。 |
| 动作提示 | 复用项目的 ReAct 提示词结构，包括任务、当前进度、近期历史、当前观察和 admissible actions。Action 输出采用单个 `<action>…</action>` 标签对。 |
| 动作回退 | ALFWorld 与现有两种方法一样，标签解析失败时直接提交 `response_text[-30:].lower()`。WebShop 沿用 `response_text.lower()[-20:]`，仅当后缀可解析且环境允许时执行，否则页面保持、`reward=0`、`done=False`。合法标签内的文本仍按现有解析和环境行为处理。 |
| 重复与评分 | 每个模型、方法、评测 split 在同一任务清单上跑三次并报告平均。ALFWorld 报官方任务成功率，WebShop 报成功率与平均奖励分数，并明确分数尺度。 |
| 成本统计 | 逐请求保存输入、输出 token 及缺失情况。TRAD 分别汇总 Thought、Action，再合计每任务在线成本。离线标注与 Embedding 单独计账。Self-Refine 同时报两轮合计成本和第二轮成功率。 |

ALFWorld 在线评测沿用现有 `evaluate_dagger` 适配器，以官方 `res_points` 计分，并核对 `won`。到达步数上限的正常失败计入分母。服务或环境异常按现有重试、续跑口径处理，未完成整套任务时保留待完成状态。WebShop 的现有适配器执行官方 `baseline_models/test.py` 中的 `episode`，按满奖励判成功，报告中区分原始奖励和百分制分数。

### 数据和隔离

- 服务器仓库优先用 `/data/home/liujingyao/agent_bench/alfworld`、`/data/home/liujingyao/agent_bench/WebShop`。若不可访问，使用 `/data/pretrained_models/share_project/agent_bench/` 下的对应仓库。
- ALFWorld 从 `alfworld/data/json_2.1.1/train_2000` 构库，分开评测 `valid_seen` 和 `valid_unseen`。按现有任务筛选规则要求支持的任务类型、`game.tw-pddl` 存在且 `solvable=true`。本地只读清点得到 **train_2000 有 2000 个合格游戏，seen 有 140 个，unseen 有 134 个**。合格游戏数与成功专家轨迹数分别统计。
- WebShop 的经验池、评测清单分别使用 `WebShop/baseline_models/data/human_goals_train_2000_split.json` 和 `WebShop/baseline_models/data/human_goals_test_split.json`，商品等数据来自 `WebShop/data`。当前 TRAD 实现目标是 ALFWorld。若后续用于 WebShop，结果单列为方法迁移。
- 两个下载仓库与数据目录按只读输入处理。轨迹、Thought、索引和运行日志写入实验输出目录。评测时只暴露任务、在线观察、动作历史和当前可选动作，walkthrough、专家计划、环境事实及评分字段仅在各自的离线构库或计分环节使用。经验库在评测前冻结，seen/unseen 的交互结果都不写回。

## 3. 现有 baseline 代码评估与接入

以下位置均相对于 `ysc_long_horizon_experience_learning/qwen3.5-27b`。

| 现有实现 | 核对结果与接入方式 |
| --- | --- |
| `no_exp/alfworld` | 提示词与给定 ReAct 版本一致，单轮运行，使用真实文字环境和官方评分。`history_window=50` 可覆盖本轮已执行的历史。TRAD 可复用其任务发现、环境和评分适配、模型客户端、标签解析、后缀回退、运行日志与三次汇总。 |
| `self_refine/alfworld` | 第一轮提示词与 No-Exp 一致。第一轮正常完成后始终从同一任务重新 reset，即使第一轮成功也跑第二轮。第二轮使用第一轮实际动作和对应观察，逐步反思并重新行动。传入轨迹不包含奖励、成功标志或原始模型输出，最终以第二轮评分。符合两轮设定。 |
| `no_exp/webshop` | 已使用文字环境、15 步限制、20 字符回退与官方 episode 适配。在所查目录中，Self-Refine 实现位于 ALFWorld。 |

建议后续将 TRAD 作为 ALFWorld 下的独立方法接入，复用现有执行外壳。新增逻辑集中在离线构库、两级检索和双阶段提示词。Thought 提示保留同一个任务和当前进度结构，补充完整专家示例，要求返回一段状态与下一步意图的 Thought。Action 提示保留原动作约束，追加当前 Thought 与带相对步号的专家片段，并使用 TRAD 的 History Alignment 窗口。

TRAD 与 No-Exp 的主比较回答的是「整套方法在相同环境交互预算下是否提升成功率」。两者每步生成请求数和提示历史长度不同，解读时同时报告 token 成本。

## 4. 实施顺序与验收

1. **先做训练专家轨迹。** 专家轨迹采用成功的轨迹。首选回放 `train_2000` 中游戏自带的 `walkthrough`，从真实纯文字环境记录初始观察和每步动作前后的观察，只有最终 `won=True` 的轨迹进入经验库。本地样本已确认含 `walkthrough` 字段，尚未验证 2000 条的回放成功率。先小样本核对动作命名、可选动作和终局，再汇总各任务类型的成功、失败和缺失数。离线回放与在线 agent 分离。
2. **补齐 Thought 并建库。** 从训练成功轨迹中挑少量步骤人工写 Thought 示例。对其余专家步骤，向标注模型提供任务、已执行的前缀、当前观察和该步专家动作，生成与该动作相符的简洁 Thought。标注阶段只给该步决策时能观察到的状态和专家动作。主对比可用固定的 Qwen3.5-27B 作为离线标注器，让两个决策模型共享同一经验库。这是本项目的构库选择，记录标注器、提示版本和经验库版本。
3. **验证一步，再验证一局。** 检查两个命中是否来自不同训练轨迹、Step 0 是否对应检索命中、片段在开头与结尾能否正确裁剪，以及当前任务动作是否来自最终 Action 响应。用少量 seen/unseen 任务确认每个实际环境步只执行一次动作，并能追踪两次生成、检索命中和官方得分。参数检查用训练任务或训练留出集。seen/unseen 小样本仅检查接线。
4. **冻结后正式评测。** 运行两个模型各自的 seen/unseen，每组 3 次。按模型和 split 记录各次成功数/总数、三次平均成功率、相对 No-Exp 的百分点差和输入/输出 token。先完成 ALFWorld 主对比，再决定是否扩展 WebShop。论文的 96.77% 用作历史参照。

单步日志至少保留当前任务 ID、步号、两阶段请求与 token、Thought 文本、每个命中的轨迹 ID/步号/余弦分数、扩展范围、解析状态、提交动作和环境结果。结果汇总记录实际训练库规模、各任务类型覆盖及每轮完整性。

## 5. TRAD 方法细节与固定参数

以下保留论文第 3 节的方法。论文未逐项给出 ALFWorld 的运行细节时，采用官方 ALFWorld 实现和 README 的复现实验设置。

| 设置 | ALFWorld 主实验采用 | 依据 |
| --- | --- | --- |
| Thought Preparation | 少量人工标注作为 few-shot，利用专家动作生成逐步 Pseudo-Golden Thought | 论文第 3.1 |
| 轨迹级示例数 | 2。以「初始 Observation + 任务」做密集检索，同任务类型中取最相似的两条轨迹，展示时短轨迹在前 | 论文第 4.1，官方 `run_trad.py`、`thought_retrieval.py` |
| Thought 生成历史 | 完整的当前 episode 历史，含已执行步骤的 Observation、Thought、Action；加当前 Observation | 官方 `make_prompt_thought`。项目的 50 步上限覆盖整局 |
| 步骤级 K | 2。按余弦分数从高到低选取，每条轨迹至多命中一步；展示时按命中步索引升序 | 论文第 3.2，官方 `thought_retrieval.py` |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2`。两级检索各自使用相同编码器和文本字段规则构建 query/key，向量 L2 归一化后用点积计算余弦相似度 | 官方 `thought_retrieval.py`、`build_thought_embedding.py` |
| Temporal Expansion | **B=1，F=2**。B 指命中步之前，F 指命中步之后。每条示例最多 4 个动作步骤，边界处自然裁剪，可保留片段最后一个动作之后的 Observation | 论文第 3.3，官方 ALFWorld README 与 `make_prompt` |
| Relative Order Mark | 开启。官方字面形式为 `[Step -1]`、`[Step 0]`、`[Step 1]`、`[Step 2]` | 论文第 3.3，官方 `--with_mark` |
| History Alignment | 开启。Action 输入最近 **B+F=3** 个已执行步骤，保留任务、当前 Observation 和当前 Thought；步数不足时使用已有历史 | 论文第 3.3，官方 `--with_prev` 和 `make_prompt` |
| 运行频率 | 每局 1 次轨迹检索；每个环境步 1 次 Thought 生成、1 次 Thought Embedding 检索、1 次 Action 生成，再执行 1 次环境动作 | 官方 `alfworld_run` |

`K=2、B=1、F=2` 是主实验的固定参数。官方脚本单独运行时的默认值是 `B=0、F=1`，标记和历史对齐默认关闭；复现实验使用 README 显式给出的扩展与开关。论文图 2 的 `B=F=1` 是示意配置。官方 `traj.zip` 提供预处理后的专家轨迹供原实验使用，本项目主表改用指定的 `train_2000` 构库。每条经验需要稳定的 `trajectory_id`、`task_type`、`task_description`、`initial_observation`、带 `step_idx` 的 `observation/thought/action`，以及独立保存的终局观察；只有可决策步骤进入 Thought 索引。按任务类型预检至少有两条独立成功轨迹，索引行固定映射到轨迹和步号。

```text
reset 得到 task、initial_observation
task_demos = 同任务类型下检索 2 条完整专家轨迹
for 每个未终止的环境步:
    thought = LLM(task_demos, task, 当前观察, 完整当前历史)
    hits = 同任务类型下按 thought 检索 2 个不同轨迹的步骤
    aligned_demos = 对各命中前取 1 步、后取 2 步并标相对步号
    reply = LLM(aligned_demos, task, 最近 3 步, 当前观察, thought, 可选动作)
    action = 解析 <action> 标签，解析失败时用约定后缀
    执行 action，记录环境结果与本步 Thought
```

项目适配层使用正文约定的模型、split、生成预算、可选动作提示、标签解析与官方环境评分。官方 GPT-4 脚本中的 300-token 限制、按换行停止、针对 GPT 输出的 `in/on` 字符替换和循环动作早停属于原运行外壳。项目实验沿用现有基线的动作与终止口径，检索前沿用官方对 Thought 中带空格的 ` in `、` on ` 统一为 ` in/on ` 的文本处理，并将处理后的 Thought 用于 Action 提示。

参考来源见[官方 ALFWorld README](https://github.com/SkyRiver-2000/TRAD-Official/tree/main/ALFWorld#readme) · [官方检索实现](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/thought_retrieval.py) · [官方 Thought 向量构建](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/build_thought_embedding.py) · [官方运行脚本](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/run_trad.py) · [AdaMEM 参考仓库](https://github.com/yunx-z/AdaMEM)
