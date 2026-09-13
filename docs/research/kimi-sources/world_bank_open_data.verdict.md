# world_bank_open_data 裁决：摘

**裁决：摘**（从 kimi KNOWN_SOURCES 移除；官方 World Bank REST 完全免费免 key，数据同源且更新，kimi 包装无独有价值）。

## 1. kimi 侧现状（2 个 API + 路由事实）

kimi world_bank_open_data 源仅暴露 2 个 API（见同目录 `world_bank_open_data.md` describe dump）：

- `world_bank_open_data`：按指标代码取数（country=ISO3/all/list、indicator=WDI 代码、date_range/most_recent、language=zh/en），CSV 落盘。
- `world_bank_search_indicators`：按关键词搜指标代码（纯搜索，不取数）。

**当前经它路由的宏观指标**（`src/unified_finance_mcp/tools/kimi.py` `KIMI_MACRO_VALUES`）：

| unified indicator | 映射值 | 是否 WB 指标 |
|---|---|---|
| GDP | NY.GDP.MKTP.CD | 是 |
| CPI | FP.CPI.TOTL | 是 |
| INFLATION | FP.CPI.TOTL.ZG | 是 |
| UNEMPLOYMENT | SL.UEM.TOTL.ZS | 是 |
| FEDERAL_FUNDS_RATE | FEDFUNDS | 否（FRED 代码，WB 无此序列） |
| TREASURY_YIELD_10Y | DGS10 | 否（FRED 代码） |
| RETAIL_SALES | RSXFS | 否（FRED 代码） |
| NONFARM_PAYROLL | PAYEMS | 否（FRED 代码） |

即 8 个宏观指标里 4 个（利率/国债/零售/非农）本来就不可能由 WB 提供，实际只 GDP/CPI/INFLATION/UNEMPLOYMENT 与 WB 有关。

### 路由其实是死代码（重要旁证）

`KimiProvider.economic()`（providers/kimi.py:421）按 `KIMI_MACRO_CANDIDATES` 逐个 probe，其中 WB 两条：

```python
("world_bank_open_data", "get_world_bank_series", "series"),
("world_bank_open_data", "get_indicator_data", "indicator"),
```

但 `economic()` 的护栏是 `doc = await self.describe(source); if api not in doc: continue` —— 而 describe 文档里只有 `world_bank_open_data` 和 `world_bank_search_indicators` 两个 api 名，**`get_world_bank_series` 与 `get_indicator_data` 均不存在于文档**，两条 WB 候选必然 `continue`，最终 `NotFound` 回退 alphavantage。即使 api 名侥幸匹配，`call(source, api, {param: value})` 也只传了 `series`/`indicator` 一个参数，缺真实 API 必填的 `country`（macro.py 以 market="US" 路由，但 country 从未下传）。**结论：今天没有任何指标真正经 kimi WB 出数；它是从未生效的一等公民。**

## 2. 官方 World Bank REST 实测（免 key，2026-09-13）

一次 live httpx GET（无任何鉴权头）：

```
GET https://api.worldbank.org/v2/country/USA;CHN/indicator/NY.GDP.MKTP.CD
    ?format=json&date=2020:2023&per_page=10
HTTP 200
top-level: list len 2
[0] meta: {"page": 1, "pages": 1, "per_page": 10, "total": 8,
          "sourceid": "2", "lastupdated": "2026-07-13"}
CHN 2023 18270356654533.2     USA 2023 27811517000000
CHN 2022 18316765021690.2     USA 2022 26054614000000
CHN 2021 18201698719564      USA 2021 23725645000000
CHN 2020 14996414166715.1    USA 2020 21375281000000
```

要点：

- **免 key、无鉴权头、HTTP 200**；双国家（USA;CHN 分号语法）一次取回。
- JSON 形状干净：`[meta, rows]`，row 含 `countryiso3code/date/value`，无需 CSV 预览再 `_parse_macro_preview` 松解析。
- `lastupdated 2026-07-13`（两个月前），数据新鲜。
- 其余 3 个 WB 代码（FP.CPI.TOTL / FP.CPI.TOTL.ZG / SL.UEM.TOTL.ZS）走同一 `/v2/country/{iso3}/indicator/{code}` 端点模式，均为标准 WDI 代码。
- 指标搜索（替代 `world_bank_search_indicators`）：`/v2/indicator?format=json` 全量指标清单 + `/v2/indicator/{code}` 单查，同样免 key。

## 3. 对比与裁决理由

| 维度 | kimi world_bank_open_data | 官方 api.worldbank.org |
|---|---|---|
| 数据本体 | 同一 WDI 库（kimi 描述即世行平台文案） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 | 免 key、零成本 |
| 输出 | CSV 预览 + 落盘文件（需松解析） | 干净 JSON |
| 语言 | language=zh（标签中文化） | 英文标签（数值无差异） |
| 接入 | describe/doc-check 两跳 | 直接 REST |

kimi 唯一"加分项"是 `language=zh`（元数据中文化）与 CSV 落盘——对 GDP/CPI 这类数值序列均非数据缺口，不构成保留理由。按 kimi-dedup 判据"免费覆盖 ≥ 90% 且公开免 key API 存在 → 摘"。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`KNOWN_SOURCES` 移除 `"world_bank_open_data"`；`economic()` docstring 去掉 world_bank 提法。
- `src/unified_finance_mcp/tools/kimi.py`：`KIMI_MACRO_CANDIDATES` 删 WB 两条（本就永不匹配）；`KIMI_MACRO_VALUES` 中 WB 4 项与 FRED 4 项随之失去 kimi 路由意义，macro chain 退化为 alphavantage 直连（或未来接官方 WB REST 作一等 provider）。
- `tests/test_provider_kimi.py:618`：`assert "world_bank_open_data" in kimi.KNOWN_SOURCES` 需同步删除。
