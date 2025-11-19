# Incus Server Settings Management

Complete documentation for managing Incus server global configuration settings using Salt.

## Table of Contents

- [Overview](#overview)
- [Configuration Approaches](#configuration-approaches)
  - [server_settings - Bulk Configuration](#server_settings---bulk-configuration)
  - [server_settings_individual - Individual Management](#server_settings_individual---individual-management)
  - [Comparison Table](#comparison-table)
  - [Can You Use Both?](#can-you-use-both)
- [Execution Module Functions](#execution-module-functions)
- [State Functions](#state-functions)
- [Configuration Examples](#configuration-examples)
- [Common Use Cases](#common-use-cases)
- [Available Settings](#available-settings)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Quick Reference](#quick-reference)

## Overview

The Incus settings module provides comprehensive management of server-wide configuration. These settings control various aspects of the Incus daemon including:

- **Core Settings**: API access, HTTPS configuration, trust password
- **Image Management**: Auto-updates, compression, caching
- **Cluster Configuration**: Cluster networking, healing, replicas
- **Storage**: Default volumes, ZFS configuration
- **Integration**: MAAS, Candid, OCI registry
- **Operations**: Backups, metrics, logging

## Configuration Approaches

There are two main ways to configure Incus server settings via Salt pillars: **bulk updates** (`server_settings`) and **individual management** (`server_settings_individual`).

### `server_settings` - Bulk Configuration

The `server_settings` approach updates multiple settings in a **single state** call.

**Pillar Example:**
```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      images.auto_update_cached: "true"
      images.auto_update_interval: "12"
      images.compression_algorithm: "zstd"
```

**Characteristics:**
- ✅ All settings updated in **one state** call
- ✅ Simpler and more compact for managing related settings
- ✅ Creates **one** state ID: `incus-server-settings`
- ✅ All changes shown **together** in one result
- ❌ If one setting is invalid, all may fail to apply
- ❌ Less flexibility for managing individual settings

**Generated State:**
```yaml
incus-server-settings:
  incus.settings_present:
    - name: incus_server_configuration
    - config:
        core.https_address: "[::]:8443"
        images.auto_update_cached: "true"
        # ... all settings together
```

**Use Cases:**
- Initial server setup
- Managing a group of related settings (e.g., all `images.*` settings)
- When simplicity and compactness are priorities
- When settings should be applied atomically (all or nothing)

---

### `server_settings_individual` - Individual Management

The `server_settings_individual` approach creates a **separate state** for each setting.

**Pillar Example:**
```yaml
incus:
  server_settings_individual:
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"

    auto_update:
      ensure: present
      key: images.auto_update_interval
      value: "12"

    remove_old:
      ensure: absent
      key: some.old.setting
```

**Characteristics:**
- ✅ Each setting is a **separate state** with its own ID
- ✅ Can control state (`ensure: present/absent`) per setting
- ✅ Can add dependencies (`require`, `watch`) for individual settings
- ✅ If one setting fails, others still apply
- ✅ More detailed control and reporting per setting
- ❌ More verbose for large number of settings

**Generated States:**
```yaml
incus-setting-https_api:
  incus.settings_config:
    - name: https_api
    - key: core.https_address
    - value: "[::]:8443"

incus-setting-auto_update:
  incus.settings_config:
    - name: auto_update
    - key: images.auto_update_interval
    - value: "12"

incus-setting-remove_old-absent:
  incus.settings_absent:
    - name: remove_old
    - key: some.old.setting
```

**Use Cases:**
- Adding/removing one specific setting
- Settings managed by different teams/roles
- Need for dependencies between settings
- Flexibility in state management (`ensure: present/absent`)
- Conditional settings (e.g., only on certain servers)

---

### Comparison Table

| Aspect                     | `server_settings`          | `server_settings_individual`      |
|----------------------------|----------------------------|-----------------------------------|
| **Number of states**       | 1 state for all settings   | 1 state per setting               |
| **Simplicity**             | ✅ Simpler and more compact | ❌ More verbose                    |
| **Flexibility**            | ❌ Limited                  | ✅ Maximum                         |
| **ensure: absent**         | ❌ Not supported            | ✅ Supported                       |
| **Dependencies (require)** | ❌ Only for entire group    | ✅ Per setting                     |
| **Conditional logic**      | ❌ More complex             | ✅ Easier                          |
| **Reporting**              | All changes together       | Each setting separate             |
| **Rollback**               | Harder (all at once)       | Easier (per setting)              |
| **Use case**               | Initial setup, bulk config | Fine-grained control, conditional |

---

### Can You Use Both?

**Yes!** They complement each other:

```yaml
incus:
  # Base configuration for all servers
  server_settings:
    config:
      images.auto_update_cached: "true"
      images.compression_algorithm: "zstd"

  # Server-specific settings
  server_settings_individual:
    {% if grains['id'] == 'incus-prod-01' %}
    cluster_address:
      ensure: present
      key: cluster.https_address
      value: "192.168.1.100:8443"
    {% endif %}

    {% if grains['environment'] == 'production' %}
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"
    {% endif %}
```

---

### Practical Example

Suppose you have:
- **10 production servers** - need HTTPS
- **5 development servers** - don't need HTTPS
- **3 cluster servers** - need cluster-specific settings

```yaml
incus:
  # Common settings for ALL servers
  server_settings:
    config:
      images.auto_update_cached: "true"
      images.auto_update_interval: "12"
      images.compression_algorithm: "zstd"

  # Specific settings
  server_settings_individual:
    # Production only
    {% if grains['environment'] == 'production' %}
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"

    trust_password:
      ensure: present
      key: core.trust_password
      value: {{ pillar['incus_prod_password'] }}
    {% endif %}

    # Cluster servers only
    {% if 'cluster' in grains['roles'] %}
    cluster_address:
      ensure: present
      key: cluster.https_address
      value: {{ grains['ipv4'][0] }}:8443

    cluster_threshold:
      ensure: present
      key: cluster.offline_threshold
      value: "120"
    {% endif %}

    # Remove deprecated setting everywhere
    remove_deprecated:
      ensure: absent
      key: old.deprecated.config
```

**Key Takeaway:** The main difference is in **granularity of control** and **flexibility of management**. Use `server_settings` for simple bulk updates, and `server_settings_individual` when you need fine-grained control over each setting.

---

## Execution Module Functions

### `incus.settings_get()`

Get current Incus server global configuration.

**CLI Usage:**
```bash
salt '*' incus.settings_get
```

**Return Example:**
```python
{
    'success': True,
    'settings': {
        'config': {
            'core.https_address': '[::]:8443',
            'core.trust_password': 'secret',
            'images.auto_update_cached': 'true',
            'images.auto_update_interval': '6'
        }
    }
}
```

---

### `incus.settings_update(config)`

Update server settings (merges with existing configuration).

**Parameters:**
- `config` (dict): Configuration key-value pairs to update

**CLI Usage:**
```bash
salt '*' incus.settings_update config="{'images.auto_update_interval':'12'}"
salt '*' incus.settings_update config="{'core.https_address':'[::]:8443','images.auto_update_cached':'true'}"
```

**Python Usage:**
```python
# Enable HTTPS on all interfaces
__salt__['incus.settings_update']({
    'core.https_address': '[::]:8443'
})

# Configure image auto-update
__salt__['incus.settings_update']({
    'images.auto_update_cached': 'true',
    'images.auto_update_interval': '12'
})
```

---

### `incus.settings_set(key, value)`

Set a single server configuration setting.

**Parameters:**
- `key` (str): Configuration key name
- `value` (str): Configuration value

**CLI Usage:**
```bash
salt '*' incus.settings_set core.https_address '[::]:8443'
salt '*' incus.settings_set images.auto_update_interval 12
salt '*' incus.settings_set images.compression_algorithm zstd
```

**Python Usage:**
```python
# Enable HTTPS
__salt__['incus.settings_set']('core.https_address', '[::]:8443')

# Set auto-update interval
__salt__['incus.settings_set']('images.auto_update_interval', '12')
```

---

### `incus.settings_unset(key)`

Remove a server configuration setting (revert to default).

**Parameters:**
- `key` (str): Configuration key name to remove

**CLI Usage:**
```bash
salt '*' incus.settings_unset core.trust_password
salt '*' incus.settings_unset images.auto_update_interval
```

**Python Usage:**
```python
# Remove trust password (disable password authentication)
__salt__['incus.settings_unset']('core.trust_password')

# Reset auto-update interval to default
__salt__['incus.settings_unset']('images.auto_update_interval')
```

---

### `incus.settings_replace(config)`

Replace entire server configuration (destructive operation).

**WARNING**: This replaces ALL settings. Any settings not specified will be removed.

**Parameters:**
- `config` (dict): Complete configuration (replaces all settings)

**CLI Usage:**
```bash
salt '*' incus.settings_replace config="{'core.https_address':'[::]:8443','images.auto_update_cached':'true'}"
```

**Python Usage:**
```python
# Replace all settings with minimal config
__salt__['incus.settings_replace']({
    'core.https_address': '[::]:8443',
    'images.auto_update_cached': 'true'
})
```

---

## State Functions

### `incus.settings_present`

Ensure the server has specific global configuration settings (merges with existing).

**Parameters:**
- `name` (str): State name (descriptive identifier)
- `config` (dict): Configuration key-value pairs to apply

**State Example:**
```yaml
incus_basic_config:
  incus.settings_present:
    - config:
        images.auto_update_cached: "true"
        images.auto_update_interval: "12"

incus_https_config:
  incus.settings_present:
    - config:
        core.https_address: "[::]:8443"
        core.trust_password: "mysecret"

incus_image_compression:
  incus.settings_present:
    - config:
        images.compression_algorithm: "zstd"
        images.remote_cache_expiry: "10"
```

---

### `incus.settings_config`

Ensure a single server configuration setting has a specific value.

**Parameters:**
- `name` (str): State name
- `key` (str): Configuration key name
- `value` (str): Configuration value

**State Example:**
```yaml
https_address:
  incus.settings_config:
    - key: core.https_address
    - value: "[::]:8443"

auto_update_interval:
  incus.settings_config:
    - key: images.auto_update_interval
    - value: "12"

compression_algorithm:
  incus.settings_config:
    - key: images.compression_algorithm
    - value: "zstd"
```

---

### `incus.settings_absent`

Ensure a specific server configuration setting is not present (revert to default).

**Parameters:**
- `name` (str): State name
- `key` (str): Configuration key name to remove

**State Example:**
```yaml
remove_trust_password:
  incus.settings_absent:
    - key: core.trust_password

reset_auto_update:
  incus.settings_absent:
    - key: images.auto_update_interval

remove_https_address:
  incus.settings_absent:
    - key: core.https_address
```

---

### `incus.settings_managed`

Ensure server configuration exactly matches specified settings (replaces all).

**WARNING**: This is a destructive operation. All settings not specified will be removed.

**Parameters:**
- `name` (str): State name
- `config` (dict): Complete desired configuration

**State Example:**
```yaml
incus_exact_config:
  incus.settings_managed:
    - config:
        core.https_address: "[::]:8443"
        images.auto_update_cached: "true"
        images.auto_update_interval: "12"
        images.compression_algorithm: "zstd"
```

---

## Configuration Examples

### Basic Configuration (Pillar)

```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      core.trust_password: "changeme"
      images.auto_update_cached: "true"
      images.auto_update_interval: "12"
```

### Individual Settings Management

```yaml
incus:
  server_settings_individual:
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"

    auto_update:
      ensure: present
      key: images.auto_update_interval
      value: "6"

    remove_old_setting:
      ensure: absent
      key: some.deprecated.setting
```

### Managed Configuration (Exact Match)

```yaml
incus:
  server_settings:
    managed: true
    managed_config:
      core.https_address: "[::]:8443"
      core.trust_password: "secret"
      images.auto_update_cached: "true"
      images.auto_update_interval: "12"
```

---

## Common Use Cases

### 1. Enable HTTPS API Access

```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      core.trust_password: "secure_password_here"
```

### 2. Configure Automatic Image Updates

```yaml
incus:
  server_settings:
    config:
      images.auto_update_cached: "true"
      images.auto_update_interval: "6"  # Check every 6 hours
      images.compression_algorithm: "zstd"
```

### 3. Set Up Cluster Configuration

```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      cluster.https_address: "192.168.1.100:8443"
      cluster.offline_threshold: "120"
      cluster.images_minimal_replica: "3"
```

### 4. Configure Behind Proxy

```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      core.proxy_http: "http://proxy.internal:3128"
      core.proxy_https: "http://proxy.internal:3128"
      core.proxy_ignore_hosts: "localhost,127.0.0.1,.local"
```

### 5. Production Setup with Backups

```yaml
incus:
  server_settings:
    config:
      core.https_address: "0.0.0.0:8443"
      core.trust_password: "strong_password"
      images.auto_update_cached: "true"
      images.auto_update_interval: "6"
      images.compression_algorithm: "zstd"
      storage.backups_volume: "backups"
      backups.compression_algorithm: "zstd"
```

### 6. Disable Specific Features

```yaml
incus:
  server_settings_individual:
    disable_auto_update:
      ensure: absent
      key: images.auto_update_cached

    disable_trust_password:
      ensure: absent
      key: core.trust_password
```

---

## Available Settings

### Core Settings (core.*)

| Setting                          | Type   | Description                                                  |
|----------------------------------|--------|--------------------------------------------------------------|
| `core.https_address`             | string | HTTPS API listen address (e.g., `[::]:8443`, `0.0.0.0:8443`) |
| `core.trust_password`            | string | Password for adding new clients                              |
| `core.https_allowed_headers`     | string | Allowed HTTP headers for CORS                                |
| `core.https_allowed_methods`     | string | Allowed HTTP methods for CORS                                |
| `core.https_allowed_origin`      | string | CORS allowed origin                                          |
| `core.https_allowed_credentials` | bool   | Allow credentials in CORS                                    |
| `core.https_trusted_proxy`       | string | Trusted proxy addresses                                      |
| `core.proxy_http`                | string | HTTP proxy URL                                               |
| `core.proxy_https`               | string | HTTPS proxy URL                                              |
| `core.proxy_ignore_hosts`        | string | Hosts to bypass proxy                                        |
| `core.remote_token_expiry`       | int    | Remote token expiration (seconds)                            |
| `core.shutdown_timeout`          | int    | Graceful shutdown timeout (minutes)                          |
| `core.bgp_address`               | string | BGP router address                                           |
| `core.bgp_asn`                   | int    | BGP autonomous system number                                 |
| `core.dns_address`               | string | DNS server address                                           |

### Image Settings (images.*)

| Setting                        | Type   | Description                                                          |
|--------------------------------|--------|----------------------------------------------------------------------|
| `images.auto_update_cached`    | bool   | Auto-update cached images                                            |
| `images.auto_update_interval`  | int    | Hours between update checks                                          |
| `images.compression_algorithm` | string | Compression algorithm: `gzip`, `zstd`, `bzip2`, `lzma`, `xz`, `none` |
| `images.remote_cache_expiry`   | int    | Days to cache remote images                                          |
| `images.default_architecture`  | string | Default architecture for images                                      |

### Cluster Settings (cluster.*)

| Setting                          | Type   | Description                              |
|----------------------------------|--------|------------------------------------------|
| `cluster.https_address`          | string | Address for cluster communication        |
| `cluster.offline_threshold`      | int    | Seconds before member considered offline |
| `cluster.images_minimal_replica` | int    | Minimum image replicas in cluster        |
| `cluster.healing_threshold`      | int    | Threshold for healing operations         |
| `cluster.max_voters`             | int    | Maximum voters in cluster                |
| `cluster.max_standby`            | int    | Maximum standby members                  |

### Storage Settings (storage.*)

| Setting                  | Type   | Description             |
|--------------------------|--------|-------------------------|
| `storage.backups_volume` | string | Volume name for backups |
| `storage.images_volume`  | string | Volume name for images  |
| `storage.zfs_pool_name`  | string | ZFS pool name           |

### Backup Settings (backups.*)

| Setting                         | Type   | Description                       |
|---------------------------------|--------|-----------------------------------|
| `backups.compression_algorithm` | string | Compression algorithm for backups |

### MAAS Integration (maas.*)

| Setting               | Type   | Description                 |
|-----------------------|--------|-----------------------------|
| `maas.api.url`        | string | MAAS API URL                |
| `maas.api.key`        | string | MAAS API key                |
| `maas.machine.domain` | string | Default domain for machines |

### Candid Authentication (candid.*)

| Setting          | Type   | Description            |
|------------------|--------|------------------------|
| `candid.api.url` | string | Candid API URL         |
| `candid.api.key` | string | Candid API key         |
| `candid.domains` | string | Allowed domains        |
| `candid.expiry`  | int    | Token expiry (seconds) |

### OCI Registry (oci.*)

| Setting    | Type | Description       |
|------------|------|-------------------|
| `oci.port` | int  | OCI registry port |

### Metrics (metrics.*)

| Setting                  | Type   | Description                        |
|--------------------------|--------|------------------------------------|
| `metrics.authentication` | bool   | Require authentication for metrics |
| `metrics.address`        | string | Metrics endpoint address           |

### Miscellaneous

| Setting         | Type   | Description                  |
|-----------------|--------|------------------------------|
| `syslog.socket` | string | Syslog socket path           |
| `user.*`        | string | User-defined key-value pairs |

---

## Best Practices

1. **Use `settings_present` for Incremental Updates**
   - Safest option for most use cases
   - Only updates specified keys
   - Preserves other settings

2. **Use `settings_config` for Single Settings**
   - Clear and explicit
   - Easy to understand in states
   - Good for conditional configurations

3. **Use `settings_managed` with Caution**
   - Only when you need complete control
   - Document why it's necessary
   - Test thoroughly before production

4. **Test Mode is Your Friend**
   ```bash
   salt '*' state.apply incus.settings test=True
   ```

5. **Version Control Your Pillars**
   - Track all configuration changes
   - Easy rollback if needed
   - Clear audit trail

6. **Use Strong Passwords**
   - Never commit passwords to version control
   - Consider using Salt's encrypted pillars
   - Rotate passwords regularly

7. **Monitor Settings Changes**
   - Use Salt's event system
   - Log all configuration changes
   - Alert on unexpected modifications

---

## Troubleshooting

### Settings Not Applied

Check if the setting key is valid:
```bash
salt '*' incus.settings_get
```

### Permission Denied

Ensure Salt minion has access to Incus socket:
```bash
salt '*' cmd.run 'ls -la /var/lib/incus/unix.socket'
```

### Cluster Settings Not Working

Verify cluster is initialized:
```bash
salt '*' incus.cluster_info
```

### Changes Not Visible

Some settings require service restart:
```bash
salt '*' service.restart incus
```

---

## Quick Reference

### When to Use Which Approach?

| Scenario                               | Recommended Approach         | Reason                       |
|----------------------------------------|------------------------------|------------------------------|
| Initial server setup                   | `server_settings`            | Simple, all settings at once |
| Group of related settings              | `server_settings`            | Compact, atomic update       |
| Single setting change                  | `server_settings_individual` | Clear and explicit           |
| Conditional settings (per environment) | `server_settings_individual` | Easier Jinja templating      |
| Need to remove settings                | `server_settings_individual` | Supports `ensure: absent`    |
| Settings with dependencies             | `server_settings_individual` | Per-setting `require`        |
| Multiple teams managing settings       | `server_settings_individual` | Better separation            |
| Complete config replacement            | `settings_managed` state     | Exact match required         |

### Quick Syntax Comparison

**Bulk Update (`server_settings`):**
```yaml
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      images.auto_update_cached: "true"
```

**Individual Management (`server_settings_individual`):**
```yaml
incus:
  server_settings_individual:
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"
```

**Combined Approach (Recommended):**
```yaml
incus:
  # Base for all
  server_settings:
    config:
      images.auto_update_cached: "true"

  # Conditional
  server_settings_individual:
    {% if grains['environment'] == 'production' %}
    https_api:
      ensure: present
      key: core.https_address
      value: "[::]:8443"
    {% endif %}
```

---

## References

- [Incus Server Configuration Documentation](https://linuxcontainers.org/incus/docs/main/server/)
- [Incus API Reference](https://linuxcontainers.org/incus/docs/main/rest-api/)
- [Salt State Documentation](https://docs.saltproject.io/en/latest/ref/states/all/)
