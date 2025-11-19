# ======================================================================
# Incus Instance Snapshots Configuration Example
# ======================================================================
# This pillar file demonstrates instance snapshot management with
# automatic rotation policies.
#
# Snapshots allow you to save the state of an instance and restore it later.
# They can be:
# - Stateless (filesystem only) - fast, small
# - Stateful (includes runtime state/memory) - slower, larger, for VMs
#
# Features:
# - Simple snapshot creation (stateful and stateless)
# - Automatic snapshot rotation based on retention policies
# - Pattern-based snapshot management (daily-*, weekly-*, etc.)
# - Snapshot restoration
# - Expiry date management
#
# Usage:
#   1. Copy this file to your pillar directory
#   2. Customize the snapshots according to your needs
#   3. Include in your top.sls or specific minion pillar
#   4. Apply with: salt '*' state.apply incus.instance-snapshots
# ======================================================================

incus:
  # ====================================================================
  # Basic Instance Snapshots
  # ====================================================================
  # Simple snapshots without rotation policies
  instance_snapshots:
    # Simple stateless snapshot
    web-backup:
      instance: web-container
      name: before-update
      stateful: false
      description: Snapshot before system update

    # Pre-deployment snapshot
    app-deploy-snapshot:
      instance: app-container
      name: pre-deploy-v2.0
      stateful: false
      description: Snapshot before v2.0 deployment

    # Stateful VM snapshot (includes memory state)
    vm-stateful:
      instance: windows-vm
      name: running-state
      stateful: true
      description: VM snapshot with running state preserved

    # Database snapshot before migration
    db-migration:
      instance: postgres-container
      name: before-schema-migration
      stateful: false
      description: Database snapshot before schema changes

    # Development environment snapshot
    dev-env:
      instance: dev-container
      name: clean-environment
      stateful: false
      description: Clean development environment baseline

    # Snapshot before kernel update
    kernel-update:
      instance: server-container
      name: before-kernel-update
      stateful: false
      description: Snapshot before kernel upgrade

# ======================================================================
# Snapshot Management Patterns
# ======================================================================

# Pattern 1: Regular Backup Strategy
# Create snapshots before major operations
incus_backup_strategy:
  instance_snapshots:
    web-daily:
      instance: web-server
      name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
      stateful: false
      description: Daily automated snapshot

    web-pre-update:
      instance: web-server
      name: before-update
      stateful: false
      description: Before system updates

    web-pre-deploy:
      instance: web-server
      name: before-deploy
      stateful: false
      description: Before application deployment

# Pattern 2: Development Workflow
# Snapshots for development and testing
incus_dev_workflow:
  instance_snapshots:
    dev-baseline:
      instance: dev-container
      name: baseline
      stateful: false
      description: Clean baseline for development

    dev-feature-start:
      instance: dev-container
      name: feature-user-auth-start
      stateful: false
      description: Before implementing user authentication

    dev-experiment:
      instance: dev-container
      name: experimental-changes
      stateful: false
      description: Before experimental changes

# Pattern 3: Production Deployment Strategy
# Multi-tier snapshot strategy
incus_production_deployment:
  instance_snapshots:
    # Frontend tier
    frontend-pre-deploy:
      instance: frontend-prod
      name: pre-deploy-v{{ pillar.get('app_version', '1.0') }}
      stateful: false
      description: Frontend snapshot before v{{ pillar.get('app_version', '1.0') }} deployment

    # Backend tier
    backend-pre-deploy:
      instance: backend-prod
      name: pre-deploy-v{{ pillar.get('app_version', '1.0') }}
      stateful: false
      description: Backend snapshot before v{{ pillar.get('app_version', '1.0') }} deployment

    # Database tier
    database-pre-migration:
      instance: db-prod
      name: before-migration-v{{ pillar.get('app_version', '1.0') }}
      stateful: false
      description: Database before schema migration to v{{ pillar.get('app_version', '1.0') }}

# Pattern 4: VM Snapshot with State
# For virtual machines, capture running state
incus_vm_snapshots:
  instance_snapshots:
    vm-configured:
      instance: ubuntu-vm
      name: post-configuration
      stateful: true
      description: VM after initial configuration with services running

    vm-before-upgrade:
      instance: ubuntu-vm
      name: before-os-upgrade
      stateful: false  # Stateless for OS upgrades
      description: VM before operating system upgrade

    vm-golden-image:
      instance: template-vm
      name: golden-image
      stateful: false
      description: Template VM golden image

# Pattern 5: Testing Strategy
# Snapshots for testing and rollback
incus_testing_strategy:
  instance_snapshots:
    test-baseline:
      instance: test-container
      name: baseline
      stateful: false
      description: Clean test environment

    test-pre-integration:
      instance: test-container
      name: before-integration-tests
      stateful: false
      description: Before running integration tests

    test-successful:
      instance: test-container
      name: all-tests-passed
      stateful: false
      description: Snapshot after all tests passed

