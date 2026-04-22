# Code Review Checklist

## Pre-PR Review

- [ ] Tests pass
- [ ] Lint passes
- [ ] Types check
- [ ] Documentation updated

## Code Quality

- [ ] No dead code
- [ ] No TODO comments without issue
- [ ] Proper error handling
- [ ] No hardcoded values

## Security

- [ ] No secrets committed
- [ ] Input validation present
- [ ] SQL injection prevented
- [ ] XSS prevented

## Performance

- [ ] No N+1 queries
- [ ] Proper indexing considered
- [ ] Lazy loading used where appropriate

## Testing

- [ ] Unit tests for new logic
- [ ] Edge cases covered
- [ ] Integration tests for flows