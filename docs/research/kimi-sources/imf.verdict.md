# imf 裁决：摘

**裁决：摘**（从 kimi KNOWN_SOURCES 移除；IMF 数据本体免费且官方提供免 key REST，kimi 包装走 cliproxy 耗额度，且其预置指标码绑定的是已停服的旧 API，在本仓库的路由又是从未生效的死代码）。

## 1. kimi 侧现状（11 个 API + 路由事实）

kimi imf 源暴露 11 个 API（见同目录 `imf.md` describe dump），覆盖 10 个数据集 + 1 个指标搜索：

| API | 数据集 | 典型指标 |
|---|---|---|
| imf_ifs_data | IFS（CPI/汇率/利率） | PCPI_IX, ENDE_XDC_USD_RATE, FILR_PA |
| imf_bop_data | BOP（国际收支） | BCA_BP6_USD, BXG_BP6_USD |
| imf_weo_data | WEO（预测） | NGDP_RPCH, PCPIPCH, LUR |
| imf_fsi_data | FSI（银行健康） | FSANL_PT, FSKRTC_PT |
| imf_cofer_data | COFER（储备币种） | AFXRA, TFXRA + CI_USD/SHRO_PT |
| imf_qgfs_data | QGFS（季度财政） | GGR, GGX, GGSB |
| imf_pip_data | PIP（组合投资，原 CPIS） | P_F3_DIC_USD_P_USD |
| imf_dip_data | DIP（直接投资，原 CDIS） | INWD_D_AG_FL_ALL |
| imf_dots_data | DOTS（双边贸易） | TXG_FOB_USD, TMG_CIF_USD |
| imf_irfcl_data | IRFCL（国际储备） | RA_FX, RA_GOLD, RA_TB |
| imf_search_indicators | 指标元搜索 | （纯搜索，不取数） |

### 路由是死代码（与 WB 同款旁证）

`src/unified_finance_mcp/tools/kimi.py:57` 的候选三元组：

```python
("imf", "get_imf_series", "series"),
```

而 `KimiProvider.economic()`（`src/unified_finance_mcp/providers/kimi.py:421`）的护栏是 `doc = await self.describe(source); if api not in doc: continue`。describe 文档（即 imf.md）里只有上表 11 个 `imf_*_data` / `imf_search_indicators` 名字，**`get_imf_series` 不存在**，该候选必然 `continue`。且 `KIMI_MACRO_VALUES` 里 8 个映射值全是 WB/FRED 代码（NY.GDP.MKTP.CD、FEDFUNDS 等），没有一个是 IMF 指标码——即使 api 名侥幸匹配，传过去的也是无效代码。**结论：今天没有任何指标真正经 kimi imf 出数。**

## 2. 官方免费路径实测（免 key，2026-09-13 live）

IMF 官方 API 正在从经典 SDMX 向新平台迁移，三个端点现状：

### 2.1 经典 dataservices.imf.org —— DNS 已死

```
GET https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/A.US.PCPI_IX
ERROR: ConnectError [Errno -2] Name or service not known   （NXDOMAIN，域名已下线）
```

kimi imf 预置的指标码（`PCPI_IX`、`BCA_BP6_USD`、`AFXRA`…）正是这套旧 CompactData 语法——旧端点死了，这套码对新平台并不直接通用（见 §3）。

### 2.2 DataMapper API —— 稳定、免 key、JSON 干净

```
GET https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/USA
HTTP 200 (application/json)
values.NGDP_RPCH.USA: 1980–2031 全序列
  2023=2.9  2024=2.8  2025=2.1  2026=2.3  2027=2.1 … 2031=1.8
source: World Economic Outlook (April 2026)   ← 当前 vintage
GET /NGDP_RPCH/USA/CHN  → 一次多国：CHN 2026=4.4
GET /indicators → 132 个精选指标清单（WEO 15 + Fiscal Monitor 8 + GDD 10 + REO 26 …）
GET /regions → 200
```

多国家一请求可用（`/USA/CHN` 路径语法）；多指标 `+` 语法 403，不支持。

### 2.3 新 api.imf.org SDMX 2.1 —— 免 key 但内容协商挑剔

```
GET https://api.imf.org/external/sdmx/2.1/dataflow/all/all/latest
HTTP 200 → 300+ 个 dataflow（XML）
GET …/data/IMF.RES,WEO/USA.NGDP_RPCH?startPeriod=2022&endPeriod=2031
     + Accept: application/vnd.sdmx.data+csv;version=2.1.0
HTTP 200 → USA NGDP_RPCH: 2022=2.524  2023=2.935  2024=2.793
            2025=2.117  2026=2.324 … 2031=1.755
            （与 DataMapper 数值一致；PUBLICATION_DATE 2026-04-14，当前 vintage）
GET …/data/IMF.STA,CPI/USA.CPI._T.IX.A?startPeriod=2024
HTTP 200 → 2024=143.857（USA CPI 全项指数，即旧 IFS PCPI_IX 等价物）
```

**关键坑（实测）**：
- 不带 Accept 或带 `generic+xml`/`structurespecific+xml`/`sdmx.data+json` → **500 Internal Server Error**（服务端内容协商坏，持续复现）；
- 只有 `Accept: application/vnd.sdmx.data+csv;version=2.1.0` 稳定 200（且返回体实际是 structure-specific XML 而非 CSV）；
- 偶发 500 需重试（WEO 查询首次重试即过）。

