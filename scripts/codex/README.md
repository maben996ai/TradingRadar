# scripts/codex

Codex 多 agent 工作流的运行态目录。

## 文件

- `prd.json`：当前功能的任务源。由 Codex PM 生成，由主编排读取。该文件不长期保留在模板中；每个功能会覆盖或归档。
- `prd.json.example`：PRD 结构示例。
- `progress.md`：跨轮次进度和 codebase patterns。
- `reports/`：RD / QA 子 agent 的报告目录。

## 推荐流程

1. PM 阶段生成 `openspec/changes/<change>/` 和 `prd.json`。
2. 主编排按 `prd.json` 派发 RD / QA。
3. RD 写 dev-report，QA 写 test-report 并回写 `passes`。
4. 全部通过后，用户确认提交、推送、归档 OpenSpec。
