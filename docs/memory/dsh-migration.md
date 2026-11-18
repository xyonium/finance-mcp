# 从 Claude Code 迁到 DSH

> 2026-11-18。

## 迁移前

项目在 `eli@dockerno1:~/finance-mcp`，由 Claude Code 维护。仓库里其实**没有 `CLAUDE.md`**，常驻信息散在三处：

- `dockerno1:~/.claude/projects/-home-eli-finance-mcp/memory/` —— 5 份项目记忆（配额、FMP 矩阵、发布、futu kwarg、cliproxy 归属）+ `MEMORY.md` 索引
- `dockerno1:~/.claude/CLAUDE.md` —— 工具纪律（firecrawl 代替 WebFetch、codegraph 优先）
- 仓库内 `docs/research/`、`docs/superpowers/`、`.superpowers/sdd/` —— 已有文档，与 Claude 无关

## 迁移后

- 常驻指令：根目录 **`AGENTS.md`**（DSH 会加载 `AGENTS.md`/`CLAUDE.md`，项目链与用户全局链分开预算）。本项目只保留 `AGENTS.md`，**不建 `CLAUDE.md`**，避免两份漂移。
- 记忆：`docs/memory/` + `MEMORY.md` 索引，由 `AGENTS.md` 按域指路。原因：DSH 没有 Claude Code 那种自动 memory 注入，笔记必须显式落库并被指令引用，否则等于没写。
- 工具纪律（firecrawl / codegraph）从 `~/.claude/CLAUDE.md` 搬进 `AGENTS.md` 的「Agent 工具纪律」，不再依赖用户级 Claude 配置。
- 未迁移：`~/.claude/settings.local.json` 的 permissions（Claude 专有机制，DSH 用沙箱与审批）、`~/.claude/` 的 session transcript（无长期价值）。
- `docs/handoff-2026-11-18-kdense-gaps.md` 保留在 `docs/` 原位，是本次接源的立项依据。

## 以后

- 别再引入 `.claude/`、Claude hooks、Claude 专有 settings。
- 新纪律写 `AGENTS.md`；新记忆写 `docs/memory/` 并在 `MEMORY.md` 挂一行。
- 与 `scientific-data-mcp`（2026-11-17 完成同样迁移）保持同一形态，便于跨仓库切换。
