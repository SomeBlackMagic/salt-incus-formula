# Incus Profile Management

Complete guide for managing Incus profiles via Salt.

## Table of Contents

- [Overview](#overview)
- [What are Profiles](#what-are-profiles)
- [Pillar Structure](#pillar-structure)
- [State Functions](#state-functions)
- [Execution Module](#execution-module)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Salt module for Incus supports full profile management:

- **Profile Creation** with configuration and devices
- **Profile Updates** with parameter changes
- **Configuration Management** without device changes
- **Profile Deletion** when no longer needed
- **Profile Copying** to create variations
- **Profile Renaming** to change names

## What are Profiles

Profiles in Incus are configuration templates that are applied to instances at creation time. A profile can contain:

- **Configuration** (config) — resource, security, and boot parameters
- **Devices** (devices) — network interfaces, disks, GPUs, USB devices
- **Description** (description) — human-readable description of the profile's purpose

### Why Use Profiles?

1. **Standardization** — same settings for a group of instances
2. **Reusability** — one profile for multiple containers
3. **Simplification** — fewer parameters when creating instances
4. **Centralization** — profile changes affect all instances
5. **Flexibility** — multiple profiles can be applied to a single instance

## Pillar Structure

```yaml
incus:
  profiles:
    profile-name:
      ensure: present          # present or absent
      description: "..."       # Profile description
      config: {}              # Configuration parameters
      devices: {}             # Devices
      update_config: {}       # Configuration update (optional)
      update_description: ""  # Description update (optional)
```

### Main Parameters

- **ensure**: `present` (create/update) or `absent` (delete)
- **description**: Description of the profile's purpose
- **config**: Dictionary of configuration parameters
- **devices**: Dictionary of devices
- **update_config**: Apply configuration changes without recreation
- **update_description**: Update description without recreation

## State Functions

### profile_present

Creates or updates a profile.

```yaml
webserver:
  incus.profile_present:
    - config:
        limits.cpu: "4"
        limits.memory: 4GB
    - devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
    - description: Web server profile
```

### profile_absent

Deletes a profile.

```yaml
old_profile:
  incus.profile_absent
```

**Important**: A profile cannot be deleted if it is being used by instances.

### profile_config

Updates only the profile configuration without changing devices.

```yaml
webserver:
  incus.profile_config:
    - config:
        limits.memory: 8GB
    - description: Updated memory allocation
```

## Execution Module

### List Profiles

```bash
# Get list of profile names
salt '*' incus.profile_list

# Get full information about profiles
salt '*' incus.profile_list recursion=1
```

### Get Profile Information

```bash
salt '*' incus.profile_get default
salt '*' incus.profile_get webserver
```

### Create Profile

```bash
# Create simple profile
salt '*' incus.profile_create myprofile

# Create profile with configuration
salt '*' incus.profile_create myprofile \
  config="{'limits.cpu':'2','limits.memory':'4GB'}"

# Create profile with devices
salt '*' incus.profile_create webserver \
  config="{'limits.cpu':'4'}" \
  devices="{'eth0':{'type':'nic','network':'lxdbr0'}}" \
  description="Web server profile"
```

### Update Profile

```bash
# Update configuration
salt '*' incus.profile_update myprofile \
  config="{'limits.memory':'8GB'}"

# Update devices
salt '*' incus.profile_update myprofile \
  devices="{'eth1':{'type':'nic','network':'mybr0'}}"

# Update description
salt '*' incus.profile_update myprofile \
  description="Updated description"
```

### Rename Profile

```bash
salt '*' incus.profile_rename oldname newname
```

### Copy Profile

```bash
# Copy with same description
salt '*' incus.profile_copy default myprofile

# Copy with new description
salt '*' incus.profile_copy default myprofile \
  description="Copy of default profile"
```

### Delete Profile

```bash
salt '*' incus.profile_delete myprofile
```

## Usage Examples

### 1. Basic Resource Profiles

```yaml
incus:
  profiles:
    # Minimal resources for testing
    minimal:
      ensure: present
      description: Minimal resources for testing
      config:
        limits.cpu: "1"
        limits.memory: 512MB

    # Standard resources
    standard:
      ensure: present
      description: Standard resources
      config:
        limits.cpu: "2"
        limits.memory: 2GB

    # Maximum performance
    performance:
      ensure: present
      description: High-performance workloads
      config:
        limits.cpu: "8"
        limits.memory: 16GB
        limits.processes: "2000"
```

### 2. Profiles with Network Devices

```yaml
incus:
  profiles:
    # Single network interface
    single-nic:
      ensure: present
      description: Single network interface
      config:
        limits.cpu: "2"
        limits.memory: 2GB
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0

    # Multiple network interfaces
    multi-nic:
      ensure: present
      description: Multiple network interfaces
      config:
        limits.cpu: "2"
        limits.memory: 2GB
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        eth1:
          name: eth1
          type: nic
          nictype: bridged
          parent: lxdbr1
        eth2:
          name: eth2
          type: nic
          nictype: macvlan
          parent: eth0
          vlan: "100"
```

### 3. Profiles with Disks

```yaml
incus:
  profiles:
    # Large root disk
    large-disk:
      ensure: present
      description: Large root disk
      config:
        limits.cpu: "2"
        limits.memory: 4GB
      devices:
        root:
          path: /
          pool: default
          size: 100GB
          type: disk

    # Additional disks for data
    database:
      ensure: present
      description: Database with data volume
      config:
        limits.cpu: "8"
        limits.memory: 16GB
      devices:
        root:
          path: /
          pool: default
          type: disk
        data:
          path: /var/lib/mysql
          pool: default
          source: mysql-data
          type: disk
        logs:
          path: /var/log/mysql
          pool: logs-pool
          source: mysql-logs
          type: disk
```

### 4. Security Profiles

```yaml
incus:
  profiles:
    # Privileged container
    privileged:
      ensure: present
      description: Privileged container
      config:
        security.privileged: "true"
        security.nesting: "true"
        linux.kernel_modules: "ip_tables,ip6_tables,netlink_diag,nf_nat,overlay"

    # Nested virtualization (Docker inside)
    nested:
      ensure: present
      description: Support for Docker/LXD inside
      config:
        security.nesting: "true"
        security.privileged: "false"
        linux.kernel_modules: "overlay,br_netfilter,ip_tables"

    # Isolated container
    isolated:
      ensure: present
      description: Maximum isolation
      config:
        security.privileged: "false"
        security.nesting: "false"
        security.idmap.isolated: "true"
        security.syscalls.deny_default: "true"
```

### 5. Development Profiles

```yaml
incus:
  profiles:
    # Developer environment with GPU
    development:
      ensure: present
      description: Development environment
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.nesting: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          network: lxdbr0
        gpu:
          type: gpu
          gputype: physical
          pci: "0000:01:00.0"
        home:
          path: /home/developer
          source: /home/developer
          type: disk

    # CI/CD runner
    ci-runner:
      ensure: present
      description: CI/CD runner with Docker
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.nesting: "true"
        linux.kernel_modules: "overlay,br_netfilter,nf_nat"
        raw.lxc: |
          lxc.apparmor.profile=unconfined
          lxc.mount.auto=proc:rw sys:rw cgroup:rw
```

### 6. Autostart Profiles

```yaml
incus:
  profiles:
    # Autostart with priority
    autostart:
      ensure: present
      description: Auto-start on boot
      config:
        boot.autostart: "true"
        boot.autostart.delay: "10"
        boot.autostart.priority: "50"
        boot.host_shutdown_timeout: "60"

    # Critical services (start first)
    critical-service:
      ensure: present
      description: Critical services (high priority)
      config:
        boot.autostart: "true"
        boot.autostart.priority: "100"
        boot.autostart.delay: "0"
```

### 7. Virtual Machine Profiles

```yaml
incus:
  profiles:
    # Standard VM
    vm-standard:
      ensure: present
      description: Standard VM profile
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.secureboot: "false"
        boot.autostart: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          network: lxdbr0
        root:
          path: /
          pool: default
          size: 50GB
          type: disk
          boot.priority: "0"

    # High-performance VM with GPU
    vm-performance:
      ensure: present
      description: High-performance VM
      config:
        limits.cpu: "16"
        limits.memory: 32GB
        security.secureboot: "false"
      devices:
        eth0:
          name: eth0
          type: nic
          network: lxdbr0
        root:
          path: /
          pool: nvme-pool
          size: 200GB
          type: disk
        gpu:
          type: gpu
          gputype: mdev
          mdev: "i915-GVTg_V5_4"
```

### 8. Updating Existing Profiles

```yaml
incus:
  profiles:
    # Original profile
    webserver:
      ensure: present
      config:
        limits.cpu: "4"
        limits.memory: 4GB
      # Update only memory without recreation
      update_config:
        limits.memory: 8GB
      update_description: Increased memory allocation

    # Gradual scaling
    database:
      ensure: present
      config:
        limits.cpu: "4"
        limits.memory: 8GB
      # Resource scaling
      update_config:
        limits.cpu: "8"
        limits.memory: 16GB
        limits.processes: "5000"
```

### 9. Specialized Profiles

```yaml
incus:
  profiles:
    # NAT Gateway
    nat-gateway:
      ensure: present
      description: NAT gateway with forwarding
      config:
        security.nesting: "true"
        raw.lxc: |
          lxc.mount.entry=/proc/sys/net proc/sys/net none bind,create=dir 0 0
      devices:
        eth0:
          name: eth0
          type: nic
          network: internal
        eth1:
          name: eth1
          type: nic
          network: external

    # GPU Workstation
    gpu-workstation:
      ensure: present
      description: Workstation with GPU and USB
      config:
        limits.cpu: "8"
        limits.memory: 16GB
      devices:
        eth0:
          name: eth0
          type: nic
          network: lxdbr0
        gpu:
          type: gpu
          gputype: physical
          id: "0"
        usb-keyboard:
          type: usb
          vendorid: "046d"
          productid: "c52b"

    # Router/Firewall
    router:
      ensure: present
      description: Router with multiple interfaces
      config:
        security.privileged: "true"
        linux.kernel_modules: "ip_tables,ip6_tables,nf_nat,xt_conntrack"
      devices:
        wan:
          name: eth0
          type: nic
          nictype: bridged
          parent: wan-br
        lan:
          name: eth1
          type: nic
          nictype: bridged
          parent: lan-br
```

### 10. Deleting Profiles

```yaml
incus:
  profiles:
    # Delete old profile
    old-profile:
      ensure: absent

    # Delete temporary profile
    temp-profile:
      ensure: absent

    # Delete unused profile
    deprecated-profile:
      ensure: absent
```

## Best Practices

### 1. Profile Naming

- Use clear names: `webserver`, `database`, `ci-runner`
- Add prefixes for grouping: `prod-`, `dev-`, `test-`
- Indicate purpose: `nginx-frontend`, `mysql-backend`

### 2. Profile Organization

```yaml
incus:
  profiles:
    # Base profiles (used as foundation)
    base-minimal:
      ensure: present
      config:
        limits.cpu: "1"
        limits.memory: 512MB

    base-standard:
      ensure: present
      config:
        limits.cpu: "2"
        limits.memory: 2GB

    # Specialized profiles (extend base profiles)
    web-production:
      ensure: present
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        boot.autostart: "true"
      devices:
        eth0:
          type: nic
          network: prod-network
```

### 3. Documentation

Always add descriptions:

```yaml
database-primary:
  ensure: present
  description: "Primary database server - 16GB RAM, 8 CPU, auto-start enabled"
  config:
    limits.cpu: "8"
    limits.memory: 16GB
```

### 4. Testing

Create test profiles before production:

```yaml
# Testing
test-webserver:
  ensure: present
  config:
    limits.cpu: "1"
    limits.memory: 1GB

# Production (after testing)
prod-webserver:
  ensure: present
  config:
    limits.cpu: "4"
    limits.memory: 8GB
```

### 5. Using update_config

Use `update_config` to modify live profiles:

```yaml
webserver:
  ensure: present
  config:
    limits.cpu: "2"
    limits.memory: 4GB
  # Gradual resource increase
  update_config:
    limits.memory: 8GB
  update_description: "Memory increased to 8GB - {{ pillar['date'] }}"
```

### 6. Profiles by Environment

```yaml
incus:
  profiles:
    # Development
    dev-app:
      ensure: present
      config:
        limits.cpu: "2"
        limits.memory: 2GB

    # Staging
    staging-app:
      ensure: present
      config:
        limits.cpu: "4"
        limits.memory: 4GB

    # Production
    prod-app:
      ensure: present
      config:
        limits.cpu: "8"
        limits.memory: 16GB
        boot.autostart: "true"
```

## Configuration Parameters

### Resources (Resource Limits)

```yaml
config:
  limits.cpu: "4"                    # Number of CPUs or % ("50%")
  limits.memory: 4GB                 # Memory limit
  limits.processes: "500"            # Maximum processes
  limits.cpu.priority: "10"          # CPU priority (0-10)
  limits.cpu.allowance: "50%"        # CPU time allowance
  limits.memory.enforce: "hard"      # hard or soft
```

### Security

```yaml
config:
  security.privileged: "false"              # Privileged container
  security.nesting: "true"                  # Nested containers
  security.idmap.isolated: "true"           # Isolated ID mapping
  security.syscalls.deny_default: "true"    # Deny dangerous syscalls
  security.syscalls.deny_compat: "true"     # Deny 32-bit syscalls
  security.protection.delete: "true"        # Protection from deletion
  security.protection.shift: "true"         # Protection from ID shift
```

### Boot

```yaml
config:
  boot.autostart: "true"                # Auto-start
  boot.autostart.delay: "10"            # Delay in seconds
  boot.autostart.priority: "50"         # Start order (0-100)
  boot.host_shutdown_timeout: "60"      # Timeout on host shutdown
  boot.stop.priority: "50"              # Stop order
```

### Kernel

```yaml
config:
  linux.kernel_modules: "ip_tables,overlay,br_netfilter"  # Kernel modules
  raw.lxc: |                                               # Direct LXC configuration
    lxc.apparmor.profile=unconfined
    lxc.mount.auto=proc:rw sys:rw
```

### Snapshots

```yaml
config:
  snapshots.schedule: "@daily"           # Snapshot schedule
  snapshots.schedule.stopped: "false"    # Snapshots of stopped instances
  snapshots.pattern: "snap-%Y%m%d"       # Name template
  snapshots.expiry: "7d"                 # Retention period
```

## Device Types

### Network Interfaces (NIC)

```yaml
devices:
  eth0:
    type: nic
    nictype: bridged             # bridged, macvlan, physical, routed, p2p, sriov
    parent: lxdbr0               # Parent interface/bridge
    network: mybr0               # Managed network
    hwaddr: "00:16:3e:xx:xx:xx"  # MAC address
    mtu: "1500"                  # MTU
    vlan: "100"                  # VLAN ID
```

### Disks (Disk)

```yaml
devices:
  root:
    type: disk
    path: /                # Mount path
    pool: default          # Storage pool
    source: volume-name    # Source (volume or host path)
    size: 50GB             # Size (for new volumes only)
    boot.priority: "0"     # Boot priority for VM
```

### GPU

```yaml
devices:
  gpu0:
    type: gpu
    gputype: physical      # physical, mdev, mig, sriov
    id: "0"                # GPU ID
    pci: "0000:01:00.0"    # PCI address
    mdev: "type-id"        # mdev type
```

### USB

```yaml
devices:
  usb-device:
    type: usb
    vendorid: "046d"       # Vendor ID
    productid: "c52b"      # Product ID
    required: "true"       # Required presence
```

### Proxy

```yaml
devices:
  proxy-ssh:
    type: proxy
    listen: tcp:0.0.0.0:2222       # Listen address
    connect: tcp:127.0.0.1:22      # Connect address
    bind: host                      # host or container
    nat: "true"                     # NAT mode
```

## Troubleshooting

### Profile is in use by instances

```bash
# Error: Profile is currently in use
# Solution: find instances using the profile
salt '*' incus.instance_list recursion=1 | grep profile_name

# Remove profile from instance
salt '*' incus.instance_update instance_name profiles='["default"]'
```

### Device conflict

```bash
# Error: Device already exists
# Solution: check existing devices
salt '*' incus.profile_get profile_name

# Update device instead of adding
salt '*' incus.profile_update profile_name devices="{'eth0':{'type':'nic',...}}"
```

### Insufficient permissions

```bash
# Error: Permission denied
# Solution: check user permissions
groups $(whoami)  # should have lxd/incus group

# Add user to group
sudo usermod -aG incus $(whoami)
newgrp incus
```

### Incorrect configuration syntax

```yaml
# ❌ Incorrect
config:
  limits.memory: 4GB     # String, not a number

# ✅ Correct
config:
  limits.memory: "4GB"   # Always in quotes
```

### Profile is not applied to instances

```bash
# Profile changes don't affect running instances
# Solution: restart the instance
salt '*' incus.instance_stop instance_name
salt '*' incus.instance_start instance_name
```

### Debugging

```bash
# View complete profile configuration
salt '*' incus.profile_get profile_name

# View which profiles an instance uses
salt '*' incus.instance_get instance_name | grep profiles

# Check State status
salt '*' state.apply incus.profiles test=True

# View Salt logs
tail -f /var/log/salt/minion
```

## Additional Resources

- [Incus Documentation - Profiles](https://linuxcontainers.org/incus/docs/main/profiles/)
- [Pillar Examples](../pillars.example/profiles.sls)

## Conclusion

Profiles are a powerful tool for standardizing and simplifying Incus instance management. Use them for:

- Creating configuration templates
- Grouping common settings
- Simplifying instance creation
- Centralized settings management

Proper use of profiles significantly simplifies Incus infrastructure administration.
