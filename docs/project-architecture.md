# OpenCode × Leeway 專案架構文件

**版本**：v0.13.0
**更新日期**：2026-04-22
**用途**：幫助 AI 模型快速理解專案架構與檔案關係

---

## 1. 專案概述

### 1.1 專案目標

將 **Leeway**（YAML 決策樹工作流程框架）整合到 **OpenCode**（AI Agent），讓 OpenCode 透過 `workflow` 工具呼叫執行 YAML 定義的工作流程，升級為「可引導的工作流程 Agent」。

### 1.2 技術棧

| 層面 | 技術 |
|------|------|
| OpenCode 端 | TypeScript / Node.js |
| Daemon 端 | Python 3.10+ / Pydantic |
| 通訊協定 | JSON-RPC 2.0 over stdin/stdout |
| 專案管理 | uv (Python) |

### 1.3 關鍵特性

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
- **Workflow 版本管理（Phase B.1）**
- **Workflow 模板市場（Phase B.2）**
- **Workflow 視覺化編輯器（Phase B.3）**
- **Workflow 測試框架（Phase B.5）**
- **Workflow 效能分析（Phase B.6）**

---

## 2. 目錄結構

```
Leeway/
│
├── docs/                          # 文件
│   ├── integration-design.md     # 整合設計文件 (688 行)
│   ├── integration-todo.md       # 任務追蹤清單
│   └── project-architecture.md  # 本文件 (專案架構)
│
├── src/                          # 原始碼
│   ├── leeway_integration/       # Python 整合層
│   │   ├── __init__.py           # 版本定義 (__version__ = "0.1.0")
│   │   ├── protocol.py           # JSON-RPC 類型定義 (+ streaming events)
│   │   ├── error.py             # 錯誤類別定義
│   │   └── daemon/              # Daemon 實現
│   │       ├── __init__.py
│   │       └── core.py         # Daemon 核心邏輯 (+ streaming, HITL)
│   │
│   └── tools/                   # TypeScript 工具
│       ├── workflow-daemon.ts   # Daemon 通訊層 (+ streaming events)
│       ├── workflow.ts         # Workflow Tool
│       └── index.ts           # 模組匯出
│
├── .leeway/                     # Leeway 配置
│   ├── settings.json           # 設定檔（含 MCP servers 配置）
│   ├── workflows/              # Workflow YAML
│   │   ├── code-health.yaml   # 代碼健康檢查
│   │   ├── api-design.yaml    # API 設計審查
│   │   ├── pr-review.yaml     # PR 審查
│   │   ├── security-scan.yaml # 安全掃描
│   │   ├── github-search.yaml # GitHub 搜尋（MCP）
│   │   └── research-assistant.yaml # 多來源研究（MCP）
│   └── skills/                 # Skills 定義
│       ├── coding-standards/
│       │   └── SKILL.md
│       ├── code-review/
│       │   ├── SKILL.md
│       │   └── references/
│       │       └── checklist.md
│       └── security-audit/
│           ├── SKILL.md
│           └── references/
│               └── owasp.md
│
├── examples/                    # 範例腳本
│   ├── test-daemon.py          # Python 測試
│   ├── test-streaming.py      # Streaming 功能測試
│   ├── test-mcp.py            # MCP 整合測試
│   └── test-workflow.ts       # TypeScript 範例
│
├── pyproject.toml              # Python 專案設定
└── README.md                  # 專案說明
```

---

## 3. 檔案關係圖

### 3.1 Python 層 (src/leeway_integration/)

