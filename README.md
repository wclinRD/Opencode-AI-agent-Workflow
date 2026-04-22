# OpenCode × Leeway Integration

**版本**：v0.14.0
**更新日期**：2026-04-22

將 **Leeway**（YAML 決策樹工作流程框架）整合到 **OpenCode**（AI Agent），讓 OpenCode 透過 `workflow` 工具呼叫執行 YAML 定義的工作流程，升級為「可引導的工作流程 Agent」。

---

## 1. 專案目標

讓 OpenCode 從自由發揮的 AI Agent，進化為「可定義、可審計、可重複」的工作流程 Agent，適用於：
- Code Health Check（代碼結構掃描、分類、審查、報告）
- API Design Review（設計審查、文件生成）
- Security Audit（安全漏洞掃描）
- PR Review（Pull Request 審查）
- 任意自定義流程

---

## 2. 技術棧

| 層面 | 技術 |
|------|------|
| OpenCode 端 | TypeScript / Node.js |
| Daemon 端 | Python 3.10+ / Pydantic |
| 通訊協定 | JSON-RPC 2.0 over stdin/stdout |
| 專案管理 | uv (Python) |

---

## 3. 關鍵特性

- JSON-RPC 2.0 標準協定
- stdin/stdout subprocess 通訊
- **Streaming 進度事件（即時輸出）**
- **Human-in-the-Loop (HITL) 支援**
- 自動重試與超時處理
- 完整錯誤碼定義
- **增強審計追蹤（execution_id, parallel_branches）**
- **多 workflow 支援（code-health, api-design, pr-review, security-scan）**
- **Skills 系統（coding-standards, code-review, security-audit）**
- **MCP 整合（GitHub, Filesystem, Brave Search 支援）**
- **Cron 排程（定時執行 workflow）**
- **Workflow 版本管理**
- **Workflow 模板市場**
- **Workflow 視覺化編輯器**
- **Workflow 測試框架**
- **Workflow 效能分析**

---

## 4. 目錄結構

```
Leeway/
├── docs/                          # 文件
│   ├── integration-design.md       # 整合設計文件
│   ├── integration-todo.md        # 任務追蹤清單
│   └── project-architecture.md   # 專案架構文件
│
├── src/                          # 原始碼
│   ├── leeway_integration/        # Python 整合層
│   │   ├── __init__.py            # 版本定義
│   │   ├── protocol.py           # JSON-RPC 類型定義
│   │   ├── error.py             # 錯誤類別定義
│   │   └── daemon/              # Daemon 實現
│   │       └── core.py           # Daemon 核心邏輯
│   │
│   └── tools/                   # TypeScript 工具
│       ├── workflow-daemon.ts  # Daemon 通訊層
│       ├── workflow.ts        # Workflow Tool
│       └── index.ts           # 模組匯出
│
├── .leeway/                     # Leeway 配置
│   ├── settings.json            # 設定檔（含 MCP）
│   ├── workflows/              # Workflow YAML
│   │   ├── code-health.yaml   # 代碼健康檢查
│   │   ├── api-design.yaml    # API 設計審查
│   │   ├── pr-review.yaml     # PR 審查
│   │   ├── security-scan.yaml # 安全掃描
│   │   ├── github-search.yaml # GitHub 搜尋（MCP）
│   │   └── research-assistant.yaml # 多來源研究（MCP）
│   └── skills/                 # Skills 定義
│       ├── coding-standards/
│       ├── code-review/
│       └── security-audit/
│
├── examples/                    # 範例腳本
│   ├── test-daemon.py          # Python 測試
│   ├── test-streaming.py      # Streaming 功能測試
│   └── test-mcp.py           # MCP 整合測試
│
├── pyproject.toml              # Python 專案設定
└── README.md                  # 專案說明
```

---

## 5. 安裝

```bash
uv sync
```

---

## 6. 在 OpenCode 上安裝與使用

本節說明如何將 Leeway 整合到 OpenCode。請按照以下步驟執行。