# Pattern 6: Disaster Recovery
# Critical snapshots for disaster recovery
incus_disaster_recovery:
  instance_snapshots:
    prod-daily:
      instance: production-app
      name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
      stateful: false
      description: Daily production snapshot for DR

    prod-weekly:
      instance: production-app
      name: weekly-{{ salt['cmd.run']('date +%YW%V') }}
      stateful: false
      description: Weekly production snapshot for long-term backup

    prod-pre-maintenance:
      instance: production-app
      name: before-maintenance
      stateful: false
      description: Before scheduled maintenance window

# Pattern 7: Multi-Instance Coordinated Snapshots
# Snapshot multiple related instances together
incus_coordinated_snapshots:
  instance_snapshots:
    # Snapshot timestamp for coordination
    web1-snapshot:
      instance: web-server-1
      name: coordinated-2024-01-15
      stateful: false
      description: Coordinated snapshot of web tier

    web2-snapshot:
      instance: web-server-2
      name: coordinated-2024-01-15
      stateful: false
      description: Coordinated snapshot of web tier

    api-snapshot:
      instance: api-server
      name: coordinated-2024-01-15
      stateful: false
      description: Coordinated snapshot of API tier

    db-snapshot:
      instance: database-server
      name: coordinated-2024-01-15
      stateful: false
      description: Coordinated snapshot of database tier

# ======================================================================
# Snapshot Naming Conventions
# ======================================================================
#
# Recommended naming patterns:
#
# 1. Time-based:
#    - daily-YYYYMMDD (e.g., daily-20240115)
#    - weekly-YYYYWWW (e.g., weekly-2024W03)
#    - monthly-YYYYMM (e.g., monthly-202401)
#
# 2. Event-based:
#    - before-update
#    - before-deploy
#    - before-migration
#    - after-configuration
#
# 3. Version-based:
#    - pre-deploy-v1.2.3
#    - post-upgrade-v2.0
#
# 4. Purpose-based:
#    - baseline
#    - golden-image
#    - clean-state
#    - configured-state
#
# 5. Feature-based:
#    - feature-user-auth-start
#    - feature-user-auth-complete
#
# ======================================================================
# Managed Snapshots with Automatic Rotation
# ======================================================================
# Use 'managed: true' to enable automatic rotation based on patterns
# and retention policies. This is ideal for scheduled automated backups.

incus_managed_snapshots:
  instance_snapshots:
    # Daily snapshots with 7-day retention
    web-daily:
      instance: web-server
      name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
      stateful: false
      description: Daily automated snapshot
      managed: true
      pattern: daily-*
      keep: 7

    # Weekly snapshots with 4-week retention
    web-weekly:
      instance: web-server
      name: weekly-{{ salt['cmd.run']('date +%YW%V') }}
      stateful: false
      description: Weekly automated snapshot
      managed: true
      pattern: weekly-*
      keep: 4

    # Monthly snapshots with 12-month retention
    web-monthly:
      instance: web-server
      name: monthly-{{ salt['cmd.run']('date +%Y%m') }}
      stateful: false
      description: Monthly automated snapshot
      managed: true
      pattern: monthly-*
      keep: 12

    # Database with hourly snapshots and 24-hour retention
    db-hourly:
      instance: database
      name: hourly-{{ salt['cmd.run']('date +%Y%m%d-%H') }}
      stateful: false
      description: Hourly database snapshot
      managed: true
      pattern: hourly-*
      keep: 24

# ======================================================================
# Standalone Rotation Policies
# ======================================================================
# Define rotation policies separately from snapshot creation.
# Useful for managing existing snapshots.

incus:
  snapshot_rotation:
    # Rotate old daily backups
    rotate-web-daily:
      instance: web-server
      pattern: daily-*
      keep: 7

    # Rotate old weekly backups
    rotate-web-weekly:
      instance: web-server
      pattern: weekly-*
      keep: 4

    # Rotate deployment snapshots
    rotate-deployments:
      instance: app-server
      pattern: deploy-*
      keep: 10

    # Rotate backup snapshots
    rotate-backups:
      instance: database
      pattern: backup-*
      keep: 30

# ======================================================================
# Advanced: Coordinated Multi-Instance Snapshots with Rotation
# ======================================================================
# Create snapshots across multiple instances with the same timestamp
# and automatic rotation

incus_coordinated_backup:
  instance_snapshots:
    # Web tier
    web1-coordinated:
      instance: web-server-1
      name: coordinated-{{ salt['cmd.run']('date +%Y%m%d-%H%M') }}
      stateful: false
      description: Coordinated snapshot of web tier
      managed: true
      pattern: coordinated-*
      keep: 7

    web2-coordinated:
      instance: web-server-2
      name: coordinated-{{ salt['cmd.run']('date +%Y%m%d-%H%M') }}
      stateful: false
      description: Coordinated snapshot of web tier
      managed: true
      pattern: coordinated-*
      keep: 7

    # API tier
    api-coordinated:
      instance: api-server
      name: coordinated-{{ salt['cmd.run']('date +%Y%m%d-%H%M') }}
      stateful: false
      description: Coordinated snapshot of API tier
      managed: true
      pattern: coordinated-*
      keep: 7

    # Database tier
    db-coordinated:
      instance: database-server
      name: coordinated-{{ salt['cmd.run']('date +%Y%m%d-%H%M') }}
      stateful: false
      description: Coordinated snapshot of database tier
      managed: true
      pattern: coordinated-*
      keep: 7

