#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报提交汇总脚本 — 一次输出当天本人全部提交 + GitLab 溯源四件套（JSON）。

背景：
    SKILL 第 1 步原来要拼 4~5 条 git 命令（log / diff --stat / remote / branch），
    且 git diff 不支持 --author、会静默忽略不报错（2026-09-09 实测），同事提交混入变更总量。
    本脚本把第 1 步机械化：author 过滤内置；行数按逐 commit numstat 求和（二进制跳过）；
    网页链接规整内置（git@ / ssh:// / https → https 网页地址，凭据剥离，拼不出则输出原文）。

    🔴 远端名兼容（2026-09-10 实测：本工作区 4/15 仓库远端叫 gitlab、没有 origin）：
    按 origin → gitlab → upstream → 唯一远端 依次兜底，输出实际用的远端名。
    🔴 凭据剥离（2026-09-10）：部分远端 URL 形如 http://user:pass@host/...，
    直接落进日报会泄露账号密码，normalize_web_url / origin 字段先剥 user:pass@。

用法（在目标 git 仓库目录下运行）：
    python today_commits.py                     # 今天
    python today_commits.py 2026-09-05          # 补历史（YYYY-MM-DD）
    python today_commits.py --author 张三       # 换作者（默认 胡志伟，或环境变量 DAILY_REPORT_AUTHOR）

输出（JSON，stdout；提取字段用 jq，禁止 python -c 二次处理）：
    date / no_commits / count / files / insertions / deletions
    window        {first, last, first_full, last_full}   HH:MM 时间窗与完整时间
    branch / remote_name / origin / web_url / web_url_resolved
    commits       [{id, time, datetime, subject, files, insertions, deletions}]  按时间升序
                  files = 该 commit 去重文件数；insertions/deletions = 该 commit 行数累计
                  （二进制计文件不计行；构建产物过滤由 SKILL/chains 口径决定，脚本不过滤）

退出码：0 正常（含 no_commits）；2 参数错误 / 不在 git 仓库 / git 命令失败。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

# 🔴 只统计自己的提交（SKILL 红线）：作者身份以 %an 输出「胡志伟 <huzhiwei@lanxum.com>」为准。
# 可用 --author 覆盖（换机器 / 换 git 身份时），也读环境变量 DAILY_REPORT_AUTHOR。
DEFAULT_AUTHOR = "胡志伟"

# 🔴 远端名兼容顺序（2026-09-10 实测：本工作区部分仓库远端是 gitlab，无 origin）
REMOTE_PREFERENCE = ("origin", "gitlab", "upstream")


def git_out(args, cwd, required=True):
    """跑 git 命令返回 stdout 文本；required=True 时失败 exit 2（中文报错不抛 traceback）。"""
    try:
        p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, timeout=60)
    except FileNotFoundError:
        print("找不到 git 命令，请确认 git 已安装并在 PATH 中", file=sys.stderr)
        sys.exit(2)
    if p.returncode != 0:
        if not required:
            return None
        msg = p.stderr.decode("utf-8", errors="replace").strip() or " ".join(args)
        print(f"git 命令失败：{msg}", file=sys.stderr)
        sys.exit(2)
    return p.stdout.decode("utf-8", errors="replace")


def strip_credentials(url):
    """剥离 URL 里的 user:pass@，防止账号密码落进日报（2026-09-10 实测 origin 带凭据）。"""
    return re.sub(r"^([a-zA-Z][a-zA-Z0-9+.-]*://)[^/@]*@", r"\1", url.strip())


def normalize_web_url(origin):
    """origin 远端地址 → GitLab 网页链接；规则拼不出来返回 (原文, False)，不猜、不硬编码 host。

    先剥凭据：http(s)://user:pass@host/... 与 git@host:... 中的账号信息都不得进日报。
    """
    url = strip_credentials(origin)
    if not url:
        return "", False
    no_git = url[:-4] if url.endswith(".git") else url
    m = re.match(r"^git@([^:]+):(.+)$", no_git)                 # git@host:组/仓库
    if m:
        return f"https://{m.group(1)}/{m.group(2)}", True
    m = re.match(r"^ssh://git@([^/:]+)(?::\d+)?/(.+)$", no_git)  # ssh://git@host[:端口]/组/仓库
    if m:
        return f"https://{m.group(1)}/{m.group(2)}", True
    if no_git.startswith("http://") or no_git.startswith("https://"):
        return no_git, True                                     # http(s) 原样（已去 .git、已剥凭据）
    return url, False


