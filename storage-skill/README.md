# Storage Skill — 快手存储架构选型决策助手

> 把业务约束转换为可追溯的存储选型报告，回答"选谁、为什么、有哪些坑、如何验证"。

## 一、项目定位

面向快手内部真实业务场景的存储中间件选型 Skill。当用户提出数据库、缓存、KV、宽表、搜索/OLAP、消息队列、文件/对象存储或向量检索的选型、架构评审、容量权衡、成本分析、反模式排查时触发。

覆盖快手在用的 **14 类存储产品**：KSQL、KTable、Redis、KCache、Kiwi（KwaiKV）、Memcached、KwaiBase、HBase、Elasticsearch、ClickHouse、Doris（Bleem）、Kafka、BTQ / RocketMQ、KGraph，以及 BlobStore、KFS / HDFS、Milvus 等扩展产品。

---

## 二、目录结构

```
storage-skill/
├── SKILL.md                        # Skill 入口：触发条件、强制边界、工作流、资源导航
├── agents/
│   └── openai.yaml                 # OpenAI 兼容 Agent 接口描述
├── cases/                          # 评测集（全部来自公司内部真实文档）
│   ├── typical/                    # 典型场景（6 个）
│   │   ├── biz-olap-doris-to-clickhouse.json         # 商业化报表 Doris → CK 迁移
│   │   ├── im-message-hbase-to-kwaibase.json         # IM 消息三层架构 → KwaiBase
│   │   ├── label-system-kiwi-replace-redis-cold.json # 标签系统离线标签 Redis → Kiwi
│   │   ├── mainsite-mysql-kv-to-kwaibase-cost.json   # 主站 KV 类数据 MySQL → KwaiBase
│   │   ├── social-relation-mysql-to-kwaibase.json    # 关注/粉丝关系 MySQL → KwaiBase
│   │   └── view-later-list-kgraph-replace-mysql-redis.json  # 稍后再看列表 → KGraph
│   └── traps/                      # 陷阱场景（3 个）
│       ├── ck-high-frequency-update-too-many-parts.json  # 🚫 CK 高频 UPDATE → too-many-parts
│       ├── cleartle-mysql-single-table-bottleneck.json   # 🚫 清结算单表不治理预埋风险
│       └── redis-cross-service-hotkey-incident.json      # 🚫 Redis 热Key跨服务扩散事故
├── eval/
│   └── run_eval.sh                 # 静态契约校验 + 确定性规则回归入口
├── knowledge/                      # 存储产品能力档案（14 个 YAML）
│   ├── btq.yaml                    # BTQ / RocketMQ
│   ├── clickhouse.yaml             # ClickHouse
│   ├── doris.yaml                  # Doris（Bleem）
│   ├── elasticsearch.yaml          # Elasticsearch
│   ├── hbase.yaml                  # HBase
│   ├── kafka.yaml                  # Kafka
│   ├── kcache.yaml                 # KCache
│   ├── kgraph.yaml                 # KGraph
│   ├── kiwi.yaml                   # Kiwi / KwaiKV
│   ├── ksql.yaml                   # KSQL
│   ├── ktable.yaml                 # KTable
│   ├── kwaibase.yaml               # KwaiBase
│   ├── memcached.yaml              # Memcached
│   └── redis.yaml                  # Redis
├── prompts/                        # AI 决策 Prompt
│   ├── main.md                     # 主决策 Prompt：决策树 + 打分 + 输出格式
│   └── anti-pattern-check.md       # 反模式检查 Prompt：7 大类 30+ 条检查项
├── references/                     # 参考规范
│   ├── decision-rubric.md          # 决策评分规则：硬约束 → 决策树 → 矩阵打分 → 红线
│   ├── evidence-and-safety.md      # 证据优先级 & 安全边界
│   └── report-schema.md           # 选型报告输出契约（YAML Schema）
└── scripts/
    ├── validate_skill_data.py      # 知识库、案例与契约完整性校验
    ├── run_selection.py            # 确定性选型规则引擎，生成 JSON / Markdown 报告
    └── evaluate_cases.py           # 执行案例、比较金标、生成回归报告
```

---

## 三、核心能力

### 1. 结构化选型工作流（6 步）

```
澄清诉求 → 加载证据 → 筛选候选 → 矩阵打分 → 反模式检查 → 输出报告
```

