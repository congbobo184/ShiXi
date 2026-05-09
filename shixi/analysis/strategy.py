"""角度七：策略推演 — 接下来做什么、老人能操作"""

from collections import defaultdict
from statistics import mean
from typing import List
from datetime import date
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []

    daily = build_daily(sales)
    if not daily:
        return findings

    findings.extend(summer_plan(daily, store_config))
    findings.extend(ticket_lift_simple(sales))
    findings.extend(weak_months_plan(daily))
    findings.extend(one_thing_now(sales, store_config))

    return findings


def build_daily(sales):
    daily = defaultdict(set)
    for s in sales:
        if s.营业日期:
            daily[s.营业日期].add(s.real_order_id)
    return daily


def summer_plan(daily: dict, store_config: dict) -> List[Finding]:
    off_peak = [len(oids) for d, oids in daily.items() if d.month <= 4]
    if not off_peak:
        return []

    base = mean(off_peak)
    store_type = store_config.get('location', {}).get('type', 'coastal_tourist')
    mult = 3.0 if store_type == 'coastal_tourist' else 1.5
    jul_est = round(base * mult)
    aug_est = round(base * mult * 1.17)

    today = date.today()
    weeks = max(1, (date(today.year, 7, 1) - today).days // 7)

    return [Finding(
        level="red",
        title=f"暑期倒计时: 约 {weeks} 周（7月预计日均 {jul_est} 单, 8月 {aug_est} 单）",
        evidence=f"淡季基线日均 {base:.0f} 单，沿海旅游商圈暑期系数 {mult}x",
        impact=f"接不住: 排队超10分钟客人就走了。接住了: 2个月赚淡季半年的钱",
        suggestion=(
            f"爸妈能做的几件事（不复杂）:\n"
            f"  ①6月中: 食材进货量翻{int(mult)}倍（提前跟供应商说好）\n"
            f"  ②7月前: 门口换张大海报，字要大——'威海特色麻辣烫'\n"
            f"  ③7-8月: 营业时间拉长到早10晚11（不用做活动，开门就行）\n"
            f"  ④如果忙不过来: 找个临时工帮忙洗菜切菜（不需要雇长期）"
        ),
        expect=f"接住暑期每多一天=多赚 ¥{base * (mult - 1) * 35:.0f}",
        data={"weeks": weeks, "jul": jul_est, "aug": aug_est, "base": round(base)},
    )]


def ticket_lift_simple(sales: List[DishSale]) -> List[Finding]:
    """客单价提升 — 只做最简单的事"""
    all_oids = set(s.real_order_id for s in sales)
    if not all_oids:
        return []

    order_rev = {}
    for s in sales:
        if s.real_order_id not in order_rev and s.订单收入 > 0:
            order_rev[s.real_order_id] = s.订单收入

    avg_ticket = mean(order_rev.values()) if order_rev else 0

    orders_w_rice = set(s.real_order_id for s in sales
                        if s.菜品大类 == '主食' and '米饭' in s.菜品名称)
    orders_w_drink = set(s.real_order_id for s in sales if s.菜品大类 == '饮料')

    rice_rate = len(orders_w_rice) / len(all_oids) * 100
    drink_rate = len(orders_w_drink) / len(all_oids) * 100

    month_orders = len(all_oids) / 4  # 约4个月数据
    rice_gain = month_orders * (0.7 - rice_rate / 100) * 2
    drink_gain = month_orders * (0.6 - drink_rate / 100) * 4

    return [Finding(
        level="yellow",
        title=f"两件爸妈顺手就能做的事（当前客单价 ¥{avg_ticket:.0f}）",
        evidence=(
            f"米饭搭售 {rice_rate:.0f}% → 问'加碗米饭？'到70%=月多赚 ¥{rice_gain:.0f}\n"
            f"饮料搭售 {drink_rate:.0f}% → 问'冰镇饮料要吗？'到60%=月多赚 ¥{drink_gain:.0f}"
        ),
        impact="这两件事不用做活动、不用设计、不用成本——就是收钱时多问一句话",
        suggestion=(
            "收银口诀（爸妈背下来就行）:\n"
            "  客人称完重 → '加碗米饭？'\n"
            "  客人付钱时 → '冰镇饮料来一个？'\n"
            "  就这么简单，多问这两句话一个月多赚一两千"
        ),
        expect=f"客单价 ¥{avg_ticket:.0f} → ¥{avg_ticket + 5:.0f}，一个月见效",
    )]


def weak_months_plan(daily: dict) -> List[Finding]:
    """弱月简单应对"""
    by_month = defaultdict(lambda: {"orders": set(), "days": set()})
    for d, oids in daily.items():
        by_month[d.month]["orders"].update(oids)
        by_month[d.month]["days"].add(d)

    daily_avg = {}
    for m, v in by_month.items():
        daily_avg[m] = len(v["orders"]) / len(v["days"]) if v["days"] else 0

    months = sorted(daily_avg)
    if len(months) < 2:
        return []

    overall = mean(daily_avg.values())
    weak = [(m, daily_avg[m]) for m in months if daily_avg[m] < overall * 0.8]
    if not weak:
        return []

    return [Finding(
        level="yellow",
        title=f"弱月: {', '.join(f'{m}月(日均{v:.0f}单)' for m, v in weak)}",
        evidence=f"整体日均 {overall:.0f} 单",
        impact="弱月白付房租人工，不如少开门",
        suggestion="弱月缩短营业时间（比如只开午高峰+晚高峰），或安排休假回老家。不用硬扛",
        expect="减少无效营业天数，省人工水电",
    )]


def one_thing_now(sales: List[DishSale], store_config: dict) -> List[Finding]:
    """当前最该做的一件事"""
    segments = store_config.get('customer_segments', [])

    # 找增速最快的口味
    by_month = defaultdict(lambda: defaultdict(float))
    month_days = defaultdict(set)
    for s in sales:
        if s.菜品大类 == '称重菜' and s.营业日期:
            by_month[s.营业日期.month][s.菜品名称] += s.菜品收入
            month_days[s.营业日期.month].add(s.营业日期)

    months = sorted(by_month)
    if len(months) < 2:
        return []

    fm, lm = months[0], months[-1]
    fd, ld = len(month_days[fm]), len(month_days[lm])
    growing = []
    for name in set().union(*[by_month[m].keys() for m in months]):
        f = by_month[fm].get(name, 0) / fd if fd > 0 else 0
        l = by_month[lm].get(name, 0) / ld if ld > 0 else 0
        if f > 0 and (l - f) / f > 0.1:
            growing.append((name, (l - f) / f))

    growing.sort(key=lambda x: x[1], reverse=True)

    return [Finding(
        level="red",
        title="本周爸妈最该做的一件事",
        evidence=(
            f"增长最快的口味: {', '.join(f'{n}(+{g:.0%})' for n, g in growing[:3]) if growing else '暂无明确增长口味'}\n"
            f"客群机会: {', '.join(s['name'] for s in segments[:3]) if segments else '周边居民+游客'}"
        ),
        impact="不做太多事，聚焦一件。做对了=花最少力气拿最大回报",
        suggestion=(
            "挑一件最简单的做:\n"
            f"  ①如果麻辣拌在涨 → 门口海报换'小谷姐姐招牌麻辣拌'（品牌本来就叫这个）\n"
            f"  ②如果核电站工人来得多 → 备料多备荤菜（工人要吃饱）\n"
            f"  ③暑期马上到 → 门口换张大海报（爸妈唯一要做的事）"
        ),
        expect="一件事做对了，比做十件半途而废的事强",
    )]
