"""Server assembly: build_mcp(settings) / build_app(settings) / main()."""
from __future__ import annotations

import argparse
import importlib
import io
import logging
import os
import sys

# Eager-import on the main thread: tradingview_screener's first Query() lazily
# imports pandas and can deadlock inside an anyio worker (tradingview-mcp#91).
import pandas  # noqa: F401
import tradingview_screener  # noqa: F401
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .config import Settings, get_settings

log = logging.getLogger("unified_finance_mcp")


def _install_stdio_sanitizer() -> None:
    """Redirect the process' real stdout (fd 1) to stderr so nothing third-party
    code prints can corrupt the MCP stdio JSONRPC stream.

    mcp.server.stdio writes JSONRPC frames to ``sys.stdout.buffer``. Some
    providers (notably the vendored futu skill pack, which prints diagnostics
    via bare ``print()``) bypass this and write directly to fd 1, injecting
    non-JSON bytes into the stream. mcpo's line-by-line parser then emits
    "Failed to parse JSONRPC message from server / trailing characters" for
    every polluted line.

    Fix: ``dup(1)`` first — the duplicate still points at the original stdout
    destination — and point ``sys.stdout`` at a TextIOWrapper around that dup,
    so MCP keeps writing where it always did. Then ``dup2`` the opened
    ``/dev/stderr`` onto fd 1, so every byte written by third-party code to
    the process stdout is rerouted to stderr instead.

    Weakref.finalize is deliberately NOT used: the mcp run loop blocks
    forever, so the fds live for the lifetime of the process anyway. At exit
    the interpreter flushes/closes ``sys.stdout`` (the dup wrapper), not the
    ``/dev/stderr`` fd, which is owned by the runtime.
    """
    mcp_fd = os.dup(1)  # still points at the real stdout destination
    stderr_fd = os.open("/dev/stderr", os.O_WRONLY)
    os.dup2(stderr_fd, 1)
    os.close(stderr_fd)
    sys.stdout = io.TextIOWrapper(io.FileIO(mcp_fd, "w"), encoding="utf-8")


INSTRUCTIONS = (
    "Unified finance data server. Prefer the unified tools (get_quote, get_history, "
    "get_company_info, get_financial_report, get_news, get_technical_indicators, "
    "run_screener, get_ownership, get_events_calendar, get_economic_data, "
    "search_symbols, get_option_chain, get_short_interest, get_analyst_estimates, "
    "get_dividend_split_history, get_earnings_history, "
    "get_company_risk_cn, quant_backtest, kimi_datasource, "
    "get_service_status, tv_scan, tv_analyze, egx_market) — they auto-route across "
    "sources by market coverage; the accepted `source` values vary per tool (each "
    "tool's description lists its own options; the common core is auto | futu | "
    "yahoo | fmp | alphavantage). Use the futu_*-style tools (get_snapshot, get_kline, "
    "futu_get_option_chain, ...) for HK/CN/US depth from Futu OpenD. "
    "tv_scan/tv_analyze/egx_market are TradingView scanner containers selected by "
    "`action`; an unknown action returns the available list. quant_backtest runs "
    "strategy backtests; call it with action='help' for its full parameter guide. "
    "get_company_risk_cn profiles Chinese companies (tianyancha via kimi); "
    "for Chinese 快讯/flash headlines (熱度/view_count, no summary/sentiment), "
    "use the futu-mounted search_news tool instead of get_news; "
    "kimi_datasource gives direct self-describing access to deep datasources with "
    "action='list' | 'describe' | 'call' (e.g. action='list' to enumerate sources, "
    "action='describe' for one source's API doc, action='call' with source/api/params "
    "to invoke). get_service_status reports which sources are configured."
)


def build_mcp(settings: Settings) -> FastMCP:
    from . import tools
    from .providers import build_providers

    mcp = FastMCP("unified-finance-mcp", instructions=INSTRUCTIONS)
    providers = build_providers(settings)
    for mod_name in tools.ALL_MODULES:
        mod = importlib.import_module(f"{__package__}.tools.{mod_name}")
        mod.register(mcp, providers, settings)
    if settings.futu_enabled:
        try:
            from .providers import futu_bridge
        except ImportError as exc:  # futu_bridge lands with the provider registry
            # Expected until Task 3 adds providers/futu_bridge.py; debug, not warning.
            log.debug("futu bridge unavailable (%s); skipping futu tool mount", exc)
        else:
            futu_bridge.mount_futu_tools(mcp)
    return mcp


def build_app(settings: Settings):
    mcp = build_mcp(settings)

    @mcp.custom_route("/health", methods=["GET"])
    async def _health(request):
        return JSONResponse({"status": "ok"})

    app = mcp.streamable_http_app()
    app.state.settings = settings
    app.state.mcp = mcp
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="unified-finance-mcp")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    settings = get_settings()
    transport = args.transport or settings.transport
    if transport == "stdio":
        _install_stdio_sanitizer()
        build_mcp(settings).run()
        return
    import uvicorn

    uvicorn.run(build_app(settings), host=args.host or settings.host,
                port=args.port or settings.port, log_level="info")


if __name__ == "__main__":
    main()
