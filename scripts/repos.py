#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报默认仓库清单（单一事实源）— incremental_commits.py 默认扫描的对象。

背景（2026-10-20 架构师要求「默认几个仓库，免得来回切」）：
    以前记日报要挨个项目切目录跑脚本；现在把常用仓库登记在这份清单里，
    incremental_commits.py 不带参数就一次扫全部，输出按仓库分组的增量 JSON。

口径（红线）：
    🔴 清单只登记「别名 → 本地 git 仓库路径」；日报「仓库」列真名**不在这里维护**——
       脚本运行时按 remote URL 末段去 .git 现取（与 SKILL「仓库列口径」一致），防两边漂移。
    🔴 加新仓库：在 DEFAULT_REPOS 里按常用顺序加一行 (别名, 路径)；别名随手起、
       不与既有别名/目录名撞车即可（撞车会在 --repo 时报「同时命中多个」）。
    🔴 路径漂了（目录被移走 / 不是 git 仓库）不炸整批：--all 模式下该仓库条目标
       status="error" 单独报，其余仓库照常出；此时先改这里再补记。

用法（供 incremental_commits.py 导入；也可单独跑看清单）：
    python repos.py        # 打印当前清单 JSON
"""

import json
import os
import sys

# 常用仓库按顺序登记（2026-10-20 架构师指定四仓：两个中信底稿 + 两个 amisp）。
# 顺序即 --all 输出顺序，最常用的放前面。
DEFAULT_REPOS = [
    ("zxdm",        r"F:\idea-workspase-zhongXin-diGaoV5\standard_thdg_zxdm"),
    ("zxdm-react",  r"F:\idea-workspase-zhongXin-diGaoV5\standard_thdg_zxdm_react"),
    ("amisp-java",  r"F:\idea-workspase-amispV6\lanxum-amisp-java"),
    ("amisp-react", r"F:\idea-workspase-amispV6\lanxum-amisp-react"),
]


def _norm(path):
    """Windows 路径归一（绝对化 + 小写），用于 --repo 参数与清单路径比对。"""
    return os.path.normpath(os.path.abspath(path)).lower()


def resolve_repos(arg):
    """--repo 参数解析：别名 / 目录名 / 完整路径都认；不在清单里就当任意仓库路径用。

    返回 [(别名, 路径)]；resolve_repos(None) = 全部默认仓库。
    裸名同时命中多个默认仓库时抛 ValueError（调用方报错退出）。
    """
    if not arg:
        return list(DEFAULT_REPOS)
    key = _norm(arg)
    base = os.path.basename(os.path.normpath(arg)).lower()
    hits = []
    for alias, path in DEFAULT_REPOS:
        base_of_registered = os.path.basename(os.path.normpath(path)).lower()
        if arg.lower() == alias.lower() or key == _norm(path) or base == base_of_registered:
            hits.append((alias, path))
    if len(hits) == 1:
        return hits
    if len(hits) > 1:
        raise ValueError(
            f"--repo {arg!r} 同时命中多个默认仓库：{[h[0] for h in hits]}；"
            f"请用更精确的别名或完整路径")
    # 清单外：当任意仓库路径用（别名 = 目录名，仅作展示）
    return [(base or arg, os.path.abspath(arg))]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure
    print(json.dumps({"default_repos": [
        {"alias": a, "path": p} for a, p in DEFAULT_REPOS
    ]}, ensure_ascii=False, indent=2))
