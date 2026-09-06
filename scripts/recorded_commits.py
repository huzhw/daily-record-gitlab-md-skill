#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报增量去重脚本 — 解析当天 md 已记录的（仓库 + 提交id），与传入的 commit 短 id 机械比对。

背景：
    同一天多次「补充日报」时，必须只记录还没写进 md 的 commit。
    以前靠 AI 肉眼比对溯源括号，容易重复/漏记；本脚本把判断机械化：
    事实源就是 md 表格末列「提交id」（日报管家解析只取前 9 列，此列不进库、不影响管家）。

用法：
    python recorded_commits.py                                  # 今天：仅输出已记录清单
    python recorded_commits.py 档案V6 b875e2c0 12adb983         # 今天：按「仓库+id」判差集
    python recorded_commits.py 2026-09-06 档案V6 b875e2c0       # 指定日期
    python recorded_commits.py --md <md路径> ...                # 测试用：指定 md 文件

参数 token 分类（与顺序无关，按形状识别）：
    YYYY-MM-DD          → 日期（缺省今天）
    ^[0-9a-fA-F]{6,40}$ → commit 短 id（可多个）
    其他                → 仓库名（= md 仓库列的值，中文名或原名；最多一个）

🔴 防漏硬闸门：传了 commit 短 id 就必须传仓库名，否则 exit 2 拒绝执行——
   没有仓库限定的比对在跨仓库 id 撞车时会误判"已记录"造成漏需求；
   宁可不判重（顶多重复一行），不在信息不全时判重（可能丢需求）。

去重键是「仓库 + 提交id」二元组：同仓库内 git 短 id 唯一；跨仓库即使短 id 撞车，
仓库不同也不会误判。长短 id 前缀互匹配（≥4 位）。

输出（JSON，stdout；提取字段用 jq，禁止 python -c 二次处理）：
    date / md / md_exists
    recorded           [{seq, repo, ids}]     已记录清单（按行分组）
    non_commit_rows    [{seq, repo}]          提交id 列填「无」的行（正常，如纯数据运维）
    rows_without_ids   [{seq, repo, reason}]  拿不到 id 的行（历史9列 / 列为空 / 解析失败）
                                              → 去重对此类行失效，需人工核对后再记录
    repo_not_found_in_md  bool                传入仓库名与 md 任何行都不匹配（防传错名导致全判未记录）
    given / unrecorded / all_recorded
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime

# 复用 report_dir 的月目录定位逻辑（单一事实源，不重复实现 08月/8月 兼容）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_dir import resolve_report_dir  # noqa: E402

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_ID = re.compile(r"^[0-9a-fA-F]{6,40}$")  # 真实 %h ≥7 位；6 位兼容 SKILL.md 示例格式
RE_ID_TOKEN = re.compile(r"^([0-9a-fA-F]{6,40})(?:\(([^)]*)\))?$")  # 1a2b3c(master) → 1a2b3c
NO_COMMIT_WORDS = {"无", "-", "—", "/"}


def id_match(given, recorded):
    """长短 id 前缀互匹配：git 同仓库短 id 唯一，长度可能 7~10 位不等。"""
    g, r = given.lower(), recorded.lower()
    if len(g) < 4 or len(r) < 4:
        return g == r
    return g.startswith(r) or r.startswith(g)


