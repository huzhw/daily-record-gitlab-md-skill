# daily-record-gitlab-md — 日报需求记录（GitLab → md）

## 相关技能

> 本 skill 写完 md 即收工：合并到当月 Excel、导出、发邮件由日报管家（daily-report-panel）自动完成，无需手动合并步骤。
- [git-commit](https://github.com/huzhw/git-commit-skill) — Git 提交规范
- [reread-rules](https://github.com/huzhw/reread-rules-skill) — 重载 CLAUDE.md / AGENTS.md 规则
- [code-check](https://github.com/huzhw/code-check-skill) — 增量代码隐患检查
- [deepseek-harness-settings-curator](https://github.com/huzhw/deepseek-harness-settings-curator) — DSH 模型配置梳理
- [deepseek-harness-plugin-doctor](https://github.com/huzhw/deepseek-harness-plugin-doctor) — DSH 插件与升级体检医生
- [agent-config-sync-check](https://github.com/huzhw/agent-config-sync-check)：四端同步守卫：链接/硬链接/README 同步检查与修复
- [coding-rules](https://github.com/huzhw/coding-rules)：编码规则库（独立仓库，非 skill）
- [service-manager](https://github.com/huzhw/service-manager)：服务管理器（关联仓库，非 skill）
- [daily-merge-gitlab-excel](https://github.com/huzhw/daily-merge-gitlab-excel-skill)：日报合并（手动兜底，已由日报管家接管，不推荐）
- [daily-report-panel](https://github.com/huzhw/daily-report-panel)：日报管家（关联仓库，非 skill，自动合并/导出/发件）

---

从 GitLab 提交记录中提取当天完成的需求，开发类按五维度（设计调研、代码改动、测试验证、风险返工、沟通协作）机械计价评估工时、**文档类（`docs/`/`memory/`/`memory/ai/`）按文档单价表**、**运维/实施类按实测记录**，直接写入 md 表格；**全程自动零确认**，写后输出算式审计块供核对；写完即收工，合并与发件由日报管家（daily-report-panel）自动完成。

## 核心能力

- **只读自己的提交** — `today_commits.py` 一键汇总当天提交：内置 `--author="胡志伟"` 过滤（可用 `--author` 覆盖），一次输出提交清单（含每笔 commit 的文件数与 ±行）/总文件数/总行数（逐 commit numstat 求和）/时间窗/分支/GitLab 网页链接 JSON；远端名兼容（`origin`→`gitlab`→`upstream`→唯一远端）、URL 凭据自动剥离，同分支上同事提交不混入
- **增量记录** — 同一天多次记录自动去重：md 表格带「提交id」列，`recorded_commits.py` 按「仓库 + 提交id」二元组机械比对（长短 id 前缀互匹配），只评估未记录的 commit，不靠 AI 肉眼判断；传 id 必传仓库名、跳过清单显式展示、写入后复跑自检——宁重复、勿漏记
- **智能合并** — 同文件/同模块/同功能的多笔 commit 自动合并为一条需求，避免碎片化
- **五维工时评估** — 不拍脑袋，设计/改动/测试/返工/沟通逐一展开，**固定单价计价表**机械相乘（AI 只数数量不选值），人工工时与 AI 辅助工时分开算
- **AI 辅助工时 = 人 + AI 配合的实际工时**（计价表 v1.6 定口径）— 这条需求从开工到收工，人和 AI 一起干的实际时长，按实测 / 用户口径记；🔴 不再按「单价 × 数量」求和（v1.4/v1.5 的等效投入口径已废），🔴 禁止拿会话数 / 对话轮数反推
- **任务类型（v1.6/v1.7）** — **开发类**＝产出代码/配置（五维单价表 + 链路卡）；**文档类**＝`docs/`、`memory/`、`memory/ai/` 下当天新增或修改的文档（走文档单价表）；**运维/实施类**＝无 git 改动的服务器/环境操作（装库、部署、配置对齐、启停、发版、备份），**不进单价表**：分型写「运维」、人工与 AI 两列都记实测、`⏱` 用实测起止（禁止借用其他行的提交时间窗）。🔴 判据冲突取高：含代码即开发类
- **文档类单价表（v1.7）** — 新建文档 0.5h/篇 + 正文 0.3h/百行 + 事实核对/渲染校验 5min/篇 + 修改已有文档 8min/处（机械替换 3min/处）+ 边界遗漏 0.2h；取整 0.5h、单条最低 0.25h；数量口径＝`docs/`、`memory/`、`memory/ai/` 下当天文档去重文件数与新增行数（`memory/ai/` 被 .gitignore 排除时按文件实际行数）
- **链路卡（chains.md）** — 按仓库定数量口径：Java/React/旧JSP/Python 各有「一项/一处」怎么数、标准触点清单与已知坑；构建产物、纯机械迁移不计项数
- **自我校准** — 审计块以 HTML 注释落盘 md 末尾，每次触发回看人工改值偏差；同一链路卡同一子项 ≥3 次同向偏差才提案调价/调卡，架构师确认才落盘升版本，双向可调、禁止静默改价
- **工时口径** — 人工工时（开发类 / 文档类）＝等效产出，单条不设 8h 上限（v1.1 起）、取整四舍五入到 0.5h（v1.3）；AI 辅助工时＝人 + AI 配合的实际工时（v1.6，墙钟、与人工列同量纲可算压缩比）；运维/实施类两列都记实测；子项切分与 ×0.6 折扣走 v1.5 机械规则（业务链路簇 + 源码 insertions 定锚）；已完成任务只用边界遗漏不算乘法返工
- **重记 / 重跑** — 用户说「删掉重新记录」时不走去重：贴旧行对账 → 删旧行与对应审计块、序号重排 → 对该仓库当天全部 commit 全量重跑（不留旧数字）→ 复跑 `recorded_commits.py` 自检

## 触发词

补充日报、写日报、记录需求、日报总结、今天干了什么

## 完整流程

### 1. 汇总提交 → 增量过滤 → 合并任务
跑 `today_commits.py` 拉取当天全部提交（内置 `--author="胡志伟"` 过滤、可覆盖；远端名 `origin/gitlab/upstream` 兜底、凭据剥离）；跑 `recorded_commits.py` 与当天 md 已记录的（仓库 + 提交id）机械比对去重；未记录的按模块/功能聚拢合并（同文件反复改、同模块同类改动、同一功能全链路合成一条），子项切分与 ×0.6 折扣按 SKILL 第 2 步 v1.5 机械规则。

### 2. 判任务类型 → 分型 → 查链路卡 → 工时评估
**先判任务类型（v1.6/v1.7）**：**开发类**（产出代码/配置）按机械判据分型（简单修复/常规/复杂/新架构，分型仅作审计展示）、数量口径查 chains.md 对应链路卡（Java 一个类、React 一个组件、JSP 一个页面块、Python 一个函数各自算「一项」）、人工五维单价不变；**文档类**（`docs/`、`memory/`、`memory/ai/` 的文档，不含代码改动）查 chains.md 卡 8（文档类）走文档单价表；**运维/实施类**（无 git 改动）**不走单价表**——分型写「运维」、查 chains.md 卡 7（服务器运维/实施），人工与 AI 两列都记实测耗时、`⏱` 用实测起止。AI 辅助工时按 v1.6＝人 + AI 配合的实际工时。

| 维度 | 内容 |
|------|------|
| 设计调研 | 现状摸排 + 方案设计 + 依赖追溯 + 方案对齐 |
| 代码改动 | 新增代码 + 机械替换 + 差异修改 + 上下文切换 |
| 测试验证 | 操作入口回归 + 异步场景 + 异常分支 + 日志确认 |
| 风险返工 | 已完成：仅边界遗漏；进行中：(前三项) × 广度系数 × 深度系数 + 边界遗漏 |
| 沟通协作 | 按天算，不逐任务累加 |

### 3. 直接写入 → 写后审计块
算完不等确认，直接写入 `日报需求记录-{YYYY}-{MM}-{DD}.md`；写后在回复里输出「写后审计块」（已跳过 commit 清单、合并结果、工时算式——开发类＝五维单价 × 数量逐项；文档类＝文档单价表（新建篇数/新增行数/修改处数）；运维/实施类＝实测起止与时长——AI 辅助工时实测值 + 证据行、工时汇总、压缩比）供事后核对，有异议直接改 md 对应行；审计块同步以 HTML 注释落盘 md 末尾，下次触发自动回看比对（自我校准）。当日无本人 commit 且无运维/实施工作才回复无可记录提交收工，不编造记录。

### 4. 重记 / 重跑
用户说「删掉重新记录」时：贴出旧行对账 → 删旧行与对应审计注释块、剩余序号重排 → 对该仓库当天全部 commit 全量重跑（不留旧数字）→ 复跑 `recorded_commits.py` 自检。详见 SKILL.md「重记 / 重跑」。

## 输出格式

| 序号 | 日期 | 仓库 | 需求概述 | 涉及模块 | 状态 | 人工工时(h) | AI辅助工时(h) | 备注 | 提交id |
|------|------|------|---------|---------|------|-------------|---------------|------|--------|

- 状态：`100%`（已完成）、`50%`（进行中）、`0%`（未开始）
- 仓库列直写 git 仓库原名（如 `ai_data_infra`）= **remote URL 末段去掉 `.git`**，不是本地目录名（目录 `standard_thdg_zxdm` → 仓库 `workingpaper-v5.5`）；中文项目名由日报管家合并时按 repo_map 映射，本 skill 不做映射
- 需求概述末行溯源括号必带 **GitLab 网页链接 + 分支 + commit id + 提交日期**（如 `（2次提交 09-05 13:42~13:52 · 分支 master · GitLab：https://gitlab.xx.com/g/lanxum-amisp · commit 1a2b3c/4d5e6f）`），来源为 `today_commits.py` 输出的 `web_url` / `branch` / `commits[].datetime`（内部即 `git remote get-url <origin|gitlab|upstream>` + `git branch --show-current` + `git log %ai`，ssh 自动转网页链接、URL 凭据自动剥离）
- 提交id 列（第 10 列，必填）：本条需求全部 commit 短 id，`/` 分隔，跨分支带 `(分支名)` 后缀，无提交填`无`；供 `recorded_commits.py` 增量判重，日报管家解析只取前 9 列、不受影响
- 备注含**源码文件去重数**、**源码 insertions**（`+X/-Y 行`；构建产物 / `min` / `*.tsbuildinfo` / 二进制 / 纯重命名迁移不计）与该行耗时窗口 `⏱ MM-DD HH:MM~HH:MM（约 Xh）`

## 工时关系

**人工工时 = 等效产出**，不是日历时间。AI 辅助下一个人一天可产出远超 8h 的工作量。必须标注实际耗时窗口（如 `⏱️ 16:27~16:40（约 13min）`）和压缩比（人工工时 ÷ 实际日历耗时），让读者知道这是 AI 压缩后的产出及放大倍数。

## 安装

```bash
git clone https://github.com/huzhw/daily-record-gitlab-md-skill.git ~/.claude/skills/daily-record-gitlab-md
```

安装后在 AI 编码助手里说「补充日报」即可触发。

## 许可

MIT