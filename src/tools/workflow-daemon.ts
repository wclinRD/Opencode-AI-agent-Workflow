/**
 * Leeway Daemon Communication Layer
 *
 * Handles JSON-RPC 2.0 communication with the Leeway daemon subprocess
 * over stdin/stdout.
 */

import { spawn, ChildProcess } from "child_process";
import * as readline from "readline";

// JSON-RPC Types
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string;
  result?: unknown;
  error?: JsonRpcError;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

// Error codes (matching Python protocol.py)
export const ERROR_CODES = {
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  WORKFLOW_NOT_FOUND: -32000,
  NODE_NOT_FOUND: -32001,
  SIGNAL_VALIDATION_FAILED: -32002,
  PERMISSION_DENIED: -32003,
  TOOL_EXECUTION_FAILED: -32004,
  PARALLEL_BRANCH_TIMEOUT: -32005,
  HITL_TIMEOUT: -32006,
  // MCP errors
  MCP_SERVER_NOT_FOUND: -32100,
  MCP_TOOL_NOT_FOUND: -32101,
  MCP_CONNECTION_FAILED: -32102,
  MCP_TOOL_EXECUTION_ERROR: -32103,
  // Cron errors
  CRON_NOT_FOUND: -32200,
  CRON_INVALID_CRONSTRING: -32201,
  CRON_WORKFLOW_NOT_FOUND: -32202,
  // Version Management errors (Phase B.1)
  VERSION_NOT_FOUND: -32800,
  VERSION_ALREADY_EXISTS: -32801,
  VERSION_INVALID_FORMAT: -32802,
  VERSION_DEPRECATED: -32803,
  VERSION_MAX_REACHED: -32804,
  // Template Marketplace errors (Phase B.2)
  TEMPLATE_NOT_FOUND: -32900,
  TEMPLATE_ALREADY_EXISTS: -32901,
  TEMPLATE_PUBLISH_FAILED: -32902,
  TEMPLATE_DOWNLOAD_FAILED: -32903,
  TEMPLATE_CATEGORY_NOT_FOUND: -32904,
  TEMPLATE_INVALID_METADATA: -32905,
  TEMPLATE_RATING_FAILED: -32906,
  TEMPLATE_REVIEW_FAILED: -32907,
  // Visual Editor errors (Phase B.3)
  EDITOR_PROJECT_NOT_FOUND: -33000,
  EDITOR_NODE_NOT_FOUND: -33001,
  EDITOR_EDGE_NOT_FOUND: -33002,
  EDITOR_INVALID_NODE_TYPE: -33003,
  EDITOR_INVALID_EDGE: -33004,
  EDITOR_CIRCULAR_DEPENDENCY: -33005,
  EDITOR_YAML_PARSE_ERROR: -33006,
  EDITOR_YAML_SERIALIZE_ERROR: -33007,
  EDITOR_VALIDATION_ERROR: -33008,
  EDITOR_PROJECT_ALREADY_EXISTS: -33009,
  // LLM Provider errors (Phase B.4)
  LLM_PROVIDER_NOT_FOUND: -33100,
  LLM_MODEL_NOT_FOUND: -33101,
  LLM_AUTHENTICATION_FAILED: -33102,
  LLM_RATE_LIMIT_EXCEEDED: -33103,
  LLM_INVALID_REQUEST: -33104,
  LLM_PROVIDER_ERROR: -33105,
  LLM_CONTEXT_LENGTH_EXCEEDED: -33106,
  // Testing Framework errors (Phase B.5)
  TEST_NOT_FOUND: -33200,
  TEST_ALREADY_EXISTS: -33201,
  TEST_COMPILE_ERROR: -33202,
  TEST_EXECUTION_ERROR: -33203,
  TEST_ASSERTION_FAILED: -33204,
  TEST_TIMEOUT: -33205,
  TEST_SUITE_NOT_FOUND: -33206,
  TEST_SUITE_ALREADY_EXISTS: -33207,
  TEST_COVERAGE_ERROR: -33208,
  // Performance Profiling errors (Phase B.6)
  PROFILE_NOT_FOUND: -33300,
  PROFILE_ALREADY_EXISTS: -33301,
  PROFILE_INVALID: -33302,
} as const;

// Daemon ping result
export interface DaemonPingResult {
  version: string;
  status: string;
}

// Workflow types
export interface WorkflowExecuteParams {
  name: string;
  user_context: string;
  model?: string;
  cwd?: string;
  max_turns?: number;
  interactive?: boolean;
  api_key?: string;
  base_url?: string;
}

export interface WorkflowExecuteResult {
  success: boolean;
  final_output: string;
  audit: WorkflowAudit;
  error: string | null;
}

export interface WorkflowAudit {
  workflow_name: string;
  path_taken: string[];
  node_executions: NodeExecution[];
  parallel_branches?: Record<string, Record<string, BranchExecution>>;
  started_at: string;
  completed_at: string;
  total_turns: number;
  execution_id?: string;
}

export interface NodeExecution {
  node_name: string;
  signal_decision: string | null;
  signal_summary: string | null;
  turns_used: number;
  tools_called: string[];
  parallel_results?: Record<string, BranchExecution>;
}

export interface BranchExecution {
  branch_name: string;
  triggered: boolean;
  approved: boolean;
  success: boolean;
  error: string | null;
  turns_used: number;
  tools_called: string[];
}

export interface WorkflowListResult {
  workflows: string[];
}

export interface WorkflowValidateResult {
  valid: boolean;
  errors: string[];
}

// Progress event (streaming)
export interface ProgressEvent {
  type: "progress";
  message: string;
  node?: string;
  step?: string;
}

// HITL question option
export interface HitlQuestionOption {
  label: string;
  description: string;
}

// HITL signal event (Human-in-the-Loop)
export interface HitlSignalEvent {
  type: "signal";
  node: string;
  tool: string;
  question: string;
  options: HitlQuestionOption[];
  timeout?: number;
}

// Branch event (parallel execution)
export interface BranchEvent {
  type: "branch";
  branch_name: string;
  action: "triggered" | "completed" | "approved";
  status: "pending" | "running" | "completed" | "approved";
}

// Node execution event
export interface NodeEvent {
  type: "node";
  node_name: string;
  action: "started" | "completed" | "failed";
  signal?: string;
  signal_summary?: string;
}

// Workflow lifecycle event
export interface WorkflowEvent {
  type: "workflow";
  action: "started" | "completed" | "failed" | "stopped";
  workflow_name?: string;
}

// Union type for all streaming events
export type StreamingEvent = ProgressEvent | HitlSignalEvent | BranchEvent | NodeEvent | WorkflowEvent;

// Event callback type
export type StreamingEventCallback = (event: StreamingEvent) => void;

// MCP Types
export interface McpServerInfo {
  name: string;
  status: "running" | "stopped" | "error";
  tools_count: number;
  error?: string;
}

