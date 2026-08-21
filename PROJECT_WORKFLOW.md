# 汽轮机安装调试知识图谱问答系统：业务流程说明

## 1. 项目是做什么的

本项目把汽轮机安装调试技术资料整理成可追溯的知识图谱，并通过 LangGraph 问答流程回答现场技术问题。

系统的核心原则是：

1. 答案必须来自项目指定的正式资料，不能依靠模型自由补充工程结论。
2. 每条重要知识都要能追溯到具体页码、章节和原文证据。
3. 先检索证据，再让大模型组织语言，最后重新检查答案和引用。
4. 参数、尺寸、间隙、检查方法和操作步骤等高风险内容，证据不足时不强行作答。

当前正式数据规模：

| 数据 | 当前数量 | 含义 |
|---|---:|---|
| Graph Record（图记录） | 1022 条 | 实体之间的业务关系记录 |
| 业务实体 | 1121 个 | 文档、章节、部件、工序、步骤、参数等 |
| Evidence（证据） | 909 条 | 带页码、章节和原文的证据节点 |

正式数据文件位于：

- neo4j/data/graph_records.jsonl：图记录。
- neo4j/data/evidence.jsonl：证据。
- neo4j/data/entity_aliases.json：实体别名。
- neo4j/data/ontology_gaps.jsonl：本体缺口和待处理项。

## 2. 整体业务流程

系统分为两条主流程。

### 2.1 离线流程：把技术资料建设成知识图谱

~~~text
正式 PDF / OCR 文本
        ↓
人工复核页码、章节和原文
        ↓
建立 Evidence（证据）
        ↓
整理实体和关系
        ↓
形成 Graph Record（图记录）
        ↓
Validator（校验器）检查
        ↓
Loader（加载器）写入 Neo4j
~~~

这条流程在资料新增、资料修订或知识图谱重建时执行，不是每次问答都执行。

### 2.2 在线流程：根据证据回答用户问题

~~~text
用户问题
    ↓
问题规范化
    ↓
提取检索词并匹配实体
    ↓
从 Neo4j 检索关系和 Evidence
    ↓
判断证据是否足够
    ↓
大模型依据本次证据生成答案和 claims
    ↓
校验页码、章节、数值、单位和证据来源
    ↓
返回答案与引用
~~~

在线流程由 LangGraph 固定串联五个节点完成，详见第 7 节。

## 3. PDF 是怎样抽取成知识图谱的

### 3.1 先回答：是不是先定义一个根节点

**不是先创建一个“汽轮机根节点”，再由程序从这个节点自动向下抽取整本 PDF。**

代码中有三种不同含义的“根”，需要分开理解：

| 名称 | 是什么 | 在什么时候使用 |
|---|---|---|
| 根本体类型 | Document、Section、Component、Procedure 等顶层类型 | 阅读 PDF、归纳知识结构后冻结，约束后续抽取 |
| 文档节点 | TURBINE_MANUAL，即“汽轮机本体安装及维护说明书”这个实体 | 图谱中表示资料本身，并通过关系连接部分章节 |
| 问答根实体 | 根据当前问题选出的部件、工序或检查项 | 在线检索时使用，每个问题可能不同 |

因此，本项目的真实顺序是：

~~~text
先阅读并登记 PDF
    ↓
识别反复出现的对象、动作、参数和证据形式
    ↓
归纳“根本体类型”
    ↓
冻结节点类型、关系方向和属性白名单
    ↓
按冻结结构抽取实体、关系和 Evidence
    ↓
形成 Graph Record 并入库
~~~

根本体表示“允许使用哪些类别”，不是一组必须首先创建的具体业务节点，也不是自动抽取算法的起始数据。

### 3.2 根本体是怎么得到的

项目采用 PDF-first（从 PDF 出发）的本体设计方法，过程记录在：

- docs/ontology_extraction_framework.md
- neo4j/ontology/ontology_extraction_framework.py

具体做法：

1. 先阅读原始扫描 PDF，建立物理页、章节、图表和证据块的对应关系。
2. 从不同章节反复出现的稳定语义中归纳类别，例如部件、工序、步骤、参数、技术要求和检查项。
3. 判断一个概念应该成为独立节点，还是只作为属性。
4. 定义允许的关系以及关系方向。
5. 人工评审后，将节点类型、属性、关系和合法端点冻结在 ontology.yaml 中。

例如：

- “轴承、汽缸、阀门、管道”都归入 Component（部件），不为每种设备再创造新的节点类型。
- “安装、找中、焊接、吹管”归入 Procedure（工序）的细化方向。
- “间隙、公差、力矩、温度”归入 Parameter（参数）的细化方向。
- 数值、单位、方向、顺序通常作为属性，不随意增加节点类型。

### 3.3 正式抽取使用哪些源文件

build_corpus.py 使用三份材料，但用途不同：

| 材料 | 用途 | 是否可以成为答案证据 |
|---|---|---|
| 原始扫描 PDF：汽轮机本体安装及维护说明书.pdf | 唯一正式知识源，用于页码、图像和原文视觉复核 | 可以，是最终依据 |
| OCR 文字版 PDF：汽轮机本体安装及维护说明书_文字版.pdf | 辅助取得逐页文字，方便切分和检索 | 不能脱离原始扫描页独立作为最终依据 |
| 260814 安调处置方案.docx | 只验证四个盲测主题是否存在 | 不会复制到 Evidence、Graph Record 或回答提示词 |

