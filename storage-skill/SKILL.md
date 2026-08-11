---
name: storage-skill
description: 面向快手内部存储架构选型的结构化决策 Skill。当用户提出数据库、缓存、KV、宽表、搜索/OLAP、消息队列、文件/对象存储或向量检索的选型、架构评审、容量权衡、成本分析、反模式排查时触发。覆盖快手在用的存储产品：KSQL、KTable、Redis、KCache、Kiwi（KwaiKV）、Memcached、KwaiBase、HBase、Elasticsearch、ClickHouse、Doris（Bleem）、Kafka、BTQ、RocketMQ、KGraph、BlobStore、KFS、HDFS、Milvus 等，并输出推荐、备选、淘汰、风险、验证建议与证据来源。内部能力、SLA、成本数字需引用已审核的内部资料；查不到时标记"待验证"，禁止臆造。
---

# 快手存储架构选型

把业务约束转换为可追溯的存储选型报告，回答"选谁、为什么、有哪些坑、如何验证"。

## 强制边界

- 仅执行档案读取、内部文档检索和明确标记为只读的验证命令。
- 禁止读取生产敏感数据，禁止执行线上写入、压测、扩缩容或配置变更。
- 不得臆造内部中间件的 SLA、价格、配额或公司案例，查不到时标记 `待验证`。
- 引用内部资料时只给标题、链接或摘要；不得把未审核原文发布到外网。

## 公司存储产品速览

| 类型 | 产品 | 快手内部名 | 核心定位 |
|---|---|---|---|
| 关系型 | MySQL 自研版 | KSQL | < 5T 在线事务主库 |
| 分布式关系型 | KTable 2.0 | KTable | > 5T 或 > 200 列，可弹性扩展 |
| 内存缓存 | Redis 定制版 | Redis | 高性能缓存，全命令兼容 |
| 内存缓存 | 自研 AEP 缓存 | KCache | 热 Key 友好，成本低于 Redis |
| 持久化 KV | SSD KV 存储 | Kiwi / KwaiKV | 低访问密度、大容量、持久化 |
| 高性能缓存 | Memcached | Memcached | 超高 QPS 缓存（待迁移方向） |
| 宽表 | 自研在线宽表 | KwaiBase | 在线/近线 HBase 协议替代 |
| 宽表 | HBase 定制版 | HBase | 离线/大数据场景（在线场景迁 KwaiBase） |
| 搜索 | Elasticsearch | ES | 全文检索、日志分析 |
| OLAP | ClickHouse | CK | 大规模列式分析 |
| OLAP | Doris（Bleem） | Doris | 多表 Join、交互式分析、bitmap 圈选 |
| 图数据库 | 自研图数据库 | KGraph | 社交关系、推荐关联 |
| 消息队列 | Kafka | Kafka | 高吞吐事件流 |
| 消息队列 | 自研 MQ | BTQ / RocketMQ | 业务事件解耦 |
| 对象存储 | 自研对象存储 | BlobStore | 海量二进制文件 |
| 文件存储 | 自研文件系统 | KFS / HDFS | 共享文件 / 大数据管道 |
| 向量检索 | Milvus | Milvus | 超大规模向量检索 |

**2025 年官方选型路线图**：
- 关系库：KSQL（小）→ KTable（大），KSQL 8.0 持续升级
- 持久化 KV：Kiwi → KwaiKV（未来演进方向）
- 缓存：Memcached 待迁移至 Redis / KCache
- 宽表在线场景：HBase → KwaiBase
- OLAP：Doris（Bleem）已具备替换 CK 的能力
- 向量：小规模用 ES，超大规模用 Milvus

## 关键选型阈值（来源：2025快手四大存储选型标准）

| 场景 | 阈值 | 说明 |
|---|---|---|
| KSQL vs KTable | 数据量 < 5TB → KSQL；> 5TB 或列数 > 200 → KTable | |
| Redis vs KCache | 访问密度 < 1000/GB → 考虑 KCache；> 1000/GB → Redis | KCache 约 2.04 元/GB/月，Redis 约 4.28 元/GB/月（价格随时间变动，使用前查最新报价） |
| Redis vs Kiwi | 访问密度 < 300/GB + 持久化需求 → Kiwi；不持久化或高 QPS → Redis/KCache | Kiwi 约 0.32 元/GB/月，基于 SSD |
| MySQL 健康度：大库 | 单库 > 1TB | 需治理 |
| MySQL 健康度：大表 | 单表 > 50GB | 需治理 |
| MySQL 副本数 | > 4 副本 | 优先治理 |
| Redis 大 Key | 单 Key > 10KB | 需拆分 |
| Redis 热 Key | > 10w QPS | 需处理 |
| Redis 逐出 | 逐出数 > 0 | 预留容量不足 |
| Kiwi 单分片 | > 50GB | 运维效率低，不支持分裂 |
| KCache 利用率 | > 85% | 需扩容 |
| ES 分片大小 | 单分片 > 50GB | 高危 |
| ES 堆内存 | > 85% | 高危 |
| ES 查询耗时 | 峰值 > 10s | 高危 |

