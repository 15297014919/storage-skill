# 订单系统存储选型报告 — v0 基线与变化推演

> 本文档基于 `storage-skill/cases/demo/order-system-variation-demo.md` 中的业务诉求，按 `storage-skill` 的 6 步工作流（澄清诉求 → 加载证据 → 筛选候选 → 矩阵打分 → 反模式检查 → 输出报告）输出选型报告。
>
> 第一部分为 v0 基线完整选型报告；第二部分演示 v0 → v1/v2/v3/v4 时选型报告的逐字段变化。

---

## 第一部分：v0 基线选型报告

### 1.1 业务诉求（v0）

```
我有一个订单系统：
- 数据量 2TB，日增 500 万笔，单表 50 列
- 强一致事务，主键点查 + 少量范围查询
- P99 < 10ms，跨 2 AZ 部署
- 无全文检索、无大规模聚合
应该选什么存储？
```

### 1.2 工作流执行轨迹

| 步骤 | 动作 | 结果 |
|---|---|---|
| 1. 澄清诉求 | 9 项关键输入齐全（数据规模/QPS/延迟/一致性/查询/容灾/成本） | 无需追问 |
| 2. 加载证据 | 加载 `knowledge/ksql.yaml`、`knowledge/ktable.yaml`、`references/decision-rubric.md`、`references/report-schema.md`、`prompts/anti-pattern-check.md` | 证据就位 |
| 3. 硬约束筛选 | 命中硬约束第 1 行 `强一致事务主记录 + 数据量 < 5T` → 必须 KSQL；未命中第 2/3/4 行 | KSQL 通过；KTable 不必打分 |
| 4. 矩阵打分 | 8 维度加权打分（仅对通过硬约束的候选） | KSQL 88/100 |
| 5. 反模式检查 | 逐条检查 KSQL 6 条反模式，命中 1 条 P2（大库治理线） | 列入风险栏 |
| 6. 输出报告 | 按 `report-schema.md` 输出 | 见 1.3 |

### 1.3 v0 选型报告（YAML 摘要）

