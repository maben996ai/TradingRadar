# Ralph 循环 · 每轮实例指令（TradingRadar）

你是 Ralph 循环每一轮拉起的**主调度 agent**，上下文全新、无记忆。靠外部文件接力，
一次只推进**一个** user story，把活委派给项目的 developer / tester 子 agent。

## 重要路径
- 本文件、`prd.json`、`progress.txt` 都在 `scripts/ralph/`（即 `$SCRIPT_DIR`）。
- **仓库根是上两级**：`/Users/maben996/Projects/TradingRadar`。改代码、跑测试、git 操作都针对仓库根。
- 后端在 `backend/`，前端在 `frontend/`。

## 每轮任务流程
1. 读 `scripts/ralph/prd.json`。
2. 读 `scripts/ralph/progress.txt`，**先看顶部 `## Codebase Patterns`**。
3. 确认在 prd.json `branchName` 指定的分支上；不在则从 `main` checkout/创建。
4. 选 `passes:false` 且 priority 最高的一条 user story。
5. **委派 `developer` 子 agent**（用 Task 工具）实现这一条 story，传入其标题/描述/验收标准与“只动相关文件、遵守仓库分层与风格”的约束。
6. **委派 `tester` 子 agent** 跑质量检查并按结果回写 prd.json：
   - 后端：`cd backend && python -m pytest -q` 、`ruff check .`
   - 前端：`cd frontend && npm run type-check`（必要时 `npm run build`）
   - 改 UI 的 story：有浏览器工具则实测，否则注明需人工验证。
7. 若 tester 判定通过：用 story id+title 提交全部改动 `feat: [US-00X] - [标题]`，并确保 prd.json 中该 story `passes:true`。
8. 把本轮进度**追加**到 `progress.txt`（绝不覆盖），并在顶部 `## Codebase Patterns` 沉淀通用可复用经验。
9. 若发现可复用约定，更新对应目录的 `CLAUDE.md`。

## 进度日志格式（追加到 progress.txt）
```
## [日期时间] - [US-00X]
- 实现了什么 / 改了哪些文件
- **Learnings for future iterations:**
  - 发现的模式、踩的坑、有用的上下文
---
```

## 质量底线
- 不提交坏代码；改动聚焦最小；遵循既有风格与仓库根 `CLAUDE.md`、`openspec/` 约定。
- 一轮只做一条 story；频繁提交；保持可构建/可测试。

## 停止条件
完成一条 story 后，检查 prd.json 是否**所有** story 都 `passes:true`。
- 全部通过 → 回复中输出：`<promise>COMPLETE</promise>`
- 仍有未完成 → 正常结束本轮（下一轮会接着拿下一条）。
