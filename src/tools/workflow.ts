/**
 * Workflow Tool for OpenCode
 *
 * Executes YAML-defined workflows via the Leeway daemon.
 * Each workflow node is a full agent loop with tools.
 * Use this for repeatable, auditable multi-step tasks.
 */

import {
  getDaemonClient,
  WorkflowExecuteParams as DaemonWorkflowParams,
  WorkflowExecuteResult,
  WorkflowNotFoundError,
  DaemonError,
  RequestTimeoutError,
  ConnectionError,
  ERROR_CODES,
} from "./workflow-daemon";

// Tool result type
export interface ToolResult {
  output: string;
  is_error?: boolean;
  metadata?: Record<string, unknown>;
}

// Input schema for the workflow tool
export interface WorkflowInputSchema {
  name: string;
  user_context: string;
  model?: string;
  cwd?: string;
  max_turns?: number;
  interactive?: boolean;
}

// Workflow tool class
export class WorkflowTool {
  name = "workflow";
  description = `Execute a YAML-defined workflow.

Each node in the workflow is a complete agent loop with access to tools.
The workflow is defined in YAML and controls the flow between nodes
using signals.

Use this tool for:
- Repeatable, auditable multi-step tasks
- Structured code reviews or audits
- Complex tasks requiring multiple agent turns
- Tasks with clear decision points and branches

Examples:
- Run a code health check: workflow { name: "code-health", user_context: "Check my codebase" }
- Execute API design review: workflow { name: "api-design", user_context: "Review the API design" }
- Run security audit: workflow { name: "security-audit", user_context: "Scan for vulnerabilities" }`;

  input_schema = {
    type: "object" as const,
    properties: {
      name: {
        type: "string" as const,
        description: "Workflow name (without .yaml extension)",
      },
      user_context: {
        type: "string" as const,
        description: "Initial context or task description for the workflow",
      },
      model: {
        type: "string" as const,
        description: "Override the default model",
        optional: true,
      },
      cwd: {
        type: "string" as const,
        description: "Working directory for the workflow",
        optional: true,
      },
      max_turns: {
        type: "number" as const,
        description: "Maximum number of turns per node",
        optional: true,
      },
      interactive: {
        type: "boolean" as const,
        description: "Allow human-in-the-loop interactions (default: false)",
        optional: true,
      },
    },
    required: ["name", "user_context"],
  };

  /**
   * Execute the workflow tool
   */
  async execute(params: WorkflowInputSchema, config?: {
    requestTimeout?: number;
    maxRetries?: number;
  }): Promise<ToolResult> {
    const startTime = Date.now();

    // Ensure daemon is running
    const daemon = getDaemonClient(config);
    await daemon.ensure();

    try {
      // Execute the workflow
      const result = await daemon.executeWorkflow({
        name: params.name,
        user_context: params.user_context,
        model: params.model,
        cwd: params.cwd,
        max_turns: params.max_turns,
        interactive: params.interactive ?? false,
      });

      // Format the result
      return this.formatResult(result, startTime);
    } catch (error) {
      return this.handleError(error, params.name, startTime);
    }
  }

  /**
   * Format the workflow result
   */
  private formatResult(result: WorkflowExecuteResult, startTime: number): ToolResult {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    // Build output based on success
    if (result.success) {
      let output = result.final_output;

      // Append audit summary if verbose
      if (result.audit && result.audit.path_taken.length > 0) {
        output += "\n\n---\n\n**Execution Summary**\n";
        output += `- Workflow: ${result.audit.workflow_name}\n`;
        output += `- Path: ${result.audit.path_taken.join(" → ")}\n`;
        output += `- Total turns: ${result.audit.total_turns}\n`;
        output += `- Duration: ${elapsed}s\n`;

        // Add node executions if available
        if (result.audit.node_executions.length > 0) {
          output += "\n**Nodes executed:**\n";
          for (const node of result.audit.node_executions) {
            const signal = node.signal_decision
              ? ` (${node.signal_decision})`
              : "";
            output += `- ${node.node_name}${signal}: ${node.turns_used} turns\n`;
          }
        }
      }

      return {
        output,
        is_error: false,
        metadata: {
          workflow: result.audit?.workflow_name,
          path_taken: result.audit?.path_taken,
          total_turns: result.audit?.total_turns,
          duration_seconds: elapsed,
        },
      };
    } else {
      // Workflow failed
      return {
        output: `Workflow failed: ${result.error ?? "Unknown error"}\n\n${result.final_output}`,
        is_error: true,
        metadata: {
          workflow: result.audit?.workflow_name,
          error: result.error,
        },
      };
    }
  }

  /**
   * Handle errors from the daemon
   */
  private handleError(error: unknown, workflowName: string, startTime: number): ToolResult {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    if (error instanceof WorkflowNotFoundError) {
      return {
        output: `Workflow '${workflowName}' not found.\n\nAvailable workflows: ${(error.data as { available: string[] }).available.join(", ") || "none"}`,
        is_error: true,
        metadata: {
          code: error.code,
          available: (error.data as { available: string[] }).available,
        },
      };
    }

    if (error instanceof RequestTimeoutError) {
      return {
        output: `Workflow '${workflowName}' timed out after ${elapsed}s.\nPlease try again or reduce the scope.`,
        is_error: true,
        metadata: {
          code: ERROR_CODES.INTERNAL_ERROR,
          timeout: true,
        },
      };
    }

    if (error instanceof ConnectionError) {
      return {
        output: `Failed to connect to workflow daemon: ${error.message}\n\nPlease ensure the daemon is properly installed.`,
        is_error: true,
        metadata: {
          code: ERROR_CODES.INTERNAL_ERROR,
          connection_error: true,
        },
      };
    }

    if (error instanceof DaemonError) {
      return {
        output: `Workflow error: ${error.message}`,
        is_error: true,
        metadata: {
          code: error.code,
          data: error.data,
        },
      };
    }

    // Unknown error
    const message = error instanceof Error ? error.message : String(error);
    return {
      output: `Unexpected error executing workflow '${workflowName}': ${message}`,
      is_error: true,
      metadata: {
        code: ERROR_CODES.INTERNAL_ERROR,
        unexpected: true,
      },
    };
  }
}

// Export singleton instance for convenience
export const workflowTool = new WorkflowTool();

// Export for use in other modules
export default workflowTool;