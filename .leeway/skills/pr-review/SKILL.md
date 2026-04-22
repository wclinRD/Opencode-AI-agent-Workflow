# pr-review

Pull request review checklist and guidelines.

## Pre-PR Checklist

Before submitting a PR, ensure:

- [ ] Tests pass locally
- [ ] Lint passes
- [ ] Types check (TypeScript)
- [ ] No console.log or debug code
- [ ] No hardcoded values
- [ ] Documentation updated if needed
- [ ] Commit messages are meaningful

## PR Description Requirements

A good PR description includes:

1. **Title**: Clear, concise summary
2. **Overview**: What and why
3. **Changes**: What was modified
4. **Testing**: How to test
5. **Screenshots**: If UI changes
6. **Related Issues**: Links to issues

### Template
```markdown
## Overview
<!-- Brief description of changes -->

## Changes
- Added feature X
- Fixed bug Y
- Updated documentation

## Testing
<!-- How to test these changes -->

## Screenshots
<!-- If applicable -->
```

## Review Criteria

### Code Quality
- [ ] Code follows project style
- [ ] No code duplication
- [ ] Functions are small and focused
- [ ] Proper error handling
- [ ] No security issues

### Testing
- [ ] Tests added for new logic
- [ ] Edge cases covered
- [ ] Tests pass on CI

### Documentation
- [ ] Public APIs documented
- [ ] Complex logic explained
- [ ] README updated if needed

### Performance
- [ ] No N+1 queries
- [ ] Proper indexing
- [ ] Lazy loading where appropriate

## Security Checks

- [ ] No secrets in code
- [ ] Input validation present
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] Proper authentication/authorization

## Review Comments

### Use Constructive Language
- ❌ "This is wrong"
- ✅ "Consider using X because..."

### Be Specific
- ❌ "Fix this"
- ✅ "Line 42: The variable 'x' could be named more descriptively as 'userCount'"

### Explain Why
- ❌ "Use const instead of let"
- ✅ "Using const here makes it clear the variable is not reassigned, improving readability"

## Common Issues to Look For

| Issue | Severity | Example |
|-------|----------|---------|
| Missing tests | High | No test coverage for new feature |
| Security vulnerability | Critical | SQL injection risk |
| Breaking change | High | Changed API without notice |
| Performance issue | Medium | N+1 query |
| Code smell | Low | Magic numbers |

## Workflow Usage

```typescript
workflow({
  name: "pr-review",
  user_context: "Review PR #123 for the auth feature"
})
```