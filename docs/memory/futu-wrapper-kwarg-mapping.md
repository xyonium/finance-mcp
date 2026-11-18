# futu wrapper kwarg 映射纪律

**futu-opend-mcp 的 wrapper → skill 调用约定（易踩）：**

`skill_runner._run_skill_json(fn, *args, output_json=True, **kwargs)` 直接把 kwargs 透传给 `_skill/futuapi/scripts/quote/<name>.py` 的主函数。脚本主函数**没有 `**kwargs` 兜底** → wrapper 只要传一个脚本没有的 kwarg 名，就 `TypeError: <fn>() got an unexpected keyword argument '...'` —— **每个调用路径恒炸**，跟 agent 传什么无关。

**2026-09-12 修复（futu-opend-mcp 0.1.4）**：4 个 wrapper 曾按臆造的通用签名 `(market,date,max_count)`/`name` 传参，脚本真实形参不同：

- `get_economic_calendar`：脚本 `(begin_date, end_date, markets_str, count)`。wrapper 现 `begin_date=date or 今天, end_date=end_date, markets_str=market, count=max_count`
- `get_earnings_calendar`：`market_str=market, begin_date=date`（脚本无 count，max_count 改死参）
- `get_institution_list`：`market_str=market, name_part=name, count=count`
- `get_plate_list`：唯一换名 `count→limit`（其余 market/plate_type/keyword 本就同名）

**排查法**：静态比对 wrapper 的 `_run_skill_json` kwargs 与脚本主函数 AST 形参；**只认 "wrapper 传了脚本没有的 kwarg"**（positional/可选缺省不算）。脚本形参常是 `*_str`/`begin_date`/`limit` 风格，不是 wrapper 那套通用名。**铁律：只改 `tools/` wrapper，绝不碰 vendored `_skill/`**。

**同类防幻觉 docstring（finance-mcp 0.1.5）**：`get_quote`（伪 ticker 如 USOIL，正确 CL=F/USO/BZ=F；per-symbol partial 失败语义）、`get_technical_indicators`（summary 与名单互斥 + AV 合法词表无 ATR + 期货走 tv 源）、`tv_analyze`（必须真实 TV ticker，原油 NYMEX:CL1!，先 search_symbols）。

相关：`publish-pipeline-hatch-vcs.md`