```
protocol.py
├── JsonRpcRequest          # JSON-RPC 請求
├── JsonRpcResponse         # JSON-RPC 響應
├── DaemonPingParams/Result
├── WorkflowExecuteParams/Result
├── WorkflowListParams/Result
├── WorkflowValidateParams/Result
├── WorkflowRespondParams/Result  # HITL 回應
├── DaemonStopParams
├── ERROR_CODES 常數
├── ProgressEvent            # Streaming: 進度事件
├── HitlSignal               # Streaming: HITL 訊號
├── HitlQuestion             # Streaming: HITL 選項
├── BranchEvent              # Streaming: 分支事件
├── NodeEvent               # Streaming: 節點事件
└── WorkflowEvent          # Streaming: 工作流事件

error.py
├── DaemonError (基底類別)
├── InvalidRequestError     # -32600
├── MethodNotFoundError    # -32601
├── InvalidParamsError     # -32602
├── InternalError          # -32603
├── WorkflowNotFoundError  # -32000
├── NodeNotFoundError      # -32001
├── SignalValidationError  # -32002
├── PermissionDeniedError # -32003
├── ToolExecutionError     # -32004
├── ParallelBranchTimeoutError  # -32005
├── HitlTimeoutError      # -32006
├── McpServerNotFoundError  # -32100
├── McpToolNotFoundError   # -32101
├── McpConnectionError    # -32102
└── McpToolExecutionError # -32103

daemon/core.py
├── McpServer 類別         # MCP 伺服器管理
│   ├── start()            # 啟動 MCP 伺服器
│   ├── stop()            # 停止 MCP 伺服器
│   ├── list_tools()      # 列出工具
│   ├── execute_tool()  # 執行工具
│   └── is_running()     # 檢查運行狀態
│
├── McpManager 類別       # MCP 伺服器生命週期管理
│   ├── get_server()     # 取得伺服器
│   ├── list_servers()  # 列出伺服器
│   ├── start_server()  # 啟動伺服器
│   └── stop_server()   # 停止伺服器
│
├── CronScheduler 類別   # Cron 排程管理
│   ├── create()          # 建立排程
│   ├── list()           # 列出排程
│   ├── delete()        # 刪除排程
│   ├── toggle()         # 啟用/停用排程
│   └── _validate_cron_expression()  # 驗證 cron 表達式
│
├── SchedulerDaemon 類別   # 後台排程執行器
│   ├── start()          # 啟動排程執行緒
│   ├── stop()           # 停止排程執行緒
│   ├── is_running()    # 檢查運行狀態
│   ├── get_status()     # 取得狀態
│   ├── get_executions() # 取得執行歷史
│   ├── _run_loop()      # 主執行迴圈
│   ├── _check_and_execute() # 檢查並執行
│   ├── _execute_workflow() # 執行 workflow
│   └── _is_due()        # 檢查是否到期
│
├── WorkflowVersionManager 類別   # Workflow 版本管理 (Phase B.1)
│   ├── list_versions()    # 列出所有版本
│   ├── get_version()      # 取得特定版本
│   ├── create_version()    # 創建新版本
│   ├── set_default_version()  # 設定預設版本
│   ├── deprecate_version()    # 廢除版本
│   ├── delete_version()   # 刪除版本
│   ├── compare_versions()  # 比較版本
│   └── rollback()         # 回滾到指定版本
│
├── TemplateManager 類別    # Workflow 模板市場 (Phase B.2)
│   ├── list_templates()   # 列出模板
│   ├── get_template()    # 取得模板
│   ├── search_templates() # 搜索模板
│   ├── list_categories() # 列出分類
│   ├── install_template() # 安裝模板
│   ├── uninstall_template() # 卸載模板
│   ├── publish_template() # 發布模板
│   ├── update_template()  # 更新模板
│   ├── delete_template()  # 刪除模板
│   ├── rate_template()   # 評分模板
│   ├── add_review()      # 添加評論
│   ├── get_reviews()     # 獲取評論
│   ├── get_featured()    # 取得精選模板
│   ├── get_popular()     # 取得熱門模板
│   ├── get_newest()      # 取得最新模板
│   └── download_template() # 下載模板
│
├── WorkflowVisualEditor 類別  # Workflow 視覺化編輯器 (Phase B.3)
│   ├── create_project()   # 建立專案
│   ├── open_project()    # 打開專案
│   ├── save_project()    # 儲存專案
│   ├── list_projects()  # 列表專案
│   ├── delete_project() # 刪除專案
│   ├── add_node()      # 新增節點
│   ├── update_node()   # 更新節點
│   ├── delete_node()  # 刪除節點
│   ├── add_edge()     # 新增邊
│   ├── update_edge()  # 更新邊
│   ├── delete_edge() # 刪除邊
│   ├── validate()    # 驗證圖形
│   ├── export_project()  # 匯出專案
│   ├── import_content() # 匯入內容
│   ├── preview()     # 預覽內容
│   ├── auto_layout() # 自動佈局
│   ├── duplicate_node() # 複製節點
│   ├── undo()        # 復原
│   └── redo()        # 重做
│
├── WorkflowTestRunner 類別  # Workflow 測試框架 (Phase B.5)
│   ├── create_test()    # 建立測試用例
│   ├── update_test()   # 更新測試用例
│   ├── delete_test()   # 刪除測試用例
│   ├── get_test()     # 取得測試用例
│   ├── list_tests()   # 列出測試用例
│   ├── run()         # 執行單一測試
│   ├── run_many()    # 執行多個測試
│   ├── duplicate_test() # 複製測試
│   ├── create_suite() # 建立測試套件
│   ├── delete_suite()# 刪除測試套件
│   ├── list_suites() # 列出測試套件
│   ├── run_suite()  # 執行測試套件
│   ├── get_coverage() # 取得覆蓋率報告
│   ├── get_metrics() # 取得測試度量
│   └── get_history() # 取得執行歷史
│   ├── create_project()   # 建立專案
│   ├── open_project()    # 打開專案
│   ├── save_project()    # 儲存專案
│   ├── list_projects()  # 列表專案
│   ├── delete_project() # 刪除專案
│   ├── add_node()      # 新增節點
│   ├── update_node()   # 更新節點
│   ├── delete_node()  # 刪除節點
│   ├── add_edge()     # 新增邊
│   ├── update_edge()  # 更新邊
│   ├── delete_edge() # 刪除邊
│   ├── validate()    # 驗證圖形
│   ├── export_project()  # 匯出專案
│   ├── import_content() # 匯入內容
│   ├── preview()     # 預覽內容
│   ├── auto_layout() # 自動佈局
│   ├── duplicate_node() # 複製節點
│   ├── undo()        # 復原
│   └── redo()        # 重做
│
└── Daemon 類別
    ├── handle_request()      # 處理 JSON-RPC 請求
    ├── _register_methods()   # 註冊方法
    ├── _ping()              # daemon.ping
    ├── _workflow_execute()   # workflow.execute (+ streaming)
    ├── _workflow_list()     # workflow.list
    ├── _workflow_validate() # workflow.validate
    ├── _workflow_respond() # workflow.respond (HITL)
    ├── _stop()             # daemon.stop
    ├── _mcp_servers()     # mcp.servers
    ├── _mcp_start()       # mcp.start
    ├── _mcp_stop()        # mcp.stop
    ├── _mcp_list_tools()  # mcp.list_tools
    ├── _mcp_execute()    # mcp.execute
    ├── _cron_create()     # cron.create
    ├── _cron_list()      # cron.list
    ├── _cron_delete()   # cron.delete
    ├── _cron_toggle()   # cron.toggle
    ├── _scheduler_start()   # scheduler.start
    ├── _scheduler_stop()   # scheduler.stop
    ├── _scheduler_status() # scheduler.status
    ├── _scheduler_executions() # scheduler.executions
    ├── _version_list()     # workflow.version.list
    ├── _version_get()      # workflow.version.get
    ├── _version_create()   # workflow.version.create
    ├── _version_set_default() # workflow.version.set_default
    ├── _version_deprecate() # workflow.version.deprecate
    ├── _version_delete()   # workflow.version.delete
    ├── _version_compare()  # workflow.version.compare
    ├── _version_rollback() # workflow.version.rollback
    ├── _templates_list()    # templates.list
    ├── _templates_get()     # templates.get
    ├── _templates_search() # templates.search
    ├── _templates_categories() # templates.categories
    ├── _templates_install() # templates.install
    ├── _templates_uninstall() # templates.uninstall
    ├── _templates_publish() # templates.publish
    ├── _templates_update() # templates.update
    ├── _templates_delete() # templates.delete
    ├── _templates_rate()   # templates.rate
    ├── _templates_review() # templates.review
    ├── _templates_reviews() # templates.reviews
    ├── _templates_featured() # templates.featured
    ├── _templates_popular() # templates.popular
    ├── _templates_newest()  # templates.newest
    ├── _templates_versions() # templates.versions
    ├── _templates_download() # templates.download
    ├── _send_progress()    # 發送進度事件
    ├── _send_node_event()  # 發送節點事件
    ├── _send_branch_event() # 發送分支事件
    ├── _send_workflow_event() # 發送工作流事件
    └── _send_hitl()       # 發送 HITL 訊號
```

### 3.2 TypeScript 層 (src/tools/)

