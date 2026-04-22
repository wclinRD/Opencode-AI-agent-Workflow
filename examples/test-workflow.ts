/**
 * Test script for Leeway Workflow Integration
 *
 * This script demonstrates how to use the workflow tool.
 * Run with: npx ts-node examples/test-workflow.ts
 *
 * Note: This requires the TypeScript code to be compiled or run with ts-node.
 */

import { getDaemonClient, WorkflowDaemonClient } from "../src/tools/workflow-daemon";

// Configuration
const config = {
  workflowsDir: ".leeway/workflows",
  pythonPath: "python",
  startupTimeout: 5000,
  requestTimeout: 30000,
};

async function main() {
  console.log("Starting Leeway workflow test...\n");

  // Create daemon client
  const daemon = new WorkflowDaemonClient(config);

  try {
    // Start the daemon
    console.log("1. Starting daemon...");
    await daemon.start();
    console.log("   Daemon started successfully\n");

    // Ping
    console.log("2. Pinging daemon...");
    const pingResult = await daemon.ping();
    console.log(`   Version: ${pingResult.version}`);
    console.log(`   Status: ${pingResult.status}\n`);

    // List workflows
    console.log("3. Listing workflows...");
    const listResult = await daemon.listWorkflows();
    console.log(`   Available: ${listResult.workflows.join(", ")}\n`);

    // Execute workflow
    console.log("4. Executing 'code-health' workflow...");
    const execResult = await daemon.executeWorkflow({
      name: "code-health",
      user_context: "Test the workflow integration",
    });

    console.log(`   Success: ${execResult.success}`);
    console.log(`   Output: ${execResult.final_output.substring(0, 100)}...`);
    if (execResult.audit) {
      console.log(`   Path: ${execResult.audit.path_taken.join(" -> ") || "(empty)"}`);
      console.log(`   Total turns: ${execResult.audit.total_turns}`);
    }

    // Validate workflow
    console.log("\n5. Validating 'code-health' workflow...");
    const validateResult = await daemon.validateWorkflow("code-health");
    console.log(`   Valid: ${validateResult.valid}`);
    if (validateResult.errors.length > 0) {
      console.log(`   Errors: ${validateResult.errors.join(", ")}`);
    }

    // Stop daemon
    console.log("\n6. Stopping daemon...");
    await daemon.stop();
    console.log("   Daemon stopped\n");

    console.log("✅ All tests passed!");
  } catch (error) {
    console.error("\n❌ Test failed:", error);
    process.exit(1);
  }
}

main();
