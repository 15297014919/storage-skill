#!/usr/bin/env python3
"""Deterministic, read-only storage-selection rule engine for regression evaluation."""
import argparse
import json
from pathlib import Path

EVIDENCE = {"source": "references/decision-rubric.md", "claim": "2025 快手存储选型硬约束与能力矩阵"}


def risk(code, severity, description, mitigation):
    return {"code": code, "severity": severity, "description": description, "mitigation": mitigation}


def rejection(component, code, reason):
    return {"component": component, "reason_code": code, "reason": reason}


def validation(topic, metric):
    return {"topic": topic, "environment": "staging", "metric": metric,
            "pass_criteria": "满足经确认的业务目标且无错误率回归", "stop_condition": "延迟、错误率或资源水位超过安全阈值即停止"}


def score(component, hard_constraint, total, evidence):
    return {"component": component, "hard_constraint": hard_constraint, "score": total, "evidence": evidence}


def validate_input(data):
    required = {"scenario", "data_model", "consistency", "query_patterns"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"输入缺少必填字段: {sorted(missing)}")
    if data["data_model"] not in {"relation", "kv", "wide_table", "document", "search", "olap", "event_stream", "graph", "vector"}:
        raise ValueError("data_model 不在允许枚举中")
    if data["consistency"] not in {"strong", "eventual", "none", "unknown"}:
        raise ValueError("consistency 不在允许枚举中")
    if not isinstance(data["query_patterns"], list) or not data["query_patterns"]:
        raise ValueError("query_patterns 必须是非空数组")