正式构建脚本首先检查：

1. 原始 PDF 和 OCR 文字版是否存在。
2. 原始 PDF 是否正好为 94 个物理页。
3. OCR 文字版页数是否与原始 PDF 完全一致。
4. 计算原始 PDF 的 SHA-256，用于标识资料版本。

只要页数或资料版本不符合预期，就应停止构建，不能继续把页码错位的数据写入图谱。

### 3.4 第一道处理：逐页登记和 OCR 辅助转录

正式流程由 build_page_manifest() 逐页执行：

1. 使用人工维护的 known_pages 映射表，把 1～94 物理页对应到章节或页面说明。
2. 从 OCR 文字版的相同物理页提取文字。
3. 去掉“PDF物理页、OCR辅助阅读版”等辅助页眉和页脚。
4. 应用 OCR_VISUAL_CORRECTIONS 中经过原始扫描页核对的修订。
5. 读取原始扫描页的图像尺寸，作为 Evidence 的 bbox 定位范围。
6. 为每页建立 EV_PAGE_001～EV_PAGE_094 页级 Evidence。
7. 生成页面清单，记录物理页、章节说明、复核状态、图像尺寸和 Evidence ID。

这里的关键点是：**OCR 只负责提高文字处理效率，人工视觉复核决定文字是否可信。**不能因为 OCR 给出了某个数值，就直接把它升级成工程参数。

项目还提供 neo4j/loader/ocr_pages.py，用于需要重新做 OCR 时：

1. 把指定 PDF 页面按默认 180 DPI 转成图片，或读取已经渲染好的页面图片。
2. 使用 RapidOCR 识别每页文字和置信度。
3. 按页生成 EV_OCR_PAGE_* 临时证据块。
4. 将 section 标为 unreviewed、status 标为 pending。
5. 输出待人工审核的 ocr_chunks.jsonl。

这个脚本只生成待审页面块，不生成 Graph Record，也不写 Neo4j。审核人员必须核对原图、补充章节并把状态确认成 accepted，后续语义抽取才允许使用。

### 3.5 第二道处理：把页面文字切成可引用原文

页级 Evidence 适合定位，但一整页可能同时包含多条要求、表格行和相邻步骤，不能把整页当成一个工程结论。

build_source_clause_records() 会处理有实质内容的页面：

1. 排除封面、目录、空白页等 NON_SUBSTANTIVE_PAGES。
2. 清除固定页眉、页脚和末尾页码。
3. 按句号、分号、项目编号和换行切分。
4. 过滤过短文本、OCR 噪声和重复片段。
5. 只做裁剪和切分，不改写原文。
6. 为每个片段建立 EV_CLAUSE_Pxxx_xxx 细粒度 Evidence。
7. 建立页内容 Section 和 Fact。
8. 用 SECTION_CONTAINS 关系表达“本页包含这条原文事实”。

例如：

~~~text
TURBINE.SECTION.PAGE_CONTENT_061
    ── SECTION_CONTAINS ──>
TURBINE.FACT.P061.xxx
    + EV_CLAUSE_P061_xxx
~~~

Fact 的 statement 和对应 Evidence 的 source_text 都保存连续原文，使问答能够检索到具体句子，而不是只命中“第 61 页”。

### 3.6 第三道处理：建立业务语义记录

当前正式 graph_records.jsonl 不是单一自动抽取结果，而是四类记录合并：

| 构建函数 | 产生什么 |
|---|---|
| build_curated_records() | 人工确认的核心文档、章节、部件、工序、图表和关系锚点 |
| build_supplemental_records() | 针对具体安装、检查、参数和流程补充的业务记录 |
| build_additional_page_records() | 对续页、图示页和随机复核发现的工程事实进行细粒度补充 |
| build_source_clause_records() | 从逐页复核文字切分出的 Section → Fact 原文记录 |

建立业务记录时，维护人员先判断原文表达的业务含义：

~~~text
原文提到什么对象？       → Component
描述的是一组作业过程？   → Procedure
是过程中的单个动作？     → Step
包含数值、范围或单位？   → Parameter
表达必须满足的条件？     → Requirement
描述要检查的内容？       → InspectionItem
只是需要保留的原文事实？ → Fact
~~~

然后选择合法关系，把实体和 Evidence 组成 Graph Record。无法放入冻结类型或关系白名单的概念，进入 ontology_gaps.jsonl，不自动扩展 Schema。

### 3.7 文档节点在图谱中的作用

build_curated_records() 确实创建了一个文档实体：

~~~text
TURBINE_MANUAL
名称：汽轮机本体安装及维护说明书
页数：94
SHA-256：由原始 PDF 计算
~~~

Document 保存资料名称、页数和文件摘要，并通过 DOCUMENT_HAS_SECTION 表达文档与章节的关系。业务知识继续由 Section 连接 Procedure、Component、Requirement、InspectionItem 和 Fact。在线问答根据用户问题匹配部件、工序或检查项作为检索起点，不需要从 Document 开始逐层遍历。

### 3.8 第四道处理：归一、校验和输出

四类记录合并后，build_corpus.py 继续执行：

1. canonicalize_records() 统一重复实体的标准属性，避免记录顺序改变最终节点内容。
2. 汇总页级 Evidence、细粒度 Evidence 和人工语义 Evidence。
3. 输出 evidence.jsonl。
4. 输出 graph_records.jsonl。
5. 输出 ontology_gaps.jsonl。
6. 生成别名文件、页面结构清单和抽取覆盖报告。
7. 再由 Validator 做确定性校验。
8. 校验通过后，Loader 才能写入 Neo4j。

