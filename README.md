# daily-record-gitlab-md — 日报需求记录（GitLab → md）

## 相关技能

> 本 skill 写完 md 即收工：合并到当月 Excel、导出、发邮件由日报管家（daily-report-panel）自动完成，无需手动合并步骤。
- [git-commit](https://github.com/huzhw/git-commit-skill) — Git 提交规范
- [reread-rules](https://github.com/huzhw/reread-rules-skill) — 重载 CLAUDE.md / AGENTS.md 规则
- [claude-code-token-3000](https://github.com/huzhw/claude-code-token-3000-skill) — Claude Code API Token 切换
- [code-check](https://github.com/huzhw/code-check-skill) — 增量代码隐患检查
- [deepseek-harness-settings-curator](https://github.com/huzhw/deepseek-harness-settings-curator) — DSH 模型配置梳理
- [agent-config-sync-check](https://github.com/huzhw/agent-config-sync-check)：四端同步守卫：链接/硬链接/README 同步检查与修复
- [coding-rules](https://github.com/huzhw/coding-rules)：编码规则库（独立仓库，非 skill）
- [service-manager](https://github.com/huzhw/service-manager)：服务管理器（关联仓库，非 skill）
- [daily-merge-gitlab-excel](https://github.com/huzhw/daily-merge-gitlab-excel-skill)：日报合并（手动兜底，已由日报管家接管，不推荐）
- [daily-report-panel](https://github.com/huzhw/daily-report-panel)：日报管家（关联仓库，非 skill，自动合并/导出/发件）

---

从 GitLab 提交记录中提取当天完成的需求，按五维度（设计调研、代码改动、测试验证、风险返工、沟通协作）机械计价评估工时，直接写入 md 表格；**全程自动零确认**，写后输出算式审计块供核对；写完即收工，合并与发件由日报管家（daily-report-panel）自动完成。

## 核心能力

- **只读自己的提交** — 自动过滤 `--author="胡志伟"`，同分支上同事提交不混入
- **增量记录** — 同一天多次记录自动去重：md 表格带「提交id」列，`recorded_commits.py` 按「仓库 + 提交id」二元组机械比对（长短 id 前缀互匹配），只评估未记录的 commit，不靠 AI 肉眼判断；传 id 必传仓库名、跳过清单显式展示、写入后复跑自检——宁重复、勿漏记
- **智能合并** — 同文件/同模块/同功能的多笔 commit 自动合并为一条需求，避免碎片化
- **五维工时评估** — 不拍脑袋，设计/改动/测试/返工/沟通逐一展开，**固定单价计价表**机械相乘（AI 只数数量不选值），人工工时与 AI 辅助工时分开算
- **AI 工时 = 实际投入墙钟**（计价表 v1.2 定）— 不再用等效替代：需求先按机械判据分型（简单修复/常规/复杂/新架构）锁设计协助档，生成 1min/文件+1min/百行、审查 3min/文件、修正对话仅计代码返工轮 2min/轮
- **链路卡（chains.md）** — 按仓库定数量口径：Java/React/旧JSP/Python 各有「一项/一处」怎么数、标准触点清单与已知坑；构建产物、纯机械迁移不计项数
- **自我校准** — 审计块以 HTML 注释落盘 md 末尾，每次触发回看人工改值偏差；同一链路卡同一子项 ≥3 次同向偏差才提案调价/调卡，架构师确认才落盘升版本，双向可调、禁止静默改价
- **等效产出口径** — 人工工时单条不设 8h 上限（v1.1 起），人工/AI 取整统一四舍五入到 0.5h（v1.3）、不再拆分；已完成任务只用边界遗漏不算乘法返工

## 触发词

补充日报、写日报、记录需求、日报总结、今天干了什么

## 完整流程

### 1. 汇总提交 → 增量过滤 → 合并任务
从 git log 拉取当天全部提交（仅 `--author="胡志伟"`）；跑 `recorded_commits.py` 与当天 md 已记录的（仓库 + 提交id）机械比对去重；未记录的按模块/功能聚拢合并，同文件反复改的、同模块同类改动的、同一功能全链路的全部合为一条需求。

### 2. 分型 → 查链路卡 → 五维工时评估
需求先按机械判据分型（简单修复/常规/复杂/新架构，锁 AI 设计协助档）；数量口径查 chains.md 对应链路卡（Java 一个类、React 一个组件、JSP 一个页面块、Python 一个函数各自算「一项」）；人工五维单价不变，AI 辅助工时按墙钟单价另算。

| 维度 | 内容 |
|------|------|
| 设计调研 | 现状摸排 + 方案设计 + 依赖追溯 + 方案对齐 |
| 代码改动 | 新增代码 + 机械替换 + 差异修改 + 上下文切换 |
| 测试验证 | 操作入口回归 + 异步场景 + 异常分支 + 日志确认 |
| 风险返工 | 已完成：仅边界遗漏；进行中：(前三项) × 广度系数 × 深度系数 + 边界遗漏 |
| 沟通协作 | 按天算，不逐任务累加 |

### 3. 直接写入 → 写后审计块
算完不等确认，直接写入 `日报需求记录-{YYYY}-{MM}-{DD}.md`；写后在回复里输出「写后审计块」（已跳过 commit 清单、合并结果、五维度单价 × 数量算式、AI 墙钟算式 + 会话轮数证据行、工时汇总、压缩比）供事后核对，有异议直接改 md 对应行；审计块同步以 HTML 注释落盘 md 末尾，下次触发自动回看比对（自我校准）。当日无本人 commit 则回复无可记录提交收工，不编造记录。

## 输出格式

| 序号 | 日期 | 仓库 | 需求概述 | 涉及模块 | 状态 | 人工工时(h) | AI辅助工时(h) | 备注 | 提交id |
|------|------|------|---------|---------|------|-------------|---------------|------|--------|

- 状态：`100%`（已完成）、`50%`（进行中）、`0%`（未开始）
- 仓库列直写 git 仓库原名（如 `ai_data_infra`）；中文项目名由日报管家合并时按 repo_map 映射，本 skill 不做映射
- 需求概述末行溯源括号必带 **GitLab 网页链接 + 分支 + commit id + 提交日期**（如 `（2次提交 09-05 13:42~13:52 · 分支 master · GitLab：https://gitlab.xx.com/g/lanxum-amisp · commit 1a2b3c/4d5e6f）`），来源为运行时 `git remote get-url origin`（ssh 自动转网页链接）+ `git branch --show-current` + `git log %ai` 日期
- 提交id 列（第 10 列，必填）：本条需求全部 commit 短 id，`/` 分隔，跨分支带 `(分支名)` 后缀，无提交填`无`；供 `recorded_commits.py` 增量判重，日报管家解析只取前 9 列、不受影响
- 备注含文件数、行数变化、实际耗时窗口

## 工时关系

**人工工时 = 等效产出**，不是日历时间。AI 辅助下一个人一天可产出远超 8h 的工作量。必须标注实际耗时窗口（如 `⏱️ 16:27~16:40（约 13min）`）和压缩比（人工工时 ÷ 实际日历耗时），让读者知道这是 AI 压缩后的产出及放大倍数。

## 安装

```bash
git clone https://github.com/huzhw/daily-record-gitlab-md-skill.git ~/.claude/skills/daily-record-gitlab-md
```

安装后在 AI 编码助手里说「补充日报」即可触发。

## 许可

MIT