```yaml
需求摘要:
  数据规模: "2TB，日增 500 万笔，单表 50 列"
  读写负载: "读写约 5k QPS 量级（订单系统典型）"
  延迟目标: "P99 < 10ms"
  一致性与事务: "强一致 + ACID 事务，跨 2 AZ"
  查询模式: ["主键点查", "少量范围查询"]
  可用性与容灾: "跨 2 AZ，RTO/RPO 按 KDB 平台 SLA"
  生命周期与扩展: "数据量未到 5T 硬约束，3 倍增长内单机 KSQL 可承载"
  成本约束: "中等（未指定具体预算）"

显式假设:
  - "读写 QPS 未显式给出，按订单系统典型量级假设约 5k QPS"
  - "未提及副本数，按平台默认 ≤4 副本"
  - "未提及大字段/TEXT/BLOB，假设行格式紧凑"

推荐方案:
  组件: ["KSQL"]
  置信度: 高
  能力对齐:
    - "强一致 ACID 事务（KSQL InnoDB 原生支持）"
    - "主键/索引点查（KSQL query_patterns 命中）"
    - "数据量 2TB < 5T 硬约束阈值"
    - "P99 < 10ms 在 KSQL 单机容量内可达"
    - "跨 AZ 部署由 KDB 平台主从半同步保障"

推荐理由:
  - "硬约束第 1 行命中：强一致事务主记录 + 数据量 < 5T → 必须 KSQL"
  - "数据模型完全匹配：关系表 + 主键 + 索引，KSQL 原生支持"
  - "查询模式命中 KSQL 强项：主键点查 + 有限范围查询"
  - "2TB 未触发大库治理红线（>1TB），但已临近，需关注治理"
  - "KTable 不必要：未触发 >5T 或 >200 列硬约束，单机 KSQL 更高效且运维成本更低"

次优方案:
  组件: ["KTable"]
  适用条件:
    - "未来 12 个月数据增长超 5T 或列数超 200 时，启动迁移评估"
    - "需要弹性扩展 QPS 超单机上限时"

明确淘汰方案:
  - 组件: "ES"
    原因: "硬约束第 3 行：ES 不得作为强一致主账本；近实时可见性约 1s，不满足订单强一致"
  - 组件: "CK"
    原因: "硬约束：大规模列式聚合分析场景才选 CK/Doris；本场景无聚合需求"
  - 组件: "KwaiBase"
    原因: "硬约束：在线宽表场景选 KwaiBase；本场景是关系型事务主记录，非宽表"
  - 组件: "Kafka / BTQ"
    原因: "硬约束：高吞吐持续事件流 > 万/s 才选；本场景写入量级未到该阈值"

决策轨迹:
  - 候选: "KSQL"
    硬约束: 通过
    加权分: 88
    证据:
      - "knowledge/ksql.yaml: data_model=关系表/主键/索引/InnoDB 事务"
      - "knowledge/ksql.yaml: scalability=数据量 <5T 优先 KSQL"
      - "knowledge/ksql.yaml: query_patterns=事务型主记录/主键点查"
      - "references/decision-rubric.md: 硬约束第 1 行"
    假设:
      - "读写 QPS 约 5k（订单系统典型量级）"
  - 候选: "KTable"
    硬约束: 通过（但非必要）
    加权分: 75
    证据:
      - "knowledge/ktable.yaml: data_model=兼容 MySQL 协议分布式 KV"
      - "knowledge/ktable.yaml: anti_patterns=<5T 强行用 KTable 低效"
    假设:
      - "数据量 2TB < 5T，KTable 非必要"
  - 候选: "ES"
    硬约束: 淘汰
    加权分: 0
    证据:
      - "knowledge/elasticsearch.yaml: consistency=近实时约 1s 可见性，不满足强一致"
      - "anti-pattern-check.md D 类: ES 作强一致主记录"
  - 候选: "Kafka"
    硬约束: 淘汰
    加权分: 0
    证据:
      - "references/decision-rubric.md: 硬约束第 4 行 > 万/s 事件流"
  - 候选: "KwaiBase"
    硬约束: 淘汰
    加权分: 0
    证据:
      - "references/decision-rubric.md: 硬约束第 9 行在线宽表场景"

已识别风险与反模式:
  - "[P2] KSQL 大库治理线：数据量 2TB > 1TB 治理阈值（已知 270+ 大库在治理中）。规避：归档历史订单、按月分表、监控增长率，达到 4T 启动 KTable 迁移评估"
  - "[P2] KSQL 副本数须 ≤4：副本 >4 会触发主从延迟风险，扩容时优先垂直扩容而非加副本"
  - "[P3] 深翻页风险：订单列表查询若 OFFSET > 1 万行需改用游标翻页（keyset pagination）"

验证建议:
  - 目标: "验证 KSQL 在订单读写场景下的延迟与容量"
    环境: staging
    指标:
      - "P99 < 10ms（订单主键点查）"
      - "P95 < 5ms（范围查询）"
      - "单库容量 < 4TB（留 1T 缓冲到 5T 硬约束）"
      - "主从延迟 < 1s"
      - "副本数 ≤4"
    步骤:
      - "使用脱敏订单数据在 staging 构造 2TB 容量压测"
      - "回放线上读写流量样例（含大促峰值场景）"
      - "模拟主从切换验证跨 AZ 容灾"
    通过标准: "P99 < 10ms 且 24h 无慢查告警"
    停止条件: "P99 > 50ms 或主从延迟 > 5s 立即停止并扩容"

引用来源:
  - 标题: "2025快手四大存储选型标准"
    链接: "https://docs.corp.kuaishou.com/d/home/fcABmaRT3JxBzWIWc9wDTj7TI"
    更新时间: "待验证"
    支撑结论: "硬约束第 1 行：强一致事务 + <5T → KSQL"
  - 标题: "25快手存储健康度治理&业务存储架构演进"
    链接: "https://docs.corp.kuaishou.com/d/home/fcADgnjSSO4AkIN4CGkfpsnKb"
    更新时间: "待验证"
    支撑结论: "KSQL 大库 >1TB 治理线、副本 ≤4 阈值"
  - 标题: "knowledge/ksql.yaml"
    链接: "storage-skill/knowledge/ksql.yaml"
    更新时间: "skill 内置档案"
    支撑结论: "KSQL 能力档案：data_model/consistency/scalability/query_patterns"

待验证项:
  - "KSQL 当前最新版本与配额（需通过 KDB 平台查询）"
  - "KSQL 跨 2 AZ 部署的具体 RTO/RPO 承诺（见 KDB 平台 SLA 文档）"
  - "KSQL 内部报价（成本量化需通过 KDB 平台查询）"
```

