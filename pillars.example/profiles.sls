# =============================================================================
# Incus Profiles Pillar Example
# =============================================================================
# This file demonstrates all available options for managing Incus profiles
# through Salt states.
#
# Profiles are templates that define configuration and devices for instances.
# They can be applied to containers and VMs at creation time.
#
# Usage:
#   1. Copy this file to your pillar directory (e.g., pillar/incus_profiles.sls)
#   2. Customize the profiles according to your needs
#   3. Reference in top.sls or include in your pillar data
#   4. Apply with: salt '*' state.apply incus.profiles
# =============================================================================

incus:
  profiles:
    # =========================================================================
    # Basic Profile Examples
    # =========================================================================

    # Minimal profile with resource limits
    minimal:
      ensure: present
      description: Minimal resources profile for testing
      config:
        limits.cpu: "1"
        limits.memory: 512MB

    # Standard profile with common settings
    standard:
      ensure: present
      description: Standard profile for general-purpose containers
      config:
        limits.cpu: "2"
        limits.memory: 2GB
        limits.processes: "500"

    # High-performance profile
    performance:
      ensure: present
      description: High-performance profile for demanding workloads
      config:
        limits.cpu: "8"
        limits.memory: 16GB
        limits.processes: "2000"

    # =========================================================================
    # Profiles with Devices
    # =========================================================================

    # Web server profile with network device
    webserver:
      ensure: present
      description: Web server profile with network configuration
      config:
        limits.cpu: "4"
        limits.memory: 4GB
        security.nesting: "true"
        boot.autostart: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        root:
          path: /
          pool: default
          type: disk

    # Database server profile with additional storage
    database:
      ensure: present
      description: Database server profile with data volume
      config:
        limits.cpu: "8"
        limits.memory: 16GB
        limits.processes: "5000"
        boot.autostart: "true"
        boot.autostart.delay: "5"
        boot.autostart.priority: "10"
      devices:
        eth0:
          name: eth0
          type: nic
          network: mybr0
        root:
          path: /
          pool: default
          type: disk
        data:
          path: /var/lib/mysql
          pool: default
          source: mysql-data
          type: disk

    # =========================================================================
    # Security Profiles
    # =========================================================================

    # Privileged container profile
    privileged:
      ensure: present
      description: Privileged container with full host access
      config:
        security.privileged: "true"
        security.nesting: "true"
        linux.kernel_modules: "ip_tables,ip6_tables,netlink_diag,nf_nat,overlay"
      devices:
        kmsg:
          path: /dev/kmsg
          source: /dev/kmsg
          type: unix-char

    # Nested virtualization profile
    nested:
      ensure: present
      description: Profile for running Docker/LXD inside containers
      config:
        security.nesting: "true"
        security.privileged: "false"
        linux.kernel_modules: "overlay,br_netfilter,ip_tables,ip6_tables"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0

    # Isolated security profile
    isolated:
      ensure: present
      description: Maximum isolation security profile
      config:
        security.privileged: "false"
        security.nesting: "false"
        security.idmap.isolated: "true"
        security.syscalls.deny_default: "true"
        security.syscalls.deny_compat: "true"

    # =========================================================================
    # Development Profiles
    # =========================================================================

    # Development environment
    development:
      ensure: present
      description: Development environment with GPU passthrough
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.nesting: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        gpu:
          type: gpu
          gputype: physical
          pci: "0000:01:00.0"
        home:
          path: /home/developer
          source: /home/developer
          type: disk

    # CI/CD runner profile
    ci-runner:
      ensure: present
      description: CI/CD runner with Docker support
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.nesting: "true"
        linux.kernel_modules: "overlay,br_netfilter,nf_nat,xt_conntrack"
        raw.lxc: |
          lxc.apparmor.profile=unconfined
          lxc.mount.auto=proc:rw sys:rw cgroup:rw
          lxc.cgroup.devices.allow=a

    # =========================================================================
    # Network-Specific Profiles
    # =========================================================================

    # Multiple network interfaces
    multi-nic:
      ensure: present
      description: Profile with multiple network interfaces
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

    # NAT gateway profile
    nat-gateway:
      ensure: present
      description: NAT gateway with IP forwarding
      config:
        limits.cpu: "2"
        limits.memory: 1GB
        security.nesting: "true"
        raw.lxc: |
          lxc.mount.entry=/proc/sys/net proc/sys/net none bind,create=dir 0 0
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
          parent: external-br

    # =========================================================================
    # Storage-Specific Profiles
    # =========================================================================

    # Large root disk
    large-disk:
      ensure: present
      description: Profile with large root disk
      config:
        limits.cpu: "2"
        limits.memory: 4GB
      devices:
        root:
          path: /
          pool: default
          size: 100GB
          type: disk

    # Shared storage profile
    shared-storage:
      ensure: present
      description: Profile with shared storage volumes
      config:
        limits.cpu: "2"
        limits.memory: 2GB
      devices:
        shared-data:
          path: /mnt/shared
          pool: default
          source: shared-volume
          type: disk
        backup:
          path: /mnt/backup
          pool: backup-pool
          source: backup-volume
          type: disk

    # =========================================================================
    # Special Purpose Profiles
    # =========================================================================

    # GPU workstation
    gpu-workstation:
      ensure: present
      description: Workstation with GPU passthrough and USB devices
      config:
        limits.cpu: "8"
        limits.memory: 16GB
        security.nesting: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        gpu:
          type: gpu
          gputype: physical
          id: "0"
        usb-keyboard:
          type: usb
          vendorid: "046d"
          productid: "c52b"
        audio:
          type: proxy
          bind: container
          connect: unix:/run/user/1000/pulse/native
          listen: unix:/tmp/.pulse-native
          security.uid: "1000"
          security.gid: "1000"

    # Router/Firewall profile
    router:
      ensure: present
      description: Router/Firewall with multiple interfaces
      config:
        limits.cpu: "2"
        limits.memory: 2GB
        security.nesting: "true"
        security.privileged: "true"
        linux.kernel_modules: "ip_tables,ip6_tables,nf_nat,xt_conntrack,iptable_nat"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: wan-br
        eth1:
          name: eth1
          type: nic
          nictype: bridged
          parent: lan-br

    # =========================================================================
    # Update Config Examples
    # =========================================================================
    # Use update_config to modify existing profiles without recreating them

    # Example: Update existing profile configuration
    # webserver:
    #   ensure: present
    #   config:
    #     limits.cpu: "4"
    #     limits.memory: 4GB
    #   # Update only memory limit without changing other settings
    #   update_config:
    #     limits.memory: 8GB
    #   update_description: Updated memory allocation

    # =========================================================================
    # Profile Removal Example
    # =========================================================================

    # Remove old/unused profile
    old-profile:
      ensure: absent

    # =========================================================================
    # VM-Specific Profiles
    # =========================================================================

    # Virtual machine profile
    vm-standard:
      ensure: present
      description: Standard VM profile with UEFI and virtio
      config:
        limits.cpu: "4"
        limits.memory: 8GB
        security.secureboot: "false"
        boot.autostart: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        root:
          path: /
          pool: default
          size: 50GB
          type: disk
          boot.priority: "0"

    # High-performance VM
    vm-performance:
      ensure: present
      description: High-performance VM with TPM and GPU
      config:
        limits.cpu: "16"
        limits.memory: 32GB
        security.secureboot: "false"
        migration.stateful: "true"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: lxdbr0
        root:
          path: /
          pool: nvme-pool
          size: 200GB
          type: disk
        tpm:
          type: tpm
          path: /dev/tpm0
        gpu:
          type: gpu
          gputype: mdev
          mdev: "i915-GVTg_V5_4"

    # =========================================================================
    # Complex Profiles with Multiple Features
    # =========================================================================

    # Production application server
    app-production:
      ensure: present
      description: Production application server with monitoring and backups
      config:
        # Resources
        limits.cpu: "8"
        limits.memory: 16GB
        limits.processes: "5000"
        limits.cpu.priority: "10"

        # Boot settings
        boot.autostart: "true"
        boot.autostart.delay: "10"
        boot.autostart.priority: "50"
        boot.host_shutdown_timeout: "60"

        # Security
        security.nesting: "false"
        security.privileged: "false"

        # Snapshots
        snapshots.schedule: "@daily"
        snapshots.schedule.stopped: "false"
        snapshots.pattern: "snap-%Y%m%d"
        snapshots.expiry: "7d"
      devices:
        eth0:
          name: eth0
          type: nic
          nictype: bridged
          parent: prod-br
          hwaddr: "00:16:3e:aa:bb:cc"
        root:
          path: /
          pool: ssd-pool
          size: 100GB
          type: disk
        app-data:
          path: /opt/app/data
          pool: ssd-pool
          source: app-data-volume
          type: disk
        logs:
          path: /var/log
          pool: hdd-pool
          source: app-logs-volume
          type: disk

