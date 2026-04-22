# OpenCode × Leeway 整合設計文件

**版本**：v0.1.0
**日期**：2026-04-22
**狀態**：DRAFT
**作者**：OpenCode AI Assistant

---

## 1. 整合目標與背景

### 1.1 為什麼要整合 Leeway？

OpenCode 目前是一個自由發揮的 AI Agent，擅長探索性任務，但缺少「可定義、可審計、可重複」的工作流程能力。

Leeway 是一個基於 YAML 決策樹的工作流程驅動 AI Agent 框架：
- 每個節點是一個完整 agent 迴圈
- 人類定義圖結構，AI 在節點內部操作
- 透過 `workflow_signal` 訊號在節點間轉換
- 內建 21+ 工具、Skills、Hooks、MCP 支援

**整合目標**：讓 OpenCode 透過 `workflow` 工具呼叫執行 YAML 定義的工作流程，升級為「可引導的工作流程 Agent」。

### 1.2 適用場景

| 場景 | 說明 |
|------|------|
| Code Health Check | 對 code base 進行結構掃描、分類、審查、報告 |
| API Design Review | 設計審查、文件生成 |
| Security Audit | 安全漏洞掃描 |
| PR Review | Pull Request 審查 |
| 任意自定義流程 | 使用者定義的 YAML workflow |

---

## 2. 架構概覽

### 2.1 高層架構

```
┌─────────────────────────────────────────────────────────────┐
│  OpenCode Agent (TypeScript / Node.js)                            │
│                                                             │
│    ToolRegistry                                             │
│      ├─ read / edit / write                                 │
│      ├─ glob / grep                                         │
│      ├─ bash                                               │
│      ├─ web_fetch / web_search                              │
│      ├─ ...                                                │
│      └─ workflow ← NEW                                     │
│                                                             │
│    working_memory                                           │
│    core_memory                                             │
│                                                             │
│    SessionManager                                           │
└────┬──────────────────────────────────────────────────────────┘
     │  JSON-RPC 2.0 (stdin/stdout)
     │  subprocess spawn
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Leeway Daemon (Python subprocess)                          │
│                                                             │
│    WorkflowRegistry                                        │
│      ├─ parse_workflow()                                   │
│      ├─ load_workflow_registry()                          │
│      └─ WorkflowEngine.execute()                          │
│                                                             │
│    QueryEngine                                           │
│      ├─ run_query()                                     │
│      └─ submit_message()                                 │
│                                                             │
│    ToolRegistry (21+ tools)                               │
│      ├─ bash, read_file, write_file, edit_file            │
│      ├─ glob, grep                                       │
│      ├─ web_fetch, web_search                           │
│      ├─ ask_user_question, skill                      │
│      ├─ task_create, task_list, task_get, task_stop    │
│      ├─ cron_create, cron_list, cron_delete           │
│      ├─ agent, remote_trigger                        │
│      ├─ memory_read, memory_write                    │
│      └─ mcp_* (dynamic)                            │
│                                                             │
│    SkillRegistry                                         │
│    HookRegistry                                         │
│    PermissionChecker                                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 通訊架構

```
┌──────────────┐     stdin      ┌──────────────┐
│  OpenCode   │ ───────────► │   Leeway    │
│  (TS)      │              │  Daemon    │
│             │ ◄────────── │  (Python)  │
└──────────────┘    stdout    └──────────────┘
```

通訊協定：JSON-RPC 2.0 over stdin/stdout

---

## 3. 執行模式

### 3.1 兩種可選模式

| 模式 | 啟動方式 | 優點 | 缺點 |
|------|---------|------|------|
| **Long-running daemon** | 初始化時啟動一次 | 低延遲、session 持久 | 佔記憶體、需要管理生命週期 |
| **Ephemeral** | 每次 workflow 呼叫時啟動 | 無狀態隔離、簡單 | 每次啟動約 0.5-2s 延遲 |

**推薦**：Long-running daemon
- OpenCode 初始化時啟動 daemon
- workflow 工具透過 stdin/stdout 傳送 JSON-RPC
- daemon 異常時自動重啟

### 3.2 Daemon 生命週期

```
OpenCode 初始化
    │
    ▼
啟動 leeway-daemon subprocess
    │
    ▼
daemon.ping() → 驗證健康
    │
    ▼
主循環：接收 workflow.execute() 請求
    │
    ▼
