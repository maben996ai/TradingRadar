# Codex Multi-Agent Workflow

本目录定义 TradingRadar 的 Codex 多 agent 工作流。它参考 `.claude/` 的 PM / RD / QA 设计，但使用 Codex 当前可用的 `multi_agent_v1` 子 agent 工具，而不是 Claude 的 `Task` 子 agent。

## 角色

- `agents/pm.md`：产品经理。负责澄清需求、生成 OpenSpec change、转换 `scripts/codex/prd.json`，不写业务代码。
- `agents/orchestrator.md`：主编排。读取 `scripts/codex/prd.json`，按 user story 派发 RD 和 QA，负责集成、提交和汇报。
- `agents/rd.md`：开发。实现单个 story，写必要测试，交付 dev-report，不自判通过。
- `agents/qa.md`：验收。独立跑自动化检查和真实功能验证，写 test-report，只由 QA 判定 PASS / FAIL / BLOCKED。
- `workflows/build-feature.md`：Codex 主编排的标准开发循环。
- `schemas/prd.schema.json`：`scripts/codex/prd.json` 的结构约束。
- `templates/`：PRD、dev-report、test-report、progress 的模板。

## 任务文件

- `scripts/codex/prd.json`：当前功能的唯一任务源，由 PM 生成，由主编排消费，默认不提交。
- `scripts/codex/state.json`：记录 story 对应子 agent 会话，默认不提交。
- `scripts/codex/reports/`：RD / QA 的交付报告目录，报告默认不提交。
- `scripts/codex/progress.md`：跨轮次沉淀的实现进度和 codebase patterns，默认不提交。

## 使用方式

1. 规划阶段：用户要求“用 Codex PM 规划 <功能>”。主 agent 按 `agents/pm.md` 工作，生成 OpenSpec change 和 `scripts/codex/prd.json`。
2. 开发阶段：用户要求“用 Codex build-feature 开发”。主 agent 按 `workflows/build-feature.md` 和 `agents/orchestrator.md` 工作。
3. 收尾阶段：所有 story PASS 后，主 agent提示用户归档 OpenSpec，必要时提交/推送。

## 与 Claude 编排的区别

- Codex 不依赖 Claude `Task(subagent_type)`，而是由主 agent 调 `multi_agent_v1.spawn_agent`，用 prompt 加载对应角色说明。
- Codex 子 agent 没有仓库内固定 agent registry；这些 `.md` 文件是角色契约和提示词源，由主 agent 读取后传给子 agent。
- Worker 并行时必须显式声明写入范围，避免多 agent 修改同一文件。
- 运行态文件放在 `scripts/codex/` 且默认被 `.gitignore` 忽略；工作流本身放在 `.codex/` 并可提交。
- 主 agent 仍对最终集成、冲突解决、验证和提交负责。