| 步骤 | 说明 |
|------|------|
| **澄清诉求** | 收集数据规模、QPS、延迟、一致性、查询模式、SLA、成本等 9 项关键信息；缺失时主动追问 |
| **加载证据** | 按候选加载 `knowledge/*.yaml`，读取 `decision-rubric.md` 和 `report-schema.md` |
| **筛选候选** | 先应用硬约束（强事务→KSQL/KTable、全文检索→ES、高吞吐流→Kafka/BTQ 等），排除不合格候选 |
| **矩阵打分** | 8 维度加权打分（数据模型 20%、一致性 20%、查询 15%、性能 15%、扩展性 10%、可用性 10%、成本 5%、运维 5%） |
| **反模式检查** | 对照 `anti-pattern-check.md` 逐条检查 7 大类 30+ 条内部真实反模式 |
| **输出报告** | 严格遵循 `report-schema.md`，包含推荐/备选/淘汰、决策轨迹、风险、验证计划和引用来源 |

### 2. 公司存储中间件知识库

14 个 YAML 档案，每个包含 7 个必填字段：

| 字段 | 说明 |
|------|------|
| `data_model` | 数据模型（关系/KV/宽表/文档/图等） |
| `consistency` | 一致性与事务保障级别 |
| `scalability` | 扩展性与集群规模 |
| `cost_profile` | 成本量级（元/GB/月） |
| `sla` | SLA 承诺与容灾方案 |
| `query_patterns` | 典型查询/访问模式 |
| `anti_patterns` | 反模式清单（含阈值和治理数据） |

### 3. 快手 2025 官方选型决策树

