# cliproxy-kimi-tools 是用户名下的 Go 插件

`xyonium/cliproxy-kimi-tools` 是用户 eli 名下的**独立开源项目**（Golang，CLIProxyAPI 的 plugin）。它注册了一个 management 路由 `POST /v0/management/kimi/tools`，把任何请求体**verbatim 转发**到 upstream `https://api.kimi.com/coding/v1/tools`（注入 auth JSON 里的 access_token + device_id）。

**Why**: 2026-09-13 finance-mcp R14 工作中我们误以为它是 router-for-me/CLIProxyAPI 团队写的第三方插件，其实它就是用户本人的项目，所以：
- 改它**不需要协调成本**（独立 commit/push 即可）
- 它**只转发不改写** —— Kimi 上游不认识的方法（如 `list_data_sources`）会 404，插件只是诚实透传
- finance-mcp 侧的"R14 探测式 `_resolve_source`"逻辑可以在**不动这个插件**的前提下完整工作

**How to apply**:
- finance-mcp（Python）和 cliproxy-kimi-tools（Go）是两个独立 repo，分别独立演进
- mcpo 容器只是通过 `KIMI_PROXY_URL=http://cli-proxy-api:8317/v0/management/kimi/tools` 调用它；"我改了 cliproxy 插件" = `.so` 重新 build 到 `/CLIProxyAPI/plugins/linux/amd64/kimi-tools.so` + cliproxy 容器重启
- 插件 repo：`https://github.com/xyonium/cliproxy-kimi-tools`（`xyonium` = 用户 GitHub 账户）
