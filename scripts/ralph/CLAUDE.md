# Ralph 循环 · 每轮实例指令（TradingRadar）

你是 Ralph 循环每一轮拉起的**单个 agent**。每轮上下文可能是新的，
必须依靠 `scripts/ralph/prd.json`、`scripts/ralph/progress.txt`、OpenSpec 和 Git 状态接力。

每轮你**独自**把一个 user story 从头走到尾：选 story → 实现 → 自动化验证 → 契约/浏览器验证 → 审查 → 回写状态 → 单独提交。下面的「阶段」是你一轮内顺序经过的工序，不是别的 agent——你既写代码也跑验证，所以更要靠客观证据（可照跑命令的输出）自我约束，不许放水标 `passes:true`。

> 规划与收尾在循环外、主会话进行：`pm` 子 agent 负责 OpenSpec 产规格 → `prd.json`，以及循环结束后的归档收尾。本循环内不调用它、不自己归档。

Ralph 的目标不是“尽快把 passes 改成 true”，而是让一个 user story 从 PRD 进入真实可用状态：

`PRD → 范围确认 → 实现 → 自动化验证 → 集成/浏览器验证 → 审查 → 标记通过 → 提交`

## 重要路径

- 本文件、`prd.json`、`progress.txt` 都在 `scripts/ralph/`。
- 仓库根是：`/Users/maben996/Projects/TradingRadar`。
- 后端在 `backend/`，前端在 `frontend/`。
- OpenSpec 在 `openspec/`；当前变更 = `prd.json` 的 `branchName` 去掉 `ralph/` 前缀，优先读取 `openspec/changes/<change>/`。

## 全局硬规则

- 一轮只推进一个 `passes:false` 且 priority 最高的 user story。
- 禁止重做或修改已经 `passes:true` 的 user story，除非当前用户明确指出该 story 有 bug。
- 禁止只因为 type-check/build 通过就把 UI story 标成 `passes:true`。
- 任何写入 `passes:true` 的 story，必须同时满足：验收标准全部完成、自动化验证通过、集成路径可证明、review 无阻塞问题。
- UI story 如果要求浏览器验证，但当前环境无法启动浏览器/dev server，必须保持 `passes:false`，并在 notes 写明“代码已完成但待人工浏览器验证”。
- 如果用户在体验中发现功能不可用，必须把对应 story 改回 `passes:false`，优先修主流程。
- 提交前必须确认 `git status --short` 中没有混入无关文件；Ralph 脚本自身改动不应混入业务 story commit。
- 只有当 `prd.json` 所有 story 都是 `passes:true`，并且最后一轮输出中单独一行写：
  `<promise>COMPLETE</promise>`。

## 每轮执行流程（一个 agent 顺序走完这些阶段）

一轮只推进**一个** `passes:false` 且 priority 最高的 story。按下列阶段顺序进行；任一阶段判定 `BLOCKED`（规格歧义、前置未完成、无浏览器工具无法验 UI）则停止本 story，按规则记录、不强行标 passes。

### 阶段 1 · 选 story 与圈边界
- 读 `prd.json` 选 `passes:false` 且 priority 最高的一条；读对应 OpenSpec、`progress.txt` 顶部 `## Codebase Patterns`。
- 明确：story id/title、依赖的已完成 story、**本轮允许修改的文件范围**、逐条验收标准清单。不扩大范围。

### 阶段 2 · 勘察现场
- 改代码前先读相关页面/api client/路由/service/model/既有测试，找出真实数据流：前端事件 → api → 路由 → service → DB → 页面刷新。
- 不读现有代码就新增平行实现是禁止的。记下可能失败点（401/422/500、接口返回 added=0、事件被默认行为吞掉、页面未刷新）。

### 阶段 3 · 最小实现
- 只满足本 story 验收标准；严守分层（后端 `api/` 仅入口、逻辑在 `services/`、模型 `models/`、schema `schemas/`；前端 `api/`/`views/`/`components/`/`stores/`/`i18n.ts`）。
- 复用既有函数/服务/组件/类型/样式，不为未来需求提前抽象，不做无关重构。
- UI 必须有成功/失败/空结果三种反馈，不许静默失败；不许只做 UI 假状态不打通后端。