```
workflow-daemon.ts
├── WorkflowDaemonClient     # Daemon 通訊客戶端
│   ├── start()              # 啟動 daemon subprocess
│   ├── ping()               # 健康檢查
│   ├── executeWorkflow()   # 執行 workflow
│   ├── executeWorkflowWithStreaming() # streaming 執行
│   ├── listWorkflows()      # 列出 workflows
│   ├── validateWorkflow()    # 驗證 workflow
│   ├── respondToHitl()      # HITL 回應
│   ├── onStreamingEvent()    # 註冊 streaming 回調
│   └── stop()               # 停止 daemon
│
├── StreamingEvent types   # 事件類型
│   ├── ProgressEvent
│   ├── HitlSignalEvent
│   ├── BranchEvent
│   ├── NodeEvent
│   └── WorkflowEvent
│
├── ERROR_CODES           # 錯誤碼常數
├── DaemonError           # 錯誤類別
├── ConnectionError
├── WorkflowNotFoundError
└── RequestTimeoutError

workflow.ts
└── WorkflowTool 類別
    ├── name = "workflow"
    ├── input_schema       # 工具輸入定義
    ├── execute()        # 執行工具
    ├── formatResult()   # 格式化結果
    └── handleError()   # 錯誤處理

index.ts
└── 匯出所有 public 介面
```

---

## 4. 函數呼叫流程

### 4.1 正常流程 (workflow.execute)

```
OpenCode Agent
    │
    ▼ 呼叫 workflow tool
WorkflowTool.execute()
    │
    ├── getDaemonClient()         # 取得 singleton
    ├── daemon.ensure()          # 確保 daemon 運行
    └── daemon.executeWorkflow() # 發送請求
        │
        ▼ JSON-RPC
WorkflowDaemonClient.sendRequest()
    │
    ├── 寫入 stdin
    └── 等待 response
        │
        ▼
Python Daemon.run()
    │
    ├── 讀取 stdin line
    ├── json.loads()
    └── handle_request()
        │
        ├── 查找方法 (_workflow_execute)
        ├── 執行 workflow 節點
        │   ├── 發送 streaming 事件 (stdout)
        │   └── 記錄 audit trail
        └── 返回 JsonRpcResponse
            │
            ▼ JSON-RPC response
WorkflowDaemonClient.handleResponse()
    │
    ├── 解析 JSON
    ├── 處理 streaming 事件 (另一行)
    └── resolve Promise
        │
        ▼
WorkflowTool.formatResult()
    │
    └── 返回 ToolResult
```

### 4.1.1 Streaming 事件流程

```
Daemon._workflow_execute()
    │
    ├── _send_workflow_event("started")
    ├── _send_progress("▶ Starting...")
    │
    ├── 遍歷 nodes
    │   ├── _send_node_event("started")
    │   ├── _send_progress("● Node '...'")
    │   ├── 執行節點工具
    │   ├── _send_branch_event() (if parallel)
    │   └── _send_node_event("completed")
    │
    └── _send_workflow_event("completed")
        │
        ▼ stdout (streaming)
StreamingEvent callback (TypeScript)
    │
    └── console.log / 顯示 UI
```

### 4.2 錯誤流程 (Workflow Not Found)

```
WorkflowTool.execute()
    │
    └── daemon.executeWorkflow()
        │
        ▼
Daemon._workflow_execute()
    │
    ├── 檢查 workflow是否存在
    └── raise WorkflowNotFoundError()
        │
        ▼
Daemon.handle_request()  catch
    │
    └── 返回 error response
        │
        ▼
WorkflowDaemonClient.handleResponse()
    │
    └── reject Promise
        │
        ▼
WorkflowTool.handleError()
    │
    └── 返回錯誤 ToolResult
```

### 4.3 Daemon 啟動流程

```
WorkflowDaemonClient.start()
    │
    ├── spawn Python subprocess
    ├── 設��� stdin/stdout pipe
    └── readline.on('line', handleResponse)
        │
        ▼
waitForReady() [internal]
    │
    ├── 等待 startTimeout
    └── pingInternal() 直到成功
```

---

## 5. JSON-RPC 協定

### 5.1 請求格式

```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "method": "workflow.execute",
  "params": {
    "name": "code-health",
    "user_context": "Check my codebase"
  }
}
```

### 5.2 響應格式 (成功)

```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "result": {
    "success": true,
    "final_output": "Workflow executed successfully.",
    "audit": {
      "workflow_name": "code-health",
      "path_taken": ["scan", "triage", "review"],
      "node_executions": [
        {"node_name": "scan", "turns_used": 2, "tools_called": ["glob", "bash"]},
        {"node_name": "triage", "turns_used": 3, "tools_called": ["grep"]}
      ],
      "parallel_branches": {
        "review": {
          "quality": {"triggered": true, "completed": true, "approved": true}
        }
      },
      "execution_id": "a4de55f6",
      "started_at": "2026-04-22T10:00:00Z",
      "completed_at": "2026-04-22T10:05:00Z",
      "total_turns": 18
    }
  }
}
```

### 5.3 響應格式 (錯誤)

```json
{
  "jsonrpc": "2.0",
  "id": "req-123",
  "error": {
    "code": -32000,
    "message": "Workflow 'xxx' not found",
    "data": { "available": ["code-health"] }
  }
}
```

### 5.4 方法列表

