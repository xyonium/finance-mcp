# 发布管路 hatch-vcs

**2026-09-12 起 finance-mcp 的 PyPI 发布管路：**

- `pyproject.toml` 用 `dynamic = ["version"]` + `[tool.hatch.version] source = "vcs"` —— **version 完全由 git tag 推导**，不再写死
- `publish.yml` 由 `push tags v*` 触发；tag 推上去就发。不要手改 pyproject version
- **教训（2026-09-11）**：硬编码 `version = "0.1.2"` + 打 v0.1.3 tag 时，wheel metadata 仍是 0.1.2 → PyPI 视为 duplicate **静默丢**，workflow 却 success —— PyPI 卡死在 0.1.2 一天没人发现
- **mcpo 里的 finance server**：launch cmd 是 `uvx --refresh --from unified-finance-mcp unified-finance-mcp`，永远拉 PyPI 最新 —— 不需要"重启 mcpo 等新版"，冷启动就拉新
- **`config.json` `mcpServers.finance.env` 的 `FINANCE_MCP_FUTU_MOUNT_LAYOUT=grouped`**：mcpo `/finance/openapi.json` 收敛到 grouped 形态。**2026-11-18 起 30 paths** = 23 unified + 7 futu 容器（market / fundamentals / corporate / capital / options / macro / futu_reference）。折叠只在 unified 这边，直连 `futu-opend-mcp` server 仍是 53 平铺
- **教训（2026-09-14, v0.3.0）**：mcpo 容器 pip 默认源在 PyPI 发布后数分钟内**看不到新 tag** → `pip install unified-finance-mcp==X` 报 No matching distribution。解法：`--index-url https://pypi.org/simple --no-cache-dir`。热更新流程：`docker exec mcpo pip install --no-deps --force-reinstall --no-cache-dir --index-url https://pypi.org/simple unified-finance-mcp==X` + `docker restart mcpo`
- **Grouped 调用形态**：`POST /finance/futu_<域> {"action":"list|describe|call", "tool":"...", "params":{...}}` —— 容器 list 返回该域 tool 名录，describe 透传 vendored futu 签名 + docstring

contingency: 若 publish 卡 version mismatch，`gh api /pypi/unified-finance-mcp/json .info.version` 对照最新 remote tag。
