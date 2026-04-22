# workflow-handler

Meta-skill that tells the LLM when and how to use the workflow tool.

## When to Use Workflow Tool

Use the `workflow` tool when the user asks for:

1. **Code health check** - "check code quality", "analyze codebase", "code review"
2. **API design review** - "review API", "check API design", "API documentation"
3. **Security scan** - "scan for vulnerabilities", "security audit", "check for bugs"
4. **PR review** - "review PR", "check pull request"
5. **GitHub search** - "search GitHub", "find code examples"
6. **Research** - "research topic", "find information"

## Workflow Invocation Syntax

```typescript
workflow({
  name: "<workflow-name>",
  user_context: "<task-description>"
})
```

## Available Workflows

| Workflow | Use Case |
|----------|----------|
| code-health | Code structure scanning, classification, review |
| api-design | API design review, documentation |
| pr-review | Pull request review |
| security-scan | Security vulnerability scanning |
| github-search | GitHub code search (MCP) |
| research-assistant | Multi-source research (MCP) |

## Interpreting Results

- **Success**: The workflow completed with results
- **Error**: Check the error message and retry if needed
- **Streaming**: Progress events are streamed in real-time
- **HITL**: Some workflows may require human input

## Error Handling

- Workflow not found: Check if the workflow name is correct
- Tool execution failed: Check the error details
- Permission denied: Ensure proper permissions
