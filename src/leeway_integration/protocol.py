"""Leeway daemon protocol definitions."""

from typing import Any
from pydantic import BaseModel


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: dict = {}


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    id: str
    result: dict | None = None
    error: dict | None = None


class DaemonPingParams(BaseModel):
    """daemon.ping parameters."""
    pass


class DaemonPingResult(BaseModel):
    """daemon.ping result."""
    version: str
    status: str


class WorkflowExecuteParams(BaseModel):
    """workflow.execute parameters."""
    name: str
    user_context: str
    model: str | None = None
    cwd: str | None = None
    max_turns: int | None = None
    interactive: bool = False
    api_key: str | None = None
    base_url: str | None = None


class WorkflowExecuteResult(BaseModel):
    """workflow.execute result."""
    success: bool
    final_output: str
    audit: dict
    error: str | None = None


class WorkflowListParams(BaseModel):
    """workflow.list parameters."""
    pass


class WorkflowListResult(BaseModel):
    """workflow.list result."""
    workflows: list[str]


class WorkflowValidateParams(BaseModel):
    """workflow.validate parameters."""
    name: str


class WorkflowValidateResult(BaseModel):
    """workflow.validate result."""
    valid: bool
    errors: list[str] = []


class DaemonStopParams(BaseModel):
    """daemon.stop parameters."""
    pass


class WorkflowRespondParams(BaseModel):
    """workflow.respond parameters for HITL."""
    answer: str


class WorkflowRespondResult(BaseModel):
    """workflow.respond result."""
    received: bool
    answer: str


# Error codes
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
WORKFLOW_NOT_FOUND = -32000
NODE_NOT_FOUND = -32001
SIGNAL_VALIDATION_FAILED = -32002
PERMISSION_DENIED = -32003
TOOL_EXECUTION_FAILED = -32004
PARALLEL_BRANCH_TIMEOUT = -32005
HITL_TIMEOUT = -32006


# Streaming event types
class ProgressEvent(BaseModel):
    """Progress event for streaming output."""
    type: str = "progress"
    message: str
    node: str | None = None
    step: str | None = None


class HitlQuestion(BaseModel):
    """Human-in-the-loop question option."""
    label: str
    description: str


class HitlSignal(BaseModel):
    """HITL signal event - asking user for input."""
    type: str = "signal"
    node: str
    tool: str = "ask_user_question"
    question: str
    options: list[HitlQuestion] = []
    timeout: int | None = None


class BranchEvent(BaseModel):
    """Parallel branch event."""
    type: str = "branch"
    branch_name: str
    action: str  # "triggered", "completed", "approved"
    status: str = "pending"  # "pending", "running", "completed", "approved"


class NodeEvent(BaseModel):
    """Node execution event."""
    type: str = "node"
    node_name: str
    action: str  # "started", "completed", "failed"
    signal: str | None = None
    signal_summary: str | None = None


class WorkflowEvent(BaseModel):
    """Workflow lifecycle event."""
    type: str = "workflow"
    action: str  # "started", "completed", "failed", "stopped"
    workflow_name: str | None = None


# MCP Protocol Types
class McpServerConfig(BaseModel):
    """MCP server configuration."""
    command: str
    args: list[str]
    env: dict[str, str] | None = None


class McpToolCall(BaseModel):
    """MCP tool call request."""
    server_name: str
    tool_name: str
    arguments: dict = {}


class McpToolResult(BaseModel):
    """MCP tool call result."""
    success: bool
    result: Any = None
    error: str | None = None


class McpServerInfo(BaseModel):
    """MCP server information."""
    name: str
    status: str  # "running", "stopped", "error"
    tools_count: int = 0
    error: str | None = None


class McpListToolsParams(BaseModel):
    """mcp.list_tools parameters."""
    server_name: str | None = None


class McpListToolsResult(BaseModel):
    """mcp.list_tools result."""
    tools: list[dict]


class McpExecuteParams(BaseModel):
    """mcp.execute parameters."""
    server_name: str
    tool_name: str
    arguments: dict = {}


class McpExecuteResult(BaseModel):
    """mcp.execute result."""
    success: bool
    result: Any = None
    error: str | None = None


class McpServersParams(BaseModel):
    """mcp.servers parameters."""
    pass


class McpServersResult(BaseModel):
    """mcp.servers result."""
    servers: list[dict]


# MCP Error codes
MCP_SERVER_NOT_FOUND = -32100
MCP_TOOL_NOT_FOUND = -32101
MCP_CONNECTION_FAILED = -32102
MCP_TOOL_EXECUTION_ERROR = -32103


# Cron Error codes
CRON_NOT_FOUND = -32200
CRON_INVALID_CRONSTRING = -32201
CRON_WORKFLOW_NOT_FOUND = -32202


# Cron Schedule Types
class CronSchedule(BaseModel):
    """Cron schedule definition."""
    id: str
    name: str
    workflow_name: str
    cron_expression: str
    enabled: bool = True
    user_context: str | None = None
    next_run: str | None = None
    last_run: str | None = None
    created_at: str


class CronCreateParams(BaseModel):
    """cron.create parameters."""
    name: str
    workflow_name: str
    cron_expression: str
    user_context: str | None = None


class CronCreateResult(BaseModel):
    """cron.create result."""
    success: bool
    schedule: CronSchedule | None = None
    error: str | None = None


class CronListParams(BaseModel):
    """cron.list parameters."""
    pass


class CronListResult(BaseModel):
    """cron.list result."""
    schedules: list[CronSchedule]


class CronDeleteParams(BaseModel):
    """cron.delete parameters."""
    id: str


class CronDeleteResult(BaseModel):
    """cron.delete result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


class CronToggleParams(BaseModel):
    """cron.toggle parameters."""
    id: str
    enabled: bool


class CronToggleResult(BaseModel):
    """cron.toggle result."""
    success: bool
    schedule: CronSchedule | None = None
    error: str | None = None


# Scheduler Daemon Error codes
SCHEDULER_NOT_RUNNING = -32300
SCHEDULER_ALREADY_RUNNING = -32301
SCHEDULER_EXECUTION_FAILED = -32302


# Scheduler Daemon Types
class SchedulerExecution(BaseModel):
    """Execution record for a scheduled workflow run."""
    id: str
    schedule_id: str
    schedule_name: str
    workflow_name: str
    started_at: str
    completed_at: str | None = None
    success: bool | None = None
    output: str | None = None
    error: str | None = None


class SchedulerStatus(BaseModel):
    """Scheduler daemon status."""
    running: bool
    enabled_schedules: int
    total_schedules: int
    last_check: str | None = None
    executions_today: int = 0


class SchedulerStartParams(BaseModel):
    """scheduler.start parameters."""
    pass


class SchedulerStartResult(BaseModel):
    """scheduler.start result."""
    success: bool
    status: SchedulerStatus | None = None
    error: str | None = None


class SchedulerStopParams(BaseModel):
    """scheduler.stop parameters."""
    pass


class SchedulerStopResult(BaseModel):
    """scheduler.stop result."""
    success: bool
    error: str | None = None


class SchedulerStatusParams(BaseModel):
    """scheduler.status parameters."""
    pass


class SchedulerStatusResult(BaseModel):
    """scheduler.status result."""
    status: SchedulerStatus


class SchedulerExecutionsParams(BaseModel):
    """scheduler.executions parameters."""
    schedule_id: str | None = None
    limit: int = 10


class SchedulerExecutionsResult(BaseModel):
    """scheduler.executions result."""
    executions: list[SchedulerExecution]


# Hooks Error codes
HOOK_NOT_FOUND = -32400
HOOK_REGISTRATION_FAILED = -32401
HOOK_EXECUTION_FAILED = -32402
INVALID_HOOK_TYPE = -32403


# Hook Types
class HookType(str):
    """Hook type enumeration."""
    COMMAND = "command"
    HTTP = "http"


class HookEvent(str):
    """Hook event type enumeration."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    NODE_START = "node_start"
    NODE_END = "node_end"
    BEFORE_TOOL_USE = "before_tool_use"
    AFTER_TOOL_USE = "after_tool_use"