export interface McpTool {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

export interface McpServersResult {
  servers: McpServerInfo[];
}

export interface McpStartParams {
  server_name: string;
}

export interface McpStopParams {
  server_name: string;
}

export interface McpListToolsParams {
  server_name: string;
}

export interface McpListToolsResult {
  tools: McpTool[];
}

export interface McpExecuteParams {
  server_name: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface McpExecuteResult {
  success: boolean;
  result?: unknown;
  error?: string;
}

// Cron Types
export interface CronSchedule {
  id: string;
  name: string;
  workflow_name: string;
  cron_expression: string;
  enabled: boolean;
  user_context?: string;
  next_run?: string;
  last_run?: string;
  created_at: string;
}

export interface CronCreateParams {
  name: string;
  workflow_name: string;
  cron_expression: string;
  user_context?: string;
}

export interface CronCreateResult {
  success: boolean;
  schedule?: CronSchedule;
  error?: string;
}

export interface CronListResult {
  schedules: CronSchedule[];
}

export interface CronDeleteParams {
  id: string;
}

export interface CronDeleteResult {
  success: boolean;
  deleted_id?: string;
  error?: string;
}

export interface CronToggleParams {
  id: string;
  enabled: boolean;
}

export interface CronToggleResult {
  success: boolean;
  schedule?: CronSchedule;
  error?: string;
}

// Cache Types
export interface CacheStats {
  size: number;
  max_size: number;
  hits: number;
  misses: number;
  hit_rate: number;
  default_ttl: number;
}

export interface CacheClearResult {
  success: boolean;
  message?: string;
}

export interface CacheInvalidateResult {
  success: boolean;
  invalidated: number;
}

// Daemon Warmup Types
export interface WarmupResult {
  success: boolean;
  preloaded: {
    workflows: string[];
    mcp_servers: string[];
  };
  message: string;
}

// Testing Framework Types (Phase B.5)
export interface TestAssertion {
  type: string;  // "equals", "not_equals", "contains", "regex", "greater_than", "less_than", "truthy", "falsy"
  expected?: unknown;
  actual?: unknown;
  message?: string;
}

export interface TestStep {
  name: string;
  action: string;
  params: Record<string, unknown>;
  timeout: number;
}

export interface WorkflowTestCase {
  id: string;
  name: string;
  description?: string;
  type: string;  // "unit", "integration", "e2e", "smoke", "regression", "performance"
  workflow_name: string;
  input: Record<string, unknown>;
  expected_output: Record<string, unknown>;
  assertions: TestAssertion[];
  steps: TestStep[];
  timeout: number;
  retries: number;
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface WorkflowTestResult {
  test_id: string;
  name: string;
  status: string;  // "passed", "failed", "error", "skipped"
  duration_ms: number;
  output?: string;
  error?: string;
  assertions: TestAssertion[];
  execution_id?: string;
}

export interface WorkflowTestSuite {
  id: string;
  name: string;
  description?: string;
  tests: WorkflowTestCase[];
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface WorkflowTestSuiteResult {
  suite_id: string;
  suite_name: string;
  total_tests: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  duration_ms: number;
  results: WorkflowTestResult[];
}

export interface TestCoverageReport {
  workflow_name: string;
  total_nodes: number;
  covered_nodes: number;
  node_coverage_percent: number;
  total_signals: number;
  covered_signals: number;
  signal_coverage_percent: number;
  uncovered_nodes: string[];
  uncovered_signals: string[];
}

export interface TestMetrics {
  total_runs: number;
  passed: number;
  failed: number;
  skipped: number;
  pass_rate: number;
  avg_duration_ms: number;
  total_duration_ms: number;
}

// Performance Profiling Types (Phase B.6)
export interface WorkflowProfileData {
  workflow_name: string;
  execution_id: string;
  started_at: string;
  completed_at?: string;
  duration_ms: number;
  node_profiles: NodeProfileData[];
  tool_profiles: ToolProfileData[];
}

export interface NodeProfileData {
  node_name: string;
  started_at: string;
  completed_at?: string;
  duration_ms: number;
  turns_used: number;
  tools_called: number;
  llm_calls: number;
  llm_tokens_input: number;
  llm_tokens_output: number;
  signal?: string;
  error?: string;
}

export interface ToolProfileData {
  tool_name: string;
  called_at: string;
  completed_at?: string;
  duration_ms: number;
  success: boolean;
  error?: string;
}

export interface WorkflowProfileSummary {
  profile_id: string;
  workflow_name: string;
  started_at: string;
  completed_at?: string;
  duration_ms: number;
  node_count: number;
  tool_count: number;
}

export interface PerformanceMetrics {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  avg_duration_ms: number;
  median_duration_ms: number;
  p95_duration_ms: number;
  p99_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
  avg_turns_per_execution: number;
  avg_tools_per_execution: number;
  avg_llm_calls_per_execution: number;
  avg_tokens_per_execution: number;
}

export interface SlowestNodesReport {
  nodes: { node_name: string; avg_duration_ms: number; total_calls: number; error_rate: number }[];
}

export interface BottleneckReport {
  bottlenecks: { type: string; location: string; metric: string; value: number; threshold: number; severity: string }[];
}

// Template Marketplace Types (Phase B.2)
export interface TemplateAuthor {
  name: string;
  email?: string;
  url?: string;
  avatar?: string;
}

export interface TemplateStats {
  downloads: number;
  rating: number;
  rating_count: number;
  reviews_count: number;
}

export interface TemplateMetadata {
  id: string;
  name: string;
  version: string;
  description: string;
  author: TemplateAuthor;
  license: string;
  tags: string[];
  category: string;
  homepage?: string;
  repository?: string;
  keywords: string[];
  min_leeway_version?: string;
  workflow_version?: string;
  created_at: string;
  updated_at?: string;
  featured: boolean;
  verified: boolean;
}

export interface TemplateReview {
  id: string;
  template_id: string;
  user_id: string;
  user_name: string;
  rating: number;
  title?: string;
  content: string;
  created_at: string;
}

export interface TemplateRating {
  average: number;
  count: number;
  distribution: Record<number, number>;
}

export interface WorkflowTemplate {
  id: string;
  metadata: TemplateMetadata;
  content: string;
  readme?: string;
  examples: Record<string, unknown>[];
  variables: Record<string, unknown>[];
}

export interface TemplateCategory {
  id: string;
  name: string;
  description: string;
  icon?: string;
  parent_id?: string;
}

// Template list params/result
export interface TemplateListParams {
  category?: string;
  tag?: string;
  search?: string;
  sort_by?: string;
  page?: number;
  limit?: number;
}

export interface TemplateListResult {
  templates: WorkflowTemplate[];
  total: number;
  page: number;
  total_pages: number;
}

export interface TemplateGetResult {
  template?: WorkflowTemplate;
}

export interface TemplateSearchResult {
  templates: WorkflowTemplate[];
  total: number;
  suggestions: string[];
}

export interface TemplateCategoriesResult {
  categories: TemplateCategory[];
}

export interface TemplateInstallParams {
  template_id: string;
  name?: string;
  version?: string;
  target_dir?: string;
}

export interface TemplateInstallResult {
  success: boolean;
  template_id: string;
  workflow_name: string;
  installed_path?: string;
  error?: string;
}

export interface TemplateUninstallParams {
  template_id: string;
  delete_files?: boolean;
}

export interface TemplateUninstallResult {
  success: boolean;
  template_id: string;
  deleted_files: string[];
}

export interface TemplatePublishParams {
  name: string;
  description: string;
  category: string;
  content: string;
  readme?: string;
  examples?: Record<string, unknown>[];
  tags?: string[];
  license?: string;
  version?: string;
  homepage?: string;
  repository?: string;
  keywords?: string[];
  min_leeway_version?: string;
  workflow_version?: string;
  author_name?: string;
  author_email?: string;
}

export interface TemplatePublishResult {
  success: boolean;
  template_id?: string;
  version?: string;
  error?: string;
}

export interface TemplateUpdateParams {
  template_id: string;
  content?: string;
  readme?: string;
  examples?: Record<string, unknown>[];
  description?: string;
  tags?: string[];
  version?: string;
}

export interface TemplateUpdateResult {
  success: boolean;
  template_id: string;
  new_version?: string;
  error?: string;
}

export interface TemplateDeleteParams {
  template_id: string;
  reason?: string;
}

export interface TemplateDeleteResult {
  success: boolean;
  template_id?: string;
  error?: string;
}

export interface TemplateRateParams {
  template_id: string;
  rating: number;
  user_id?: string;
}

export interface TemplateRateResult {
  success: boolean;
  template_id: string;
  new_average?: number;
  total_ratings?: number;
  error?: string;
}

export interface TemplateReviewParams {
  template_id: string;
  rating: number;
  title?: string;
  content: string;
  user_id?: string;
  user_name?: string;
}

export interface TemplateReviewResult {
  success: boolean;
  review_id?: string;
  error?: string;
}

export interface TemplateReviewsParams {
  template_id: string;
  page?: number;
  limit?: number;
}

export interface TemplateReviewsResult {
  reviews: TemplateReview[];
  total: number;
  page: number;
  total_pages: number;
}

export interface TemplateFeaturedParams {
  category?: string;
  limit?: number;
}

export interface TemplateFeaturedResult {
  templates: WorkflowTemplate[];
}

export interface TemplatePopularParams {
  category?: string;
  time_range?: string;
  limit?: number;
}

export interface TemplatePopularResult {
  templates: WorkflowTemplate[];
}

export interface TemplateNewestResult {
  templates: WorkflowTemplate[];
}

export interface TemplateVersionsParams {
  template_id: string;
}

export interface TemplateVersionsResult {
  template_id: string;
  versions: Record<string, unknown>[];
}

export interface TemplateDownloadParams {
  template_id: string;
  version?: string;
}

export interface TemplateDownloadResult {
  success: boolean;
  template_id: string;
  version: string;
  content?: string;
  error?: string;
}

// =============================================================================
// Phase B.3: Visual Editor Types
// =============================================================================

export interface EditorPosition {
  x: number;
  y: number;
}

export interface EditorNodeConfig {
  prompt?: string;
  tools?: string[];
  skills?: string[];
  edges?: Record<string, unknown>[];
  parallel?: Record<string, unknown>;
  requires_approval?: boolean;
  max_turns?: number;
  timeout?: number;
  metadata?: Record<string, unknown>;
}

export interface EditorNode {
  id: string;
  type: "linear" | "branch" | "loop" | "parallel" | "terminal";
  name: string;
  position: EditorPosition;
  config: EditorNodeConfig;
  collapsed?: boolean;
  color?: string;
}

export interface EditorEdge {
  id: string;
  source: string;
  target: string;
  type: "signal" | "always";
  condition?: Record<string, unknown>;
  label?: string;
  animated?: boolean;
}

export interface EditorCanvas {
  zoom: number;
  pan_x: number;
  pan_y: number;
  grid_size: number;
  show_grid: boolean;
  snap_to_grid: boolean;
}

export interface EditorMetadata {
  author?: string;
  description?: string;
  tags?: string[];
  category?: string;
  version: string;
}

export interface EditorProject {
  id: string;
  name: string;
  description?: string;
  content: string;
  created_at: string;
  updated_at?: string;
  version?: string;
  nodes: EditorNode[];
  edges: EditorEdge[];
  canvas: EditorCanvas;
  metadata: EditorMetadata;
}

export interface EditorValidationError {
  type: string;
  message: string;
  node_id?: string;
  edge_id?: string;
  line?: number;
  column?: number;
}

export interface EditorValidationResult {
  valid: boolean;
  errors: EditorValidationError[];
  warnings: EditorValidationError[];
}

export interface EditorExportOptions {
  format: "yaml" | "json";
  include_metadata?: boolean;
  pretty_print?: boolean;
  validate?: boolean;
}

export interface EditorProjectSummary {
  id: string;
  name: string;
  description?: string;
  node_count: number;
  edge_count: number;
  created_at: string;
  updated_at?: string;
}

// Visual Editor Error classes
export class McpServerNotFoundError extends DaemonError {
  constructor(serverName: string, available: string[]) {
    super(
      `MCP server '${serverName}' not found`,
      ERROR_CODES.MCP_SERVER_NOT_FOUND,
      { available }
    );
    this.name = "McpServerNotFoundError";
  }
}

export class McpConnectionError extends DaemonError {
  constructor(serverName: string, message: string) {
    super(
      `MCP connection failed for '${serverName}': ${message}`,
      ERROR_CODES.MCP_CONNECTION_FAILED,
      { server: serverName, message }
    );
    this.name = "McpConnectionError";
  }
}

// Cron Error classes
export class CronNotFoundError extends DaemonError {
  constructor(cronId: string) {
    super(
      `Cron schedule '${cronId}' not found`,
      ERROR_CODES.CRON_NOT_FOUND,
      { id: cronId }
    );
    this.name = "CronNotFoundError";
  }
}

export class CronInvalidCronStringError extends DaemonError {
  constructor(cronString: string) {
    super(
      `Invalid cron expression: ${cronString}`,
      ERROR_CODES.CRON_INVALID_CRONSTRING,
      { cron_expression: cronString }
    );
    this.name = "CronInvalidCronStringError";
  }
}

export class CronWorkflowNotFoundError extends DaemonError {
  constructor(workflowName: string, available: string[]) {
    super(
      `Workflow '${workflowName}' not found for cron schedule`,
      ERROR_CODES.CRON_WORKFLOW_NOT_FOUND,
      { workflow: workflowName, available }
    );
    this.name = "CronWorkflowNotFoundError";
  }
}

// Template Marketplace Error classes (Phase B.2)
export class TemplateNotFoundError extends DaemonError {
  constructor(templateId: string, available: string[]) {
    super(
      `Template '${templateId}' not found`,
      ERROR_CODES.TEMPLATE_NOT_FOUND,
      { template_id: templateId, available }
    );
    this.name = "TemplateNotFoundError";
  }
}

export class TemplateAlreadyExistsError extends DaemonError {
  constructor(name: string) {
    super(
      `Template '${name}' already exists`,
      ERROR_CODES.TEMPLATE_ALREADY_EXISTS,
      { name }
    );
    this.name = "TemplateAlreadyExistsError";
  }
}

export class TemplatePublishFailedError extends DaemonError {
  constructor(name: string, message: string) {
    super(
      `Failed to publish template '${name}': ${message}`,
      ERROR_CODES.TEMPLATE_PUBLISH_FAILED,
      { name, message }
    );
    this.name = "TemplatePublishFailedError";
  }
}

export class TemplateCategoryNotFoundError extends DaemonError {
  constructor(category: string, available: string[]) {
    super(
      `Template category '${category}' not found`,
      ERROR_CODES.TEMPLATE_CATEGORY_NOT_FOUND,
      { category, available }
    );
    this.name = "TemplateCategoryNotFoundError";
  }
}

// Visual Editor Error classes
export class EditorProjectNotFoundError extends DaemonError {
  constructor(projectId: string, available: string[]) {
    super(
      `Editor project '${projectId}' not found`,
      ERROR_CODES.EDITOR_PROJECT_NOT_FOUND,
      { project_id: projectId, available }
    );
    this.name = "EditorProjectNotFoundError";
  }
}

export class EditorNodeNotFoundError extends DaemonError {
  constructor(nodeId: string, projectId?: string) {
    super(
      `Editor node '${nodeId}' not found`,
      ERROR_CODES.EDITOR_NODE_NOT_FOUND,
      { node_id: nodeId, project_id: projectId }
    );
    this.name = "EditorNodeNotFoundError";
  }
}

export class EditorEdgeNotFoundError extends DaemonError {
  constructor(edgeId: string, projectId?: string) {
    super(
      `Editor edge '${edgeId}' not found`,
      ERROR_CODES.EDITOR_EDGE_NOT_FOUND,
      { edge_id: edgeId, project_id: projectId }
    );
    this.name = "EditorEdgeNotFoundError";
  }
}

export class EditorInvalidNodeTypeError extends DaemonError {
  constructor(nodeType: string, validTypes?: string[]) {
    super(
      `Invalid node type: '${nodeType}'`,
      ERROR_CODES.EDITOR_INVALID_NODE_TYPE,
      { node_type: nodeType, valid_types: validTypes || ["linear", "branch", "loop", "parallel", "terminal"] }
    );
    this.name = "EditorInvalidNodeTypeError";
  }
}

export class EditorYamlParseError extends DaemonError {
  constructor(message: string, line?: number, column?: number) {
    super(
      `YAML parse error: ${message}`,
      ERROR_CODES.EDITOR_YAML_PARSE_ERROR,
      { line, column }
    );
    this.name = "EditorYamlParseError";
  }
}

export class EditorValidationError extends DaemonError {
  constructor(message: string, errors?: Record<string, unknown>[]) {
    super(
      `Workflow validation error: ${message}`,
      ERROR_CODES.EDITOR_VALIDATION_ERROR,
      { errors }
    );
    this.name = "EditorValidationError";
  }
}

// Configuration for daemon
export interface DaemonConfig {
  workflowsDir?: string;
  pythonPath?: string;
  startupTimeout?: number;
  requestTimeout?: number;
  maxRetries?: number;
  retryDelay?: number;
  /** Enable automatic daemon restart on crash */
  autoRestart?: boolean;
  /** Maximum number of auto-restart attempts */
  maxAutoRestarts?: number;
  /** Base delay for exponential backoff (ms) */
  retryBaseDelay?: number;
  /** Maximum retry delay (ms) */
  retryMaxDelay?: number;
  /** Enable request result caching for idempotent retries */
  enableResultCache?: boolean;
  /** Cache TTL in milliseconds */
  cacheTtl?: number;
  /** Enable daemon warmup on startup for faster first requests */
  enableWarmup?: boolean;
  /** Timeout for different method types */
  methodTimeouts?: {
    ping?: number;
    workflowExecute?: number;
    workflowList?: number;
    workflowValidate?: number;
    cron?: number;
    mcp?: number;
    hooks?: number;
    tools?: number;
    default?: number;
  };
}

// Default configuration
const DEFAULT_CONFIG: Required<DaemonConfig> = {
  workflowsDir: ".leeway/workflows",
  pythonPath: "python",
  startupTimeout: 5000,
  requestTimeout: 300000, // 5 minutes
  maxRetries: 3,
  retryDelay: 1000,
  autoRestart: true,
  maxAutoRestarts: 5,
  retryBaseDelay: 500,
  retryMaxDelay: 30000,
  enableResultCache: true,
  cacheTtl: 300000, // 5 minutes
  enableWarmup: true,
  methodTimeouts: {
    ping: 5000,
    workflowExecute: 300000, // 5 minutes
    workflowList: 10000,
    workflowValidate: 10000,
    cron: 30000,
    mcp: 60000,
    hooks: 30000,
    tools: 60000,
    default: 60000,
  },
};

export class DaemonError extends Error {
  constructor(
    message: string,
    public code: number = ERROR_CODES.INTERNAL_ERROR,
    public data?: unknown
  ) {
    super(message);
    this.name = "DaemonError";
  }
}

export class ConnectionError extends DaemonError {
  constructor(message: string) {
    super(message, ERROR_CODES.INTERNAL_ERROR);
    this.name = "ConnectionError";
  }
}

export class WorkflowNotFoundError extends DaemonError {
  constructor(workflowName: string, available: string[]) {
    super(
      `Workflow '${workflowName}' not found`,
      ERROR_CODES.WORKFLOW_NOT_FOUND,
      { available }
    );
    this.name = "WorkflowNotFoundError";
  }
}

export class RequestTimeoutError extends DaemonError {
  constructor(method: string) {
    super(
      `Request '${method}' timed out`,
      ERROR_CODES.INTERNAL_ERROR,
      { method }
    );
    this.name = "RequestTimeoutError";
  }
}

// LLM Provider Errors (Phase B.4)
export class LlmProviderNotFoundError extends DaemonError {
  constructor(provider: string, available: string[]) {
    super(
      `LLM provider '${provider}' not found`,
      ERROR_CODES.LLM_PROVIDER_NOT_FOUND,
      { provider, available }
    );
    this.name = "LlmProviderNotFoundError";
  }
}

export class LlmModelNotFoundError extends DaemonError {
  constructor(model: string, provider?: string) {
    super(
      `LLM model '${model}' not found`,
      ERROR_CODES.LLM_MODEL_NOT_FOUND,
      { model, provider }
    );
    this.name = "LlmModelNotFoundError";
  }
}

export class LlmAuthenticationError extends DaemonError {
  constructor(provider: string, message: string = "Authentication failed") {
    super(message, ERROR_CODES.LLM_AUTHENTICATION_FAILED, { provider });
    this.name = "LlmAuthenticationError";
  }
}

export class LlmRateLimitError extends DaemonError {
  constructor(provider: string) {
    super(
      `Rate limit exceeded for ${provider}`,
      ERROR_CODES.LLM_RATE_LIMIT_EXCEEDED,
      { provider }
    );
    this.name = "LlmRateLimitError";
  }
}

export class LlmContextLengthError extends DaemonError {
  constructor(model: string, contextWindow: number, promptTokens: number) {
    super(
      `Context length exceeded for model '${model}' (max: ${contextWindow}, provided: ${promptTokens})`,
      ERROR_CODES.LLM_CONTEXT_LENGTH_EXCEEDED,
      { model, context_window: contextWindow, prompt_tokens: promptTokens }
    );
    this.name = "LlmContextLengthError";
  }
}

// Testing Framework error classes (Phase B.5)
export class TestNotFoundError extends DaemonError {
  constructor(testId: string, available?: string[]) {
    super(
      `Test '${testId}' not found`,
      ERROR_CODES.TEST_NOT_FOUND,
      { test_id: testId, available }
    );
    this.name = "TestNotFoundError";
  }
}

export class TestAlreadyExistsError extends DaemonError {
  constructor(testId: string) {
    super(
      `Test '${testId}' already exists`,
      ERROR_CODES.TEST_ALREADY_EXISTS,
      { test_id: testId }
    );
    this.name = "TestAlreadyExistsError";
  }
}

export class TestExecutionError extends DaemonError {
  constructor(testId: string, message: string) {
    super(
      `Test execution error for '${testId}': ${message}`,
      ERROR_CODES.TEST_EXECUTION_ERROR,
      { test_id: testId, message }
    );
    this.name = "TestExecutionError";
  }
}

export class TestAssertionFailedError extends DaemonError {
  constructor(testId: string, assertion: string, expected: unknown, actual: unknown) {
    super(
      `Assertion failed for test '${testId}': ${assertion}`,
      ERROR_CODES.TEST_ASSERTION_FAILED,
      { test_id: testId, assertion, expected, actual }
    );
    this.name = "TestAssertionFailedError";
  }
}

export class TestTimeoutError extends DaemonError {
  constructor(testId: string, timeout: number) {
    super(
      `Test '${testId}' timed out after ${timeout}s`,
      ERROR_CODES.TEST_TIMEOUT,
      { test_id: testId, timeout }
    );
    this.name = "TestTimeoutError";
  }
}

export class TestSuiteNotFoundError extends DaemonError {
  constructor(suiteId: string, available?: string[]) {
    super(
      `Test suite '${suiteId}' not found`,
      ERROR_CODES.TEST_SUITE_NOT_FOUND,
      { suite_id: suiteId, available }
    );
    this.name = "TestSuiteNotFoundError";
  }
}

// Performance Profiling Errors (Phase B.6)
export class ProfileNotFoundError extends DaemonError {
  constructor(profileId: string, available?: string[]) {
    super(
      `Profile '${profileId}' not found`,
      ERROR_CODES.PROFILE_NOT_FOUND,
      { profile_id: profileId, available }
    );
    this.name = "ProfileNotFoundError";
  }
}

export class ProfileAlreadyExistsError extends DaemonError {
  constructor(profileId: string) {
    super(
      `Profile '${profileId}' already exists`,
      ERROR_CODES.PROFILE_ALREADY_EXISTS,
      { profile_id: profileId }
    );
    this.name = "ProfileAlreadyExistsError";
  }
}

export class ProfileInvalidError extends DaemonError {
  constructor(message: string) {
    super(
      `Profile invalid: ${message}`,
      ERROR_CODES.PROFILE_INVALID,
      { message }
    );
    this.name = "ProfileInvalidError";
  }
}

// Request result cache entry
interface CacheEntry<T> {
  result: T;
  timestamp: number;
  expiresAt: number;
}

// Pending request with retry info
interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  retryCount: number;
  lastError?: Error;
}

export class WorkflowDaemonClient {
  private process: ChildProcess | null = null;
  private config: Required<DaemonConfig>;
  private pendingRequests: Map<string, PendingRequest> = new Map();
  private requestId = 0;
  private ready = false;
  private readyPromise: Promise<void>;
  private readyResolve: (() => void) | null = null;
  private streamingCallbacks: Set<StreamingEventCallback> = new Set();
  private hitlResolve: ((answer: string) => void) | null = null;

