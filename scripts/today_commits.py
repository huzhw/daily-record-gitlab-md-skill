#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报提交汇总脚本 — 一次输出当天本人全部提交 + GitLab 溯源四件套（JSON）。

背景：
    SKILL 第 1 步原来要拼 4~5 条 git 命令（log / diff --stat / remote / branch），
    且 git diff 不支持 --author、会静默忽略不报错（2026-09-09 实测），同事提交混入变更总量。
    本脚本把第 1 步机械化：author 过滤内置；行数按逐 commit numstat 求和（二进制跳过），
    网页链接规整内置（git@ / ssh:// / https → https 网页地址，拼不出则输出原文）。

用法（在目标 git 仓库目录下运行）：
    python today_commits.py                # 今天
    python today_commits.py 2026-09-05     # 补历史（YYYY-MM-DD）

输出（JSON，stdout；提取字段用 jq，禁止 python -c 二次处理）：
    date / no_commits / count / files / insertions / deletions
    window      {first, last, first_full, last_full}   HH:MM 时间窗与完整时间
    branch / origin / web_url / web_url_resolved
    commits     [{id, time, datetime, subject}]        按时间升序

退出码：0 正常（含 no_commits）；2 参数错误 / 不在 git 仓库 / git 命令失败。
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

# 🔴 只统计自己的提交（SKILL 红线）：作者身份以 %an 输出「胡志伟 <huzhiwei@lanxum.com>」为准
AUTHOR = "胡志伟"


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


def normalize_web_url(origin):
    """origin 远端地址 → GitLab 网页链接；规则拼不出来返回 (原文, False)，不猜、不硬编码 host。"""
    url = origin.strip()
    if not url:
        return "", False
    no_git = url[:-4] if url.endswith(".git") else url
    m = re.match(r"^git@([^:]+):(.+)$", no_git)                # git@host:组/仓库
    if m:
        return f"https://{m.group(1)}/{m.group(2)}", True
    m = re.match(r"^ssh://git@([^/:]+)(?::\d+)?/(.+)$", no_git)  # ssh://git@host[:端口]/组/仓库
    if m:
        return f"https://{m.group(1)}/{m.group(2)}", True
    if no_git.startswith("http://") or no_git.startswith("https://"):
        return no_git, True                                     # https 原样（已去 .git）
    return url, False


def collect_commits(day, cwd):
    """取 day 当天本人提交（按作者日期精确筛选），附逐 commit numstat 聚合。

    git 侧 --since/--until 是宽窗口预过滤（按 commit 日期），最终以 %ai 作者日期精确比对，
    保证展示日期与筛选口径一致。
    """
    fmt = "--format=%x00%h%x00%ai%x00%s"
    since = f"{(day - timedelta(days=1)).isoformat()} 00:00:00"
    until = f"{(day + timedelta(days=1)).isoformat()} 23:59:59"
    raw = git_out(["log", fmt, f"--author={AUTHOR}", f"--since={since}", f"--until={until}",
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
                cur = {"id": cid, "datetime": ai,
                       "time": ai[11:16], "subject": subject}
                commits.append(cur)
            else:
                cur = None
        elif cur is not None and line.strip():
            parts = line.split("\t")
            if len(parts) >= 3:
                files.add(parts[2])
                if parts[0] != "-":  # 二进制文件行数为 "-"，只计文件不计行
                    ins += int(parts[0])
                if parts[1] != "-":
                    dele += int(parts[1])
    commits.sort(key=lambda c: c["datetime"])
    return commits, files, ins, dele


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure

    day = date.today()
    if len(sys.argv) > 1:
        try:
            day = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"非法日期参数：{sys.argv[1]}，需为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)

    cwd = os.getcwd()
    git_out(["rev-parse", "--is-inside-work-tree"], cwd)  # 不在 git 仓库内则 exit 2

    branch = (git_out(["branch", "--show-current"], cwd) or "").strip()
    origin_raw = git_out(["remote", "get-url", "origin"], cwd, required=False)
    origin = (origin_raw or "").strip()
    web_url, resolved = normalize_web_url(origin)

    has_head = git_out(["rev-parse", "--verify", "HEAD"], cwd, required=False) is not None
    commits, files, ins, dele = collect_commits(day, cwd) if has_head else ([], set(), 0, 0)

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
        "origin": origin,
        "web_url": web_url,
        "web_url_resolved": resolved,
        "commits": commits,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