class HookScope(str):
    """Hook scope enumeration."""
    GLOBAL = "global"
    WORKFLOW = "workflow"
    NODE = "node"


class CommandHook(BaseModel):
    """Command hook definition."""
    type: str = HookType.COMMAND
    command: str
    args: list[str] = []
    env: dict[str, str] | None = None
    timeout: int = 30  # seconds


class HttpHook(BaseModel):
    """HTTP/webhook hook definition."""
    type: str = HookType.HTTP
    url: str
    method: str = "POST"
    headers: dict[str, str] | None = None
    body: dict | None = None
    timeout: int = 30  # seconds


class Hook(BaseModel):
    """Hook definition (union of command and http)."""
    id: str
    name: str
    scope: str  # "global", "workflow", "node"
    event: str  # "workflow_start", "workflow_end", "node_start", "node_end", "before_tool_use", "after_tool_use"
    workflow_name: str | None = None  # For workflow-level hooks
    node_name: str | None = None  # For node-level hooks
    enabled: bool = True
    command: CommandHook | None = None
    http: HttpHook | None = None


class HookExecutionContext(BaseModel):
    """Context passed to hook execution."""
    execution_id: str
    workflow_name: str
    node_name: str | None = None
    tool_name: str | None = None
    event: str
    data: dict = {}


class HookExecutionResult(BaseModel):
    """Result of hook execution."""
    hook_id: str
    success: bool
    output: str | None = None
    error: str | None = None
    exit_code: int | None = None
    http_status: int | None = None
    duration_ms: int = 0


# Hooks JSON-RPC Parameter/Result Types
class HooksListParams(BaseModel):
    """hooks.list parameters."""
    scope: str | None = None  # "global", "workflow", "node"
    workflow_name: str | None = None
    event: str | None = None


class HooksListResult(BaseModel):
    """hooks.list result."""
    hooks: list[dict]


class HooksRegisterParams(BaseModel):
    """hooks.register parameters."""
    name: str
    scope: str
    event: str
    workflow_name: str | None = None
    node_name: str | None = None
    command: CommandHook | None = None
    http: HttpHook | None = None


class HooksRegisterResult(BaseModel):
    """hooks.register result."""
    success: bool
    hook: dict | None = None
    error: str | None = None


class HooksUnregisterParams(BaseModel):
    """hooks.unregister parameters."""
    hook_id: str


class HooksUnregisterResult(BaseModel):
    """hooks.unregister result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


class HooksToggleParams(BaseModel):
    """hooks.toggle parameters."""
    hook_id: str
    enabled: bool


class HooksToggleResult(BaseModel):
    """hooks.toggle result."""
    success: bool
    hook: dict | None = None
    error: str | None = None


class HooksExecuteParams(BaseModel):
    """hooks.execute parameters (for manual trigger)."""
    hook_id: str
    context: dict | None = None


class HooksExecuteResult(BaseModel):
    """hooks.execute result."""
    success: bool
    result: HookExecutionResult | None = None
    error: str | None = None


# Global hooks config (for settings.json)
class GlobalHooksConfig(BaseModel):
    """Global hooks configuration."""
    enabled: bool = True
    hooks: list[Hook] = []


# Custom Tools Error codes
TOOL_NOT_FOUND = -32500
TOOL_REGISTRATION_FAILED = -32501
TOOL_EXECUTION_ERROR = -32502
TOOL_VALIDATION_ERROR = -32503
TOOL_ALREADY_EXISTS = -32504


# Custom Tool Types
class ToolParameter(BaseModel):
    """Tool parameter definition."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str = ""
    required: bool = False
    default: Any = None


class ToolDefinition(BaseModel):
    """Custom tool definition."""
    name: str
    description: str
    parameters: list[ToolParameter] = []
    code: str  # Python code for the tool
    version: str = "1.0.0"
    author: str | None = None
    tags: list[str] = []


class CustomTool(BaseModel):
    """Custom tool instance."""
    id: str
    name: str
    description: str
    parameters: list[ToolParameter] = []
    code: str
    version: str = "1.0.0"
    author: str | None = None
    tags: list[str] = []
    enabled: bool = True
    created_at: str
    updated_at: str | None = None


class ToolExecutionInput(BaseModel):
    """Input for tool execution."""
    name: str
    arguments: dict = {}


class ToolExecutionResult(BaseModel):
    """Result of tool execution."""
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: int = 0


# Custom Tools JSON-RPC Parameter/Result Types
class ToolsListParams(BaseModel):
    """tools.list parameters."""
    tag: str | None = None  # Filter by tag


class ToolsListResult(BaseModel):
    """tools.list result."""
    tools: list[dict]


class ToolsRegisterParams(BaseModel):
    """tools.register parameters."""
    name: str
    description: str
    parameters: list[ToolParameter] = []
    code: str
    version: str = "1.0.0"
    author: str | None = None
    tags: list[str] = []


class ToolsRegisterResult(BaseModel):
    """tools.register result."""
    success: bool
    tool: dict | None = None
    error: str | None = None


class ToolsUnregisterParams(BaseModel):
    """tools.unregister parameters."""
    tool_id: str


