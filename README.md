<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://cdn.jsdelivr.net/gh/SomeBlackMagic/salt-incus-formula@master/docs/incus-logo.png" width="350" alt="Incus Salt Logo">
  <img src="https://cdn.jsdelivr.net/gh/SomeBlackMagic/salt-incus-formula@master/docs/incus-logo-black.png" width="350" alt="Incus Salt Logo">
</picture>


Full-featured Salt formula for managing Incus infrastructure via REST API.

## Features

- 🚀 **Installation Management**: Automatic installation of Incus from official repositories
- 🖼️ **Images**: Import and manage container/VM images
- 📦 **Instances**: Create and configure containers and virtual machines
- 🗄️ **Storage**: Manage storage pools and volumes
- 🌐 **Networks**: Configure networks and network bridges
- 👤 **Profiles**: Configure profiles with devices and settings
- ⚙️ **Settings**: Manage Incus server configuration
- 📸 **Snapshots**: Create and manage instance snapshots

## Installation

### 1. Add Formula to Salt

```bash
# Clone formula to Salt directory
cd /srv/salt
git clone <repository-url> incus

# Or via symlink
ln -s /path/to/incus /srv/salt/incus
```

### 2. Configure Salt Master

Add module paths to `/etc/salt/master`:

```yaml
file_roots:
  base:
    - /srv/salt

module_dirs:
  - /srv/salt/incus/_modules

states_dirs:
  - /srv/salt/incus/_states
```

Restart Salt Master:

```bash
systemctl restart salt-master
```

### 3. Sync Modules to Minions

```bash
salt '*' saltutil.sync_all
```

## Quick Start

### 1. Basic Incus Installation

Create pillar file `/srv/pillar/incus.sls`:

```yaml
incus:
  # Basic installation
  install: true

  # Server settings
  settings:
    core.https_address: '[::]:8443'
    core.trust_password: 'secure-password'
```

Apply state:

```bash
salt 'minion-id' state.apply incus
```

### 2. Import Image and Create Instance

Extend pillar:

```yaml
incus:
  # Images
  images:
    ubuntu2204:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true
      aliases:
        - ubuntu-jammy
        - ubuntu-lts

  # Instances
  instances:
    web-server:
      source:
        type: image
        alias: ubuntu2204
      config:
        limits.cpu: "2"
        limits.memory: "2GB"
      devices:
        root:
          path: /
          pool: default
          type: disk
      profiles:
        - default
```

Apply:

```bash
salt 'minion-id' state.apply incus.images
salt 'minion-id' state.apply incus.instances
```

## Usage

### Formula Structure

```
incus/
├── init.sls              # Main entry point
├── repo.sls              # Repository configuration
├── install.sls           # Package installation
├── service.sls           # Service management
├── images.sls            # Image management
├── instances.sls         # Instance management
├── storage.sls           # Storage management
├── network.sls           # Network management
├── profiles.sls          # Profile management
├── settings.sls          # Server settings
├── snapshots.sls         # Snapshot management
├── _modules/
│   └── incus.py          # Execution module (REST API)
├── _states/
│   └── incus.py          # State module
├── docs/                 # Documentation
│   ├── images.md
│   ├── instances.md
│   ├── storage.md
│   ├── network.md
│   ├── profiles.md
│   └── ...
├── pillars.example/      # Configuration examples
│   ├── images.sls
│   ├── instances.sls
│   ├── storage.sls
│   └── ...
└── tests/
    └── integration/      # Integration tests
```

### Applying States

```bash
# Full installation and configuration
salt 'minion-id' state.apply incus

# Individual components
salt 'minion-id' state.apply incus.images
salt 'minion-id' state.apply incus.instances
salt 'minion-id' state.apply incus.storage
salt 'minion-id' state.apply incus.network
salt 'minion-id' state.apply incus.profiles

# Test mode (dry-run)
salt 'minion-id' state.apply incus.images test=True
```

### Using Execution Module

```bash
# List images
salt 'minion-id' incus.image_list

# Get image information
salt 'minion-id' incus.image_get <fingerprint>

# List instances
salt 'minion-id' incus.instance_list

# Get instance state
salt 'minion-id' incus.instance_state web-server

# Start/stop instances
salt 'minion-id' incus.instance_start web-server
salt 'minion-id' incus.instance_stop web-server

# Execute command in instance
salt 'minion-id' incus.instance_exec web-server "apt update"
```

## Configuration Examples

All examples are located in the `pillars.example/` directory:

### 📁 `pillars.example/`

- **`images.sls`** - Image management examples
  - Import from LinuxContainers.org
  - Import from local files
  - Multiple aliases
  - Auto-update configurations
  - Images for production/development/CI-CD

- **`instances.sls`** - Instance creation examples
  - Containers and VMs
  - Resource configuration (CPU, RAM)
  - Devices (disks, networks)
  - Cloud-init configuration
  - Profiles and presets

- **`storage.sls`** - Storage pool examples
  - Dir, ZFS, LVM, BTRFS
  - Volumes and sizes
  - Quota configuration

- **`network.sls`** - Network examples
  - Bridge networks
  - NAT configuration
  - VLAN setup
  - IP management (DHCP/static)

- **`profiles.sls`** - Profile examples
  - Basic profiles
  - Production/Development presets
  - Devices and limits

- **`settings.sls`** - Server settings examples
  - HTTPS configuration
  - Trust password
  - Routing


### Quick Examples

#### Import Ubuntu Image

