/**
 * Leeway Workflow Tools
 *
 * This module provides the workflow tool integration for OpenCode.
 * It communicates with the Leeway daemon via JSON-RPC over stdin/stdout.
 *
 * Usage:
 * ```typescript
 * import { workflowTool } from "./tools/workflow";
 *
 * const result = await workflowTool.execute({
 *   name: "code-health",
 *   user_context: "Check my codebase at /path/to/project"
 * });
 *
 * console.log(result.output);
 * ```
 *
 * Or use the daemon client directly:
 * ```typescript
 * import { getDaemonClient } from "./tools/workflow-daemon";
 *
 * const daemon = getDaemonClient();
 * await daemon.ensure();
 * const result = await daemon.executeWorkflow({
 *   name: "code-health",
 *   user_context: "..."
 * });
 * ```
 */

export { WorkflowTool, workflowTool } from "./workflow";
export type { ToolResult, WorkflowInputSchema } from "./workflow";

export {
  WorkflowDaemonClient,
  getDaemonClient,
  resetDaemonClient,
  DaemonError,
  ConnectionError,
  WorkflowNotFoundError,
  RequestTimeoutError,
  ERROR_CODES,
} from "./workflow-daemon";

export type {
  DaemonConfig,
  WorkflowExecuteParams,
  WorkflowExecuteResult,
  WorkflowAudit,
  NodeExecution,
  BranchExecution,
  WorkflowListResult,
  WorkflowValidateResult,
  ProgressEvent,
} from "./workflow-daemon";