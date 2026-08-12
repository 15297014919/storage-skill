# 订单系统存储选型 — 业务诉求与变化演示

> 用于演示 storage-skill 在参数变化时如何调整选型结论。选取一个**变化可控**的自由业务诉求，通过 4 个版本的单参数变化，触发 skill 不同硬约束分支。

---

## 第一部分：业务诉求输入信息

### 1.1 选取场景：订单系统

**选取理由**：

- 不在 9 个评测案例中，属于自由发挥场景
- 决策树在该场景下有多个清晰硬约束节点（5T/200 列阈值、聚合分流、全文检索分流、事件流削峰）
- 参数变化能精准触发 skill 不同分支，便于演示"如何调整"
- 每个变化只动一个参数，符合控制变量法，便于归因

### 1.2 Base 诉求（版本 v0）

```
我有一个订单系统：
- 数据量 2TB，日增 500 万笔，单表 50 列
- 强一致事务，主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 无全文检索、无大规模聚合

应该选什么存储？
```

### 1.3 结构化输入字段（对应 skill `input` 契约）

| 字段 | v0 取值 |
|---|---|
| scenario | 订单系统主账本选型 |
| data_model | relational |
| data_scale_tb | 2 |
| daily_increment | 500万笔 |
| column_count | 50 |
| read_qps | 5000 |
| write_qps | 5000 |
| p99_latency_ms | 10 |
| consistency | strong |
| transaction_required | true |
| persistence_required | true |
| workload_mode | online |
| query_patterns | ["key_lookup", "range_scan"] |
| fulltext_search | false |
| cross_az | true |
| cost_sensitive | medium |

### 1.4 Skill 在 v0 上的预期运行轨迹

| 步骤 | 触发机制 | 结果 |
|---|---|---|
| 1. 澄清诉求 | 工作流步骤 1 | 9 项关键输入齐全 |
| 2. 加载证据 | `knowledge/ksql.yaml` + `knowledge/ktable.yaml` + `decision-rubric.md` | 加载 KSQL/KTable 档案 |
| 3. 硬约束筛选 | 硬约束表第 1 行：`强一致事务主记录 + 数据量 < 5T` → **必须 KSQL** | KSQL 通过；KTable 不必进入打分 |
| 4. 矩阵打分 | 8 维度加权 | KSQL 总分预计 85+ |
| 5. 反模式检查 | `anti-pattern-check.md` KSQL 6 条 | 检查大库（2TB>1TB 治理线但未到 5T 硬约束）、大表（单表需 < 50GB）、副本数 |
| 6. 输出报告 | `report-schema.md` 契约 | 推荐 KSQL；次优 KTable（不必要）；淘汰 ES/CK/KwaiBase |

### 1.5 v0 预期金标断言

```yaml
allowed_alternatives: []
minimum_evidence_count: 1
required_primary_components:
  - KSQL
forbidden_primary_components:
  - ES
  - CK
  - KwaiBase
required_rejection_codes: []
required_risk_codes: []
required_validation_topics:
  - staging_latency
```

---

## 第二部分：变化信息

### 2.1 变化版本总览

| 版本 | 变化参数 | 触发硬约束 | 推荐方案 | 调整类型 |
|---|---|---|---|---|
| v0 | 基线 | 硬约束 1 | KSQL | — |
| v1 | 数据 2T→8T | 硬约束 2（>5T） | KTable | 单产品翻转 |
| v2 | 列数 50→250 | 硬约束 2（>200 列） | KTable | 单产品翻转（原因码不同） |
| v3 | +全文检索 | 硬约束 3 | KSQL + ES 双写 | 组合架构 |
| v4 | 写入 5k→5w/s | 硬约束 4 | Kafka + KSQL | 组合架构 + 接入层 |

---

### 2.2 Variation v1：数据量从 2TB → 8TB

**变化诉求**：

