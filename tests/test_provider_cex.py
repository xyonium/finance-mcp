"""CexProvider: TV-first (monkeypatched _get_analysis) + bare REST failover.

All REST mocks pin the shapes live-verified 2026-09-13:
- bitget ticker wraps a 1-element list in {"code","data"}; needs symbol+productType
- gate ticker wraps a 1-element list without a wrapper; needs contract param
- mexc ticker is a query-form JSON dict {fundingRate, holdVol, fairPrice, symbol}
- mexc kline is columnar: {"time":[...], "open":[...], ...} zipped client-side
No live exchange/TV calls (respx fences every REST route; _get_analysis is
monkeypatched).
"""
import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, ProviderError, UpstreamError
from unified_finance_mcp.providers.cex import CexProvider, normalize_symbol


def make_provider(monkeypatch, exchanges=("bitget", "gate", "mexc")):
    monkeypatch.setenv("FINANCE_MCP_CEX_EXCHANGES", ",".join(exchanges))
    return CexProvider(get_settings())


def fake_analysis():
    return type("A", (), {"summary": {"RECOMMENDATION": "BUY"},
                          "oscillators": {}, "moving_averages": {},
                          "indicators": {"close": 95.6, "open": 96.5, "high": 96.6,
                                         "low": 95.2, "volume": 81440.0,
                                         "change": -1.0}})()


def test_normalize_symbol_rejects_other_commodities():
    """Brent / nat-gas are different assets: never silently fold them onto WTI."""
    for bad in ("XBR", "XBRUSDT", "NG", "NGUSDT", "UKOIL", "UKOILUSDT"):
        with pytest.raises(NotFound):
            normalize_symbol(bad)


def test_iso_handles_seconds_ms_and_garbage():
    from unified_finance_mcp.providers.cex import _iso
    assert _iso(1789171200) == "2026-09-12T00:00:00+00:00"      # gate/mexc: s
    assert _iso("1789171200000") == "2026-09-12T00:00:00+00:00"  # bitget: ms
    # Out-of-range / non-numeric must not raise out of a kline response.
    assert _iso(1e15) == str(1e15)          # too large to be an epoch: verbatim
    assert _iso("not-a-ts") == "not-a-ts"
    assert _iso(None) == "None"


def test_normalize_symbol_variants():
    assert normalize_symbol("CL") == "CL"
    assert normalize_symbol("CLUSDT") == "CL"
    assert normalize_symbol("CL_USDT") == "CL"
    assert normalize_symbol("OIL_USDT") == "CL"      # 旧 mexc 别名进同一逻辑名
    assert normalize_symbol("USOIL_USDT") == "CL"    # mexc 现 WTI 合约 → CL
    assert normalize_symbol("USOIL") == "CL"          # mexc "OIL(WTI)" 短名 → CL
    assert normalize_symbol("CL/USDT:USDT") == "CL"


@respx.mock
async def test_kline_bitget_ok(monkeypatch):
    respx.get("https://api.bitget.com/api/v2/mix/market/candles").respond(
        200, json={"code": "00000", "msg": "success", "data": [
            ["1789142400000", "97.011", "97.571", "95.221", "95.556", "201097.83",
             "19390959.25"]]})
    p = make_provider(monkeypatch)
    rows = await p.kline("bitget", "CL", interval="1d", limit=1)
    assert rows[0]["close"] == "95.556" and rows[0]["open"] == "97.011"


@respx.mock
async def test_kline_failover_bitget_404_then_gate(monkeypatch):
    """从 bitget 起步:400/404 落 gate.failover 链真实被走过 (review I2)."""
    bitget = respx.get(
        "https://api.bitget.com/api/v2/mix/market/candles").respond(404, json={})
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/candlesticks").respond(
        200, json=[{"t": 1789142400, "o": "97.0", "h": "97.5", "l": "95.2",
                    "c": "95.5", "v": "201097"}])
    p = make_provider(monkeypatch)
    rows = await p.kline("bitget", "CL", interval="1d", limit=1)
    assert bitget.called  # bitget 必须先被打了、失败,failover 才成立
    assert rows[0]["close"] == "95.5"