class ToolsUnregisterResult(BaseModel):
    """tools.unregister result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


class ToolsToggleParams(BaseModel):
    """tools.toggle parameters."""
    tool_id: str
    enabled: bool


class ToolsToggleResult(BaseModel):
    """tools.toggle result."""
    success: bool
    tool: dict | None = None
    error: str | None = None


class ToolsExecuteParams(BaseModel):
    """tools.execute parameters."""
    name: str
    arguments: dict = {}


class ToolsExecuteResult(BaseModel):
    """tools.execute result."""
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: int = 0


class ToolsGetParams(BaseModel):
    """tools.get parameters."""
    tool_id: str


class ToolsGetResult(BaseModel):
    """tools.get result."""
    tool: dict | None = None


class ToolsValidateParams(BaseModel):
    """tools.validate parameters."""
    code: str


class ToolsValidateResult(BaseModel):
    """tools.validate result."""
    valid: bool
    errors: list[str] = []


# =============================================================================
# Plugin System Types
# =============================================================================

# Plugin Error codes
PLUGIN_NOT_FOUND = -32600
PLUGIN_REGISTRATION_FAILED = -32601
PLUGIN_INSTALL_FAILED = -32602
PLUGIN_UNINSTALL_FAILED = -32603
PLUGIN_ALREADY_EXISTS = -32604
PLUGIN_INVALID_FORMAT = -32605
PLUGIN_DEPENDENCY_MISSING = -32606


class PluginMetadata(BaseModel):
    """Plugin metadata definition."""
    id: str
    name: str
    version: str
    description: str = ""
    author: str | None = None
    homepage: str | None = None
    license: str = "MIT"
    tags: list[str] = []
    categories: list[str] = []  # "workflow", "skill", "tool", "integration"
    dependencies: dict[str, str] = {}  # {"plugin-name": "version"}
    peer_dependencies: dict[str, str] = {}


class PluginContent(BaseModel):
    """Plugin content definition."""
    workflows: list[dict] = []  # YAML workflow definitions
    skills: list[dict] = []  # Skill definitions
    tools: list[dict] = []  # Tool definitions
    hooks: list[dict] = []  # Hook definitions
    mcp_servers: list[dict] = []  # MCP server configurations


class Plugin(BaseModel):
    """Plugin definition."""
    id: str
    metadata: PluginMetadata
    content: PluginContent
    enabled: bool = True
    installed_at: str | None = None
    updated_at: str | None = None
    installed_version: str | None = None


class PluginInstallSource(BaseModel):
    """Plugin install source."""
    type: str = "local"  # "local", "git", "npm", "url"
    path: str | None = None  # For local plugins
    url: str | None = None  # For URL-based plugins
    git: str | None = None  # For git-based plugins
    npm: str | None = None  # For npm-based plugins


class PluginExecutionContext(BaseModel):
    """Context passed to plugin execution."""
    execution_id: str
    workflow_name: str
    node_name: str | None = None
    data: dict = {}


# Plugin JSON-RPC Parameter/Result Types
class PluginsListParams(BaseModel):
    """plugins.list parameters."""
    category: str | None = None  # Filter by category
    tag: str | None = None  # Filter by tag


class PluginsListResult(BaseModel):
    """plugins.list result."""
    plugins: list[dict]


class PluginsGetParams(BaseModel):
    """plugins.get parameters."""
    plugin_id: str


class PluginsGetResult(BaseModel):
    """plugins.get result."""
    plugin: dict | None = None


class PluginsInstallParams(BaseModel):
    """plugins.install parameters."""
    source: PluginInstallSource
    name: str | None = None  # Optional name override
    version: str | None = None  # Specific version
    force: bool = False  # Force reinstall


class PluginsInstallResult(BaseModel):
    """plugins.install result."""
    success: bool
    plugin: dict | None = None
    error: str | None = None
    installed_files: list[str] = []


class PluginsUninstallParams(BaseModel):
    """plugins.uninstall parameters."""
    plugin_id: str
    force: bool = False  # Force uninstall even if dependencies


class PluginsUninstallResult(BaseModel):
    """plugins.uninstall result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None
    removed_files: list[str] = []


class PluginsEnableParams(BaseModel):
    """plugins.enable parameters."""
    plugin_id: str
    enabled: bool


class PluginsEnableResult(BaseModel):
    """plugins.enable result."""
    success: bool
    plugin: dict | None = None
    error: str | None = None


class PluginsUpdateParams(BaseModel):
    """plugins.update parameters."""
    plugin_id: str
    version: str | None = None  # Specific version, or latest if None
    force: bool = False


class PluginsUpdateResult(BaseModel):
    """plugins.update result."""
    success: bool
    plugin: dict | None = None
    error: str | None = None
    updated_files: list[str] = []


class PluginsValidateParams(BaseModel):
    """plugins.validate parameters."""
    content: PluginContent


class PluginsValidateResult(BaseModel):
    """plugins.validate result."""
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class PluginsSearchParams(BaseModel):
    """plugins.search parameters."""
    query: str
    category: str | None = None


class PluginsSearchResult(BaseModel):
    """plugins.search result."""
    plugins: list[dict]
    total: int


# =============================================================================
# Phase 4.4: Monitoring & Logging
# =============================================================================

class DaemonHealthParams(BaseModel):
    """daemon.health parameters."""
    pass


class DaemonHealthResult(BaseModel):
    """daemon.health result."""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    uptime_seconds: float
    timestamp: str
    components: dict


class MetricsGetParams(BaseModel):
    """metrics.get parameters."""
    name: str | None = None  # Optional metric name prefix filter


class MetricsGetResult(BaseModel):
    """metrics.get result."""
    metrics: dict


class MetricsResetParams(BaseModel):
    """metrics.reset parameters."""
    name: str | None = None  # Optional metric name to reset


class MetricsResetResult(BaseModel):
    """metrics.reset result."""
    reset: int  # Number of metrics reset


class MetricsSummaryParams(BaseModel):
    """metrics.summary parameters."""
    pass


class MetricsSummaryResult(BaseModel):
    """metrics.summary result."""
    summary: dict


# =============================================================================
# Phase B.1: Workflow Version Management
# =============================================================================

# Version Management Error codes
VERSION_NOT_FOUND = -32800
VERSION_ALREADY_EXISTS = -32801
VERSION_INVALID_FORMAT = -32802
VERSION_DEPRECATED = -32803
VERSION_MAX_REACHED = -32804


class WorkflowVersion(BaseModel):
    """Workflow version definition."""
    version: str  # Semantic version (e.g., "1.0.0")
    created_at: str
    created_by: str | None = None
    changelog: str | None = None
    is_default: bool = False
    is_deprecated: bool = False
    workflow_content: str | None = None  # YAML content (optional, can be loaded from file)
    metadata: dict = {}  # Additional metadata


class WorkflowVersionMetadata(BaseModel):
    """Workflow version metadata."""
    workflow_name: str
    total_versions: int
    default_version: str | None = None
    latest_version: str | None = None
    latest_stable: str | None = None
    deprecated_versions: list[str] = []


class WorkflowVersionInfo(BaseModel):
    """Workflow version info for listing."""
    version: str
    created_at: str
    created_by: str | None = None
    changelog: str | None = None
    is_default: bool
    is_deprecated: bool


# Version Management JSON-RPC Parameter/Result Types
class VersionListParams(BaseModel):
    """workflow.version.list parameters."""
    workflow_name: str


