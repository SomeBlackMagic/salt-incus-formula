# ======================================================================
# Incus Instances Configuration Example
# ======================================================================
# This pillar file demonstrates instance (containers and VMs) management.
#
# Instances are the main workload units in Incus. They can be:
# - Containers (system containers with shared kernel)
# - Virtual Machines (full VMs with own kernel)
#
# Usage:
#   1. Copy this file to your pillar directory
#   2. Customize instances according to your needs
#   3. Include in your top.sls or specific minion pillar
#   4. Apply with: salt '*' state.apply incus.instances
# ======================================================================

incus:
  # ====================================================================
  # Instances
  # ====================================================================
  instances:
    # ------------------------------------------------------------------
    # Basic Container Examples
    # ------------------------------------------------------------------
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

    app-container:
      instance_type: container
      source:
        type: image
        alias: debian/12
      config:
        limits.cpu: "4"
        limits.memory: 4GiB
        boot.autostart: "true"
      profiles:
        - default
      ephemeral: false

    # ------------------------------------------------------------------
    # Virtual Machine Examples
    # ------------------------------------------------------------------
    windows-vm:
      instance_type: virtual-machine
      source:
        type: image
        alias: windows/11
      config:
        limits.cpu: "4"
        limits.memory: 8GiB
        security.secureboot: "false"
      profiles:
        - default
        - vm-profile
      ephemeral: false

    ubuntu-vm:
      instance_type: virtual-machine
      source:
        type: image
        alias: ubuntu/22.04/cloud
      config:
        limits.cpu: "2"
        limits.memory: 4GiB
      profiles:
        - default
      ephemeral: false

# ======================================================================
# Instance Management Patterns
# ======================================================================

# Pattern 1: Multi-Tier Application
incus_web_application:
  instances:
    # Frontend tier
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
      ephemeral: false

    frontend-02:
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
      ephemeral: false

    # Backend tier
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
      ephemeral: false

    # Database tier
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
      ephemeral: false

# Pattern 2: Development Environments
incus_dev_environments:
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
      ephemeral: false

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
      ephemeral: false

    dev-go:
      instance_type: container
      source:
        type: image
        alias: alpine/3.18
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
      profiles:
        - default
        - development
      ephemeral: false

# Pattern 3: CI/CD Runners
incus_ci_runners:
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

# Pattern 4: Ephemeral Testing Instances
incus_ephemeral_test:
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

    integration-test:
      instance_type: container
      source:
        type: image
        alias: debian/12
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
      profiles:
        - default
      ephemeral: true

# Pattern 5: Privileged Containers
incus_privileged_containers:
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
      ephemeral: false

# Pattern 6: GPU Workstation
incus_gpu_workstation:
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
      ephemeral: false

# Pattern 7: Multi-Network Instance
incus_multi_network:
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
      ephemeral: false

# Pattern 8: Instance with Custom Devices
incus_custom_devices:
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
          hwaddr: "00:16:3e:xx:xx:xx"
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
      ephemeral: false

# Pattern 9: Cluster-Aware Instances
incus_cluster_instances:
  instances:
    # Instance on specific cluster member
    web-on-node1:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
      profiles:
        - default
      # Note: Use cluster targeting in Salt to place on specific node
      ephemeral: false

    # Highly available instance (can migrate)
    ha-database:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "8"
        limits.memory: 16GiB
        migration.stateful: "true"
      profiles:
        - default
      devices:
        data:
          type: disk
          pool: ceph-pool  # Shared storage required for HA
          source: ha-database-data
          path: /var/lib/mysql
      ephemeral: false

# ======================================================================
# Instance State Management
# ======================================================================

# Ensure instances are running
incus_running_instances:
  instances:
    production-web:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "4"
        limits.memory: 4GiB
        boot.autostart: "true"
      profiles:
        - default
      state: running  # Ensure instance is running

# Ensure instances are stopped
incus_stopped_instances:
  instances:
    maintenance-container:
      instance_type: container
      source:
        type: image
        alias: debian/12
      config:
        limits.cpu: "1"
        limits.memory: 1GiB
      profiles:
        - default
      state: stopped  # Ensure instance is stopped

# Remove instances
incus_absent_instances:
  instances:
    old-container:
      ensure: absent
      force: true  # Force removal even if running

# ======================================================================
# Important Notes
# ======================================================================
#
# Instance Types:
#   - container: System container with shared kernel
#   - virtual-machine: Full VM with own kernel
#
# Source Types:
#   - image: Create from image (most common)
#   - copy: Copy from another instance
#   - migration: Migrate from another server
#   - none: Empty instance (manual setup)
#
# Configuration Options:
#   - limits.cpu: CPU cores ("2", "4") or percentage ("50%")
#   - limits.memory: Memory limit (1GiB, 2GiB, etc.)
#   - limits.processes: Max number of processes
#   - boot.autostart: Auto-start on host boot
#   - boot.autostart.delay: Delay before starting
#   - boot.autostart.priority: Start order
#   - security.nesting: Allow nested containers
#   - security.privileged: Run as privileged
#   - migration.stateful: Enable stateful migration
#
# Profiles:
#   - Applied to instance at creation
#   - Can stack multiple profiles
#   - Profile changes affect existing instances
#   - Order matters (later profiles override earlier)
#
# Devices:
#   - nic: Network interfaces
#   - disk: Storage volumes
#   - gpu: GPU passthrough
#   - usb: USB devices
#   - proxy: Port forwarding
#   - unix-char/unix-block: Device passthrough
#
# Ephemeral Instances:
#   - Deleted automatically when stopped
#   - Useful for testing/CI/CD
#   - Cannot be restarted after stopping
#   - No snapshots or backups
#
# Best Practices:
#   - Use profiles for common configuration
#   - Set resource limits appropriately
#   - Enable auto-start for critical services
#   - Use descriptive instance names
#   - Document instance purposes
#   - Regular snapshots before changes
#   - Monitor resource usage
#   - Plan for high availability
#
# ======================================================================
