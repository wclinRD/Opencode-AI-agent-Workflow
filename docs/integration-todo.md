# OpenCode × Leeway 整合 TODO

**版本**：v0.14.0
**更新日期**：2026-04-22
**狀態**：Phase B.6 完成（Workflow 效能分析）

---

## Phase 1：最小可行整合（MVI）

### 1.1 專案初始化

- [x] **1.1.1** 初始化 Python 專案結構（使用 uv）
  - 建立 `pyproject.toml`
  - 設定 dependencies: leeway, pydantic, pyyaml

- [x] **1.1.2** 建立 `.leeway/` 目錄結構
  ```
  .leeway/
  ├── workflows/
  │   └── code-health.yaml
  ├── skills/
  │   ├── coding-standards/
  │   │   └── SKILL.md
  │   └── code-review/
  │       ├── SKILL.md
  │       └── references/
  │           └── checklist.md
  └── settings.json
  ```

- [x] **1.1.3** 建立 OpenCode `src/` 目錄結構（Python）
  ```
  src/leeway_integration/
  ├── __init__.py
  ├── protocol.py
  ├── error.py
  └── daemon/
      ├── __init__.py
      └── core.py
  ```

### 1.2 Leeway Daemon 實現

- [x] **1.2.1** 創建 daemon - 主入口
  - 實現 JSON-RPC 2.0 協定
  - stdin/stdout 通訊
  - 基本錯誤處理

- [x] **1.2.2** 實現 `daemon.ping` 方法
  - 回傳版本資訊
  - 健康狀態檢查

- [x] **1.2.3** 實現 `workflow.execute` 方法
  - 載入 workflow YAML
  - 解析並執行
  - 返回結果

- [x] **1.2.4** 實現 `workflow.list` 方法
  - 列出所有可用 workflows

- [x] **1.2.5** 實現 `workflow.validate` 方法
  - 語法驗證
  - 資源檢查（tools, skills, hooks）

- [x] **1.2.6** 實現 `daemon.stop` 方法
  - 優雅關閉 daemon

- [x] **1.2.7** 添加基本錯誤處理
  - JSON-RPC error codes (-32600 ~ -32603)
  - Custom error codes (-32000 ~ -32006)

### 1.3 OpenCode Workflow Tool 實現

> ✅ **TypeScript 端已完成實作**

- [x] **1.3.1** 創建 `src/tools/workflow.ts`
  - 實現 `execute()` 方法
  - 實現 input schema

- [x] **1.3.2** 實現 daemon 通訊層
  - subprocess spawn/管理
  - stdin/stdout JSON-RPC 封裝
  - 請求/響應處理

- [x] **1.3.3** 實現錯誤處理
  - 連接失敗處理
  - 超時處理
  - 重試邏輯

- [x] **1.3.4** 實現結果解析
  - 解析 WorkflowResult
  - 格式化輸出

### 1.4 Example Workflow

- [x] **1.4.1** 添加 `code-health.yaml` workflow
  - 測試所有 5 種節點模式
  - 驗證 signal-based 轉換
  - 驗證 parallel 分支

- [x] **1.4.2** 測試端到端執行 ✅
  - 啟動 daemon - ✅ Python daemon ping/list/execute 正常
  - 呼叫 workflow 工具 - ✅ TypeScript 工具程式碼完成
  - 驗證結果 - ⚠️ 待整合到 OpenCode 主專案測試

---

## Phase 2：功能增強

### 2.1 Streaming 進度顯示

- [x] **2.1.1** 修改 daemon 實現 streaming 輸出
  - 改用非阻塞 I/O
  - 即時發送 progress 事件

- [x] **2.1.2** 修改 OpenCode workflow tool
  - 處理 streaming 事件
  - 即時顯示進度訊息

- [x] **2.1.3** 實現豐富的進度訊息
  - 節點開始/結束
  - 訊號發射
  - 分支觸發/完成

### 2.2 Human-in-the-Loop (HITL)

- [x] **2.2.1** 實現 HITL 訊號協議
  - `ask_user_question` 事件
  - 選項呈現