class VersionListResult(BaseModel):
    """workflow.version.list result."""
    workflow_name: str
    versions: list[WorkflowVersionInfo]
    metadata: WorkflowVersionMetadata


class VersionGetParams(BaseModel):
    """workflow.version.get parameters."""
    workflow_name: str
    version: str | None = None  # If None, get default version


class VersionGetResult(BaseModel):
    """workflow.version.get result."""
    workflow_name: str
    version: WorkflowVersion
    is_default: bool


class VersionCreateParams(BaseModel):
    """workflow.version.create parameters."""
    workflow_name: str
    version: str  # Semantic version (e.g., "1.0.0")
    changelog: str | None = None
    created_by: str | None = None
    set_default: bool = False


class VersionCreateResult(BaseModel):
    """workflow.version.create result."""
    success: bool
    workflow_name: str
    version: str | None = None
    error: str | None = None


class VersionSetDefaultParams(BaseModel):
    """workflow.version.set_default parameters."""
    workflow_name: str
    version: str


class VersionSetDefaultResult(BaseModel):
    """workflow.version.set_default result."""
    success: bool
    workflow_name: str
    version: str | None = None
    error: str | None = None


class VersionDeprecateParams(BaseModel):
    """workflow.version.deprecate parameters."""
    workflow_name: str
    version: str


class VersionDeprecateResult(BaseModel):
    """workflow.version.deprecate result."""
    success: bool
    workflow_name: str
    version: str | None = None
    error: str | None = None


class VersionDeleteParams(BaseModel):
    """workflow.version.delete parameters."""
    workflow_name: str
    version: str
    force: bool = False  # Force delete even if default


class VersionDeleteResult(BaseModel):
    """workflow.version.delete result."""
    success: bool
    workflow_name: str
    version: str | None = None
    error: str | None = None


class VersionCompareParams(BaseModel):
    """workflow.version.compare parameters."""
    workflow_name: str
    version_a: str
    version_b: str


class VersionCompareResult(BaseModel):
    """workflow.version.compare result."""
    workflow_name: str
    version_a: str
    version_b: str
    relationship: str  # "newer", "older", "equal"
    diff: dict | None = None  # Key differences


class VersionRollbackParams(BaseModel):
    """workflow.version.rollback parameters."""
    workflow_name: str
    target_version: str
    new_version: str | None = None  # Optional new version for rollback
    changelog: str | None = None


class VersionRollbackResult(BaseModel):
    """workflow.version.rollback result."""
    success: bool
    workflow_name: str
    target_version: str
    new_version: str | None = None
    error: str | None = None


# =============================================================================
# Phase B.2: Workflow Template Marketplace
# =============================================================================

# Template Marketplace Error codes
TEMPLATE_NOT_FOUND = -32900
TEMPLATE_ALREADY_EXISTS = -32901
TEMPLATE_PUBLISH_FAILED = -32902
TEMPLATE_DOWNLOAD_FAILED = -32903
TEMPLATE_CATEGORY_NOT_FOUND = -32904
TEMPLATE_INVALID_METADATA = -32905
TEMPLATE_RATING_FAILED = -32906
TEMPLATE_REVIEW_FAILED = -32907


class TemplateCategory(BaseModel):
    """Template category definition."""
    id: str
    name: str
    description: str
    icon: str | None = None
    parent_id: str | None = None  # For nested categories


class TemplateAuthor(BaseModel):
    """Template author information."""
    name: str
    email: str | None = None
    url: str | None = None
    avatar: str | None = None


class TemplateStats(BaseModel):
    """Template usage statistics."""
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    reviews_count: int = 0


class TemplateMetadata(BaseModel):
    """Template metadata."""
    id: str
    name: str
    version: str  # Semantic version of the template itself
    description: str
    author: TemplateAuthor
    license: str = "MIT"
    tags: list[str] = []
    category: str
    homepage: str | None = None
    repository: str | None = None
    keywords: list[str] = []
    min_leeway_version: str | None = None  # Minimum Leeway version required
    workflow_version: str | None = None  # Compatible workflow version
    created_at: str
    updated_at: str | None = None
    featured: bool = False
    verified: bool = False  # Author verified badge


class TemplateReview(BaseModel):
    """Template review."""
    id: str
    template_id: str
    user_id: str
    user_name: str
    rating: int  # 1-5
    title: str | None = None
    content: str
    created_at: str


class TemplateRating(BaseModel):
    """Template rating summary."""
    average: float
    count: int
    distribution: dict[int, int] = {}  # {1: count, 2: count, ...}


class WorkflowTemplate(BaseModel):
    """Workflow template definition."""
    id: str
    metadata: TemplateMetadata
    content: str  # YAML workflow content
    readme: str | None = None  # Markdown documentation
    examples: list[dict] = []  # Example usages
    variables: list[dict] = []  # Template variables schema


# Template Marketplace JSON-RPC Parameter/Result Types
class TemplateListParams(BaseModel):
    """templates.list parameters."""
    category: str | None = None
    tag: str | None = None
    search: str | None = None
    sort_by: str = "popular"  # "popular", "newest", "rating", "name"
    page: int = 1
    limit: int = 20


class TemplateListResult(BaseModel):
    """templates.list result."""
    templates: list[WorkflowTemplate]
    total: int
    page: int
    total_pages: int


class TemplateGetParams(BaseModel):
    """templates.get parameters."""
    template_id: str


class TemplateGetResult(BaseModel):
    """templates.get result."""
    template: WorkflowTemplate | None = None


class TemplateSearchParams(BaseModel):
    """templates.search parameters."""
    query: str
    category: str | None = None
    tags: list[str] = []
    author: str | None = None
    min_rating: float | None = None
    page: int = 1
    limit: int = 20


class TemplateSearchResult(BaseModel):
    """templates.search result."""
    templates: list[WorkflowTemplate]
    total: int
    suggestions: list[str] = []  # Search suggestions


class TemplateCategoriesParams(BaseModel):
    """templates.categories parameters."""
    parent_id: str | None = None  # Get subcategories


class TemplateCategoriesResult(BaseModel):
    """templates.categories result."""
    categories: list[TemplateCategory]


class TemplateInstallParams(BaseModel):
    """templates.install parameters."""
    template_id: str
    name: str | None = None  # Custom name for installed workflow
    version: str | None = None  # Specific version, defaults to latest
    target_dir: str | None = None  # Custom target directory


class TemplateInstallResult(BaseModel):
    """templates.install result."""
    success: bool
    template_id: str
    workflow_name: str
    installed_path: str | None = None
    error: str | None = None


class TemplateUninstallParams(BaseModel):
    """templates.uninstall parameters."""
    template_id: str
    delete_files: bool = False  # Also delete downloaded template files


class TemplateUninstallResult(BaseModel):
    """templates.uninstall result."""
    success: bool
    template_id: str
    deleted_files: list[str] = []