@respx.mock
async def test_kline_mexc_columnar_body(monkeypatch):
    """MEXC kline 是列式 {"time":[...], "open":[...], ...} (review C2)."""
    respx.get("https://contract.mexc.com/api/v1/contract/kline/USOIL_USDT").respond(
        200, json={"success": True, "code": 0, "data": {
            "time": [1789142400, 1789146000],
            "open": ["97.0", "97.1"], "high": ["97.5", "97.6"],
            "low": ["95.2", "95.3"], "close": ["95.5", "95.6"],
            "vol": ["201097", "190000"]}})
    p = make_provider(monkeypatch, exchanges=("mexc",))
    rows = await p.kline("mexc", "CL", interval="1d", limit=1)
    assert len(rows) == 1 and rows[0]["close"] == "95.6"  # limit 截最新一根


@respx.mock
async def test_kline_mexc_trims_to_limit(monkeypatch):
    """MEXC 忽略 limit,一次返回 ~2000 根;provider 端截 (review M3)."""
    n = 5
    respx.get("https://contract.mexc.com/api/v1/contract/kline/USOIL_USDT").respond(
        200, json={"success": True, "code": 0, "data": {
            "time": list(range(1789142400, 1789142400 + n)),
            "open": ["1"] * n, "high": ["1"] * n, "low": ["1"] * n,
            "close": [str(i) for i in range(n)], "vol": ["1"] * n}})
    p = make_provider(monkeypatch, exchanges=("mexc",))
    rows = await p.kline("mexc", "CL", interval="1d", limit=3)
    assert len(rows) == 3 and rows[-1]["close"] == "4"  # 截的是尾部最新 3 根


async def test_exchange_whitelist(monkeypatch):
    p = make_provider(monkeypatch, exchanges=("bitget",))
    with pytest.raises(NotFound):
        await p.kline("binance", "CL")  # 未启用 → not_found


@respx.mock
async def test_quote_tv(monkeypatch):
    """TV 是主通道;mark 补全走裸 ticker,需要被 respx 围栏 (review I3)."""
    monkeypatch.setattr(
        "unified_finance_mcp.providers.cex._get_analysis",
        lambda exchange, symbol, interval: fake_analysis())
    respx.get("https://api.bitget.com/api/v2/mix/market/ticker").respond(500, json={})
    p = make_provider(monkeypatch)
    q = await p.quote("bitget", "CL")
    assert q["price"] == 95.6 and q["source"] == "cex" and q["mark"] is None


def test_name_and_markets(monkeypatch):
    p = make_provider(monkeypatch)
    assert p.name == "cex" and p.markets == frozenset({"CRYPTO"})


def test_native_symbol_per_exchange():
    """逻辑名 CL 在各家翻成不同原生合约。MEXC WTI 现在是 USOIL_USDT
    (2026-09-13 实测,OIL_USDT 已退市 code 1001)。"""
    from unified_finance_mcp.providers.cex import _NATIVE
    assert _NATIVE["bitget"]["CL"] == "CLUSDT"
    assert _NATIVE["gate"]["CL"] == "CL_USDT"
    assert _NATIVE["mexc"]["CL"] == "USOIL_USDT"


@respx.mock
async def test_quote_tv_symbol_is_dot_p_perp(monkeypatch):
    """TV 通道必须打 CLUSDT.P(USDT 永续),不是现货 CLUSDT (review I3)."""
    seen = {}

    def fake(exchange, symbol, interval):
        seen.update(exchange=exchange, symbol=symbol, interval=interval)
        return fake_analysis()

    monkeypatch.setattr("unified_finance_mcp.providers.cex._get_analysis", fake)
    respx.get("https://api.bitget.com/api/v2/mix/market/ticker").respond(500, json={})
    p = make_provider(monkeypatch)
    await p.quote("bitget", "CL")
    assert seen == {"exchange": "BITGET", "symbol": "CLUSDT.P", "interval": "1d"}


