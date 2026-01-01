# REST API Security Plan

## Overview

This document outlines the security strategy for the REST microservices architecture. The current implementation (initial migration from gRPC) runs services on localhost without authentication, suitable for the single-user, single-device Arduino Uno Q deployment.

## Current State (Phase 1: Local Deployment)

### Network Security
- **Binding**: All services bind to `0.0.0.0` but only accept connections from localhost
- **Ports**: Services run on ports 8001-8007
- **TLS**: Currently disabled (`tls.enabled: false` in services.yaml)
- **Network Isolation**: Services communicate only on local loopback interface

### Authentication
- **None implemented**: Services trust all requests from localhost
- **Assumption**: Physical access control is the primary security boundary
- **Risk**: Minimal for single-user device with no external network exposure

### Rationale for Current Approach
1. **Single User**: System manages one user's retirement portfolio
2. **Single Device**: Arduino Uno Q has no multi-tenancy requirements
3. **No Remote Access**: Device operates autonomously without external API exposure
4. **Simplicity**: Reduces attack surface and operational complexity

## Future Considerations (Phase 2: Multi-Device/Network Deployment)

If the system evolves to support:
- Multiple Arduino devices communicating over network
- Remote management interface
- External API access

The following security measures should be implemented:

### 1. TLS/HTTPS Encryption

**Enable TLS in services.yaml:**
```yaml
tls:
  enabled: true
  mutual: false  # or true for mutual TLS
  cert_file: /path/to/server.crt
  key_file: /path/to/server.key
  ca_file: /path/to/ca.crt  # for mutual TLS
```

**Implementation:**
- Generate self-signed certificates for inter-service communication
- Use Let's Encrypt for any external-facing endpoints
- Store private keys securely (encrypted filesystem, hardware security module)

### 2. Service Authentication

**Options (in order of complexity):**

#### Option A: Shared Secret (Simplest)
- Environment variable `SERVICE_API_KEY` on each device
- Services include `X-API-Key` header in requests
- Validation middleware checks key matches

**Pros:** Simple to implement, low overhead
**Cons:** Key rotation requires device access, shared secret model

#### Option B: JWT Tokens
- Each service has a unique identity (service account)
- Services authenticate with central auth service to obtain JWT
- JWT includes service name, expiration, permissions
- Services validate JWT signature on each request

**Pros:** Standard protocol, supports expiration and revocation
**Cons:** Requires auth service, more complex

#### Option C: Mutual TLS (mTLS)
- Each service has its own certificate signed by CA
- Services validate client certificates during TLS handshake
- Certificate CN/SAN identifies the service

**Pros:** Strong cryptographic identity, no additional auth layer needed
**Cons:** Complex certificate management, rotation challenges

**Recommendation:** Start with Option A for multi-device, upgrade to mTLS for production

### 3. Authorization

**Service-Level Permissions:**
- Define which services can call which endpoints
- Example: Gateway service can call all services; Planning service can only call Scoring
- Implement authorization middleware that checks service identity

**Endpoint-Level Controls:**
- Read-only vs. write operations
- Critical operations (trade execution) require elevated permissions

### 4. Network Security

**Firewall Rules:**
- Block all external access to service ports (8001-8007)
- Only allow connections from known device IPs
- Use iptables/nftables or hardware firewall

**VPN/Wireguard:**
- For multi-device deployments, establish encrypted tunnel
- Devices authenticate to VPN before accessing services
- Additional layer of network-level security

### 5. Rate Limiting

**Per-Service Limits:**
- Prevent abuse or runaway processes
- Example: Max 100 requests/minute per service
- Implement using circuit breaker pattern (already in place)

### 6. Audit Logging

**Security Events:**
- Log all authentication attempts (success/failure)
- Log authorization failures
- Log critical operations (trade execution, configuration changes)
- Store logs securely with tamper protection

### 7. Secrets Management

**Current:**
- API keys in `.env` file (filesystem permissions: 600)

**Future:**
- Use secrets manager (HashiCorp Vault, systemd-creds, encrypted keyring)
- Rotate secrets periodically
- Never log or expose secrets in error messages

## Implementation Phases

### Phase 1: Current (Single Device, Localhost)
✅ **Status:** Complete
- No authentication
- No TLS
- Services trust localhost

### Phase 2: Multi-Device (Local Network)
**When:** Adding second Arduino or remote management
**Priority:** Medium
**Tasks:**
1. Implement shared secret authentication
2. Enable TLS between devices
3. Add firewall rules
4. Implement audit logging

### Phase 3: External Access (Internet-Facing)
**When:** Building web dashboard or mobile app
**Priority:** Low (not currently planned)
**Tasks:**
1. Implement JWT-based authentication
2. Add user authentication layer
3. Implement rate limiting
4. Security audit and penetration testing
5. Consider API gateway (Kong, Traefik)

## Security Checklist

For Phase 2 deployment, verify:

- [ ] TLS certificates generated and installed
- [ ] Service API keys created and distributed
- [ ] Firewall rules configured
- [ ] Services.yaml updated with TLS config
- [ ] Authentication middleware implemented
- [ ] Authorization checks added to critical endpoints
- [ ] Audit logging enabled
- [ ] Security event monitoring configured
- [ ] Incident response plan documented
- [ ] Secrets stored securely (not in git)

## Threat Model

### Threats Mitigated (Current)
- Physical access attacks: Prevented by physical security of device
- Local privilege escalation: Limited by OS user permissions

### Threats NOT Mitigated (Current)
- Malicious local processes: Any process on Arduino can call services
- Network attacks: N/A (no network exposure)
- Replay attacks: N/A (no auth tokens)

### Additional Threats (Multi-Device)
- Man-in-the-middle: Mitigated by TLS
- Unauthorized service access: Mitigated by authentication
- Service impersonation: Mitigated by mTLS or JWT
- Denial of service: Mitigated by rate limiting
- Data exfiltration: Mitigated by network isolation + TLS

## References

- REST API Migration: `REST_API_MIGRATION.md`
- Services Configuration: `app/config/services.yaml`
- Deployment Guide: `INSTALL.md`
- Security Best Practices: OWASP API Security Top 10

---

Last Updated: 2026-01-01
Status: Phase 1 (Localhost deployment)
Next Review: When multi-device deployment is planned