| 方法 | 參數 | 返回 |
|------|------|------|
| `daemon.ping` | `{}` | `{version, status}` |
| `workflow.execute` | `{name, user_context, ...}` | `{success, final_output, audit}` |
| `workflow.list` | `{}` | `{workflows: [...]}` |
| `workflow.validate` | `{name}` | `{valid, errors}` |
| `workflow.respond` | `{answer}` | `{received, answer}` (HITL) |
| `daemon.stop` | `{}` | `{status}` |
| `mcp.servers` | `{}` | `{servers: [...]}` |
| `mcp.start` | `{server_name}` | `{name, status}` |
| `mcp.stop` | `{server_name}` | `{name, status}` |
| `mcp.list_tools` | `{server_name}` | `{tools: [...]}` |
| `mcp.execute` | `{server_name, tool_name, arguments}` | `{success, result, error}` |
| `cron.create` | `{name, workflow_name, cron_expression, ...}` | `{success, schedule, error}` |
| `cron.list` | `{}` | `{schedules: [...]}` |
| `cron.delete` | `{id}` | `{success, deleted_id, error}` |
| `cron.toggle` | `{id, enabled}` | `{success, schedule, error}` |
| `scheduler.start` | `{}` | `{success, status, error}` |
| `scheduler.stop` | `{}` | `{success, error}` |
| `scheduler.status` | `{}` | `{status: {...}}` |
| `scheduler.executions` | `{schedule_id?, limit?}` | `{executions: [...]}` |
| `hooks.list` | `{scope?, workflow_name?, event?}` | `{hooks: [...]}` |
| `hooks.register` | `{name, scope, event, ...}` | `{success, hook, error}` |
| `hooks.unregister` | `{hook_id}` | `{success, deleted_id, error}` |
| `hooks.toggle` | `{hook_id, enabled}` | `{success, hook, error}` |
| `hooks.execute` | `{hook_id, context?}` | `{success, result, error}` |
| **Phase B.1: 版本管理** |
| `workflow.version.list` | `{workflow_name}` | `{workflow_name, versions: [...], metadata: {...}}` |
| `workflow.version.get` | `{workflow_name, version?}` | `{workflow_name, version: {...}, is_default}` |
| `workflow.version.create` | `{workflow_name, version, ...}` | `{success, workflow_name, version}` |
| `workflow.version.set_default` | `{workflow_name, version}` | `{success, workflow_name, version}` |
| `workflow.version.deprecate` | `{workflow_name, version}` | `{success, workflow_name, version}` |
| `workflow.version.delete` | `{workflow_name, version, force?}` | `{success, workflow_name, version}` |
| `workflow.version.compare` | `{workflow_name, version_a, version_b}` | `{workflow_name, version_a, version_b, relationship, diff}` |
| `workflow.version.rollback` | `{workflow_name, target_version, ...}` | `{success, workflow_name, target_version, new_version}` |
| **Phase B.2: 模板市場** |
| `templates.list` | `{category?, tag?, search?, sort_by?, page?, limit?}` | `{templates: [...], total, page, total_pages}` |
| `templates.get` | `{template_id}` | `{template: {...}}` |
| `templates.search` | `{query, category?, tags?, author?, min_rating?, page?, limit?}` | `{templates: [...], total, suggestions: [...]}` |
| `templates.categories` | `{parent_id?}` | `{categories: [...]}` |
| `templates.install` | `{template_id, name?, version?, target_dir?}` | `{success, template_id, workflow_name, installed_path}` |
| `templates.uninstall` | `{template_id, delete_files?}` | `{success, template_id, deleted_files: [...]}` |
| `templates.publish` | `{name, description, category, content, ...}` | `{success, template_id, version}` |
| `templates.update` | `{template_id, content?, readme?, ...}` | `{success, template_id, new_version}` |
| `templates.delete` | `{template_id, reason?}` | `{success, template_id}` |
| `templates.rate` | `{template_id, rating, user_id?}` | `{success, template_id, new_average, total_ratings}` |
| `templates.review` | `{template_id, rating, content, user_id?, user_name?, title?}` | `{success, review_id}` |
| `templates.reviews` | `{template_id, page?, limit?}` | `{reviews: [...], total, page, total_pages}` |
| `templates.featured` | `{category?, limit?}` | `{templates: [...]}` |
| `templates.popular` | `{category?, time_range?, limit?}` | `{templates: [...]}` |
| `templates.newest` | `{category?, limit?}` | `{templates: [...]}` |
| `templates.versions` | `{template_id}` | `{template_id, versions: [...]}` |
| `templates.download` | `{template_id, version?}` | `{success, template_id, version, content}` |
| **Phase B.3: 視覺化編輯器** |
| `editor.create_project` | `{name, description?, content?, metadata?}` | `{success, project: {...}}` |
| `editor.open_project` | `{project_id?, workflow_name?}` | `{success, project: {...}}` |
| `editor.save_project` | `{project_id, content?, validate?}` | `{success, project: {...}}` |
| `editor.list_projects` | `{limit?, offset?}` | `{projects: [...], total}` |
| `editor.delete_project` | `{project_id}` | `{success, deleted_id}` |
| `editor.add_node` | `{project_id, node: {...}}` | `{success, project_id, node: {...}}` |
| `editor.update_node` | `{project_id, node_id, node: {...}}` | `{success, project_id, node: {...}}` |
| `editor.delete_node` | `{project_id, node_id}` | `{success, project_id, deleted_node_id}` |
| `editor.add_edge` | `{project_id, edge: {...}}` | `{success, project_id, edge: {...}}` |
| `editor.update_edge` | `{project_id, edge_id, edge: {...}}` | `{success, project_id, edge: {...}}` |
| `editor.delete_edge` | `{project_id, edge_id}` | `{success, project_id, deleted_edge_id}` |
| `editor.validate` | `{project_id?, content?}` | `{valid, errors, warnings}` |
| `editor.export` | `{project_id, options?}` | `{success, content, format}` |
| `editor.import` | `{content, name?, description?}` | `{success, project: {...}}` |
| `editor.preview` | `{project_id, format?}` | `{success, content, format}` |
| `editor.auto_layout` | `{project_id, direction?}` | `{success, project: {...}}` |
| `editor.duplicate_node` | `{project_id, node_id, offset_x?, offset_y?}` | `{success, project_id, new_node: {...}}` |
| `editor.undo` | `{project_id}` | `{success, project: {...}}` |
| `editor.redo` | `{project_id}` | `{success, project: {...}}` |
| **Phase B.5: 測試框架** |
| `tests.list` | `{workflow_name?, tag?, type?}` | `{tests: [...], total}` |
| `tests.get` | `{test_id}` | `{test: {...}}` |
| `tests.create` | `{test: {...}}` | `{success, test: {...}}` |
| `tests.update` | `{test_id, test: {...}}` | `{success, test: {...}}` |
| `tests.delete` | `{test_id}` | `{success, deleted_id}` |
| `tests.run` | `{test_id, workflow_name?, input?}` | `{success, result: {...}, error?}` |
| `tests.run_many` | `{test_ids:[], workflow_name?, parallel?}` | `{success, results: [...], total, passed, failed, duration_ms}` |
| `tests.duplicate` | `{test_id, new_name?}` | `{success, new_test: {...}}` |
| `tests.coverage` | `{workflow_name, test_ids?}` | `{success, report: {...}}` |
| `tests.metrics` | `{workflow_name?, time_range?}` | `{metrics: {...}}` |
| `tests.history` | `{test_id?, limit?}` | `{executions: [...], total}` |
| `tests.suite.create` | `{name, description?, test_ids?, tags?}` | `{success, suite: {...}}` |
| `tests.suite.list` | `{tag?}` | `{suites: [...], total}` |
| `tests.suite.run` | `{suite_id, parallel?}` | `{success, result: {...}}` |
| `tests.suite.delete` | `{suite_id}` | `{success, deleted_id}` |

### 5.5 Streaming 事件類型

| 事件類型 | 用途 | 範例 |
|---------|------|------|
| `progress` | 一般進度訊息 | `{"type":"progress","message":"▶ Starting..."}` |
| `node` | 節點開始/完成 | `{"type":"node","node_name":"scan","action":"started"}` |
| `workflow` | 工作流生命週期 | `{"type":"workflow","action":"completed"}` |
| `branch` | 平行分支事件 | `{"type":"branch","branch_name":"security","action":"triggered"}` |
| `signal` | HITL 詢問 | `{"type":"signal","question":"What to check?","options":[...]}` |

