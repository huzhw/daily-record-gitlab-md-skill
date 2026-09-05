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

从 GitLab 提交记录中提取当天完成的需求，按五维度（设计调研、代码改动、测试验证、风险返工、沟通协作）逐项评估工时，写入 md 表格；写完即收工，合并与发件由日报管家（daily-report-panel）自动完成。

## 核心能力

- **只读自己的提交** — 自动过滤 `--author="胡志伟"`，同分支上同事提交不混入
- **智能合并** — 同文件/同模块/同功能的多笔 commit 自动合并为一条需求，避免碎片化
- **五维工时评估** — 不拍脑袋，设计/改动/测试/返工/沟通逐一展开，人工工时与 AI 辅助工时分开算
- **上限兜底** — 单条 ≤ 8h，超过自动拆分；已完成任务只用边界遗漏不算乘法返工

## 触发词

补充日报、写日报、记录需求、日报总结、今天干了什么

## 完整流程

### 1. 汇总提交 → 合并任务
从 git log 拉取当天全部提交（仅 `--author="胡志伟"`），按模块/功能聚拢合并，同文件反复改的、同模块同类改动的、同一功能全链路的全部合为一条需求。

### 2. 五维工时评估
| 维度 | 内容 |
|------|------|
| 设计调研 | 现状摸排 + 方案设计 + 依赖追溯 + 方案对齐 |
| 代码改动 | 新增代码 + 机械替换 + 差异修改 + 上下文切换 |
| 测试验证 | 操作入口回归 + 异步场景 + 异常分支 + 日志确认 |
| 风险返工 | 已完成：仅边界遗漏；进行中：(前三项) × 广度系数 × 深度系数 + 边界遗漏 |
| 沟通协作 | 按天算，不逐任务累加 |

### 3. 用户确认 → 写入 md
展示汇总后等用户确认工时数字，确认后写入 `日报需求记录-{YYYY}-{MM}-{DD}.md`。

## 输出格式

| 序号 | 日期 | 仓库 | 需求概述 | 涉及模块 | 状态 | 人工工时(h) | AI辅助工时(h) | 备注 |
|------|------|------|---------|---------|------|-------------|---------------|------|

- 状态：`100%`（已完成）、`50%`（进行中）、`0%`（未开始）
- 仓库名自动映射为中文简称（如 `ai_data_infra` → 智能数据底座）
- 需求概述末行溯源括号必带 **GitLab 网页链接 + 分支 + commit id**（如 `（2次提交 13:42~13:52 · 分支 master · GitLab：https://gitlab.xx.com/g/lanxum-amisp · commit 1a2b3c/4d5e6f）`），来源为运行时 `git remote get-url origin`（ssh 自动转网页链接）+ `git branch --show-current`
- 备注含文件数、行数变化、实际耗时窗口

## 工时关系

**人工工时 = 等效产出**，不是日历时间。AI 辅助下一个人一天可产出远超 8h 的工作量。必须标注实际耗时窗口（如 `⏱️ 16:27~16:40（约 13min）`），让读者知道这是 AI 压缩后的产出。

## 安装

```bash
git clone https://github.com/huzhw/daily-record-gitlab-md-skill.git ~/.claude/skills/daily-record-gitlab-md
```

安装后在 AI 编码助手里说「补充日报」即可触发。

## 许可

MIT