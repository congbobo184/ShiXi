"""报告生成器 — 8维度经营诊断, 输出到文件"""

from datetime import date, datetime
from pathlib import Path
from typing import List
from shixi.core.schema import DishSale, Finding


def generate(sales: List[DishSale], store_config: dict) -> str:
    from shixi.analysis.segments import diagnose as diag_segments
    from shixi.analysis.weighing import diagnose as diag_weighing
    from shixi.analysis.flavor import diagnose as diag_flavor
    from shixi.analysis.prep import diagnose as diag_prep
    from shixi.analysis.behavior import diagnose as diag_behavior
    from shixi.analysis.efficiency import diagnose as diag_efficiency
    from shixi.analysis.location_value import diagnose as diag_location
    from shixi.analysis.strategy import diagnose as diag_strategy

    if not sales:
        return "暂无数据。"

    dates = [s.营业日期 for s in sales if s.营业日期]
    date_from = min(dates)
    date_to = max(dates)
    total_orders = len(set(s.real_order_id for s in sales))
    active_days = len(set(dates))
    daily_avg = total_orders / active_days if active_days > 0 else 0

    store_name = store_config.get('name', '本店')
    constraints = store_config.get('constraints', [])
    constraint_text = "\n".join(f"  · {c}" for c in constraints) if constraints else "  无特殊约束"

    lines = []
    lines.append("")
    lines.append("══════════════════════════════════════════════════")
    lines.append(f"  石溪 · 经营诊断报告")
    lines.append(f"  {store_name}")
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  数据范围: {date_from} ~ {date_to} ({active_days}天)")
    lines.append(f"  总单量: {total_orders} 单 | 日均: {daily_avg:.0f} 单")
    lines.append("══════════════════════════════════════════════════")
    lines.append("")
    lines.append(f"【店铺约束】")
    lines.append(constraint_text)
    lines.append("")

    all_findings: List[Finding] = []

    # 8个诊断角度
    modules = [
        ("segments", diag_segments, "角度零：客群画像 — 谁在吃你的麻辣烫？谁还没来？"),
        ("weighing", diag_weighing, "角度一：称重结构 — 客人拿得多吗？"),
        ("flavor", diag_flavor, "角度二：口味格局 — 几种口味活得怎么样？"),
        ("prep", diag_prep, "角度三：食材备料 — 哪些赚钱、哪些占位？"),
        ("behavior", diag_behavior, "角度四：客人行为 — 怎么吃、还买了什么？"),
        ("efficiency", diag_efficiency, "角度五：时段效率 — 赚钱还是白烧？"),
        ("location", diag_location, "角度六：位置变现 — 石岛湾你用上了吗？"),
        ("strategy", diag_strategy, "角度七：策略推演 — 爸妈能做的下一件事"),
    ]

    for name, diag_fn, section_title in modules:
        try:
            findings = diag_fn(sales, store_config)
            all_findings.extend(findings)
        except Exception as e:
            lines.append(f"  ⚠️ {name} 诊断出错: {e}")
            continue

        if not findings:
            continue

        lines.append(section_title)
        lines.append("─" * 50)

        for f in findings:
            icon = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(f.level, "·")
            lines.append(f"")
            lines.append(f"  {icon} {f.title}")
            lines.append(f"")
            if f.evidence:
                lines.append(f"     发现: {f.evidence}")
            if f.impact and f.impact != "—":
                lines.append(f"     影响: {f.impact}")
            if f.suggestion:
                lines.append(f"     怎么做: {f.suggestion}")
            if f.expect:
                lines.append(f"     预期: {f.expect}")
        lines.append("")

    # 行动清单
    lines.append("══════════════════════════════════════════════════")
    lines.append("  行动清单")
    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    for level, label in [("red", "🔴 立刻做"), ("yellow", "🟡 这个月做"), ("green", "🟢 持续关注")]:
        items = [f for f in all_findings if f.level == level]
        if not items:
            continue
        lines.append(f"  {label}:")
        for f in items:
            first_line = f.suggestion.split('\n')[0] if f.suggestion else f.title
            lines.append(f"    · {first_line}")
        lines.append("")

    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    return "\n".join(lines)


def save_report(report: str, store_name: str = "shidaowan"):
    """保存报告到文件"""
    today = date.today().strftime("%Y%m%d")
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    filepath = reports_dir / f"{store_name}_{today}.md"
    filepath.write_text(report, encoding='utf-8')
    return filepath