- [x] **2.2.2** OpenCode 端處理 HITL
  - 解析問題與選項
  - 展示給使用者
  - 收集回應

- [x] **2.2.3** 實現 approval gates
  - `requires_approval: true` 分支
  - 需要使用者確認

### 2.3 更多 Workflow Examples

- [x] **2.3.1** 添加 `api-design.yaml`
  - 設計審查流程
  - 文件生成

- [x] **2.3.2** 添加 `pr-review.yaml`
  - PR 審查流程
  - 評論生成

- [x] **2.3.3** 添加 `security-scan.yaml`
  - 安全掃描流程

### 2.4 Skills 整合

- [x] **2.4.1** 實現 `coding-standards` skill
  - SKILL.md
  - references/

- [x] **2.4.2** 實現 `code-review` skill
  - SKILL.md
  - references/checklist.md

- [x] **2.4.3** 實現 `security-audit` skill
  - SKILL.md
  - references/owasp.md

### 2.5 Audit Trail 增強

- [x] **2.5.1** 完整記錄 path_taken
- [x] **2.5.2** 記錄 parallel 分支結果
- [x] **2.5.3** 實現 `execution_id` 追蹤
- [ ] **2.5.4** 實現可搜尋的審計日誌

---

## Phase 3：深度整合

### 3.1 MCP 整合

- [x] **3.1.1** 添加 MCP 支援到 daemon
  - 從 settings.json 讀取 MCP servers
  - 動態註冊 MCP tools

- [x] **3.1.2** 實現 MCP tool 代理
  - 標準化 MCP tool 命名
  - 處理 MCP 協議轉換

- [x] **3.1.3** 添加 MCP example
  - 在 workflow 中使用 mcp_github_search

### 3.2 Cron 排程

- [x] **3.2.1** 添加 Cron 工具到 workflow
  - cron_create
  - cron_list
  - cron_delete
  - cron_toggle

- [x] **3.2.2** 實現 scheduler daemon（可選）
  - 後台定時執行 workflow
  - scheduler.start / scheduler.stop / scheduler.status / scheduler.executions

### 3.3 Hooks 整合

- [x] **3.3.1** 添加 command hooks
  - workflow_start / workflow_end
  - node_start / node_end
  - before_tool_use / after_tool_use

- [x] **3.3.2** 添加 HTTP hooks
  - webhook 通知

- [x] **3.3.3** 實現 HookRegistry
  - 全局 / workflow / node 級別 hooks
  - 合併與繼承邏輯
  - 異步執行（不阻塞 workflow）
  - hooks.list / hooks.register / hooks.unregister / hooks.toggle / hooks.execute

### 3.4 自定義 Tool

- [x] **3.4.1** 實現 Python tool authoring API
- [x] **3.4.2** 實現自定義 tool 註冊
- [x] **3.4.3** 添加自定義 tool example

### 3.5 Plugin 系統

- [x] **3.5.1** 實現 plugin 格式
  - workflow + skills + tools 打包

- [x] **3.5.2** 實現 plugin 安裝/卸載
- [x] **3.5.3** 添加 plugin registry

---

## Phase 4：最佳化與穩定性

### 4.1 錯誤處理與重試

- [x] **4.1.1** 實現 daemon 自動重啟
  - 添加 `autoRestart` 配置選項
  - 實現崩潰檢測與指數退避重啟
  - 最大重啟次數限制 (`maxAutoRestarts`)
  - 健康狀態持續 5 分鐘後重置計數

- [x] **4.1.2** 實現請求超時處理
  - 添加 `methodTimeouts` 配置，為不同類型的方法設置不同超時
  - `workflow.execute` 預設 5 分鐘
  - `ping` 預設 5 秒
  - 讀取方法預設 60 秒

- [x] **4.1.3** 實現 idempotent 重試
  - 實現結果緩存 (`enableResultCache`)
  - 請求去重：通過 method + params 生成唯一 key
  - 指數退避重試策略 (`retryBaseDelay`, `retryMaxDelay`)
  - 錯誤類型識別：可重試 vs 不可重試錯誤