@respx.mock
async def test_quote_mark_from_bare_ticker(monkeypatch):
    """mark 由裸 ticker 补(Bitget markPrice);TV 是主通道。"""
    monkeypatch.setattr("unified_finance_mcp.providers.cex._get_analysis",
                        lambda exchange, symbol, interval: fake_analysis())
    respx.get("https://api.bitget.com/api/v2/mix/market/ticker").respond(
        200, json={"code": "00000", "data": [{"symbol": "CLUSDT", "markPrice": "95.60"}]})
    p = make_provider(monkeypatch)
    q = await p.quote("bitget", "CL")
    assert q["mark"] == "95.60" and q["price"] == 95.6 and q["source"] == "cex"
    assert q["symbol"] == "CL" and q["exchange"] == "bitget"


@respx.mock
async def test_quote_mark_none_when_bare_ticker_fails(monkeypatch):
    """裸 ticker 挂了不许拖垮 quote:mark 为 None,且不顺链 failover。"""
    monkeypatch.setattr("unified_finance_mcp.providers.cex._get_analysis",
                        lambda exchange, symbol, interval: fake_analysis())
    respx.get("https://api.bitget.com/api/v2/mix/market/ticker").respond(500, json={})
    gate = respx.get("https://api.gateio.ws/api/v4/futures/usdt/tickers").respond(
        200, json=[{"contract": "CL_USDT", "mark_price": "1.0"}])
    p = make_provider(monkeypatch)
    q = await p.quote("bitget", "CL")
    assert q["mark"] is None and q["price"] == 95.6
    assert not gate.called  # mark 是 best-effort,不触发跨所 failover


async def test_quote_tv_failure_is_provider_error(monkeypatch):
    def boom(exchange, symbol, interval):
        raise ValueError("Exchange or symbol not found")

    monkeypatch.setattr("unified_finance_mcp.providers.cex._get_analysis", boom)
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError, match="tradingview TA cex"):
        await p.quote("bitget", "CL")


async def test_summary_shape_matches_technicals(monkeypatch):
    monkeypatch.setattr("unified_finance_mcp.providers.cex._get_analysis",
                        lambda exchange, symbol, interval: fake_analysis())
    p = make_provider(monkeypatch)
    s = await p.summary("bitget", "CL", interval="1h")
    assert set(s) == {"symbol", "exchange", "interval", "summary", "oscillators",
                      "moving_averages", "indicators", "source"}
    assert s["summary"]["RECOMMENDATION"] == "BUY" and s["interval"] == "1h"
    assert s["source"] == "cex" and s["exchange"] == "bitget"


async def test_summary_rejects_unknown_interval(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.summary("bitget", "CL", interval="7m")


async def test_summary_not_found_for_rest_only_exchange(monkeypatch):
    """gate/mexc 无 TV screener → NotFound,让容器给结构化错误而不是乱猜。"""
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.summary("gate", "CL")


@respx.mock
async def test_funding_bitget(monkeypatch):
    route = respx.get("https://api.bitget.com/api/v2/mix/market/ticker").respond(
        200, json={"code": "00000", "data": [{"symbol": "CLUSDT",
                                              "fundingRate": "0.0001"}]})
    p = make_provider(monkeypatch)
    out = await p.funding("bitget", "CL")
    assert out == {"symbol": "CL", "funding_rate": "0.0001", "source": "cex"}
    # C1 回归:bitget ticker 必须带 symbol+productType 参数,不然 400。
    params = respx.calls[0].request.url.params
    assert params["symbol"] == "CLUSDT" and params["productType"] == "USDT-FUTURES"
    assert route.called


@respx.mock
async def test_funding_gate_sends_contract_param(monkeypatch):
    """C1 回归:gate ticker 必须带 contract,不然返回全市场 981 条 data[0] 错资产。"""
    route = respx.get("https://api.gateio.ws/api/v4/futures/usdt/tickers").respond(
        200, json=[{"contract": "CL_USDT", "funding_rate": "0.0002",
                    "total_size": "12345"}])
    p = make_provider(monkeypatch, exchanges=("gate",))
    out = await p.funding("gate", "CL")
    assert out == {"symbol": "CL", "funding_rate": "0.0002", "source": "cex"}
    assert respx.calls[0].request.url.params["contract"] == "CL_USDT"
    assert route.called


@respx.mock
async def test_open_interest_gate(monkeypatch):
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/tickers").respond(
        200, json=[{"contract": "CL_USDT", "funding_rate": "0.0002",
                    "total_size": "12345"}])
    p = make_provider(monkeypatch, exchanges=("gate",))
    out = await p.open_interest("gate", "CL")
    assert out == {"symbol": "CL", "open_interest": "12345", "source": "cex"}


