# 环境、密钥与配额纪律

`/home/eli/finance-mcp/.env` 现状（2026-09-09 整理后）：`FMP_BASE_URL=https://financialmodelingprep.com`（=默认值，可删）、`FMP_API_KEY=<key>`、`ALPHAVANTAGE_API_KEY=<key>`。用户原始写法是 key 嵌在官方 URL 末端当第一段路径（`https://host/<KEY>`），由控制器机械拆出——finance-mcp 的 provider 只认标准 query param（`apikey`），且 AV 走 REST `www.alphavantage.co/query`（`mcp.alphavantage.co` 是 AV 官方 MCP 端点，不作 base）。

**Why:** Settings 读 `FMP_API_KEY`/`FMP_BASE_URL`、`ALPHAVANTAGE_API_KEY`/`ALPHAVANTAGE_BASE_URL`。`available()` = `bool(key) or base_url != DEFAULT`，配 key 即视为可用。应用**不加载 .env**（无 dotenv 依赖），本地测试需先 `set -a; . .env; set +a`；Docker 部署由 compose / mcpo `config.json` 注入。若 api-key-rotator 增加 FMP/AV profile，改用 `*_BASE_URL` 指 rotator 且不设 key。

**How to apply:** Alpha Vantage 免费档日配额约 25 次——自动化测试一律 mock，禁止真实 AV 调用；live smoke 每次会话最多 1-2 次且须先声明。FMP 同理从简。

相关：`fmp-free-tier-endpoints.md`、`../CREDENTIALS.md`