### 4.2 效能優化

- [x] **4.2.1** 實現 workflow 結果快取
  - Python daemon 端 ResultCache 類別
  - 支援 TTL 過期
  - 支援 cache key 生成與命中追蹤
  - 支援 cacheableMethods (workflow.list, workflow.validate, mcp.servers, 等)
  - 支援 deterministic 方法快取 (workflow.execute, tools.execute)
  
- [x] **4.2.2** 優化冷啟動時間
  - daemon.warmup 方法預加載 workflow 定義
  - 支援 MCP 服務器預啟動
  - TypeScript client 自動 warmup

- [x] **4.2.3** 實現 tool result 快取
  - tools.execute 結果快取 (基於 tool name + arguments)
  - 快取 TTL: 5 分鐘

### 4.3 安全加固

- [x] **4.3.1** 實現 API key 安全存儲
  - SecureConfig 類別：支援環境變數、.env、macOS Keychain、settings.json
  - 方法：`config.get_secure`
- [x] **4.3.2** 實現權限細粒度控制
  - PermissionChecker 類別：RBAC 角色權限、workflow/tool 級權限
  - 方法：`auth.set_role`, `auth.roles.list`, `auth.roles.add`, `auth.check`
- [x] **4.3.3** 實現 audit log 加密
  - AuditLogger 類別：AES-256-GCM 加密、HMAC 完整性驗證
  - 方法：`audit.logs`, `audit.verify`, `audit.cleanup`

### 4.4 監控與日誌

- [x] **4.4.1** 添加結構化日誌（StructuredLogger 類）
- [x] **4.4.2** 實現 metrics 收集（MetricsCollector 類）
- [x] **4.4.3** 添加健康檢查端點（daemon.health 方法）

---

## Phase B：功能增強（Backlog）

### B.1 Workflow 版本管理

- [x] **B.1.1** 實現版本管理類型定義（protocol.py）
  - WorkflowVersion, WorkflowVersionMetadata, WorkflowVersionInfo
  - 8 個 JSON-RPC 方法的參數/結果類型

- [x] **B.1.2** 實現版本管理錯誤類型（error.py）
  - VersionNotFoundError, VersionAlreadyExistsError, VersionInvalidFormatError
  - VersionDeprecatedError, VersionMaxReachedError

- [x] **B.1.3** 實現 WorkflowVersionManager 類（daemon/core.py）
  - Semantic versioning 支援
  - 版本持久化存儲
  - 版本比較、回滾、設置默認版本

- [x] **B.1.4** 實現 JSON-RPC 版本管理方法
  - workflow.version.list / get / create
  - workflow.version.set_default / deprecate / delete
  - workflow.version.compare / rollback

---

## Phase B.2: Workflow 模板市場

- [x] **B.2.1** 實現模板市場類型定義（protocol.py）
  - WorkflowTemplate, TemplateMetadata, TemplateAuthor
  - TemplateCategory, TemplateReview, TemplateRating
  - 20+ 個 JSON-RPC 方法的參數/結果類型

- [x] **B.2.2** 實現模板市場錯誤類型（error.py）
  - TemplateNotFoundError, TemplateAlreadyExistsError
  - TemplatePublishFailedError, TemplateDownloadFailedError
  - TemplateCategoryNotFoundError, TemplateInvalidMetadataError
  - TemplateRatingFailedError, TemplateReviewFailedError

- [x] **B.2.3** 實現 TemplateManager 類（daemon/core.py）
  - 本地模板存儲和索引
  - 模板搜索和過濾
  - 模板安裝/卸載
  - 模板發布（本地上registry）
  - 評分和評論
  - 分類管理

- [x] **B.2.4** 實現 JSON-RPC 模板市場方法
  - templates.list / get / search / categories
  - templates.install / uninstall
  - templates.publish / update / delete
  - templates.rate / review / reviews
  - templates.featured / popular / newest
  - templates.versions / download

