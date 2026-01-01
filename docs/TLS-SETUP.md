# TLS/mTLS Setup Guide

This guide explains how to enable secure communication between Arduino Trader microservices using TLS (Transport Layer Security) or mTLS (Mutual TLS).

## When to Use TLS

**Use TLS when:**
- Running services across two Arduino devices (dual-device deployment)
- Services communicate over network (not in-process)
- Security is a concern (recommended for production dual-device setups)

**Skip TLS when:**
- Running in local mode (all services in-process)
- Services are on the same device communicating via localhost
- Testing in development environment on trusted network

## TLS vs mTLS

### TLS (Server Authentication)
- **What**: Server proves its identity to clients
- **Use case**: Basic encryption and server verification
- **Security**: Prevents eavesdropping, validates server identity
- **Complexity**: Lower (only server certificates needed)

### mTLS (Mutual Authentication)
- **What**: Both server and clients prove their identities
- **Use case**: High security environments, strict access control
- **Security**: Full mutual authentication, prevents unauthorized clients
- **Complexity**: Higher (requires per-device client certificates)

**Recommendation**: Start with TLS, upgrade to mTLS if you need client authentication.

## Setup Instructions

### Step 1: Generate Certificates

The project includes a script to generate self-signed certificates for private network use.

#### For TLS (Server-only authentication):
```bash
cd /path/to/arduino-trader
./scripts/generate_certs.sh
```

#### For mTLS (Mutual authentication):
```bash
./scripts/generate_certs.sh --mtls
```

This creates certificates in the `certs/` directory:
```
certs/
├── ca-cert.pem                # Certificate Authority (distribute to all devices)
├── ca-key.pem                 # CA private key (KEEP SECURE)
├── server-cert.pem            # Server certificate
├── server-key.pem             # Server private key (KEEP SECURE)
├── device1-client-cert.pem    # Device 1 client certificate (mTLS only)
├── device1-client-key.pem     # Device 1 client key (mTLS only)
├── device2-client-cert.pem    # Device 2 client certificate (mTLS only)
└── device2-client-key.pem     # Device 2 client key (mTLS only)
```

**⚠️ Security Note**: The `certs/` directory has a `.gitignore` that prevents committing certificates to version control. Never commit private keys (*.pem files) to git.

### Step 2: Distribute Certificates to Devices

For a dual-device setup:

#### Device 1 (Server):
Copy these files to Device 1's `certs/` directory:
```bash
# Required for all modes:
certs/ca-cert.pem
certs/server-cert.pem
certs/server-key.pem

# Additional for mTLS (if device also acts as client):
certs/device1-client-cert.pem
certs/device1-client-key.pem
```

#### Device 2 (Client):
Copy these files to Device 2's `certs/` directory:
```bash
# Required for TLS:
certs/ca-cert.pem

# Additional for mTLS:
certs/device2-client-cert.pem
certs/device2-client-key.pem
```

**Transfer methods:**
```bash
# Using SCP (secure copy):
scp certs/ca-cert.pem user@device2:/path/to/arduino-trader/certs/
scp certs/device2-client-cert.pem user@device2:/path/to/arduino-trader/certs/
scp certs/device2-client-key.pem user@device2:/path/to/arduino-trader/certs/

# Or use USB drive for offline transfer
```

### Step 3: Configure TLS in services.yaml

Edit `app/config/services.yaml`:

#### For TLS (Server authentication):
```yaml
tls:
  enabled: true
  mutual: false
  ca_cert: "certs/ca-cert.pem"
  server_cert: "certs/server-cert.pem"
  server_key: "certs/server-key.pem"
  server_hostname_override: "arduino-trader-server"
```

#### For mTLS (Mutual authentication):
```yaml
tls:
  enabled: true
  mutual: true
  ca_cert: "certs/ca-cert.pem"
  server_cert: "certs/server-cert.pem"
  server_key: "certs/server-key.pem"
  client_cert: "certs/device1-client-cert.pem"  # Device-specific
  client_key: "certs/device1-client-key.pem"    # Device-specific
  server_hostname_override: "arduino-trader-server"
```

**Note**: On Device 2, use `device2-client-cert.pem` and `device2-client-key.pem`.

### Step 4: Verify Configuration

Before starting services, verify certificates are readable:

```bash
# Check CA certificate
openssl x509 -in certs/ca-cert.pem -text -noout

# Check server certificate
openssl x509 -in certs/server-cert.pem -text -noout

# Verify server certificate against CA
openssl verify -CAfile certs/ca-cert.pem certs/server-cert.pem

# Verify client certificate against CA (mTLS)
openssl verify -CAfile certs/ca-cert.pem certs/device1-client-cert.pem
```

Expected output: `OK` for verification commands.

### Step 5: Start Services

Start services as normal. They will automatically use TLS if configured:

```bash
# On Device 1 (server):
python -m services.planning.main
# Output: "Starting Planning service on 0.0.0.0:50051 (with TLS)"

# On Device 2 (client):
python -m app.main
# Clients will automatically use TLS when connecting
```

## Configuration Reference