### 6.1 預備知識

在執行安裝前，需要了解：
- Leeway 專案位於：`~/opencode/Leeway/`（或您下載的位置）
- OpenCode 專案位於：`~/opencode/grap/`（或您的 OpenCode 目錄）
- 需要使用 Bash 工具執行 shell 命令
- 需要使用 Write 工具編輯設定檔

### 6.2 安裝步驟（請依序執行）

#### 步驟 1：確認專案位置

```bash
ls -la ~/opencode/Leeway/src/tools/
ls -la ~/opencode/grap/src/
```

#### 步驟 2：複製 TypeScript 工具模組

將 Leeway 的 workflow tool 複製到 OpenCode：

```bash
cp ~/opencode/Leeway/src/tools/workflow-daemon.ts ~/opencode/grap/src/
cp ~/opencode/Leeway/src/tools/workflow.ts ~/opencode/grap/src/
```

#### 步驟 3：複製 Leeway 配置目錄

```bash
cp -r ~/opencode/Leeway/.leeway ~/opencode/grap/
```

#### 步驟 4：驗證複製結果

```bash
ls -la ~/opencode/grap/src/workflow*.ts
ls -la ~/opencode/grap/.leeway/
```

#### 步驟 5：更新設定檔

編輯 `~/opencode/grap/.leeway/settings.json`，使用 llama.cpp server：

```json
{
  "api_key": "",
  "base_url": "http://localhost:8080",
  "model": "Qwen3.5-4B-UD-Q4_K_XL",
  "permission_mode": "default",
  "workflows_dir": ".leeway/workflows",
  "skills_dir": ".leeway/skills",
  "max_turns": 50,
  "max_tokens": 16384,
  "verbose": false,
  "llm_providers": {
    "llama-cpp": {
      "display_name": "Llama.cpp Server (Qwen3.5)",
      "description": "Run GGUF models via llama.cpp server",
      "api_key_env": "",
      "default_model": "Qwen3.5-4B-UD-Q4_K_XL",
      "base_url": "http://localhost:8080"
    },
    "anthropic": {
      "display_name": "Anthropic Claude",
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-3-5-sonnet-20241022"
    }
  }
}
```

**注意**：使用 llama.cpp server 時：
- `api_key` 留空
- `base_url` 設為 `http://localhost:8080`（llama.cpp server 預設端口）
- `model` 設為您下載的 GGUF 模型名稱（如 `llama-7b`、`mistral-7b` 等）

確保 llama.cpp server 已啟動：
```bash
# 啟動 llama.cpp server
./server -m Qwen3.5-4B-UD-Q4_K_XL.gguf -c 4096 -ngl 1 --port 8080
```

### 6.3 在 OpenCode 中使用

完成安裝後，在 OpenCode 中可以使用以下方式呼叫 workflow：

```
# 語法
workflow { name: "<workflow名稱>", user_context: "<任務描述>" }

# 範例：執行 code health check
workflow { name: "code-health", user_context: "Check my codebase at ./src" }

# 範例：執行 API 設計審查
workflow { name: "api-design", user_context: "Review the API design in src/api.ts" }

# 範例：執行安全掃描
workflow { name: "security-scan", user_context: "Scan for vulnerabilities" }
```

### 6.4 可用的 Workflow

| Workflow | 用途 |
|----------|------|
| `code-health` | 代碼結構掃描、分類、審查、報告 |
| `api-design` | API 設計審查、文件生成 |
| `pr-review` | Pull Request 審查 |
| `security-scan` | 安全漏洞掃描 |
| `github-search` | GitHub 搜尋（MCP）|
| `research-assistant` | 多來源研究（MCP）|

**注意**：請確保 llama.cpp server 已啟動（使用 Qwen3.5-4B 模型）：
```bash
# 下載模型：https://huggingface.co/unsloth/Qwen3.5-4B-GGUF
./server -m Qwen3.5-4B-UD-Q4_K_XL.gguf -c 4096 -ngl 1 --port 8080
```

