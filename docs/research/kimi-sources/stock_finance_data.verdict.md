# stock_finance_data 裁决（kimi-dedup R1）

- 评估日期：2026-09-13
- 描述文档：`docs/research/kimi-sources/stock_finance_data.md`（13,668 B，实际含 **9** 个 API，任务书说 8 个——doc 里 `get_stock_financial_index` 是第 9 个）
- 现有 repo provider：`yahoo.py`（A/HK/US 通吃 quote/history/三表/company_info）、`tradingview.py`（TA 指标+screener）、`futu_bridge.py`、`cex.py`。**无任何 CN 专属 provider**（pyproject 无 akshare/tushare 依赖，import 均失败——akshare/tushare 均为"需新依赖"）。
- 免费验证方式：直接 httpx 打东方财富（push2 / push2his / emweb F10 / datacenter）、新浪 hq、巨潮 cninfo —— 全部免 key、无登录。

## API ↔ 免费替代映射表

| # | kimi API | 覆盖内容 | 免费替代 | 实测证据（本机 2026-09-13） | 等质度 |
|---|----------|---------|---------|--------------------------|--------|
| 1 | `get_stock_realtime_price` | A/HK/US 实时价+涨跌+量额（realtime_price）；A股实时技术指标 realtime_tech（MA/EXPMA/SAR/BOLL/BBI/RSI/KDJ/MACD/DMI/BIAS/WR/CCI/ROC/LB/ATR） | 新浪 `hq.sinajs.cn/list=sh601126,hk00700,gb_aapl`（三市场实时全免 key）；EM `push2.eastmoney.com/api/qt/stock/get`；repo 已有 `get_technical_indicators`（TV：RSI/MACD/SMA/EMA/BBANDS/STOCH/ATR，CN 在 TV 支持列表）；KDJ/DMI/BIAS 等可由免费 kline 本地算 | sina 实测：sh601126 四方股份 41.42/-0.66%、hk00700 腾讯 419.40/+0.658%、gb_aapl 苹果 332.27/+1.75 三条全 200；EM push2 实测 601126 价/涨跌/量/总市值 200（后被 EM 限流，见下方注） | **≈95%**（realtime_tech 指标集更全，但全部可从免费 kline 推导，且 TV 已覆盖常用集） |
| 2 | `get_price` | 历史价（股票/指数/商品），D/W/M/Q/Y，前/后复权，最长 3 年，最多 3 codes | EM `push2his.eastmoney.com/api/qt/stock/kline/get`：`klt=101/102/103`（日/周/月）、`fqt=0/1/2`（不复权/前/后复权）；US/HK 走 repo 已有 yahoo `history` | 实测 600223.SH 前复权日线 2024-01-02→2026-09-11 共 **654 行**含开高低收量额振幅；指数（1.000001）、商品 SHG（118.AU9999）同端点模式（商品那次赶上 EM 限流未出数，端点模式为 akshare 同款） | **≈100%**（kimi 自身限 3 年，EM 反而更长） |
| 3 | `get_financial_statements` | 资产负债/利润/现金流三表（A/HK/US，任意报告期） | EM datacenter `RPT_DMSK_FN_BALANCE` 等（A 股）；HK/US 走 repo 已有 yahoo `financial_report`（income/balance/cashflow 全实现） | 实测 EM datacenter balance 600223 → 200、54 页数据；repo `yahoo.py:68` `_STMT` 三表齐 | **≈100%** |
| 4 | `get_stock_announcement` | A 股公告（日期/标题/PDF URL） | **巨潮 cninfo 官方** `www.cninfo.com.cn/new/hisAnnouncement/query`（orgId 先查 topSearch） | 实测 600223 2026-08-01~09-13 → **18 条**，含标题+`finalpage/…PDF` 链接，与 kimi 同源级别（cninfo 即法定披露渠道） | **100%**（cninfo 就是公告的一手源） |
| 5 | `get_holder_info` | 股东名/持股数/比例/类型、股东人数变动、机构持仓 | EM F10 `PC_HSF10/ShareholderResearch/PageAjax`：`sdltgd`/`sdgd`（十大流通/十大股东）、`gdrs`（股东户数）、`jgcc`（机构持股）、`jjcg`（基金持股）；US/HK 走 repo 已有 yahoo `ownership`（major/institutional/mutualfund/insider） | 实测 601126 十大流通股东前 3：四方电气集团 3.26 亿股/39.45%、华科恒基 4.63%、香港中央结算 2.32%；接口键位齐全 | **≈100%** |
| 6 | `get_stock_info` | 公司资料（股本/控股股东/实控人/员工/经营范围/主营/官网/可比公司） | EM F10 `PC_HSF10/CompanySurvey/PageAjax`（jbzl：BUSINESS_SCOPE、CHAIRMAN、LEGAL_PERSON、ORG_WEB、EMP_NUM、REG_CAPITAL、ORG_PROFILE…）+ ShareholderResearch（控股股东/实控人）；US/HK 走 repo 已有 yahoo `company_info`（t.info） | 实测 601126 jbzl 全键返回（40+ 字段含经营范围全文、员工数、注册资本、官网）；可比公司列表 kimi 有、EM 无直接字段（行业/同业可由 TV screener 行业筛选替代） | **≈90%**（缺"可比公司"现成字段） |
| 7 | `get_stock_business_segmentation` | 主营构成（按产品/行业/地区的收入、成本、毛利率）——**预期最大 gap，实测免费全给** | EM F10 `PC_HSF10/BusinessAnalysis/PageAjax` 的 `zygcfx` | 实测 601126 → **200 条**主营构成：`二次设备` 收入 34.01 亿/占比 75.89%/毛利率 36.66%、`电力电子` 4.38 亿/9.77%/31.74%…，按 REPORT_DATE 分期，MAINOP_TYPE 分产品/地区 | **100%** |
| 8 | `get_forecast` | A 股业绩预测（净利润、营收及其同比） | EM F10 `PC_HSF10/ProfitForecast/PageAjax`（`jgyc`：机构 EPS1-4/PE1-4 + 近六月平均共识）+ datacenter `RPT_WEB_RESPREDICT`（评级机构数/EPS 共识）；净利润绝对额=EPS×股本可推导，akshare `stock_profit_forecast_em` 同源直出 | 实测 jgyc 601126：近六月平均 2025 EPS 0.995 / 2026 EPS 1.176，机构行齐全；RPT_WEB_RESPREDICT 200（rating_org_num、EPS1-3）。**净利润/营收绝对额未逐字段实测**，属 EM 研报数据集已知内容 | **≈85%**（EPS/评级实测 OK；净利/营收 YoY 需推导或换 akshare 一个函数） |
| 9 | `get_stock_financial_index` | 六大类财务指标体系（资本结构/流动性/效率/盈利/成长/现金覆盖，含 EBITDA 利息保障等） | 无单点免费同构 API；但**全部为三表衍生比率**——输入免费（API 3），计算本地化；akshare `stock_financial_analysis_indicator`（sina）覆盖 ROE/周转/成长等常用项 | 未逐项实测（推导性结论）；EM datacenter 估值/指标数据集（RPT_VALUEANALYSIS_DET 实测 200，PE_TTM/PB/PCF 等 2111 期）覆盖估值面 | **≈75%**（数据全免费，缺的是"成品打包"，需要写一层聚合计算） |