### 阶段 4 · 契约抽查（实现完自己验链路，不能只信 type 通过）
- 前端请求路径是否经 `/api` baseURL 正确拼接；payload 字段与后端 schema 是否一致。
- 后端是否按当前用户过滤；**写入后能否从读取接口查到结果**。
- 发现契约裂缝 → 回阶段 3 修。

### 阶段 5 · 自动化验证（贴真实输出作证据）
- 后端：`cd backend && python -m pytest -q`、`cd backend && ruff check .`
- 前端：`cd frontend && npm run type-check`；UI/跨页面改动还要 `cd frontend && npm run build`
- 覆盖不足先补测试。失败禁止标 passes；“未运行”不得写成“通过”。

### 阶段 6 · 浏览器/人工验收（仅 UI story）
- 有浏览器工具：走真实路径（打开页 → 操作入口 → 提交 → 看 toast/错误 → 切目标页确认数据出现 → 后续按钮动作），记录结果。
- 无浏览器工具或 dev server 起不来：**不得标 passes:true**，在 notes 写 `自动化检查通过；浏览器验收未完成，待人工验证：<具体路径>`，本 story 维持 `passes:false`。
- 不得用“代码审查通过”替代浏览器验收。

### 阶段 7 · 审查
对照 PRD/OpenSpec/验收标准复查 diff：有无静默失败、只改 UI 没打通后端、写入读不到、过早标记、无关文件混入、误改已完成 story。有阻塞问题 → 回前面阶段修。

### 阶段 8 · 回写状态与日志
- 满足阶段 5/6/7 且无阻塞，才把该 story `passes` 改为 `true`，并在 `notes` 记验证方式（实际命令 + 结果摘要）。硬条件见「全局硬规则」。
- 追加 `progress.txt` 本轮记录（**绝不覆盖**），在顶部 `## Codebase Patterns` 沉淀可复用经验。

### 阶段 9 · 单独提交
- 本 story 单独提交：提交前 `git status --short` + `git diff --stat`，只暂存本 story 相关文件。
- 业务提交信息：`feat: [US-00X] - [标题]`。
- `scripts/ralph/ralph.sh`、`.claude/agents/*`、Ralph 指令/工具配置改动，必须单独用 `chore:` 提交，不混入业务 commit。
- `.git` 无写权限或提交失败，不得声称已提交，须写明“实现已完成但未提交”。

### 阶段 10 · 收口检查
是否所有 story 都 `passes:true`。若是，按「完成标准」输出 COMPLETE，并提示用户回主会话用 `pm` 做 OpenSpec 收尾归档（循环内不自己归档）。

## 进度日志格式

追加到 `scripts/ralph/progress.txt`：

```md
## [日期时间] - [US-00X]
- Scope: 本轮 story 和修改范围
- Implementation: 实现了什么 / 改了哪些文件
- Contract: 请求路径、payload、response、读取路径是否打通
- Tests: 实际运行命令与结果
- Browser QA: 已验证路径；如果未验证，写清楚阻塞原因
- Review: 是否阻塞通过，残余风险
- Commit: commit hash；如果失败，写清失败原因
- **Learnings for future iterations:**
  - 可复用模式、踩坑、架构约束
---
```

## 完成标准

某个 story 完成：
- 所有 acceptanceCriteria 都有证据。
- 自动化验证通过。
- 需要 UI 验证的，浏览器/人工验证完成。
- `prd.json` 对应 story 为 `passes:true`。
- 有单独 commit。

整个 PRD 完成：
- 所有 stories 都 `passes:true`。
- 工作区没有未提交业务改动。
- 最后一轮输出中单独一行：
  `<promise>COMPLETE</promise>`
- 并提示用户：回主会话用 `pm` 做 OpenSpec 收尾（`openspec archive <change>` / `opsx:sync`）。**循环内不自己归档、不自己合并分支**——这些有外部影响的动作交用户在主会话确认执行。
