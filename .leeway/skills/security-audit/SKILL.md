# security-audit

Security audit guidelines and checklist for code review.

## OWASP Top 10 Considerations

1. **A01:2021 - Broken Access Control**
   - Check for proper authorization checks
   - Verify IDOR vulnerabilities
   - Check for privilege escalation risks

2. **A02:2021 - Cryptographic Failures**
   - Check for hardcoded secrets
   - Verify proper encryption usage
   - Check for weak cryptographic algorithms

3. **A03:2021 - Injection**
   - SQL injection risks
   - Command injection
   - XSS vulnerabilities
   - LDAP injection

4. **A04:2021 - Insecure Design**
   - Business logic flaws
   - Race conditions
   - Authentication weaknesses

5. **A05:2021 - Security Misconfiguration**
   - Default credentials
   - Debug mode enabled
   - Information disclosure

6. **A06:2021 - Vulnerable Components**
   - Outdated dependencies
   - Known CVEs
   - Unmaintained libraries

7. **A07:2021 - Authentication Failures**
   - Weak password policies
   - Session management issues
   - Missing MFA

8. **A08:2021 - Software and Data Integrity Failures**
   - Unsafe deserialization
   - CI/CD vulnerabilities
   - Update integrity

9. **A09:2021 - Security Logging Failures**
   - Insufficient logging
   - Missing audit trails
   - Error information leakage

10. **A10:2021 - Server-Side Request Forgery**
    - URL validation
    - External API calls
    - DNS rebinding

## Common Security Patterns to Check

### Input Validation
- All user input validated
- Whitelist over blacklist
- Proper encoding

### Authentication
- Strong password requirements
- Secure session handling
- Proper token storage

### Data Protection
- Encryption at rest
- Secure key management
- Proper data classification

### Error Handling
- No stack traces in production
- Generic error messages
- Proper logging