### TLS Configuration Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `enabled` | boolean | Yes | Enable/disable TLS encryption |
| `mutual` | boolean | No | Enable mutual TLS (client authentication) |
| `ca_cert` | string | Yes | Path to CA certificate (validates server/client certs) |
| `server_cert` | string | Yes | Path to server certificate |
| `server_key` | string | Yes | Path to server private key |
| `client_cert` | string | mTLS only | Path to client certificate |
| `client_key` | string | mTLS only | Path to client private key |
| `server_hostname_override` | string | No | Override server hostname for cert validation |

### Certificate Paths

Paths can be:
- **Relative**: Resolved from project root (e.g., `certs/ca-cert.pem`)
- **Absolute**: Used as-is (e.g., `/etc/arduino-trader/certs/ca-cert.pem`)

### File Permissions

The certificate generation script sets proper permissions:
```bash
# Private keys (owner read/write only)
-rw------- 1 user user  *-key.pem

# Certificates (readable by all)
-rw-r--r-- 1 user user  *-cert.pem
```

**Important**: Never change private key permissions to be world-readable.

## Troubleshooting

### Error: "Certificate verify failed"

**Cause**: CA certificate mismatch or expired certificate.

**Solution**:
1. Verify CA certificate is present on both devices
2. Check certificate validity: `openssl x509 -in certs/server-cert.pem -dates -noout`
3. Regenerate certificates if expired

### Error: "SSL handshake failed"

**Cause**: Client doesn't trust server certificate or certificate hostname mismatch.

**Solutions**:
1. Verify `ca-cert.pem` is the same on both devices
2. Check `server_hostname_override` matches server certificate CN
3. Verify certificates with: `openssl verify -CAfile certs/ca-cert.pem certs/server-cert.pem`

### Error: "Connection refused" after enabling TLS

**Cause**: Server may not have started with TLS, or client trying to use insecure connection.

**Solutions**:
1. Check server logs for "Starting ... (with TLS)" message
2. Verify `tls.enabled: true` in services.yaml on both devices
3. Ensure firewall allows TLS port (default: 50051-50057)

### Error: "Client certificate required" (mTLS)

**Cause**: Server configured for mTLS but client not providing certificate.

**Solutions**:
1. Verify `tls.mutual: true` in server's services.yaml
2. Ensure client has `client_cert` and `client_key` configured
3. Check client certificate files exist and are readable

### Service fails to start with "FileNotFoundError"

**Cause**: Certificate files not found at configured paths.

**Solutions**:
1. Verify certificate files exist: `ls -la certs/`
2. Check paths in services.yaml (relative to project root)
3. Use absolute paths if having issues with relative paths

## Security Best Practices

### Certificate Management

1. **Validity Period**: Generated certificates are valid for 10 years
   - Monitor expiration dates
   - Plan certificate renewal before expiry

2. **Private Key Security**:
   - Never commit `*-key.pem` files to version control
   - Use file permissions 600 (owner read/write only)
   - Store backups in encrypted storage

3. **CA Certificate**:
   - The CA certificate (`ca-cert.pem`) is safe to distribute
   - CA private key (`ca-key.pem`) should never leave trusted environment
   - Use CA key only for generating new certificates

### Production Considerations

For production deployments:

1. **Certificate Rotation**:
   - Rotate certificates annually or when compromised
   - Use certificate expiration monitoring

2. **Separate CA for Production**:
   - Use a dedicated CA for production (not the same as dev/test)
   - Consider hardware security module (HSM) for CA key storage

3. **Network Security**:
   - TLS encrypts data in transit but doesn't protect the network layer
   - Use firewall rules to restrict service access
   - Consider VPN for additional network isolation

4. **Upgrade Path**:
   - Start with TLS in production
   - Move to mTLS when you need strict client authentication
   - Plan certificate distribution before enabling mTLS

## Migration from Insecure to Secure

### Zero-Downtime Migration Strategy

If you have running services without TLS and want to enable it:

1. **Prepare certificates**: Generate on one device, distribute to all
2. **Update configuration**: Set `tls.enabled: true` in services.yaml
3. **Restart services one by one**:
   - Services will detect TLS config on restart
   - No code changes needed

### Testing TLS Before Production

Test TLS locally before deploying:

```bash
# 1. Generate test certificates
./scripts/generate_certs.sh

# 2. Enable TLS in services.yaml (set enabled: true)

# 3. Start a test service
python -m services.planning.main

# 4. Verify TLS in logs:
# "Starting Planning service on 0.0.0.0:50051 (with TLS)"

# 5. Test client connection
python -m pytest tests/integration/test_planning_service.py -v
```

## Additional Resources

- **gRPC Authentication Guide**: https://grpc.io/docs/guides/auth/
- **OpenSSL Certificate Management**: https://www.openssl.org/docs/
- **Python gRPC Security**: https://grpc.github.io/grpc/python/grpc.html#grpc.ssl_channel_credentials

## Summary

**For dual-device deployment**:
1. Generate certificates: `./scripts/generate_certs.sh --mtls`
2. Copy certificates to each device
3. Edit `app/config/services.yaml` (set `tls.enabled: true`)
4. Restart services
5. Verify "with TLS" in startup logs

**For local deployment**:
- No TLS needed (keep `tls.enabled: false`)
- Services run in-process without network communication