(可選) OpenCode 關閉時終止 daemon
```

---

## 4. JSON-RPC 2.0 協定

### 4.1 OpenCode → Daemon（請求）

#### 4.1.1 Daemon 健康檢查

```json
{
  "jsonrpc": "2.0",
  "id": "ping-001",
  "method": "daemon.ping",
  "params": {}
}
```

#### 4.1.2 執行 Workflow

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "method": "workflow.execute",
  "params": {
    "name": "code-health",
    "user_context": "Check the codebase at /Users/wclin/project",
    "model": "claude-sonnet-4-7",
    "cwd": "/Users/wclin/project",
    "max_turns": 50,
    "interactive": false,
    "api_key": "sk-...",
    "base_url": "https://api.anthropic.com"
  }
}
```

#### 4.1.3 列出可用 Workflows

```json
{
  "jsonrpc": "2.0",
  "id": "wf-list-001",
  "method": "workflow.list",
  "params": {}
}
```

#### 4.1.4 驗證 Workflow 語法

```json
{
  "jsonrpc": "2.0",
  "id": "wf-validate-001",
  "method": "workflow.validate",
  "params": {
    "name": "code-health"
  }
}
```

#### 4.1.5 停止 Daemon

```json
{
  "jsonrpc": "2.0",
  "id": "stop-001",
  "method": "daemon.stop",
  "params": {}
}
```

### 4.2 Daemon → OpenCode（回應）

#### 4.2.1 成功回應

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "result": {
    "success": true,
    "final_output": "## Summary\n\nThe codebase uses...",
    "audit": {
      "workflow_name": "code-health",
      "path_taken": ["scan", "triage", "review", "report"],
      "node_executions": [
        {
          "node_name": "scan",
          "turns_used": 3,
          "tools_called": ["ask_user_question", "glob", "bash"]
        },
        {
          "node_name": "triage",
          "signal_decision": "ready",
          "signal_summary": "has_security_risk, missing_docs",
          "turns_used": 5,
          "tools_called": ["bash"]
        }
      ],
      "started_at": "2026-04-22T10:00:00Z",
      "completed_at": "2026-04-22T10:05:00Z",
      "total_turns": 18
    },
    "error": null
  }
}
```

#### 4.2.2 進度事件（Streaming）

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "result": {
    "type": "progress",
    "message": "▶ Starting workflow 'code-health' at node 'scan'"
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "result": {
    "type": "progress",
    "message": "  ● Node 'scan'"
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "result": {
    "type": "progress",
    "message": "    ⇢ Signal 'ready' → moving to 'triage'"
  }
}
```

#### 4.2.3 錯誤回應

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "error": {
    "code": -32603,
    "message": "Workflow 'nonexistent' not found",
    "data": {
      "available": ["code-health", "api-design", "security-scan"]
    }
  }
}
```

### 4.3 Daemon → OpenCode（Workflow Signal / HITL）

當 workflow 節點需要使用者輸入時：

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "result": {
    "type": "signal",
    "node": "scan",
    "tool": "ask_user_question",
    "question": "What do you want to check?",
    "options": [
      {"label": "Everything", "description": "Full codebase scan"},
      {"label": "Backend only", "description": "Python/TypeScript files only"}
    ]
  }
}
```

OpenCode 回應（作為人類代理）：

```json
{
  "jsonrpc": "2.0",
  "id": "wf-001",
  "method": "workflow.respond",
  "params": {
    "answer": "Everything"
  }
}
```

### 4.4 Error Codes

| Code | 意義 | 說明 |
|------|------|------|
| `-32600` | Invalid Request | JSON-RPC 請求格式錯誤 |
| `-32601` | Method not found | 不支援的方法 |
| `-32602` | Invalid params | 參數驗證失敗 |
| `-32603` | Internal error | Python daemon 內部錯誤 |
| `-32000` | Workflow not found | 指定的 workflow 不存在 |
| `-32001` | Node not found | 節點不存在 |
| `-32002` | Signal validation failed | 訊號不在白名單 |
| `-32003` | Permission denied | 權限檢查失敗 |
| `-32004` | Tool execution failed | 工具執行失敗 |
| `-32005` | Parallel branch timeout | 平行分支超時 |
| `-32006` | HITL timeout | 人類輸入超時 |

---

## 5. OpenCode workflow Tool 介面

### 5.1 TypeScript 定義