### 6.5 疑難排解

| 問題 | 解決方式 |
|------|----------|
| 找不到 workflow tool | 確認 `~/opencode/grap/src/workflow*.ts` 已複製 |
| workflow 不存在 | 確認 `~/opencode/grap/.leeway/workflows/` 中有對應的 YAML 檔案 |
| llama.cpp server 無回應 | 確認 server 已啟動在 port 8080 |

---

## 7. 快速開始（本地測試）

### 7.1 測試 Daemon

```bash
PYTHONPATH=src uv run python examples/test-daemon.py
```

### 7.2 執行 Daemon

```bash
PYTHONPATH=src uv run python -m leeway_integration.daemon.core --workflows-dir .leeway/workflows
```

### 7.3 JSON-RPC 操作

```bash
# 列出 workflows
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.list","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 執行 workflow
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.execute","params":{"name":"code-health","user_context":"test"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 驗證 workflow
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.validate","params":{"name":"code-health"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core
```

---

## 8. JSON-RPC 方法列表

### 8.1 核心方法

| 方法 | 說明 |
|------|------|
| `daemon.ping` | 健康檢查 |
| `workflow.execute` | 執行 workflow |
| `workflow.list` | 列出 workflows |
| `workflow.validate` | 驗證 workflow |
| `workflow.respond` | HITL 回應 |
| `daemon.stop` | 停止 daemon |

### 8.2 MCP 方法

| 方法 | 說明 |
|------|------|
| `mcp.servers` | 列出 MCP 伺服器 |
| `mcp.start` | 啟動 MCP 伺服器 |
| `mcp.stop` | 停止 MCP 伺服器 |
| `mcp.list_tools` | 列出 MCP 工具 |
| `mcp.execute` | 執行 MCP 工具 |

### 8.3 Cron 排程

| 方法 | 說明 |
|------|------|
| `cron.create` | 建立排程 |
| `cron.list` | 列出排程 |
| `cron.delete` | 刪除排程 |
| `cron.toggle` | 啟用/停用排程 |
| `scheduler.start` | 啟動排程執行緒 |
| `scheduler.stop` | 停止排程執行緒 |
| `scheduler.status` | 查看排程狀態 |
| `scheduler.executions` | 查看執行歷史 |

### 8.4 Hooks

| 方法 | 說明 |
|------|------|
| `hooks.list` | 列出 hooks |
| `hooks.register` | 註冊 hook |
| `hooks.unregister` | 移除 hook |
| `hooks.toggle` | 啟用/停用 hook |
| `hooks.execute` | 執行 hook |

### 8.5 版本管理

| 方法 | 說明 |
|------|------|
| `workflow.version.list` | 列出版本 |
| `workflow.version.get` | 取得版本 |
| `workflow.version.create` | 創建版本 |
| `workflow.version.set_default` | 設定預設版本 |
| `workflow.version.deprecate` | 廢除版本 |
| `workflow.version.delete` | 刪除版本 |
| `workflow.version.compare` | 比較版本 |
| `workflow.version.rollback` | 回滾版本 |

### 8.6 模板市場

| 方法 | 說明 |
|------|------|
| `templates.list` | 列出模板 |
| `templates.get` | 取得模板 |
| `templates.search` | 搜索模板 |
| `templates.categories` | 列出分類 |
| `templates.install` | 安裝模板 |
| `templates.uninstall` | 卸載模板 |
| `templates.publish` | 發布模板 |
| `templates.rate` | 評分模板 |
| `templates.review` | 評論模板 |
| `templates.featured` | 精選模板 |

### 8.7 視覺化編輯器

| 方法 | 說明 |
|------|------|
| `editor.create_project` | 建立專案 |
| `editor.open_project` | 打開專案 |
| `editor.save_project` | 儲存專案 |
| `editor.list_projects` | 列表專案 |
| `editor.add_node` | 新增節點 |
| `editor.add_edge` | 新增邊 |
| `editor.validate` | 驗證圖形 |
| `editor.undo` | 復原 |
| `editor.redo` | 重做 |