### 2.4 数据集覆盖核对（api.imf.org dataflow 实测清单）

kimi 10 个数据集在新官方 API 的对应：

| kimi 数据集 | api.imf.org dataflow（agency） | 状态 |
|---|---|---|
| WEO | WEO (IMF.RES, v9.0.0) | ✅ 实测出数 |
| BOP | BOP (IMF.STA) | ✅ flow 存在（BOP_2026_*_VINTAGE 月度 vintage 系列） |
| COFER | COFER (IMF.STA) | ✅ flow 存在 |
| QGFS | QGFS (IMF.STA) | ✅ flow 存在 |
| IRFCL | IRFCL (IMF.STA) | ✅ flow 存在 |
| DIP（原 CDIS） | DIP (IMF.STA) | ✅ flow 存在（已随官方改名） |
| PIP（原 CPIS） | PIP (IMF.STA) | ✅ flow 存在（已随官方改名） |
| FSI | FSIC / FSIBSIS (IMF.STA) | ✅ flow 存在（拆分） |
| IFS | 拆分为 CPI/ER/FA/IL/MFS_* 等 | ✅ CPI flow 实测出数（USA.CPI._T.IX.A） |
| DOTS | 无同名 flow；ITG（International Trade in Goods）疑似继任 | ⚠️ 未逐维验证 |

即 ≥9/10 数据集在新官方 API 有免 key 归宿（DOTS→ITG 待验证）。DataMapper 另有 132 个精选指标兜底。

## 3. 字段级对比

| 维度 | kimi imf | 官方免费路径 |
|---|---|---|
| 数据本体 | 同一 IMF 库（kimi 仅是代理） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 耗 kimi 额度 | 免 key、零成本 |
| 指标码体系 | `PCPI_IX`/`BCA_BP6_USD` 旧 CompactData 语法 | 新 SDMX 维度分解（CPI flow 5 维：COUNTRY.INDEX_TYPE.COICOP_1999.TYPE_OF_TRANSFORMATION.FREQ）——**kimi 预置码对旧端点，旧端点已 DNS 死亡，预置码是负债不是资产** |
| 指标搜索 | imf_search_indicators（关键词搜码） | DataMapper `/indicators` 132 个含 label/unit/source；新 SDMX codelist 端点（CL_INDEX_TYPE 等，免 key） |
| 批量取数 | 单指标/单国家每次 call | DataMapper 单指标多国家一请求；多指标不支持（403） |
| 输出 | CSV 预览 + 落盘（需 `_parse_macro_preview` 松解析） | DataMapper 干净 JSON；新 SDMX XML（内容协商挑剔） |
| 时效 | 依赖 kimi 刷新 | DataMapper 已是 WEO April 2026 vintage（预测到 2031）；新 SDMX PUBLICATION_DATE 2026-04-14 |
| WEO/BOP/COFER/GFS 覆盖 | 有 | 有（BOP/COFER/QGFS/IRFCL/DIP/PIP 均为新 API flow） |

kimi 的"加分项"只剩：① 预置指标码免查——但绑定旧语法，正在失效；② 每数据集一个扁平函数签名——但等价于把新 SDMX 的维度拼 key 一次性学会。均不构成数据缺口。

## 4. 裁决理由

按 kimi-dedup 判据"免费覆盖 ≥ 90% 且公开免 key API 存在 → 摘"：

1. **免 key 官方 API 存在且当前**：DataMapper（稳定 JSON，WEO April 2026，USA 1980–2031）+ api.imf.org SDMX 2.1（全量 flow，WEO 实测出数）双通道 live 验证通过。
2. **覆盖 ≥ 90%**：10 个数据集 ≥9 个在新 API 有归宿；缺口仅 DOTS→ITG 一项待验证（若真缺，也该直连官方而非付 kimi 额度）。
3. **本仓库路由本就死代码**：`get_imf_series` 不在 describe 文档、`KIMI_MACRO_VALUES` 无 IMF 码，今天零指标经 kimi imf 出数——摘除无任何功能损失。
4. **kimi 预置码绑定已死端点**：旧 CompactData DNS 已下线，kimi 的指标码体系对新平台不通，保留价值随迁移归零。
5. 唯一实践摩擦是新 SDMX 数据层内容协商挑剔（仅 CSV Accept 稳、偶发 500 需重试）——这是"写官方 provider 时要注意"的实现细节，不是保留 kimi 付费代理的理由。

## 5. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`KNOWN_SOURCES` 移除 `"imf"`；`economic()` docstring 去掉 imf 提法。
- `src/unified_finance_mcp/tools/kimi.py`：`KIMI_MACRO_CANDIDATES` 删 `("imf", "get_imf_series", "series")`（本就永不匹配）。
- `tests/test_provider_kimi.py`：`assert "imf" in kimi.KNOWN_SOURCES` 同步删除。
- 宏观路由：macro chain（`CHAIN = ["kimi", "alphavantage"]`）不受影响——kimi 侧本就靠 WB 候选之外的回退，WB/imf 两族候选全删后 chain 退化为 alphavantage 直连（或未来接 DataMapper 作一等 provider，见 §2.2 证据）。