@respx.mock
async def test_open_interest_mexc_uses_holdvol(monkeypatch):
    """MEXC OI 字段是 holdVol(不是 holdingAmount/total_size)(review M3)."""
    respx.get("https://contract.mexc.com/api/v1/contract/ticker").respond(
        200, json={"success": True, "code": 0, "data": {
            "symbol": "USOIL_USDT", "fundingRate": 0,
            "holdVol": 65378247, "fairPrice": 96.46, "lastPrice": 96.46}})
    p = make_provider(monkeypatch, exchanges=("mexc",))
    out = await p.open_interest("mexc", "CL")
    assert out == {"symbol": "CL", "open_interest": 65378247, "source": "cex"}


@respx.mock
async def test_ticker_contract_mismatch_is_notfound(monkeypatch):
    """C1 反幻觉护栏:ticker 返回的 contract 不在白名单映射表 → NotFound,
    不许把 MARSCOIN 的 funding_rate 当成 CL 的 (review C1)。"""
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/tickers").respond(
        200, json=[{"contract": "MARSCOIN_USDT", "funding_rate": "9.99"}])
    p = make_provider(monkeypatch, exchanges=("gate",))
    with pytest.raises(NotFound):
        await p.funding("gate", "CL")


@respx.mock
async def test_funding_failover_bitget_404_then_gate(monkeypatch):
    """从 bitget 起步:bitget ticker 404 落 gate (review I2)."""
    bitget = respx.get(
        "https://api.bitget.com/api/v2/mix/market/ticker").respond(404, json={})
    route = respx.get("https://api.gateio.ws/api/v4/futures/usdt/tickers").respond(
        200, json=[{"contract": "CL_USDT", "funding_rate": "0.0002"}])
    p = make_provider(monkeypatch)
    out = await p.funding("bitget", "CL")
    assert bitget.called
    assert out["funding_rate"] == "0.0002" and route.called


@respx.mock
async def test_all_exchanges_down_is_upstream_error(monkeypatch):
    """每一家都 5xx → 末次错误上抛(retryable unavailable),不是 NotFound。"""
    respx.get("https://api.bitget.com/api/v2/mix/market/candles").respond(500, json={})
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/candlesticks").respond(
        503, json={})
    respx.get("https://contract.mexc.com/api/v1/contract/kline/USOIL_USDT").respond(
        500, json={})
    p = make_provider(monkeypatch)
    with pytest.raises((UpstreamError, ProviderError)):
        await p.kline("bitget", "CL", interval="1d", limit=1)


@respx.mock
async def test_kline_limit_and_interval_params(monkeypatch):
    route = respx.get("https://api.bitget.com/api/v2/mix/market/candles").respond(
        200, json={"code": "00000", "data": [
            ["1789171200000", "97.011", "97.571", "95.221", "95.556", "201097.83",
             "19390959.25"]]})
    p = make_provider(monkeypatch)
    rows = await p.kline("bitget", "CL", interval="1h", limit=10)
    params = respx.calls[0].request.url.params
    assert params["symbol"] == "CLUSDT"
    assert params["productType"] == "USDT-FUTURES"
    assert params["granularity"] == "1H"   # bitget 用大写 H/D/W/M
    assert params["limit"] == "10" and route.called
    assert rows[0]["date"] == "2026-09-12T00:00:00+00:00"  # ms epoch -> ISO UTC


@respx.mock
async def test_kline_dates_are_iso_utc(monkeypatch):
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/candlesticks").respond(
        200, json=[{"t": 1789142400, "o": "97.0", "h": "97.5", "l": "95.2",
                    "c": "95.5", "v": "201097"}])
    p = make_provider(monkeypatch, exchanges=("gate",))
    rows = await p.kline("gate", "CL", interval="1d", limit=1)
    assert rows[0]["date"] == "2026-09-11T16:00:00+00:00"  # 秒级 epoch -> ISO UTC
    assert rows[0]["volume"] == "201097"
