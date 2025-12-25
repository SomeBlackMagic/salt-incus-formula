# Incus Instances Management

This document describes how to manage Incus instances (containers and virtual machines) using Salt states.

## Table of Contents

- [Overview](#overview)
- [State Functions](#state-functions)
- [Configuration Examples](#configuration-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Instances are the main workload units in Incus. They can be:

- **Containers**: System containers sharing the host kernel (lightweight, fast startup)
- **Virtual Machines**: Full VMs with their own kernel (isolated, different OS possible)

### Key Features

- **Resource Limits**: CPU, memory, processes
- **Device Management**: NICs, disks, GPUs, USB devices
- **State Management**: Running, stopped, frozen
- **Snapshots**: Point-in-time backups and restore
- **Migration**: Live or stateful migration between hosts
- **Profiles**: Template-based configuration

## State Functions

### instance_present

Ensure an instance exists with a specified configuration.

**Parameters:**
- `name` (required): Instance name
- `source` (optional): Source configuration for creating instance
  - **Type**: `image` - Create from image (default)
  - **Type**: `copy` - Copy existing instance
  - **Type**: `migration` - Migrate instance from another host
  - **Type**: `none` - Create empty instance without base image
- `instance_type` (optional): "container" or "virtual-machine" (default: "container")
- `config` (optional): Instance configuration dict
- `devices` (optional): Device configuration dict
- `profiles` (optional): List of profiles to apply
- `ephemeral` (optional): Whether instance is ephemeral (default: `false`)

**Examples:**

**Create from image:**
```yaml
web-server:
  incus.instance_present:
    - source:
        type: image
        alias: ubuntu/22.04
    - instance_type: container
    - config:
        limits.cpu: "2"
        limits.memory: 2GiB
        boot.autostart: "true"
    - profiles:
        - default
        - webserver
    - devices:
        eth0:
          type: nic
          network: frontend-net
```

**Create empty instance (no base image):**
```yaml
custom-instance:
  incus.instance_present:
    - source:
        type: none
    - instance_type: container
    - config:
        limits.cpu: "1"
        limits.memory: 512MiB
    - profiles:
        - default
```

**Copy existing instance:**
```yaml
web-server-clone:
  incus.instance_present:
    - source:
        type: copy
        source: web-server
    - config:
        limits.cpu: "2"
        limits.memory: 2GiB
```

**Migrate instance from remote:**
```yaml
migrated-instance:
  incus.instance_present:
    - source:
        type: migration
        mode: pull
        base-image: ubuntu/22.04
        server: https://remote-server:8443
    - instance_type: container
```

### instance_absent

Ensure an instance does not exist.

**Parameters:**
- `name` (required): Instance name
- `force` (optional): Force deletion even if running (default: `false`)

**Example:**

```yaml
old-container:
  incus.instance_absent:
    - force: true
```

### instance_running

Ensure an instance is in a running state.

**Parameters:**
- `name` (required): Instance name
- `wait_is_ready` (optional): Wait for incus-agent to be fully ready (default: `false`)
- `ready_timeout` (optional): Timeout in seconds for waiting agent readiness (default: `300`)

**Example:**

```yaml
web-server:
  incus.instance_running

# Wait for VM agent to be ready
ubuntu-vm:
  incus.instance_running:
    - wait_is_ready: true
    - ready_timeout: 600
```

**Note:** The `wait_is_ready` parameter is particularly useful for virtual machines, as they need time for the incus-agent to start and become responsive. This ensures the instance is fully operational before proceeding with subsequent states.

### instance_stopped

Ensure an instance is in the stopped state.

**Parameters:**
- `name` (required): Instance name
- `force` (optional): Force stop (default: `false`)

**Example:**

```yaml
maintenance-container:
  incus.instance_stopped:
    - force: true
```

### instance_initialized

Ensure an instance has completed cloud-init initialization.

This state checks if cloud-init is installed on the instance. If cloud-init is not available, the state is skipped (no changes). If cloud-init is enabled, the state waits for cloud-init to complete successfully.

The state is idempotent and can be run multiple times safely. It's particularly useful for:
- Ensuring VMs with cloud-init have completed their initial setup
- Detecting cloud-init errors early in the deployment process
- Coordinating dependent states that need the instance to be fully initialized

**Parameters:**
- `name` (required): Instance name
- `timeout` (optional): Maximum seconds to wait for cloud-init completion (default: `600`)
- `check_interval` (optional): Poll interval in seconds (default: `5`)

**Behavior:**
- **cloud-init not installed**: State succeeds with no changes (skipped)
- **cloud-init successful**: State succeeds with changes showing completion time
- **cloud-init error**: State fails with error details from cloud-init
- **cloud-init timeout**: State fails if timeout is reached before completion

**Examples:**

```yaml
# Basic usage
ubuntu-vm:
  incus.instance_initialized

# With custom timeout
ubuntu-vm:
  incus.instance_initialized:
    - timeout: 900         # Wait up to 15 minutes
    - check_interval: 10   # Check every 10 seconds

# With dependencies
database-vm:
  incus.instance_present:
    - source:
        type: image
        alias: ubuntu/22.04/cloud
    - instance_type: virtual-machine
    - config:
        limits.cpu: "4"
        limits.memory: 8GiB
    - started: true

database-vm-ready:
  incus.instance_initialized:
    - name: database-vm
    - timeout: 600
    - require:
      - incus: database-vm

configure-database:
  cmd.run:
    - name: incus exec database-vm -- /opt/setup-database.sh
    - require:
      - incus: database-vm-ready
```

**State Return Values:**

Success (cloud-init completed):
```python
{
    'result': True,
    'changes': {
        'cloud-init': {
            'status': 'done',
            'elapsed_time': '45.3s'
        }
    },
    'comment': 'cloud-init completed successfully on instance myvm (waited 45.3s)'
}
```

Success (cloud-init not installed):
```python
{
    'result': True,
    'changes': {},
    'comment': 'Instance myvm does not have cloud-init installed. Skipping initialization check.'
}
```

Failure (cloud-init error):
```python
{
    'result': False,
    'changes': {
        'cloud-init': {
            'status': 'error',
            'details': {'errors': ['Failed to fetch metadata', ...]}
        }
    },
    'comment': 'cloud-init on instance myvm completed with errors: [...]'
}
```

## Configuration Examples

### Basic Container

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
      profiles:
        - default
      ephemeral: false
```

### Virtual Machine

```yaml
incus:
  instances:
    ubuntu-vm:
      instance_type: virtual-machine
      source:
        type: image
        alias: ubuntu/22.04/cloud
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        security.secureboot: false
      profiles:
        - default
        - vm-profile
      ephemeral: false
      started: true
      wait_is_ready: true     # Wait for incus-agent to be ready
      ready_timeout: 600       # Wait up to 10 minutes
```

### Virtual Machine with Cloud-Init

```yaml
incus:
  instances:
    ubuntu-cloud-vm:
      instance_type: virtual-machine
      source:
        type: image
        alias: ubuntu/22.04/cloud
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        cloud-init.user-data: |
          #cloud-config
          packages:
            - nginx
            - postgresql
          runcmd:
            - systemctl enable nginx
            - systemctl start nginx
      profiles:
        - default
      started: true
      wait_is_ready: true
      ready_timeout: 600

# In your SLS file, ensure cloud-init completes:
ubuntu-cloud-vm-initialized:
  incus.instance_initialized:
    - name: ubuntu-cloud-vm
    - timeout: 900              # cloud-init may take longer
    - check_interval: 10
    - require:
      - incus: ubuntu-cloud-vm
```

### Multi-Tier Application

```yaml
incus:
  instances:
    # Frontend
    frontend-01:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
        boot.autostart: "true"
        boot.autostart.priority: "10"
      profiles:
        - default
        - webserver
      devices:
        eth0:
          type: nic
          network: frontend-net

    # Backend
    backend-01:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        boot.autostart: "true"
        boot.autostart.priority: "20"
      profiles:
        - default
        - app-server
      devices:
        eth0:
          type: nic
          network: backend-net

    # Database
    database-01:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "8"
        limits.memory: 16GiB
        boot.autostart: "true"
        boot.autostart.priority: "30"
        boot.autostart.delay: "10"
      profiles:
        - default
        - database
      devices:
        eth0:
          type: nic
          network: backend-net
        data:
          type: disk
          pool: default
          source: database-data
          path: /var/lib/postgresql
```

### Development Environment

```yaml
incus:
  instances:
    dev-python:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 4GiB
        security.nesting: "true"
      profiles:
        - default
        - development
      devices:
        home:
          type: disk
          source: /home/developer
          path: /home/developer

    dev-nodejs:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 4GiB
        security.nesting: "true"
      profiles:
        - default
        - development
```

### CI/CD Runners

```yaml
incus:
  instances:
    ci-runner-01:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        security.nesting: "true"
        linux.kernel_modules: overlay,br_netfilter
      profiles:
        - default
        - ci-runner
      ephemeral: false

    ci-runner-02:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        security.nesting: "true"
        linux.kernel_modules: overlay,br_netfilter
      profiles:
        - default
        - ci-runner
      ephemeral: false
```

### Ephemeral Testing Instance

```yaml
incus:
  instances:
    test-container:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "1"
        limits.memory: 1GiB
      profiles:
        - default
      ephemeral: true  # Deleted when stopped
```

### Privileged Container (Docker Host)

```yaml
incus:
  instances:
    docker-host:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        security.privileged: "true"
        security.nesting: "true"
        linux.kernel_modules: overlay,br_netfilter,nf_nat,xt_conntrack
      profiles:
        - default
      devices:
        kmsg:
          type: unix-char
          source: /dev/kmsg
          path: /dev/kmsg
```

### GPU Workstation

```yaml
incus:
  instances:
    ml-workstation:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "16"
        limits.memory: 32GiB
        nvidia.runtime: "true"
      profiles:
        - default
        - gpu
      devices:
        gpu:
          type: gpu
          gputype: physical
          pci: "0000:01:00.0"
```

### Multi-Network Instance

```yaml
incus:
  instances:
    router-instance:
      instance_type: container
      source:
        type: image
        alias: alpine/3.18
      config:
        limits.cpu: "2"
        limits.memory: 1GiB
        security.nesting: "true"
      profiles:
        - default
      devices:
        eth0:
          type: nic
          network: external-net
          name: eth0
        eth1:
          type: nic
          network: internal-net
          name: eth1
        eth2:
          type: nic
          network: dmz-net
          name: eth2
```

### Instance with Custom Devices

```yaml
incus:
  instances:
    custom-container:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 4GiB
      profiles:
        - default
      devices:
        # Network device
        eth0:
          type: nic
          nictype: bridged
          parent: lxdbr0
          hwaddr: "00:16:3e:aa:bb:cc"
        # Disk device
        data:
          type: disk
          pool: default
          source: app-data
          path: /opt/data
        # USB device
        usb-device:
          type: usb
          vendorid: "046d"
          productid: "c52b"
        # Proxy device (port forwarding)
        web-proxy:
          type: proxy
          listen: tcp:0.0.0.0:8080
          connect: tcp:127.0.0.1:80
          bind: host
```

## Best Practices

### Resource Limits

Always set resource limits to prevent resource exhaustion:

```yaml
config:
  limits.cpu: "2"              # 2 CPU cores
  limits.memory: 2GiB          # 2GB RAM
  limits.processes: "1000"     # Max 1000 processes
```

CPU can also be specified as a percentage:
```yaml
config:
  limits.cpu: "50%"            # 50% of one core
  limits.cpu.priority: "10"    # Higher priority
```

### Auto-Start Configuration

For production services, enable auto-start:

```yaml
config:
  boot.autostart: "true"
  boot.autostart.delay: "0"       # Delay in seconds
  boot.autostart.priority: "10"   # Higher priority starts first
  boot.host_shutdown_timeout: "60" # Graceful shutdown timeout
```

### Waiting for Instance Readiness

When working with virtual machines, it's important to wait for the incus-agent to become fully operational before executing subsequent states. This is especially critical for VMs that take time to boot:

```yaml
incus:
  instances:
    my-vm:
      instance_type: virtual-machine
      source:
        type: image
        alias: ubuntu/22.04/cloud
      config:
        limits.cpu: "2"
        limits.memory: 4GiB
      started: true
      wait_is_ready: true      # Wait for agent to respond
      ready_timeout: 300       # Timeout in seconds (default: 300)
```

**When to use `wait_is_ready`:**
- **Virtual Machines**: Always recommended, as VMs need time to boot and start the agent
- **Containers**: Usually not needed, as containers start quickly
- **Automation**: When subsequent Salt states depend on the instance being fully operational
- **Cloud-init**: When the instance uses cloud-init and needs time to complete initialization

**Timeout recommendations:**
- **Fast VMs**: 300 seconds (5 minutes) - default
- **Slow VMs or cloud-init**: 600-900 seconds (10-15 minutes)
- **Containers**: 60-120 seconds (1-2 minutes) if needed

### Cloud-Init Initialization

When using cloud-init with your instances, especially VMs, it's important to wait for cloud-init to complete before running dependent states. The `instance_initialized` state provides this functionality:

```yaml
# Create VM with cloud-init configuration
app-vm:
  incus.instance_present:
    - source:
        type: image
        alias: ubuntu/22.04/cloud
    - instance_type: virtual-machine
    - config:
        limits.cpu: "2"
        limits.memory: 4GiB
        cloud-init.user-data: |
          #cloud-config
          packages:
            - docker.io
            - nginx
    - started: true

# Wait for cloud-init to complete
app-vm-initialized:
  incus.instance_initialized:
    - name: app-vm
    - timeout: 900          # Allow time for package installation
    - check_interval: 10
    - require:
      - incus: app-vm

# Run configuration only after cloud-init completes
configure-app:
  cmd.run:
    - name: incus exec app-vm -- /opt/configure-app.sh
    - require:
      - incus: app-vm-initialized
```

**Benefits:**
- **Error Detection**: Catches cloud-init failures early in the deployment process
- **Coordination**: Ensures dependent states run only after initialization is complete
- **Idempotency**: Can be safely run multiple times
- **Skipping**: Automatically skips if cloud-init is not installed

**Best practices for cloud-init with instances:**
1. **Set appropriate timeout**: Cloud-init with package installation may take 10-15 minutes
2. **Use with VMs**: Especially important for VMs that use cloud images
3. **Chain dependencies**: Use `require` to ensure proper order of operations
4. **Handle errors**: Check state results and logs if initialization fails

### Naming Conventions

Use descriptive, consistent names:

**Environment-based:**
```
prod-web-01
prod-web-02
dev-app-01
staging-db-01
```

**Role-based:**
```
web-frontend-01
api-backend-01
database-master
cache-redis-01
```

**Application-based:**
```
wordpress-web
wordpress-db
nextcloud-app
gitea-server
```

### Security

1. **Avoid Privileged Containers** unless necessary
2. **Disable Nesting** if not needed
3. **Use Security Profiles**:
   ```yaml
   config:
     security.privileged: "false"
     security.nesting: "false"
     security.idmap.isolated: "true"
   ```

4. **Limit Kernel Modules**:
   ```yaml
   config:
     linux.kernel_modules: overlay  # Only what's needed
   ```

### Snapshots

Enable automatic snapshots for important instances:

```yaml
config:
  snapshots.schedule: "@daily"      # Daily snapshots
  snapshots.expiry: "7d"            # Keep for 7 days
  snapshots.pattern: "auto-%Y%m%d" # Naming pattern
```

### Monitoring

Monitor instance resource usage:

```bash
# CPU and memory usage
incus info <instance>

# Resource consumption
incus list --format csv -c ns4mMu

# Real-time monitoring
watch -n 2 incus list
```

## Troubleshooting

### Instance Won't Start

**Problem**: Instance fails to start

**Solutions**:
1. Check instance logs:
   ```bash
   incus info <instance> --show-log
   incus console <instance> --show-log
   ```

2. Verify image exists:
   ```bash
   incus image list
   ```

3. Check storage pool:
   ```bash
   incus storage info <pool>
   ```

4. Verify network:
   ```bash
   incus network info <network>
   ```

### Out of Memory

**Problem**: Instance running out of memory

**Solutions**:
1. Increase memory limit:
   ```yaml
   config:
     limits.memory: 4GiB  # Increase from 2GiB
   ```

2. Check actual usage:
   ```bash
   incus exec <instance> -- free -h
   ```

3. Review running processes:
   ```bash
   incus exec <instance> -- ps aux --sort=-%mem | head
   ```

### Cloud-Init Failures

**Problem**: `instance_initialized` state fails or times out

**Solutions**:

1. Check cloud-init status manually:
   ```bash
   incus exec <instance> -- cloud-init status
   incus exec <instance> -- cloud-init status --long
   ```

2. View cloud-init logs:
   ```bash
   incus exec <instance> -- cat /var/log/cloud-init.log
   incus exec <instance> -- cat /var/log/cloud-init-output.log
   ```

3. Check for specific errors:
   ```bash
   incus exec <instance> -- journalctl -u cloud-init
   incus exec <instance> -- cloud-init analyze show
   ```

4. Verify cloud-init configuration:
   ```bash
   incus exec <instance> -- cloud-init schema --system
   ```

5. Increase timeout if cloud-init takes longer than expected:
   ```yaml
   myvm-initialized:
     incus.instance_initialized:
       - name: myvm
       - timeout: 1200  # Increase to 20 minutes
   ```

6. If cloud-init is not needed, remove it or disable it:
   ```yaml
   config:
     cloud-init.user-data: |
       #cloud-config
       # Disable cloud-init after first run
       bootcmd:
         - cloud-init-per once disable-cloudinit touch /etc/cloud/cloud-init.disabled
   ```

**Common cloud-init errors:**
- **Metadata service unavailable**: Check network connectivity
- **Package installation failures**: Check apt/yum repositories
- **Script execution errors**: Review cloud-init logs for command failures
- **Timeout waiting for network**: Verify network configuration

### Network Connectivity Issues

**Problem**: Instance cannot reach network

**Solutions**:
1. Check network configuration:
   ```bash
   incus network show <network>
   ```

2. Verify device attachment:
   ```bash
   incus config device show <instance>
   ```

3. Test from inside instance:
   ```bash
   incus exec <instance> -- ping 8.8.8.8
   incus exec <instance> -- ip addr
   ```

### Storage Issues

**Problem**: Storage errors or disk full

**Solutions**:
1. Check storage pool:
   ```bash
   incus storage info <pool>
   ```

2. Check instance disk usage:
   ```bash
   incus exec <instance> -- df -h
   ```

3. Increase disk size:
   ```yaml
   devices:
     root:
       type: disk
       path: /
       pool: default
       size: 20GB  # Increase size
   ```

### Migration Failures

**Problem**: Cannot migrate instance

**Solutions**:
1. Ensure shared storage:
   ```yaml
   devices:
     root:
       pool: ceph-pool  # Must be shared storage
   ```

2. Enable stateful migration:
   ```yaml
   config:
     migration.stateful: "true"
   ```

3. Check network connectivity between nodes

## Related Documentation

- [profile.md](profile.md) - Profile configuration
- [storages.md](storages.md) - Storage management
- [networks.md](networks.md) - Network configuration
- [instances_snapshots.md](instances_snapshots.md) - Snapshot management
- [Incus Instances Documentation](https://linuxcontainers.org/incus/docs/main/instances/)

## See Also

- Pillar example: `pillars.example/instances.sls`
- State module: `_states/incus.py`
  - Instance states: lines 115-520
  - Cloud-init state: `instance_initialized` function (lines 4217-4341)
- Execution module: `_modules/incus.py`
  - Cloud-init functions: lines 4001-4221
- Instances state: `instances.sls`
