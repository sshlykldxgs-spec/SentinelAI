import math
from datetime import datetime, timezone

AGENTS = [
    {"id": "planner", "name": "Planner Agent", "role": "拆解决策目标与分析边界", "icon": "route"},
    {"id": "research", "name": "Research Agent", "role": "提取证据与数据来源", "icon": "search"},
    {"id": "analyst", "name": "Analyst Agent", "role": "量化趋势与关键指标", "icon": "chart"},
    {"id": "risk", "name": "Risk Reviewer Agent", "role": "审查假设、反例与风险", "icon": "shield"},
    {"id": "action", "name": "Action Agent", "role": "制定优先级与行动计划", "icon": "bolt"},
]

PROMPTS = {
    "planner": "你是企业决策规划师。用简短 summary 明确目标、范围与分析步骤，提供至少一条非空字符串 acceptance_conditions。遵守当前 Planner 输出 Schema；不要复制 Schema 或提前生成下游分析、风险和行动。不得编造事实。",
    "research": "你是研究员。只从提供的资料提取事实，引用文件名和行/字段；缺失信息要明确标记。不得使用外部来源。",
    "analyst": "你是量化分析师。结合资料和前序结果分析业务影响，明确数字计算依据，区别事实与假设。",
    "risk": "你是独立风险审查员。检查证据、数字、矛盾和未验证假设。发现严重问题必须标记 needs_evidence 或 human_review，不可无条件批准；置信度只描述证据支持程度与限制，不输出校准概率。",
    "action": "你是行动负责人。根据前序分析与风险审查，给出按优先级排列的行动、负责人角色、时间表、影响范围及审批需求。不得忽略风险审查意见。只生成建议，不执行外部操作。",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def supply_metrics(documents: list[dict]) -> dict | None:
    for document in documents:
        rows = document.get("rows", [])
        if not rows or not {"supplier", "on_time_rate", "defect_rate", "monthly_spend_usd"}.issubset(rows[0]):
            continue
        suppliers = []
        for row in rows:
            try:
                suppliers.append({
                    "name": row["supplier"],
                    "region": row.get("region", "未知"),
                    "on_time": float(row["on_time_rate"]),
                    "defect": float(row["defect_rate"]),
                    "spend": float(row["monthly_spend_usd"]),
                    "lead_time": float(row.get("lead_time_days") or 0),
                })
            except (ValueError, TypeError, KeyError):
                continue
        suppliers = [s for s in suppliers if all(math.isfinite(s[k]) for k in ('on_time', 'defect', 'spend', 'lead_time'))
                     and 0 <= s['on_time'] <= 100 and 0 <= s['defect'] <= 100 and s['spend'] >= 0 and s['lead_time'] >= 0]
        if not suppliers:
            continue
        spend = sum(item["spend"] for item in suppliers)
        return {
            "source": document["name"],
            "count": len(suppliers),
            "spend": round(spend),
            "on_time": round(sum(s["on_time"] for s in suppliers) / len(suppliers), 1),
            "defect": round(sum(s["defect"] for s in suppliers) / len(suppliers), 2),
            "suppliers": sorted(suppliers, key=lambda s: (s["on_time"], -s["defect"])),
        }
    return None


def demo_output(agent_id: str, run: dict, documents: list[dict]) -> str:
    metrics = supply_metrics(documents)
    source_list = "、".join(doc["name"] for doc in documents) or "无资料"
    if not metrics:
        snippets = "\n".join(
            f"- **{doc['name']}**：{doc['text'][:160].replace(chr(10), ' ')}…"
            for doc in documents[:5]
        ) or "- 尚未提供可分析资料。"
        generic = {
            "planner": f"围绕「{run['question']}」，依次核验资料、梳理发现、审查风险并形成行动建议。分析范围限于已上传文件。",
            "research": f"已检查 {len(documents)} 份资料：{source_list}。\n\n{snippets}",
            "analyst": "当前资料未包含标准供应商指标表；无法可靠计算交付、质量或成本趋势。建议补充带有时间字段的结构化数据后复核。",
            "risk": "**证据边界**：演示模式只做文档摘录和固定规则判断，不具备语义推理能力；不得将摘要视为已核实的业务事实。",
            "action": "1. **业务负责人 · 本周**：确认决策问题和指标口径。\n2. **数据负责人 · 3 日内**：补齐可验证的数据集。\n3. **风险负责人 · 复核后**：再决定是否执行变更。",
        }
        return generic[agent_id]

    worst = metrics["suppliers"][0]
    largest = max(metrics["suppliers"], key=lambda s: s["spend"])
    flagged = [s for s in metrics["suppliers"] if s["on_time"] < 90 or s["defect"] > 3]
    flag_names = "、".join(s["name"] for s in flagged) or "无"
    spend_line = (
        f"\n- 支出最高：**{largest['name']}**，月采购额 ${largest['spend']:,.0f}，占总额 **{largest['spend'] / metrics['spend'] * 100:.1f}%**。"
        if metrics["spend"] > 0 else
        f"\n- 支出最高：**{largest['name']}**，月采购额 $0；总采购额为零，无法计算支出占比。"
    )
    return {
        "planner": f"将「{run['question']}」拆成四项：交付稳定性、质量损失、支出集中度及可执行的改善计划。以 {metrics['source']} 为量化来源，其余文档仅提供业务背景。",
        "research": (
            f"从 **{metrics['source']}** 读取到 {metrics['count']} 家供应商的记录，月度采购额合计 **${metrics['spend']:,.0f}**。"
            f"\n\n按交付率 < 90% 或缺陷率 > 3% 的演示阈值，需复核：**{flag_names}**。"
            f"\n\n其余资料：{source_list}。"
        ),
        "analyst": (
            f"- 平均准时交付率 **{metrics['on_time']}%**；平均缺陷率 **{metrics['defect']}%**（均为各供应商简单平均，非订单加权）。"
            f"\n- 交付率最低：**{worst['name']}**，{worst['on_time']:g}%，交期 {worst['lead_time']:g} 天。"
            f"{spend_line}"
            f"\n\n来源：{metrics['source']}。"
        ),
        "risk": (
            f"**高优先级**：{worst['name']} 交付率仅 {worst['on_time']:g}%，可能影响供应连续性，需先验证数据时间窗口。"
            f"\n\n**口径限制**：当前 CSV 是单期供应商快照，不含订单数量、价格变动和历史趋势；简单平均不能代表订单层面的实际表现。"
            f"阈值为演示规则，实际决策应由采购及风控团队确认。"
        ),
        "action": (
            f"1. **采购负责人 · 48 小时内**：联系 {worst['name']} 核对逾期原因与未来两周交付承诺；指标：逾期订单数。"
            f"\n2. **质量负责人 · 本周内**：对 {flag_names} 复核缺陷批次；指标：复检缺陷率。"
            f"\n3. **供应链负责人 · 两周内**：评估第二来源与库存缓冲；指标：关键物料覆盖天数。"
            f"\n4. **数据负责人 · 本周内**：补充订单级历史数据以验证上述结论。"
        ),
    }[agent_id]


async def run_workflow(run: dict, documents: list[dict]) -> None:
    from .engine import execute

    await execute(run, documents)