### 5.6 Streaming 事件格式 (非 JSON-RPC)

Streaming 事件透過獨立的 stdout 發送（每行一個 JSON 物件）：

```json
{"type":"workflow","action":"started","workflow_name":"code-health"}
{"type":"progress","message":"▶ Starting workflow 'code-health'"}
{"type":"node","node_name":"scan","action":"started"}
{"type":"progress","message":"  ● Node 'scan'"}
{"type":"node","node_name":"scan","action":"completed","signal":"ready","signal_summary":"Signal 'ready' → moving to 'triage'"}
{"type":"progress","message":"    ⇢ Signal 'ready' → moving to 'triage'"}
{"type":"node","node_name":"triage","action":"started"}
{"type":"progress","message":"  ● Node 'triage'"}
{"type":"workflow","action":"completed","workflow_name":"code-health"}
```

---

## 6. 錯誤碼對照表

### 6.1 標準 JSON-RPC 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32600` | Invalid Request | 請求格式錯誤 |
| `-32601` | Method not found | 方法不存在 |
| `-32602` | Invalid params | 參數驗證失敗 |
| `-32603` | Internal error | 內部錯誤 |

### 6.2 自定義錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32000` | Workflow not found | workflow 不存在 |
| `-32001` | Node not found | 節點不存在 |
| `-32002` | Signal validation failed | 訊號不在白名單 |
| `-32003` | Permission denied | 權限不足 |
| `-32004` | Tool execution failed | 工具執行失敗 |
| `-32005` | Parallel branch timeout | 平行分支超時 |
| `-32006` | HITL timeout | 人類輸入超時 |

### 6.3 MCP 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32100` | MCP server not found | MCP 伺服器不存在 |
| `-32101` | MCP tool not found | MCP 工具不存在 |
| `-32102` | MCP connection failed | MCP 連線失敗 |
| `-32103` | MCP tool execution error | MCP 工具執行錯誤 |

### 6.4 Cron 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32200` | Cron not found | Cron 排程不存在 |
| `-32201` | Invalid cron string | Cron 表達式無效 |
| `-32202` | Cron workflow not found | 指定的 workflow 不存在 |

### 6.5 Hooks 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32400` | Hook not found | Hook 不存在 |
| `-32401` | Hook registration failed | Hook 註冊失敗 |
| `-32402` | Hook execution failed | Hook 執行失敗 |
| `-32403` | Invalid hook type | Hook 類型必須是 'command' 或 'http' |

### 6.6 版本管理錯誤碼 (Phase B.1)

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32800` | Version not found | Version 不存在 |
| `-32801` | Version already exists | Version 已存在 |
| `-32802` | Invalid version format | Version 格式無效（需符合 semantic versioning）|
| `-32803` | Version deprecated | Version 已被廢除 |
| `-32804` | Version max reached | 超過最大版本數限制 |

### 6.7 模板市場錯誤碼 (Phase B.2)

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32900` | Template not found | Template 不存在 |
| `-32901` | Template already exists | Template 已存在 |
| `-32902` | Template publish failed | Template 發布失敗 |
| `-32903` | Template download failed | Template 下載失敗 |
| `-32904` | Category not found | 分類不存在 |
| `-32905` | Invalid template metadata | Template 元資料無效 |
| `-32906` | Template rating failed | Template 評分失敗 |
| `-32907` | Template review failed | Template 評論失敗 |

### 6.8 視覺化編輯器錯誤碼 (Phase B.3)

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-33000` | Project not found | 專案不存在 |
| `-33001` | Node not found | 節點不存在 |
| `-33002` | Edge not found | 邊不存在 |
| `-33003` | Invalid node type | 節點類型無效 |
| `-33004` | Invalid edge | 邊無效 |
| `-33005` | Circular dependency | 循環依賴偵測 |
| `-33006` | YAML parse error | YAML 解析錯誤 |
| `-33007` | YAML serialize error | YAML 序列化錯誤 |
| `-33008` | Validation error | 驗證錯誤 |
| `-33009` | Project already exists | 專案已存在 |

### 6.9 測試框架錯誤碼 (Phase B.5)

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-33200` | Test not found | 測試不存在 |
| `-33201` | Test already exists | 測試已存在 |
| `-33202` | Test compile error | 測試編譯錯誤 |
| `-33203` | Test execution error | 測試執行錯誤 |
| `-33204` | Test assertion failed | 測試斷言失敗 |
| `-33205` | Test timeout | 測試超時 |
| `-33206` | Test suite not found | 測試套件不存在 |
| `-33207` | Test suite already exists | 測試套件已存在 |
| `-33208` | Test coverage error | 測試覆蓋率錯誤 |

---

## 7. 類型對照表

### 7.1 Python → TypeScript 類型映射

| Python (protocol.py) | TypeScript (workflow-daemon.ts) |
|-------------------|----------------------------|
| `JsonRpcRequest` | `JsonRpcRequest` |
| `JsonRpcResponse` | `JsonRpcResponse` |
| `WorkflowExecuteParams` | `WorkflowExecuteParams` |
| `WorkflowExecuteResult` | `WorkflowExecuteResult` |
| `WorkflowAudit` | `WorkflowAudit` (+ `parallel_branches`, `execution_id`) |
| `NodeExecution` | `NodeExecution` |
| `BranchExecution` | `BranchExecution` |
| `WorkflowListResult` | `WorkflowListResult` |
| `WorkflowValidateResult` | `WorkflowValidateResult` |
| `DaemonPingResult` | `DaemonPingResult` |
| `WorkflowRespondParams` | `WorkflowRespondParams` (HITL) |
| `ProgressEvent` | `ProgressEvent` |
| `HitlSignal` | `HitlSignalEvent` |
| `HitlQuestion` | `HitlQuestionOption` |
| `BranchEvent` | `BranchEvent` |
| `NodeEvent` | `NodeEvent` |
| `WorkflowEvent` | `WorkflowEvent` |

---

## 8. 測試腳本

### 8.1 Python 測試

```bash
PYTHONPATH=src uv run python examples/test-daemon.py
```

測試內容：
1. `daemon.ping` - 健康檢查
2. `workflow.list` - 列出 workflows
3. `workflow.execute` - 執行 workflow
4. `workflow.validate` - 驗證 workflow
5. 錯誤處理 - workflow not found

### 8.2 預期輸出