class TemplatePublishParams(BaseModel):
    """templates.publish parameters."""
    name: str
    description: str
    category: str
    content: str  # YAML workflow content
    readme: str | None = None
    examples: list[dict] = []
    tags: list[str] = []
    license: str = "MIT"
    version: str = "1.0.0"
    homepage: str | None = None
    repository: str | None = None
    keywords: list[str] = []
    min_leeway_version: str | None = None
    workflow_version: str | None = None


class TemplatePublishResult(BaseModel):
    """templates.publish result."""
    success: bool
    template_id: str | None = None
    version: str | None = None
    error: str | None = None


class TemplateUpdateParams(BaseModel):
    """templates.update parameters."""
    template_id: str
    content: str | None = None
    readme: str | None = None
    examples: list[dict] | None = None
    description: str | None = None
    tags: list[str] | None = None
    version: str | None = None  # New version for update
    version_note: str | None = None  # Version change notes


class TemplateUpdateResult(BaseModel):
    """templates.update result."""
    success: bool
    template_id: str
    new_version: str | None = None
    error: str | None = None


class TemplateDeleteParams(BaseModel):
    """templates.delete parameters."""
    template_id: str
    reason: str | None = None


class TemplateDeleteResult(BaseModel):
    """templates.delete result."""
    success: bool
    template_id: str | None = None
    error: str | None = None


class TemplateRateParams(BaseModel):
    """templates.rate parameters."""
    template_id: str
    rating: int  # 1-5


class TemplateRateResult(BaseModel):
    """templates.rate result."""
    success: bool
    template_id: str
    new_average: float | None = None
    total_ratings: int | None = None
    error: str | None = None


class TemplateReviewParams(BaseModel):
    """templates.review parameters."""
    template_id: str
    rating: int  # 1-5
    title: str | None = None
    content: str


class TemplateReviewResult(BaseModel):
    """templates.review result."""
    success: bool
    review_id: str | None = None
    error: str | None = None


class TemplateReviewsParams(BaseModel):
    """templates.reviews parameters."""
    template_id: str
    page: int = 1
    limit: int = 10


class TemplateReviewsResult(BaseModel):
    """templates.reviews result."""
    reviews: list[TemplateReview]
    total: int
    page: int
    total_pages: int


class TemplateFeaturedParams(BaseModel):
    """templates.featured parameters."""
    category: str | None = None
    limit: int = 10


class TemplateFeaturedResult(BaseModel):
    """templates.featured result."""
    templates: list[WorkflowTemplate]


class TemplatePopularParams(BaseModel):
    """templates.popular parameters."""
    category: str | None = None
    time_range: str = "all"  # "week", "month", "all"
    limit: int = 10


class TemplatePopularResult(BaseModel):
    """templates.popular result."""
    templates: list[WorkflowTemplate]


class TemplateNewestParams(BaseModel):
    """templates.newest parameters."""
    category: str | None = None
    limit: int = 10


class TemplateNewestResult(BaseModel):
    """templates.newest result."""
    templates: list[WorkflowTemplate]


class TemplateVersionsParams(BaseModel):
    """templates.versions parameters."""
    template_id: str


class TemplateVersionsResult(BaseModel):
    """templates.versions result."""
    template_id: str
    versions: list[dict]  # List of available versions


class TemplateDownloadParams(BaseModel):
    """templates.download parameters."""
    template_id: str
    version: str | None = None  # Specific version


class TemplateDownloadResult(BaseModel):
    """templates.download result."""
    success: bool
    template_id: str
    version: str
    content: str | None = None
    error: str | None = None


# =============================================================================
# Phase B.3: Workflow Visual Editor
# =============================================================================

# Visual Editor Error codes
EDITOR_PROJECT_NOT_FOUND = -33000
EDITOR_NODE_NOT_FOUND = -33001
EDITOR_EDGE_NOT_FOUND = -33002
EDITOR_INVALID_NODE_TYPE = -33003
EDITOR_INVALID_EDGE = -33004
EDITOR_CIRCULAR_DEPENDENCY = -33005
EDITOR_YAML_PARSE_ERROR = -33006
EDITOR_YAML_SERIALIZE_ERROR = -33007
EDITOR_VALIDATION_ERROR = -33008
EDITOR_PROJECT_ALREADY_EXISTS = -33009


# Node types in visual editor
class EditorNodeType(str):
    """Editor node type enumeration."""
    LINEAR = "linear"
    BRANCH = "branch"
    LOOP = "loop"
    PARALLEL = "parallel"
    TERMINAL = "terminal"


# Edge types
class EditorEdgeType(str):
    """Editor edge type enumeration."""
    SIGNAL = "signal"
    ALWAYS = "always"


class EditorPosition(BaseModel):
    """Node position in canvas."""
    x: int = 0
    y: int = 0


class EditorNodeConfig(BaseModel):
    """Editor node configuration."""
    prompt: str | None = None
    tools: list[str] = []
    skills: list[str] = []
    edges: list[dict] = []
    parallel: dict | None = None
    requires_approval: bool = False
    max_turns: int | None = None
    timeout: int | None = None
    metadata: dict = {}


class EditorNode(BaseModel):
    """Editor node definition."""
    id: str
    type: str = EditorNodeType.LINEAR  # "linear", "branch", "loop", "parallel", "terminal"
    name: str
    position: EditorPosition = EditorPosition()
    config: EditorNodeConfig = EditorNodeConfig()
    collapsed: bool = False  # Whether node is collapsed in canvas
    color: str | None = None  # Custom color for node


class EditorEdge(BaseModel):
    """Editor edge (connection) definition."""
    id: str
    source: str  # Source node id
    target: str  # Target node id
    type: str = EditorEdgeType.SIGNAL  # "signal" or "always"
    condition: dict | None = None  # {"signal": "ready"} or {"always": true}
    label: str | None = None  # Optional label for edge
    animated: bool = True  # Whether edge is animated


class EditorCanvas(BaseModel):
    """Editor canvas state."""
    zoom: float = 1.0
    pan_x: int = 0
    pan_y: int = 0
    grid_size: int = 20
    show_grid: bool = True
    snap_to_grid: bool = True


class EditorMetadata(BaseModel):
    """Editor metadata."""
    author: str | None = None
    description: str | None = None
    tags: list[str] = []
    category: str | None = None
    version: str = "1.0.0"


class EditorProject(BaseModel):
    """Workflow editor project."""
    id: str
    name: str
    description: str | None = None
    content: str  # YAML content
    created_at: str
    updated_at: str | None = None
    version: str | None = None
    nodes: list[EditorNode] = []
    edges: list[EditorEdge] = []
    canvas: EditorCanvas = EditorCanvas()
    metadata: EditorMetadata = EditorMetadata()


class EditorValidationError(BaseModel):
    """Validation error for workflow."""
    type: str  # "node", "edge", "syntax"
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    line: int | None = None
    column: int | None = None


