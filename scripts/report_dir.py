#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报目录定位脚本 — 解析当天或指定日期对应的报告月目录。

目录规范与 daily-merge/scripts/shared.py 的 find_report_dir 保持一致：
    报告-{年}年/日报-{年}-{月}月
优先匹配带前导零的「08月」，回退匹配历史遗留的「8月」，都不存在则创建「08月」规范目录。

用法：
    python report_dir.py                # 今天
    python report_dir.py 2026-08-03     # 指定日期（补历史日报用，YYYY-MM-DD）

输出：报告月目录的绝对路径（打印到 stdout），创建动作提示走 stderr 不污染路径。
"""
import os
import sys
from datetime import date, datetime

DESKTOP = r"F:\idea-workspase-skills\daily-report-panel"  # 日报根目录（2026-09-04 迁移自桌面，变量名沿用免改引用）


def resolve_report_dir(day):
    """返回 day 对应的报告月目录；规范目录不存在时创建「08月」格式。

    Args:
        day: datetime.date 对象

    Returns:
        报告月目录的绝对路径
    """
    year = f"{day.year:04d}"
    month = f"{day.month:02d}"          # 两位补零，如 08
    month_no_zero = str(day.month)      # 历史遗留格式，如 8

    parent = os.path.join(DESKTOP, f"报告-{year}年")
    path_mm = os.path.join(parent, f"日报-{year}-{month}月")
    path_m = os.path.join(parent, f"日报-{year}-{month_no_zero}月")

    # 优先匹配规范格式（08月），回退历史格式（8月）
    if os.path.isdir(path_mm):
        return path_mm
    if os.path.isdir(path_m):
        return path_m
    # 都不存在 → 创建规范格式目录
    os.makedirs(path_mm, exist_ok=True)
    print(f"[提示] 目录不存在，已创建规范目录：{path_mm}", file=sys.stderr)
    return path_mm


def main():
    # Windows 控制台多为 GBK，中文路径打印统一走 utf-8，防止 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure，交给系统默认编码

    if len(sys.argv) > 1:
        try:
            day = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"非法日期参数：{sys.argv[1]}，需为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
    else:
        day = date.today()

    print(resolve_report_dir(day))


if __name__ == "__main__":
    main()
