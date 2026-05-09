"""报告生成器 — 汇总所有Finding，生成可读的经营分析报告"""

from typing import List
from datetime import date
from shixi.core.schema import DishSale, Finding


def generate(sales: List[DishSale], store_config: dict) -> str:
    """生成完整经营分析报告"""
    from shixi.analysis.diagnostic import diagnose
    from shixi.analysis.menu import analyze as menu_analyze
    from shixi.analysis.location import analyze as location_analyze
    from shixi.analysis.forecast import forecast

    if not sales:
        return "暂无数据。请先用 `shixi ingest 文件.xlsx` 导入数据。"

    dates = [s.营业日期 for s in sales if s.营业日期]
    date_from = min(dates) if dates else date.today()
    date_to = max(dates) if dates else date.today()
    total_orders = len(set(s.订单编号 for s in sales))

    # 收集所有分析结果
    all_findings: List[Finding] = []
    all_findings.extend(diagnose(sales))
    all_findings.extend(menu_analyze(sales))
    all_findings.extend(location_analyze(sales, store_config))
    all_findings.extend(forecast(sales, store_config))

    # 生成报告
    store_name = store_config.get('name', '本店')
    lines = []
    lines.append("")
    lines.append("══════════════════════════════════════════════════")
    lines.append(f"  石溪 · 经营分析报告")
    lines.append(f"  {store_name}")
    lines.append(f"  数据: {date_from} ~ {date_to} | {total_orders} 单")
    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    # 按模块分组
    sections = [
        ("一、⏰ 营业节奏诊断", "diagnostic"),
        ("二、🥘 菜品结构诊断", "menu"),
        ("三、📍 商圈与客群洞察", "location"),
        ("四、📈 客流预测", "forecast"),
    ]

    for section_title, module_key in sections:
        module_findings = [f for f in all_findings if f.module == module_key]
        if not module_findings:
            continue

        lines.append(section_title)
        lines.append("─" * 50)

        for f in module_findings:
            icon = {"problem": "⚠️", "strength": "✅",
                    "suggestion": "💡", "prediction": "📈"}.get(f.type, "·")
            priority_bar = {"high": "🔴 高优", "medium": "🟡 中优", "low": "🟢 低优"}.get(f.priority, "")

            lines.append(f"")
            lines.append(f"  {icon} {f.title}")
            if priority_bar:
                lines.append(f"    优先级: {priority_bar}")
            lines.append(f"    {f.detail}")

            if f.recommendation:
                lines.append(f"    → {f.recommendation}")

            if f.data:
                lines.append(f"    数据: {f.data}")

        lines.append("")

    # 行动清单
    lines.append("══════════════════════════════════════════════════")
    lines.append("  行动清单（按优先级排列）")
    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    problems = [f for f in all_findings if f.type == "problem"]
    problems.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.priority, 1))

    suggestions = [f for f in all_findings if f.type in ("suggestion", "prediction")]
    suggestions.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.priority, 1))

    if problems:
        lines.append("  🔴 立即处理：")
        for f in problems:
            if f.recommendation:
                lines.append(f"    - {f.title}: {f.recommendation}")
            else:
                lines.append(f"    - {f.title}")
        lines.append("")

    if suggestions:
        lines.append("  🟡 近期规划：")
        for f in suggestions:
            if f.recommendation:
                lines.append(f"    - {f.recommendation}")
        lines.append("")

    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    return "\n".join(lines)
