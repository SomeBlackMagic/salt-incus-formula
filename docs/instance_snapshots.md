# Incus Instance Snapshots Management

This document describes how to manage Incus instance snapshots using Salt states.

## Table of Contents

- [Overview](#overview)
- [State Functions](#state-functions)
- [Configuration Examples](#configuration-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Instance snapshots in Incus allow you to save the state of an instance (container or VM) and restore it later. Snapshots can be:

- **Stateless**: Only capture the filesystem state (fast, lightweight)
- **Stateful**: Capture both filesystem and runtime state including memory (VMs only, slower, larger)

### Use Cases

- **Backups**: Regular snapshots for disaster recovery
- **Rollback Points**: Before major changes (updates, migrations, deployments)
- **Development**: Baseline environments, experimental changes
- **Testing**: Clean states for repeated testing
- **Cloning**: Create new instances from snapshots

## State Functions

### instance_snapshot_present

Ensure an instance snapshot exists.

**Parameters:**
- `instance` (required): Instance name
- `name` (required): Snapshot name
- `stateful` (optional): Create stateful snapshot (default: `false`)
- `description` (optional): Snapshot description

**Example:**

```yaml
before-update-snap:
  incus.instance_snapshot_present:
    - instance: web-container
    - name: before-system-update
    - stateful: false
    - description: Snapshot before OS update

vm-running-state:
  incus.instance_snapshot_present:
    - instance: windows-vm
    - name: configured-state
    - stateful: true
    - description: VM with all services running
```

### instance_snapshot_absent

Ensure an instance snapshot does not exist.

**Parameters:**
- `instance` (required): Instance name
- `name` (required): Snapshot name

**Example:**

```yaml
old-snapshot:
  incus.instance_snapshot_absent:
    - instance: web-container
    - name: obsolete-snap
```

### instance_snapshot_restored

Restore an instance to a snapshot state.

⚠️ **WARNING**: This will restore the instance to the snapshot state, losing any changes made after the snapshot was created.

**Parameters:**
- `instance` (required): Instance name
- `name` (required): Snapshot name to restore

**Example:**

```yaml
restore-before-update:
  incus.instance_snapshot_restored:
    - instance: web-container
    - name: before-system-update
```

## Configuration Examples

### Basic Snapshot Strategy

```yaml
incus:
  instance_snapshots:
    # Daily snapshot
    web-daily:
      instance: web-server
      name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
      stateful: false
      description: Daily automated snapshot

    # Pre-update snapshot
    web-pre-update:
      instance: web-server
      name: before-update
      stateful: false
      description: Before system updates

    # Pre-deployment snapshot
    web-pre-deploy:
      instance: web-server
      name: before-deploy
      stateful: false
      description: Before application deployment
```

### Development Workflow

```yaml
incus:
  instance_snapshots:
    # Clean baseline
    dev-baseline:
      instance: dev-container
      name: baseline
      stateful: false
      description: Clean baseline for development

    # Feature development
    dev-feature-start:
      instance: dev-container
      name: feature-user-auth-start
      stateful: false
      description: Before implementing user authentication

    # Experimental changes
    dev-experiment:
      instance: dev-container
      name: experimental-changes
      stateful: false
      description: Before experimental changes
```

### Production Deployment Strategy

```yaml
incus:
  instance_snapshots:
    # Frontend tier
    frontend-pre-deploy:
      instance: frontend-prod
      name: pre-deploy-v1.2.3
      stateful: false
      description: Frontend before v1.2.3 deployment

    # Backend tier
    backend-pre-deploy:
      instance: backend-prod
      name: pre-deploy-v1.2.3
      stateful: false
      description: Backend before v1.2.3 deployment

    # Database tier (critical!)
    database-pre-migration:
      instance: db-prod
      name: before-migration-v1.2.3
      stateful: false
      description: Database before schema migration
```

### VM Stateful Snapshots

```yaml
incus:
  instance_snapshots:
    # VM with services running
    vm-configured:
      instance: ubuntu-vm
      name: post-configuration
      stateful: true
      description: VM after configuration with services running

    # Before OS upgrade (stateless)
    vm-before-upgrade:
      instance: ubuntu-vm
      name: before-os-upgrade
      stateful: false  # Stateless for OS upgrades
      description: VM before operating system upgrade

    # Golden image template
    vm-golden-image:
      instance: template-vm
      name: golden-image
      stateful: false
      description: Template VM golden image
```

### Coordinated Multi-Instance Snapshots

```yaml
incus:
  instance_snapshots:
    # Use same timestamp for all snapshots
    web1-snapshot:
      instance: web-server-1
      name: coordinated-2024-01-15-1200
      stateful: false
      description: Coordinated snapshot of web tier

    web2-snapshot:
      instance: web-server-2
      name: coordinated-2024-01-15-1200
      stateful: false
      description: Coordinated snapshot of web tier

    api-snapshot:
      instance: api-server
      name: coordinated-2024-01-15-1200
      stateful: false
      description: Coordinated snapshot of API tier

    db-snapshot:
      instance: database-server
      name: coordinated-2024-01-15-1200
      stateful: false
      description: Coordinated snapshot of database tier
```

## Best Practices

### Naming Conventions

Use consistent, descriptive snapshot names:

**Time-based:**
```
daily-YYYYMMDD          # daily-20240115
weekly-YYYYWWW          # weekly-2024W03
monthly-YYYYMM          # monthly-202401
```

**Event-based:**
```
before-update
before-deploy
before-migration
after-configuration
```

**Version-based:**
```
pre-deploy-v1.2.3
post-upgrade-v2.0
```

**Purpose-based:**
```
baseline
golden-image
clean-state
configured-state
```

### Stateless vs Stateful

**Use Stateless Snapshots for:**
- Containers (only option)
- Regular backups
- Before/after comparisons
- Template creation
- Storage efficiency

**Use Stateful Snapshots for:**
- VMs with running services
- Testing live migration
- Preserving complete runtime state
- Debugging purposes

### Snapshot Management

1. **Regular Backups**
   ```yaml
   # Automated daily snapshots (use cron + salt)
   incus:
     instance_snapshots:
       web-daily:
         instance: web-server
         name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
         stateful: false
         description: Daily automated snapshot
   ```

2. **Pre-Change Snapshots**
   - Always snapshot before major changes
   - Test restore procedures
   - Document snapshot contents

3. **Retention Policy**
   ```bash
   # Clean up old snapshots (manual or via script)
   incus snapshot list web-server
   incus delete web-server/daily-20240101
   ```

4. **Storage Considerations**
   - Monitor storage pool capacity
   - Use ZFS or Btrfs for efficient snapshots
   - Implement retention policies
   - Clean up old snapshots regularly

### Automatic Snapshot Configuration

Configure automatic snapshots in instance config:

```yaml
incus:
  instances:
    web-server:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
        snapshots.schedule: "@daily"     # Automatic schedule
        snapshots.expiry: "7d"            # Auto-delete after 7 days
        snapshots.pattern: "auto-%Y%m%d" # Naming pattern
      profiles:
        - default
```

## Troubleshooting

### Snapshot Creation Fails

**Problem**: Snapshot creation fails with errors

**Solutions**:
1. Check storage pool capacity:
   ```bash
   incus storage info <pool>
   ```

2. Verify instance exists and is accessible:
   ```bash
   incus info <instance>
   ```

3. For stateful snapshots, ensure VM is running:
   ```bash
   incus start <instance>
   ```

4. Check for disk space:
   ```bash
   df -h /var/lib/incus
   ```

### Snapshot Restore Issues

**Problem**: Cannot restore from snapshot

**Solutions**:
1. Stop instance before restore:
   ```bash
   incus stop <instance>
   incus restore <instance> <snapshot>
   ```

2. Check snapshot exists:
   ```bash
   incus info <instance>
   ```

3. Verify snapshot is not corrupted:
   ```bash
   incus snapshot show <instance>/<snapshot>
   ```

### Performance Issues

**Problem**: Snapshots are slow or consume too much storage

**Solutions**:
1. Use ZFS or Btrfs storage drivers (efficient snapshots)
2. Avoid stateful snapshots unless necessary
3. Implement snapshot retention policies
4. Monitor storage pool performance

### Missing Snapshots

**Problem**: Snapshots disappear or are not created

**Solutions**:
1. Check expiry settings:
   ```bash
   incus config show <instance>
   ```

2. Verify automatic snapshot schedule:
   ```bash
   incus config get <instance> snapshots.schedule
   ```

3. Check storage pool health:
   ```bash
   incus storage info <pool>
   ```

## Related Documentation

- [instances.md](instances.md) - Instance management
- [storages.md](storages.md) - Storage configuration
- [Incus Snapshots Documentation](https://linuxcontainers.org/incus/docs/main/howto/storage_backup_volume/)

## See Also

- Pillar example: `pillars.example/instance-snapshots.sls`
- State module: `_states/incus.py` (lines 442-660)