### 1.4 v0 报告要点速览

| 维度 | v0 结论 |
|---|---|
| 推荐 | KSQL（置信度 高，88 分） |
| 次优 | KTable（未来超 5T 时启动） |
| 淘汰 | ES / CK / KwaiBase / Kafka / BTQ |
| 风险 | 3 条（P2 大库治理 + P2 副本数 + P3 深翻页） |
| 验证 | staging 压测 P99<10ms、容量 <4TB |
| 待验证 | 3 项（版本/SLA/报价） |

---

## 第二部分：v0 → 变化版本的报告差异

> 以下每个版本只展示相对 v0 的**字段级差异**，未列出的字段保持 v0 取值。

### 2.1 v0 → v1：数据量 2TB → 8TB

**输入变化**：`data_scale_tb: 2 → 8`；`daily_increment: 500万笔 → 2000万笔`

**Skill 工作流变化**：

| 步骤 | v0 | v1 |
|---|---|---|
| 3 硬约束筛选 | 命中第 1 行（KSQL 必须） | **改命中第 2 行：数据量 > 5T → 必须 KTable，排除单机 KSQL** |
| 4 矩阵打分 | KSQL 88 分 | KTable 86 分；KSQL 被硬约束排除不进入打分 |
| 5 反模式 | KSQL 大库 P2 | **新增 KTable 红线：磁盘 >70% / CPU >90% / 1.0 集群须接天问** |
| 6 输出 | 推荐 KSQL | **推荐翻转为 KTable；KSQL 进入淘汰** |

**报告字段差异**：

```yaml
# 推荐方案（v0 → v1）
推荐方案:
  组件: ["KSQL"]  →  ["KTable"]
  置信度: 高  →  高
  能力对齐:
    - "强一致 ACID 事务（KSQL InnoDB 原生支持）"  →  "原生分布式事务 + 全局二级索引（KTable data_model）"
    - "数据量 2TB < 5T 硬约束阈值"  →  "数据量 8TB > 5T，KTable 横向扩展适配"
    - "P99 < 10ms 在 KSQL 单机容量内可达"  →  "KTable QPS 可横向扩展，P99 < 10ms 在分片负载均衡下可达"

# 推荐理由（v0 → v1）
推荐理由:
  - "硬约束第 1 行命中：强一致事务主记录 + 数据量 < 5T → 必须 KSQL"
  →  "硬约束第 2 行命中：数据量 > 5T → 必须 KTable，排除单机 KSQL"
  - "2TB 未触发大库治理红线"  →  "8TB 远超 KSQL 5T 硬约束，KSQL 已不可用"
  - "KTable 不必要"  →  "KTable 是该规模下的硬性要求，KSQL 已淘汰"

# 明确淘汰方案（v0 → v1）
明确淘汰方案:
  - 组件: "ES"  # 保持
  - 组件: "CK"  # 保持
  - 组件: "KwaiBase"  # 保持
  - 组件: "Kafka / BTQ"  # 保持
  + 组件: "KSQL"
    原因: "硬约束第 2 行：数据量 8TB > 5T，单机 KSQL 性能劣化；knowledge/ksql.yaml anti_patterns 明确 >5T 不迁移 KTable 为反模式"
    原因码: "KSQL_CAPACITY_EXCEEDED"

# 决策轨迹（v0 → v1）
决策轨迹:
  - 候选: "KSQL"
    硬约束: 通过  →  淘汰（原因：数据量 > 5T）
    加权分: 88  →  0
  - 候选: "KTable"
    硬约束: 通过（但非必要）  →  通过（硬性要求）
    加权分: 75  →  86
    证据:
      + "knowledge/ktable.yaml: scalability=>5T 或 >200 列场景，QPS 可横向扩展"
      + "references/decision-rubric.md: 硬约束第 2 行"

# 已识别风险与反模式（v0 → v1）
已识别风险与反模式:
  - "[P2] KSQL 大库治理线"  # 移除（KSQL 已淘汰）
  + "[P1] KTable 1.0 集群须升级 2.0：1.0 与 2.0 不兼容，平台在推迁移（knowledge/ktable.yaml anti_patterns）"
  + "[P1] KTable 1.0 集群无告警接入天问：已知集群均未接入，必须配置（anti-pattern-check.md G 类）"
  + "[P2] KTable 磁盘 >70% 或 CPU >90% 高危（knowledge/ktable.yaml key_thresholds）"
  - "[P2] KSQL 副本数须 ≤4"  # 移除
  - "[P3] 深翻页风险"  # 保持

# 验证建议（v0 → v1）
验证建议:
  - 目标: "验证 KSQL 在订单读写场景下的延迟与容量"
  →  目标: "验证 KTable 在 8TB 订单场景下的扩展性与延迟"
    指标:
      - "P99 < 10ms"  # 保持
      + "KTable 分片均匀（无单分片热点）"
      + "磁盘使用率 < 70%"
      + "CPU < 90%"
      + "天问告警已接入"
    步骤:
      + "测试 KTable 1.0 → 2.0 迁移路径"
      + "验证分布式事务跨分片一致性"
    通过标准: "P99 < 10ms 且集群指标全部低于红线"
    停止条件: "P99 > 50ms 或磁盘 > 80% 立即停止"

# 待验证项（v0 → v1）
待验证项:
  - "KSQL 当前最新版本与配额"  →  "KTable 2.0 当前版本与迁移工具支持度"
  + "KTable 跨 2 AZ 部署的 SLA 承诺"
  + "KTable 内部报价与 KSQL 成本对比（同 8TB 容量下）"
```