```
Starting Leeway daemon test...

1. Pinging daemon...
   ✅ Version: 0.1.0
   ✅ Status: healthy

2. Listing workflows...
   ✅ Available: code-health

3. Executing 'code-health' workflow...
   ✅ Success: True
   ✅ Output: Workflow 'code-health' executed successfully....
   ✅ Path: []
   ✅ Total turns: 0

4. Validating 'code-health' workflow...
   ✅ Valid: True

5. Testing workflow not found...
   ✅ Error code: -32000
   ✅ Error message: Workflow 'nonexistent' not found

✅ All tests passed!
```

---

## 9. 擴展指南

### 9.1 新增 JSON-RPC 方法

1. 在 `src/leeway_integration/protocol.py` 新增 Params/Result 類別
2. 在 `src/leeway_integration/daemon/core.py` 新增 `_method_name` 方法
3. 在 `_register_methods()` 中註冊
4. 在 `src/tools/workflow-daemon.ts` 新增對應的 TypeScript 方法

### 9.2 新增錯誤類別

1. 在 `src/leeway_integration/error.py` 新增錯誤類別
2. 在 `src/tools/workflow-daemon.ts` 新增對應的 TypeScript 類別

### 9.3 新增 Workflow

1. 在 `.leeway/workflows/` 新增 `.yaml` 檔案
2. 遵循 `code-health.yaml` 的結構定義

---

## 10. 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v0.1.0 | 2026-04-22 | 初始版本，完成 Phase 1 |
| v0.2.0 | 2026-04-22 | **Phase 2 完成**：Streaming, HITL, 新 workflows, skills 整合 |
| v0.3.0 | 2026-04-22 | **Phase 3.1 完成**：MCP 整合（GitHub, Filesystem, Brave Search）|
| v0.4.0 | 2026-04-22 | **Phase 3.2.1 完成**：Cron 排程（cron_create/list/delete/toggle）|
| v0.5.0 | 2026-04-22 | **Phase 3.2.2 完成**：Scheduler Daemon（後台定時執行）|
| v0.6.0 | 2026-04-22 | **Phase 3.3 完成**：Hooks 整合（Command hooks, HTTP hooks, HookRegistry）|
| v0.7.0 | 2026-04-22 | **Phase 3.4 完成**：自定義 Tool（Python tool authoring API）|
| v0.8.0 | 2026-04-22 | **Phase 3.5 完成**：Plugin 系統（PluginRegistry, 安裝/卸載）|
| v0.9.0 | 2026-04-22 | **Phase 4.1 完成**：錯誤處理與重試（自動重啟、超時處理、idempotent 重試）|
| v0.9.1 | 2026-04-22 | **Phase 4.2 完成**：效能優化（結果快取、冷啟動優化、tool result 快取）|
| v0.10.0 | 2026-04-22 | **Phase 4.4 完成**：監控與日誌（結構化日誌、metrics 收集、健康檢查端點）|
| v0.10.1 | 2026-04-22 | **Phase 4.3 完成**：安全加固（SecureConfig、PermissionChecker、AuditLogger）|
| v0.11.0 | 2026-04-22 | **Phase B.1 完成**：Workflow 版本管理（Semantic Versioning, 版本比較, 回滾）|
| v0.12.0 | 2026-04-22 | **Phase B.2 完成**：Workflow 模板市場（本地模板存儲、搜索、安裝、發布、評分、評論）|
| v0.13.0 | 2026-04-22 | **Phase B.3 完成**：Workflow 視覺化編輯器（專案管理、節點/邊操作、圖形驗證、Undo/Redo）|
| v0.14.0 | 2026-04-22 | **Phase B.4 完成**：多語言 LLM 支援（Anthropic, OpenAI, Google AI, Ollama, Llama.cpp Server）|
| v0.15.0 | 2026-04-22 | **Phase B.5 完成**：Workflow 測試框架（測試用例、測試套件、覆蓋率、度量）|
| v0.16.0 | 2026-04-22 | **Phase B.6 完成**：Workflow 效能分析（Performance Metrics、Slowest Nodes、Bottlenecks、Export）|

---

## 10.1 Hooks 章節

### Hooks 支援

Hooks 允許在 workflow 執行過程中的關鍵點執行自定義命令或 HTTP webhook。

### Hook 事件類型

| 事件 | 觸發時機 |
|------|---------|
| `workflow_start` | Workflow 開始執行 |
| `workflow_end` | Workflow 執行完成 |
| `node_start` | Node 開始執行 |
| `node_end` | Node 執行完成 |
| `before_tool_use` | Tool 執行前（預留）|
| `after_tool_use` | Tool 執行後（預留）|

### Hook 範圍

| 範圍 | 說明 |
|------|------|
| `global` | 全域，所有 workflow 都觸發 |
| `workflow` | 特定 workflow |
| `node` | 特定 workflow 的特定 node |

### Hooks JSON-RPC 方法

| 方法 | 參數 | 返回 |
|------|------|------|
| `hooks.list` | `scope?, workflow_name?, event?` | `{hooks: [...]}` |
| `hooks.register` | `{name, scope, event, workflow_name?, node_name?, command?, http?}` | `{success, hook, error}` |
| `hooks.unregister` | `{hook_id}` | `{success, deleted_id, error}` |
| `hooks.toggle` | `{hook_id, enabled}` | `{success, hook, error}` |
| `hooks.execute` | `{hook_id, context?}` | `{success, result, error}` |

### Hooks 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32400` | Hook not found | Hook 不存在 |
| `-32401` | Hook registration failed | Hook 註冊失敗 |
| `-32402` | Hook execution failed | Hook 執行失敗 |
| `-32403` | Invalid hook type | Hook 類型無效 |

### Hooks 支援

Hooks 允許在 workflow 執行過程中的關鍵點執行自定義命令或 HTTP webhook。

### Hook 事件類型

| 事件 | 觸發時機 |
|------|---------|
| `workflow_start` | Workflow 開始執行 |
| `workflow_end` | Workflow 執行完成 |
| `node_start` | Node 開始執行 |
| `node_end` | Node 執行完成 |
| `before_tool_use` | Tool 執行前（預留）|
| `after_tool_use` | Tool 執行後（預留）|

### Hook 範圍

| 範圍 | 說明 |
|------|------|
| `global` | 全域，所有 workflow 都觸發 |
| `workflow` | 特定 workflow |
| `node` | 特定 workflow 的特定 node |

### Hooks JSON-RPC 方法