```
我有一个订单系统：
- 数据量 8TB（业务爆发增长），日增 2000 万笔，单表 50 列
- 强一致事务，主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 无全文检索、无大规模聚合

应该选什么存储？
```

**变化字段**：

| 字段 | v0 | v1 |
|---|---|---|
| data_scale_tb | 2 | 8 |
| daily_increment | 500万笔 | 2000万笔 |

**Skill 调整点**：

| 机制 | 调整动作 |
|---|---|
| 硬约束表第 2 行 | `数据量 > 5T` → **必须 KTable，排除单机 KSQL** |
| 工作流步骤 3 | KSQL 从"通过"翻转为"硬约束排除"，原因码 `KSQL_CAPACITY_EXCEEDED` |
| 步骤 4 打分 | KTable 进入打分，"扩展性"维度拿满分 10（分片机制满足 3 倍增长） |
| 步骤 5 反模式 | 触发 KTable 红线检查：磁盘 >70% / CPU >90%（KTable 1.0 须接天问） |
| 步骤 6 输出 | 主推从 KSQL 翻转为 KTable；KSQL 进入"明确淘汰方案"，原因：硬约束 > 5T |
| 引用来源 | 新增 `2025快手四大存储选型标准` 第 5T 阈值条目 |

**v1 预期金标断言**：

```yaml
required_primary_components:
  - KTable
forbidden_primary_components:
  - KSQL
required_rejection_codes:
  - KSQL_CAPACITY_EXCEEDED
required_risk_codes:
  - KTABLE_DISK_HIGH
  - KTABLE_CPU_HIGH
required_validation_topics:
  - staging_latency
  - tianwen_monitoring
```

---

### 2.3 Variation v2：列数从 50 → 250

**变化诉求**：

```
我有一个订单系统：
- 数据量 2TB，日增 500 万笔
- 单表 250 列（业务字段冗余膨胀），强一致事务
- 主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 无全文检索、无大规模聚合

应该选什么存储？
```

**变化字段**：

| 字段 | v0 | v2 |
|---|---|---|
| column_count | 50 | 250 |

**Skill 调整点**：

| 机制 | 调整动作 |
|---|---|
| 硬约束表第 2 行 | `列数 > 200` → **必须 KTable**（与 v1 同结论，但**触发条件不同**） |
| 决策树 | 命中"数据量 < 5T 且列数 ≤ 200？"的"否"分支 → KTable 2.0 |
| 步骤 4 打分 | "数据模型匹配"维度：宽表模型更契合 250 列场景，KTable 拿 18-20；KSQL 在 250 列下 B+Tree 维护成本高，降至 6-11 |
| 步骤 5 反模式 | 触发 KSQL 反模式：`大字段/列膨胀`（`anti-pattern-check.md` KSQL 类） |
| 步骤 6 输出 | 推荐翻转为 KTable；KSQL 淘汰原因码变为 `KSQL_COLUMN_EXPLOSION` 而非 `KSQL_CAPACITY_EXCEEDED` |

**关键观察**：同一推荐结果（KTable），但 skill 给出的淘汰原因码不同，证明 skill 不会"只看结论不看理由"，可被金标 `required_rejection_codes` 精确校验。

**v2 预期金标断言**：

```yaml
required_primary_components:
  - KTable
forbidden_primary_components:
  - KSQL
required_rejection_codes:
  - KSQL_COLUMN_EXPLOSION    # 与 v1 区分
required_risk_codes:
  - KTABLE_DISK_HIGH
required_validation_topics:
  - staging_latency
```

---

### 2.4 Variation v3：新增全文检索需求

**变化诉求**：

```
我有一个订单系统：
- 数据量 2TB，日增 500 万笔，单表 50 列
- 强一致事务，主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 【新增】需要按订单备注/收货地址做模糊搜索和相关性排序

应该选什么存储？
```

**变化字段**：