正式 PDF 抽取技术路线可以归纳为：

~~~mermaid
flowchart TD
    A[原始扫描 PDF<br/>唯一正式来源] --> B[94 页物理页登记和视觉复核]
    A --> C[OCR 文字版<br/>辅助转录]
    C --> B
    B --> D[页级 Evidence]
    B --> E[归纳并冻结根本体]
    D --> F[切分连续原文]
    F --> G[细粒度 Evidence 与 Fact]
    E --> H[人工核心记录和补充记录]
    D --> H
    G --> I[合并 Graph Records]
    H --> I
    I --> J[实体归一]
    J --> K[Validator]
    K --> L[Loader 写入 Neo4j]
~~~

### 3.9 可选的大模型语义抽取通道

extract_graph_records.py 是独立的辅助通道，不是当前正式数据的自动主流程。

它的处理顺序是：

1. 输入已经人工审核并标为 accepted 的页面块。
2. 读取冻结的 ontology.yaml 和 extraction_prompt.md。
3. 每次只让模型从当前页面块抽取候选 Graph Record。
4. 把模型给出的 Evidence 重新绑定到输入页面的文档、物理页和 Evidence ID。
5. 检查 source_text 是否是输入块中的连续原文。
6. 逐条调用 Validator。
7. 合格候选写入 graph_records.llm.jsonl；问题记录写入 ontology_gaps.llm.jsonl。
8. 人工审核后，才可以明确合并进正式 graph_records.jsonl。

所以，大模型不能决定根本体、不能创建新节点类型、不能生成 Cypher、不能把 pending 页面提升为 accepted，也不能把候选结果自动写进正式图谱。

## 4. 离线知识图谱建设：每一步怎么做

第 3 节解释了 PDF 抽取的代码原理，本节按照维护人员实际执行的先后顺序给出操作清单。

### 第一步：准备正式资料

**输入**

- 项目认可的正式 PDF。
- PDF 对应的 OCR 或逐页文本。
- 已冻结的本体定义。

**操作**

1. 确认资料版本，避免多个版本混用。
2. 按物理页保存 OCR 文本。
3. 人工复核页码、章节标题、图表编号、数值和单位。
4. 对 OCR 错字在修订记录中说明，不直接制造无法追溯的新原文。

**输出**

- 可按物理页定位的正式文本。
- 可用于建立证据的页码、章节和原文片段。

相关实现：neo4j/loader/ocr_pages.py、docs/source_corrections.md。

### 第二步：建立证据 Evidence

Evidence 是系统回答问题时真正引用的材料。每条证据至少要说明：

- 证据 ID。
- 来源文档。
- 物理页码。
- 章节。
- 原文内容。
- 证据类型。

项目中常见证据分为四类：

| 类型 | 作用 | 能否单独证明工程结论 |
|---|---|---|
| EV_CLAUSE_* | 对应完整条款或语义完整的原文 | 通常可以 |
| EV_P* | 页内较细粒度的参数、步骤或要求原文 | 通常可以 |
| EV_PAGE_* | 只表示某一页被命中 | 通常不可以，只用于定位 |
| PAGE_CONTEXT_SUPPLEMENT | 同页补充上下文 | 只能辅助，不能替代核心证据 |

建立证据时要保留连续原文，不能只留下脱离上下文的数值。页级证据只能说明“相关内容可能在这一页”，不能单独证明具体间隙、尺寸或操作要求。

### 第三步：识别实体

从资料中识别部件、工序、步骤、参数、技术要求等业务对象。实体名称和类型必须符合本体白名单，不能随意创造新类型。

同一个对象出现不同写法时，要归并到一个稳定实体 ID，并把其他写法放入别名。例如“盘车装置”和资料中的其他等价称呼，应尽量指向同一部件实体。

正式语料主要通过 neo4j/loader/build_corpus.py 生成，来源包括：

1. 人工整理的核心记录。
2. 针对遗漏内容补充的记录。
3. 按页保留的原文事实 Fact。

因此，正式图谱不是把整本 PDF 直接交给大模型后自动生成的。

### 第四步：建立实体关系

识别实体后，根据业务含义连接实体。例如：

- 某文档包含某章节。
- 某工序适用于某部件。
- 某工序包含某步骤。
- 某步骤需要某参数或技术要求。
- 某检查项检查某部件。

关系方向必须符合本体定义。例如“工序包含步骤”应从 Procedure 指向 Step，不能反向记录。

### 第五步：形成 Graph Record（图记录）

每条图记录的基本结构是：

~~~text
source（源实体）
    ── relationship（关系） ──>
target（目标实体）
    + evidence（支持这条关系的证据）
~~~

简化示例：

~~~json
{
  "source": {
    "id": "TURBINE.PROCEDURE.TURNING_GEAR_INSTALLATION",
    "type": "Procedure",
    "name": "盘车装置安装"
  },
  "relationship": {
    "type": "PROCEDURE_HAS_STEP",
    "properties": {
      "order": 7
    }
  },
  "target": {
    "id": "TURBINE.STEP.TURNING_SIDE_CLEARANCE_CHECK",
    "type": "Step",
    "name": "检查盘车装置齿侧间隙"
  },
  "evidence": [
    "EV_P061_TURNING_SIDE_CLEARANCE"
  ]
}
~~~

