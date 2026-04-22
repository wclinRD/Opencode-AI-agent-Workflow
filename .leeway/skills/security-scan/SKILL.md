# security-scan

Security vulnerability scanning guidelines.

## Scanning Strategy

### 1. Input Validation
- Check all user inputs
- Use whitelist validation
- Validate on server side (not just client)
- Sanitize outputs

### 2. Authentication
- Password requirements
- Session management
- Token storage
- MFA support

### 3. Authorization
- Role-based access control
- Principle of least privilege
- IDOR protection
- Parameter tampering

### 4. Data Protection
- Encryption at rest
- Secure key management
- Data classification
- PII handling

## Common Vulnerabilities

### Injection
- SQL injection
- Command injection
- XSS (Cross-site scripting)
- LDAP injection
- Template injection

### Authentication
- Weak passwords
- Session fixation
- Credential stuffing
- Missing MFA

### Data Exposure
- Cleartext transmission
- Insecure storage
- Information disclosure
- Stack traces

## OWASP Top 10 (2021)

| ID | Category | Risk Level |
|----|----------|------------|
| A01 | Broken Access Control | Critical |
| A02 | Cryptographic Failures | Critical |
| A03 | Injection | Critical |
| A04 | Insecure Design | High |
| A05 | Security Misconfiguration | High |
| A06 | Vulnerable Components | High |
| A07 | Auth Failures | High |
| A08 | Software Integrity Failures | Medium |
| A09 | Logging Failures | Medium |
| A10 | SSRF | Medium |

## Scan Checklist

### Before Scanning
- [ ] Understand the codebase
- [ ] Identify entry points
- [ ] Map data flows
- [ ] List dependencies

### During Scanning
- [ ] Test input validation
- [ ] Check authentication
- [ ] Verify authorization
- [ ] Review error handling
- [ ] Check for secrets

### After Scanning
- [ ] Prioritize findings
- [ ] Create remediation plan
- [ ] Document false positives
- [ ] Generate report

## Remediation Priority

### Critical (Fix Immediately)
- SQL injection
- Remote code execution
- Authentication bypass

### High (Fix Soon)
- XSS vulnerabilities
- CSRF
- Information disclosure

### Medium (Plan to Fix)
- Weak cryptography
- Missing security headers
- Insufficient logging

### Low (Consider Fixing)
- Information in comments
- Missing error pages
- Verbose error messages

## Report Format

```yaml
findings:
  - id: CVE-XXXX-XXXX
    severity: critical
    title: SQL Injection
    location: src/db/query.ts:42
    description: User input not sanitized
    remediation: Use parameterized queries
    references:
      - https://owasp.org/...
```

## Usage Example

```typescript
workflow({
  name: "security-scan",
  user_context: "Scan for vulnerabilities in the authentication module"
})
```