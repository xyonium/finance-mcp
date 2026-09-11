"""Regression: _install_stdio_sanitizer must keep MCP frames on the original
stdout destination while rerouting anything third-party code writes to fd 1
directly, so MCP stdio never sees non-JSON bytes.
"""
import io
import os
import sys

import pytest

from unified_finance_mcp.server import _install_stdio_sanitizer


@pytest.mark.skipif(not os.path.exists("/dev/stderr"),
                    reason="requires /dev/stderr (POSIX)")
def test_stdio_sanitizer_reroutes_fd1_to_stderr_and_preserves_sys_stdout():
    orig_stdout = sys.stdout
    try:
        mcp_r, mcp_w = os.pipe()      # what sys.stdout should keep writing to
        err_r, err_w = os.pipe()      # what fd 1 should be rerouted to

        saved_fd1 = os.dup(1)
        saved_fd2 = os.dup(2)
        # Point fd 1 at the "original stdout" pipe and fd 2 at the "stderr"
        # pipe, so /dev/stderr inside the helper resolves to our err_w.
        os.dup2(mcp_w, 1)
        os.dup2(err_w, 2)
        # sys.stdout must wrap the same pipe mcp will write to.
        sys.stdout = io.TextIOWrapper(io.FileIO(mcp_w, "w",
                                                closefd=False),
                                      encoding="utf-8")

        _install_stdio_sanitizer()

        # Bytes written through the NEW sys.stdout (mcp's path) must land on
        # the original stdout pipe, not on the rerouted fd 1.
        sys.stdout.write("mcp-frame\n")
        sys.stdout.flush()
        # Bytes written directly to fd 1 (third-party print path) must land on
        # the stderr pipe.
        os.write(1, b"third-party-noise\n")

        got_mcp = os.read(mcp_r, 100)
        got_err = os.read(err_r, 100)
        assert got_mcp == b"mcp-frame\n"
        assert got_err == b"third-party-noise\n"

        os.close(mcp_r)
        os.close(err_r)
    finally:
        # Restore original fds regardless of assertion outcome.
        os.dup2(saved_fd1, 1)
        os.dup2(saved_fd2, 2)
        os.close(saved_fd1)
        os.close(saved_fd2)
        sys.stdout = orig_stdout