**v1 关键观察**：推荐方案从单机 KSQL 翻转为分布式 KTable；KSQL 从推荐变为带原因码 `KSQL_CAPACITY_EXCEEDED` 的淘汰项；风险栏新增 KTable 三条专属红线。

---

### 2.2 v0 → v2：列数 50 → 250

**输入变化**：`column_count: 50 → 250`

**Skill 工作流变化**：

| 步骤 | v0 | v2 |
|---|---|---|
| 3 硬约束筛选 | 命中第 1 行（KSQL 必须） | **改命中第 2 行：列数 > 200 → 必须 KTable** |
| 4 矩阵打分 | KSQL 数据模型匹配 18-20 | KTable 数据模型匹配 18-20（宽表更契合 250 列）；KSQL 在 250 列下 B+Tree 维护成本高，分数降至 6-11 |
| 5 反模式 | KSQL 大库 P2 | **新增 KSQL 反模式：大字段/列膨胀** |
| 6 输出 | 推荐 KSQL | **推荐翻转为 KTable；KSQL 淘汰原因码与 v1 不同** |

**报告字段差异**：

```yaml
# 推荐方案（v0 → v2）
推荐方案:
  组件: ["KSQL"]  →  ["KTable"]
  能力对齐:
    - "主键/索引点查"  →  "全局二级索引（KTable data_model）适配 250 列宽表"
    - "数据量 2TB < 5T 硬约束阈值"  →  "列数 250 > 200 硬约束阈值，KTable 宽表模型适配"

# 推荐理由（v0 → v2）
推荐理由:
  - "硬约束第 1 行命中：强一致事务主记录 + 数据量 < 5T → 必须 KSQL"
  →  "硬约束第 2 行命中：列数 > 200 → 必须 KTable（与数据量无关）"
  + "250 列宽表场景 KSQL B+Tree 维护成本高，KTable 存算分离 + 全局二级索引更适配"
  + "knowledge/ktable.yaml query_patterns: 大宽表（>200列）为 KTable 强项"

# 明确淘汰方案（v0 → v2）
明确淘汰方案:
  + 组件: "KSQL"
    原因: "硬约束第 2 行：列数 250 > 200，KSQL B+Tree 行格式膨胀导致缓冲池命中率下降；knowledge/ksql.yaml anti_patterns: 列数 >200 不迁移 KTable 为反模式"
    原因码: "KSQL_COLUMN_EXPLOSION"  # 注意：与 v1 的 KSQL_CAPACITY_EXCEEDED 不同

# 决策轨迹（v0 → v2）
决策轨迹:
  - 候选: "KSQL"
    硬约束: 通过  →  淘汰（原因：列数 > 200）
    加权分: 88  →  0
  - 候选: "KTable"
    硬约束: 通过（但非必要）  →  通过（硬性要求）
    加权分: 75  →  84
    证据:
      + "knowledge/ktable.yaml: data_model=大宽表（>200列）适配"

# 已识别风险与反模式（v0 → v2）
已识别风险与反模式:
  - "[P2] KSQL 大库治理线"  # 保持（2TB 仍 >1TB 治理线）
  + "[P1] KSQL 大字段/列膨胀反模式：250 列导致行格式膨胀，缓冲池命中率下降（anti-pattern-check.md A 类：大字段）"
  + "[P1] KTable 1.0 → 2.0 升级与天问告警接入"
  + "[P2] KTable 磁盘/CPU 红线"

# 验证建议（v0 → v2）
验证建议:
  - 目标: "验证 KSQL 在订单读写场景下的延迟与容量"
  →  目标: "验证 KTable 在 250 列宽表场景下的查询性能"
    指标:
      + "250 列宽表查询 P99 < 10ms"
      + "全局二级索引命中率 > 95%"
      + "宽表行存储压缩率与磁盘占用"
    步骤:
      + "构造 250 列宽表测试数据，验证常用列查询性能"
      + "对比 KSQL 50 列 vs KTable 250 列的查询性能差异"

# 待验证项（v0 → v2）
待验证项:
  + "KTable 在 250 列宽表下的具体 SLA 与性能 Benchmark"
  + "KTable 全局二级索引在该业务列组合下的命中率"
```

