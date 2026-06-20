# Codex Command: build-feature

这是 `.codex/workflows/build-feature.md` 的命令入口别名。

当用户说“用 Codex build-feature 开发”或“按 `scripts/codex/prd.json` 推进”时，主 agent 应读取：

1. `.codex/workflows/build-feature.md`
2. `.codex/agents/orchestrator.md`
3. `.codex/agents/rd.md`
4. `.codex/agents/qa.md`

然后按 workflow 执行。
