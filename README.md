# daily-record-gitlab-md — 日报需求记录（GitLab → md）

从 GitLab 提交记录提取**未记进日报的增量**（回看 7 天，跨天自动补记），按计价表 **v2.4** 机械计价评估工时（开发类走五维单价表、文档类走文档单价表、运维/实施类按实测），统一写入**今天日期**的 md 日报表；**全程自动零确认**，写后回复「工时一览表」+每行一条一行式算式供核对（审计明细落盘 md，不进回复）；写完即收工，合并到当月 Excel、导出、发邮件由日报管家（daily-report-panel）自动完成。

> 📖 **规则单一事实源 = [SKILL.md](SKILL.md)**（本 README 只留速览，防两份文档漂移）。
> 版本演进见 [CHANGELOG.md](CHANGELOG.md)；计价细则 / 例算 / 历史废存对照见 [pricing-detail.md](pricing-detail.md)。

## 核心能力（速览）

- **增量汇总（跨天补记 · 默认多仓库）** — `incremental_commits.py` 默认一次扫 `scripts/repos.py` 清单里的全部常跑仓库（当前四仓，不用逐仓切目录），汇总最近 7 天内**本人、且还没记进 md** 的提交：内置 `--author="胡志伟"` 过滤（可覆盖），自动扫窗口月份全部 live md + 日报管家 `已合并\` 分片建已记录集合做差集（多仓共享一份），输出未记录清单 / 已跳过清单 / 文件数 / ±行数（逐 commit numstat 求和）/ 时间窗 / 分支 / GitLab 网页链接 JSON；单仓失败不炸整批；`--repo <别名|路径>` 单扫指定仓（清单外也认）、`--cwd` 保留旧单仓模式；远端名兜底（origin→gitlab→upstream→唯一远端）、URL 凭据自动剥离；`today_commits.py` 保留作「明确只补某一天」兜底
- **写后自检** — `recorded_commits.py` 按「仓库 + 提交id」二元组机械比对（提交id 列按**表头列名**定位，缺列报错），验证写入后 `unrecorded` 为空；传 id 必传仓库名——宁重复、勿漏记
- **智能合并** — 同文件 / 同模块 / 同功能的 commit 合并为一条需求；行内子项按业务链路簇切分、非锚定子项 ×0.6（v1.5 机械规则）
- **机械计价** — 先判三类（开发 / 文档 / 运维实施）；开发类双轴分型（轴 1 类 A~F 定人工数法、轴 2 档①~⑥定压缩比 K）+ 五维单价表固定单价机械相乘，C 类按「接口 / 表」一级锚点计数（v2.1），AI 只数数量不选值
- **AI 辅助工时** — `(人工 − 本人手测) ÷ K + 本人手测`（v2.3 口径；本人手测实测直记不折算）；🈲 不按时间窗口 / 会话数 / 对话轮数推
- **自我校准** — 审计块以 HTML 注释落盘；`calibrate.py` 机械比对公式字段 vs 行内实值输出偏差，同一卡 / 子项 ≥3 次同向偏差才提案调价；K 档校准同走提案制（`--k-samples` 输出每档实测分布）
- **重记 / 重跑** — 用户说「删掉重新记录」时对账 → 删旧行与旧审计块 → 重跑增量差集（更早提交用 `--days` 扩窗）全量重估不留旧数字 → 复跑 `recorded_commits.py` 自检

## 触发词

补充日报、写日报、记录需求、日报总结、今天干了什么

## 相关技能

> 本 skill 写完 md 即收工：合并到当月 Excel、导出、发邮件由日报管家（daily-report-panel）自动完成，无需手动合并步骤。
- [git-commit](https://github.com/huzhw/git-commit-skill)：Git 提交规范
- [reread-rules](https://github.com/huzhw/reread-rules-skill)：重载 CLAUDE.md / AGENTS.md 规则
- [code-check](https://github.com/huzhw/code-check-skill)：增量代码隐患检查
- [deepseek-harness-settings-curator](https://github.com/huzhw/deepseek-harness-settings-curator)：DeepSeek Harness 模型配置梳理
- [deepseek-harness-plugin-doctor](https://github.com/huzhw/deepseek-harness-plugin-doctor)：DeepSeek Harness 插件与升级体检医生
- [agent-config-sync-check](https://github.com/huzhw/agent-config-sync-check)：八端同步守卫：链接/硬链接/README 同步检查与修复
- [coding-rules](https://github.com/huzhw/coding-rules)：编码规则库（独立仓库，非 skill）
- [daily-merge-gitlab-excel](https://github.com/huzhw/daily-merge-gitlab-excel-skill)：日报合并（手动兜底，已由日报管家接管，不推荐）
- [daily-report-panel](https://github.com/huzhw/daily-report-panel)：日报管家（关联仓库，非 skill，自动合并/导出/发件）
- [dev-env-upgrade](https://github.com/huzhw/dev-env-upgrade)：开发环境升级医生：版本体检/最新版查询/安全升级
- [prd](https://github.com/huzhw/prd-skill)：PRD 生成器（一句话需求→结构化需求文档）
- [ralph](https://github.com/huzhw/ralph-skill)：PRD 转 prd.json（Ralph 自主执行格式）

## 安装

```bash
git clone https://github.com/huzhw/daily-record-gitlab-md-skill.git ~/.claude/skills/daily-record-gitlab-md
```

安装后在 AI 编码助手里说「补充日报」即可触发。

## 许可

MIT
