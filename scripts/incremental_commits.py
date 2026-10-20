#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报增量汇总脚本 — 汇总「还没记进日报」的本人提交（跨天），供 SKILL 第 1 步使用。

背景（2026-10-19 规则变更）：
    旧流程只取「今天」的提交，漏记的日子只能人工补；架构师要求改为按 GitLab 提交增量：
    取最近 N 天（默认 7 天，含今天＝「漏记最多一周」）内本人的提交，减去日报 md 里已记录的
    「仓库 + 提交id」，只把没记录过的写进**今天日期**的 md 文件，行日期列写真实提交日期。

背景（2026-10-20 多仓库）：
    默认不再按「当前目录」定仓库，而是扫 scripts/repos.py 登记的默认仓库清单
    （架构师常用四仓），一次输出全部仓库的增量；单仓库用 --repo 别名/路径，
    旧行为（按当前目录）保留在 --cwd 作清单外兜底。

关键点：
    🔴 去重事实源 = 回看窗口覆盖的每个月份目录下**全部 live md** + `已合并/*.md` 分片。
       不能只看今天：补记前几天的提交时，已记录行多半在更早的日文件 / 已合并分片里。
    🔴 仓库名口径 = remote URL 末段去 .git（与 SKILL「仓库列口径」一致），不猜本地目录名。
    🔴 差集键 = 仓库 + 短 id 前缀互匹配（复用 recorded_commits.id_match，长短 id 都认）。
    🔴 单仓 JSON 形状与 2026-10-19 版完全一致（只多 alias/path/status 三个字段）；
       --repo / 默认 --all 模式在外面套一层 {mode,...,repos:[...]}，--cwd 模式单仓 JSON 原样。
    🔴 本脚本只读：不写 md、不建月目录（report_dir 以 create=False 调用）。

用法：
    python incremental_commits.py                    # 扫 repos.py 全部默认仓库（回看 7 天含今天）
    python incremental_commits.py --repo zxdm        # 只扫指定仓库（别名/目录名/完整路径都认）
    python incremental_commits.py --cwd              # 旧行为：按当前目录定仓库（清单外兜底）
    python incremental_commits.py --days 14          # 漏记超过一周时扩大回看
    python incremental_commits.py --author 张三      # 换作者（默认 胡志伟，或环境变量 DAILY_REPORT_AUTHOR）
    python incremental_commits.py --today 2026-10-20 # 测试用：模拟「今天」

输出（JSON，stdout；提取字段用 jq，禁止 python -c 二次处理）：
    --cwd 模式 = 单仓 JSON（同 2026-10-19 版形状）。
    默认 / --all / --repo 模式 = {mode, date, lookback_days, window, author,
        total_unrecorded, repos_with_unrecorded, repos[]}；
        每个单仓条目 = 2026-10-19 版字段 + {alias, path, status}：
        date / no_unrecorded / repo / repo_source / author
        lookback_days / window{since,until} / branch / remote_name / origin / web_url / web_url_resolved
        md_files_scanned / md_repos             回看月份扫到的 md（含已合并分片）与其中的仓库列取值
        recorded_rows / rows_without_ids        该仓库已记录行数 / 拿不到提交id 的行（去重失效，需人工核对）
        repo_not_found_in_md                    仓库名与 md 已有写法不匹配（首次记录也会命中，先核对再写）
        candidate_count / files / insertions / deletions   窗口内本人提交总数与变更量
        unrecorded_count / unrecorded[] / unrecorded_ids[] / unrecorded_by_date{}
        already_recorded[]                      窗口内但 md 已记录的提交（「已跳过」清单，防漏用）
        commits 条目 = {id, datetime, time, date, mmdd, subject, files, insertions, deletions}
        status="error" 的条目只有 {alias, path, status, error}（目录漂了/不是 git 仓库/无远端），不炸整批。

退出码：0 正常（含 no_unrecorded / 个别仓库 error）；2 参数错误 / git 命令失败 /
--cwd 模式不在 git 仓库或无可用远端。
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

# 复用同目录既有实现（单一事实源，不重复造轮子）：
#   report_dir     → 月目录定位（create=False：只读、不建空月目录）
#   today_commits  → 远端兜底 / 凭据剥离 / 网页链接规整 / 提交汇总（区间版 collect_commits_range）
#   recorded_commits → md 表格解析（提交id 列按表头定位）/ 长短 id 前缀互匹配
#   repos          → 默认仓库清单（2026-10-20 起 --all / --repo 的对象来源）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_dir import DESKTOP, resolve_report_dir  # noqa: E402
from recorded_commits import id_match, parse_md_table  # noqa: E402
from repos import resolve_repos  # noqa: E402
from today_commits import (  # noqa: E402
    DEFAULT_AUTHOR,
    collect_commits_range,
    git_out,
    normalize_web_url,
    resolve_remote,
    strip_credentials,
)

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RepoError(Exception):
    """单仓库扫描前置失败（目录漂了 / 不是 git 仓库 / 无可用远端）——--all 模式只标不炸。"""


