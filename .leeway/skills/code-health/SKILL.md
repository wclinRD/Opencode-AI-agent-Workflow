# code-health

Code health check guidelines for analyzing and reviewing codebase structure.

## Overview

The code-health workflow performs comprehensive code structure analysis:
- File organization and structure
- Code classification by type
- Quality metrics and review
- Report generation

## Code Classification Types

| Type | Description | Indicators |
|------|-------------|-----------|
| `core` | Core business logic | Domain models, services |
| `api` | API endpoints | Route handlers, controllers |
| `util` | Utility functions | Helper functions, formatters |
| `config` | Configuration | Settings, constants |
| `test` | Test files | Specs, mocks, fixtures |
| `db` | Database related | Queries, migrations |
| `ui` | User interface | Components, views |
| `unknown` | Unclassified | Needs review |

## Review Checklist

### Structure
- [ ] Files are properly organized
- [ ] Naming conventions followed
- [ ] Clear directory structure
- [ ] No circular dependencies

### Quality
- [ ] Code is modular
- [ ] Functions are small and focused
- [ ] Proper error handling
- [ ] No code duplication

### Documentation
- [ ] Public APIs documented
- [ ] Complex logic explained
- [ ] Examples provided
- [ ] Changelog updated

## Report Format

```yaml
summary:
  total_files: <number>
  total_lines: <number>
  categorized: <percentage>

by_type:
  core: { count: <n>, lines: <n> }
  api: { count: <n>, lines: <n> }
  # ...

recommendations:
  - <issue>
  - <suggestion>
```

## Usage Example

```typescript
workflow({
  name: "code-health",
  user_context: "Analyze the codebase at ./src"
})
```