| 字段 | v0 | v3 |
|---|---|---|
| fulltext_search | false | true |
| query_patterns | ["key_lookup", "range_scan"] | ["key_lookup", "range_scan", "fulltext_search"] |

**Skill 调整点**：

| 机制 | 调整动作 |
|---|---|
| 硬约束表第 3 行 | `全文检索或相关性排序` → **ES 必须进入候选；ES 不得作为强一致主账本** |
| 步骤 3 筛选 | 候选从 {KSQL} 扩展为 {KSQL（主账本）, ES（检索侧）}，这是**双产品架构**而非单选 |
| 步骤 4 打分 | KSQL 仍是主账本打分领先；ES 在"查询模式"维度拿满 15（倒排索引匹配全文检索），但"一致性"维度仅 6-11（最终一致） |
| 步骤 5 反模式 | 触发 ES 反模式：`强一致主记录`（`anti-pattern-check.md` ES 类）——明确 ES 不可作订单主账本 |
| 步骤 6 输出 | 推荐变为 **KSQL（主）+ ES（检索侧，双写）**；新增"明确淘汰方案"：ES 单独作为订单主账本；风险栏新增"KSQL→ES 双写一致性" |
| 验证建议 | 新增 staging 验证：双写 DIFF 率 < 万分之一，ES 查询 P95 < 200ms |

**关键观察**：skill 不是"单产品推荐器"，硬约束触发时会自动组合出**双产品架构**，并在反模式检查中明确边界（哪个是主账本、哪个是检索侧）。

**v3 预期金标断言**：

```yaml
required_primary_components:
  - KSQL
  - ES                          # 双产品
forbidden_primary_components:
  - ES_AS_PRIMARY               # ES 不可作主账本
required_rejection_codes:
  - ES_STRONG_CONSISTENCY_PROHIBITED
required_risk_codes:
  - DUAL_WRITE_CONSISTENCY
  - ES_SHARD_TOO_LARGE
required_validation_topics:
  - staging_latency
  - dual_write_diff
  - es_search_latency
```

---

### 2.5 Variation v4：写入峰值从 5k/s → 5w/s（大促场景）

**变化诉求**：

```
我有一个订单系统：
- 数据量 2TB，日增 500 万笔，单表 50 列
- 强一致事务，主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 【新增】大促时写入峰值 5w 条/s，平时 5k 条/s

应该选什么存储？
```

**变化字段**：

| 字段 | v0 | v4 |
|---|---|---|
| write_qps | 5000 | 50000（峰值） |
| peak_write_qps | — | 50000 |

**Skill 调整点**：

| 机制 | 调整动作 |
|---|---|
| 硬约束表第 4 行 | `高吞吐持续事件流 (> 万/s 量级)` → **Kafka 或 BTQ 作接入层，不直写 KSQL/KwaiBase** |
| 步骤 3 筛选 | 候选扩展为 {Kafka 或 BTQ（接入削峰）, KSQL（主账本）}，又是组合架构 |
| 步骤 4 打分 | Kafka 在"性能目标"维度拿满 15（单 shard 10w+ 条/s）；"一致性"维度 12-16（最终一致，依赖消费幂等） |
| 步骤 5 反模式 | 触发消息队列 3 条反模式：`消息积压无监控`、`缺少幂等+死信`、`分区键不当`（`anti-pattern-check.md` MQ 类） |
| 步骤 6 输出 | 推荐变为 **Kafka/BTQ 接入 + KSQL 主账本**；风险栏新增 P0：幂等+死信、分区键设计；验证建议新增"积压监控接入天问" |
| 待验证项 | 若 v0 未声明幂等要求，skill 会在"待验证项"标记 `需业务确认订单写入幂等性` |

**关键观察**：当峰值跨越"万/s"硬阈值，skill 会**主动加一层接入存储**，并在反模式检查中预置 MQ 相关 P0 风险，不需要用户提示。

**v4 预期金标断言**：

