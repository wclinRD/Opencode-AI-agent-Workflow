# github-search

GitHub code search guidelines and techniques.

## Search Syntax

### Basic Search
- `keyword` - Find keyword anywhere
- `repo:owner/name` - Search in specific repo
- `user:username` - Search user's repos
- `org:orgname` - Search organization repos

### File Search
- `filename:config` - Find files named config
- `extension:js` - JavaScript files
- `path:src/main` - Files in path
- `language:python` - Python files

### Code Search
- `const.*=.*function` - Const arrow functions
- `class User` - Class definitions
- `TODO` - TODO comments
- `"string literal"` - Exact string match

### Boolean Operators
- `keyword1 AND keyword2` - Both keywords
- `keyword1 OR keyword2` - Either keyword
- `NOT keyword` - Exclude keyword

### qualifiers
- `stars:>100` - More than 100 stars
- `forks:>50` - More than 50 forks
- `pushed:>2024-01-01` - Recently pushed
- `created:>2023-01-01` - Recently created

## Search Examples

### Find Code Examples
```
repo:facebook/react useEffect
repo:nodejs/node http.createServer
language:typescript createReducer
```

### Find Configuration
```
filename:.gitignore
extension:yaml path:docker
repo:docker/compose docker-compose.yml
```

### Find Patterns
```
function.*async language:javascript
class.*extends.*React.Component
TODO fixme language:typescript
```

### Find Vulnerabilities
```
password= api_key= language:javascript
Process\.env NOT .env
exec( language:javascript
```

## Best Practices

### Search Strategy
1. Start with broad search
2. Narrow down with qualifiers
3. Use multiple searches
4. Check recent commits
5. Look at official examples

### Evaluation
- Check repo stars/forks
- Verify maintainer activity
- Look for tests
- Check license
- Review issues

### Citation
- Link to exact line
- Note the context
- Verify it's current
- Check for alternatives

## MCP Integration

This workflow uses GitHub MCP for enhanced search:

### Available Tools
- `github_search_repositories` - Search repos
- `github_search_code` - Search code
- `github_get_file` - Get file contents
- `github_list_prs` - List pull requests
- `github_get_issue` - Get issue details

### Usage
```typescript
workflow({
  name: "github-search",
  user_context: "Find examples of React hooks for data fetching"
})
```

## Common Use Cases

| Use Case | Search Query |
|----------|-------------|
| Find auth patterns | `authenticate token language:javascript` |
| Find React patterns | `useState useEffect react` |
| Find config examples | `filename:docker-compose extension:yml` |
| Find tests | `describe it language:javascript` |
| Find APIs | `GET POST endpoint express` |

## Tips

- Use quotes for exact matches
- Use `lang:en` for English
- Star repos you use often
- Save searches as Gists
- Use GitHub CLI for complex searches