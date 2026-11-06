#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报仓库级联清单（单一事实源）— incremental_commits.py 默认扫描的对象。

结构：
    清单在 `scripts/repos.json`：项目（两套系统）→ 分组 → 仓。
    `--all` 每次只扫**一套系统**：默认按锚点（当前目录所在的那套）定域，
    在底稿的仓里敲只扫底稿，在档案的仓里敲只扫档案；跨系统用 `--system <系统名>` 点名；
    锚点不属于任何登记系统时报错并列出可选系统名，不静默扩大范围。

口径（红线）：
    🔴 清单只登记「系统 / 分组 / 仓目录名 / 中文名」；日报「仓库」列真名**不在这里维护**——
       脚本运行时按 remote URL 末段去 .git 现取（与 SKILL「仓库列口径」一致），防两边漂移。
    🔴 加新仓库：只改 `scripts/repos.json`（在对应系统的 groups 里加一条 {dir, cn}），不动代码；
       目录名即 --repo 别名，重名会在 --repo 时报「同时命中多个」。
    🔴 路径漂了（目录被移走 / 不是 git 仓库）不炸整批：该仓库条目标 status="error" 单独报，
       其余仓库照常出；此时先改 repos.json 再补记。

用法（供 incremental_commits.py 导入；也可单独跑看清单）：
    python repos.py                      # 打印当前清单 JSON（含所属系统与分组）
    python repos.py --system 档案V6       # 只打印该系统的仓
"""

import json
import os
import subprocess
import sys

CFG_NAME = "repos.json"


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _norm(path):
    """Windows 路径归一（绝对化 + 小写），用于 --repo 参数与清单路径比对。"""
    return os.path.normcase(os.path.normpath(os.path.abspath(path))).lower()


def load_cfg():
    """读 scripts/repos.json；读不到或格式坏直接抛 ValueError（调用方退出）。"""
    path = os.path.join(_script_dir(), CFG_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except OSError as e:
        raise ValueError(f"仓库清单读不到：{path}（{e}）")
    except ValueError as e:
        raise ValueError(f"仓库清单格式坏了：{path}（{e}）")
    if not cfg.get("projects"):
        raise ValueError(f"仓库清单里没有 projects：{path}")
    return cfg


def system_names(cfg):
    """登记的系统名列表（projects[].project），报错提示可选项用。"""
    return [p.get("project") for p in cfg.get("projects", []) if p.get("project")]


def flatten(cfg, system=None):
    """把 系统 → 分组 → 仓 摊平成 [{system, group, alias, cn, dir, path}]。

    system=None 收全部；否则只收点名的那套（点名不存在由调用方先校验）。
    alias 默认为仓目录名（--repo 直接用它），cn 只作展示。
    """
    out = []
    for proj in cfg.get("projects", []):
        pname = proj.get("project") or ""
        if system is not None and pname != system:
            continue
        root = proj.get("root")
        if not root:
            continue
        exclude = set(proj.get("exclude") or [])
        for group in proj.get("groups", []):
            gname = group.get("name") or ""
            for item in group.get("repos", []):
                if isinstance(item, str):
                    d, cn = item, ""
                else:
                    d = item.get("dir") or item.get("repo") or ""
                    cn = item.get("cn") or item.get("name") or ""
                if not d or d in exclude:
                    continue
                out.append({
                    "system": pname,
                    "group": gname,
                    "alias": d,
                    "cn": cn,
                    "dir": d,
                    "path": os.path.join(root, d),
                })
    return out


def git_toplevel(cwd):
    """当前目录所在 git 仓根；不是 git 仓返回 None（锚点退回用传入目录本身）。"""
    p = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                       capture_output=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return None
    return p.stdout.strip() or None


def anchor_path(cwd):
    """级联锚点：优先 git 仓根（在仓的子目录里敲也能定位），不是 git 仓就用该目录本身。"""
    return git_toplevel(cwd) or os.path.abspath(cwd)


def is_within(path, parent):
    """path 是否落在 parent 目录内（含相等）。两边按 realpath + normcase 归一。

    归一防符号链接、大小写差异把归属判错；不同盘符时 commonpath 抛 ValueError，按「不在里面」处理。
    """
    try:
        p = os.path.normcase(os.path.realpath(path))
        q = os.path.normcase(os.path.realpath(parent))
    except OSError:
        return False
    if p == q:
        return True
    try:
        return os.path.commonpath([p, q]) == q
    except ValueError:
        return False


def resolve_scope(cfg, anchor):
    """按锚点目录判定扫描哪套系统；多个登记根嵌套时取路径最长的那个（更具体）。"""
    best, best_len = None, -1
    for proj in cfg.get("projects", []):
        root = proj.get("root")
        if not root or not os.path.isdir(root):
            continue
        if not is_within(anchor, root):
            continue
        n = len(os.path.normcase(os.path.realpath(root)))
        if n > best_len:
            best, best_len = proj, n
    return best


def resolve_repos(arg=None, system=None, anchor=None):
    """解析本次要扫的仓库。

    arg    = --repo 参数：别名（仓目录名）/ 中文名 / 目录名 / 完整路径都认；清单外路径也认。
    system = --system 参数：点名要扫的系统（projects[].project）。
    anchor = 锚点目录（默认当前目录）：不点名系统时按它判定属于哪套系统。

    返回 (targets, scope_name)：targets = [{system, group, alias, cn, dir, path}]；
    scope_name = 本次扫的系统名（--repo 单仓模式或清单外路径时为 None）。
    定不出范围（锚点不属于任何系统、系统名写错、--repo 撞名）抛 ValueError，调用方打印退出。
    """
    cfg = load_cfg()
    names = system_names(cfg)

    if arg:
        key = _norm(arg)
        base = os.path.basename(os.path.normpath(arg)).lower()
        hits = []
        for item in flatten(cfg):
            registered = os.path.basename(os.path.normpath(item["path"])).lower()
            if (arg.lower() == item["alias"].lower()
                    or (item["cn"] and arg == item["cn"])
                    or key == _norm(item["path"])
                    or base == registered):
                hits.append(item)
        if len(hits) == 1:
            return hits, None
        if len(hits) > 1:
            raise ValueError(
                f"--repo {arg!r} 同时命中多个登记仓：{[h['alias'] for h in hits]}；"
                f"请用更精确的目录名或完整路径")
        # 清单外：当任意仓库路径用（只作展示）
        return [{"system": "", "group": "", "alias": base or arg, "cn": "",
                 "dir": base, "path": os.path.abspath(arg)}], None

    if system:
        if system not in names:
            raise ValueError(f"没有这个系统：{system}（可选：{' / '.join(names)}）")
    else:
        anchor = anchor_path(anchor or os.getcwd())
        proj = resolve_scope(cfg, anchor)
        if proj is None:
            raise ValueError(
                f"当前目录不属于任何登记系统：{anchor}\n"
                f"用 --system <系统名> 指定要扫哪一套（可选：{' / '.join(names)}），"
                f"或进到该系统的仓里执行")
        system = proj.get("project") or ""

    targets = flatten(cfg, system)
    if not targets:
        raise ValueError(f"系统「{system}」下没有登记的仓，检查 {os.path.join(_script_dir(), CFG_NAME)}")
    return targets, system


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure
    want = None
    if len(sys.argv) > 2 and sys.argv[1] == "--system":
        want = sys.argv[2]
    try:
        cfg = load_cfg()
        items = flatten(cfg, want)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    print(json.dumps({"systems": system_names(cfg), "repos": items},
                     ensure_ascii=False, indent=2))