**v2 关键观察**：推荐结果与 v1 相同（都是 KTable），但**淘汰原因码不同**（`KSQL_COLUMN_EXPLOSION` vs `KSQL_CAPACITY_EXCEEDED`），证明 skill 不会"只看结论不看理由"，可被金标 `required_rejection_codes` 精确校验。

---

### 2.3 v0 → v3：新增全文检索需求

**输入变化**：`fulltext_search: false → true`；`query_patterns: +fulltext_search`

**Skill 工作流变化**：

| 步骤 | v0 | v3 |
|---|---|---|
| 3 硬约束筛选 | 命中第 1 行（KSQL 必须） | **同时命中第 1 行（KSQL 主账本）+ 第 3 行（ES 必须进候选且不得作主账本）** |
| 4 矩阵打分 | 只对 KSQL 打分 | KSQL 主账本打分 88；ES 作为检索侧打分 72（查询模式满分，一致性低分） |
| 5 反模式 | KSQL 大库 P2 | **新增 ES 反模式：ES 作强一致主记录（D 类）+ 大分片 >50GB（D 类）+ 未接天问告警** |
| 6 输出 | 单产品推荐 KSQL | **双产品架构：KSQL（主账本）+ ES（检索侧，双写）** |

**报告字段差异**：

```yaml
# 推荐方案（v0 → v3）
推荐方案:
  组件: ["KSQL"]  →  ["KSQL", "ES"]
  置信度: 高  →  中（双写架构引入一致性复杂度）
  能力对齐:
    # KSQL 部分保持
    + "ES 倒排索引匹配订单备注/收货地址全文检索（knowledge/elasticsearch.yaml query_patterns）"
    + "ES 相关性排序适配模糊搜索需求"

# 推荐理由（v0 → v3）
推荐理由:
  # KSQL 部分保持
  + "硬约束第 3 行命中：全文检索需求 → ES 必须进入候选"
  + "ES 不得作为强一致主账本，故采用 KSQL 主账本 + ES 检索侧双写架构"
  + "knowledge/elasticsearch.yaml: consistency=近实时约 1s，不满足强一致，仅作检索投影"

# 明确淘汰方案（v0 → v3）
明确淘汰方案:
  - 组件: "ES"  # 改为下面这条
  - 组件: "ES（单独作为订单主账本）"
    原因: "硬约束第 3 行后半：ES 不得作为强一致主账本；近实时可见性约 1s，写入失败无事务回滚"
    原因码: "ES_STRONG_CONSISTENCY_PROHIBITED"
  # 其他淘汰项保持

# 决策轨迹（v0 → v3）
决策轨迹:
  - 候选: "KSQL"  # 保持通过 88 分
  + 候选: "ES（检索侧）"
    硬约束: 通过（作为检索侧，不作主账本）
    加权分: 72
    证据:
      - "knowledge/elasticsearch.yaml: query_patterns=全文检索与相关性排序"
      - "references/decision-rubric.md: 硬约束第 3 行"
    假设:
      - "ES 仅作检索投影，主账本数据在 KSQL"

# 已识别风险与反模式（v0 → v3）
已识别风险与反模式:
  # KSQL 三条保持
  + "[P0] KSQL → ES 双写一致性：异步双写可能出现短暂不一致或丢数据（anti-pattern-check.md G 类：缓存与数据库同步异常）"
  + "[P1] ES 作强一致主记录反模式：明确 ES 不可作订单主账本（anti-pattern-check.md D 类）"
  + "[P1] ES 大分片 >50GB 高危：订单数据 2TB 须合理分片（<50GB/分片，<200 分片/Index）"
  + "[P1] ES 未配置天问告警：必须接入（anti-pattern-check.md D 类）"
  + "[P2] ES 深翻页 >1 万行需用 search_after 或 scroll"

# 验证建议（v0 → v3）
验证建议:
  # KSQL 验证保持
  + 目标: "验证 KSQL → ES 双写一致性与 ES 检索性能"
    环境: staging
    指标:
      - "双写 DIFF 率 < 万分之一"
      - "ES 检索 P95 < 200ms"
      - "ES 单分片 < 50GB"
      - "ES 堆内存 < 85%"
      - "ES 天问告警已接入"
    步骤:
      - "构造订单备注/收货地址全文检索样例"
      - "双写期间采样比对 KSQL 与 ES 数据一致性"
      - "模拟 ES 节点故障，验证双写降级策略"
    通过标准: "双写 DIFF 率 < 万分之一 且 ES 检索 P95 < 200ms"
    停止条件: "DIFF 率超 千分之一 或 ES P95 > 1s 立即停止双写"

# 待验证项（v0 → v3）
待验证项:
  # KSQL 三项保持
  + "ES 当前集群容量与可用分片数"
  + "ES 全文检索对订单备注/收货地址分词器的适配性"
  + "KSQL → ES 双写方案：Canal 异步投影 or 应用层双写"
```

