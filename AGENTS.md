# finance-mcp — 维护指南

一个 FastMCP server：把 Yahoo Finance、TradingView、FMP、Alpha Vantage、marketaux、Futu OpenD、CEX 公共 REST、Kimi Datasource 和官方宏观/财政端点收在一个工具面后，按市场自动路由。当前 **23 个 unified 工具 + 53 个 futu 挂载工具**（`grouped` 布局折叠成 30 个）。

本项目由 **DSH 维护**（2026-11-18 从 Claude Code 迁入）。`AGENTS.md` 是唯一常驻指令；`docs/memory/` 是工作记忆，动手前先读 `docs/memory/MEMORY.md`。不再有 `.claude/`、Claude hooks 或 Claude 专有 settings。

## 定位与边界

| 项目 | 管什么 | 不管 |
|------|--------|------|
| **finance-mcp**（本仓库） | 行情 / 财报 / 新闻 / 持仓 / 宏观 / 财政 / 加密永续 / 公司披露（SEC EDGAR） | 科研实体数据、文献检索 |
| `scientific-data-mcp` | 化合物 / 活性 / 蛋白 / 结构 / 文献元数据 | 金融行情 |
| `paper-search` | 找论文 / 读论文 / RAG 入库 | 金融数据 |

K-Dense `database-lookup` 的域归属：经济/金融/监管/社科 14 源归本仓库或 paper-search；本轮只接 SEC EDGAR + World Bank 透传 + US Treasury（见 `docs/memory/kdense-source-intake.md`）。

## 命令

```bash
# 本机沙箱会把 uv 默认缓存挡在 $HOME 外，先指到仓库内
export UV_CACHE_DIR=$PWD/.uv-cache UV_PYTHON_INSTALL_DIR=$PWD/.uv-python
python3 -m venv .venv                     # 或 uv venv --python 3.12 .venv
.venv/bin/pip install -e '.[dev]'         # 或 uv pip install -e '.[dev]' --python .venv/bin/python

.venv/bin/python -m pytest -q -m "not integration"   # hermetic，0 egress
.venv/bin/ruff check .
.venv/bin/unified-finance-mcp                        # stdio（mcpo 用这个）
.venv/bin/unified-finance-mcp --transport http       # + /health
```

live smoke 不进 CI：手工跑，且每个会话最多 1-2 次真实调用（见配额纪律）。

## 架构纪律

- `providers/<source>.py`：URL 构造、分页、字段归一化、错误映射。`tools/<domain>.py`：LLM-facing schema、参数校验、错误包装。
- **两层边界**：provider 抛 `errors.py` 的分类异常；tool 用 `route_and_call` 包住，**永不抛异常**，失败返回 `{"error": ...}`（单源失败折叠进 `source_errors`）。`CancelledError` 不捕。
- HTTP 一律走 `http.PoliteClient`：per-host 限速（`FINANCE_MCP_MIN_HOST_DELAY`，默认 0.5s）、429/503 重试 + `Retry-After`、401/403→`AuthError`、404→`NotFound`。需要自己读错误体时用 `get_response`/`get_text`。
- **反幻觉**：只返回上游真实字段；缺失值保持 `None`/原样，不插值、不补全、不回填；日期保上游拼写。需要溯源的数据带上 `accn`/`filed`/`form`。
- **不加载 `.env`**（无 dotenv 依赖）：key 只按需 `os.environ.get`；无 key 时 provider `available()` 为 False，auto 路由静默跳过；显式 `source=` 时返回"未配置"而不是假装空数据。
- **版本只来自 git tag**（hatch-vcs）：不改 `pyproject.toml` 的 version。
- 新增源必须同步 7 处：`providers/__init__.py`、`tools/__init__.py:ALL_MODULES`、`tools/diagnostics.py`（`UNIFIED_MODULES` + `MODULE_TOOLS`）、`server.py:INSTRUCTIONS`、README（工具表/配置/数据源）、`tests/test_invariants.py` 的工具计数、`docs/CREDENTIALS.md`。**漏一处 = `get_service_status` 与真实工具面 drift**（2026-11-18 修过一次 fred 漏报）。
- **新源优先并入现有工具**（用户 2026-11-18 裁决）：能挂在现有工具上的不要新开工具。先例：SEC EDGAR → `get_sec_filing(kind=filings|facts)`；World Bank / US Treasury → `get_economic_data` 的第三种词表。新增工具要先说明为什么现有容器装不下。
- 市场门控：provider 用 `markets=` 声明覆盖域（`None` = 全球）；`route_and_call` 按 `market` 过滤候选，再按 chain 顺序取第一个非空。