| 方法 | 參數 | 返回 |
|------|------|------|
| `hooks.list` | `scope?, workflow_name?, event?` | `{hooks: [...]}` |
| `hooks.register` | `{name, scope, event, workflow_name?, node_name?, command?, http?}` | `{success, hook, error}` |
| `hooks.unregister` | `{hook_id}` | `{success, deleted_id, error}` |
| `hooks.toggle` | `{hook_id, enabled}` | `{success, hook, error}` |
| `hooks.execute` | `{hook_id, context?}` | `{success, result, error}` |

### Hooks 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32400` | Hook not found | Hook 不存在 |
| `-32401` | Hook registration failed | Hook 註冊失敗 |
| `-32402` | Hook execution failed | Hook 執行失敗 |
| `-32403` | Invalid hook type | Hook 類型無效 |


## 11.1 Custom Tools 章節

允許使用者編寫和註冊自定義的 Python 工具，在 workflow 中使用。

### Tool 結構

每個自定義 tool 由以下部分組成：
- `name`: 工具名稱
- `description`: 工具描述
- `code`: Python 程式碼（定義 `execute`/`run`/`main` 函數）
- `parameters`: 參數定義列表
- `version`: 版本號
- `tags`: 標籤列表

### Tool 範例

```python
def execute(operation: str, a: float, b: float = 0) -> dict:
    """A simple calculator tool."""
    if operation == "add":
        return {"result": a + b}
    return {"error": "Unknown operation"}
```

### Tools JSON-RPC 方法

| 方法 | 參數 | 返回 |
|------|------|------|
| `tools.list` | `tag?` | `{tools: [...]}` |
| `tools.register` | `{name, description, code, parameters?, version?, tags?}` | `{success, tool, error}` |
| `tools.unregister` | `{tool_id}` | `{success, deleted_id, error}` |
| `tools.toggle` | `{tool_id, enabled}` | `{success, tool, error}` |
| `tools.execute` | `{name, arguments}` | `{success, result, error, execution_time_ms}` |
| `tools.get` | `{tool_id}` | `{tool: {...}}` |
| `tools.validate` | `{code}` | `{valid, errors}` |

### Tools 錯誤碼

| 錯誤碼 | 名稱 | 說明 |
|--------|------|------|
| `-32500` | Tool not found | Tool 不存在 |
| `-32501` | Tool registration failed | Tool 註冊失敗 |
| `-32502` | Tool execution error | Tool 執行錯誤 |
| `-32503` | Tool validation error | Tool 驗證失敗（代碼錯誤）|
| `-32504` | Tool already exists | Tool 已存在 |

---

## 11.2 快速參考

### 11.1 常用命令

```bash
# 測試 Python daemon
PYTHONPATH=src uv run python examples/test-daemon.py

# 測試 Streaming 功能
PYTHONPATH=src uv run python examples/test-streaming.py

# 測試 Scheduler Daemon
PYTHONPATH=src uv run python examples/test-scheduler.py

# 執行 Python daemon
PYTHONPATH=src uv run python -m leeway_integration.daemon.core --workflows-dir .leeway/workflows

# 列出 workflows
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.list","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 執行 workflow
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.execute","params":{"name":"code-health","user_context":"test"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Cron 操作
# 列出排程
echo '{"jsonrpc":"2.0","id":"1","method":"cron.list","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 建立排程
echo '{"jsonrpc":"2.0","id":"1","method":"cron.create","params":{"name":"daily-check","workflow_name":"code-health","cron_expression":"0 9 * * *"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Scheduler Daemon 操作
# 啟動 scheduler daemon
echo '{"jsonrpc":"2.0","id":"1","method":"scheduler.start","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 查看 scheduler 狀態
echo '{"jsonrpc":"2.0","id":"1","method":"scheduler.status","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 查看執行歷史
echo '{"jsonrpc":"2.0","id":"1","method":"scheduler.executions","params":{"limit":10}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Hooks 操作
# 列出 hooks
echo '{"jsonrpc":"2.0","id":"1","method":"hooks.list","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 註冊 command hook
echo '{"jsonrpc":"2.0","id":"1","method":"hooks.register","params":{"name":"log-start","scope":"global","event":"workflow_start","command":{"command":"echo","args":["Starting"]}}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 註冊 HTTP hook (webhook)
echo '{"jsonrpc":"2.0","id":"1","method":"hooks.register","params":{"name":"notify-end","scope":"workflow","event":"workflow_end","workflow_name":"code-health","http":{"url":"https://example.com/webhook","method":"POST"}}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Custom Tools 操作
# 列出自定義 tools
echo '{"jsonrpc":"2.0","id":"1","method":"tools.list","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 註冊自定義 tool
echo '{"jsonrpc":"2.0","id":"1","method":"tools.register","params":{"name":"my-tool","description":"My custom tool","code":"def execute(msg: str) -> dict:\\n    return {\"result\": msg}"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 執行自定義 tool
echo '{"jsonrpc":"2.0","id":"1","method":"tools.execute","params":{"name":"my-tool","arguments":{"msg":"Hello!"}}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 驗證 tool code
echo '{"jsonrpc":"2.0","id":"1","method":"tools.validate","params":{"code":"def execute(x: int) -> dict:\\n    return {\"result\": x}"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Version Management 操作
# 列出 workflow 版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.list","params":{"workflow_name":"code-health"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 創建新版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.create","params":{"workflow_name":"code-health","version":"1.1.0","changelog":"Added new node","set_default":true}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 設定預設版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.set_default","params":{"workflow_name":"code-health","version":"1.0.0"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 廢除版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.deprecate","params":{"workflow_name":"code-health","version":"1.0.0"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 比較版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.compare","params":{"workflow_name":"code-health","version_a":"1.0.0","version_b":"1.1.0"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 回滾到舊版本
echo '{"jsonrpc":"2.0","id":"1","method":"workflow.version.rollback","params":{"workflow_name":"code-health","target_version":"1.0.0","changelog":"Rollback"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# Template Marketplace 操作
# 列出模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.list","params":{"sort_by":"popular"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 搜索模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.search","params":{"query":"security","category":"security"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 列出分類
echo '{"jsonrpc":"2.0","id":"1","method":"templates.categories","params":{}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 發布模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.publish","params":{"name":"my-workflow","description":"A custom workflow","category":"custom","content":"scan:\\n  prompt: \"Scan...\"","version":"1.0.0"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 安裝模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.install","params":{"template_id":"my-workflow","name":"installed-workflow"}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 評分模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.rate","params":{"template_id":"my-workflow","rating":5}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 評論模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.review","params":{"template_id":"my-workflow","rating":5,"title":"Great template!","content":"This template is very useful."}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core

# 獲取精選模板
echo '{"jsonrpc":"2.0","id":"1","method":"templates.featured","params":{"limit":10}}' | \
  PYTHONPATH=src uv run python -m leeway_integration.daemon.core
```

