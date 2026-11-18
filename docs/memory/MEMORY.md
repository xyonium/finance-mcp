# 项目记忆索引

> 从 Claude Code 的 per-project memory 迁移而来（2026-11-18，源：`dockerno1:~/.claude/projects/-home-eli-finance-mcp/memory/`）。
> DSH 不会自动加载 `docs/memory/`，所以这里的笔记由根目录 `AGENTS.md` 显式指路；改对应域之前先读。

- [环境、密钥与配额纪律](finance-mcp-env-and-quotas.md) — .env 现状与注入方式；AV 免费档约 25 次/日，自动化测试一律 mock
- [FMP 免费档端点矩阵](fmp-free-tier-endpoints.md) — news 类端点 402 是订阅锁不是 key 坏；402 先读响应体
- [发布管路 hatch-vcs](publish-pipeline-hatch-vcs.md) — version 只来自 tag；硬编码 version + 打 tag = PyPI 静默丢包
- [futu wrapper kwarg 映射](futu-wrapper-kwarg-mapping.md) — wrapper kwargs 必须等于脚本主函数形参名，否则恒炸
- [cliproxy-kimi-tools 归属](cliproxy-kimi-tools-ownership.md) — 是用户自己的 Go 插件，透明转发，改它零协调成本
- [从 Claude Code 迁到 DSH](dsh-migration.md) — 迁了什么、为什么、以后别引入 `.claude/` 依赖
- [2026-11-18 K-Dense 缺口源裁决](kdense-source-intake.md) — EDGAR / World Bank 透传 / Treasury 曲线入库；BLS 经 Jina Reader 作月度备份；Census、BEA、ECB 等暂缓及理由