```yaml
required_primary_components:
  - Kafka                       # 或 BTQ
  - KSQL
forbidden_primary_components: []
required_rejection_codes: []
required_risk_codes:
  - MQ_BACKLOG_NO_MONITOR       # P0
  - MQ_NO_IDEMPOTENT_DLQ        # P0
  - MQ_BAD_PARTITION_KEY        # P0
required_validation_topics:
  - staging_latency
  - mq_backlog_monitoring
  - idempotent_test
```

---

## 第三部分：变化对照与可观测性说明

### 3.1 四版变化对照表

| 版本 | 变化参数 | 触发硬约束 | 推荐方案 | 淘汰/新增 | 调整类型 |
|---|---|---|---|---|---|
| v0 | 基线 | 硬约束 1（强一致+<5T） | KSQL | — | 基线 |
| v1 | 数据 2T→8T | 硬约束 2（>5T） | KTable | 淘汰 KSQL（`KSQL_CAPACITY_EXCEEDED`） | 单产品翻转 |
| v2 | 列数 50→250 | 硬约束 2（>200 列） | KTable | 淘汰 KSQL（`KSQL_COLUMN_EXPLOSION`） | 单产品翻转（原因码区分） |
| v3 | +全文检索 | 硬约束 3 | KSQL + ES 双写 | 淘汰 ES 作主账本；新增双写一致性风险 | 组合架构 |
| v4 | 写入 5k→5w/s | 硬约束 4 | Kafka + KSQL | 新增 MQ 三条反模式风险 | 组合架构 + 接入层 |

### 3.2 为什么这组变化"可控"

1. **每个变化只动一个参数**，符合控制变量法，便于归因
2. **每个变化精准命中一条硬约束**（v1/v2 命中第 2 行、v3 命中第 3 行、v4 命中第 4 行），不是模糊的"分数微调"
3. **结果可被金标断言校验**：v1/v2 可用 `required_rejection_codes` 区分原因码；v3/v4 可用 `required_risk_codes` 校验新增风险
4. **覆盖三种调整模式**：
   - 单产品翻转（v1/v2）
   - 组合架构（v3/v4）
   - 原因码区分（v1 vs v2）

### 3.3 Skill 调整的可观测性证据

每次参数变化在 skill 输出报告中可观测到以下同步变化：

| 报告字段 | v0 → v1 | v0 → v2 | v0 → v3 | v0 → v4 |
|---|---|---|---|---|
| 推荐方案 | KSQL → KTable | KSQL → KTable | KSQL → KSQL+ES | KSQL → Kafka+KSQL |
| 明确淘汰方案 | + KSQL | + KSQL | + ES（主账本） | 无新增淘汰 |
| 决策轨迹 | 硬约束翻转 | 硬约束翻转 | 候选扩展 | 候选扩展 |
| 已识别风险 | + KTable 红线 | + 列膨胀 | + 双写一致性 | + MQ 三条 P0 |
| 验证建议 | + 天问接入 | + 列数评估 | + 双写 DIFF | + 积压监控 |
| 待验证项 | 无新增 | 无新增 | 无新增 | + 幂等性确认 |
| 引用来源 | + 5T 阈值条目 | + 200 列条目 | + ES 选型调研 | + MQ 选型条目 |

### 3.4 演示使用方式

**方式一：逐版本喂给 skill**

将 v0~v4 五段诉求依次输入 skill，对照"预期运行轨迹"和"预期金标断言"检查输出是否一致。

**方式二：扩充评测集**

将 v0~v4 转写为 5 个 `input/golden` JSON 文件放入 `cases/typical/`，运行 `bash eval/run_eval.sh` 做自动化回归。

**方式三：差异分析**

固定 v0 为基线，每次只跑一个 variation，对比 skill 输出报告的差异字段，验证 skill 是否按"硬约束 → 候选筛选 → 打分 → 反模式 → 输出"的顺序逐层调整。