这里表达的是：“盘车装置安装”工序包含“检查盘车装置齿侧间隙”步骤，顺序为 7，该关系由指定证据支持。

### 第六步：运行 Validator（校验器）

在写入 Neo4j 前，必须执行确定性校验。校验器主要检查：

1. 源实体、目标实体和关系类型是否在 Validator / ontology.yaml 白名单内。
2. 关系两端的实体类型是否合法。
3. 必填属性是否齐全。
4. 实体 ID 是否稳定、格式是否正确。
5. Evidence 的文档、页码、章节、原文和状态字段是否完整、格式是否合法。
6. relationship.properties.evidence_ids 是否与 Graph Record 内嵌的 Evidence ID 完全一致。
7. 页码是否在 1～94 范围内，文档名是否为本项目唯一正式说明书。
8. 实体、关系和 Evidence 是否达到 accepted 入库状态。

Validator 本身不会重新打开 PDF 判断原文是否连续，也不会自动修复 OCR。连续原文核对由人工复核负责；可选大模型抽取通道还会在 _bind_evidence() 中检查模型引用是否为输入页面块的连续子串。

运行方式：

~~~powershell
python neo4j/validator/validator.py neo4j/data/graph_records.jsonl --accepted-only
~~~

只有校验通过的数据才应进入下一步。

### 第七步：写入 Neo4j

Loader 位于 neo4j/loader/load_graph.py，主要执行：

1. 为实体创建或更新节点。
2. 为 Evidence 创建或更新独立证据节点。
3. 按 Graph Record 创建业务关系。
4. 为每条 Graph Record 的源实体和目标实体建立 FACT_SUPPORTED_BY（由证据支持）追溯关系。
5. 创建唯一约束和全文索引。
6. 清理本项目中已经不在当前正式数据里的过期节点和关系。

Loader 使用参数化 Cypher 和 MERGE，避免同一实体重复创建。

FACT_SUPPORTED_BY 追溯边由 Loader 根据每条 Graph Record 内嵌的 Evidence 自动建立，不需要维护人员在 graph_records.jsonl 中另写一条支持关系记录。

运行前先完成 Validator 校验。普通重载已经会同步当前项目数据，不要把 --reset 当作日常参数；它会扩大清理范围，仅应在明确理解影响时使用。

### 第八步：人工抽查

入库后至少抽查：

- 一个精确参数问题。
- 一个完整工序流程。
- 一个跨页检查清单。
- 一个原文 Fact 及其 Evidence 追溯关系。

还要确认 Neo4j 中的页码、章节、数值和 graph_records.jsonl、evidence.jsonl 一致。

### 可选通道：大模型辅助抽取

neo4j/loader/extract_graph_records.py 可以按照 Schema 调用大模型生成候选三元组，但它只是辅助通道：

1. 读取待处理文本。
2. 按本体约束提示大模型抽取实体和关系。
3. 生成候选 Graph Record。
4. 人工检查实体归一、关系方向、原文证据和数值。
5. 审核通过后，再明确合并到正式语料。

该脚本的产物不会自动进入正式图谱，不能跳过人工审核、Validator 和 Loader。

## 5. 知识图谱有哪些实体

当前 ontology.yaml 和 validator.py 实际定义 15 类节点。Evidence（证据）使用独立标签和独立节点写入，其余类型作为业务 Entity（实体）写入。schema.json 只约束 Graph Record 的通用 JSON 形状，不负责枚举全部节点类型和关系端点。

| 序号 | 中文名称 | 程序类型 | 业务含义 | 示例 |
|---:|---|---|---|---|
| 1 | 文档 | Document | 正式技术资料 | 汽轮机安装说明书 |
| 2 | 章节 | Section | 文档中的章节或小节 | 2-17 盘车装置 |
| 3 | 部件 | Component | 设备、组件或零部件 | 盘车装置、轴承 |
| 4 | 工序/流程 | Procedure | 一组有业务顺序的作业过程 | 盘车装置安装 |
| 5 | 步骤 | Step | 工序中的具体动作 | 检查齿侧间隙 |
| 6 | 工具 | Tool | 作业所需工具或工装 | 塞尺、百分表 |
| 7 | 参数 | Parameter | 数值、范围、单位或控制量 | 齿侧间隙 0.3～0.6 mm |
| 8 | 技术要求 | Requirement | 必须满足的技术条件 | 间隙应符合规定范围 |
| 9 | 原文事实 | Fact | 从资料逐页保留的原文事实 | 某页的一段安装说明 |
| 10 | 检查项 | InspectionItem | 要检查的对象和内容 | 盘车装置齿侧间隙检查 |
| 11 | 维护动作 | MaintenanceAction | 调整、修配、处理等动作 | 调整垫片、修刮 |
| 12 | 风险 | Risk | 安装、运行或安全风险 | 间隙异常、碰磨风险 |
| 13 | 图 | Figure | 文档中的插图 | 图 2-17 |
| 14 | 表 | Table | 文档中的表格 | 间隙参数表 |
| 15 | 证据 | Evidence | 带页码、章节和原文的引用依据 | EV_P061_* |

### 5.1 实体如何定义

实体分为“类型定义”和“具体实例”两层：