# ======================================================================
# Snapshot Restoration
# ======================================================================
# To restore an instance to a previous snapshot state, set ensure: restored

incus_restore_example:
  instance_snapshots:
    restore-web-backup:
      instance: web-server
      name: before-update
      ensure: restored  # This will restore the instance to this snapshot

# WARNING: Restoration will overwrite current instance state!
# Always create a snapshot before restoring if you want to preserve current state.

# ======================================================================
# Snapshot Deletion
# ======================================================================
# To delete a snapshot, set ensure: absent

incus_cleanup_example:
  instance_snapshots:
    delete-old-snapshot:
      instance: web-server
      name: temporary-snapshot
      ensure: absent  # This will delete the snapshot

# ======================================================================
# Complete Production Example with All Features
# ======================================================================

incus_production_complete:
  instance_snapshots:
    # Pre-deployment snapshot (manual, kept indefinitely)
    prod-pre-deploy:
      instance: production-app
      name: pre-deploy-v{{ pillar.get('app_version', '1.0') }}
      stateful: false
      description: Snapshot before v{{ pillar.get('app_version', '1.0') }} deployment
      ensure: present

    # Hourly snapshots for production (24-hour retention)
    prod-hourly:
      instance: production-app
      name: hourly-{{ salt['cmd.run']('date +%Y%m%d-%H') }}
      stateful: false
      description: Hourly production snapshot
      managed: true
      pattern: hourly-*
      keep: 24

    # Daily snapshots for production (7-day retention)
    prod-daily:
      instance: production-app
      name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
      stateful: false
      description: Daily production snapshot
      managed: true
      pattern: daily-*
      keep: 7

    # Weekly snapshots for production (4-week retention)
    prod-weekly:
      instance: production-app
      name: weekly-{{ salt['cmd.run']('date +%YW%V') }}
      stateful: false
      description: Weekly production snapshot
      managed: true
      pattern: weekly-*
      keep: 4

    # Monthly snapshots for production (12-month retention)
    prod-monthly:
      instance: production-app
      name: monthly-{{ salt['cmd.run']('date +%Y%m') }}
      stateful: false
      description: Monthly production snapshot
      managed: true
      pattern: monthly-*
      keep: 12

  # Additional rotation policies
  snapshot_rotation:
    # Cleanup old test snapshots
    rotate-test-snapshots:
      instance: production-app
      pattern: test-*
      keep: 3

    # Cleanup old experimental snapshots
    rotate-experimental:
      instance: production-app
      pattern: experimental-*
      keep: 1

# ======================================================================
# Important Notes
# ======================================================================
#
# Stateful Snapshots:
# - Only supported for virtual machines
# - Include memory and runtime state
# - VM must be running for stateful snapshot
# - Larger size than stateless snapshots
# - Slower to create and restore
# - Use for: VM state preservation, live migration testing
#
# Stateless Snapshots:
# - Support both containers and VMs
# - Only capture filesystem state
# - Fast to create and restore
# - Smaller storage footprint
# - Instance can be stopped or running
# - Use for: Backups, rollback points, templates
#
# Rotation Policies:
# - Automatically delete old snapshots based on patterns
# - Keep only the N most recent snapshots
# - Pattern matching uses Unix shell-style wildcards (*, ?, [seq])
# - Snapshots are sorted by creation time
# - Rotation happens AFTER creating new snapshots
#
# Best Practices:
# - Always snapshot before major changes
# - Use descriptive names and descriptions
# - Document what each snapshot contains
# - Implement snapshot retention policies (use 'keep' parameter)
# - Test restore procedures regularly
# - Consider storage implications
# - Coordinate snapshots for multi-tier applications
# - Use patterns for automated rotation (daily-*, weekly-*, etc.)
# - Set 'managed: true' for automatic rotation
# - Create separate rotation policies for different snapshot types
#
# Snapshot Naming Conventions:
# - Time-based: daily-YYYYMMDD, weekly-YYYYWWW, monthly-YYYYMM
# - Event-based: before-update, before-deploy, after-configuration
# - Version-based: pre-deploy-v1.2.3, post-upgrade-v2.0
# - Purpose-based: baseline, golden-image, clean-state
#
# Storage Considerations:
# - Snapshots consume storage space
# - Monitor storage pool capacity
# - Implement retention policies (use 'keep' parameter)
# - Rotation automatically cleans up old snapshots
# - Use ZFS or Btrfs for efficient snapshots
# - Consider snapshot frequency vs. storage capacity
#
# Scheduling:
# - Use Salt scheduler or cron for automated snapshot creation
# - Example Salt scheduler:
#   schedule:
#     daily_snapshot:
#       function: state.apply
#       args:
#         - incus.instance-snapshots
#       kwargs:
#         pillar:
#           incus:
#             instance_snapshots:
#               daily:
#                 instance: mycontainer
#                 name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
#                 managed: true
#                 pattern: daily-*
#                 keep: 7
#       hours: 24
#
# ======================================================================