def select(data):
    patterns = set(data["query_patterns"])
    known_risks = set(data.get("known_risks", []))
    scale = data.get("data_scale_tb")
    columns = data.get("column_count")
    write_qps = data.get("write_qps", 0)
    density = data.get("access_density_per_gb")
    mode = data.get("workload_mode", "unknown")
    primary, reasons, alternatives, rejections, risks, validations, trace = [], [], [], [], [], [], []
    assumptions = []

    strong_transaction = data["consistency"] == "strong" or data.get("transaction_required")
    if strong_transaction:
        if scale is not None and scale > 5 or columns is not None and columns > 200:
            primary = ["KTable"]
            reasons.append("强一致事务数据且规模超过 KSQL 的 5TB/200 列硬约束，选择 KTable。")
            rejections.append(rejection("KSQL", "KSQL_SCALE_LIMIT", "数据规模或列数超过 KSQL 推荐边界。"))
            trace.append({"rule_id": "STRONG_TRANSACTION_LARGE_SCALE", "decision": "REQUIRE", "component": "KTable"})
        else:
            primary = ["KSQL"]
            reasons.append("强一致事务主记录且未超过 KSQL 容量边界，选择 KSQL。")
            alternatives.append({"components": ["KTable"], "applicable_when": ["数据量超过 5TB", "列数超过 200", "需要横向扩展"]})
            trace.append({"rule_id": "STRONG_TRANSACTION_UNDER_5TB", "decision": "REQUIRE", "component": "KSQL"})
        rejections.append(rejection("ES", "NOT_STRONG_CONSISTENT_PRIMARY_STORE", "ES 为近实时索引，不可作为强一致主记录。"))
        if "es_as_primary" in known_risks:
            risks.append(risk("ES_AS_PRIMARY", "P0", "ES 作为唯一订单主存不满足写后强一致。", "以 KSQL/KTable 为权威主存，异步构建 ES 搜索投影。"))
        if "replica_overload" in known_risks:
            rejections.append(rejection("扩容从库", "DEFERRED_SHARDING_RISK", "容量快速增长时等待到上限再分库分表会放大资金链路迁移风险。"))
            risks += [risk("REPLICA_OVERLOAD", "P1", "副本数超过健康阈值会增加主从延迟和运维成本。", "优先降至健康副本数，并在低负载窗口完成分库分表。"), risk("LARGE_TABLE_GROWTH", "P1", "持续高增量会快速触及大库大表红线。", "按订单 ID 规划分库分表和数据归档。")]
            validations += [validation("sharding_routing", "分库分表路由正确率"), validation("data_consistency", "双写阶段数据 DIFF 率")]

    # codeflicker-fix: LOGIC-Issue-002/d8mms5q7xd5xjg3mo5qm
    elif data["data_model"] == "olap":
        if "high_frequency_update" in patterns:
            primary = ["KCache", "CK"]
            reasons.append("实时状态使用 KCache 承接热点更新，历史明细使用 CK 追加写和聚合查询，避免 CK 高频 UPDATE。")
            rejections.append(rejection("CK", "CK_HIGH_FREQUENCY_UPDATE", "ReplacingMergeTree 高频 UPDATE/Mutation 会堆积 Parts 并触发 readonly 风险。"))
            risks.append(risk("TOO_MANY_PARTS", "P1", "高频小批写或 Mutation 会触发 CK too-many-parts。", "改为追加写、物化视图预聚合，并按批次导入。"))
            validations += [validation("batch_write", "Parts 数量、批次写入延迟和聚合 P99"), validation("hot_key", "实时状态 Key 的热点负载")]
            trace.append({"rule_id": "CK_HIGH_FREQUENCY_UPDATE", "decision": "REQUIRE", "component": "KCache"})
        elif "benchmark_ck_migration" in patterns:
            primary = ["CK"]
            reasons.append("已提供的高吞吐报表 Benchmark 显示 CK 在目标 QPS、导入 lag 和资源效率上优于当前 Doris。")
            rejections.append(rejection("Doris", "DORIS_BENCHMARK_CAPACITY", "当前 Doris 在目标导入吞吐和查询 P99 下已出现 lag 与稳定性不足。"))
            risks += [risk("TOO_MANY_PARTS", "P1", "CK 高频小批写会造成 Part/Merge 压力。", "采用批量导入和预聚合。"), risk("SHARD_SKEW", "P1", "分片不均会造成热 Shard 瓶颈。", "按稳定哈希设计分片键并验证负载均衡。")]
            validations += [validation("benchmark_latency", "目标 QPS 下 CK 与 Doris 的查询 P99"), validation("batch_write", "导入 lag、CPU 水位与 Parts 数量")]
            trace.append({"rule_id": "CK_BENCHMARK_MIGRATION", "decision": "REQUIRE", "component": "CK"})

    elif "event_stream" in patterns or (data["data_model"] == "event_stream" and write_qps >= 10000):
        primary = ["Kafka", "Doris"]
        reasons.append("高吞吐持续事件流应由 Kafka 接入，并使用 Doris 承接交互式聚合分析。")
        alternatives.append({"components": ["BTQ", "CK"], "applicable_when": ["业务事件语义更适合 BTQ", "已有 CK 集群且完成 Doris 替代评估"]})
        rejections.append(rejection("KSQL", "LOG_STREAM_DIRECT_TO_KSQL", "高吞吐日志流直写 KSQL 会产生写放大并影响长期分析。"))
        trace.append({"rule_id": "HIGH_THROUGHPUT_EVENT_STREAM", "decision": "REQUIRE", "component": "Kafka"})
        risks += [risk("SMALL_BATCH_WRITE", "P1", "OLAP 小批频繁写入会造成 Part/Merge 压力。", "攒批写入并验证批次大小。"), risk("MESSAGE_BACKLOG", "P1", "消息积压会导致消费延迟和可用性风险。", "配置积压监控、告警、幂等与死信队列。")]
        validations += [validation("message_backlog", "生产与消费延迟"), validation("batch_write", "批次大小、写入延迟与 Merge 水位")]

    elif "full_text_search" in patterns or data["data_model"] == "search":
        primary = ["ES"]
        reasons.append("全文检索与相关性排序命中 ES 的原生倒排索引能力。")
        trace.append({"rule_id": "FULL_TEXT_SEARCH", "decision": "REQUIRE", "component": "ES"})
        if "index_mapping" in known_risks:
            risks.append(risk("INDEX_MAPPING", "P1", "字段膨胀或不当 mapping 会增加 ES 内存与分片压力。", "限制字段、设计 mapping，并控制分片大小。"))
        validations += [validation("staging_latency", "搜索 P99 延迟和召回质量"), validation("shard_size", "分片大小与堆内存水位")]

    elif data["data_model"] == "wide_table":
        if mode in {"online", "nearline"}:
            primary = ["KwaiBase"]
            reasons.append("在线/近线宽表为硬约束，优先使用 KwaiBase，禁止新增 HBase 在线集群。")
            rejections.append(rejection("HBase", "ONLINE_HBASE_PROHIBITED", "HBase 在线场景处于维护与迁移方向，不应新增。"))
            trace.append({"rule_id": "ONLINE_WIDE_TABLE", "decision": "REQUIRE", "component": "KwaiBase"})
        else:
            primary = ["HBase"]
            reasons.append("离线大数据宽表可使用 HBase。")
            alternatives.append({"components": ["KwaiBase"], "applicable_when": ["转为在线或近线访问"]})
            trace.append({"rule_id": "OFFLINE_WIDE_TABLE", "decision": "ALLOW", "component": "HBase"})
        if "secondary_index" in known_risks or "secondary_index" in patterns or "multi_filter" in patterns:
            if mode not in {"online", "nearline"}:
                primary.append("ES")
            rejections.append(rejection("HBase", "WIDE_TABLE_ARBITRARY_SECONDARY_INDEX", "宽表不能单独支持任意组合二级索引。"))
            risks.append(risk("SECONDARY_INDEX", "P1", "复杂组合查询会导致宽表全表扫描或索引同步问题。", "采用宽表加 ES 协同，并验证索引同步一致性。"))
            validations.append(validation("index_sync", "宽表到 ES 的同步延迟和一致性"))
        if "row_key_hotspot" in known_risks:
            risks.append(risk("ROW_KEY_HOTSPOT", "P1", "RowKey 分布不均会造成热点分区。", "使用散列前缀并验证分布均匀性。"))
            validations.append(validation("row_key_distribution", "分区负载与热点分布"))
        if "multi_layer_consistency" in known_risks:
            risks.append(risk("MULTI_LAYER_CONSISTENCY", "P1", "多层存储会增加双写和回源一致性风险。", "迁移期间执行双读 DIFF 校验，并逐步收敛为单层宽表。"))
        if "cache_replacement" in known_risks:
            rejections.append(rejection("KSQL", "MYSQL_KV_COST_OVERHEAD", "纯 KV/列表数据继续使用 MySQL 加缓存会保留分库分表与缓存一致性成本。"))
            risks.append(risk("CACHE_REPLACEMENT", "P1", "替代缓存前需验证热点读是否仍满足延迟目标。", "在 staging 回放热点流量并保留降级缓存。"))
            validations.append(validation("capacity_cost", "存储与缓存层成本估算"))
        if "secondary_index" in known_risks and mode in {"online", "nearline"}:
            rejections.append(rejection("KSQL", "MYSQL_SHARDING_OVERHEAD", "纯 KV 关系数据继续分库分表会增加人工扩容与缓存维护成本。"))
        validations.append(validation("staging_latency", "点查与前缀访问 P99 延迟"))

    elif data["data_model"] == "graph":
        primary = ["KGraph"]
        reasons.append("有序的用户到内容关系列表符合 KGraph 的关系集合与图语义模型。")
        rejections.append(rejection("MySQL + Redis", "MYSQL_REDIS_DUAL_LAYER_OVERHEAD", "双层架构需要维护缓存一致性、回源和人工扩容，关系模型可由单层图存储承接。"))
        trace.append({"rule_id": "ORDERED_GRAPH_RELATION", "decision": "REQUIRE", "component": "KGraph"})
        if "graph_hotspot" in known_risks:
            risks.append(risk("GRAPH_HOTSPOT", "P1", "头部用户的关系列表可能形成热点读写。", "回放头部用户流量并为热点配置本地缓存或隔离。"))
        if "migration_consistency" in known_risks:
            risks.append(risk("MIGRATION_CONSISTENCY", "P1", "双写迁移期间可能出现有序列表数据差异。", "执行双写、双读 DIFF 校验后再灰度切换。"))
        validations += [validation("staging_latency", "有序列表分页查询与写入 P99"), validation("data_consistency", "迁移双写数据 DIFF 率")]

    elif data["data_model"] == "kv":
        if data.get("persistence_required") and density is not None and density < 300 and data.get("cost_sensitive") == "high":
            primary = ["Kiwi"]
            reasons.append("低访问密度、需持久化且成本敏感，选择 Kiwi/KwaiKV。")
            rejections.append(rejection("Redis", "REDIS_COLD_DATA_COST", "低频长期冷数据使用 Redis 成本高且不适合作为冷存。"))
            trace.append({"rule_id": "LOW_DENSITY_PERSISTENT_KV", "decision": "REQUIRE", "component": "Kiwi"})
            risks.append(risk("REDIS_COLD_DATA", "P1", "冷数据放入 Redis 会造成高内存成本与容量浪费。", "使用 Kiwi 并在分片容量阈值内规划扩容。"))
            if "kiwi_write_limit" in known_risks:
                risks.append(risk("KIWI_WRITE_LIMIT", "P1", "Kiwi 批量写入吞吐需验证是否满足全量修复窗口。", "用脱敏样本压测并按标签数拆分批量任务。"))
            if "hot_label" in known_risks:
                risks.append(risk("HOT_LABEL", "P1", "高频标签不适合全部放入 Kiwi。", "按访问密度分层，将热标签保留在 Redis 或 KCache。"))
            validations += [validation("capacity_cost", "单位容量成本和分片水位"), validation("batch_write", "批量写入吞吐与全量修复窗口"), validation("staging_latency", "KV 读写 P99 延迟")]
        else:
            primary = ["Redis"] if density is None or density > 1000 else ["KCache"]
            reasons.append("缓存 KV 根据访问密度选择 Redis 或 KCache。")
            alternatives.append({"components": ["KCache" if primary == ["Redis"] else "Redis"], "applicable_when": ["访问密度、命令兼容性或热点特征变化"]})
            trace.append({"rule_id": "CACHE_BY_ACCESS_DENSITY", "decision": "PREFER", "component": primary[0]})
            rejections.append(rejection("Memcached", "MEMCACHED_NEW_USAGE_DEPRECATED", "Memcached 是迁移方向，新场景不建议新增使用。"))
            if "hot_key" in known_risks:
                risks.append(risk("HOT_KEY", "P1", "热点 Key 可能造成单核瓶颈和延迟抖动。", "打散热点、增加本地缓存或评估 KCache。"))
            if "cross_service_hotkey" in known_risks:
                primary = ["KCache"]
                reasons.append("跨服务热 Key 场景优先选择 KCache，并隔离业务集群以避免热点扩散。")
                rejections.append(rejection("Redis", "REDIS_HOT_KEY_LIMIT", "单 Key 超过 Redis 热点阈值会影响同集群其他服务。"))
                risks.append(risk("CROSS_SERVICE_HOTKEY", "P1", "共享集群中的热点会跨服务传播延迟风险。", "使用多副本 Key 打散并进行物理或逻辑集群隔离。"))
                validations.append(validation("cluster_isolation", "隔离后其他服务的 RT 波动和热点告警"))
            if "kiwi_write_limit" in known_risks:
                risks.append(risk("KIWI_WRITE_LIMIT", "P1", "Kiwi 批量写入吞吐需验证是否满足全量修复窗口。", "用脱敏样本压测并按标签数拆分批量任务。"))
            if "hot_label" in known_risks:
                risks.append(risk("HOT_LABEL", "P1", "高频标签不适合全部放入 Kiwi。", "按访问密度分层，将热标签保留在 Redis 或 KCache。"))
            if "cache_consistency" in known_risks:
                risks.append(risk("CACHE_CONSISTENCY", "P1", "缓存与主存同步异常会导致旧数据或不一致。", "采用先更新主存再删缓存或异步投影，并设计回滚。"))
            validations += [validation("staging_latency", "缓存命中 P99 延迟"), validation("hot_key", "单 Key QPS 与热点打散效果")]

    else:
        primary = ["待人工确认"]
        reasons.append("当前输入未命中确定性硬约束，需要补充数据模型和访问模式。")
        assumptions.append("补充业务关键约束后重新执行选型。")
        validations.append(validation("staging_latency", "补齐场景后验证核心访问延迟"))

    if data.get("availability", {}).get("cross_region"):
        assumptions.append("跨地域 RPO/RTO 与平台复制能力必须查验当前内部文档，不在本地规则层承诺。")
    if scale is None:
        assumptions.append("未提供数据规模，容量边界结论需在补充规模后复核。")

    candidate_scores = [score(component, "通过", 90 if component in primary else 70, "硬约束与能力矩阵") for component in primary]
    return {"report_version": "1.0", "recommendation": {"components": primary, "confidence": "high" if not assumptions else "medium", "reasons": reasons}, "alternatives": alternatives, "rejections": rejections, "decision_trace": {"hard_constraints": trace, "candidate_scores": candidate_scores, "assumptions": assumptions}, "risks": risks, "validation_plan": validations, "evidence": [EVIDENCE], "pending_verifications": assumptions}


def render_markdown(report):
    lines = ["# 存储选型报告", "", "## 推荐方案", ", ".join(report["recommendation"]["components"]), "", "## 推荐理由"]
    lines += [f"- {item}" for item in report["recommendation"]["reasons"]]
    lines += ["", "## 风险与反模式"] + [f"- [{item['severity']}] {item['code']}: {item['description']}" for item in report["risks"]]
    lines += ["", "## 验证建议"] + [f"- {item['topic']}（{item['environment']}）：{item['metric']}" for item in report["validation_plan"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    data = payload.get("input", payload)
    validate_input(data)
    report = select(data)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
