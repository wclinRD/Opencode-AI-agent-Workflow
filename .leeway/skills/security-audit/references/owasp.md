# OWASP Top 10 - 2021

The Open Web Application Security Project (OWASP) Top 10 is a standard awareness document for developers and web application security. It represents a broad consensus about the most critical security risks to web applications.

## A01:2021 - Broken Access Control

Access control enforces policy such that users cannot act outside of their intended permissions. Failures typically lead to unauthorized information disclosure, modification, or destruction of all data or performing a business function outside the user's limits.

**Common vulnerabilities:**
- Violation of the principle of least privilege
- Bypassing access control checks by modifying the URL
- Permitting viewing or editing someone else's account
- Accessing API with missing access controls for POST, PUT and DELETE

## A02:2021 - Cryptographic Failures

Previously known as Sensitive Data Exposure, this category focuses on failures related to cryptography which often leads to sensitive data exposure.

**Common vulnerabilities:**
- Transmitting data in clear text
- Using old or weak cryptographic algorithms
- Default crypto keys not being managed properly
- Not enforcing encryption (missing HTTPStrictTransportSecurity header)

## A03:2021 - Injection

An application is vulnerable to attack when:
- User-supplied data is not validated, filtered, or sanitized
- Dynamic queries or non-parameterized calls are used
- Hostile data is used within ORM search parameters

**Types:**
- SQL injection
- NoSQL injection
- OS command injection
- LDAP injection
- Expression language injection

## A04:2021 - Insecure Design

Insecure design is a broad category representing different weaknesses, expressed as "missing or ineffective control design."

**Key concepts:**
- Threat modeling
- Secure design patterns
- Reference architectures

## A05:2021 - Security Misconfiguration

The application might be vulnerable if it is:
- Missing appropriate security hardening across any part of the application stack
- Using default credentials
- Having unnecessary features enabled or installed
- Error handling reveals stack traces

## A06:2021 - Vulnerable and Outdated Components

You are probably vulnerable if:
- You do not know all versions of your components
- Software is unsupported
- You do not scan for vulnerabilities regularly
- You do not fix or upgrade the underlying platform, frameworks, and dependencies

## A07:2021 - Identification and Authentication Failures

Confirmation of the user's identity, authentication, and session management is critical to protect against authentication-related attacks.

**Common issues:**
- Weak passwords
- Credential stuffing
- Session fixation
- Improper session handling

## A08:2021 - Software and Data Integrity Failures

Software and data integrity failures relate to code and infrastructure that does not protect against integrity violations.

**Examples:**
- Auto-update without integrity verification
- Insecure deserialization
- CI/CD pipeline without validation
- Insecure response caching

## A09:2021 - Security Logging and Monitoring Failures

Insufficient logging, detection, monitoring, and active response occurs any time:

- Auditable events, such as logins, failed logins, and high-value transactions, are not logged
- Warning and error messages generate no, inadequate, or unclear log messages
- Logs are not monitored for suspicious activity

## A10:2021 - Server-Side Request Forgery (SSRF)

SSRF occurs when a web application fetches a remote resource without validating the user-supplied URL.

**Risk factors:**
- Cloud metadata storage exposure
- Internal port scanning
- PII exfiltration

## References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP API Security Top 10: https://owasp.org/www-project-api-security/
- ASVS (Application Security Verification Standard)