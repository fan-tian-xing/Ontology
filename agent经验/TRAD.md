
## 1. TRAD 方法

1. **离线准备专家经验。** 从少量专家步骤开始，人工编写 Thought 作为 few-shot 示例。标注模型根据任务、已执行历史、当前观察和该步专家动作生成 Pseudo-Golden Thought。经验库保留完整轨迹，并给每个可决策步骤的 Thought 建立向量索引。专家动作只在离线标注与历史示例中可见。
2. **每局检索一次完整轨迹。** 官方 ALFWorld 实现在 reset 后，用「初始观察 + 任务描述」检索同任务类型的专家轨迹。命中的完整轨迹作为本局 Thought 生成的示例。每次生成 Thought 时，再加入当前观察及本局已执行的历史。
3. **每步检索相关经验。** 单独编码当前 Thought，与同任务类型的历史 Thought 计算余弦相似度，从高到低选出来自不同轨迹的 Top-K 步骤。检索结果保留轨迹 ID 和步索引，供后续按原轨迹取相邻步骤。
4. **对齐经验并生成动作。** Temporal Expansion（TE）从每个命中步向前取 B 步、向后取 F 步，遇到边界时裁剪。Relative Order Mark（ROM）以命中步为 Step 0，标记其余步骤的相对位置。History Alignment（HA）在 Action 提示中加入当前任务最近 B+F 个已执行步骤。官方 ALFWorld 实现还把当前观察和当前 Thought 交给模型生成 Action，执行后进入下一轮。正常情况下，每个环境步需要两次生成请求。

两级检索承担不同职责。轨迹级示例帮助模型理解当前进度并生成 Thought，步骤级示例帮助模型选择当前动作。当前 Thought 由模型在线生成，可能判断错误。扩展后的专家片段提供动作的前提和后续结果，帮助模型结合当前观察作出决策。详细参数列在文末。

### 论文结果

| 基准 | 论文设置 | 任务成功率 |
| --- | --- | --- |
| ALFWorld | GPT-4，2 个上下文示例，134 个 OOD 任务，三次平均 | TRAD **96.77%**，Synapse 89.55%，Synapse + ReAct 93.78% |
| Mind2Web | GPT-3.5-turbo，3 个上下文示例，汇总三个测试子集 | TRAD **2.1%**，Synapse 1.6% |


## 2. 项目统一实验设置

| 项目    | 设置                                                                                                                                                                          |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 环境    | ALFWorld 用 TextWorld PDDL 纯文字版，WebShop 用 text 模式。                                                                                                                           |
| 模型    | Qwen3.5-27B、Qwen3.5-9B 各自独立比较。相同模型下各方法使用同一服务配置。                                                                                                                             |
| 生成设置  | `temperature=0.0`、`top_p=1.0`、`enable_thinking=false`。沿用现有代码的 `max_tokens=4096` **每次生成请求**口径，TRAD 的 Thought 和 Action 各是一个请求。关闭模型思考模式时，TRAD 的 Thought 仍由普通文本生成。              |
| 环境步数  | ALFWorld 每个 episode 最多 50 个环境动作，WebShop 最多 15 个。TRAD 的 Thought 与检索都在同一次环境动作之前完成。Self-Refine 的两轮各有自己的上限。                                                                     |
| 动作提示  | 复用项目的 ReAct 提示词结构，包括任务、当前进度、近期历史、当前观察和 admissible actions。Action 输出采用单个 `<action>…</action>` 标签对。                                                                           |
| 动作回退  | ALFWorld 与现有两种方法一样，标签解析失败时直接提交 `response_text[-30:].lower()`。WebShop 沿用 `response_text.lower()[-20:]`，仅当后缀可解析且环境允许时执行，否则页面保持、`reward=0`、`done=False`。合法标签内的文本仍按现有解析和环境行为处理。 |
| 重复与评分 | 每个模型、方法、评测 split 在同一任务清单上跑三次并报告平均。ALFWorld 报官方任务成功率，WebShop 报成功率与平均奖励分数，并明确分数尺度。                                                                                            |
| 成本统计  | 逐请求保存输入、输出 token 及缺失情况。TRAD 分别汇总 Thought、Action，再合计每任务在线成本。离线标注与 Embedding 单独计账。Self-Refine 同时报两轮合计成本和第二轮成功率。                                                               |

ALFWorld 在线评测沿用现有 `evaluate_dagger` 适配器，以官方 `res_points` 计分，并核对 `won`。到达步数上限的正常失败计入分母。服务或环境异常按现有重试、续跑口径处理，未完成整套任务时保留待完成状态。WebShop 的现有适配器执行官方 `baseline_models/test.py` 中的 `episode`，按满奖励判成功，报告中区分原始奖励和百分制分数。

### 数据和隔离

- 数据采用已有的数据集。
- ALFWorld 从 `alfworld/data/json_2.1.1/train_2000` 构库，分开评测 `valid_seen` 和 `valid_unseen`。按现有任务筛选规则要求支持的任务类型、`game.tw-pddl` 存在且 `solvable=true`。本地只读清点得到 **train_2000 有 2000 个合格游戏，seen 有 140 个，unseen 有 134 个**。合格游戏数与成功专家轨迹数分别统计。
- WebShop 的经验池、评测清单分别使用 `WebShop/baseline_models/data/human_goals_train_2000_split.json` 和 `WebShop/baseline_models/data/human_goals_test_split.json`，商品等数据来自 `WebShop/data`。当前 TRAD 实现目标是 ALFWorld。若后续用于 WebShop，结果单列为方法迁移。
- 两个下载仓库与数据目录按只读输入处理。轨迹、Thought、索引和运行日志写入实验输出目录。评测时只暴露任务、在线观察、动作历史和当前可选动作，walkthrough、专家计划、环境事实及评分字段仅在各自的离线构库或计分环节使用。经验库在评测前冻结，seen/unseen 的交互结果都不写回。

