"""Leeway daemon error definitions."""

from typing import Any


class DaemonError(Exception):
    """Base exception for daemon errors."""

    def __init__(self, code: int, message: str, data: dict | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }


class InvalidRequestError(DaemonError):
    def __init__(self, message: str = "Invalid Request"):
        super().__init__(-32600, message)


class MethodNotFoundError(DaemonError):
    def __init__(self, method: str):
        super().__init__(-32601, f"Method not found: {method}")


class InvalidParamsError(DaemonError):
    def __init__(self, message: str):
        super().__init__(-32602, message)


class InternalError(DaemonError):
    def __init__(self, message: str):
        super().__init__(-32603, message)


class WorkflowNotFoundError(DaemonError):
    def __init__(self, name: str, available: list[str]):
        super().__init__(
            -32000,
            f"Workflow '{name}' not found",
            {"available": available},
        )


class NodeNotFoundError(DaemonError):
    def __init__(self, node: str):
        super().__init__(-32001, f"Node not found: {node}")


class SignalValidationError(DaemonError):
    def __init__(self, signal: str, allowed: list[str]):
        super().__init__(
            -32002,
            f"Signal '{signal}' not in allowed list",
            {"allowed": allowed},
        )


class PermissionDeniedError(DaemonError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(-32003, message)


class ToolExecutionError(DaemonError):
    def __init__(self, tool: str, message: str):
        super().__init__(
            -32004,
            f"Tool execution failed: {tool}",
            {"tool": tool, "message": message},
        )


class ParallelBranchTimeoutError(DaemonError):
    def __init__(self, timeout: int):
        super().__init__(
            -32005,
            f"Parallel branch timeout after {timeout}s",
        )


class HitlTimeoutError(DaemonError):
    def __init__(self, timeout: int):
        super().__init__(
            -32006,
            f"Human input timeout after {timeout}s",
        )


# MCP Errors
class McpServerNotFoundError(DaemonError):
    def __init__(self, server_name: str, available: list[str]):
        super().__init__(
            -32100,
            f"MCP server '{server_name}' not found",
            {"available": available},
        )


class McpToolNotFoundError(DaemonError):
    def __init__(self, tool_name: str, server_name: str):
        super().__init__(
            -32101,
            f"MCP tool '{tool_name}' not found on server '{server_name}'",
        )


class McpConnectionError(DaemonError):
    def __init__(self, server_name: str, message: str):
        super().__init__(
            -32102,
            f"MCP connection failed for '{server_name}': {message}",
        )


class McpToolExecutionError(DaemonError):
    def __init__(self, tool_name: str, server_name: str, message: str):
        super().__init__(
            -32103,
            f"MCP tool execution failed: {tool_name} on {server_name}",
            {"tool": tool_name, "server": server_name, "message": message},
        )


# Cron Errors
class CronNotFoundError(DaemonError):
    def __init__(self, cron_id: str):
        super().__init__(
            -32200,
            f"Cron schedule '{cron_id}' not found",
        )


class CronInvalidCronStringError(DaemonError):
    def __init__(self, cron_string: str):
        super().__init__(
            -32201,
            f"Invalid cron expression: {cron_string}",
        )


class CronWorkflowNotFoundError(DaemonError):
    def __init__(self, workflow_name: str, available: list[str]):
        super().__init__(
            -32202,
            f"Workflow '{workflow_name}' not found for cron schedule",
            {"available": available},
        )


# Scheduler Daemon Errors
class SchedulerNotRunningError(DaemonError):
    def __init__(self):
        super().__init__(
            -32300,
            "Scheduler daemon is not running",
        )


class SchedulerAlreadyRunningError(DaemonError):
    def __init__(self):
        super().__init__(
            -32301,
            "Scheduler daemon is already running",
        )


class SchedulerExecutionError(DaemonError):
    def __init__(self, schedule_id: str, message: str):
        super().__init__(
            -32302,
            f"Scheduled workflow execution failed: {message}",
            {"schedule_id": schedule_id, "message": message},
        )


# Hook Errors
class HookNotFoundError(DaemonError):
    def __init__(self, hook_id: str):
        super().__init__(
            -32400,
            f"Hook '{hook_id}' not found",
        )


class HookRegistrationError(DaemonError):
    def __init__(self, message: str):
        super().__init__(
            -32401,
            f"Hook registration failed: {message}",
        )


class HookExecutionError(DaemonError):
    def __init__(self, hook_id: str, message: str):
        super().__init__(
            -32402,
            f"Hook execution failed: {hook_id}",
            {"hook_id": hook_id, "message": message},
        )


class InvalidHookTypeError(DaemonError):
    def __init__(self, hook_type: str):
        super().__init__(
            -32403,
            f"Invalid hook type: {hook_type}. Must be 'command' or 'http'",
        )


# Custom Tool Errors
class ToolNotFoundError(DaemonError):
    def __init__(self, tool_name: str, available: list[str]):
        super().__init__(
            -32500,
            f"Tool '{tool_name}' not found",
            {"available": available},
        )


class ToolRegistrationError(DaemonError):
    def __init__(self, message: str):
        super().__init__(
            -32501,
            f"Tool registration failed: {message}",
        )


class ToolExecutionError(DaemonError):
    def __init__(self, tool_name: str, message: str):
        super().__init__(
            -32502,
            f"Tool execution failed: {tool_name}",
            {"tool": tool_name, "message": message},
        )


class ToolValidationError(DaemonError):
    def __init__(self, message: str, errors: list[str]):
        super().__init__(
            -32503,
            f"Tool validation failed: {message}",
            {"errors": errors},
        )


class ToolAlreadyExistsError(DaemonError):
    def __init__(self, tool_name: str):
        super().__init__(
            -32504,
            f"Tool '{tool_name}' already exists",
        )


# =============================================================================
# Plugin System Errors
# =============================================================================

class PluginNotFoundError(DaemonError):
    def __init__(self, plugin_id: str, available: list[str] | None = None):
        super().__init__(
            -32600,
            f"Plugin '{plugin_id}' not found",
            {"available": available or []},
        )


class PluginRegistrationError(DaemonError):
    def __init__(self, message: str):
        super().__init__(
            -32601,
            f"Plugin registration failed: {message}",
        )


class PluginInstallError(DaemonError):
    def __init__(self, plugin_id: str, message: str):
        super().__init__(
            -32602,
            f"Plugin install failed: {plugin_id}",
            {"plugin_id": plugin_id, "message": message},
        )


class PluginUninstallError(DaemonError):
    def __init__(self, plugin_id: str, message: str):
        super().__init__(
            -32603,
            f"Plugin uninstall failed: {plugin_id}",
            {"plugin_id": plugin_id, "message": message},
        )


class PluginAlreadyExistsError(DaemonError):
    def __init__(self, plugin_id: str):
        super().__init__(
            -32604,
            f"Plugin '{plugin_id}' already exists",
            {"plugin_id": plugin_id},
        )


class PluginInvalidFormatError(DaemonError):
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(
            -32605,
            f"Plugin invalid format: {message}",
            {"errors": errors or []},
        )


class PluginDependencyMissingError(DaemonError):
    def __init__(self, plugin_id: str, missing_deps: list[str]):
        super().__init__(
            -32606,
            f"Plugin '{plugin_id}' has missing dependencies",
            {"plugin_id": plugin_id, "missing": missing_deps},
        )


# =============================================================================
# Security Errors
# =============================================================================

class SecurityError(DaemonError):
    """Base class for security-related errors."""
    pass


class KeychainAccessError(SecurityError):
    def __init__(self, key_name: str, message: str):
        super().__init__(
            -32700,
            f"Keychain access failed for '{key_name}': {message}",
            {"key_name": key_name},
        )


class EncryptionError(SecurityError):
    def __init__(self, message: str):
        super().__init__(
            -32701,
            f"Encryption error: {message}",
        )


class AuditLogError(SecurityError):
    def __init__(self, message: str):
        super().__init__(
            -32702,
            f"Audit log error: {message}",
        )


class AuditIntegrityError(SecurityError):
    def __init__(self, execution_id: str):
        super().__init__(
            -32703,
            f"Audit log integrity verification failed for execution '{execution_id}'",
            {"execution_id": execution_id},
        )


class InvalidRoleError(SecurityError):
    def __init__(self, role: str):
        super().__init__(
            -32704,
            f"Invalid role: '{role}'",
            {"role": role},
        )


class RoleManagementError(SecurityError):
    def __init__(self, message: str):
        super().__init__(
            -32705,
            f"Role management error: {message}",
        )


# =============================================================================
# Phase B.1: Workflow Version Management Errors
# =============================================================================

class VersionNotFoundError(DaemonError):
    def __init__(self, workflow_name: str, version: str, available: list[str] | None = None):
        super().__init__(
            -32800,
            f"Version '{version}' not found for workflow '{workflow_name}'",
            {"workflow_name": workflow_name, "available": available or []},
        )


class VersionAlreadyExistsError(DaemonError):
    def __init__(self, workflow_name: str, version: str):
        super().__init__(
            -32801,
            f"Version '{version}' already exists for workflow '{workflow_name}'",
            {"workflow_name": workflow_name, "version": version},
        )


class VersionInvalidFormatError(DaemonError):
    def __init__(self, version: str, message: str):
        super().__init__(
            -32802,
            f"Invalid version format '{version}': {message}",
            {"version": version},
        )


class VersionDeprecatedError(DaemonError):
    def __init__(self, workflow_name: str, version: str):
        super().__init__(
            -32803,
            f"Version '{version}' of workflow '{workflow_name}' is deprecated",
            {"workflow_name": workflow_name, "version": version},
        )


class VersionMaxReachedError(DaemonError):
    def __init__(self, workflow_name: str, max_versions: int):
        super().__init__(
            -32804,
            f"Maximum number of versions ({max_versions}) reached for workflow '{workflow_name}'",
            {"workflow_name": workflow_name, "max_versions": max_versions},
        )


# =============================================================================
# Phase B.2: Workflow Template Marketplace Errors
# =============================================================================

class TemplateNotFoundError(DaemonError):
    def __init__(self, template_id: str, available: list[str] | None = None):
        super().__init__(
            -32900,
            f"Template '{template_id}' not found",
            {"template_id": template_id, "available": available or []},
        )


class TemplateAlreadyExistsError(DaemonError):
    def __init__(self, name: str):
        super().__init__(
            -32901,
            f"Template '{name}' already exists",
            {"name": name},
        )


class TemplatePublishFailedError(DaemonError):
    def __init__(self, name: str, message: str):
        super().__init__(
            -32902,
            f"Failed to publish template '{name}': {message}",
            {"name": name, "message": message},
        )


class TemplateDownloadFailedError(DaemonError):
    def __init__(self, template_id: str, message: str):
        super().__init__(
            -32903,
            f"Failed to download template '{template_id}': {message}",
            {"template_id": template_id, "message": message},
        )


class TemplateCategoryNotFoundError(DaemonError):
    def __init__(self, category: str, available: list[str] | None = None):
        super().__init__(
            -32904,
            f"Template category '{category}' not found",
            {"category": category, "available": available or []},
        )


class TemplateInvalidMetadataError(DaemonError):
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(
            -32905,
            f"Invalid template metadata: {message}",
            {"errors": errors or []},
        )


class TemplateRatingFailedError(DaemonError):
    def __init__(self, template_id: str, message: str):
        super().__init__(
            -32906,
            f"Failed to rate template '{template_id}': {message}",
            {"template_id": template_id, "message": message},
        )


class TemplateReviewFailedError(DaemonError):
    def __init__(self, template_id: str, message: str):
        super().__init__(
            -32907,
            f"Failed to review template '{template_id}': {message}",
            {"template_id": template_id, "message": message},
        )


# =============================================================================
# Phase B.3: Workflow Visual Editor Errors
# =============================================================================

class EditorProjectNotFoundError(DaemonError):
    def __init__(self, project_id: str, available: list[str] | None = None):
        super().__init__(
            -33000,
            f"Editor project '{project_id}' not found",
            {"project_id": project_id, "available": available or []},
        )


class EditorNodeNotFoundError(DaemonError):
    def __init__(self, node_id: str, project_id: str | None = None):
        super().__init__(
            -33001,
            f"Editor node '{node_id}' not found",
            {"node_id": node_id, "project_id": project_id},
        )


class EditorEdgeNotFoundError(DaemonError):
    def __init__(self, edge_id: str, project_id: str | None = None):
        super().__init__(
            -33002,
            f"Editor edge '{edge_id}' not found",
            {"edge_id": edge_id, "project_id": project_id},
        )


class EditorInvalidNodeTypeError(DaemonError):
    def __init__(self, node_type: str, valid_types: list[str] | None = None):
        super().__init__(
            -33003,
            f"Invalid node type: '{node_type}'",
            {"node_type": node_type, "valid_types": valid_types or ["linear", "branch", "loop", "parallel", "terminal"]},
        )


class EditorInvalidEdgeError(DaemonError):
    def __init__(self, message: str, source: str | None = None, target: str | None = None):
        super().__init__(
            -33004,
            f"Invalid edge: {message}",
            {"source": source, "target": target},
        )


class EditorCircularDependencyError(DaemonError):
    def __init__(self, cycle: list[str]):
        super().__init__(
            -33005,
            f"Circular dependency detected: {' -> '.join(cycle)}",
            {"cycle": cycle},
        )


class EditorYamlParseError(DaemonError):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(
            -33006,
            f"YAML parse error: {message}",
            {"line": line, "column": column},
        )


class EditorYamlSerializeError(DaemonError):
    def __init__(self, message: str):
        super().__init__(
            -33007,
            f"YAML serialize error: {message}",
        )


class EditorValidationError(DaemonError):
    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(
            -33008,
            f"Workflow validation error: {message}",
            {"errors": errors or []},
        )


class EditorProjectAlreadyExistsError(DaemonError):
    def __init__(self, name: str):
        super().__init__(
            -33009,
            f"Editor project '{name}' already exists",
            {"name": name},
        )


# =============================================================================
# Phase B.4: Multi-Language LLM Errors
# =============================================================================

class LlmProviderNotFoundError(DaemonError):
    def __init__(self, provider: str, available: list[str]):
        super().__init__(
            -33100,
            f"LLM provider '{provider}' not found",
            {"provider": provider, "available": available},
        )


class LlmModelNotFoundError(DaemonError):
    def __init__(self, model: str, provider: str | None = None):
        data = {"model": model}
        if provider:
            data["provider"] = provider
        super().__init__(
            -33101,
            f"LLM model '{model}' not found",
            data,
        )


class LlmAuthenticationError(DaemonError):
    def __init__(self, provider: str, message: str = "Authentication failed"):
        super().__init__(
            -33102,
            message,
            {"provider": provider},
        )


class LlmRateLimitError(DaemonError):
    def __init__(self, provider: str, message: str = "Rate limit exceeded"):
        super().__init__(
            -33103,
            message,
            {"provider": provider},
        )


class LlmInvalidRequestError(DaemonError):
    def __init__(self, message: str, provider: str | None = None):
        data = {"message": message}
        if provider:
            data["provider"] = provider
        super().__init__(-33104, message, data)


class LlmProviderError(DaemonError):
    def __init__(self, provider: str, message: str, response: dict | None = None):
        data = {"provider": provider, "message": message}
        if response:
            data["response"] = response
        super().__init__(-33105, f"Provider error: {message}", data)


class LlmContextLengthError(DaemonError):
    def __init__(self, model: str, context_window: int, prompt_tokens: int):
        super().__init__(
            -33106,
            f"Context length exceeded for model '{model}' (max: {context_window}, provided: {prompt_tokens})",
            {"model": model, "context_window": context_window, "prompt_tokens": prompt_tokens},
        )


# =============================================================================
# Phase B.5: Workflow Testing Framework Errors
# =============================================================================

class TestNotFoundError(DaemonError):
    def __init__(self, test_id: str, available: list[str] | None = None):
        super().__init__(
            -33200,
            f"Test '{test_id}' not found",
            {"test_id": test_id, "available": available or []},
        )


class TestAlreadyExistsError(DaemonError):
    def __init__(self, test_id: str):
        super().__init__(
            -33201,
            f"Test '{test_id}' already exists",
            {"test_id": test_id},
        )


class TestCompileError(DaemonError):
    def __init__(self, test_id: str, errors: list[str]):
        super().__init__(
            -33202,
            f"Test compile error for '{test_id}'",
            {"test_id": test_id, "errors": errors},
        )


class TestExecutionError(DaemonError):
    def __init__(self, test_id: str, message: str):
        super().__init__(
            -33203,
            f"Test execution error for '{test_id}': {message}",
            {"test_id": test_id, "message": message},
        )


class TestAssertionFailedError(DaemonError):
    def __init__(self, test_id: str, assertion: str, expected: Any, actual: Any):
        super().__init__(
            -33204,
            f"Assertion failed for test '{test_id}': {assertion}",
            {"test_id": test_id, "assertion": assertion, "expected": expected, "actual": actual},
        )


class TestTimeoutError(DaemonError):
    def __init__(self, test_id: str, timeout: int):
        super().__init__(
            -33205,
            f"Test '{test_id}' timed out after {timeout}s",
            {"test_id": test_id, "timeout": timeout},
        )


class TestSuiteNotFoundError(DaemonError):
    def __init__(self, suite_id: str, available: list[str] | None = None):
        super().__init__(
            -33206,
            f"Test suite '{suite_id}' not found",
            {"suite_id": suite_id, "available": available or []},
        )


class TestSuiteAlreadyExistsError(DaemonError):
    def __init__(self, suite_id: str):
        super().__init__(
            -33207,
            f"Test suite '{suite_id}' already exists",
            {"suite_id": suite_id},
        )


class TestCoverageError(DaemonError):
    def __init__(self, workflow_name: str, message: str):
        super().__init__(
            -33208,
            f"Coverage error for workflow '{workflow_name}': {message}",
            {"workflow_name": workflow_name, "message": message},
        )


# =============================================================================
# Phase B.6: Performance Profiling Errors
# =============================================================================

class ProfileNotFoundError(DaemonError):
    def __init__(self, profile_id: str, available: list[str] | None = None):
        super().__init__(
            -33300,
            f"Profile '{profile_id}' not found",
            {"profile_id": profile_id, "available": available or []},
        )


class ProfileAlreadyExistsError(DaemonError):
    def __init__(self, profile_id: str):
        super().__init__(
            -33301,
            f"Profile '{profile_id}' already exists",
            {"profile_id": profile_id},
        )


class ProfileInvalidError(DaemonError):
    def __init__(self, message: str):
        super().__init__(
            -33302,
            f"Profile invalid: {message}",
            {"message": message},
        )