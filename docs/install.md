# Incus Installation State

## Description

State `incus.install` manages installation and basic initialization of Incus.

## Functionality

### Main Features

1. **Zabbly Repository Setup** (if `incus.repo.enable: true`):
   - Creates `/etc/apt/keyrings`
   - Downloads repository key
   - Creates DEB822 source file for APT (Debian/Ubuntu)
   - Configures yum/dnf repository (RedHat family)

2. **Incus Package Installation**:
   - Installs package from configured repositories
   - Supports optional pinned version (`incus.version`)

3. **Incus Service Management**:
   - Ensures service is enabled and running
   - Runs `incus admin init --minimal` once on fresh setup

4. **Additional Dependencies**:
   - Installs packages from `incus.pkg.deps`

## Key Parameters

```yaml
incus:
  enable: true

  repo:
    enable: true
    channel: stable
    debian:
      architecture: amd64
      key_url: https://pkgs.zabbly.com/key.asc

  pkg:
    name: incus
    deps:
      - qemu-kvm
      - lxcfs

  service:
    name: incus
    enable: true
```

## Execution Order

1. Configure repository (optional)
2. Install `incus`
3. Start/enable service
4. Run one-time minimal init
5. Install additional dependencies