  // Auto-restart state
  private autoRestartCount = 0;
  private lastAutoRestartTime = 0;

  // Request result cache for idempotent retries
  private requestCache: Map<string, CacheEntry<unknown>> = new Map();
  private cleanupTimer: ReturnType<typeof setInterval> | null = null;

  constructor(config: DaemonConfig = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.readyPromise = new Promise((resolve) => {
      this.readyResolve = resolve;
    });

    // Start cache cleanup timer
    this.startCacheCleanupTimer();
  }

  /**
   * Start a timer to periodically clean up expired cache entries
   */
  private startCacheCleanupTimer(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
    this.cleanupTimer = setInterval(() => {
      const now = Date.now();
      for (const [key, entry] of this.requestCache) {
        if (entry.expiresAt < now) {
          this.requestCache.delete(key);
        }
      }
    }, 60000); // Clean up every minute
  }

  /**
   * Generate cache key for a request
   */
  private getCacheKey(method: string, params: Record<string, unknown>): string {
    // Create a deterministic key from method and params
    const paramsStr = JSON.stringify(params, Object.keys(params).sort());
    return `${method}:${paramsStr}`;
  }

  /**
   * Get cached result if available and not expired
   */
  private getCachedResult<T>(method: string, params: Record<string, unknown>): T | null {
    if (!this.config.enableResultCache) {
      return null;
    }

    // Only cache read-only methods
    const cacheableMethods = [
      "daemon.ping",
      "workflow.list",
      "workflow.validate",
      "mcp.servers",
      "mcp.list_tools",
      "cron.list",
      "scheduler.status",
      "scheduler.executions",
      "hooks.list",
      "tools.list",
      "plugins.list",
      "templates.list",
      "templates.categories",
      "templates.featured",
      "templates.popular",
      "templates.newest",
    ];

    if (!cacheableMethods.includes(method)) {
      return null;
    }

    const key = this.getCacheKey(method, params);
    const entry = this.requestCache.get(key) as CacheEntry<T> | undefined;

    if (entry && entry.expiresAt > Date.now()) {
      return entry.result;
    }

    return null;
  }