def month_keys(start_day, end_day):
    """回看窗口覆盖到的 (年, 月) 列表（按月去重、升序）。"""
    keys, d = [], start_day
    while d <= end_day:
        key = (d.year, d.month)
        if key not in keys:
            keys.append(key)
        d = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return keys


def collect_report_rows(start_day, end_day):
    """解析回看窗口覆盖月份下全部 live md 与 `已合并/` 分片，返回 (rows, 扫到的 md 路径列表)。

    只读：月目录不存在就跳过，不创建空目录。「已合并」分片是同一天 md 的递增快照，
    同一行可能出现多次 → 按 (seq, repo, ids, reason) 去重，避免重复计数。
    """
    files, rows = [], []
    for year, month in month_keys(start_day, end_day):
        month_dir = resolve_report_dir(date(year, month, 1), create=False)
        if not os.path.isdir(month_dir):
            continue
        md_paths = sorted(glob.glob(os.path.join(month_dir, "*.md")))
        md_paths += sorted(glob.glob(os.path.join(month_dir, "已合并", "*.md")))
        for md_path in md_paths:
            md_rows, ok, _id_col = parse_md_table(md_path)
            if not ok:
                continue
            files.append(md_path)
            for row in md_rows:
                row["md"] = md_path
                rows.append(row)

    seen, deduped = set(), []
    for row in rows:
        key = (row["seq"], row["repo"], tuple(row["ids"]), row["reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped, files


# --all 一次扫 N 个仓库，md 已记录集合与仓库无关 → 按 (起, 止) 缓存一份，防重复解析
_REPORT_ROWS_CACHE = {}


def collect_report_rows_cached(start_day, end_day):
    key = (start_day.isoformat(), end_day.isoformat())
    if key not in _REPORT_ROWS_CACHE:
        _REPORT_ROWS_CACHE[key] = collect_report_rows(start_day, end_day)
    return _REPORT_ROWS_CACHE[key]


def repo_name_from_url(url):
    """remote URL → 仓库列口径（末段去 .git）；拼不出返回空串，由调用方报错。"""
    cleaned = strip_credentials(url or "").strip().rstrip("/")
    if not cleaned:
        return ""
    last = re.split(r"[/:]", cleaned)[-1]
    return last[:-4] if last.endswith(".git") else last


def relpath(path):
    """报告根目录下的相对路径（/ 分隔），输出更易读。"""
    try:
        rel = os.path.relpath(path, DESKTOP)
    except ValueError:  # Windows 跨盘符时退化为绝对路径
        rel = path
    return rel.replace(os.sep, "/")


def scan_repo(alias, cwd, args, today, start):
    """扫一个仓库 → 单仓 JSON 条目（2026-10-19 版形状 + alias/path/status 三个字段）。

    前置不满足（目录不存在 / 不是 git 仓库 / 无可用远端）抛 RepoError；
    git 命令本身失败仍走 git_out 的 exit 2（全局环境问题，报错即停）。
    """
    if not os.path.isdir(cwd):
        raise RepoError("目录不存在（可能被移走）：改 scripts/repos.py 清单或 --repo 指别的仓库")
    if not os.path.exists(os.path.join(cwd, ".git")):
        raise RepoError("不是 git 仓库（没有 .git）：路径漂了就改 scripts/repos.py 清单")
    git_out(["rev-parse", "--is-inside-work-tree"], cwd)  # git 本身坏了 exit 2

    branch = (git_out(["branch", "--show-current"], cwd) or "").strip()
    remote_name, origin_raw = resolve_remote(cwd)
    origin = strip_credentials(origin_raw)                # 输出前剥凭据，防泄露
    web_url, resolved = normalize_web_url(origin)
    repo = repo_name_from_url(web_url if resolved else origin)
    if not repo:
        raise RepoError("找不到可用远端，无法按「remote URL 末段」确定仓库名：先配置远端再跑")

    # ---- 已记录集合：回看窗口覆盖月份的全部 live md + 已合并分片（多仓库共享一份）----
    rows, md_files = collect_report_rows_cached(start, today)
    repo_rows = [r for r in rows if r["repo"] == repo]
    recorded_ids, recorded_rows_n = [], 0
    for r in repo_rows:
        if r["reason"] is None and r["ids"]:
            recorded_ids.extend(r["ids"])
            recorded_rows_n += 1
    rows_without_ids = [
        {"md": relpath(r["md"]), "seq": r["seq"], "reason": r["reason"]}
        for r in repo_rows if r["reason"] not in (None, "无commit")
    ]
    md_repos = sorted({r["repo"] for r in rows if r["repo"]})

    # ---- 回看窗口内本人提交（复用 today_commits 的区间汇总）----
    has_head = git_out(["rev-parse", "--verify", "HEAD"], cwd, required=False) is not None
    if has_head:
        candidates, files, ins, dele = collect_commits_range(start, today, cwd, args.author)
    else:
        candidates, files, ins, dele = [], set(), 0, 0

    # ---- 差集：仓库内已记录的不再计入，余下的就是本次要记的增量 ----
    unrecorded, already = [], []
    for c in candidates:
        c["date"] = c["datetime"][:10]
        c["mmdd"] = c["datetime"][5:10]
        matched = next((rec for rec in recorded_ids if id_match(c["id"], rec)), None)
        if matched:
            already.append({"id": c["id"], "date": c["date"], "mmdd": c["mmdd"],
                            "time": c["time"], "subject": c["subject"],
                            "recorded_as": matched})
        else:
            unrecorded.append(c)

    unrecorded_by_date = {}
    for c in unrecorded:
        unrecorded_by_date.setdefault(c["date"], []).append(c["id"])

    # 仓库名与 md 任何行都不匹配 = 疑似写法不一致（首次记录该仓库时也会命中，先核对再写）
    repo_not_found = bool(rows) and repo not in md_repos

    return {
        "alias": alias,
        "path": cwd,
        "status": "ok",
        "date": today.isoformat(),
        "no_unrecorded": not unrecorded,
        "repo": repo,
        "repo_source": "web_url" if resolved else "origin",
        "author": args.author,
        "lookback_days": args.days,
        "window": {"since": start.isoformat(), "until": today.isoformat()},
        "branch": branch,
        "remote_name": remote_name,
        "origin": origin,
        "web_url": web_url,
        "web_url_resolved": resolved,
        "md_files_scanned": [relpath(p) for p in md_files],
        "md_repos": md_repos,
        "recorded_rows": recorded_rows_n,
        "rows_without_ids": rows_without_ids,
        "repo_not_found_in_md": repo_not_found,
        "candidate_count": len(candidates),
        "files": len(files),
        "insertions": ins,
        "deletions": dele,
        "unrecorded_count": len(unrecorded),
        "unrecorded": unrecorded,
        "unrecorded_ids": [c["id"] for c in unrecorded],
        "unrecorded_by_date": unrecorded_by_date,
        "already_recorded": already,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure

    ap = argparse.ArgumentParser(
        description="日报第 1 步：汇总「未记录」的本人提交（跨天增量，JSON；默认扫 repos.py 全部仓库）")
    ap.add_argument("--days", type=int, default=7,
                    help="回看天数（含今天，默认 7；对应「漏记最多一周」）")
    ap.add_argument("--author", default=os.environ.get("DAILY_REPORT_AUTHOR", DEFAULT_AUTHOR),
                    help=f"git 作者名过滤（默认 {DEFAULT_AUTHOR}）")
    ap.add_argument("--repo", metavar="别名|路径",
                    help="只扫指定仓库（repos.py 别名 / 目录名 / 完整路径；清单外路径也认）")
    ap.add_argument("--cwd", action="store_true",
                    help="旧行为：按当前目录定仓库（单仓 JSON 原样输出，清单外兜底用）")
    ap.add_argument("--all", action="store_true",
                    help="扫全部默认仓库（默认即是，显式写更好读）")
    ap.add_argument("--today", help="测试用：模拟今天（YYYY-MM-DD）")
    args = ap.parse_args()

    if args.days < 1:
        print("--days 必须 ≥ 1", file=sys.stderr)
        sys.exit(2)
    if args.cwd and args.repo:
        print("--cwd 与 --repo 二选一（--cwd 按当前目录、--repo 按清单/路径）", file=sys.stderr)
        sys.exit(2)
    if args.cwd and args.all:
        print("--cwd 与 --all 二选一", file=sys.stderr)
        sys.exit(2)
    today = date.today()
    if args.today:
        try:
            today = datetime.strptime(args.today, "%Y-%m-%d").date()
        except ValueError:
            print(f"非法日期参数：{args.today}，需为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
    start = today - timedelta(days=args.days - 1)

    # ---- --cwd：旧行为（2026-10-19 版），单仓 JSON 原样输出 ----
    if args.cwd:
        cwd = os.getcwd()
        try:
            entry = scan_repo(os.path.basename(cwd), cwd, args, today, start)
        except RepoError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return

    # ---- 默认 / --all / --repo：逐仓库扫描，外包一层汇总；单仓失败只标 error 不炸整批 ----
    try:
        targets = resolve_repos(args.repo)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    entries = []
    for alias, path in targets:
        try:
            entries.append(scan_repo(alias, path, args, today, start))
        except RepoError as e:
            entries.append({"alias": alias, "path": path, "status": "error", "error": str(e)})

    total = sum(len(e.get("unrecorded", [])) for e in entries)
    print(json.dumps({
        "mode": "repo" if args.repo else "all",
        "date": today.isoformat(),
        "lookback_days": args.days,
        "window": {"since": start.isoformat(), "until": today.isoformat()},
        "author": args.author,
        "total_unrecorded": total,
        "repos_with_unrecorded": [e["alias"] for e in entries if e.get("unrecorded")],
        "repos": entries,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
