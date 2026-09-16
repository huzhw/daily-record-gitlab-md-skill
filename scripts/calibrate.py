#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报自我校准脚本 — 机械比对审计注释块公式字段与表格行实值，输出偏差与 K 样本。

背景：
    SKILL「自我校准」要求每次触发回看「审计块公式 vs 行内实值」，此前靠 AI 肉眼比对，
    而 2026-09-10 已实证 AI 裁量会漂（2.75h）。本脚本把比对机械化（与判重脚本同一哲学）：
    - 偏差信号：审计块「人工公式 / AI=…」的数字 vs 表格行「人工工时 / AI辅助工时」列实值，
      不一致即偏差（deviations），同卡同子项 ≥3 次同向偏差才够格提案调价
    - K 样本：带「档=」的开发类审计块 + 行内「实测用时」列 → 人工 ÷ 实测 比值分布，
      按档汇总（by_tier），为 K 档校准提供实证底数（样本不足不动 K）

兼容审计块版本（字段结构照认，解析不了的进 unparseable、不静默跳过）：
    审计格式 v1（现行）、审计 v1.8：人工公式=<X>h · AI=人工÷K(<K>)=<X.X>h / AI=实测<X.X>h
    v1.6/v1.7：人工公式=<X>h · AI实测=<X.X>h；运维类 人工=实测<X>h · AI=实测<X.X>h
    v1.5 及以前：人工公式=<X>h · AI公式=<X.X>h
    识别规则：HTML 注释内含「seq=」+「仓库=」即视为审计块（不依赖版本标记）。

用法：
    python calibrate.py                          # 今天：偏差比对
    python calibrate.py 2026-09-16               # 指定日期：偏差比对
    python calibrate.py --k-samples 2026-09-01 2026-09-30   # K 样本：日期区间（缺省当月1日~今天）
    python calibrate.py --md <md路径>            # 测试用：指定 md 文件

输出（JSON，stdout；提取字段用 jq，禁止 python -c 二次处理）：
    偏差比对：mode/date/documents/checked/deviations/blocks_unparseable/
              blocks_unmatched/rows_without_block/ok
    K 样本  ：mode/from/to/samples_n/samples/by_tier {档:{k_book,n,min,median,max}}

退出码：0 正常（有偏差也是 0——偏差是数据不是错误）；2 参数错误 / md 不存在。
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
from datetime import date, datetime, timedelta

# 复用 report_dir 的月目录定位逻辑（单一事实源，不重复实现 08月/8月 兼容）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_dir import resolve_report_dir  # noqa: E402

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_TABLE_HEADER = re.compile(r"^\|\s*序号\s*\|")
RE_H = re.compile(r"([\d.]+)\s*h")            # 「18.5h」「4h」→ 18.5 / 4（审计块字段口径）
RE_NUM = re.compile(r"^\s*([\d.]+)\s*h?\s*$")  # 表格行单元格：纯数字或数字+h（「10」「1.5」「18.5h」）
RE_AI_K = re.compile(r"人工÷K\(([\d.]+)\)=([\d.]+)\s*h")   # AI=人工÷K(2.5)=9.0h
RE_SHICE = re.compile(r"实测\s*([\d.]+)\s*h")  # 「人工=实测4.5h」「AI=实测4.5h」
RE_ACTUAL_COL = re.compile(r"约\s*([\d.]+)\s*h")            # 实测用时列「约 2h」
RE_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
TIER_CHARS = "①②③④⑤⑥"


def parse_hours(text):
    """从「18.5」「18.5h」「10」里取小时数；取不到返回 None。

    先按整格纯数字（可带 h）解析——表格行单元格口径（人工/AI 列是裸数字，单位在表头）；
    再按「数字+h」搜索兜底——审计块字段口径（人工公式=10h）。
    """
    if text is None:
        return None
    text = str(text)
    m = RE_NUM.match(text)
    if m:
        return float(m.group(1))
    m = RE_H.search(text)
    return float(m.group(1)) if m else None


def parse_rows(md_path):
    """解析表格数据行：[{seq, repo, human, ai, actual, cells}]；列位与日报管家前 9 列口径一致。"""
    if not os.path.isfile(md_path):
        return []
    with open(md_path, "r", encoding="utf-8-sig") as f:
        lines = f.read().split("\n")

    rows, in_table = [], False
    for raw in lines:
        line = raw.strip()
        if RE_TABLE_HEADER.match(line):
            in_table = True
            continue
        if not in_table:
            continue
        if not set(line) - set("|-: \t"):
            continue
        if not line.startswith("|"):
            if not line:
                continue
            break  # 表格结束（图例段 / 审计注释区不进行集合）
        if "空行为模板" in line:
            break
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 9:
            continue
        seq, repo = cells[0], cells[2]
        if not repo and not cells[3] and not any(cells[4:]):
            continue  # 模板空行
        rows.append({
            "seq": seq, "repo": repo,
            "human": parse_hours(cells[6]), "human_raw": cells[6],
            "ai": parse_hours(cells[7]), "ai_raw": cells[7],
            "actual": (RE_ACTUAL_COL.search(cells[10]).group(1)
                       if len(cells) > 10 and RE_ACTUAL_COL.search(cells[10]) else None),
            "actual_raw": cells[10] if len(cells) > 10 else "",
        })
    return rows


