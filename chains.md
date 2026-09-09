# 链路卡库（chains.md）— 按仓库定数量口径

> 配套 SKILL.md 计价表 **v1.2**。单价全栈统一，**栈差异全在「怎么数数量」**：本文件定义每个仓库评估时的「一项 / 一处」口径、标准触点清单（评估时逐项过，没碰不计）、测试验证典型项与已知坑。
>
> 维护纪律（🔴 与 SKILL「自我校准」一致）：改卡走提案制——AI 只收集偏差信号和提案，**架构师回确认词才改本文件**；每张卡标注实证依据，无实证标「待实证」，首记后必须回填。

---

## 卡 1：中信底稿V5

- 仓库：`workingpaper-v5.5` / `standard_thdg_zxdm` ｜ 曾用中文名（旧版日报参考）：中信底稿v5 / 中信底稿V5
- 技术栈：Java 8 + Spring MVC + MyBatis + 旧 JSP + React（wpcms-react）+ 达梦/MySQL
- 依据：2026-09-05 ~ 09-08 日报实证

**数量口径**

- 新增代码一项 = 一个新类（Controller/Service/Bo/Vo）/ 一组 Mapper+XML / 一个 React 组件三件套（App/main/index.html）/ 一个新 JSP 页面块
- 差异修改一处 = 一个需要单独判断的改动点（用哪个重载、参数来源、有无特殊逻辑）
- vite 构建产物、min 文件不计项数，备注标注

**标准触点清单**（逐项过，没碰不计）

- 后端：Controller（.mvc / 白名单）→ Service → Mapper/.xml
- 前端新页：wpcms-react 源码 + API ts 封装 + v3 JSP 壳页 + module-*.xml 权限白名单
- 前端旧页：JSP + js/ 直接改
- 数据：DDL + Mapper XML
- 全站级批量替换按「机械替换」数处数，不按文件数

**测试验证典型项**：接口回归 5min/个；异步任务构造触发 12min/个；启动验证；日志/库表确认 3min/类

**已知坑**

- mapperLocations 通配须含 `dao/**/*.xml`，域子包 XML 才自动加载（2026-09-08）
- 达梦方言差异；归档/报送双链路行为必须对齐
- diff 统计混入构建产物虚增文件数（2026-09-08：66 文件含 37 构建产物）

---

## 卡 2：智能数据底座（ragflow精简）

- 仓库：`ai_data_infra` ｜ 曾用中文名（旧版日报参考）：智能数据底座（ragflow精简）
- 技术栈：Python（ragflow 精简）+ 容器化发版
- 依据：2026-09-09 日报实证

**数量口径**

- 新增代码一项 = 一个模块函数 / 一个处理段（如归一化排序键）
- 差异修改一处 = 单点修复（异常兜底、排序键替换）

**标准触点清单**

- rag/nlp/* 业务逻辑 → api/ragflow_server.py 入口 / 后台线程 → 容器发版
- 无页面回归，验证以日志与容器状态为主

**测试验证典型项**：AST / 容器 Python3.13 复现验证；发版后容器 healthy 检查；全量日志核对 0 ERROR（3min/类）

**已知坑**

- 后台线程 scoped_session 断连残留 → PendingRollbackError 反复报错（2026-09-09）
- position_int 缺省/扁平/标量/嵌套四形态混排触发 Python3 比较异常（2026-09-09）

---

## 卡 3：档案V6

- 仓库：`lanxum-amisp` / `lanxum-amisp-java` / `lanxum-amisp-react` ｜ 曾用中文名（旧版日报参考）：档案V6
- 技术栈：Java + React + JSP（三仓联动）
- 依据：**待实证**（近期日报无记录）

**数量口径**：暂按卡 6 通用兜底口径，首次记录后按实证回填并走提案确认

**标准触点清单**（暂定骨架）：Java 后端链路 / React 页面 / JSP 接入 / 权限白名单

**测试验证典型项**：按卡 6 通用兜底

**已知坑**：待积累

---

## 卡 4：intelliauditflow（+web）

- 仓库：`intelliauditflow` / `intelliauditflow-web` ｜ 曾用中文名：无（仓库列直用原名）
- 技术栈：Java（原生 SqlSessionFactoryBean，非 MyBatis-Plus 全家桶配置）+ 达梦 + React（antd 5.5.0）
- 依据：2026-09-06 日报实证

**数量口径**：同卡 1（Java 类 / React 组件），前端按页面/组件数

**标准触点清单**

- 后端：entity/mapper/XML → service → controller（/lanxum-intelli/customer/*）
- 前端：src/pages/customer 页面 + 菜单路由
- 数据：MySQL + 达梦双库建表 / 存量回填

**已知坑**

- 原生 SqlSessionFactoryBean 下 MP 内置语句不注入 → XML 手写 selectCount/deleteById（2026-09-06）
- 达梦列名大写 + 工程无驼峰转换配置 → resultType 自动映射失效查询全空，select 必须挂 resultMap 显式映射（2026-09-06）
- antd 5.5.0 无 customCell API → 合并行用 onCell 实现（2026-09-06）

---

## 卡 5：日报面板

- 仓库：`daily-report-panel` ｜ 曾用中文名（旧版日报参考）：日报面板
- 技术栈：Node 22 + Fastify 5（ESM）+ Vue 3 + Naive UI + MySQL（daily_panel@13306）+ Tauri 桌面壳
- 依据：daily-report-panel 项目 AGENTS.md 规则

**数量口径**：一项 = 一个 service 能力文件 / 一个 route 组 / 一个 Vue 视图或组件

**标准触点清单**

- 后端：server/src/routes/api.js + services/*（一文件一能力）
- 业务参数三源同步：可改 → sys_cfg SCHEMA + default.json + 代码读取点；不可改 → services/sysconst.js
- 前端：web/src/views/* + api.js；vite build 产物免重启
- 数据：CREATE TABLE IF NOT EXISTS 自举 + docs/init.sql 登记

**测试验证典型项**：改后端必须 `nssm restart daily-report-panel` 后 curl /api/health；查 server/data/panel.log；前端 rebuild 即时生效

**已知坑**

- Fastify 拒绝空 body（POST 发 `{}`）；mysql2 Date 必须字符串化（UTC 错一天坑）；exceljs 日期/百分比要感知 numFmt
- NSSM 托管：改后端不重启不生效，不要手动 node 抢端口

---

## 卡 6：通用兜底（无对应卡的仓库）

- 依据：无——**首记后必须提案转正式卡**

**数量口径**：新增代码一项 = 一个类 / 组件 / 模块级函数；差异修改一处 = 一个独立判断点

**标准触点清单**：后端接口链路 / 前端页面 / 配置与白名单 / DDL（有则计）

**测试验证典型项**：接口回归 + 日志确认

**已知坑**：无——首记时把踩到的坑一并提案入卡
