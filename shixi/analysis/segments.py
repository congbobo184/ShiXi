"""角度八：客群画像 — 六个客群谁来了、谁没来、怎么接"""

from collections import defaultdict
from statistics import mean
from typing import List
from shixi.core.schema import DishSale, Finding


def diagnose(sales: List[DishSale], store_config: dict) -> List[Finding]:
    findings = []
    segments = store_config.get('customer_segments', [])
    if not segments:
        return findings

    # 从数据推断各客群的存在感和服务机会
    findings.extend(general_patterns(sales))
    findings.extend(segment_opportunities(sales, segments))
    return findings


def general_patterns(sales: List[DishSale]) -> List[Finding]:
    """从数据推断客群行为模式"""
    findings = []

    # 工作时间段分析（间接推断工人/渔民）
    hour_orders = defaultdict(int)
    for s in sales:
        if s.点菜时间:
            hour_orders[s.点菜时间.hour] += 1

    # 非标准时段（10点前、14-16点、21点后）→ 可能是工人/倒班人员
    odd_hours = {h: hour_orders.get(h, 0) for h in [8, 9, 10, 14, 15, 16, 21, 22]}
    odd_total = sum(odd_hours.values())
    all_total = sum(hour_orders.values())

    if all_total > 0:
        findings.append(Finding(
            level="green",
            title=f"非饭点时段(10点前/14-16点/21点后)占 {odd_total / all_total * 100:.1f}% 客流",
            evidence=" → ".join(f"{h}h:{odd_hours[h]}单" for h in sorted(odd_hours) if odd_hours[h] > 0),
            impact="非标准时段客流说明有倒班工人、渔民等非白领客群",
            suggestion="这些时段保持备料，别让这些客人扑空——他们可能是你最忠实的回头客",
        ))

    # 客单价分层（间接推断消费力）
    order_rev = {}
    for s in sales:
        if s.real_order_id not in order_rev and s.订单收入 > 0:
            order_rev[s.real_order_id] = s.订单收入

    if order_rev:
        revs = sorted(order_rev.values())
        low = revs[int(len(revs) * 0.1)] if len(revs) > 10 else revs[0]
        high = revs[int(len(revs) * 0.9)] if len(revs) > 10 else revs[-1]

        findings.append(Finding(
            level="green",
            title=f"客单价跨度 ¥{low:.0f} - ¥{high:.0f}，消费力分层明显",
            evidence=f"低消费力(¥{low:.0f}以下)=学生/留守家属; 高消费力(¥{high:.0f}以上)=工人/双人/家庭",
            impact="不同客群诉求不同，一个菜单要服务所有人",
            suggestion="基础麻辣烫服务所有人，加料/套餐服务高消费力客群，两不耽误",
        ))

    # 工作日午高峰 vs 周末 → 工人/学生的影响
    by_date = defaultdict(lambda: {"orders": set(), "weekday": None})
    for s in sales:
        if s.营业日期:
            by_date[s.营业日期]["orders"].add(s.real_order_id)
            by_date[s.营业日期]["weekday"] = s.营业日期.weekday()

    weekday_counts = [len(v["orders"]) for d, v in by_date.items() if v["weekday"] is not None and v["weekday"] < 5]
    if weekday_counts:
        stable = max(weekday_counts) / (min(weekday_counts) if min(weekday_counts) > 0 else 1)
        if stable < 1.5:
            findings.append(Finding(
                level="green",
                title="工作日单量非常稳定（波动<50%）",
                evidence=f"工作日日均 {mean(weekday_counts):.0f} 单，说明有稳定的日常客群支撑",
                impact="稳定基本盘=核电站工人+周边居民+渔民。这群人不会突然消失",
                suggestion="稳定客群不要'惊喜'，要'不出错'。口味稳定、出餐快、价格透明",
            ))

    return findings


def segment_opportunities(sales: List[DishSale], segments: List[dict]) -> List[Finding]:
    """逐个客群分析机会"""
    findings = []
    constraints = ["无外卖", "不做复杂活动", "无会员系统"]

    for seg in segments:
        name = seg['name']
        desc = seg.get('description', '')
        status = seg.get('current_status', '未知')

        if status == '当前主要客群':
            findings.append(Finding(
                level="green",
                title=f"「{name}」— 当前主力客群, 要守住",
                evidence=desc.strip().split('\n')[0],
                impact="这是淡季保命的基本盘，流失不起",
                suggestion="口味稳定+价格透明+出餐快。不需要花活，需要靠谱",
            ))
        elif status == '未专门服务':
            # 不同客群不同建议
            if '工人' in name:
                findings.append(Finding(
                    level="yellow",
                    title=f"「{name}」— 高消费力、非饭点来，现成的好客人",
                    evidence=desc.strip().split('\n')[0],
                    impact="工人三班倒，不只在饭点吃。你开门他们就来，你关门他们就只能去别家",
                    suggestion="①营业时间覆盖工人下班时段（尤其夜班下班）②荤菜备足（工人要扛饿）③不复杂，就是'量大管饱'",
                ))
            elif '学生' in name:
                findings.append(Finding(
                    level="yellow",
                    title=f"「{name}」— 自带传播力, 但价格要亲民",
                    evidence=desc.strip().split('\n')[0],
                    impact="学生会发朋友圈/短视频帮你宣传——免费广告",
                    suggestion="①推'学生价'单人餐(麻辣烫+米饭 ¥25封顶?)②不复杂——门口贴个'学生优惠'就行③学生爱结伴，桌子要大一点或能拼桌",
                ))
            elif '渔民' in name:
                findings.append(Finding(
                    level="yellow",
                    title=f"「{name}」— 中午回港, 要快要饱",
                    evidence=desc.strip().split('\n')[0],
                    impact="渔民11-14点密集吃饭，跟午高峰重叠。他们吃完就走翻台快",
                    suggestion="①午高峰食材多备1/3（渔民+上班族叠加）②海鲜偏好→你的海鲜味麻辣烫可以主打'本地味'③出餐要快，渔船不等人",
                ))
            elif '留守' in name or '妇女' in name:
                findings.append(Finding(
                    level="green",
                    title=f"「{name}」— 下午有时段, 可能带孩子",
                    evidence=desc.strip().split('\n')[0],
                    impact="留守家属有空闲时间，下午可能带孩子来吃。社交传播力强",
                    suggestion="①下午如果开门，备点不辣的口味（孩子能吃）②友好环境：有高脚椅更好，没有也不强求③她们之间会互相推荐——做好一个就带动一群",
                ))
            elif '游客' in name:
                findings.append(Finding(
                    level="yellow",
                    title=f"「{name}」— 暑期爆发红利, 现在就要准备",
                    evidence=desc.strip().split('\n')[0],
                    impact="游客是一次性消费，但量巨大。接不住就白白送给别人",
                    suggestion="①门口招牌要大要醒目(游客走路看手机,抬头一瞬间决定进不进)②大众点评/高德地图更新照片③暑期加'威海特色'标签",
                ))

    return findings