def resolve_remote(cwd):
    """挑一个可用远端：origin → gitlab → upstream → 唯一远端；返回 (远端名, url)。无远端返回 ("", "")。"""
    names = (git_out(["remote"], cwd, required=False) or "").split()
    for name in REMOTE_PREFERENCE:
        if name in names:
            url = (git_out(["remote", "get-url", name], cwd) or "").strip()
            return name, url
    if len(names) == 1:  # 只有唯一远端（名字不认识）时也认它
        url = (git_out(["remote", "get-url", names[0]], cwd) or "").strip()
        return names[0], url
    return "", ""


def collect_commits(day, cwd, author):
    """取 day 当天本人提交（按作者日期精确筛选），附逐 commit numstat 聚合。

    git 侧 --since/--until 是宽窗口预过滤（按 commit 日期），最终以 %ai 作者日期精确比对，
    保证展示日期与筛选口径一致。
    """
    fmt = "--format=%x00%h%x00%ai%x00%s"
    since = f"{(day - timedelta(days=1)).isoformat()} 00:00:00"
    until = f"{(day + timedelta(days=1)).isoformat()} 23:59:59"
    raw = git_out(["log", fmt, f"--author={author}", f"--since={since}", f"--until={until}",
                   "--numstat"], cwd)

    commits, files, ins, dele = [], set(), 0, 0
    cur = None
    for line in raw.splitlines():
        if line.startswith("\x00"):
            _, cid, ai, subject = line.split("\x00", 3)
            try:
                dt = datetime.strptime(ai, "%Y-%m-%d %H:%M:%S %z")
            except ValueError:
                continue
            if dt.date() == day:  # 作者日期精确筛选
                cur = {"id": cid, "datetime": ai, "time": ai[11:16], "subject": subject,
                       "files": 0, "insertions": 0, "deletions": 0, "_fset": set()}
                commits.append(cur)
            else:
                cur = None
        elif cur is not None and line.strip():
            parts = line.split("\t")
            if len(parts) >= 3:
                files.add(parts[2])
                cur["_fset"].add(parts[2])
                if parts[0] != "-":  # 二进制文件行数为 "-"，只计文件不计行
                    cur["insertions"] += int(parts[0])
                    ins += int(parts[0])
                if parts[1] != "-":
                    cur["deletions"] += int(parts[1])
                    dele += int(parts[1])
    for c in commits:
        c["files"] = len(c.pop("_fset"))
    commits.sort(key=lambda c: c["datetime"])
    return commits, files, ins, dele


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure

    ap = argparse.ArgumentParser(
        description="日报第 1 步：汇总当天本人全部提交 + GitLab 溯源四件套（JSON）")
    ap.add_argument("date", nargs="?", help="YYYY-MM-DD（缺省今天）")
    ap.add_argument("--author", default=os.environ.get("DAILY_REPORT_AUTHOR", DEFAULT_AUTHOR),
                    help=f"git 作者名过滤（默认 {DEFAULT_AUTHOR}）")
    args = ap.parse_args()

    day = date.today()
    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"非法日期参数：{args.date}，需为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)

    cwd = os.getcwd()
    git_out(["rev-parse", "--is-inside-work-tree"], cwd)  # 不在 git 仓库内则 exit 2

    branch = (git_out(["branch", "--show-current"], cwd) or "").strip()
    remote_name, origin_raw = resolve_remote(cwd)
    origin = strip_credentials(origin_raw)                # 输出前剥凭据，防泄露
    web_url, resolved = normalize_web_url(origin)

    has_head = git_out(["rev-parse", "--verify", "HEAD"], cwd, required=False) is not None
    commits, files, ins, dele = collect_commits(day, cwd, args.author) if has_head else ([], set(), 0, 0)

    print(json.dumps({
        "date": day.isoformat(),
        "no_commits": not commits,
        "count": len(commits),
        "files": len(files),
        "insertions": ins,
        "deletions": dele,
        "window": {
            "first": commits[0]["time"] if commits else "",
            "last": commits[-1]["time"] if commits else "",
            "first_full": commits[0]["datetime"] if commits else "",
            "last_full": commits[-1]["datetime"] if commits else "",
        },
        "branch": branch,
        "remote_name": remote_name,
        "origin": origin,
        "web_url": web_url,
        "web_url_resolved": resolved,
        "commits": commits,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