补充：描述里的"intelligent stock screening"没有列任何 API（9 个里无此项），且 repo 已有 TV screener（`screener.py`，CN=china 在 `MARKET_TO_TV_SCREENER`），此项免费侧反而更强。

## 证据与限制说明

1. **EM push2 限流**：连续打 push2 后本机 IP 被 EM 断连（RemoteProtocolError），睡 45s 未恢复——EM 对高频裸 httpx 有 IP 级限流，生产侧需要走 repo 已有的 `PoliteClient`（min_host_delay）+ 失败切 sina hq。**新浪 hq 三市场实时全部 keyless 实测通过**，是 realtime 的可靠兜底。akshare 内部也是同一批端点，同样吃这个限流。
2. **接入成本**：repo 目前零 CN 专属 provider。两条路：(a) 仿 `cex.py` 模式写一个轻量 `eastmoney.py` provider（httpx 直打已验证端点，无需新依赖）；(b) 引 akshare（重依赖：pandas 全家 + py_mini_racer 等，且免费版 tushare 需注册 token、积分制，不算"无 key"）。cninfo 公告、sina 实时、EM F10 三件套加起来估计 ~300-500 LOC。
3. **kimi 侧独有点清点**：(i) 一条调用混查 A/HK/US 三市场并自动合并（方便性，非数据）；(ii) realtime_tech 的 A 股分钟级全指标集（免费可推导）；(iii) financial_index 六类成品打包（免费可推导）；(iv) forecast 净利/营收绝对额（EM 研报集有，需一跳）。——没有一项是"免费拿不到的数据"。
4. **额度收益**：stock_finance_data 是 12 源里最核心的股票行情/财报源，预计调用量最大，摘除收益最高。

## 最终裁决

**摘（有条件：先补轻量 EM/cninfo provider）**

- 数据层面免费等质覆盖 ≈ **93%**（7/9 实测等质或近等质，2/9 数据免费但需聚合计算；加权约 93%）。全部 9 个 API 均有免费落点，无独有数据，符合 dedup 规则"免费覆盖 ≥90% + 公开无 key API"（EM/sina/cninfo 三家已本机实测免 key）。
- 落地顺序建议：摘除前先写 `providers/eastmoney.py`（quote/history/holders/segmentation/forecast 五个面已验证端点）+ cninfo 公告面，yahoo 继续兜 US/HK；realtime_tech 与 financial_index 走"免费 kline/三表 + 本地计算"路线，不追平指标集广度（TV 已覆盖常用指标）。
- 保守替代案（若不想立即写 provider）：**保留-仅gap** —— dispatch 里只留 `get_forecast` + `get_stock_financial_index` 两个细面，其余 7 个 API 从 `_probe_aspect`/工具面裁掉。但鉴于实测 gap 均可推导，首选仍是摘。
