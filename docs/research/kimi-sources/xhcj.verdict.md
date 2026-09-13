# xhcj — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/xhcj.md`（describe dump，9 API）vs 免费侧调研（firecrawl）+ kimi 实调内容核验

## 结论

**摘。** xhcj（新华财经/CNFIC）9 个 API 全部是新闻/快讯/公告/政策**资讯检索与快讯流**——无行情数值、无结构化财务数据、无历史库检索。对 finance-mcp 而言：repo 已有 marketaux/fmp（后者免费档 news 已锁）+ 免费快讯生态，新闻流的增量价值为零；而"新华财经签发稿件"（`IfProd=y`）是版权内容，免费侧不可复制，但恰好属于我们**不需要**的域。本源是 R18 8 源中唯一"商业库"性质者，但其独有面（CNFIC 签发资讯）不在本 repo 数据域内，摘除零损失。

## 1. kimi API 分类账（9 API）

| kimi API | 内容 | 免费等质 |
|---|---|---|
| `get_xhcj_hotNews` | 新华财经热点新闻（24h 流） | 财联社/新浪财经/东财快讯（akshare `stock_info_global_*, stock_telegraph_cls`）；**实调返回正文含 sourceUrl 指向 bm.cnfic.com.cn 公开分享页**——正文本身公开可读 |
| `get_newsflash_stock` / `_Commodities` / `_foreign_currency` | 股票/大宗/外汇快讯 | 财联社电报（分股票/大宗/外汇栏目）、金十数据免费流 |
| `search_prodinfo` / `search_prodinfo_stockSector_news` | 成品稿检索（标题/正文/标签/时间） | akshare 东财新闻类 + 站内搜索；CNFIC 独家稿（IfProd=y）除外 |
| `get_AStock_News_byStockName` | 个股资讯 | akshare `stock_news_em`（东财个股新闻，等质） |
| `xhcj-mcp-announce-search` | 公告关键词检索 | cninfo 巨潮公告 API（官方免费，repo 已证）+ 东财公告 |
| `get-las-vector` | 政策关键词查询 | 国务院政策文件库（gov.gov.cn 公开检索）+ 各部委官网；免费侧分散但可得 |

## 2. 实调证据（2026-09-13，kimi 侧）

- `get_xhcj_hotNews begTime/endTime` → **200**，`success:true errorCode:1`，返回 24h 热点新闻数组：`contentID`/`Title`/`publishTime`/`summary`/`publishorg`（新华财经）/`source`（新华社）/`sourceUrl`（bm.cnfic.com.cn 公开分享页）/`contentTxt` 全文。抽验样例为服贸会科技金融报道——资讯流性质确认，无数值行情字段。
- response 走 assistant 通道空文本 + user 通道 JSON（与 caixin B1 同型的嵌套信封；`_extract_call_result` B1 修复已兼容）。

## 3. 对比与裁决理由

| 维度 | kimi xhcj | 免费侧 |
|---|---|---|
| 快讯流 | 3 类（股/大宗/外汇）+ 热点 | 财联社电报/金十/东财（akshare 已封装，等质） |
| 成品稿检索 | CNFIC 签发稿独有 | 独家稿不可替，但为版权资讯非数据，且 repo 无该域路由 |
| 公告检索 | 关键词版 | cninfo 官方免费（等质） |
| 政策检索 | 关键词版 | 政府公开检索（等质） |
| 成本 | 每次 call 消耗 kimi 额度 | 免 key |

- 裁决不是"免费 100% 等质"，而是"独有面（CNFIC 签发稿）落在 repo 数据域之外 + 其余 100% 等质" → 对本 repo 而言摘。
- 若未来需要 CNFIC 签发资讯流，需重新评估（届时走 保留 判定）。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
