"""Error taxonomy + never-raise tool error dicts."""
from __future__ import annotations


class ProviderError(Exception):
    kind = "error"
    retryable = False


class RateLimited(ProviderError):
    kind = "rate_limited"
    retryable = True


class AuthError(ProviderError):
    kind = "auth"


class NotFound(ProviderError):
    kind = "not_found"


class UpstreamError(ProviderError):
    kind = "unavailable"
    retryable = True


def tool_error(msg: object, hint: str | None = None, **extra) -> dict:
    out = {"error": str(msg)}
    if hint:
        out["hint"] = hint
    out.update(extra)
    return out


def scrub(text: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text
