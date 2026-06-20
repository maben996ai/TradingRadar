# Codex Workflow: build-feature

用途：按 `scripts/codex/prd.json` 的 user stories，用 Codex 多 agent 工作流完成开发、验证和收口。

## 触发方式

用户可以在主会话中说：

- “用 Codex build-feature 开发”
- “按 scripts/codex/prd.json 推进”
- “用多 agent 实现这个功能”

主 agent 应读取本文件和 `.codex/agents/orchestrator.md` 后执行。

## 输入

- `scripts/codex/prd.json`
- `scripts/codex/progress.md`
- `scripts/codex/state.json`
- `.codex/agents/rd.md`
- `.codex/agents/qa.md`
- 可选：`.codex/agents/pm.md`

如果 `progress.md` 不存在，从 `.codex/templates/progress.md` 初始化。
如果 `state.json` 不存在，在第一次 spawn RD/QA 时创建。

## 工作流

1. 检查当前分支、工作区和 PRD。
2. 校验 `scripts/codex/prd.json` 结构符合 `.codex/schemas/prd.schema.json`。
3. 选择 priority 最小且 `passes:false` 的 story。
4. Spawn RD worker：
   - 传入 RD 角色说明。
   - 传入 story id 和 PRD 路径。
   - 明确文件 owner。
   - 记录 `storyId -> rdAgentId` 到 `state.json`。
5. 等 RD 返回 dev-report。
6. Spawn QA worker：
   - 传入 QA 角色说明。
   - 传入 story id、PRD 路径、dev-report 路径。
   - 记录 `storyId -> qaAgentId` 到 `state.json`。
7. QA PASS 则继续下一 story。
8. QA FAIL 则 resume 同一个 RD 修复，再 resume 同一个 QA 复验，最多 3 轮。
9. 全部完成后跑全量验证，汇报结果。

## 状态约定

- RD：`READY_FOR_TEST` / `BLOCKED`
- QA：`PASS` / `FAIL` / `BLOCKED`
- 主编排：`COMPLETE` / `PARTIAL` / `BLOCKED`

## 并行策略

默认逐个 story。只有在依赖独立、写入范围不重叠时才并行 spawn 多个 worker。

适合并行：

- 多个 explorer 分别梳理后端/前端影响面。
- 两个互不依赖且不共享文件的实现 story。

不适合并行：

- 同时修改同一个 schema/API contract。
- 一个 story 依赖另一个 story 的数据结构或 API。

## 注意

- 不复制大段报告正文，只传文件路径。
- 不让多个 worker 写同一文件。
- 不自动归档 OpenSpec。
- 不自动提交，除非用户明确要求。
- 提交时不混入 `scripts/codex` 运行态报告；工作流文件用单独 `chore:` 提交。
