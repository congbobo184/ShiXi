"""CLI 命令行入口"""

import sys
import argparse
import yaml
from pathlib import Path
from shixi.ingest.meituan_dish import parse
from shixi.core.store import save, load, get_date_range
from shixi.report import generate


def load_store_config(config_dir: Path, store_name: str = "shidaowan") -> dict:
    """加载店铺配置"""
    config_path = config_dir / "stores" / f"{store_name}.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"name": "小谷姐姐麻辣烫·石岛湾店", "location": {"type": "coastal_tourist"}}


def cmd_ingest(args):
    """导入数据"""
    filepath = args.file
    print(f"正在解析: {filepath}")
    sales = parse(filepath)
    source = Path(filepath).name
    save(sales, source)
    dates = [s.营业日期 for s in sales if s.营业日期]
    print(f"✅ 导入完成: {len(sales)} 条菜品记录, "
          f"{len(set(s.订单编号 for s in sales))} 单")
    if dates:
        print(f"   日期范围: {min(dates)} ~ {max(dates)}")


def cmd_report(args):
    """生成经营分析报告"""
    config_dir = Path(__file__).parent / "config"
    config = load_store_config(config_dir, args.store)

    date_from, date_to = get_date_range()
    sales = load()
    if not sales:
        print("暂无数据。请先导入: shixi ingest 文件.xlsx")
        return

    # 可选的时间过滤
    if args.months:
        sales = [s for s in sales if s.营业日期 and s.营业日期.month in args.months]

    report = generate(sales, config)
    print(report)


def cmd_info(args):
    """查看数据概况"""
    sales = load()
    if not sales:
        print("暂无数据。")
        return

    dates = [s.营业日期 for s in sales if s.营业日期]
    orders = set(s.订单编号 for s in sales)
    dishes = set(s.菜品名称 for s in sales)

    print(f"数据概况:")
    print(f"  菜品记录: {len(sales)} 条")
    print(f"  订单数: {len(orders)} 单")
    print(f"  菜品种类: {len(dishes)} 个")
    if dates:
        print(f"  日期范围: {min(dates)} ~ {max(dates)} ({len(set(dates))} 天)")


def main():
    parser = argparse.ArgumentParser(
        prog='shixi',
        description='石溪 — 餐饮经营智能分析系统'
    )
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # ingest
    p_ingest = subparsers.add_parser('ingest', help='导入美团菜品销售明细')
    p_ingest.add_argument('file', help='Excel文件路径')

    # report
    p_report = subparsers.add_parser('report', help='生成经营分析报告')
    p_report.add_argument('--store', default='shidaowan', help='店铺配置名')
    p_report.add_argument('--months', type=int, nargs='+', help='限定月份，如 1 2 3')

    # info
    subparsers.add_parser('info', help='查看数据概况')

    args = parser.parse_args()

    if args.command == 'ingest':
        cmd_ingest(args)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'info':
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