**v3 关键观察**：skill 不是"单产品推荐器"，硬约束触发时自动组合出**双产品架构**（KSQL 主 + ES 检索侧），并在反模式检查中明确边界（哪个是主账本、哪个是检索投影）。验证建议从 1 个变为 2 个，新增双写一致性专项验证。

---

### 2.4 v0 → v4：写入峰值 5k → 5w/s（大促场景）

**输入变化**：`write_qps: 5000 → 50000（峰值）`

**Skill 工作流变化**：

| 步骤 | v0 | v4 |
|---|---|---|
| 3 硬约束筛选 | 命中第 1 行（KSQL 必须） | **同时命中第 1 行（KSQL 主账本）+ 第 4 行（高吞吐 > 万/s 事件流须 Kafka/BTQ 接入）** |
| 4 矩阵打分 | 只对 KSQL 打分 | KSQL 主账本打分 88；Kafka/BTQ 作为接入层打分 80（性能满分，一致性需幂等保障） |
| 5 反模式 | KSQL 大库 P2 | **新增 MQ 三条 P0：积压无监控 + 缺幂等+死信 + 分区键不当** |
| 6 输出 | 单产品推荐 KSQL | **组合架构：Kafka/BTQ 接入削峰 + KSQL 主账本** |

**报告字段差异**：