| 内容 | 定义文件 | 作用 |
|---|---|---|
| 实体类型、允许属性和必填属性 | neo4j/ontology/ontology.yaml 的 node_types | 规定可以使用哪些实体类型，以及每类实体可以包含什么属性 |
| 运行时实体白名单 | neo4j/validator/validator.py 的 NODE_PROPERTIES 和 REQUIRED_NODE_PROPERTIES | 入库前强制检查实体类型、属性和必填字段 |
| Graph Record 通用结构 | neo4j/ontology/schema.json | 规定 source、target、relationship 和 evidence 的 JSON 形状 |
| 具体业务实体和稳定 ID | neo4j/loader/build_corpus.py | 通过 entity() 创建 Document、Section、Component、Procedure、Step、Parameter 等实体 |
| 正式实体实例 | neo4j/data/graph_records.jsonl 的 source 和 target | 保存当前正式图谱实际使用的实体、ID、类型和属性 |
| 证据实例 | neo4j/data/evidence.jsonl | 保存 Evidence 的 ID、文档、页码、章节和原文 |
| 实体别名 | neo4j/data/entity_aliases.json | 保存用户问法与标准实体名称之间的别名映射 |
| Neo4j 节点创建 | neo4j/loader/load_graph.py | 把校验通过的 source、target 和 Evidence 使用 MERGE 写入 Neo4j |

每个业务实体都使用稳定 ID、类型和名称。不同类型还可以带业务属性，例如：

- Step：步骤顺序、动作描述。
- Parameter：数值、最小值、最大值、单位。
- Evidence：文档、物理页、章节、原文、区域、置信度和审核状态。
- Figure / Table：图表编号和名称。

稳定 ID 的作用是：即使名称略有变化，只要还是同一个业务对象，图谱中的身份就不变。

例如 build_corpus.py 中创建盘车装置实体时，会指定：

~~~text
类型：Component
稳定 ID：TURBINE.COMPONENT.TURNING_GEAR
名称：盘车装置
~~~

生成 Graph Record 后，该实体出现在 graph_records.jsonl 的 source 或 target 中。Validator 根据 ontology.yaml 对应的属性规则进行检查，Loader 再把它写成 Neo4j 中带 Entity 和 Component 标签的节点。

#### Fact 是什么

Fact（原文事实）是一类实体，用来表示从已复核 PDF 页面中切分出来的一条完整原文。它既保留原文内容，又能作为图谱节点被检索。

例如：

~~~text
Fact ID：TURBINE.FACT.P061.XXX
类型：Fact
fact_type：reviewed_source_clause
statement：从第 61 页切分出来的一条连续原文
~~~

Fact 与 Evidence 的区别：

| 对象 | 保存什么 | 存在哪里 |
|---|---|---|
| Fact 实体 | 这条原文表达的事实内容，主要字段是 id、name、fact_type、statement | graph_records.jsonl 的 source 或 target；入库后是 Neo4j 中的 Entity:Fact 节点 |
| Evidence 证据 | 这条事实来自哪份文档、哪一物理页、哪个章节，以及可引用的 source_text | evidence.jsonl；入库后是独立的 Evidence 节点 |

Fact 的生成过程：

~~~text
已复核页面原文
    ↓ build_source_clause_records()
切分成连续原文小项
    ↓
Section ── SECTION_CONTAINS ──> Fact
    ↓ Loader
Fact ── FACT_SUPPORTED_BY ──> Evidence
~~~

因此，Fact 可以理解为“可检索的原文事实实体”，Evidence 则是“证明该事实来自哪里、原文是什么的证据节点”。Fact 的文本主要保存在 statement，Evidence 的引用原文保存在 source_text。

### 5.2 关键关系及中文含义

| 程序关系名 | 中文含义 | 典型方向 |
|---|---|---|
| DOCUMENT_HAS_SECTION | 文档包含章节 | Document → Section |
| SECTION_CONTAINS | 章节包含业务对象 | Section → Section / Component / Procedure / Requirement / InspectionItem / Fact / Figure / Table |
| COMPONENT_PART_OF | 部件隶属于另一部件 | Component → Component |
| PROCEDURE_APPLIES_TO | 工序适用于部件 | Procedure → Component |
| PROCEDURE_HAS_STEP | 工序包含步骤 | Procedure → Step |
| STEP_NEXT_STEP | 当前步骤的下一步骤 | Step → Step |
| STEP_REQUIRES | 步骤需要工具、参数或要求 | Step → Tool / Parameter / Requirement |
| COMPONENT_HAS_PARAMETER | 部件具有参数 | Component → Parameter |
| REQUIREMENT_APPLIES_TO | 技术要求适用于对象 | Requirement → Component / Procedure / InspectionItem |
| INSPECTION_INSPECTS | 检查项检查对象 | InspectionItem → Component / Procedure |
| INSPECTION_REQUIRES | 检查项需要参数或要求 | InspectionItem → Parameter / Requirement |
| MAINTENANCE_APPLIES_TO | 维护动作适用于对象 | MaintenanceAction → Component |
| MAINTENANCE_ADDRESSES | 维护动作处理风险或要求 | MaintenanceAction → Risk / Requirement |
| PROCEDURE_REFERENCES | 工序或章节引用图表 | Procedure / Section → Figure / Table |
| FACT_SUPPORTED_BY | 业务实体由证据支持 | Component / Procedure / Step / Tool / Parameter / Requirement / InspectionItem / MaintenanceAction / Risk / Fact / Figure / Table → Evidence |

核心结构可以简化理解为：