class EditorValidationResult(BaseModel):
    """Workflow validation result."""
    valid: bool
    errors: list[EditorValidationError] = []
    warnings: list[EditorValidationError] = []


class EditorExportOptions(BaseModel):
    """Export options for workflow."""
    format: str = "yaml"  # "yaml", "json"
    include_metadata: bool = True
    pretty_print: bool = True
    validate: bool = True


class EditorProjectSummary(BaseModel):
    """Editor project summary for listing."""
    id: str
    name: str
    description: str | None = None
    node_count: int
    edge_count: int
    created_at: str
    updated_at: str | None = None


# Visual Editor JSON-RPC Parameter/Result Types

class EditorCreateProjectParams(BaseModel):
    """editor.create_project parameters."""
    name: str
    description: str | None = None
    content: str | None = None  # Optional YAML content to import
    metadata: EditorMetadata | None = None


class EditorCreateProjectResult(BaseModel):
    """editor.create_project result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


class EditorOpenProjectParams(BaseModel):
    """editor.open_project parameters."""
    project_id: str | None = None  # Open existing project by ID
    workflow_name: str | None = None  # Or open from workflow file


class EditorOpenProjectResult(BaseModel):
    """editor.open_project result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


class EditorSaveProjectParams(BaseModel):
    """editor.save_project parameters."""
    project_id: str
    content: str | None = None  # Optional: save as different content
    validate: bool = True


class EditorSaveProjectResult(BaseModel):
    """editor.save_project result."""
    success: bool
    project: EditorProject | None = None
    saved_path: str | None = None
    error: str | None = None


class EditorListProjectsParams(BaseModel):
    """editor.list_projects parameters."""
    limit: int = 20
    offset: int = 0


class EditorListProjectsResult(BaseModel):
    """editor.list_projects result."""
    projects: list[EditorProjectSummary]
    total: int


class EditorDeleteProjectParams(BaseModel):
    """editor.delete_project parameters."""
    project_id: str


class EditorDeleteProjectResult(BaseModel):
    """editor.delete_project result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


class EditorAddNodeParams(BaseModel):
    """editor.add_node parameters."""
    project_id: str
    node: EditorNode


class EditorAddNodeResult(BaseModel):
    """editor.add_node result."""
    success: bool
    project_id: str
    node: EditorNode | None = None
    error: str | None = None


class EditorUpdateNodeParams(BaseModel):
    """editor.update_node parameters."""
    project_id: str
    node_id: str
    node: EditorNode


class EditorUpdateNodeResult(BaseModel):
    """editor.update_node result."""
    success: bool
    project_id: str
    node: EditorNode | None = None
    error: str | None = None


class EditorDeleteNodeParams(BaseModel):
    """editor.delete_node parameters."""
    project_id: str
    node_id: str


class EditorDeleteNodeResult(BaseModel):
    """editor.delete_node result."""
    success: bool
    project_id: str
    deleted_node_id: str | None = None
    error: str | None = None


class EditorAddEdgeParams(BaseModel):
    """editor.add_edge parameters."""
    project_id: str
    edge: EditorEdge


class EditorAddEdgeResult(BaseModel):
    """editor.add_edge result."""
    success: bool
    project_id: str
    edge: EditorEdge | None = None
    error: str | None = None


class EditorUpdateEdgeParams(BaseModel):
    """editor.update_edge parameters."""
    project_id: str
    edge_id: str
    edge: EditorEdge


class EditorUpdateEdgeResult(BaseModel):
    """editor.update_edge result."""
    success: bool
    project_id: str
    edge: EditorEdge | None = None
    error: str | None = None


class EditorDeleteEdgeParams(BaseModel):
    """editor.delete_edge parameters."""
    project_id: str
    edge_id: str


class EditorDeleteEdgeResult(BaseModel):
    """editor.delete_edge result."""
    success: bool
    project_id: str
    deleted_edge_id: str | None = None
    error: str | None = None


class EditorValidateParams(BaseModel):
    """editor.validate parameters."""
    project_id: str | None = None
    content: str | None = None  # Or validate raw YAML content


class EditorValidateResult(BaseModel):
    """editor.validate result."""
    valid: bool
    errors: list[EditorValidationError]
    warnings: list[EditorValidationError]


class EditorExportParams(BaseModel):
    """editor.export parameters."""
    project_id: str
    options: EditorExportOptions | None = None


class EditorExportResult(BaseModel):
    """editor.export result."""
    success: bool
    content: str | None = None
    format: str
    error: str | None = None


class EditorImportParams(BaseModel):
    """editor.import parameters."""
    content: str  # YAML content
    name: str | None = None  # Optional name for imported workflow
    description: str | None = None


class EditorImportResult(BaseModel):
    """editor.import result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


class EditorPreviewParams(BaseModel):
    """editor.preview parameters."""
    project_id: str
    format: str = "yaml"  # "yaml" or "json"


class EditorPreviewResult(BaseModel):
    """editor.preview result."""
    success: bool
    content: str | None = None
    format: str


class EditorAutoLayoutParams(BaseModel):
    """editor.auto_layout parameters."""
    project_id: str
    direction: str = "top-bottom"  # "top-bottom", "left-right", "radial"


class EditorAutoLayoutResult(BaseModel):
    """editor.auto_layout result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


class EditorDuplicateNodeParams(BaseModel):
    """editor.duplicate_node parameters."""
    project_id: str
    node_id: str
    offset_x: int = 50
    offset_y: int = 50


class EditorDuplicateNodeResult(BaseModel):
    """editor.duplicate_node result."""
    success: bool
    project_id: str
    new_node: EditorNode | None = None
    error: str | None = None


class EditorUndoParams(BaseModel):
    """editor.undo parameters."""
    project_id: str


class EditorUndoResult(BaseModel):
    """editor.undo result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


class EditorRedoParams(BaseModel):
    """editor.redo parameters."""
    project_id: str


class EditorRedoResult(BaseModel):
    """editor.redo result."""
    success: bool
    project: EditorProject | None = None
    error: str | None = None


# =============================================================================
# Phase B.4: Multi-Language LLM Support
# =============================================================================

