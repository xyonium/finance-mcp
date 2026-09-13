# yahoo_finance 裁决（kimi-dedup #2）

**结论：摘。** 9 个 kimi API 全部由 repo 自有 `providers/yahoo.py`（yfinance，免 key、无额度）覆盖，其中 8 个已直连现有 MCP 工具，唯一子缺口 `upgrades_downgrades` 在同一 yfinance 库里原生存在（只是未接线，约 5 行改动），不构成保留理由。

## 1. 九个 API 逐项映射（kimi → 自有 yahoo.py）

| # | kimi API | 自有 provider 方法 | 暴露的 MCP 工具 | 覆盖判定 |
|---|----------|-------------------|-----------------|---------|
| 1 | `get_historical_stock_prices`（period/start_end/interval） | `history(interval, start, end)` | `get_history`（链 futu→yahoo→fmp→AV） | 完全覆盖，且**更好**：无 kimi 的 2 年上限（yfinance 可取 max）、无 1m/1h 区间限制 |
| 2 | `get_stock_info`（价格/公司/财务指标/分析师覆盖等大杂烩） | `company_info()`（`t.info` 全量 dict）+ `quote()` + `short_interest()`（同读 `t.info`） | `get_company_info`（INFO_CHAIN yahoo 首位） | 完全覆盖（JSON 结构化 > kimi 的 CSV 文件） |
| 3 | `get_yahoo_finance_news` | `news()`（兼容 yfinance ≥1.0 nested content 与旧版 flat 两种形态） | `get_news`（链 AV→yahoo→marketaux） | 完全覆盖 |
| 4 | `get_stock_actions`（分红+拆股） | `dividend_split_history()`（dividends+splits+calendar 下次事件） | `get_symbol_intel(kind="dividends")` | 完全覆盖且超出（附下次分红/财报日与 EPS 预估） |
| 5 | `get_financial_statement`（income/balance/cashflow × annual/quarterly = 6 组合） | `financial_report(statement, period)`，`_STMT` × freq=yearly/quarterly | `get_financial_report` | 完全覆盖（6/6 组合齐；yfinance 默认窗口即 kimi 所述"4 年年报+4 季季报"） |
| 6 | `get_holder_info`（major/institutional/mutualfund/insider_transactions/insider_purchases/insider_roster_holders 6 种） | `ownership(kind)`：major、institutional、mutualfund、insider_transactions、insider_roster + `insider_summary`（从 `t.insider_purchases` 聚合 Net/Purchases/Sales） | `get_ownership`（链 yahoo 首位） | 6/6 覆盖（insider_purchases → insider_summary 单行聚合，语义等价） |
| 7 | `get_option_expiration_dates` | `option_chain()` payload 内 `available_expirations` 字段 | `get_symbol_intel(kind="options")` | 覆盖（到期日列表恒在返回里，不必单列 API） |
| 8 | `get_option_chain`（expiration_date + option_type calls/puts 二选一） | `option_chain(parsed, expiration)`：calls+puts **一次全给**，含 strike/IV/OI/Greeks + underlying 报价 | `get_symbol_intel(kind="options", expiration=...)` | 完全覆盖且更好（无需按 option_type 分两次调用） |
| 9 | `get_recommendations`（recommendations / upgrades_downgrades / all，months_back） | `analyst_estimates()`：`recommendations`（`t.recommendations`，前 20 行）+ price_targets + earnings/revenue/growth/EPS 预估 | `get_symbol_intel(kind="analyst")` | **部分覆盖**：recommendations + price targets 齐；`upgrades_downgrades`（升降级事件流 + months_back 窗口）未接线 |

子缺口说明：yfinance 1.7.0（当前 .venv 已装）`Ticker.upgrades_downgrades` 属性**原生存在**，即免费源本身不缺该能力，只是 `providers/yahoo.py` 的 `analyst_estimates()` 尚未把它读出来。跟随任务：在 `fetch_all()` 里加一行 `"upgrades": df_to_records(t.upgrades_downgrades)` 即可 100% 对齐，无需 kimi。

结构差异：kimi 全部 9 个 API 都要 `file_path` 落 CSV 文件；自有 provider 返回结构化 JSON dict，对 MCP 场景严格更优（无磁盘副作用、可直接进上下文）。

## 2. 额度收益

yahoo_finance（历史价/新闻/期权/财报/股东）属于金融类查询的**最高频来源**，摘除后 kimi quota 节省预计为 12 源中最大之一。且 kimi 的 yahoo_finance 与我们走的是同一个 yfinance 上游，保留它纯属重复付费。

## 3. 自有 provider 可用性验证（2026-09-13，hermetic，未打 live API）

- `pytest tests/test_provider_yahoo.py` → **32 passed**（quote/history/company_info/financial_report/news/ownership/search/option_chain/short_interest/analyst_estimates/insider_summary/dividend_split_history/earnings_history 全测）。
- `pytest tests/test_tools_intel.py tests/test_tools_fundamentals.py tests/test_tools_quote.py tests/test_tools_news.py` → **26 passed**（工具层路由链含 yahoo）。
- 进程内冒烟：`build_providers(get_settings())['yahoo']` + mock yfinance Ticker，`quote('AAPL')` 与 `option_chain('AAPL')` 均返回正常 payload；provider 方法清单确认 16 个能力方法在位（quote/history/company_info/financial_report/news/ownership/search/option_chain/short_interest/dividend_split_history/earnings_history/analyst_estimates 等）。

命令（复现）：
```
.venv/bin/python -m pytest tests/test_provider_yahoo.py tests/test_tools_intel.py tests/test_tools_fundamentals.py tests/test_tools_quote.py tests/test_tools_news.py -q   # 58 passed
```

## 4. 裁决

**摘**（免费覆盖 ≥ 90% 且已有直接 provider，符合 kimi-dedup 决策规则第一档）。

- 覆盖率：9/9 数据集在自有 provider 中存在；8.5/9 已直接暴露为 MCP 工具。
- 唯一 gap（upgrades_downgrades 事件流）在同一个免 key yfinance 库里原生可得，接线成本约 1 行 fetch + 测试，应作为 follow-up 而非保留 kimi 的理由。
- 后续动作：从 `KNOWN_SOURCES`（providers/kimi.py）摘除 `yahoo_finance`；顺手在 `analyst_estimates()` 补 `t.upgrades_downgrades`。

证据文件：本文（`docs/research/kimi-sources/yahoo_finance.verdict.md`）；kimi describe 原文 `docs/research/kimi-sources/yahoo_finance.md`；provider 实现 `src/unified_finance_mcp/providers/yahoo.py`。