### 8.8 測試框架

| 方法 | 說明 |
|------|------|
| `tests.create` | 建立測試 |
| `tests.run` | 執行測試 |
| `tests.run_many` | 執行多個測試 |
| `tests.suite.create` | 建立測試套件 |
| `tests.suite.run` | 執行測試套件 |
| `tests.coverage` | 取得覆蓋率 |
| `tests.metrics` | 取得度量 |

### 8.9 效能分析

| 方法 | 說明 |
|------|------|
| `performance.analyze` | 分析效能 |
| `performance.slowest_nodes` | 最慢節點 |
| `performance.bottlenecks` | 瓶頸分析 |
| `performance.export` | 匯出報告 |

---

## 9. 錯誤碼對照表

### 9.1 標準錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32600` | Invalid Request | 請求格式錯誤 |
| `-32601` | Method not found | 方法不存在 |
| `-32602` | Invalid params | 參數驗證失敗 |
| `-32603` | Internal error | 內部錯誤 |

### 9.2 自定義錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32000` | Workflow not found | workflow 不存在 |
| `-32001` | Node not found | 節點不存在 |
| `-32002` | Signal validation failed | 訊號不在白名單 |
| `-32003` | Permission denied | 權限不足 |
| `-32004` | Tool execution failed | 工具執行失敗 |
| `-32005` | Parallel branch timeout | 平行分支超時 |
| `-32006` | HITL timeout | 人類輸入超時 |

### 9.3 MCP 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32100` | MCP server not found | MCP 伺服器不存在 |
| `-32101` | MCP tool not found | MCP 工具不存在 |
| `-32102` | MCP connection failed | MCP 連線失敗 |
| `-32103` | MCP tool execution error | MCP 工具執行錯誤 |

---

## 10. Streaming 事件

Streaming 事件透過獨立的 stdout 發送（每行一個 JSON 物件）：

```json
{"type":"workflow","action":"started","workflow_name":"code-health"}
{"type":"progress","message":"▶ Starting workflow 'code-health'"}
{"type":"node","node_name":"scan","action":"started"}
{"type":"progress","message":"  ● Node 'scan'"}
{"type":"node","node_name":"scan","action":"completed","signal":"ready"}
{"type":"workflow","action":"completed","workflow_name":"code-health"}
```

| 事件類型 | 用途 |
|----------|------|
| `progress` | 一般進度訊息 |
| `node` | 節點開始/完成 |
| `workflow` | 工作流生命週期 |
| `branch` | 平行分支事件 |
| `signal` | HITL 詢問 |

---

## 11. 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v0.1.0 | 2026-04-22 | 初始版本 |
| v0.2.0 | 2026-04-22 | Streaming, HITL, 新 workflows, skills |
| v0.3.0 | 2026-04-22 | MCP 整合 |
| v0.4.0 | 2026-04-22 | Cron 排程 |
| v0.5.0 | 2026-04-22 | Scheduler Daemon |
| v0.6.0 | 2026-04-22 | Hooks 整合 |
| v0.7.0 | 2026-04-22 | 自定義 Tool |
| v0.8.0 | 2026-04-22 | Plugin 系統 |
| v0.9.0 | 2026-04-22 | 錯誤處理與重試 |
| v0.10.0 | 2026-04-22 | 監控與日誌 |
| v0.11.0 | 2026-04-22 | Workflow 版本管理 |
| v0.12.0 | 2026-04-22 | Workflow 模板市場 |
| v0.13.0 | 2026-04-22 | Workflow 視覺化編輯器 |
| v0.14.0 | 2026-04-22 | Workflow 測試框架 + 效能分析 |

---

**維護者**：OpenCode AI Assistant

---

## 12. 相關文件

- [整合設計文件](./docs/integration-design.md)
- [任務追蹤清單](./docs/integration-todo.md)
- [專案架構文件](./docs/project-architecture.md)