# LLM Provider Types
class LlmProviderType(str):
    """LLM provider type enumeration."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"


class LlmProviderInfo(BaseModel):
    """LLM provider information."""
    name: str  # e.g., "anthropic", "openai", "google", "ollama"
    display_name: str
    description: str
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    default_models: list[str] = []
    authentication: str = "api_key"  # "api_key", "bearer_token", "none"
    base_url: str | None = None


class LlmModelInfo(BaseModel):
    """LLM model information."""
    id: str  # e.g., "claude-3-5-sonnet-20241022"
    display_name: str
    provider: str  # e.g., "anthropic"
    description: str
    context_window: int  # tokens
    max_output_tokens: int
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    pricing: dict[str, float] | None = None  # {"input": 0.003, "output": 0.015}


class LlmMessage(BaseModel):
    """LLM message."""
    role: str  # "system", "user", "assistant"
    content: str


class LlmTool(BaseModel):
    """LLM tool definition."""
    name: str
    description: str
    input_schema: dict


class LlmToolCall(BaseModel):
    """LLM tool call."""
    id: str
    name: str
    arguments: dict


class LlmCompletionParams(BaseModel):
    """LLM completion parameters."""
    model: str
    messages: list[LlmMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    stream: bool = False
    tools: list[LlmTool] | None = None
    # Provider-specific params
    provider: str | None = None  # Override default provider
    system: str | None = None  # System prompt (converted to message)


class LlmCompletionResult(BaseModel):
    """LLM completion result."""
    id: str  # Completion ID
    model: str
    content: str | None = None
    tool_calls: list[LlmToolCall] | None = None
    finish_reason: str | None = None  # "stop", "length", "tool_calls"
    usage: dict[str, int] | None = None  # {"prompt_tokens": 100, "completion_tokens": 50}
    provider: str
    created_at: str | None = None


class LlmProvidersListParams(BaseModel):
    """llm.providers.list parameters."""
    pass


class LlmProvidersListResult(BaseModel):
    """llm.providers.list result."""
    providers: list[LlmProviderInfo]


class LlmModelsListParams(BaseModel):
    """llm.models.list parameters."""
    provider: str | None = None  # Filter by provider


class LlmModelsListResult(BaseModel):
    """llm.models.list result."""
    models: list[LlmModelInfo]


class LlmExecuteParams(BaseModel):
    """llm.execute parameters."""
    model: str
    messages: list[LlmMessage]
    provider: str | None = None  # Override provider
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    tools: list[LlmTool] | None = None
    system: str | None = None


class LlmExecuteResult(BaseModel):
    """llm.execute result."""
    success: bool
    completion: LlmCompletionResult | None = None
    error: str | None = None


# LLM Error Codes (Phase B.4)
LLM_PROVIDER_NOT_FOUND = -33100
LLM_MODEL_NOT_FOUND = -33101
LLM_AUTHENTICATION_FAILED = -33102
LLM_RATE_LIMIT_EXCEEDED = -33103
LLM_INVALID_REQUEST = -33104
LLM_PROVIDER_ERROR = -33105
LLM_CONTEXT_LENGTH_EXCEEDED = -33106


# =============================================================================
# Phase B.5: Workflow Testing Framework
# =============================================================================

# Testing Framework Error Codes
TEST_NOT_FOUND = -33200
TEST_ALREADY_EXISTS = -33201
TEST_COMPILE_ERROR = -33202
TEST_EXECUTION_ERROR = -33203
TEST_ASSERTION_FAILED = -33204
TEST_TIMEOUT = -33205
TEST_SUITE_NOT_FOUND = -33206
TEST_SUITE_ALREADY_EXISTS = -33207
TEST_COVERAGE_ERROR = -33208


class TestType(str):
    """Test type enumeration."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SMOKE = "smoke"
    REGRESSION = "regression"
    PERFORMANCE = "performance"


class TestStatus(str):
    """Test status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestAssertion(BaseModel):
    """Test assertion definition."""
    type: str  # "equals", "not_equals", "contains", "regex", "greater_than", "less_than", "truthy", "falsy"
    expected: Any = None
    actual: Any = None
    message: str | None = None


class TestStep(BaseModel):
    """Test step definition."""
    name: str
    action: str  # "execute", "http", "assert", "wait", "screenshot", "scroll"
    params: dict = {}
    timeout: int = 30


class WorkflowTestCase(BaseModel):
    """Test case definition."""
    id: str
    name: str
    description: str | None = None
    type: str = TestType.UNIT
    workflow_name: str  # Workflow to test
    input: dict = {}  # Test input/scenario
    expected_output: dict = {}  # Expected output
    assertions: list[TestAssertion] = []  # Custom assertions
    steps: list[TestStep] = []  # E2E test steps
    timeout: int = 60  # Test timeout in seconds
    retries: int = 0  # Number of retries on failure
    tags: list[str] = []  # Tags for filtering
    metadata: dict = {}  # Additional metadata


class WorkflowTestResult(BaseModel):
    """Test result."""
    test_id: str
    name: str
    status: str  # "passed", "failed", "error", "skipped"
    duration_ms: int = 0
    output: str | None = None  # Actual output
    error: str | None = None  # Error message if failed
    assertions: list[TestAssertion] = []  # Assertion results
    execution_id: str | None = None  # Execution ID for debugging


class WorkflowTestSuite(BaseModel):
    """Test suite definition."""
    id: str
    name: str
    description: str | None = None
    tests: list[WorkflowTestCase] = []
    tags: list[str] = []
    metadata: dict = {}


class WorkflowTestSuiteResult(BaseModel):
    """Test suite result."""
    suite_id: str
    suite_name: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: int = 0
    results: list[WorkflowTestResult] = []


class TestCoverageReport(BaseModel):
    """Test coverage report."""
    workflow_name: str
    total_nodes: int = 0
    covered_nodes: int = 0
    node_coverage_percent: float = 0.0
    total_signals: int = 0
    covered_signals: int = 0
    signal_coverage_percent: float = 0.0
    uncovered_nodes: list[str] = []
    uncovered_signals: list[str] = []


class TestMetrics(BaseModel):
    """Test execution metrics."""
    total_runs: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_duration_ms: int = 0


# Testing Framework JSON-RPC Parameter/Result Types

class TestRunParams(BaseModel):
    """tests.run parameters."""
    test_id: str
    workflow_name: str | None = None  # Override workflow
    input: dict | None = None  # Override input


class TestRunResult(BaseModel):
    """tests.run result."""
    success: bool
    result: WorkflowTestResult | None = None
    error: str | None = None


class TestRunManyParams(BaseModel):
    """tests.run_many parameters."""
    test_ids: list[str]
    workflow_name: str | None = None
    parallel: bool = False  # Run tests in parallel


class TestRunManyResult(BaseModel):
    """tests.run_many result."""
    success: bool
    results: list[WorkflowTestResult]
    total: int
    passed: int
    failed: int
    duration_ms: int


class TestListParams(BaseModel):
    """tests.list parameters."""
    workflow_name: str | None = None
    tag: str | None = None
    type: str | None = None


class TestListResult(BaseModel):
    """tests.list result."""
    tests: list[dict]
    total: int


class TestGetParams(BaseModel):
    """tests.get parameters."""
    test_id: str


class TestGetResult(BaseModel):
    """tests.get result."""
    test: WorkflowTestCase | None = None


class TestCreateParams(BaseModel):
    """tests.create parameters."""
    test: WorkflowTestCase


class TestCreateResult(BaseModel):
    """tests.create result."""
    success: bool
    test: WorkflowTestCase | None = None
    error: str | None = None


class TestUpdateParams(BaseModel):
    """tests.update parameters."""
    test_id: str
    test: WorkflowTestCase


class TestUpdateResult(BaseModel):
    """tests.update result."""
    success: bool
    test: WorkflowTestCase | None = None
    error: str | None = None


class TestDeleteParams(BaseModel):
    """tests.delete parameters."""
    test_id: str


class TestDeleteResult(BaseModel):
    """tests.delete result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