```typescript
// 位置：src/tools/workflow.ts

interface WorkflowExecuteParams {
  /** Workflow 名稱（不含 .yaml 副檔名） */
  name: string;

  /** 使用者提供的初始上下文 */
  user_context: string;

  /** 覆蓋預設模型 */
  model?: string;

  /** 工作目錄 */
  cwd?: string;

  /** 覆蓋每節點 max_turns */
  max_turns?: number;

  /** 是否允許人類互動（預設 false） */
  interactive?: boolean;
}

interface WorkflowResult {
  success: boolean;
  final_output: string;
  audit: WorkflowAudit;
  error: string | null;
}

interface WorkflowAudit {
  workflow_name: string;
  path_taken: string[];
  node_executions: NodeExecution[];
  started_at: string;
  completed_at: string;
  total_turns: number;
}

interface NodeExecution {
  node_name: string;
  signal_decision: string | null;
  signal_summary: string | null;
  turns_used: number;
  tools_called: string[];
  parallel_results?: Record<string, BranchExecution>;
}

interface BranchExecution {
  branch_name: string;
  triggered: boolean;
  approved: boolean;
  success: boolean;
  error: string | null;
  turns_used: number;
  tools_called: string[];
}
```

### 5.2 工具實現邏輯

```typescript
// src/tools/workflow.ts

class WorkflowTool implements BaseTool {
  name = "workflow";
  description = "Execute a YAML-defined workflow. "
    + "Each node is a full agent loop with tools. "
    + "Use this for repeatable, auditable multi-step tasks.";

  input_schema = {
    type: "object",
    properties: {
      name: { type: "string", description: "Workflow name" },
      user_context: { type: "string", description: "Initial context" },
      model: { type: "string", description: "Model override" },
      cwd: { type: "string", description: "Working directory" },
      max_turns: { type: "number", description: "Max turns per node" },
      interactive: { type: "boolean", description: "Allow human interaction" }
    },
    required: ["name", "user_context"]
  };

  async execute(params: WorkflowExecuteParams): Promise<ToolResult> {
    // 1. 確保 daemon 実行中
    await ensureDaemon();

    // 2. 發送 JSON-RPC 請求
    const response = await rpcCall("workflow.execute", params);

    // 3. 處理 streaming 進度事件
    for await (const event of response.events) {
      if (event.type === "progress") {
        console.log(event.message);
      }
    }

    // 4. 返回結果
    return response.result;
  }
}
```

---

## 6. Workflow 目錄結構

### 6.1 預設Workflow 存放位置

```
~/.leeway/workflows/          # 全域 workflow（用戶級）
<project>/.leeway/workflows/  # 專案 workflow
```

### 6.2 OpenCode 整合後的位置

```
<opencode-root>/
│
├── .leeway/
│   ├── workflows/
│   │   ├── code-health.yaml
│   │   ├── api-design.yaml
│   │   ├── security-audit.yaml
│   │   └── pr-review.yaml
│   │
│   ├── skills/
│   │   ├── coding-standards/
│   │   │   └── SKILL.md
│   │   ├── code-review/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   │       └── checklist.md
│   │   └── security-audit/
│   │       ├── SKILL.md
│   │       └── references/
│   │           └── owasp.md
│   │
│   └── settings.json
│
├── src/
│   └── tools/
│       └── workflow.ts
│
└── leeway-daemon.py
```

### 6.3 settings.json 配置

```json
{
  "api_key": "",
  "base_url": "https://api.anthropic.com",
  "model": "claude-sonnet-4-7",
  "permission_mode": "default",
  "workflows_dir": ".leeway/workflows",
  "skills_dir": ".leeway/skills",
  "max_turns": 50,
  "max_tokens": 16384,
  "verbose": false
}
```

---

## 7. Workflow 語法（快速參考）

### 7.1 五種節點模式

**Linear（線性）**：

```yaml
scan:
  prompt: "Scan the project structure."
  tools: [glob, bash]
  edges:
    - target: assess
      when: { always: true }
```

**Branch（分支）**：

```yaml
assess:
  prompt: "Signal 'well_documented', 'needs_investigation', or 'trivial'."
  edges:
    - target: deep_dive
      when: { signal: needs_investigation }
    - target: summarize
      when: { signal: well_documented }
```

**Loop（循環）**：

```yaml
deep_dive:
  prompt: "Read key files. Signal 'dig_deeper' to loop."
  edges:
    - target: deep_dive
      when: { signal: dig_deeper }
    - target: summarize
      when: { signal: enough }
```

