# Example configuration for Incus installation
# Copy the required parameters to your pillar file

incus:
  # Package version (optional)
  # If not specified, the latest available version will be installed
  # version: "6.0.1"

  # Repository settings
  repo:
    # Enable Zabbly repository configuration
    # If false, the package will be installed from system default repositories
    enable: true

    # Repository channel: stable, edge
    channel: stable

    # Settings for Debian/Ubuntu
    debian:
      # Architecture: amd64, arm64
      architecture: amd64

      # Repository GPG key URL
      key_url: 'https://pkgs.zabbly.com/key.asc'

      # Additional parameters (for reference, used automatically)
      # name: 'deb [arch=amd64] https://pkgs.zabbly.com/incus/stable bookworm main'
      # human_name: 'Zabbly Incus repository'
      # uri: 'https://pkgs.zabbly.com/incus/stable'
      # dist: 'bookworm'  # determined automatically from grains.oscodename
      # comps:
      #   - main

    # Settings for RedHat/CentOS/Fedora
    redhat:
      name: 'incus-stable'
      baseurl: 'https://pkgs.zabbly.com/incus/stable/rpm/$releasever/$basearch'
      gpgkey: 'https://pkgs.zabbly.com/key.asc'
      enabled: 1
      gpgcheck: 1

  # Package settings
  pkg:
    # Main package name
    name: incus

    # List of additional dependencies
    # Adapt to your system and requirements
    deps:
      - qemu-kvm          # For virtual machine support
      - lxcfs             # For LXC containers
      # - zfsutils-linux  # For using ZFS (optional)
      # - btrfs-progs     # For using Btrfs (optional)
      # - ovmf            # For UEFI virtual machines (optional)

# ============================================================================
# Configuration examples
# ============================================================================

# --- Example 1: Minimal installation from system repositories ---
# incus:
#   enable: true
#   repo:
#     enable: false
#   pkg:
#     deps:
#       - lxcfs

# --- Example 2: Install specific version from Zabbly stable ---
# incus:
#   enable: true
#   version: "6.0.1"
#   repo:
#     enable: true
#     channel: stable
#     debian:
#       architecture: amd64
#       key_url: https://pkgs.zabbly.com/key.asc
#   pkg:
#     deps:
#       - qemu-kvm
#       - lxcfs
#       - zfsutils-linux

# --- Example 3: Install edge version for testing ---
# incus:
#   enable: true
#   repo:
#     enable: true
#     channel: edge
#     debian:
#       architecture: amd64
#       key_url: https://pkgs.zabbly.com/key.asc
#   pkg:
#     deps:
#       - qemu-kvm
#       - lxcfs

# --- Example 4: Installation on ARM architecture ---
# incus:
#   enable: true
#   repo:
#     enable: true
#     channel: stable
#     debian:
#       architecture: arm64
#       key_url: https://pkgs.zabbly.com/key.asc
#   pkg:
#     deps:
#       - qemu-system-arm
#       - lxcfs

# --- Example 5: Maximum installation with all components ---
# incus:
#   enable: true
#   repo:
#     enable: true
#     channel: stable
#     debian:
#       architecture: amd64
#       key_url: https://pkgs.zabbly.com/key.asc
#   pkg:
#     deps:
#       - qemu-kvm
#       - qemu-utils
#       - lxcfs
#       - zfsutils-linux
#       - btrfs-progs
#       - ovmf
#       - uidmap
#       - fuse3
