# research-assistant

Multi-source research methodology and guidelines.

## Research Process

### 1. Define the Question
- Clear and specific
- Measurable criteria
- Scope defined
- Time constraints noted

### 2. Identify Sources

#### Primary Sources
- Official documentation
- RFCs and standards
- Academic papers
- Official blogs

#### Secondary Sources
- Technical articles
- Stack Overflow
- GitHub issues
- Community discussions

#### Tertiary Sources
- Summaries
- Tutorials
- Video content
- Course materials

### 3. Evaluate Sources

| Criteria | Weight |
|----------|--------|
| Authority | High |
| Accuracy | High |
| Currency | Medium |
| Coverage | Low |
| Objectivity | Medium |

### 4. Synthesize Information

## Information Quality Checklist

### Authority
- [ ] Author is expert
- [ ] Organization credible
- [ ] Peer reviewed
- [ ] Cited by others

### Accuracy
- [ ] References provided
- [ ] Data verifiable
- [ ] No obvious errors
- [ ] Balanced view

### Currency
- [ ] Recent publication
- [ ] Updated regularly
- [ ] Not outdated
- [ ] Relevant today

### Relevance
- [ ] Matches query
- [ ] Right depth
- [ ] Practical focus
- [ ] Contains examples

## Note-Taking Format

### Source Card
```markdown
## Source: [Title]
- URL: [Link]
- Author: [Name]
- Date: [Date]
- Type: [Article/Paper/Doc]

## Key Points
- Point 1
- Point 2
- Point 3

## Relevance
- How it answers the question
- Quality assessment
```

### Quote Card
```markdown
## Quote
"Exact quote from source"

## Context
Where found in source

## Source
Source title, page number

## Interpretation
What this means
```

## Research Output Format

### Summary
```markdown
## Research Question
[Original question]

## Executive Summary
[Brief 2-3 sentence answer]

## Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

## Sources
- [Source 1](link)
- [Source 2](link)

## Recommendations
- [Recommendation 1]
```

### Detailed Report
```markdown
## Introduction
[Background and context]

## Analysis
[Detailed findings with citations]

## Discussion
[Interpretation and implications]

## Conclusion
[Summary and next steps]

## References
[All sources cited]
```

## MCP Tools

This workflow uses MCP for enhanced research:

### Available Tools
- `brave_search` - Web search
- `github_search_code` - Code search
- `fetch` - Content fetching
- `web_search` - General search

### Usage
```typescript
workflow({
  name: "research-assistant",
  user_context: "Research best practices for implementing rate limiting in Node.js"
})
```

## Best Practices

1. **Start broad, then narrow**
2. **Use multiple sources**
3. **Verify claims**
4. **Check dates**
5. **Note limitations**
6. **Cite properly**
7. **Stay organized**
8. **Question assumptions**

## Common Pitfalls

- Relying on single source
- Ignoring counterarguments
- Using outdated info
- Conflicting information
- Missing context
- Unverified claims