def parse_blocks(md_path):
    """解析审计注释块：[{seq, repo, fields, raw}]；识别规则=注释内含 seq= 且 仓库=。"""
    if not os.path.isfile(md_path):
        return []
    with open(md_path, "r", encoding="utf-8-sig") as f:
        text = f.read()

    blocks = []
    for m in RE_COMMENT.finditer(text):
        inner = m.group(1).strip()
        if "seq=" not in inner or "仓库=" not in inner:
            continue  # 非审计注释（模板引言等），静默忽略
        fields = {}
        for part in inner.split("·"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k.strip()] = v.strip()
        blocks.append({
            "seq": fields.get("seq", ""),
            "repo": fields.get("仓库", ""),
            "fields": fields,
            "raw": inner,
        })
    return blocks


def block_hours(block):
    """从审计块字段取 (人工h 或 None, AIh 或 None, k 或 None)；多代字段名兼容。"""
    f = block["fields"]

    human = None
    if "人工公式" in f:
        human = parse_hours(f["人工公式"])
    elif "人工" in f:                      # 运维类：人工=实测<X>h
        m = RE_SHICE.search(f["人工"])
        human = float(m.group(1)) if m else parse_hours(f["人工"])

    ai, k = None, None
    if "AI" in f:                          # 现行：AI=人工÷K(<K>)=<X>h 或 AI=实测<X>h
        m = RE_AI_K.search(f["AI"])
        if m:
            k = float(m.group(1))
            ai = float(m.group(2))
        else:
            m2 = RE_SHICE.search(f["AI"])
            ai = float(m2.group(1)) if m2 else parse_hours(f["AI"])
    elif "AI实测" in f:                    # v1.6/v1.7
        ai = parse_hours(f["AI实测"])
    elif "AI公式" in f:                    # v1.5 及以前
        ai = parse_hours(f["AI公式"])

    if k is None and "K" in f:
        try:
            k = float(f["K"])
        except ValueError:
            pass
    return human, ai, k


def collect_documents(day, md_override=None):
    """返回当天可校验的文档列表 [{name, rows, blocks}]：md 存在用 md；否则用已合并分片。"""
    if md_override:
        return [{"name": md_override, "rows": parse_rows(md_override),
                 "blocks": parse_blocks(md_override)}]
    md_path = os.path.join(resolve_report_dir(day), f"日报需求记录-{day.strftime('%Y-%m-%d')}.md")
    docs = []
    if os.path.isfile(md_path):
        docs.append({"name": md_path, "rows": parse_rows(md_path), "blocks": parse_blocks(md_path)})
        return docs
    merged_dir = os.path.join(os.path.dirname(md_path), "已合并")
    for shard in sorted(glob.glob(os.path.join(merged_dir, day.strftime("%Y-%m-%d") + "-*.md"))):
        docs.append({"name": shard, "rows": parse_rows(shard), "blocks": parse_blocks(shard)})
    return docs


