# API Client TLS (PKI) Guide

This document explains how to use the formula PKI flow for Incus API client authentication.

## What This Feature Does

The PKI flow has 3 phases:

1. Generate a client certificate/key pair via `salt-call`.
2. Import the certificate into the local Incus trust store (optional, controlled by pillar).
3. Reuse the same certificate/key in `incus.connection` for HTTPS API calls (including salt-cloud use cases).

Supported storage backends:

- `local_files`
- `sdb`

## Pillar Keys

The feature is configured under `incus:api_client`:

```yaml
incus:
  api_client:
    enabled: true
    storage:
      type: local_files   # local_files | sdb
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
    generate:
      cn: salt-cloud
      days: 3650
    trust_import: true
    trust_name: salt-cloud
    trust_restricted: false
```

Canonical import flag: `incus:api_client:trust_import`.

## Scenario 1: Local Files

### 1. Configure pillar

```yaml
incus:
  enable: true

  api_client:
    enabled: true
    storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
    generate:
      cn: salt-cloud
      days: 3650
    trust_import: true
    trust_name: salt-cloud
    trust_restricted: false

  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: true
```

### 2. Generate keypair manually (required pre-step)

Run on the target minion:

```bash
salt-call --local saltutil.sync_all
salt-call --local incus_pki.generate_keypair
```

Optional rotation:

```bash
salt-call --local incus_pki.generate_keypair force=True
```

### 3. Apply formula

```bash
salt-call --local state.apply incus
```

If you only need trust import state:

```bash
salt-call --local state.apply incus.tls
```

### 4. Verify

```bash
salt-call --local incus.trust_list
salt-call --local incus_pki.trust_present_check
```

## Scenario 2: SDB Storage

Use SDB URIs for both `api_client.storage` and HTTPS `connection.cert_storage`.

```yaml
incus:
  enable: true

  api_client:
    enabled: true
    storage:
      type: sdb
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
    generate:
      cn: salt-cloud
      days: 3650
    trust_import: true
    trust_name: salt-cloud
    trust_restricted: false

  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      type: sdb
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
      verify: sdb://vault/incus/ca_cert
```

Then run the same flow:

```bash
salt-call --local saltutil.sync_all
salt-call --local incus_pki.generate_keypair
salt-call --local state.apply incus
```

## State Behavior and Idempotency

- `incus_pki.keypair_present`: no-op if cert+key already exist.
- `incus_pki.trust_present`: no-op if trust entry matches desired state.
- If fingerprint exists but `name` or `restricted` drift, state performs recreate (`remove` + `add`).
- All PKI states support `test=True`.

Dry-run examples:

```bash
salt-call --local state.apply incus.tls test=True
salt-call --local state.apply incus test=True
```

## Useful Execution Commands

```bash
# Read material from storage
salt-call --local incus_pki.cert_get
salt-call --local incus_pki.key_get
salt-call --local incus_pki.cert_fingerprint

# Trust operations from storage
salt-call --local incus_pki.trust_add_from_storage name=salt-cloud restricted=False
salt-call --local incus_pki.trust_remove_from_storage

# Direct trust API helpers
salt-call --local incus.trust_list
salt-call --local incus.trust_get <fingerprint>
salt-call --local incus.trust_remove <fingerprint>
```

## Common Errors

### "Certificate not found in storage"

Cause:

- `trust_import: true`, but generation step was skipped.
- Wrong `storage.cert` / `storage.key` path or SDB URI.

Fix:

1. Run `salt-call --local incus_pki.generate_keypair`.
2. Check `incus_pki.cert_get` and `incus_pki.key_get`.

### Trust state does not run

Cause:

- `incus.enable` is `false`.
- `incus.api_client.enabled` is `false`.
- `incus.api_client.trust_import` is `false`.

Fix:

- Enable the required flags and apply `incus` or `incus.tls` again.

### SDB read/write failures

Cause:

- Missing/invalid SDB backend config in Salt.
- URI does not exist or has insufficient permissions.

Fix:

1. Verify SDB backend configuration.
2. Test the same URI with a simple read/write operation.