### 11.2 關鍵檔案行數

| 檔案 | 行數 | 用途 |
|------|------|------|
| `protocol.py` | ~1800 | 類型定義 + Streaming + MCP + Cron + Scheduler + Hooks + Custom Tools + Version Management + Template Marketplace + Visual Editor |
| `error.py` | ~570 | 錯誤定義 + MCP + Cron + Scheduler + Hooks + Custom Tools + Version Management + Template Marketplace + Visual Editor 錯誤 |
| `daemon/core.py` | ~8200 | Daemon 核心 + Streaming + HITL + MCP + Cron + Scheduler + Hooks + Custom Tools + Version Management + Template Marketplace + Visual Editor |
| `workflow-daemon.ts` | ~2050 | TS 通訊層 + Streaming + MCP + Cron + 自動重啟 + 超時處理 + 重試 + Template Marketplace + Visual Editor |
| `workflow.ts` | 243 | TS Tool |
| `code-health.yaml` | 122 | 範例 workflow |
| `api-design.yaml` | 90 | API 設計 workflow |
| `pr-review.yaml` | 100 | PR 審查 workflow |
| `security-scan.yaml` | 95 | 安全掃描 workflow |
| `github-search.yaml` | ~50 | GitHub 搜尋 workflow (MCP) |
| `research-assistant.yaml` | ~65 | 多來源研究 workflow (MCP) |

### 11.3 Phase 4.1 新增功能

#### 4.1.1 Daemon 自動重啟
- `autoRestart`: 啟用/停用自動重啟（預設 true）
- `maxAutoRestarts`: 最大重啟次數（預設 5 次）
- 指數退避重啟演算法
- 健康狀態持續 5 分鐘後重置計數

#### 4.1.2 請求超時處理
- `methodTimeouts`: 方法級超時配置
  - `ping`: 5 秒
  - `workflowExecute`: 5 分鐘
  - `workflowList/validate`: 10 秒
  - `cron`: 30 秒
  - `mcp/hooks/tools`: 60 秒

#### 4.1.3 Idempotent 重試
- `enableResultCache`: 啟用結果緩存（預設 true）
- `cacheTtl`: 緩存過期時間（預設 5 分鐘）
- `retryBaseDelay`: 基礎退避延遲（預設 500ms）
- `retryMaxDelay`: 最大退避延遲（預設 30 秒）
- 請求去重：method + params 序列化 key
- 錯誤類型識別：可重試 vs 不可重試錯誤

#### 新增公開方法
- `clearCache()`: 清除請求緩存
- `getCacheStats()`: 獲取緩存統計
- `getAutoRestartCount()`: 獲取自動重啟計數
- `resetAutoRestartCount()`: 重置自動重啟計數
- `destroy()`: 停止 daemon 並清理資源

---

### 11.4 Phase 4.2 新增功能

#### 4.2.1 結果快取（ResultCache）

- **Python 端**：`ResultCache` 類別
  - 支援 TTL 過期（預設 5 分鐘）
  - 支援 cache key 生成（SHA256）
  - 支援命中/未命中統計
  - 支援 size limits 防止內存溢位
  - 執行緒安全操作

- **快取方法**：
  - `cache.get_stats()`: 獲取快取統計
  - `cache.clear()`: 清除所有快取
  - `cache.invalidate()`: 選擇性清除快取

#### 4.2.2 確定性方法快取

- **可快取方法**（cacheableMethods）：
  - `workflow.list` (TTL: 5 分鐘)
  - `workflow.validate` (TTL: 1 分鐘)
  - `mcp.servers` (TTL: 1 分鐘)
  - `cron.list` (TTL: 1 分鐘)
  - `scheduler.status` (TTL: 30 秒)
  - `hooks.list` (TTL: 1 分鐘)
  - `tools.list` (TTL: 5 分鐘)
  - `plugins.list` (TTL: 5 分鐘)

- **確定性方法快取**（deterministicMethods）：
  - `workflow.execute` (TTL: 10 分鐘) - 基於 name + user_context
  - `tools.execute` (TTL: 5 分鐘) - 基於 name + arguments

#### 4.2.3 冷啟動優化（Warmup）

- **daemon.warmup 方法**：
  - 預加載 workflow 定義
  - 可選擇預啟動 MCP 伺服器
  - 返回預加載的資源列表

- **TypeScript client 自動 warmup**：
  - daemon 啟動後自動呼叫 warmup
  - 可透過 `enableWarmup` 配置開關

#### 新增 JSON-RPC 方法

| 方法 | 參數 | 返回 |
|------|------|------|
| `cache.get_stats` | `{}` | `{size, hits, miss_rate, ...}` |
| `cache.clear` | `{}` | `{success, message}` |
| `cache.invalidate` | `method?, pattern?` | `{success, invalidated}` |
| `daemon.warmup` | `workflows?, preload_mcp?` | `{success, preloaded, message}` |

---

**最後更新**：2026-04-22
**維護者**：OpenCode AI Assistant

---

### 11.5 Phase B.2 模板市場功能

#### 11.5.1 模板市場概述

Workflow 模板市場允許使用者：
- **發布自定義模板**：將 workflow 發布到本地模板市場
- **搜索和發現**：按名稱、分類、標籤搜索模板
- **評分和評論**：對模板進行評分和評論
- **安裝模板**：將模板安裝到本地 workflows
- **管理分類**：10+ 預設分類（Code Quality, Security, Testing 等）

#### 11.5.2 預設分類

- `code-quality`: Code Quality (代碼品質檢查)
- `security`: Security (安全掃描)
- `testing`: Testing (測試)
- `documentation`: Documentation (文檔生成)
- `review`: Code Review (代碼審查)
- `devops`: DevOps (CI/CD)
- `data`: Data Processing (數據處理)
- `api`: API Development (API 開發)
- `research`: Research (研究)
- `custom`: Custom (自定義)

#### 11.5.3 模板類型

```typescript
interface TemplateMetadata {
  id: string;
  name: string;
  version: string;
  description: string;
  author: { name: string; email?: string; url?: string };
  license: string;
  tags: string[];
  category: string;
  homepage?: string;
  repository?: string;
  keywords: string[];
  min_leeway_version?: string;
  featured: boolean;
  verified: boolean;
}
```

#### 11.5.4 模板市場功能

- **本地模板存儲**：模板存儲在 `.leeway/templates/`
- **評分系統**：1-5 星評分，平均評分計算
- **評論系統**：用戶評論和評分
- **下載計數追蹤**：追蹤每個模板的下載次數
- **結果緩存支援**：templates.list, templates.categories, templates.featured 等方法支援結果緩存