```yaml
incus:
  images:
    ubuntu2204:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true
```

#### Create Container

```yaml
incus:
  instances:
    web-app:
      type: container
      source:
        type: image
        alias: ubuntu2204
      config:
        limits.cpu: "4"
        limits.memory: "4GB"
```

#### Create Storage Pool

```yaml
incus:
  storage:
    pools:
      fast-ssd:
        driver: zfs
        source: /dev/nvme0n1
        config:
          size: 100GB
          volume.zfs.use_refquota: "true"
```

#### Create Network

```yaml
incus:
  network:
    networks:
      internal:
        type: bridge
        config:
          ipv4.address: 10.0.100.1/24
          ipv4.nat: "true"
          ipv6.address: none
```

## Documentation

Detailed documentation for each component is located in the `docs/` directory:

### 📚 Component Documentation

- **[images.md](docs/images.md)** - Complete guide for working with images
  - Import from remote sources
  - Load local files
  - Alias management
  - Properties and metadata
  - Auto-update and expires_at
  - Troubleshooting

- **[instances.md](docs/instances.md)** - Instance management
  - Containers vs VMs
  - Resource configuration
  - Devices and profiles
  - Cloud-init integration
  - Lifecycle management

- **[storages.md](docs/storages.md)** - Storage pools and volumes
  - Storage types (dir, zfs, lvm, btrfs)
  - Quota configuration
  - Volume snapshots
  - Data migration

- **[networks.md](docs/networks.md)** - Network configuration
  - Bridge networks
  - NAT and routing
  - VLAN and segmentation
  - Static IP and DHCP

- **[profiles.md](docs/profiles.md)** - Profile configuration
  - Creating profiles
  - Inheritance and overrides
  - Devices in profiles
  - Best practices

- **[settings.md](docs/settings.md)** - Server settings
  - HTTPS and TLS
  - Authentication
  - Cluster settings
  - Performance tuning

- **[instance_snapshots.md](docs/instance_snapshots.md)** - Snapshots and backups
  - Creating snapshots
  - Restoration
  - Expiry policies
  - Automation

### Core Concepts

#### State Name Becomes Alias

**IMPORTANT**: In the `image_present` state, the `name` parameter **ALWAYS** becomes the primary alias for the image in Incus:

```yaml
ubuntu2204:                      # ← This becomes the alias in Incus
  incus.image_present:
    - source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04      # ← Used only for import
```

Additional aliases are added via the `aliases` parameter:

```yaml
ubuntu2204:                      # ← PRIMARY alias
  incus.image_present:
    - aliases:                   # ← ADDITIONAL aliases
        - ubuntu-jammy
        - ubuntu-lts
```

Result: The image will have 3 aliases: `ubuntu2204`, `ubuntu-jammy`, `ubuntu-lts`

#### Idempotency

All states are idempotent - repeated application does not create changes if the configuration already matches:

```bash
# First run - creates resources
salt 'minion' state.apply incus.images
# Changes: created image ubuntu2204

# Second run - no changes
salt 'minion' state.apply incus.images
# Changes: None (already present)
```

## Development and Testing

### Running Tests

```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run integration tests
cd tests/integration
pytest

# Run specific test
pytest test_images.py::test_images[image_001]

# With verbose output
pytest -v -s
```

### Test Structure

```
tests/
└── integration/
    ├── conftest.py           # Fixtures and utilities
    ├── data/
    │   ├── images.yml        # Test data for images
    │   ├── instances.yml     # Test data for instances
    │   └── ...
    ├── test_images.py
    ├── test_instances.py
    └── ...
```

### Adding New Tests

Create a YAML file in `tests/integration/data/`:

```yaml
cases:
  - name: my_test_case
    pillars:
      incus:
        images:
          test-image:
            source:
              server: https://images.linuxcontainers.org
              alias: alpine/edge
              protocol: simplestreams
    command: state.apply images
    expected:
      salt_output_contains:
        - "test-image"
        - "changes"
    cleanup:
      - incus image delete test-image
```

## ToDo List

- **[clusters.md](docs/clusters.md)** - Cluster configuration
  - Cluster initialization
  - Adding nodes
  - Resource distribution
  - High availability

## Troubleshooting

### Issue: Images Are Constantly Being Reimported

**Cause**: State cannot find the existing image by alias.

**Solution**: Ensure the image has an alias matching the `name` in state:

```bash
# Check aliases
incus image alias list

# Add alias manually if needed
incus image alias create ubuntu2204 <fingerprint>
```

### Issue: Changes Shown on Every Run

**Cause**: Configuration in a pillar doesn't match the current state.

**Solution**: Check current configuration and sync pillar:

```bash
# For images
incus image show <fingerprint>

# For instances
incus config show instance-name
```

### Issue: API Connection Errors

**Cause**: Incus server is unavailable or incorrect configuration.

**Solution**:

```bash
# Check service status
systemctl status incus

# Check API availability
curl -k https://localhost:8443

# Check settings in pillar
salt 'minion' pillar.get incus:api_endpoint
```

## Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/incus-formula/issues)
- **Documentation**: See `docs/` directory
- **Examples**: See `pillars.example/` directory

## License

The GNU General Public License v3.0

## Authors

[Specify authors]

## Links

- [Incus Documentation](https://linuxcontainers.org/incus/docs/main/)
- [Incus REST API](https://linuxcontainers.org/incus/docs/main/rest-api/)
- [Salt States Documentation](https://docs.saltproject.io/en/latest/ref/states/all/)
 