## 4. 实施顺序与验收

1. **先做训练专家轨迹。** 专家轨迹采用成功的轨迹。首选回放 `train_2000` 中游戏自带的 `walkthrough`，从真实纯文字环境记录初始观察和每步动作前后的观察，只有最终 `won=True` 的轨迹进入经验库。本地样本已确认含 `walkthrough` 字段，尚未验证 2000 条的回放成功率。先小样本核对动作命名、可选动作和终局，再汇总各任务类型的成功、失败和缺失数。离线回放与在线 agent 分离。
2. **补齐 Thought 并建库。** 从训练成功轨迹中挑少量步骤人工写 Thought 示例。对其余专家步骤，向标注模型提供任务、已执行的前缀、当前观察和该步专家动作，生成与该动作相符的简洁 Thought。标注阶段只给该步决策时能观察到的状态和专家动作。每个模型都需要单独建库。
3. **验证一步，再验证一局。** 检查两个命中是否来自不同训练轨迹、Step 0 是否对应检索命中、片段在开头与结尾能否正确裁剪，以及当前任务动作是否来自最终 Action 响应。用少量 seen/unseen 任务确认每个实际环境步只执行一次动作，并能追踪两次生成、检索命中和官方得分。参数检查用训练任务或训练留出集。seen/unseen 小样本仅检查接线。
4. **冻结后正式评测。** 运行两个模型各自的 seen/unseen，每组 3 次。按模型和 split 记录各次成功数/总数、三次平均成功率、相对 No-Exp 的百分点差和输入/输出 token。先完成 ALFWorld 。

## 5. ALFWorld 的 TRAD 构库与使用流程

### 5.1 抽取专家轨迹

从 `alfworld/data/json_2.1.1/train_2000` 读取每个任务的 `game.tw-pddl` 和其中的 `walkthrough`。这 2,000 个游戏都附有解题命令序列，是构库候选。

每个游戏在 TextWorld 中回放一次。`reset` 得到任务描述和初始观察，逐条执行 `walkthrough` 的动作，记录「动作前的 Observation → Action → 动作后的 Observation」。只把达到 `won=True` 的轨迹纳入经验库。保存任务 ID、任务类型、任务描述、初始观察和按步排序的观察与动作。回放无需调用 Qwen，两种模型共用这批成功的原始轨迹。

### 5.2 为专家步骤生成 Thought

从成功轨迹中挑少量步骤，手写 Thought 作为 few-shot 示例。对每个专家步骤，把任务描述、此前已执行的历史、该步动作前的观察及专家动作交给 Qwen，生成与该动作一致的 **Pseudo-Golden Thought**，并按轨迹 ID 和步号保存。Qwen3.5-27B 和 Qwen3.5-9B 分别生成 Thought、建立各自的经验库。

使用官方 ALFWorld 的 `sentence-transformers/all-MiniLM-L6-v2` 建立两个余弦检索索引。轨迹索引用「初始观察 + 任务描述」，步骤索引只用该步 Thought。

### 5.3 评测时检索与使用经验

1. **每局开始检索一次轨迹，Top-K = 2。** 用当前任务的初始观察和任务描述，从同任务类型的训练经验库检索两条完整专家轨迹，作为本局生成 Thought 的示例。
2. **每步生成当前 Thought，使用本局完整的已执行历史。** 输入两条专家轨迹、当前任务、当前观察，以及本局之前每步的 Observation、Thought 和 Action。首步无历史，第 50 步最多可见前 49 步。
3. **用当前 Thought 检索专家步骤，Top-K = 2。** 只对当前 Thought 编码，在同任务类型的步骤索引里按余弦相似度选两个命中，每条专家轨迹最多命中一步。
4. **扩展片段并生成 Action。** 取 **B = 1、F = 2**，也就是命中步之前 1 步、之后 2 步。每条专家示例最多 4 步，按 `[Step -1]`、`[Step 0]`、`[Step 1]`、`[Step 2]` 标记，轨迹边界处只取已有步骤。Action 提示包含两个专家片段、当前任务、当前观察、当前 Thought、可选动作，以及本局最近 **B + F = 3** 个已执行步骤，历史不足时全部保留。按项目的 `<action>…</action>` 规则解析并执行，然后进入下一步。

两阶段的模型配置、动作回退、50 步上限和评分沿用第 2 节。两个示例、Thought 检索和历史对齐依据论文，具体的 B/F 与两个阶段的历史范围按官方 ALFWorld 复现实验实现。 [论文第 3 节、第 4.1 节](https://doi.org/10.1145/3626772.3657788) · [官方 ALFWorld README](https://github.com/SkyRiver-2000/TRAD-Official/tree/main/ALFWorld#readme) · [运行代码](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/run_trad.py) · [检索代码](https://github.com/SkyRiver-2000/TRAD-Official/blob/main/ALFWorld/thought_retrieval.py)