  /**
   * Cache a result for future idempotent retry
   */
  private cacheResult<T>(method: string, params: Record<string, unknown>, result: T): void {
    if (!this.config.enableResultCache) {
      return;
    }

    const key = this.getCacheKey(method, params);
    const now = Date.now();
    this.requestCache.set(key, {
      result,
      timestamp: now,
      expiresAt: now + this.config.cacheTtl,
    });
  }

  /**
   * Clear the request cache
   */
  clearCache(): void {
    this.requestCache.clear();
  }

  /**
   * Get method-specific timeout
   */
  private getMethodTimeout(method: string): number {
    const timeouts = this.config.methodTimeouts;

    // Map method to timeout config key
    const methodToKey: Record<string, keyof typeof timeouts> = {
      "daemon.ping": "ping",
      "daemon.stop": "ping",
      "workflow.execute": "workflowExecute",
      "workflow.list": "workflowList",
      "workflow.validate": "workflowValidate",
      "workflow.respond": "workflowExecute",
      "mcp.servers": "mcp",
      "mcp.start": "mcp",
      "mcp.stop": "mcp",
      "mcp.list_tools": "mcp",
      "mcp.execute": "mcp",
      "cron.create": "cron",
      "cron.list": "cron",
      "cron.delete": "cron",
      "cron.toggle": "cron",
      "scheduler.start": "cron",
      "scheduler.stop": "cron",
      "scheduler.status": "cron",
      "scheduler.executions": "cron",
      "hooks.list": "hooks",
      "hooks.register": "hooks",
      "hooks.unregister": "hooks",
      "hooks.toggle": "hooks",
      "hooks.execute": "hooks",
      "tools.list": "tools",
      "tools.register": "tools",
      "tools.unregister": "tools",
      "tools.toggle": "tools",
      "tools.execute": "tools",
      "tools.get": "tools",
      "tools.validate": "tools",
      "plugins.list": "default",
      "plugins.get": "default",
      "plugins.search": "default",
      // Template marketplace methods (Phase B.2)
      "templates.list": "default",
      "templates.get": "default",
      "templates.search": "default",
      "templates.categories": "default",
      "templates.install": "default",
      "templates.uninstall": "default",
      "templates.publish": "default",
      "templates.update": "default",
      "templates.delete": "default",
      "templates.rate": "default",
      "templates.review": "default",
      "templates.reviews": "default",
      "templates.featured": "default",
      "templates.popular": "default",
      "templates.newest": "default",
      "templates.versions": "default",
      "templates.download": "default",
    };

    const key = methodToKey[method] || "default";
    return timeouts[key] || timeouts.default || this.config.requestTimeout;
  }

  /**
   * Calculate exponential backoff delay
   */
  private calculateBackoffDelay(retryCount: number): number {
    const baseDelay = this.config.retryBaseDelay;
    const maxDelay = this.config.retryMaxDelay;
    // Exponential backoff: baseDelay * 2^retryCount
    const delay = baseDelay * Math.pow(2, retryCount);
    // Add some jitter
    const jitter = Math.random() * 0.3 * delay;
    return Math.min(delay + jitter, maxDelay);
  }