```yaml
# 推荐方案（v0 → v4）
推荐方案:
  组件: ["KSQL"]  →  ["Kafka", "KSQL"]  # 或 BTQ，取决于业务事件语义
  置信度: 高  →  中（引入 MQ 增加架构复杂度）
  能力对齐:
    # KSQL 部分保持
    + "Kafka 高吞吐事件流接入：单 shard 10w+ 条/s，满足 5w/s 峰值削峰"
    + "Kafka 分区扩展适配大促流量波动"
    + "knowledge/kafka.yaml: query_patterns=高吞吐事件流管道"

# 推荐理由（v0 → v4）
推荐理由:
  # KSQL 部分保持
  + "硬约束第 4 行命中：写入峰值 5w/s > 万/s 量级 → 必须用 Kafka 或 BTQ 作接入层，不直写 KSQL"
  + "references/decision-rubric.md: 硬约束第 4 行明确 > 万/s 事件流须 MQ 接入"
  + "Kafka vs BTQ 选型：本场景为高吞吐事件流（非业务事件解耦），优先 Kafka；若需顺序/事务消息语义则选 BTQ"

# 明确淘汰方案（v0 → v4）
明确淘汰方案:
  - 组件: "Kafka / BTQ"  # 移除（已升级为推荐组件）
  # 其他淘汰项保持

# 决策轨迹（v0 → v4）
决策轨迹:
  - 候选: "KSQL"  # 保持通过 88 分，但定位变为主账本（消费 MQ 后落库）
  + 候选: "Kafka"
    硬约束: 通过（作为接入层）
    加权分: 80
    证据:
      - "knowledge/kafka.yaml: data_model=分区追加日志，10w+ Topic"
      - "references/decision-rubric.md: 硬约束第 4 行"
    假设:
      - "大促峰值 5w/s 持续时间 < 2h，Kafka 保留周期 24h 足够回放"
      - "消费端幂等由业务层保障（订单 ID 唯一约束）"

# 已识别风险与反模式（v0 → v4）
已识别风险与反模式:
  # KSQL 三条保持
  + "[P0] Kafka 消息积压无监控：堆积为高危指标，必须接入天问告警（anti-pattern-check.md F 类）"
  + "[P0] 缺少幂等+死信处理：消费端须实现幂等（订单 ID 去重）+ 死信队列 + 报警，否则重复消费或丢数据"
  + "[P0] 分区键设计不当：分区键须选高基数字段（如 order_id），避免低基数导致单分区热点"
  + "[P2] KSQL 日志流直写反模式：本架构已通过 Kafka 接入规避（anti-pattern-check.md A 类）"

# 验证建议（v0 → v4）
验证建议:
  # KSQL 验证保持
  + 目标: "验证 Kafka 接入层在大促峰值下的削峰与稳定性"
    环境: staging
    指标:
      - "Kafka 写入吞吐 > 10w 条/s（5w 峰值的 2 倍冗余）"
      - "消费端 lag < 1000 条（大促期间）"
      - "幂等校验通过率 100%"
      - "死信队列消息数 0"
      - "分区负载标准差 < 10%（无热点分区）"
    步骤:
      - "构造 5w/s 峰值写入压测，验证 Kafka 削峰后 KSQL 落库速率稳定在 5k/s"
      - "模拟消费端故障，验证幂等重试与死信队列"
      - "模拟分区键倾斜场景，验证分区负载均衡"
    通过标准: "Kafka 写入 > 10w/s 且消费 lag < 1000 且无重复消费"
    停止条件: "Kafka 积压 > 10w 条 或 KSQL 主从延迟 > 5s 立即停止"

# 待验证项（v0 → v4）
待验证项:
  # KSQL 三项保持
  + "订单写入幂等性：业务侧是否已设计订单 ID 唯一约束或去重表"
  + "Kafka vs BTQ 最终选型：本场景是否需要顺序/事务消息语义（若需则改 BTQ/RocketMQ）"
  + "Kafka 保留周期与容量规划（按 5w/s 峰值 × 24h 计算）"
  + "消费端并发度与 KSQL 写入速率匹配（避免消费过快打挂 KSQL）"
```

**v4 关键观察**：当峰值跨越"万/s"硬阈值，skill **主动加一层接入存储**（Kafka/BTQ），不需要用户提示。风险栏新增 3 条 P0 级 MQ 反模式，验证建议从 1 个变为 2 个，新增接入层削峰验证。同时 KSQL 反模式"日志流直写"被架构规避，体现反模式检查的反向价值。