def parse_md_table(md_path):
    """解析日报 md 表格，返回 (rows, md_exists)。

    rows: [{seq, repo, ids, reason}]  reason=None 正常；否则是拿不到 id 的原因；
          ids=[] 且 reason='无commit' 表示提交id 列填「无」的正常行。
    """
    if not os.path.isfile(md_path):
        return [], False
    with open(md_path, "r", encoding="utf-8-sig") as f:
        lines = f.read().split("\n")

    rows = []
    in_table = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("| 序号"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|--") or line.startswith("| ---"):
            continue
        if not line.startswith("|"):
            if not line:
                continue  # 表格与尾部引言之间的空行
            break  # 表格结束（> 引言等）
        if "空行为模板" in line:
            break

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 9:
            continue  # 碎行/残行不参与
        seq, _d, repo, desc = cells[0], cells[1], cells[2], cells[3]
        # 模板空行（除序号外全空）跳过
        if not repo and not desc and not any(cells[4:]):
            continue

        if len(cells) < 10:
            rows.append({"seq": seq, "repo": repo, "ids": [], "reason": "历史9列，无提交id列"})
            continue

        id_cell = cells[9]
        if not id_cell:
            rows.append({"seq": seq, "repo": repo, "ids": [], "reason": "提交id列为空（疑似忘填）"})
            continue
        if id_cell in NO_COMMIT_WORDS:
            rows.append({"seq": seq, "repo": repo, "ids": [], "reason": "无commit"})
            continue

        ids, bad = [], []
        for token in id_cell.split("/"):
            token = token.strip()
            m = RE_ID_TOKEN.match(token)
            if m:
                ids.append(m.group(1).lower())
            elif token:
                bad.append(token)
        if bad:
            rows.append({"seq": seq, "repo": repo, "ids": ids,
                         "reason": "提交id列含无法解析的标记: " + ",".join(bad)})
        else:
            rows.append({"seq": seq, "repo": repo, "ids": ids, "reason": None})
    return rows, True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure

    ap = argparse.ArgumentParser(description="日报增量去重：md 已记录（仓库+提交id）与传入短 id 机械比对")
    ap.add_argument("tokens", nargs="*", help="[日期] [仓库名] <短id>...")
    ap.add_argument("--md", help="指定 md 文件路径（测试用；缺省按日期定位报告目录）")
    args = ap.parse_args()

    day, repo, given_ids = date.today(), None, []
    for tok in args.tokens:
        if RE_DATE.match(tok):
            try:
                day = datetime.strptime(tok, "%Y-%m-%d").date()
            except ValueError:
                print(f"非法日期：{tok}", file=sys.stderr)
                sys.exit(2)
        elif RE_ID.match(tok):
            if tok.lower() not in given_ids:
                given_ids.append(tok.lower())
        elif repo is None:
            repo = tok
        else:
            print(f"仓库名只能传一个，多出 token：{tok}", file=sys.stderr)
            sys.exit(2)

    # 防漏硬闸门：判重必须有仓库限定，宁可不判（重复可删）不可错判（需求丢失）
    if given_ids and repo is None:
        print("传了 commit 短 id 但没传仓库名，拒绝判重：跨仓库 id 撞车时会误判已记录造成漏需求。"
              "用法：recorded_commits.py [日期] <仓库名> <短id>...", file=sys.stderr)
        sys.exit(2)

    md_path = args.md or os.path.join(
        resolve_report_dir(day), f"日报需求记录-{day.strftime('%Y-%m-%d')}.md"
    )
    rows, md_exists = parse_md_table(md_path)

    # 日报管家的生命周期：抓取后把当天 md 移入 已合并\YYYY-MM-DD-NN.md 分片。
    # 当天 md 已不存在时，把当天分片也解析进来——「合并后同天再补记」同样能去重。
    merged_shards = []
    if not md_exists and args.md is None:
        merged_dir = os.path.join(os.path.dirname(md_path), "已合并")
        prefix = day.strftime("%Y-%m-%d") + "-"
        pattern = os.path.join(merged_dir, prefix + "*.md")
        for shard in sorted(glob.glob(pattern)):
            shard_rows, ok = parse_md_table(shard)
            if ok:
                merged_shards.append(os.path.basename(shard))
                rows.extend(shard_rows)

    recorded, non_commit, without_ids = [], [], []
    for r in rows:
        if r["reason"] == "无commit":
            non_commit.append({"seq": r["seq"], "repo": r["repo"]})
        elif r["reason"] is not None:
            without_ids.append({"seq": r["seq"], "repo": r["repo"], "reason": r["reason"]})
        elif r["ids"]:
            recorded.append({"seq": r["seq"], "repo": r["repo"], "ids": r["ids"]})

    # 已合并分片是同一天 md 的递增快照，同一行会出现多次：按 (seq, repo) 去重
    def dedup(items, keys):
        seen, out = set(), []
        for it in items:
            k = tuple(it[x] for x in keys)
            if k not in seen:
                seen.add(k)
                out.append(it)
        return out

    recorded = dedup(recorded, ("seq", "repo"))
    non_commit = dedup(non_commit, ("seq", "repo"))
    without_ids = dedup(without_ids, ("seq", "repo", "reason"))

    # 比对范围：传了仓库名 → 只比该仓库的行（二元组语义）；否则比全部行
    scope = recorded
    repo_not_found = False
    if repo is not None:
        scope = [r for r in recorded if r["repo"] == repo]
        repo_not_found = md_exists and repo not in {r["repo"] for r in rows}

    unrecorded = [
        g for g in given_ids
        if not any(id_match(g, r) for row in scope for r in row["ids"])
    ]

    print(json.dumps({
        "date": day.strftime("%Y-%m-%d"),
        "md": md_path,
        "md_exists": md_exists,
        "merged_shards": merged_shards,
        "recorded": recorded,
        "non_commit_rows": non_commit,
        "rows_without_ids": without_ids,
        "repo_not_found_in_md": repo_not_found,
        "given": given_ids,
        "unrecorded": unrecorded,
        "all_recorded": bool(given_ids) and not unrecorded,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
