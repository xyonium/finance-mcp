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

### mcpo 部署验收（2026-11-19 踩点）

发版后让 mcpo 真正跑上新版本，有两个坑：

1. **PyPI 的 JSON API 与 simple index 不同步**。`https://pypi.org/pypi/unified-finance-mcp/json` 已显示 `0.4.4` 时，uv 用的 simple index 可能还停在 `0.4.3`；此时重启 mcpo 会继续复用旧 archive。**重启前先在容器里验证解析结果**：

   ```bash
   docker exec mcpo sh -c "cd /tmp && /usr/bin/uvx --refresh --from unified-finance-mcp python -c \"import importlib.metadata as m; print(m.version(unified-finance-mcp))\""
   ```

   输出目标版本再重启；否则等 1-2 分钟重试。

2. **launch args 必须带 `--refresh`**，否则 uvx 直接复用缓存环境，重启也不会升级。2026-11-19 已把 `/mnt/docker/mcpserver/config.json` 的 finance args 改成 `["--refresh","--from","unified-finance-mcp","unified-finance-mcp"]`（备份 `config.json.bak-20261119-185547`）。

验收三项：`/finance/openapi.json` 的 path 数（grouped 布局 = 30）、运行进程的 archive 目录里有 `unified_finance_mcp-<目标版本>.dist-info`、以及一次真实工具调用。进程 archive 路径可从 `docker exec mcpo sh -c for p in /proc/1 /proc/107 /proc/114 /proc/119 /proc/125 /proc/126509 /proc/126511 /proc/126513 /proc/128 /proc/1374 /proc/1386 /proc/1387 /proc/1416 /proc/1423 /proc/1894 /proc/1898 /proc/2 /proc/229 /proc/230 /proc/238 /proc/240 /proc/245 /proc/246 /proc/248 /proc/249 /proc/263 /proc/279 /proc/283999 /proc/284001 /proc/284004 /proc/296 /proc/3 /proc/318989 /proc/402782 /proc/402829 /proc/402919 /proc/402922 /proc/402935 /proc/402945 /proc/403002 /proc/403043 /proc/403072 /proc/403079 /proc/403681 /proc/403736 /proc/403743 /proc/403800 /proc/429 /proc/430 /proc/430573 /proc/430606 /proc/430795 /proc/430796 /proc/430809 /proc/430819 /proc/430821 /proc/430827 /proc/431 /proc/432 /proc/454 /proc/482 /proc/483 /proc/499 /proc/61 /proc/7 /proc/82 /proc/96 /proc/97 /proc/99

### mcpo 部署验收（2026-11-19 踩点）

发版后让 mcpo 真正跑上新版本，有两个坑：

1. **PyPI 的 JSON API 与 simple index 不同步**。`https://pypi.org/pypi/unified-finance-mcp/json` 已显示 `0.4.4` 时，uv 用的 simple index 可能还停在 `0.4.3`；此时重启 mcpo 会继续复用旧 archive。**重启前先在容器里验证解析结果**：

   ```bash
   docker exec mcpo sh -c "cd /tmp && /usr/bin/uvx --refresh --from unified-finance-mcp python -c 'import importlib.metadata as m; print(m.version(\"unified-finance-mcp\"))'"
   ```

   输出目标版本再重启；否则等 1-2 分钟重试。

2. **launch args 必须带 `--refresh`**，否则 uvx 直接复用缓存环境，重启也不会升级。2026-11-19 已把 `/mnt/docker/mcpserver/config.json` 的 finance args 改成 `["--refresh","--from","unified-finance-mcp","unified-finance-mcp"]`（备份 `config.json.bak-20261119-185547`）。

验收三项：`/finance/openapi.json` 的 path 数（grouped 布局 = 30）、运行进程的 archive 目录里有 `unified_finance_mcp-<目标版本>.dist-info`、以及一次真实工具调用。进程 archive 路径可从 `/proc/<pid>/cmdline` 看到。