~~~mermaid
flowchart LR
    D[文档 Document] -->|包含| S[章节 Section]
    S -->|包含| C[部件 Component]
    S -->|包含| P[工序 Procedure]
    P -->|适用于| C
    P -->|包含并按 order 排序| ST[步骤 Step]
    ST -->|下一步| ST2[步骤 Step]
    ST -->|需要| PA[参数 Parameter]
    ST -->|需要| R[技术要求 Requirement]
    I[检查项 InspectionItem] -->|检查| C
    I -->|需要| PA
    F[原文事实 Fact] -->|由证据支持| E[证据 Evidence]
~~~

## 6. 问题如何变成检索词和实体

### 6.1 关键词不是由大模型生成

当前运行代码中，关键词和实体候选由确定性的 Python 逻辑生成，不是让大模型或 LangGraph 自由猜测。

相关实现：

- langgraph_app/src/nodes/normalize_question.py
- langgraph_app/src/tools/keyword_catalog.py

### 6.2 关键词目录怎么建立

系统从以下内容建立并缓存关键词目录：

1. 实体名称。
2. 图号和表号。
3. 实体自带别名。
4. neo4j/data/entity_aliases.json 中的人工别名。

程序还会使用 2～8 个汉字的片段帮助内部召回，但这些片段只是匹配辅助，不会作为最终公开关键词展示给用户。

### 6.3 用户问题怎么处理

以“盘车装置齿侧间隙如何检查？”为例：

1. 去掉“请问、如何、怎么、一下”等问句胶水词。
2. 保留“盘车装置、齿侧间隙、检查”等领域词。
3. 用完整别名优先匹配实体，完整命中的权重高于零散字词。
4. 系统优先匹配已经明确分类的部件、参数、工序和步骤。Fact 是从 PDF 中切分出来的原文句子，内容通常较长、涉及对象较多；当明确实体没有完全覆盖用户问法时，Fact 用于补充检索，防止遗漏相关原文，但不会优先占用有限的实体候选位置。
5. 按实体类型和匹配强度排序，最多保留 24 个实体候选。

得到的候选可能包括：

- 盘车装置：Component（部件）。
- 盘车装置安装：Procedure（工序）。
- 检查盘车装置齿侧间隙：Step（步骤）。
- 齿侧间隙：Parameter（参数）。

## 7. LangGraph 在线问答：每一步怎么做

LangGraph 使用固定的五节点线性工作流：

~~~mermaid
flowchart LR
    A[1 问题规范化] --> B[2 Neo4j 检索]
    B --> C[3 证据评估]
    C --> D[4 生成答案]
    D --> E[5 答案校验]
~~~

五个节点通过 State（状态对象）传递数据，主要字段分为：

| 阶段 | State 字段 | 中文含义 |
|---|---|---|
| 请求输入 | request_id、question | 请求编号和用户原始问题 |
| 问题分析 | case_types、observations、query_terms、focus_terms、matched_entities、retrieval_plan | 问题类型、观察信息、检索词、焦点词、候选实体和检索计划 |
| 图谱检索 | kg_evidence、retrieval_trace | 本次 Evidence 和检索过程记录 |
| 证据判断 | evidence_sufficient、input_warnings、missing_information | 证据是否充分、输入警告和缺失信息 |
| 回答输出 | recommendations、answer、claims、citations | 建议项、答案、可核验陈述和最终引用 |

每个节点只负责读取前序字段并补充自己的输出，最终由 validate_response 节点决定哪些 claim 和引用可以返回。

当前没有条件边。证据不足、数据库不可用或模型失败，均由各节点写入状态，并由后续安全逻辑返回受限答案。

### 节点一：问题规范化

**输入**：用户原始问题。

**操作**：

1. 清理无业务意义的问句词。
2. 从关键词目录匹配关键词、别名和候选实体。
3. 识别问题意图，例如参数查询、检查清单、完整流程或多目标查询。

**输出**：规范化问题、关键词、候选实体和问题意图。

### 节点二：Neo4j 检索

**输入**：规范化问题、关键词和候选实体。

**操作**：

1. 从高置信候选中确定根实体，通常是明确部件、工序或检查项。
2. 生成目标词、焦点词和具体测量词。
3. 用参数化 MATCH 和 CONTAINS 查询根实体周边的参数、要求、检查项、步骤和 Evidence。
4. 如果没有可靠根实体，再使用 Evidence 文本做受限兜底检索。
5. 按实体名称命中、根实体亲和度和证据质量排序。
6. 对结果去重并限制数量，防止无界扩散。

不同问题使用不同检索方式：

- 聚焦问题：围绕一个明确部件或参数找最相关证据。
- 清单问题：允许组合相关页中的多个检查项。
- 多目标问题：分别覆盖问题中提到的多个对象，避免只回答其中一个。
- 流程问题：先锁定一个 Procedure，再按 Step 的 order 展开完整步骤。

流程问题必须只锁定一个工序。否则同一章节中相邻但不属于该工序的兄弟步骤可能被错误混入。

Neo4j 虽然创建了全文索引，但当前主要查询使用参数化 MATCH、CONTAINS 和 Python 排序，没有调用 Neo4j 全文检索过程。

**输出**：命中的实体、关系、Evidence 和检索说明。

### 节点三：证据评估

**输入**：检索到的 Evidence。

**操作**：

1. 检查是否有语义完整的证据，而不是只有页级定位证据。
2. 检查证据是否覆盖问题中的关键对象。
3. 检查参数问题是否同时包含数值和单位。
4. 检查流程问题是否覆盖足够的连续步骤。
5. 对修配、调整、尺寸异常等高风险问题，额外检查动作约束、适用对象和目标值。