  /**
   * Start the daemon process
   */
  async start(): Promise<void> {
    if (this.process && this.ready) {
      return;
    }

    // Check if we should auto-restart
    if (this.config.autoRestart && this.autoRestartCount > 0) {
      const now = Date.now();
      const timeSinceLastRestart = now - this.lastAutoRestartTime;

      // Reset restart count if we've been healthy for more than 5 minutes
      if (timeSinceLastRestart > 300000) {
        this.autoRestartCount = 0;
      }

      // Check if we've exceeded max auto-restart attempts
      if (this.autoRestartCount >= this.config.maxAutoRestarts) {
        throw new ConnectionError(
          `Maximum auto-restart attempts (${this.config.maxAutoRestarts}) exceeded. Daemon keeps crashing.`
        );
      }

      // Calculate backoff delay before restart
      const backoffDelay = this.calculateBackoffDelay(this.autoRestartCount);
      console.log(`[Leeway] Daemon crashed. Auto-restarting in ${backoffDelay}ms (attempt ${this.autoRestartCount + 1}/${this.config.maxAutoRestarts})...`);
      await this.sleep(backoffDelay);
    }

    // Spawn the Python daemon
    const pythonModule = await this.getDaemonModule();
    this.process = spawn(this.config.pythonPath, ["-m", pythonModule, "--workflows-dir", this.config.workflowsDir], {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });

    // Handle process errors
    this.process.on("error", (err) => {
      if (this.config.autoRestart) {
        this.handleConnectionErrorWithAutoRestart(`Failed to start daemon: ${err.message}`);
      } else {
        this.handleConnectionError(`Failed to start daemon: ${err.message}`);
      }
    });

    this.process.on("exit", (code) => {
      if (this.config.autoRestart && (code !== 0 || this.autoRestartCount < this.config.maxAutoRestarts)) {
        this.handleConnectionErrorWithAutoRestart(`Daemon exited with code ${code}`);
      } else if (code !== 0 && code !== null) {
        this.handleConnectionError(`Daemon exited with code ${code}`);
      }
      this.cleanup();
    });

    // Create readline interface for stdout
    const rl = readline.createInterface({
      input: this.process.stdout!,
      crlfDelay: Infinity,
    });

    rl.on("line", (line) => {
      this.handleResponse(line);
    });

    // Handle stderr (log output)
    this.process.stderr?.on("data", (data: Buffer) => {
      console.error("[Leeway Daemon]", data.toString().trim());
    });

    // Wait for daemon to be ready with ping
    await this.waitForReady();

    // Reset auto-restart count on successful start
    if (this.autoRestartCount > 0) {
      console.log("[Leeway] Daemon recovered successfully!");
      this.autoRestartCount = 0;
    }

    // Auto-warmup for faster subsequent requests
    const enableWarmup = this.config.enableWarmup ?? true;
    if (enableWarmup) {
      this.warmup().catch((err) => {
        console.warn("[Leeway] Warmup failed:", err.message);
      });
    }
  }

  /**
   * Handle connection error with auto-restart capability
   */
  private handleConnectionErrorWithAutoRestart(message: string): void {
    // Reject all pending requests
    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new ConnectionError(message));
    }
    this.pendingRequests.clear();

    // Increment auto-restart count
    this.autoRestartCount++;
    this.lastAutoRestartTime = Date.now();

    // Cleanup will be called, and the process exit handler will trigger a restart
    this.cleanup();
  }

  /**
   * Get the Python module path for the daemon
   */
  private async getDaemonModule(): Promise<string> {
    // Try to import and find the daemon module path
    // In development, this would be the local src path
    return "leeway_integration.daemon.core";
  }

  /**
   * Wait for daemon to be ready by pinging it
   */
  private async waitForReady(): Promise<void> {
    const timeout = setTimeout(() => {
      this.handleConnectionError("Daemon startup timed out");
    }, this.config.startupTimeout);

    try {
      // Retry ping until ready or timeout
      let attempts = 0;
      while (attempts < this.config.maxRetries) {
        try {
          await this.pingInternal();
          this.ready = true;
          if (this.readyResolve) {
            this.readyResolve();
          }
          break;
        } catch {
          await this.sleep(this.config.retryDelay);
          attempts++;
        }
      }
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * Internal ping without waiting for ready
   */
  private async pingInternal(): Promise<DaemonPingResult> {
    return this.sendRequest<DaemonPingResult>("daemon.ping", {});
  }

  /**
   * Handle daemon response
   */
  private handleResponse(line: string): void {
    let response: JsonRpcResponse;
    try {
      response = JSON.parse(line);
    } catch {
      console.error("[Leeway] Invalid JSON response:", line);
      return;
    }

    // Check if this is a streaming event (no id or special id pattern)
    if (!response.id || response.id.startsWith("_event")) {
      this.handleStreamingEvent(response as unknown as StreamingEvent);
      return;
    }

    const pending = this.pendingRequests.get(response.id);
    if (!pending) {
      // Might be a notification or stray response
      return;
    }

    clearTimeout(pending.timer);
    this.pendingRequests.delete(response.id);

    if (response.error) {
      pending.reject(new DaemonError(
        response.error.message,
        response.error.code,
        response.error.data
      ));
    } else {
      pending.resolve(response.result);
    }
  }

  /**
   * Handle streaming events (progress, HITL, branch, node events)
   */
  private handleStreamingEvent(event: StreamingEvent): void {
    // Emit to all registered callbacks
    for (const callback of this.streamingCallbacks) {
      try {
        callback(event);
      } catch (err) {
        console.error("[Leeway] Streaming callback error:", err);
      }
    }

    // Handle HITL signals specially - emit for user interaction
    if (event.type === "signal") {
      const hitlEvent = event as HitlSignalEvent;
      console.log(`\n🤔 ${hitlEvent.question}`);
      if (hitlEvent.options.length > 0) {
        for (const opt of hitlEvent.options) {
          console.log(`  [${opt.label}] ${opt.description}`);
        }
      }
    }

    // Handle other events - just log progress
    if (event.type === "progress") {
      const progress = event as ProgressEvent;
      if (progress.message) {
        console.log(progress.message);
      }
    }

    // Handle workflow events
    if (event.type === "workflow") {
      const wfEvent = event as WorkflowEvent;
      if (wfEvent.action === "started") {
        console.log(`\n▶ Workflow '${wfEvent.workflow_name}' started`);
      } else if (wfEvent.action === "completed") {
        console.log(`✓ Workflow '${wfEvent.workflow_name}' completed`);
      } else if (wfEvent.action === "failed") {
        console.error(`✗ Workflow '${wfEvent.workflow_name}' failed`);
      }
    }

    // Handle node events
    if (event.type === "node") {
      const nodeEvent = event as NodeEvent;
      if (nodeEvent.action === "started") {
        console.log(`  ● Node '${nodeEvent.node_name}' started`);
      } else if (nodeEvent.action === "completed") {
        if (nodeEvent.signal_summary) {
          console.log(`    ⇢ ${nodeEvent.signal_summary}`);
        }
      } else if (nodeEvent.action === "failed") {
        console.error(`✗ Node '${nodeEvent.node_name}' failed`);
      }
    }
  }

  /**
   * Send a JSON-RPC request with timeout handling and retry support
   */
  private async sendRequest<T>(method: string, params: Record<string, unknown>, retryOptions?: {
    /** Enable automatic retry on failure */
    enableRetry?: boolean;
    /** Override max retries for this request */
    maxRetries?: number;
  }): Promise<T> {
    const enableRetry = retryOptions?.enableRetry ?? true;
    const maxRetries = retryOptions?.maxRetries ?? this.config.maxRetries;

    // Check cache for read-only methods first
    const cachedResult = this.getCachedResult<T>(method, params);
    if (cachedResult !== null) {
      return cachedResult;
    }

    let lastError: Error | null = null;
    let attempt = 0;

    while (attempt <= maxRetries) {
      try {
        return await this.executeRequest<T>(method, params);
      } catch (error) {
        lastError = error as Error;
        attempt++;

        // Don't retry if we hit max retries
        if (attempt > maxRetries) {
          break;
        }

        // Determine if this error is retryable
        const isRetryable = this.isErrorRetryable(error);
        if (!isRetryable || !enableRetry) {
          break;
        }

        // Calculate backoff delay
        const delay = this.calculateBackoffDelay(attempt - 1);
        console.log(`[Leeway] Request failed: ${(error as Error).message}. Retrying in ${delay}ms (attempt ${attempt}/${maxRetries})...`);
        await this.sleep(delay);
      }
    }

    // All retries exhausted, throw the last error
    throw lastError;
  }

  /**
   * Determine if an error is retryable
   */
  private isErrorRetryable(error: Error): boolean {
    // Retry on connection errors, timeouts, and transient errors
    const retryableErrors = [
      "ConnectionError",
      "RequestTimeoutError",
    ];

    const isTransient = error.name === "ConnectionError" || error.name === "RequestTimeoutError";

    // Also check message patterns
    const message = error.message.toLowerCase();
    const retryablePatterns = [
      "connection",
      "timeout",
      "econnrefused",
      "enoent",
      "not running",
      "crashed",
      "exited with code",
    ];

    return isTransient || retryablePatterns.some((pattern) => message.includes(pattern));
  }

  /**
   * Execute a single request (without retry logic)
   */
  private async executeRequest<T>(method: string, params: Record<string, unknown>): Promise<T> {
    await this.readyPromise;

    if (!this.process || !this.process.stdin) {
      // If daemon is not running, try to restart it
      if (this.config.autoRestart && this.autoRestartCount < this.config.maxAutoRestarts) {
        await this.start();
      } else {
        throw new ConnectionError("Daemon process not running");
      }
    }

    const id = `req-${++this.requestId}`;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    // Get method-specific timeout
    const timeout = this.getMethodTimeout(method);

    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new RequestTimeoutError(`${method} timed out after ${timeout}ms`));
      }, timeout);