class TestDuplicateParams(BaseModel):
    """tests.duplicate parameters."""
    test_id: str
    new_name: str | None = None


class TestDuplicateResult(BaseModel):
    """tests.duplicate result."""
    success: bool
    new_test: WorkflowTestCase | None = None
    error: str | None = None


# Test Suite Methods

class TestSuiteCreateParams(BaseModel):
    """tests.suite.create parameters."""
    name: str
    description: str | None = None
    test_ids: list[str] = []
    tags: list[str] = []


class TestSuiteCreateResult(BaseModel):
    """tests.suite.create result."""
    success: bool
    suite: WorkflowTestSuite | None = None
    error: str | None = None


class TestSuiteListParams(BaseModel):
    """tests.suite.list parameters."""
    tag: str | None = None


class TestSuiteListResult(BaseModel):
    """tests.suite.list result."""
    suites: list[dict]
    total: int


class TestSuiteRunParams(BaseModel):
    """tests.suite.run parameters."""
    suite_id: str
    parallel: bool = False


class TestSuiteRunResult(BaseModel):
    """tests.suite.run result."""
    success: bool
    result: WorkflowTestSuiteResult | None = None
    error: str | None = None


class TestSuiteDeleteParams(BaseModel):
    """tests.suite.delete parameters."""
    suite_id: str


class TestSuiteDeleteResult(BaseModel):
    """tests.suite.delete result."""
    success: bool
    deleted_id: str | None = None
    error: str | None = None


# Coverage Methods

class TestCoverageParams(BaseModel):
    """tests.coverage parameters."""
    workflow_name: str
    test_ids: list[str] = []  # Run specific tests for coverage


class TestCoverageResult(BaseModel):
    """tests.coverage result."""
    success: bool
    report: TestCoverageReport | None = None
    error: str | None = None


# Metrics Methods

class TestMetricsParams(BaseModel):
    """tests.metrics parameters."""
    workflow_name: str | None = None
    time_range: str | None = None  # "hour", "day", "week", "all"


class TestMetricsResult(BaseModel):
    """tests.metrics result."""
    metrics: TestMetrics


# History Methods

class TestHistoryParams(BaseModel):
    """tests.history parameters."""
    test_id: str | None = None
    limit: int = 10


class TestHistoryResult(BaseModel):
    """tests.history result."""
    executions: list[dict]
    total: int


# =============================================================================
# Phase B.6: Workflow Performance Profiling
# =============================================================================

class WorkflowProfileData(BaseModel):
    """Workflow profiling data."""
    workflow_name: str
    execution_id: str
    started_at: str
    completed_at: str | None = None
    duration_ms: int = 0
    node_profiles: list[dict] = []  # Profile data per node
    tool_profiles: list[dict] = []  # Profile data per tool call
    memory_samples: list[dict] = []  # Memory usage samples
    cpu_samples: list[dict] = []  # CPU usage samples


class NodeProfileData(BaseModel):
    """Single node profiling data."""
    node_name: str
    started_at: str
    completed_at: str | None = None
    duration_ms: int = 0
    turns_used: int = 0
    tools_called: int = 0
    llm_calls: int = 0
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    signal: str | None = None
    error: str | None = None


class ToolProfileData(BaseModel):
    """Single tool profiling data."""
    tool_name: str
    called_at: str
    completed_at: str | None = None
    duration_ms: int = 0
    success: bool = True
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class PerformanceMetrics(BaseModel):
    """Performance metrics summary."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    median_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    avg_turns_per_execution: float = 0.0
    avg_tools_per_execution: float = 0.0
    avg_llm_calls_per_execution: float = 0.0
    avg_tokens_per_execution: float = 0.0


class SlowestNodesReport(BaseModel):
    """Report of slowest nodes."""
    nodes: list[dict]  # {node_name, avg_duration_ms, total_calls, error_rate}


class BottleneckReport(BaseModel):
    """Report of performance bottlenecks."""
    bottlenecks: list[dict]  # {type, location, metric, value, threshold,severity}


# Performance Profiling JSON-RPC Parameters/Results

class ProfileStartParams(BaseModel):
    """profiler.start parameters."""
    workflow_name: str
    sample_interval_ms: int = 1000  # Sample every N ms


class ProfileStartResult(BaseModel):
    """profiler.start result."""
    success: bool
    profile_id: str | None = None
    message: str | None = None


class ProfileStopParams(BaseModel):
    """profiler.stop parameters."""
    profile_id: str | None = None  # Stop specific profile


class ProfileStopResult(BaseModel):
    """profiler.stop result."""
    success: bool
    profile_id: str | None = None
    profile: WorkflowProfileData | None = None


class ProfileListParams(BaseModel):
    """profiler.list parameters."""
    workflow_name: str | None = None
    limit: int = 10


class ProfileListResult(BaseModel):
    """profiler.list result."""
    profiles: list[dict]
    total: int


class ProfileGetParams(BaseModel):
    """profiler.get parameters."""
    profile_id: str


class ProfileGetResult(BaseModel):
    """profiler.get result."""
    profile: WorkflowProfileData | None = None


class ProfileDeleteParams(BaseModel):
    """profiler.delete parameters."""
    profile_id: str


class ProfileDeleteResult(BaseModel):
    """profiler.delete result."""
    success: bool
    deleted_id: str | None = None


class ProfilerMetricsParams(BaseModel):
    """profiler.metrics parameters."""
    workflow_name: str | None = None
    time_range: str | None = None  # "hour", "day", "week", "all"


class ProfilerMetricsResult(BaseModel):
    """profiler.metrics result."""
    metrics: PerformanceMetrics


class ProfilerSlowestParams(BaseModel):
    """profiler.slowest parameters."""
    workflow_name: str
    limit: int = 10


class ProfilerSlowestResult(BaseModel):
    """profiler.slowest result."""
    report: SlowestNodesReport


class ProfilerBottlenecksParams(BaseModel):
    """profiler.bottlenecks parameters."""
    workflow_name: str


class ProfilerBottlenecksResult(BaseModel):
    """profiler.bottlenecks result."""
    report: BottleneckReport


class ProfilerExportParams(BaseModel):
    """profiler.export parameters."""
    profile_id: str
    format: str = "json"  # "json", "csv", "chrome-tracing"


class ProfilerExportResult(BaseModel):
    """profiler.export result."""
    success: bool
    content: str | None = None
    format: str | None = None


class ProfilerClearParams(BaseModel):
    """profiler.clear parameters."""
    workflow_name: str | None = None


class ProfilerClearResult(BaseModel):
    """profiler.clear result."""
    success: bool
    deleted_count: int = 0