**Terminal（終端）**：

```yaml
summarize:
  prompt: "Write a summary."
  # no edges = terminal node
```

**Parallel（平行）**：

```yaml
review:
  parallel:
    branches:
      quality:
        when: { always: true }
        prompt: "Review code quality"
        tools: [grep, glob]
      security:
        when: { signal: security_risk }
        prompt: "Security audit"
        requires_approval: true
  edges:
    - target: report
      when: { always: true }
```

### 7.2 訊號驗證

每個節點宣告允許的訊號，LLM 只能發射白名單內的訊號：

```yaml
assess:
  prompt: "Review and decide."
  edges:
    - target: deep_dive
      when: { signal: needs_investigation }  # 只有這個訊號有效
    - target: summarize
      when: { signal: well_documented }
```

如果 LLM 發射不在白名單的訊號，runtime 會攔截錯誤。

---

## 8. 逐步整合路徑

### Phase 1：最小可行整合（MVI）

| 步驟 | 任務 | 說明 |
|------|------|------|
| 1.1 | 安裝 Leeway 依賴 | `uv add leeway` |
| 1.2 | 創建 leeway-daemon.py | JSON-RPC daemon |
| 1.3 | 創建 workflow Tool | OpenCode 端工具 |
| 1.4 | 添加 example workflow | code-health.yaml |
| 1.5 | 測試端到端執行 | 驗證完整流程 |

### Phase 2：功能增強

| 步驟 | 任務 | 說明 |
|------|------|------|
| 2.1 | 實現 streaming | 進度事件即時顯示 |
| 2.2 | 實現 HITL | 人類互動閘門 |
| 2.3 | 添加更多 workflows | API design, PR review |
| 2.4 | 添加 Skills | code-review, security-audit |
| 2.5 | 實現 parallel 分支顯示 | 審計 Trail |

### Phase 3：深度整合

| 步驟 | 任務 | 說明 |
|------|------|------|
| 3.1 | 實現 MCP 整合 | 外部 MCP 伺服器 |
| 3.2 | 實現 Cron 排程 | 自動化 workflow |
| 3.3 | 實現 Hooks | HTTP / command callbacks |
| 3.4 | 實現自定義 Tool | Python tool authoring |
| 3.5 | 實現 Plugin 系統 | 可分發的 workflow bundle |

---

## 9. 風險與緩解

### 9.1 風險identified

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| Python subprocess 異常 | workflow 無法執行 | daemon 健康檢查與自動重啟 |
| JSON-RPC 通訊超時 | 請求卡住 | 設置 timeout，自動重試 |
| 权限绕过 | 安全問題 | 使用 Leeway permission checker |
| context 溢出 | workflow 失敗 | 使用 Leeway auto-compaction |
| workflow 語法錯誤 | parse 失敗 | 預先 validate |

### 9.2 非功能性考量

| 面向 | 考量 |
|------|------|
| 延遲 | 每次 workflow 執行約 5-30s（視複雜度） |
| 成本 | 每個 workflow 消耗視節點數與 max_turns |
| 可審計性 | audit trail 完整記錄 path、turns、tools |

---

## 10. 附錄

### 10.1 Leeway 原始碼閱讀清單

| 檔案 | 用途 |
|------|------|
| `src/leeway/cli.py` | CLI 入口 |
| `src/leeway/engine/query_engine.py` | QueryEngine |
| `src/leeway/workflow/engine.py` | WorkflowEngine |
| `src/leeway/workflow/parser.py` | parse_workflow() |
| `src/leeway/workflow/signal_tool.py` | workflow_signal tool |
| `src/leeway/tools/base.py` | BaseTool, ToolRegistry |
| `src/leeway/permissions/checker.py` | PermissionChecker |
| `src/leeway/skills/registry.py` | SkillRegistry |
| `src/leeway/hooks/__init__.py` | HookExecutor |
| `.leeway/workflows/code-health.yaml` | 完整 example |

### 10.2 參考資源

- Leeway GitHub: https://github.com/hardness1020/Leeway
- Leeway README: 完整功能說明
- `docs/workflows.md`: Workflow 語法
- `docs/tools.md`: 工具清單
- `docs/skills.md`: Skills 說明
- `docs/hooks.md`: Hooks 說明

---

## 11. 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v0.1.0 | 2026-04-22 | 初始版本 |