      this.pendingRequests.set(id, {
        resolve: resolve as (result: unknown) => void,
        reject,
        timer,
        retryCount: 0,
      });

      try {
        this.process!.stdin!.write(JSON.stringify(request) + "\n");
      } catch (err) {
        // If write fails, the process might have crashed
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        if (this.config.autoRestart) {
          this.handleConnectionErrorWithAutoRestart(`Failed to write request: ${(err as Error).message}`);
        } else {
          this.handleConnectionError(`Failed to write request: ${(err as Error).message}`);
        }
        reject(new ConnectionError(`Failed to write request: ${(err as Error).message}`));
      }
    });
  }

  /**
   * Send a JSON-RPC request (legacy compatibility)
   */
  private async sendRequestLegacy<T>(method: string, params: Record<string, unknown>): Promise<T> {
    return this.sendRequest<T>(method, params);
  }

  /**
   * Handle connection error
   */
  private handleConnectionError(message: string): void {
    // Reject all pending requests
    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new ConnectionError(message));
    }
    this.pendingRequests.clear();
    this.cleanup();
  }

  /**
   * Cleanup resources
   */
  private cleanup(): void {
    this.ready = false;
    this.process = null;
    // Create a new ready promise for restart
    this.readyPromise = new Promise((resolve) => {
      this.readyResolve = resolve;
    });
  }

  /**
   * Get the current auto-restart count
   */
  getAutoRestartCount(): number {
    return this.autoRestartCount;
  }

  /**
   * Reset the auto-restart count (e.g., after manual restart)
   */
  resetAutoRestartCount(): void {
    this.autoRestartCount = 0;
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { size: number; hitRate: number } {
    return {
      size: this.requestCache.size,
      hitRate: 0, // Could track hits/misses if needed
    };
  }

  /**
   * Stop the daemon and cleanup resources
   */
  destroy(): void {
    // Stop cache cleanup timer
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }

    // Clear cache
    this.requestCache.clear();

    // Kill process
    if (this.process) {
      this.process.kill();
    }

    // Cleanup
    this.cleanup();
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Ping the daemon to check health
   */
  async ping(): Promise<DaemonPingResult> {
    return this.sendRequest<DaemonPingResult>("daemon.ping", {});
  }

  /**
   * Execute a workflow
   */
  async executeWorkflow(params: WorkflowExecuteParams): Promise<WorkflowExecuteResult> {
    return this.sendRequest<WorkflowExecuteResult>("workflow.execute", params as Record<string, unknown>);
  }

  /**
   * List available workflows
   */
  async listWorkflows(): Promise<WorkflowListResult> {
    return this.sendRequest<WorkflowListResult>("workflow.list", {});
  }

  /**
   * Validate a workflow
   */
  async validateWorkflow(name: string): Promise<WorkflowValidateResult> {
    return this.sendRequest<WorkflowValidateResult>("workflow.validate", { name });
  }

  /**
   * Stop the daemon
   */
  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    try {
      await this.sendRequest("daemon.stop", {});
    } finally {
      this.process.kill();
      this.cleanup();
    }
  }

  /**
   * Check if daemon is ready
   */
  isReady(): boolean {
    return this.ready;
  }

  /**
   * Ensure daemon is running, start if necessary
   */
  async ensure(): Promise<void> {
    if (!this.ready) {
      await this.start();
    }
  }

  /**
   * Register a callback for streaming events
   */
  onStreamingEvent(callback: StreamingEventCallback): () => void {
    this.streamingCallbacks.add(callback);
    // Return unsubscribe function
    return () => {
      this.streamingCallbacks.delete(callback);
    };
  }

  /**
   * Respond to a HITL question
   */
  async respondToHitl(answer: string): Promise<{ received: boolean; answer: string }> {
    return this.sendRequest<{ received: boolean; answer: string }>("workflow.respond", { answer });
  }

  /**
   * Execute a workflow with streaming event support
   * Returns a tuple of [result, eventPromise] where eventPromise resolves when workflow completes
   */
  async executeWorkflowWithStreaming(
    params: WorkflowExecuteParams,
    onEvent?: StreamingEventCallback
  ): Promise<WorkflowExecuteResult> {
    // Register callback if provided
    let unsubscribe: (() => void) | undefined;
    if (onEvent) {
      unsubscribe = this.onStreamingEvent(onEvent);
    }

    try {
      return await this.executeWorkflow(params);
    } finally {
      if (unsubscribe) {
        unsubscribe();
      }
    }
  }

  // MCP Methods

  /**
   * List all configured MCP servers
   */
  async listMcpServers(): Promise<McpServersResult> {
    return this.sendRequest<McpServersResult>("mcp.servers", {});
  }

  /**
   * Start an MCP server
   */
  async startMcpServer(serverName: string): Promise<{ name: string; status: string }> {
    return this.sendRequest<{ name: string; status: string }>("mcp.start", { server_name: serverName });
  }

  /**
   * Stop an MCP server
   */
  async stopMcpServer(serverName: string): Promise<{ name: string; status: string }> {
    return this.sendRequest<{ name: string; status: string }>("mcp.stop", { server_name: serverName });
  }

  /**
   * List tools available from an MCP server
   */
  async listMcpTools(serverName: string): Promise<McpListToolsResult> {
    return this.sendRequest<McpListToolsResult>("mcp.list_tools", { server_name: serverName });
  }

  /**
   * Execute a tool on an MCP server
   */
  async executeMcpTool(
    serverName: string,
    toolName: string,
    arguments_: Record<string, unknown> = {}
  ): Promise<McpExecuteResult> {
    return this.sendRequest<McpExecuteResult>("mcp.execute", {
      server_name: serverName,
      tool_name: toolName,
      arguments: arguments_,
    });
  }

  // Cron Methods

  /**
   * Create a new cron schedule
   */
  async createCronSchedule(params: CronCreateParams): Promise<CronCreateResult> {
    return this.sendRequest<CronCreateResult>("cron.create", params as Record<string, unknown>);
  }

  /**
   * List all cron schedules
   */
  async listCronSchedules(): Promise<CronListResult> {
    return this.sendRequest<CronListResult>("cron.list", {});
  }

  /**
   * Delete a cron schedule
   */
  async deleteCronSchedule(id: string): Promise<CronDeleteResult> {
    return this.sendRequest<CronDeleteResult>("cron.delete", { id });
  }

  /**
   * Toggle a cron schedule enabled/disabled
   */
  async toggleCronSchedule(id: string, enabled: boolean): Promise<CronToggleResult> {
    return this.sendRequest<CronToggleResult>("cron.toggle", { id, enabled });
  }

  // Cache Methods

  /**
   * Get cache statistics
   */
  async getCacheStats(): Promise<CacheStats> {
    return this.sendRequest<CacheStats>("cache.get_stats", {});
  }

  /**
   * Clear all cache entries
   */
  async clearCache(): Promise<CacheClearResult> {
    return this.sendRequest<CacheClearResult>("cache.clear", {});
  }

  /**
   * Invalidate specific cache entries
   * @param method Optional method name to invalidate
   * @param pattern Optional pattern to match methods for invalidation
   */
  async invalidateCache(method?: string, pattern?: string): Promise<CacheInvalidateResult> {
    return this.sendRequest<CacheInvalidateResult>("cache.invalidate", {
      method: method || undefined,
      pattern: pattern || undefined,
    });
  }

  /**
   * Warmup the daemon - pre-load resources for faster subsequent requests
   * @param workflows List of workflow names to pre-load (default: all)
   * @param preloadMcp Whether to pre-start MCP servers (default: false)
   */
  async warmup(workflows?: string[], preloadMcp?: boolean): Promise<WarmupResult> {
    return this.sendRequest<WarmupResult>("daemon.warmup", {
      workflows: workflows || [],
      preload_mcp: preloadMcp || false,
    });
  }

  // Template Marketplace Methods (Phase B.2)

  /**
   * List templates with filtering and pagination
   */
  async listTemplates(params: TemplateListParams): Promise<TemplateListResult> {
    return this.sendRequest<TemplateListResult>("templates.list", params as Record<string, unknown>);
  }

  /**
   * Get a template by ID
   */
  async getTemplate(templateId: string): Promise<TemplateGetResult> {
    return this.sendRequest<TemplateGetResult>("templates.get", { template_id: templateId });
  }

  /**
   * Search templates with advanced options
   */
  async searchTemplates(query: string, params?: {
    category?: string;
    tags?: string[];
    author?: string;
    min_rating?: number;
    page?: number;
    limit?: number;
  }): Promise<TemplateSearchResult> {
    return this.sendRequest<TemplateSearchResult>("templates.search", {
      query,
      ...params,
    } as Record<string, unknown>);
  }

  /**
   * List template categories
   */
  async listTemplateCategories(parentId?: string): Promise<TemplateCategoriesResult> {
    return this.sendRequest<TemplateCategoriesResult>("templates.categories", {
      parent_id: parentId,
    });
  }

  /**
   * Install a template to local workflows
   */
  async installTemplate(params: TemplateInstallParams): Promise<TemplateInstallResult> {
    return this.sendRequest<TemplateInstallResult>("templates.install", params as Record<string, unknown>);
  }

  /**
   * Uninstall a template
   */
  async uninstallTemplate(templateId: string, deleteFiles?: boolean): Promise<TemplateUninstallResult> {
    return this.sendRequest<TemplateUninstallResult>("templates.uninstall", {
      template_id: templateId,
      delete_files: deleteFiles || false,
    });
  }

  /**
   * Publish a new template
   */
  async publishTemplate(params: TemplatePublishParams): Promise<TemplatePublishResult> {
    return this.sendRequest<TemplatePublishResult>("templates.publish", params as Record<string, unknown>);
  }

  /**
   * Update an existing template
   */
  async updateTemplate(params: TemplateUpdateParams): Promise<TemplateUpdateResult> {
    return this.sendRequest<TemplateUpdateResult>("templates.update", params as Record<string, unknown>);
  }

  /**
   * Delete a template
   */
  async deleteTemplate(templateId: string, reason?: string): Promise<TemplateDeleteResult> {
    return this.sendRequest<TemplateDeleteResult>("templates.delete", {
      template_id: templateId,
      reason,
    });
  }

  /**
   * Rate a template
   */
  async rateTemplate(templateId: string, rating: number, userId?: string): Promise<TemplateRateResult> {
    return this.sendRequest<TemplateRateResult>("templates.rate", {
      template_id: templateId,
      rating,
      user_id: userId || "anonymous",
    });
  }

  /**
   * Add a review to a template
   */
  async reviewTemplate(params: TemplateReviewParams): Promise<TemplateReviewResult> {
    return this.sendRequest<TemplateReviewResult>("templates.review", params as Record<string, unknown>);
  }

  /**
   * Get reviews for a template
   */
  async getTemplateReviews(templateId: string, page?: number, limit?: number): Promise<TemplateReviewsResult> {
    return this.sendRequest<TemplateReviewsResult>("templates.reviews", {
      template_id: templateId,
      page: page || 1,
      limit: limit || 10,
    });
  }

  /**
   * Get featured templates
   */
  async getFeaturedTemplates(category?: string, limit?: number): Promise<TemplateFeaturedResult> {
    return this.sendRequest<TemplateFeaturedResult>("templates.featured", {
      category,
      limit: limit || 10,
    });
  }

  /**
   * Get popular templates
   */
  async getPopularTemplates(params?: TemplatePopularParams): Promise<TemplatePopularResult> {
    return this.sendRequest<TemplatePopularResult>("templates.popular", params || {});
  }

  /**
   * Get newest templates
   */
  async getNewestTemplates(category?: string, limit?: number): Promise<TemplateNewestResult> {
    return this.sendRequest<TemplateNewestResult>("templates.newest", {
      category,
      limit: limit || 10,
    });
  }

  /**
   * Get versions of a template
   */
  async getTemplateVersions(templateId: string): Promise<TemplateVersionsResult> {
    return this.sendRequest<TemplateVersionsResult>("templates.versions", { template_id: templateId });
  }

  /**
   * Download template content
   */
  async downloadTemplate(templateId: string, version?: string): Promise<TemplateDownloadResult> {
    return this.sendRequest<TemplateDownloadResult>("templates.download", {
      template_id: templateId,
      version,
    });
  }

  // =============================================================================
  // Phase B.3: Visual Editor Methods
  // =============================================================================

  /**
   * Create a new editor project
   */
  async createEditorProject(name: string, description?: string, content?: string, metadata?: EditorMetadata): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.create_project", {
      name,
      description,
      content,
      metadata,
    });
  }

  /**
   * Open an existing project or import from workflow file
   */
  async openEditorProject(projectId?: string, workflowName?: string): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.open_project", {
      project_id: projectId,
      workflow_name: workflowName,
    });
  }

  /**
   * Save a project
   */
  async saveEditorProject(projectId: string, content?: string, validate?: boolean): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.save_project", {
      project_id: projectId,
      content,
      validate: validate ?? true,
    });
  }

  /**
   * List all editor projects
   */
  async listEditorProjects(limit?: number, offset?: number): Promise<{ projects: EditorProjectSummary[]; total: number }> {
    return this.sendRequest("editor.list_projects", {
      limit: limit ?? 20,
      offset: offset ?? 0,
    });
  }

  /**
   * Delete a project
   */
  async deleteEditorProject(projectId: string): Promise<{ success: boolean; deleted_id?: string; error?: string }> {
    return this.sendRequest("editor.delete_project", {
      project_id: projectId,
    });
  }

  /**
   * Add a node to a project
   */
  async addEditorNode(projectId: string, node: EditorNode): Promise<{ success: boolean; project_id: string; node?: EditorNode; error?: string }> {
    return this.sendRequest("editor.add_node", {
      project_id: projectId,
      node,
    });
  }

  /**
   * Update a node in a project
   */
  async updateEditorNode(projectId: string, nodeId: string, node: EditorNode): Promise<{ success: boolean; project_id: string; node?: EditorNode; error?: string }> {
    return this.sendRequest("editor.update_node", {
      project_id: projectId,
      node_id: nodeId,
      node,
    });
  }

  /**
   * Delete a node from a project
   */
  async deleteEditorNode(projectId: string, nodeId: string): Promise<{ success: boolean; project_id: string; error?: string }> {
    return this.sendRequest("editor.delete_node", {
      project_id: projectId,
      node_id: nodeId,
    });
  }

  /**
   * Add an edge to a project
   */
  async addEditorEdge(projectId: string, edge: EditorEdge): Promise<{ success: boolean; project_id: string; edge?: EditorEdge; error?: string }> {
    return this.sendRequest("editor.add_edge", {
      project_id: projectId,
      edge,
    });
  }

  /**
   * Update an edge in a project
   */
  async updateEditorEdge(projectId: string, edgeId: string, edge: EditorEdge): Promise<{ success: boolean; project_id: string; edge?: EditorEdge; error?: string }> {
    return this.sendRequest("editor.update_edge", {
      project_id: projectId,
      edge_id: edgeId,
      edge,
    });
  }

  /**
   * Delete an edge from a project
   */
  async deleteEditorEdge(projectId: string, edgeId: string): Promise<{ success: boolean; project_id: string; error?: string }> {
    return this.sendRequest("editor.delete_edge", {
      project_id: projectId,
      edge_id: edgeId,
    });
  }

  /**
   * Validate a project or raw content
   */
  async validateEditor(projectId?: string, content?: string): Promise<EditorValidationResult> {
    return this.sendRequest("editor.validate", {
      project_id: projectId,
      content,
    });
  }

  /**
   * Export a project
   */
  async exportEditorProject(projectId: string, options?: EditorExportOptions): Promise<{ success: boolean; content?: string; format: string; error?: string }> {
    return this.sendRequest("editor.export", {
      project_id: projectId,
      options,
    });
  }

  /**
   * Import workflow content as a new project
   */
  async importEditorContent(content: string, name?: string, description?: string): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.import", {
      content,
      name,
      description,
    });
  }

  /**
   * Preview project content
   */
  async previewEditorProject(projectId: string, format?: string): Promise<{ success: boolean; content?: string; format: string }> {
    return this.sendRequest("editor.preview", {
      project_id: projectId,
      format: format ?? "yaml",
    });
  }

  /**
   * Auto-layout nodes in a project
   */
  async autoLayoutEditorProject(projectId: string, direction?: string): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.auto_layout", {
      project_id: projectId,
      direction: direction ?? "top-bottom",
    });
  }

  /**
   * Duplicate a node
   */
  async duplicateEditorNode(projectId: string, nodeId: string, offsetX?: number, offsetY?: number): Promise<{ success: boolean; project_id: string; new_node?: EditorNode; error?: string }> {
    return this.sendRequest("editor.duplicate_node", {
      project_id: projectId,
      node_id: nodeId,
      offset_x: offsetX ?? 50,
      offset_y: offsetY ?? 50,
    });
  }

  /**
   * Undo last operation
   */
  async undoEditorProject(projectId: string): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.undo", {
      project_id: projectId,
    });
  }

  /**
   * Redo last undone operation
   */
  async redoEditorProject(projectId: string): Promise<{ success: boolean; project?: EditorProject; error?: string }> {
    return this.sendRequest("editor.redo", {
      project_id: projectId,
    });
  }

  // =============================================================================
  // Phase B.4: LLM Provider Methods
  // =============================================================================

  /**
   * List all LLM providers
   */
  async listLlmProviders(): Promise<{ providers: LlmProviderInfo[]; error?: string }> {
    return this.sendRequest("llm.providers", {});
  }

  /**
   * List all LLM models, optionally filtered by provider
   */
  async listLlmModels(provider?: string): Promise<{ models: LlmModelInfo[]; error?: string }> {
    return this.sendRequest("llm.models", { provider });
  }

  /**
   * Execute an LLM completion
   */
  async executeLlmCompletion(params: LlmCompletionParams): Promise<LlmCompletionResult> {
    return this.sendRequest("llm.execute", params);
  }

  /**
   * Set API key for an LLM provider
   */
  async setLlmApiKey(provider: string, apiKey: string): Promise<{ success: boolean; provider: string; message: string }> {
    return this.sendRequest("llm.set_api_key", { provider, api_key: apiKey });
  }

  // =============================================================================
  // Phase B.5: Testing Framework Methods
  // =============================================================================

  /**
   * List tests with optional filters
   */
  async listTests(workflowName?: string, tag?: string, type?: string): Promise<{ tests: WorkflowTestCase[]; total: number }> {
    return this.sendRequest("tests.list", {
      workflow_name: workflowName,
      tag,
      type,
    });
  }

  /**
   * Get a test by ID
   */
  async getTest(testId: string): Promise<{ test?: WorkflowTestCase }> {
    return this.sendRequest("tests.get", { test_id: testId });
  }

  /**
   * Create a new test
   */
  async createTest(test: WorkflowTestCase): Promise<{ success: boolean; test?: WorkflowTestCase; error?: string }> {
    return this.sendRequest("tests.create", { test });
  }

  /**
   * Update an existing test
   */
  async updateTest(testId: string, test: WorkflowTestCase): Promise<{ success: boolean; test?: WorkflowTestCase; error?: string }> {
    return this.sendRequest("tests.update", { test_id: testId, test });
  }

  /**
   * Delete a test
   */
  async deleteTest(testId: string): Promise<{ success: boolean; deleted_id?: string; error?: string }> {
    return this.sendRequest("tests.delete", { test_id: testId });
  }

  /**
   * Run a single test
   */
  async runTest(testId: string, workflowName?: string, input?: Record<string, unknown>): Promise<{ success: boolean; result?: WorkflowTestResult; error?: string }> {
    return this.sendRequest("tests.run", {
      test_id: testId,
      workflow_name: workflowName,
      input,
    });
  }

  /**
   * Run multiple tests
   */
  async runTests(testIds: string[], workflowName?: string, parallel?: boolean): Promise<{
    success: boolean;
    results: WorkflowTestResult[];
    total: number;
    passed: number;
    failed: number;
    duration_ms: number;
  }> {
    return this.sendRequest("tests.run_many", {
      test_ids: testIds,
      workflow_name: workflowName,
      parallel: parallel ?? false,
    });
  }

  /**
   * Duplicate a test
   */
  async duplicateTest(testId: string, newName?: string): Promise<{ success: boolean; new_test?: WorkflowTestCase; error?: string }> {
    return this.sendRequest("tests.duplicate", {
      test_id: testId,
      new_name: newName,
    });
  }

  /**
   * Get coverage report for a workflow
   */
  async getTestCoverage(workflowName: string, testIds?: string[]): Promise<{ success: boolean; report?: TestCoverageReport; error?: string }> {
    return this.sendRequest("tests.coverage", {
      workflow_name: workflowName,
      test_ids: testIds,
    });
  }

  /**
   * Get test metrics
   */
  async getTestMetrics(workflowName?: string, timeRange?: string): Promise<{ metrics: TestMetrics }> {
    return this.sendRequest("tests.metrics", {
      workflow_name: workflowName,
      time_range: timeRange,
    });
  }

  /**
   * Get test execution history
   */
  async getTestHistory(testId?: string, limit?: number): Promise<{ executions: Record<string, unknown>[]; total: number }> {
    return this.sendRequest("tests.history", {
      test_id: testId,
      limit: limit ?? 10,
    });
  }

  // Test Suite Methods

  /**
   * Create a test suite
   */
  async createTestSuite(name: string, description?: string, testIds?: string[], tags?: string[]): Promise<{ success: boolean; suite?: WorkflowTestSuite; error?: string }> {
    return this.sendRequest("tests.suite.create", {
      name,
      description,
      test_ids: testIds ?? [],
      tags: tags ?? [],
    });
  }

  /**
   * List test suites
   */
  async listTestSuites(tag?: string): Promise<{ suites: WorkflowTestSuite[]; total: number }> {
    return this.sendRequest("tests.suite.list", { tag });
  }

  /**
   * Run a test suite
   */
  async runTestSuite(suiteId: string, parallel?: boolean): Promise<{ success: boolean; result?: WorkflowTestSuiteResult; error?: string }> {
    return this.sendRequest("tests.suite.run", {
      suite_id: suiteId,
      parallel: parallel ?? false,
    });
  }

  /**
   * Delete a test suite
   */
  async deleteTestSuite(suiteId: string): Promise<{ success: boolean; deleted_id?: string; error?: string }> {
    return this.sendRequest("tests.suite.delete", { suite_id: suiteId });
  }

  // =============================================================================
  // Phase B.6: Performance Profiling Methods
  // =============================================================================

  /**
   * Start profiling a workflow
   */
  async startProfiler(workflowName: string, sampleIntervalMs?: number): Promise<{ success: boolean; profile_id?: string; message?: string }> {
    return this.sendRequest("profiler.start", {
      workflow_name: workflowName,
      sample_interval_ms: sampleIntervalMs ?? 1000,
    });
  }

  /**
   * Stop profiling
   */
  async stopProfiler(profileId?: string): Promise<{ success: boolean; profile_id?: string; profile?: WorkflowProfileData }> {
    return this.sendRequest("profiler.stop", {
      profile_id: profileId,
    });
  }

  /**
   * List profiles
   */
  async listProfiles(workflowName?: string, limit?: number): Promise<{ profiles: WorkflowProfileSummary[]; total: number }> {
    return this.sendRequest("profiler.list", {
      workflow_name: workflowName,
      limit: limit ?? 10,
    });
  }

  /**
   * Get a specific profile
   */
  async getProfile(profileId: string): Promise<{ profile: WorkflowProfileData }> {
    return this.sendRequest("profiler.get", { profile_id: profileId });
  }

  /**
   * Delete a profile
   */
  async deleteProfile(profileId: string): Promise<{ success: boolean; deleted_id?: string }> {
    return this.sendRequest("profiler.delete", { profile_id: profileId });
  }

  /**
   * Get performance metrics
   */
  async getProfilerMetrics(workflowName?: string, timeRange?: string): Promise<{ metrics: PerformanceMetrics }> {
    return this.sendRequest("profiler.metrics", {
      workflow_name: workflowName,
      time_range: timeRange,
    });
  }

  /**
   * Get slowest nodes
   */
  async getSlowestNodes(workflowName: string, limit?: number): Promise<{ report: SlowestNodesReport }> {
    return this.sendRequest("profiler.slowest", {
      workflow_name: workflowName,
      limit: limit ?? 10,
    });
  }

  /**
   * Get performance bottlenecks
   */
  async getBottlenecks(workflowName: string): Promise<{ report: BottleneckReport }> {
    return this.sendRequest("profiler.bottlenecks", {
      workflow_name: workflowName,
    });
  }

  /**
   * Export a profile
   */
  async exportProfile(profileId: string, format?: string): Promise<{ success: boolean; content?: string; format?: string }> {
    return this.sendRequest("profiler.export", {
      profile_id: profileId,
      format: format ?? "json",
    });
  }

  /**
   * Clear profiles
   */
  async clearProfiles(workflowName?: string): Promise<{ success: boolean; deleted_count: number }> {
    return this.sendRequest("profiler.clear", {
      workflow_name: workflowName,
    });
  }
}