## 数据源与 key

免 key：Yahoo、TradingView、Eastmoney、CEX 公共 REST、World Bank、IMF、US Treasury、**SEC EDGAR**（只要求声明 UA）。

需 key（全部免费档）：`FRED_API_KEY`（120 req/min）、`FMP_API_KEY`、`ALPHAVANTAGE_API_KEY`（免费档约 25 次/日，自动化测试一律 mock）、`MARKETAUX_API_TOKEN`、Kimi（proxy / token / auth-file 三选一）。

- **SEC EDGAR 的坑**：SEC 对"未声明 UA"返回 403 `Undeclared Automated Tool`。仓库共享 UA 含 `github.com`，**必被 403**（2026-11-18 实测）。EDGAR provider 因此自带 UA：`SEC_EDGAR_USER_AGENT`，默认 `unified-finance-mcp`；建议设成 `"unified-finance-mcp your@email"`。SEC 站点级上限 10 req/s，PoliteClient 的 0.5s 节奏 = 2 req/s。
- `get_sec_filing` 用 `companyconcept`（2–50 KB/tag，随概念点数增长）而不是 `companyfacts`（AAPL 3.8 MB），**永远不要**把整包 companyfacts 返回给模型。
- Treasury 曲线用 `home.treasury.gov` 的 CSV 导出（`_format=csv`），不是 XML feed；Fiscal Data 是另一个 host 的 JSON API。`monthly_treasury_statement` 端点已 404，正确入口是 `/v1/accounting/mts/mts_table_N`。

## 测试纪律

- respx hermetic：所有 provider 测试 mock 上游，URL 从 `config.DEFAULT_*` 拼，**零 egress**。诊断测试还会把 `socket.getaddrinfo` 换成失败断言。
- `tests/test_invariants.py` 钉死 unified 工具面（名称 + 精确数量）；`tests/test_diagnostics.py` 钉同一个数量。两者必须一致。
- 改 docstring / 工具描述时保留"不补全、不推断"的措辞——这是给模型的硬约束。

## 发布与部署

- `pyproject.toml` 里 `dynamic = ["version"]` + `[tool.hatch.version] source = "vcs"`；`publish.yml` 由 `v*` tag 触发。**不要手改 version**（硬编码 + 打 tag = PyPI 静默丢包，2026-09-11 踩过）。
- mcpo 用 `uvx --refresh --from unified-finance-mcp unified-finance-mcp`，冷启动即拉 PyPI 最新；容器内热更新需 `pip install --index-url https://pypi.org/simple --no-cache-dir`。
- `FINANCE_MCP_FUTU_MOUNT_LAYOUT=grouped` 时 mcpo `/finance/openapi.json` 是 **30 paths**（23 unified + 7 futu 容器）。改工具面后要同步这个数字与 mcpo 验收。
- 部署机：`eli@dockerno1:~/finance-mcp`；远端 `origin` = `github.com/xyonium/finance-mcp`。

## 记忆

`docs/memory/MEMORY.md` 是索引；改某个域之前先读对应笔记：

- 改 key / 环境变量 / 配额 → `finance-mcp-env-and-quotas.md` + `docs/CREDENTIALS.md`
- 改 FMP / news 回退 → `fmp-free-tier-endpoints.md`
- 改发布 / 版本 → `publish-pipeline-hatch-vcs.md`
- 改 futu wrapper / kwarg → `futu-wrapper-kwarg-mapping.md`
- 改 kimi / cliproxy 链路 → `cliproxy-kimi-tools-ownership.md`
- 改宏观/财政/EDGAR 源或再做 K-Dense 缺口 → `kdense-source-intake.md`
- 迁移背景 / DSH 形态 → `dsh-migration.md`

## Agent 工具纪律

- 取网页/搜索走 firecrawl（`firecrawl_scrape` / `firecrawl_search`），不用原生 WebFetch。
- 仓库根有 `.codegraph/` 时先用 codegraph，再 grep/read。
- DSH 只自动加载 `AGENTS.md` / `CLAUDE.md`（项目 + 全局）；新纪律写这里，新记忆写 `docs/memory/` 并在索引挂一行。别再引入 `.claude/` 依赖。