**输出**：证据是否足够、缺少什么、是否允许生成正式答案。

证据不足时，系统应明确说明无法确认或需要补充资料，不使用常识填空。

### 节点四：生成答案

**输入**：用户问题和本次从 Neo4j 取得的 Evidence。

**操作**：

1. 只把本次检索到的证据交给大模型。
2. 要求模型输出结构化 JSON。
3. JSON 中包含 answer（答案）和 claims（可核验的陈述）。
4. 每个 claim 必须绑定支持它的 Evidence。

**输出**：候选答案、claims 和引用。

如果主、备大模型都失败，系统返回模型不可用的安全结果，不伪造答案。

### 节点五：答案校验

**输入**：候选答案、claims 和 Evidence。

**操作**：

1. 根据物理页重新绑定 Evidence ID，不能直接相信模型写出的引用。
2. 检查 claim 的页码、章节和来源是否存在于本次证据中。
3. 检查答案中的数值和单位是否与证据一致。
4. 检查每个工程结论是否真的得到对应原文支持。
5. 删除或拒绝没有依据的 claim。

**输出**：最终答案及可追溯引用；若校验失败，则返回受限结果或提示证据不足。

## 8. 一次完整问答示例

用户问题：

> 盘车装置齿侧间隙如何检查？

### 第一步：规范化和实体匹配

系统识别：

- 关键词：盘车装置、齿侧间隙、检查。
- 根实体：TURBINE.COMPONENT.TURNING_GEAR。
- 相关工序：TURBINE.PROCEDURE.TURNING_GEAR_INSTALLATION。
- 相关步骤：TURBINE.STEP.TURNING_SIDE_CLEARANCE_CHECK。

### 第二步：图谱检索

系统沿 PROCEDURE_HAS_STEP（工序包含步骤）关系找到检查步骤，并取得证据：

- Evidence ID：EV_P061_TURNING_SIDE_CLEARANCE。
- 物理页：61。
- 章节：2-17。
- 原文：“检查盘车装置齿侧间隙，要求为0.3～0.6mm。”

### 第三步：证据评估

该证据同时包含：

- 检查对象：盘车装置齿侧间隙。
- 操作：检查。
- 要求范围：0.3～0.6 mm。

因此可以回答该聚焦问题。

### 第四步：生成 claim

候选 claim：

~~~json
{
  "text": "盘车装置齿侧间隙应检查并控制在 0.3～0.6 mm。",
  "evidence_ids": [
    "EV_P061_TURNING_SIDE_CLEARANCE"
  ]
}
~~~

### 第五步：校验并返回

系统核对 claim 中的对象、数值、单位、页码和章节均与 Evidence 一致，然后返回：

> 检查盘车装置齿侧间隙，并将其控制在 0.3～0.6 mm。  
> 依据：第 61 页，2-17 节。

如果只检索到 EV_PAGE_061，而没有上述细粒度原文，系统只能提示相关内容位于第 61 页，不能直接给出 0.3～0.6 mm 的工程结论。

## 9. 核心目录职责

下面说明在线问答和知识图谱建设使用的两个核心目录。

~~~text
demo/
├─ langgraph_app/                在线问答应用
│  ├─ prompts/                   大模型回答提示词
│  ├─ scripts/                   评估脚本
│  ├─ src/                       应用源代码
│  │  ├─ models/                 返回数据结构
│  │  ├─ nodes/                  LangGraph 五个业务节点
│  │  └─ tools/                  关键词和 Neo4j 查询工具
│  └─ tests/                     自动化测试
└─ neo4j/                        知识图谱建设和数据库配置
   ├─ cypher/                    Neo4j 约束、检查和展示脚本
   ├─ data/                      正式图谱数据
   ├─ loader/                    语料构建、抽取和入库脚本
   ├─ ontology/                  本体、Schema 和抽取约束
   └─ validator/                 入库前确定性校验
~~~

### 9.1 langgraph_app：在线问答应用

该目录负责接收问题、检索 Neo4j、判断证据、调用大模型并校验最终回答。

根目录文件：

| 文件 | 用途 |
|---|---|
| pyproject.toml | Python 项目依赖、安装和工具配置 |
| .env.example | 环境变量示例，只放变量名和示例格式 |
| .env | 本机运行配置，可能包含敏感信息，不应提交或复制到文档 |
| __init__.py | Python 包标记 |

#### langgraph_app/prompts

存放大模型使用的回答提示词。

- recommendation_skill.md：规定模型只能依据本次 Evidence 回答，并要求输出 answer、claims 和引用等结构。

修改提示词后，需要重点回归数值、单位、页码和无证据问题，防止模型回答更流畅但依据变弱。

#### langgraph_app/scripts

存放应用相关的独立辅助脚本。

- evaluate_pdf_first_questions.py：批量运行 PDF-first 问题，汇总命中、回答和校验结果。

该目录不是在线 API 的请求入口，通常用于离线评估。

#### langgraph_app/src

在线应用的主源代码目录。

| 文件 | 用途 |
|---|---|
| graph.py | 组装 LangGraph 五节点工作流并规定执行顺序 |
| state.py | 定义节点之间传递的问题、关键词、证据、答案和错误状态 |
| config.py | 读取 Neo4j、大模型和运行参数 |
| errors.py | 定义项目统一使用的错误类型 |
| cli.py | 命令行问答入口 |
| api.py | FastAPI 服务和 POST /recommend 接口 |
| __init__.py | Python 包标记 |