/**
 * LLM Provider types (Phase B.4)
 */
export interface LlmProviderInfo {
  name: string;
  display_name: string;
  description: string;
  supports_streaming: boolean;
  supports_vision: boolean;
  supports_function_calling: boolean;
  supports_json_mode: boolean;
  default_models: string[];
  authentication: string;
  base_url: string | null;
}

export interface LlmModelInfo {
  id: string;
  display_name: string;
  provider: string;
  description: string;
  context_window: number;
  max_output_tokens: number;
  supports_streaming: boolean;
  supports_vision: boolean;
  supports_function_calling: boolean;
  supports_json_mode: boolean;
  pricing: Record<string, number> | null;
}

export interface LlmMessage {
  role: string;
  content: string;
}

export interface LlmTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface LlmCompletionParams {
  model: string;
  messages: LlmMessage[];
  provider?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  stream?: boolean;
  tools?: LlmTool[];
  system?: string;
}

export interface LlmCompletionResult {
  success: boolean;
  completion: {
    id: string;
    model: string;
    content: string | null;
    finish_reason: string | null;
    usage: Record<string, number>;
    provider: string;
    created_at: string;
  } | null;
  error: string | null;
}

// LLM Error codes (Phase B.4)
export const LLM_ERROR_CODES = {
  PROVIDER_NOT_FOUND: -33100,
  MODEL_NOT_FOUND: -33101,
  AUTHENTICATION_FAILED: -33102,
  RATE_LIMIT_EXCEEDED: -33103,
  INVALID_REQUEST: -33104,
  PROVIDER_ERROR: -33105,
  CONTEXT_LENGTH_EXCEEDED: -33106,
} as const;

// Singleton instance
let daemonClient: WorkflowDaemonClient | null = null;

/**
 * Get or create the singleton daemon client
 */
export function getDaemonClient(config?: DaemonConfig): WorkflowDaemonClient {
  if (!daemonClient) {
    daemonClient = new WorkflowDaemonClient(config);
  }
  return daemonClient;
}

/**
 * Reset the daemon client (for testing)
 */
export function resetDaemonClient(): void {
  daemonClient = null;
}