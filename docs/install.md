# Incus Installation State

## Description

State `incus.install` manages the installation of the Incus package and its dependencies at the operating system level.

## Functionality

### Main Features

1. **Zabbly Repository Setup** (if `incus.repo.enable: true`):
   - Creating directory for APT keys `/etc/apt/keyrings`
   - Downloading a repository GPG key
   - Creating a source file for a repository in DEB822 format

2. **Incus Package Installation**:
   - Support for installing a specific version (optional)
   - Automatic package index update before installation

3. **Dependencies Installation**:
   - Installing additional packages required for Incus operation
   - Configured via pillar `incus.pkg.deps`

## File Structure

### states/incus/install.sls

```
states/incus/install.sls:8-11  - Variable definitions (codename, arch, channel, version)
states/incus/install.sls:13    - Check installation enable flag
states/incus/install.sls:14-46 - Repository setup (optional)
states/incus/install.sls:49-60 - Install incus package
states/incus/install.sls:63-67 - Install additional dependencies
```

### Repository Parameters

```yaml
incus:
  repo:
    enable: true              # Enable repository setup
    channel: stable           # Repository channel: stable, edge
    debian:
      architecture: amd64     # Architecture: amd64, arm64
      key_url: https://pkgs.zabbly.com/key.asc  # GPG key URL
```

### Package Parameters

```yaml
incus:
  version: "6.0.1"           # Package version (optional)
  pkg:
    deps:                     # Dependencies list
      - qemu-kvm
      - lxcfs
```

## Generated Resources

### With Enabled Repository

1. **Directory**: `/etc/apt/keyrings` (mode 0755)
2. **Key File**: `/etc/apt/keyrings/zabbly.asc` (mode 0644)
3. **Sources File**: `/etc/apt/sources.list.d/zabbly-incus-{channel}.sources`

Example sources file content:
```
Enabled: yes
Types: deb
URIs: https://pkgs.zabbly.com/incus/stable
Suites: bookworm
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/zabbly.asc
```

### Installed Packages

- `incus` - main package
- Additional packages from `incus.pkg.deps` list

## Usage Examples

### Minimal Configuration

Installing Incus from system standard repositories:

```yaml
incus:
  enable: true
  repo:
    enable: false
  pkg:
    deps:
      - lxcfs
```

### Full Configuration with Zabbly Repository

```yaml
incus:
  enable: true
  version: "6.0.1"
  repo:
    enable: true
    channel: stable
    debian:
      architecture: amd64
      key_url: https://pkgs.zabbly.com/key.asc
  pkg:
    deps:
      - qemu-kvm
      - lxcfs
      - zfsutils-linux
```

### Installing Edge Version

```yaml
incus:
  enable: true
  repo:
    enable: true
    channel: edge
    debian:
      architecture: amd64
      key_url: https://pkgs.zabbly.com/key.asc
  pkg:
    deps:
      - qemu-kvm
      - lxcfs
```

## Dependencies

### Grains

- `oscodename` - used to determine distribution codename (default: bookworm)

### External Files

- `incus/map.jinja` - load configuration from pillar and defaults
- `incus/defaults.yaml` - default values

## Execution Order

1. Create a directory for keys (if the repository is enabled)
2. Download the GPG key (if the repository is enabled)
3. Create a repository sources file (if the repository is enabled)
4. Update package index and install Incus
5. Install additional dependencies

## Features

- **DEB822 Format**: Repository is configured in modern `.sources` format instead of old `.list` format
- **Index Update**: Parameter `refresh: True` is specified twice in `incus-package` (possibly redundant)
- **Signature Verification**: `skip_verify: True` disables SSL verification when downloading key
- **Channel Flexibility**: Support for different repository channels (stable, edge)

## Installation Verification

After applying state, verify installation:

```bash
# Check Incus version
incus --version

# Check repository (if enabled)
cat /etc/apt/sources.list.d/zabbly-incus-stable.sources

# Check installed packages
dpkg -l | grep incus
dpkg -l | grep -E 'qemu-kvm|lxcfs'
```

## Possible Issues

### Repository Unavailable

If `incus.repo.enable: true`, but Zabbly repository is unavailable:
- Set `incus.repo.enable: false`
- Ensure package is available in system standard repositories

### Version Conflict

When specifying a specific version via `incus.version`:
- Ensure a version is available in a selected repository channel
- Check available versions: `apt-cache madison incus`

### Missing Dependencies

Some dependencies may be missing in your distribution:
- Adapt `incus.pkg.deps` list for your system
- Virtual machines require `qemu-kvm`
- ZFS requires `zfsutils-linux`