#### langgraph_app/src/nodes

每个文件对应在线问答的一项主要业务步骤。

| 文件 | 对应业务步骤 |
|---|---|
| normalize_question.py | 规范化问题，匹配关键词和候选实体 |
| neo4j_retrieval.py | 确定根实体并执行有界图谱检索 |
| assess_evidence.py | 判断 Evidence 是否足以回答问题 |
| generate_recommendation.py | 让大模型只依据本次证据生成 answer 和 claims |
| validate_response.py | 重新核对页码、章节、数值、单位和证据来源 |
| __init__.py | Python 包标记 |

排查问答问题时，可以按这五个文件的顺序定位：先看关键词是否正确，再看检索结果，再看证据判断、模型输出和最终校验。

#### langgraph_app/src/tools

存放节点会调用的底层工具。

| 文件 | 用途 |
|---|---|
| keyword_catalog.py | 从实体名称、图表编号和别名构建关键词目录并缓存 |
| neo4j_tool.py | 连接 Neo4j，执行参数化查询、结果整理、排序和去重 |
| __init__.py | Python 包标记 |

#### langgraph_app/src/models

存放接口和模型输出使用的数据结构。

| 文件 | 用途 |
|---|---|
| response.py | 定义答案、claim、引用等响应结构 |
| __init__.py | Python 包标记 |

#### langgraph_app/tests

存放自动化测试。文件与业务模块基本一一对应。

| 文件 | 主要验证内容 |
|---|---|
| test_normalize_question.py | 关键词、别名和实体匹配 |
| test_assess_evidence.py | 证据充分性和高风险门禁 |
| test_generate_recommendation.py | 大模型输入限制、结构化输出和失败处理 |
| test_validate_response.py | claim、页码、章节、数值、单位和引用校验 |
| test_graph_records.py | 正式图记录的结构和数据约束 |
| test_cli.py | 命令行入口和整体调用行为 |

修改对应业务模块后，应先运行对应测试，再运行完整测试集。

### 9.2 neo4j：知识图谱建设和数据库

该目录负责定义知识图谱、生成正式数据、执行校验、写入 Neo4j 并检查图质量。

根目录文件：

| 文件 | 用途 |
|---|---|
| docker-compose.yml | 启动本项目使用的 Neo4j 服务 |
| .env.example | Neo4j 配置示例 |
| .env | 本机 Neo4j 配置，可能包含密码，不应提交或写入文档 |

#### neo4j/cypher

存放 Neo4j 使用的 Cypher 和展示配置。

| 文件 | 用途 |
|---|---|
| constraints.cypher | 创建唯一约束和索引 |
| kg_architecture.cypher | 查看或展示知识图谱核心结构 |
| quality_checks.cypher | 在数据库中执行质量检查 |
| entity_colors.grass | Neo4j Browser 中不同实体类型的颜色和样式 |

这些文件主要用于数据库初始化、人工检查和可视化，不负责生成正式语料。

#### neo4j/data

这是知识图谱最重要的正式数据目录。

| 文件 | 用途 |
|---|---|
| graph_records.jsonl | 1022 条 Graph Record，记录源实体、关系、目标实体和证据 |
| evidence.jsonl | 909 条 Evidence，记录页码、章节和原文 |
| entity_aliases.json | 人工维护的实体别名，用于问题匹配和实体归一 |
| ontology_gaps.jsonl | 暂时无法落入现有本体的缺口或待审核项 |

修改该目录后不能直接重启问答服务了事，必须先运行 Validator，再用 Loader 同步 Neo4j。

#### neo4j/loader

存放从资料到正式图谱的构建和入库脚本。

| 文件 | 用途 |
|---|---|
| ocr_pages.py | 读取和整理逐页 OCR 文本 |
| build_corpus.py | 把人工记录、补充记录和逐页 Fact 建成正式数据 |
| extract_graph_records.py | 可选的大模型候选三元组抽取，不会自动合并正式图谱 |
| load_graph.py | 把校验通过的实体、关系和 Evidence 写入 Neo4j |
| quality_report.py | 根据正式数据生成图谱质量统计和报告 |

日常重建的核心顺序是 build_corpus.py → validator.py → load_graph.py。

#### neo4j/ontology

存放知识图谱的类型、关系和抽取规则，是实体与关系合法性的依据。

| 文件 | 用途 |
|---|---|
| schema.json | 约束 Graph Record 的通用 JSON 形状和 Evidence 基础字段 |
| ontology.yaml | 当前冻结的节点类型、属性、关系和合法端点说明 |
| root_candidates.json | 保存当前根本体类型和细化方向 |
| extraction_prompt.md | 大模型辅助抽取时的约束提示词 |
| ontology_extraction_framework.py | 按本体组织候选抽取的辅助实现 |

增加实体类型或关系类型时，不能只改数据文件；要先评审本体，再同步 ontology.yaml、validator.py、必要的 schema.json 结构、Loader、检索代码和测试。

#### neo4j/validator

存放正式数据入库前的确定性校验。

| 文件 | 用途 |
|---|---|
| validator.py | 检查类型、关系端点、必填字段、ID、Evidence、原文和门禁状态 |
| __init__.py | Python 包标记 |

Validator 不负责修复数据。发现问题后，应回到 build_corpus.py 或 neo4j/data 中修正来源，再重新校验。