# =============================================================================
# Advanced Configuration Notes
# =============================================================================
#
# Resource Limits:
#   - limits.cpu: Number of CPU cores ("2", "4", "8") or percentage ("50%")
#   - limits.memory: Memory limit (512MB, 2GB, 16GB)
#   - limits.processes: Maximum number of processes
#   - limits.cpu.priority: CPU scheduling priority (0-10)
#
# Security Options:
#   - security.privileged: Run as privileged container (true/false)
#   - security.nesting: Allow nested containers (true/false)
#   - security.idmap.isolated: Use isolated ID mapping
#   - security.syscalls.deny: Deny specific syscalls
#
# Boot Options:
#   - boot.autostart: Auto-start on host boot (true/false)
#   - boot.autostart.delay: Delay in seconds before starting
#   - boot.autostart.priority: Start order priority
#   - boot.host_shutdown_timeout: Timeout for graceful shutdown
#
# Network Devices:
#   - type: nic
#   - nictype: bridged, macvlan, physical, routed, p2p
#   - parent: Parent network or interface
#   - network: Managed network name
#   - hwaddr: MAC address
#   - mtu: MTU size
#
# Disk Devices:
#   - type: disk
#   - path: Mount path in container
#   - source: Volume name or host path
#   - pool: Storage pool name
#   - size: Disk size (only for new volumes)
#
# GPU Devices:
#   - type: gpu
#   - gputype: physical, mdev, mig, sriov
#   - id: GPU device ID
#   - pci: PCI address
#
# USB Devices:
#   - type: usb
#   - vendorid: USB vendor ID
#   - productid: USB product ID
#
# Proxy Devices:
#   - type: proxy
#   - listen: Listen address
#   - connect: Connect address
#   - bind: container or host
#
# =============================================================================