基于 [2025快手四大存储选型标准](https://docs.corp.kuaishou.com/d/home/fcABmaRT3JxBzWIWc9wDTj7TI) 内化：

- **数据库/缓存**：强一致事务 → KSQL(<5T) / KTable(>5T)；缓存按访问密度选 Redis / KCache / Kiwi
- **OLAP**：全文检索→ES；多表 Join/bitmap→Doris；大规模聚合→CK
- **宽表**：在线→KwaiBase（禁止新增 HBase 在线）；离线→HBase
- **文件/对象**：二进制→BlobStore；共享+随机IO→KFS；顺序读写→HDFS
- **向量**：大规模→Milvus；小规模+全文→ES

### 4. 反模式检查体系

7 大类、30+ 条检查项，全部来源于快手内部真实故障和治理数据：

| 类别 | 条目数 | 典型反模式 |
|------|--------|-----------|
| KSQL | 6 | 大库大表、副本堆积、日志流直写、深翻页、跨DB JOIN、大字段 |
| KV 缓存 | 8 | 大Key、热Key、逐出、Kiwi单分片过大、Memcached新增 |
| 宽表 | 3 | 在线场景用HBase、热点RowKey、二级索引 |
| ES | 6 | 强一致主记录、大分片、堆内存、深翻页、未接天问 |
| OLAP | 4 | 小批频繁写CK、高基数GROUP BY、Doris未分区分桶 |
| 消息队列 | 3 | 消息积压无监控、缺少幂等+死信、分区键不当 |
| 通用 | 4 | 缓存DB同步异常、跨产品强依赖、告警缺失、产品名不规范 |

---

## 四、选型报告输出格式

每次选型输出一份结构化 Markdown 报告，YAML 摘要包含：

```yaml
需求摘要:          # 数据规模、读写负载、延迟、一致性、查询模式、容灾等
显式假设:          # 缺失参数的合理假设
推荐方案:          # 主推组件 + 置信度 + 能力对齐
推荐理由:          # 对齐哪些能力项、命中哪些硬约束
次优方案:          # 条件化备选
明确淘汰方案:      # 组件 + 淘汰原因
决策轨迹:          # 每个候选的硬约束状态、加权分、证据、假设
已识别风险与反模式: # P0/P1/P2 分级 + 规避建议
验证建议:          # staging/只读环境 + 指标 + 通过标准 + 停止条件
引用来源:          # 内部文档标题、链接、支撑结论
待验证项:          # 查不到内部证据的标记项
```

---

## 五、评测体系

### 评测集构成

所有 case 均从快手内部真实文档中提取（故障复盘、迁移项目报告、架构评审、运维手册），经脱敏后作为 few-shot 样本和评测集。

| ID | 类型 | 来源文档 | 真实性 |
|----|------|---------|--------|
| `im-message-hbase-to-kwaibase` | 典型 | IM消息存储成本优化工作汇报 | ✅ 已落地迁移项目报告 |
| `biz-olap-doris-to-clickhouse` | 典型 | 商业化效果数据迁移CK项目 | ✅ 真实Benchmark数据（CPU/P99对比） |
| `mainsite-mysql-kv-to-kwaibase-cost` | 典型 | 主站持久化存储演进方案调研 | ✅ 含真实集群名和数据量 |
| `social-relation-mysql-to-kwaibase` | 典型 | 主站持久化存储演进方案调研 | ✅ 含真实集群名和数据量 |
| `view-later-list-kgraph-replace-mysql-redis` | 典型 | 业务场景和存储综合分析V2 | ✅ 含真实 QPS（308w/s）和 DB 容量 |
| `label-system-kiwi-replace-redis-cold` | 典型 | KV存储选型实践 | ✅ 标签系统实际在用选型方案 |
| `redis-cross-service-hotkey-incident` | 陷阱 | redis大/热key告警case收集 | ✅ 真实天问告警事故，有服务名 |
| `cleartle-mysql-single-table-bottleneck` | 陷阱 | 清结算存储架构升级-分库分表评审 | ✅ 真实架构评审，含实际业务量数据 |
| `ck-high-frequency-update-too-many-parts` | 陷阱 | ClickHouse oncall 手册 | ⚠️ 运维故障手册真实，"广告出价"为基于真实故障模式的合成场景 |

每个 case 同时保留两层内容：

- `request` / `expected`：真实业务背景、人工审核的完整选型结论与来源，供 Skill few-shot 和答辩展示；
- `input` / `golden`：人工提炼的结构化输入与机器可判定断言，供确定性规则回归使用。

`golden` 会检查主推荐、禁止方案、淘汰原因码、风险码、验证主题和最少证据数量，避免仅凭自由文本判断结果。

### 回归评测

```bash
# 静态契约校验 + 9 个真实案例的确定性规则回归
bash eval/run_eval.sh

# 单独执行静态契约校验
python3 scripts/validate_skill_data.py .
```

评测会保留每个案例的 `request/expected`，并使用 `input/golden` 生成结构化报告、比较机器断言，在 `artifacts/eval/<timestamp>/` 输出报告、逐项比较结果和汇总通过率。

---

## 六、AI Harness 设计（七要素）

| 要素 | 本 Skill 设计 |
|------|--------------|
| **上下文** | 每次运行加载 `knowledge/*.yaml`（产品能力档案）、`references/decision-rubric.md`（评分规则）、`references/report-schema.md`（输出契约）、`prompts/anti-pattern-check.md`（反模式清单）、`cases/`（few-shot 样本） |
| **工具接口** | 允许读取本 Skill 内部档案；允许通过 docs-shuttle / kcli 等内部 skill 检索公司文档验证假设；仅允许执行明确标记为只读的验证命令 |
| **执行环境** | MyFlicker Skill 一键触发；以 `SKILL.md` 为入口，AI 自动加载知识库、决策规则和反模式检查清单 |
| **反馈闭环** | `eval/run_eval.sh` 静态校验 + 评测集 case-by-case 对比人工标注；失败时驱动 Prompt / 决策规则迭代 |
| **权限边界** | 禁止读取生产敏感数据；禁止线上写入/压测/扩缩容/配置变更；内部事实查不到时标记 `待验证`，禁止臆造 |
| **可观测性** | 报告中保留完整决策轨迹（候选、硬约束状态、加权分、证据、假设）；每次选型可追溯到具体知识库条目和内部文档 |
| **验证机制** | `validate_skill_data.py` 数据完整性校验；评测集人工标注 vs Skill 输出差异分析；输出格式 Schema 校验 |

---

## 七、使用方式

### 在 MyFlicker 中调用

直接输入业务诉求即可触发，例如：

```
我有一个订单系统，日增 500 万笔交易，需要强一致、主键查询、P99 < 10ms，
跨 2 个 AZ 部署，应该选什么存储？
```

Skill 会自动走完 6 步工作流，输出结构化选型报告。

### 关键选型阈值速查

| 场景 | 阈值 | 选型方向 |
|------|------|---------|
| KSQL vs KTable | 数据量 < 5TB → KSQL；> 5TB 或列数 > 200 → KTable | |
| Redis vs KCache | 访问密度 < 1000/GB → KCache；> 1000/GB → Redis | |
| Redis vs Kiwi | 访问密度 < 300/GB + 持久化 → Kiwi；高 QPS → Redis | |
| Redis 大 Key | > 10KB | 需拆分 |
| Redis 热 Key | > 10w QPS | 需打散 |
| KSQL 大库 | > 1TB | 需治理 |
| KSQL 大表 | > 50GB | 需治理 |
| ES 分片 | > 50GB | 高危 |
| Kiwi 单分片 | > 50GB | 运维效率低 |

---

## 八、知识来源

以下内部文档为 Skill 知识库的核心来源，访问需内网权限：

| 文档 | 链接 | 用途 |
|------|------|------|
| 25快手存储健康度治理&业务存储架构演进 | [Docs](https://docs.corp.kuaishou.com/d/home/fcADgnjSSO4AkIN4CGkfpsnKb) | 治理数据、阈值、迁移路线 |
| 2025快手四大存储选型标准 | [Docs](https://docs.corp.kuaishou.com/d/home/fcABmaRT3JxBzWIWc9wDTj7TI) | 官方决策树、选型阈值 |
| KV存储选型实践 | [Docs](https://docs.corp.kuaishou.com/d/home/fcABZNsQQ9p0-zVZR14rmdtOT) | Redis/KCache/Kiwi 对比（含成本数据和选型阈值） |
| 存储健康度治理标准 | [Docs](https://docs.corp.kuaishou.com/d/home/fcAATr1i1vxEN0C816BZAf5-U) | 健康度红线 |
| ES/Doris/CK存储选型调研 | [Docs](https://docs.corp.kuaishou.com/d/home/fcADCuLf--w6IWU1-jnlmPWIy) | OLAP 选型对比 |
| IM消息存储成本优化工作汇报 | [Docs](https://docs.corp.kuaishou.com/d/home/fcABVR8_D-x2Ff-zsOS2G6TiM) | **典型case来源**：KwaiBase落地迁移全过程 |
| 商业化效果数据迁移clickhouse项目 | [Docs](https://docs.corp.kuaishou.com/d/home/fcABdI0bD5ieCJf9uKs97G7mr) | **典型case来源**：Doris→CK Benchmark对比 |
| 主站持久化存储演进方案调研 | [Docs](https://docs.corp.kuaishou.com/d/home/fcAB1LjgjZoNX-vj4xvxyutOG) | **典型case来源**：1759集群迁移路线、Top30业务分析 |
| 业务场景和存储的综合分析V2 | [Docs](https://docs.corp.kuaishou.com/d/home/fcADITcEPhSmzG2ER-5CaRDJM) | **典型case来源**：KGraph/KwaiKV替代MySQL+Redis场景 |
| redis大/热key告警case收集 | [Docs](https://docs.corp.kuaishou.com/d/home/fcADpxiwgfmwRhQ5Hi0TqbX8u) | **陷阱case来源**：生产热Key跨服务扩散事故 |
| 清结算存储架构升级-分库分表评审 | [Docs](https://docs.corp.kuaishou.com/d/home/fcABeOsVSxy2xCH4VRQstmGUj) | **陷阱case来源**：单表容量风险预防性改造评审 |
| ClickHouse oncall 手册 | [Docs](https://docs.corp.kuaishou.com/d/home/fcAB9bcsFcw64u92N1K5D0uxP) | **陷阱case来源**：too-many-parts / readonly 故障手册 |

---

## 九、质量门禁

- 关键输入已获取或显式声明假设
- 硬约束先于量化打分
- 推荐和淘汰理由成对出现
- 反模式已逐条检查
- 内部事实可追溯，查不到标记 `待验证`
- 验证步骤仅 staging / 只读
- 所有产品名使用内部名称（KSQL 不写 MySQL，KCache 不写 Memcached，KwaiBase 不写 HBase）

---

## 十、安全边界

| 允许 | 禁止 |
|------|------|
| 读取本 Skill 档案和案例 | 对线上存储执行写入/删除/迁移/压测 |
| 检索内部文档并提取摘要 | 查询生产敏感数据 |
| 执行只读的状态/配置检查 | 未经确认执行来源不明的命令 |
| staging 使用脱敏数据做 PoC | 将未审核的内部原文发布到外网 |

---

## License

Internal use only. 本 Skill 包含快手内部存储产品信息，仅限内部使用，不得对外发布。
