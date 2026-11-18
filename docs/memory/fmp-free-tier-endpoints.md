# FMP 免费档端点矩阵（2026-09 实测）

FMP 免费 key（经 rotator `/fmp` → `financialmodelingprep.com`）2026-09-11 实测：

- ✅ `/stable/quote` 200（以及 provider 在用的 profile / historical-price-eod/light / 各 statement —— 同质基础端点）
- ❌ `/stable/news/stock` **402 "Restricted Endpoint … not available under your current subscription"**（`FmpProvider.news` 打的正是这个）
- ❌ `/stable/news/stock-latest`、`/stable/news/crypto-latest` 同 402
- ⏱️ `/api/v3/stock_news`、`/api/v4/general_news`、`/fmp-articles` 上游 45s+ 挂死（不是换条路径就能救的回退项）

**Why:** 免费档把 news 类端点整类划给付费档；402 明文是订阅不足，**不是** key 失效、不是轮替坏了、也不是打错端点。之前把 FMP 402 归给 "rotator key 无效" 是误诊，rotator agent 的矩阵 + mcpo 内 curl 复测已闭环。

**How to apply:**
- FMP 402 永远先读响应体："Restricted Endpoint" = 功能锁（不用修），其它文案才是配额/key 问题。
- 别给 finance-mcp 加 fmp news 回退路径（v3/v4 挂死，且有损 debug 性）。
- 已修（adc97c0）：`FmpProvider.news` 首行短路 `NotFound`（免费档 news 402 付费锁），零网络；`get_news` auto 即刻落 alphavantage 不白付 402；显式 `source="fmp"` 得干净 not_found。测试 `test_news_short_circuits_free_tier_paywall` 断言 route 未被 hit。
- `SYMBOL_CHAIN=["alphavantage","yahoo","marketaux"]`、`GLOBAL_CHAIN=["marketaux"]`；fmp 由 provider NotFound 自动排除，不再显式列入口。AV 字段最富（summary + per-ticker sentiment）第一，Yahoo 免费第二，marketaux 第三。Yahoo 无 summary/sentiment 且 limit=3 会混入旧闻；Futu `search_news` 有 `view_count` 但只是中文标题快讯、无 summary/sentiment/published，不放进统一 `get_news`。
- 若用户升级 FMP 付费档，`source="fmp"` 立即恢复，无需改码。
- rotator `/fmp` 前缀是 strip 式：BASE 必须写到 `/fmp`，代码自己拼 `/stable/...`；根路径裸打会挂起（非 404）。
- `/mcp?apikey=` 是 FMP 另一款 hosted MCP server 产品，与本项目 REST provider 无关，别混。

相关：`finance-mcp-env-and-quotas.md`