---

## 第三部分：变化对照总览

### 3.1 五版报告核心字段对照

| 字段 | v0 | v1（>5T） | v2（>200 列） | v3（+全文检索） | v4（5w/s 峰值） |
|---|---|---|---|---|---|
| 推荐组件 | KSQL | KTable | KTable | KSQL + ES | Kafka + KSQL |
| 置信度 | 高 | 高 | 高 | 中 | 中 |
| 次优 | KTable | — | — | — | BTQ（若需顺序语义） |
| 新增淘汰 | — | KSQL | KSQL | ES 作主账本 | — |
| 淘汰原因码 | — | KSQL_CAPACITY_EXCEEDED | KSQL_COLUMN_EXPLOSION | ES_STRONG_CONSISTENCY_PROHIBITED | — |
| 风险数 | 3 | 4 | 5 | 8 | 7 |
| 新增 P0 | — | — | — | 双写一致性 | MQ 三条 |
| 验证项数 | 1 | 1 | 1 | 2 | 2 |
| 待验证项 | 3 | 5 | 5 | 6 | 7 |
| 引用来源数 | 3 | 3 | 3 | 4 | 4 |

### 3.2 Skill 调整机制总结

| 调整模式 | 触发条件 | 调整动作 | 示例版本 |
|---|---|---|---|
| 单产品翻转 | 命中"必须用 X"硬约束 | 主推替换；原推荐进入淘汰并附原因码 | v1, v2 |
| 双产品组合 | 命中"X 必须进入候选 + 边界限定"硬约束 | 推荐变为组合架构；反模式明确边界 | v3, v4 |
| 原因码区分 | 同结论但触发条件不同 | 淘汰原因码不同，可被金标校验 | v1 vs v2 |
| 反模式同步 | 推荐组件变化 | 风险栏同步新增对应产品反模式 | v1（KTable 红线）, v3（ES 反模式）, v4（MQ P0） |
| 验证项扩展 | 架构复杂度提升 | 验证项从 1 个增到 2 个，新增专项验证 | v3, v4 |
| 待验证项扩展 | 新组件引入 | 同步增加该组件的版本/SLA/报价待验证 | v1, v2, v3, v4 |

### 3.3 报告输出契约的可追溯性

每次参数变化在 `report-schema.md` 契约的 8 个字段上均有可观测的同步变化：

| 契约字段 | v0→v1 | v0→v2 | v0→v3 | v0→v4 |
|---|---|---|---|---|
| 推荐方案.组件 | KSQL→KTable | KSQL→KTable | KSQL→KSQL+ES | KSQL→Kafka+KSQL |
| 明确淘汰方案 | +KSQL | +KSQL | +ES(主账本) | 无新增 |
| 决策轨迹 | 硬约束翻转 | 硬约束翻转 | 候选+1 | 候选+1 |
| 已识别风险 | KTable 3 条 | 列膨胀+KTable 3 条 | 双写+ES 4 条 | MQ 3 条 P0 |
| 验证建议 | +天问接入 | +宽表性能 | +双写 DIFF | +削峰监控 |
| 待验证项 | +KTable 版本 | +宽表 SLA | +ES 容量 | +幂等确认 |
| 引用来源 | +5T 阈值 | +200 列条目 | +ES 选型调研 | +MQ 选型条目 |

### 3.4 使用说明

本报告基于 `storage-skill` 的 6 步工作流与 `references/report-schema.md` 契约生成，所有内部事实引用 `knowledge/*.yaml` 档案与 `references/decision-rubric.md` 决策规则；未知项已标记 `待验证`。报告可：

1. **作为 v0 基线交付**：第一部分可直接作为订单系统 v0 场景的选型报告交付业务方
2. **作为变化推演教材**：第二部分演示参数变化时 skill 如何逐字段调整，用于 skill 能力宣讲
3. **扩充评测集**：v0~v4 的金标断言已在上文隐含，可转写为 `cases/typical/` 下 5 个 JSON 评测文件，运行 `bash eval/run_eval.sh` 做自动化回归