## 工作流

### 1. 澄清诉求

收集以下信息；缺失关键项时先提问，不要直接推荐：

- 数据规模、日增量、保留周期与冷热分层
- 峰值/平均读写 QPS、消息吞吐、对象大小
- P50/P95/P99 延迟目标
- 强一致、最终一致、事务与幂等要求
- 点查、范围查询、聚合、全文检索、复杂过滤等访问模式
- SLA、RTO、RPO、跨机房/跨 AZ 要求
- 预算、团队运维能力、扩缩容预期与迁移约束
- 是否有 hot key / 大 key 隐患

若用户无法补齐，明确列出假设及其对结论的影响。

### 2. 加载证据

- 按候选加载对应 `knowledge/*.yaml`。
- 读取 `references/decision-rubric.md` 获取打分与硬约束规则。
- 读取 `references/report-schema.md` 获取输出契约。
- 内部事实需通过内部文档检索确认（参考 `references/evidence-and-safety.md`）。

### 3. 筛选候选

先应用硬约束：

- 强事务/强一致主记录 → 优先 KSQL 或 KTable
- 数据量 > 5T 或列数 > 200 → KTable，排除单机 KSQL
- 全文检索/相关性排序 → ES 作索引，不作强一致主账本
- 高吞吐事件流 → Kafka 或 BTQ/RocketMQ
- 大规模分析聚合 → CK 或 Doris（Bleem）
- 超大规模向量检索 → Milvus
- 缓存/持久化 KV → 按访问密度和成本目标选 Redis/KCache/Kiwi

### 4. 矩阵打分

按 `references/decision-rubric.md` 给分并记录证据、假设和硬约束状态。

### 5. 反模式检查

读取 `prompts/anti-pattern-check.md`，重点关注公司真实故障场景（详见 cases/traps/）。

### 6. 输出报告

严格遵循 `references/report-schema.md`，必须包含需求摘要、推荐/备选/淘汰、打分轨迹、风险与反模式、staging/只读验证计划、引用来源和待验证项。

## 资源导航

- 产品能力档案：`knowledge/*.yaml`
- 决策评分规则：`references/decision-rubric.md`
- 报告格式契约：`references/report-schema.md`
- 安全与证据规范：`references/evidence-and-safety.md`
- 主决策 Prompt：`prompts/main.md`
- 反模式检查：`prompts/anti-pattern-check.md`
- 典型场景案例：`cases/typical/`
- 陷阱场景案例：`cases/traps/`
- 数据一致性校验：`python3 scripts/validate_skill_data.py .`
- 静态评测入口：`bash eval/run_eval.sh`

## 内部参考文档

以下文档为知识来源，访问前需内网权限：

- [《25快手存储健康度治理&业务存储架构演进》](https://docs.corp.kuaishou.com/d/home/fcADgnjSSO4AkIN4CGkfpsnKb)
- [2025快手四大存储选型标准](https://docs.corp.kuaishou.com/d/home/fcABmaRT3JxBzWIWc9wDTj7TI)
- [KV存储选型实践](https://docs.corp.kuaishou.com/d/home/fcABZNsQQ9p0-zVZR14rmdtOT)
- [存储健康度治理标准](https://docs.corp.kuaishou.com/d/home/fcAATr1i1vxEN0C816BZAf5-U)
- [ES/Doris/CK存储选型调研](https://docs.corp.kuaishou.com/k/home/VbM-rn1abDg0/fcADCuLf--w6IWU1-jnlmPWIy)

## 质量门禁

关键输入已获取或声明假设；硬约束先于评分；内部事实可追溯；推荐和淘汰理由成对出现；反模式已检查；验证步骤只读/staging；所有产品名使用内部名称（KSQL 不写 MySQL，KCache 不写 Memcached，KwaiBase 不写 HBase）。