def check_deviations(day, md_override):
    """偏差比对：审计块公式数字 vs 行内实值。"""
    docs = collect_documents(day, md_override)
    if not docs:
        print(json.dumps({
            "mode": "check", "date": day.strftime("%Y-%m-%d"), "documents": [],
            "error": "当天 md 与已合并分片都不存在", "ok": None,
        }, ensure_ascii=False, indent=2))
        return

    deviations, unparseable, unmatched, no_block, checked = [], [], [], [], 0
    for doc in docs:
        src = os.path.basename(doc["name"])
        row_map = {(r["seq"], r["repo"]): r for r in doc["rows"]}
        matched_keys = set()
        for b in doc["blocks"]:
            key = (b["seq"], b["repo"])
            row = row_map.get(key)
            if row is None:
                unmatched.append({"source": src, "seq": b["seq"], "repo": b["repo"],
                                  "reason": "审计块找不到对应表格行（行被删或 seq/仓库 不一致）"})
                continue
            matched_keys.add(key)
            human, ai, _k = block_hours(b)
            if human is None and ai is None:
                unparseable.append({"source": src, "seq": b["seq"], "repo": b["repo"],
                                    "reason": "块内取不到人工/AI 数字"})
                continue
            if human is not None:
                checked += 1
                if row["human"] is None or abs(human - row["human"]) >= 0.05:
                    deviations.append({"source": src, "seq": b["seq"], "repo": b["repo"],
                                       "field": "人工", "audit": human, "row": row["human_raw"]})
            if ai is not None:
                checked += 1
                if row["ai"] is None or abs(ai - row["ai"]) >= 0.05:
                    deviations.append({"source": src, "seq": b["seq"], "repo": b["repo"],
                                       "field": "AI", "audit": ai, "row": row["ai_raw"]})
        for r in doc["rows"]:
            if (r["seq"], r["repo"]) not in matched_keys:
                no_block.append({"source": src, "seq": r["seq"], "repo": r["repo"],
                                 "reason": "表格行没有审计块（历史行或漏写）"})

    print(json.dumps({
        "mode": "check",
        "date": day.strftime("%Y-%m-%d"),
        "documents": [os.path.basename(d["name"]) for d in docs],
        "checked": checked,
        "deviations": deviations,
        "blocks_unparseable": unparseable,
        "blocks_unmatched": unmatched,
        "rows_without_block": no_block,
        "ok": len(deviations) == 0,
    }, ensure_ascii=False, indent=2))


def k_samples(day_from, day_to, md_override):
    """K 样本：带「档=」的开发类块 × 行内「实测用时」→ 人工/实测 比值按档分布。"""
    samples = []
    day = day_from
    while day <= day_to:
        for doc in collect_documents(day, md_override if day == day_from else None):
            src = os.path.basename(doc["name"])
            row_map = {(r["seq"], r["repo"]): r for r in doc["rows"]}
            for b in doc["blocks"]:
                tier = (b["fields"].get("档") or "").strip()[:1]
                if tier not in TIER_CHARS:
                    continue  # 文档/运维类块无档位，天然排除
                _h, _ai, k = block_hours(b)
                row = row_map.get((b["seq"], b["repo"]))
                if k is None or row is None or row["actual"] is None or not row["human"]:
                    continue
                actual = float(row["actual"])
                if actual <= 0:
                    continue
                samples.append({
                    "date": day.strftime("%Y-%m-%d"), "source": src,
                    "seq": b["seq"], "repo": b["repo"], "tier": tier, "k_book": k,
                    "human": row["human"], "actual": actual,
                    "ratio": round(row["human"] / actual, 3),
                })
        day += timedelta(days=1)

    by_tier = {}
    for s in samples:
        t = by_tier.setdefault(s["tier"], {"k_book": s["k_book"], "n": 0, "ratios": []})
        t["n"] += 1
        t["ratios"].append(s["ratio"])
    for t in by_tier.values():
        rs = t.pop("ratios")
        t["ratio_min"] = min(rs)
        t["ratio_median"] = statistics.median(rs)
        t["ratio_max"] = max(rs)

    print(json.dumps({
        "mode": "k_samples",
        "from": day_from.strftime("%Y-%m-%d"),
        "to": day_to.strftime("%Y-%m-%d"),
        "samples_n": len(samples),
        "samples": samples,
        "by_tier": by_tier,
    }, ensure_ascii=False, indent=2))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure

    ap = argparse.ArgumentParser(description="日报自我校准：审计块 vs 行值机械比对 + K 样本分布")
    ap.add_argument("tokens", nargs="*", help="[日期]（偏差比对）或 [起] [止]（--k-samples 区间）")
    ap.add_argument("--k-samples", action="store_true",
                    help="K 样本模式：输出每档「人工÷实测」分布（缺省区间=当月1日~今天）")
    ap.add_argument("--md", help="指定 md 文件路径（测试用；缺省按日期定位报告目录）")
    args = ap.parse_args()

    dates = []
    for tok in args.tokens:
        if not RE_DATE.match(tok):
            print(f"非法日期：{tok}，需为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
        dates.append(datetime.strptime(tok, "%Y-%m-%d").date())

    if args.k_samples:
        day_from = dates[0] if dates else date.today().replace(day=1)
        day_to = dates[1] if len(dates) > 1 else (dates[0] if dates else date.today())
        if day_from > day_to:
            day_from, day_to = day_to, day_from
        k_samples(day_from, day_to, args.md)
    else:
        if len(dates) > 1:
            print("偏差比对只接受一个日期；区间请用 --k-samples", file=sys.stderr)
            sys.exit(2)
        check_deviations(dates[0] if dates else date.today(), args.md)


if __name__ == "__main__":
    main()