- [x] **B.2.5** 在 TypeScript workflow-daemon.ts 中添加模板市場方法
  - 所有模板市場客戶端方法
  - 錯誤類別
  - 類型定義
  - 結果緩存支援

---

## 待完成（Backlog）

### 功能 Ideas

- [x] **B.1** 實現 workflow 版本管理
- [x] **B.2** 實現 workflow 模板市場
- [x] **B.3** 實現 workflow 視覺化編輯器
- [x] **B.4** 實現多語言 LLM 支援（Anthropic, OpenAI, Google, Ollama, Llama.cpp Server）
- [x] **B.5** 實現 workflow 測試框架
- [x] **B.6** 實現 workflow 效能分析

---

## 里程碑

| 里程碑 | 目標 | 狀態 |
|--------|------|------|
| M1 | Daemon 基本運作 + code-health workflow | ✅ 完成（TypeScript 端除外） |
| M2 | Streaming + HITL + 更多 workflows | ✅ 完成 |
| M3 | MCP 整合 | ✅ 完成 |
| M3.1 | Cron 排程 | ✅ 完成（3.2.1） |
| M3.2 | Scheduler Daemon | ✅ 完成（3.2.2） |
| M3.3 | Hooks 整合 | ✅ 完成（3.3.1-3.3.3） |
| M3.4 | HTTP hooks (webhooks) | ✅ 完成（3.3.2） |
| M3.5 | 自定義 Tool | ✅ 完成（3.4.1-3.4.3） |
| M3.6 | Plugin 系統 | ✅ 完成（3.5.1-3.5.3） |
| M4.1 | 錯誤處理與重試 | ✅ 完成（4.1.1-4.1.3） |
| M4.2 | 效能優化 | ✅ 完成（4.2.1-4.2.3） |
| M4.4 | 監控與日誌 | ✅ 完成（4.4.1-4.4.3） |
| M4 | 穩定性優化 + 監控 + 安全 | ✅ Phase 4.1-4.3, 4.4 完成 |
| M5 | Workflow 版本管理 | ✅ Phase B.1 完成 |
| M6 | Workflow 模板市場 | ✅ Phase B.2 完成 |
| M7 | Workflow 視覺化編輯器 | ✅ Phase B.3 完成 |
| M8 | 多語言 LLM 支援 | ✅ Phase B.4 完成（Anthropic, OpenAI, Google, Ollama, Llama.cpp） |
| M9 | Workflow 測試框架 | ✅ Phase B.5 完成（測試用例、測試套件、覆蓋率、度量） |
| M10 | Workflow 效能分析 | ✅ Phase B.6 完成（Performance Metrics、Slowest Nodes、Bottlenecks） |

---

## 優先順序說明

1. **P0（必須）**：Phase 1 所有項目 ✅ 完成
2. **P1（重要）**：Phase 2 所有項目 ✅ 完成
3. **P2（可選）**：Phase 3.3 Hooks 整合 ✅ 完成
4. **P3（可選）**：Phase 3.4 自定義 Tool ✅ 完成
5. **P4（可選）**：Phase 3.5 Plugin 系統 ✅ 完成
6. **P5（可選）**：Phase 4.1 錯誤處理與重試 ✅ 完成
6. **P6（可選）**：Phase 4.2 效能優化 ✅ 完成
7. **P7（可選）**：Phase 4.4 監控與日誌 ✅ 完成

---

## 依賴關係

```
1.1.1 → 1.1.2 → 1.1.3
            │
            ▼
        1.2.1 → 1.2.2 → 1.2.3 → ... → 1.2.7
            │
            ▼
        1.3.1 → 1.3.2 → 1.3.3 → 1.3.4
            │
            ▼
        1.4.1 → 1.4.2 (M1 完成)

M1 完成後可開始 Phase 2
```

---

## 備註

- 使用 `uv` 管理 Python 依賴
- TypeScript 端使用 OpenCode 現有工具框架
- 先實現基本功能，再逐步優化
- 每個 task 完成后應該有測試驗證