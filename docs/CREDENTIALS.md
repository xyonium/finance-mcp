# 配置与 API key 获取指南

先说结论：**9 个数据源免 key，什么都不配也能用**（Yahoo、TradingView、Eastmoney、CEX 公共 REST、World Bank、IMF、US Treasury、SEC EDGAR、BLS）。剩下的 key 全部是免费档；没有付费才能用的能力。

唯一"像 key 但不是 key"的门槛是 **SEC EDGAR 的声明式 User-Agent**：SEC 对未声明 UA 返回 403，共享 UA 里含 `github.com` 必被拦（2026-11-18 实测）。配一个环境变量即可。

> 配好后把值写进你的配置处：
> - **mcpo**：`config.json` 的 `mcpServers.finance.env` 块
> - **Docker / compose**：`environment:` 或 `--env-file`
> - **本地 / uvx**：shell 环境变量（本服务**不读 `.env`**，没有 dotenv 依赖）

---

## 第 0 级 · 推荐（免费，1 分钟）

### 1. SEC EDGAR 的 User-Agent（`SEC_EDGAR_USER_AGENT`）

不是 key，是 SEC 的公平访问要求：

```bash
export SEC_EDGAR_USER_AGENT="unified-finance-mcp your@email"
```

- 不配也有默认值 `unified-finance-mcp`（能通），但 SEC 政策希望带联系方式；带邮箱最稳。
- **不要**在 UA 里放 `github.com`：实测同一 IP 下 `unified-finance-mcp/0.1 (+https://github.com/…)` → 403，`(+https://example.com)` → 200。
- 站点级 10 req/s；本服务 per-host 0.5s 节奏 = 2 req/s，天然安全。
- 验证：`get_sec_filing("AAPL", kind="filings", limit=3)` 返回最近 10-K。

### 2. FRED（`FRED_API_KEY`）

免费注册 5 分钟，120 req/min；解锁 `get_fred_series` / `search_fred_series` 与 8 个 canonical 指标的月/季度序列（GDP 季度；CPI/UNRATE/DGS10 月度）。

1. 打开 <https://fredaccount.stlouisfed.org/apikeys> 注册并登录
2. **Request API Key** → 填用途 → 复制 32 位 key
3. `export FRED_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4. 验证：`get_fred_series("DGS10", limit=5)`

ToS：this product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.

### 3. BLS（US 代理优先 / Jina Reader 兜底，免 key）

`api.bls.gov` 对**默认伦敦出口**返回 403，但**美国出口 200**（实测：`129.146.247.77` Phoenix）。BLS 是我们的 CPI / UNEMPLOYMENT / NONFARM_PAYROLL 月度备份（FRED 没配 key 时生效），两条免 key 通道：

1. **推荐**：`BLS_PROXY_URL=http://<us-proxy>:<port>` —— 只给 BLS 走这个代理，其它 provider 不受影响。
2. 没有代理时自动走 `r.jina.ai`（`JINA_READER_URL`，keyless ~20 RPM）。可选 `JINA_API_KEY`（<https://jina.ai/keys/>，免费月度配额）提到 500 RPM。

两条都**不需要 BLS key**。注意 BLS keyless GET 是 v1 单序列接口，适合备份而非高频主路径；停用 reader 用 `JINA_READER_URL=`。

### 4. Kimi Datasource（三选一）

`KIMI_PROXY_URL`（推荐，CLIProxyAPI 插件注入凭据）→ `KIMI_ACCESS_TOKEN` → `KIMI_AUTH_FILE`。详见 README 的 Kimi 小节；`get_service_status` 会报 `auth.source`（只报结构，不报值）。

---

## 第 1 级 · 可选（免费档很紧或需商用 key）

| 变量 | 申请 | 免费档注意 |
|---|---|---|
| `ALPHAVANTAGE_API_KEY` | <https://www.alphavantage.co/support/#api-key> | 日配额约 **25 次**：自动化测试一律 mock，live 每次会话最多 1-2 次 |
| `FMP_API_KEY` | <https://site.financialmodelingprep.com/register> | 免费档 news 类端点整类 402（订阅锁），见 `memory/fmp-free-tier-endpoints.md` |
| `MARKETAUX_API_TOKEN` | <https://www.marketaux.com/register> | 免费档有每日条数上限；`get_news` 第三顺位 |

三家都支持 `*_BASE_URL` 指向自己的 key 轮替器（例如 `http://api-key-rotator:8788/fmp`），此时**不要**再设 key。

---

## 第 2 级 · 暂缓接入的需 key 源（先给入口，避免以后重复调研）

本轮评估过但**没有接入**（理由见 `memory/kdense-source-intake.md`）。真要接时按 FRED 形态：无 key 静默跳过、`AuthError` 带注册 URL、README/本表补一行。

| 源 | key | 免费额度 | 注册 |
|---|---|---|---|
| BEA | 36 位 UserID | 100 req/min、100 MB/min；429 + Retry-After | <https://apps.bea.gov/api/signup/>（禁止一次性邮箱） |
| ~~BLS API v2~~ | **已不需要**：CPI/UNRATE/PAYEMS 已用 Jina Reader 免 key 覆盖 | 仅 JOLTS/OES 细分仍缺（暂无计划） | — |
| US Census | 必须（2026-05 起所有查询强制） | 单查询 ≤50 变量；每日数值配额现行文档未公布 | <https://www.census.gov/data/developers/api-key.html> |
| Data Commons | 必须（v2 起强制） | 自助 key 免费、官方称无配额上限（未公布数值） | <https://apikeys.datacommons.org> |

---

## 安全卫生（改代码时别破坏）

- `errors.scrub(text, *secrets)`：错误信息里出现 key/token 值一律替换成 `***`；`get_service_status` 只报结构标签（`key: set|missing|rotated-upstream`、`auth.source`），**永不输出值**。
- key 通过 query param 传递时（FRED/AV/FMP），日志与异常只带 host，不带完整 URL。
- `providers/*` 不读 `.env`，也不做"配置文件发现"；所有配置只有 `Settings` 一条路径。

## 验证

```bash
.venv/bin/python -m pytest -q -m "not integration"   # hermetic，不需要任何 key
.venv/bin/python -c "from unified_finance_mcp.providers import build_providers; from unified_finance_mcp.config import get_settings; print(sorted(build_providers(get_settings())))"
```

`get_service_status`（工具）会列出每个 provider 的 `available` / `covers` / `key`，是线上最快的自检入口。
