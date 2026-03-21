# Salt Cloud Driver for Incus

The `_clouds/incus.py` driver integrates [Incus](https://linuxcontainers.org/incus/) with
[Salt Cloud](https://docs.saltproject.io/en/latest/topics/cloud/index.html), allowing you to
provision, manage, and destroy Incus containers and virtual machines using the standard
`salt-cloud` CLI and map files.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Provider Configuration](#provider-configuration)
  - [Unix Socket (local)](#unix-socket-local)
  - [HTTPS (remote)](#https-remote)
  - [TLS Verification Options](#tls-verification-options)
- [Profile Configuration](#profile-configuration)
  - [Minimal Profile](#minimal-profile)
  - [Container with Resources](#container-with-resources)
  - [Virtual Machine](#virtual-machine)
  - [Full Profile Reference](#full-profile-reference)
- [CLI Usage](#cli-usage)
  - [Listing Resources](#listing-resources)
  - [Creating Instances](#creating-instances)
  - [Managing Instances](#managing-instances)
  - [Destroying Instances](#destroying-instances)
- [Map Files](#map-files)
- [Cloud-Init Integration](#cloud-init-integration)
- [Cluster (Multi-Node) Placement](#cluster-multi-node-placement)
- [Salt Minion Deployment](#salt-minion-deployment)
- [IP Wait Behaviour](#ip-wait-behaviour)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)

---

## Requirements

| Dependency        | Notes                                      |
|-------------------|--------------------------------------------|
| Salt >= 3006      | The `salt-cloud` command must be available |
| Incus             | Any recent stable release                  |
| Python `requests` | `pip install requests`                     |

---

## Installation

Sync the driver to the Salt master so `salt-cloud` can find it:

```bash
# Copy _clouds/incus.py to the Salt file roots
# e.g. /srv/salt/_clouds/incus.py

# Then sync cloud modules to the master
salt-run saltutil.sync_clouds
```

Alternatively, place `_clouds/incus.py` directly in Salt's extension module path
(configured via `extension_modules` in `/etc/salt/master`).

---

## Provider Configuration

Create a provider file at `/etc/salt/cloud.providers.d/incus.conf`.

Ready-to-use example files are available in:

- `docs/examples/salt-cloud/cloud.providers.local-files.conf`
- `docs/examples/salt-cloud/cloud.profiles.local-files.conf`
- `docs/examples/salt-cloud/cloud.providers.sdb.conf`
- `docs/examples/salt-cloud/cloud.profiles.sdb.conf`

### Unix Socket (local)

Connect to an Incus daemon running on the same host as the Salt master — the simplest
and most secure option.

```yaml
# /etc/salt/cloud.providers.d/incus.conf

my-incus:
  driver: incus
  connection:
    type: unix
    socket: /var/lib/incus/unix.socket   # default path, can be omitted
```

The `socket` key defaults to `/var/lib/incus/unix.socket` and can be omitted when using
the default Incus installation.

### HTTPS (remote)

Connect to a remote Incus server over HTTPS. Mutual TLS authentication is required by Incus.

```yaml
my-incus-remote:
  driver: incus
  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: true                        # verify server certificate (recommended)
```

Generate a client certificate and trust it in Incus:

```bash
# Generate client certificate and key
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-384 \
  -keyout /etc/salt/pki/incus/client.key \
  -out /etc/salt/pki/incus/client.crt \
  -nodes -days 3650 -subj "/CN=salt-cloud"

# Trust certificate on Incus server
incus config trust add-certificate /etc/salt/pki/incus/client.crt --name salt-cloud
```

### TLS Verification Options

The `connection.cert_storage.verify` key accepts three forms:

| Value             | Behaviour                                                         |
|-------------------|-------------------------------------------------------------------|
| `true`            | Verify server certificate against system CA store (default)       |
| `false`           | Disable certificate verification (not recommended for production) |
| `/path/to/ca.crt` | Verify against a specific CA certificate bundle                   |

```yaml
# Verify against a custom CA
my-incus-custom-ca:
  driver: incus
  connection:
    type: https
    url: https://incus.internal:8443
    cert_storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: /etc/ssl/certs/my-internal-ca.crt
```

### SDB-backed Certificate Sources

You can store TLS material in Salt SDB and reference it from provider config.
The driver resolves `sdb://...` URIs and, when needed, writes temporary files
for `requests`.

```yaml
my-incus-remote-sdb:
  driver: incus
  connection:
    type: https
    url: https://incus.internal:8443
    cert_storage:
      type: sdb
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
      verify: sdb://vault/incus/ca_cert
```

Notes:
- Use `connection.cert_storage.type: sdb` to resolve all TLS values via SDB.
- `connection.cert_storage.verify` may return `true`, `false`, CA file path, or CA certificate content.
- Legacy flat keys (`cert_sdb`, `key_sdb`, `verify_sdb`) remain supported for compatibility.

### Multiple Providers

You can define multiple providers in the same file to manage different Incus servers:

```yaml
# /etc/salt/cloud.providers.d/incus.conf

incus-prod:
  driver: incus
  connection:
    type: https
    url: https://incus-prod.example.com:8443
    cert_storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: true

incus-staging:
  driver: incus
  connection:
    type: unix
    socket: /var/lib/incus/unix.socket
```

---

## Profile Configuration

Profiles describe the instances that `salt-cloud` creates. Place them in
`/etc/salt/cloud.profiles.d/incus.conf`.

### Minimal Profile

```yaml
# /etc/salt/cloud.profiles.d/incus.conf

ubuntu-container:
  provider: my-incus
  image: ubuntu/22.04
```

Create an instance from this profile:

```bash
salt-cloud -p ubuntu-container web-01
```

### Container with Resources

```yaml
web-server:
  provider: my-incus
  image: ubuntu/22.04
  type: container       # default; can be omitted
  profiles:
    - default
  cpu: 4
  memory: 4GB
  disk_size: 40GB
  storage_pool: default
  network: incusbr0
```

### Virtual Machine

```yaml
db-server:
  provider: my-incus
  image: ubuntu/22.04
  type: virtual-machine   # or "vm" for short
  profiles:
    - default
  cpu: 8
  memory: 16GB
  disk_size: 100GB
  storage_pool: ssd-pool
```

### Full Profile Reference

```yaml
my-full-profile:
  provider: my-incus

  # --- required ---
  image: ubuntu/22.04           # Incus image alias (see: salt-cloud --list-images my-incus)

  # --- instance type ---
  type: container               # "container" (default), "vm", or "virtual-machine"

  # --- Incus profiles to apply (stacked left to right) ---
  profiles:
    - default

  # --- high-level resource shortcuts ---
  # These take precedence over anything in the raw `config` dict below.
  cpu: 2                        # → limits.cpu: "2"
  memory: 2GB                   # → limits.memory: "2GB"
  disk_size: 20GB               # → devices.root.size: "20GB"
  storage_pool: default         # → devices.root.pool: "default"
  network: incusbr0             # → devices.eth0.network: "incusbr0"

  # --- cloud-init ---
  cloud_init: |
    #cloud-config
    packages:
      - nginx
    runcmd:
      - systemctl enable --now nginx

  # --- raw Incus config passthrough ---
  # High-level shortcuts (cpu, memory, cloud_init) override conflicting keys here.
  config:
    security.nesting: "true"
    limits.cpu.allowance: "50%"

  # --- raw Incus devices passthrough ---
  # High-level shortcuts (disk_size, storage_pool, network) override conflicting devices here.
  devices:
    gpu0:
      type: gpu
      id: "0"

  # --- cluster placement ---
  target: node-1                # target cluster member name; empty = auto-select

  # --- IP wait settings ---
  wait_for_ip: true             # wait until the instance has an IPv4 (default: true)
  wait_timeout: 60              # seconds to wait for an IP (default: 60)
  wait_interval: 2              # seconds between polls (default: 2)
  fail_on_wait_timeout: false   # raise an error if no IP after timeout (default: false)

  # --- salt-minion deployment ---
  deploy: true                  # deploy salt-minion after boot (default: true)
```

---

## CLI Usage

### Listing Resources

```bash
# Quick list of all instances (id, state, IPs)
salt-cloud -Q

# Full instance details
salt-cloud -F

# List instances from a specific provider
salt-cloud -f list_nodes my-incus

# List available images (local aliases)
salt-cloud --list-images my-incus
# or:
salt-cloud -f list_images my-incus

# List available sizes (Incus profiles)
salt-cloud --list-sizes my-incus
# or:
salt-cloud -f list_sizes my-incus

# List available locations (cluster members or "local")
salt-cloud --list-locations my-incus
# or:
salt-cloud -f avail_locations my-incus
```

Example output of `salt-cloud -Q`:

```
[INFO    ] salt-cloud starting
my-incus:
  ----------
  incus:
    ----------
    web-01:
      ----------
      id:
          web-01
      image:
          Ubuntu 22.04 LTS amd64 (container) (20240301_07:42)
      private_ips:
          - 10.0.0.10
      public_ips:
      size:
          default
      state:
          running
```

### Creating Instances

```bash
# Create a single instance from a profile
salt-cloud -p ubuntu-container web-01

# Create multiple instances at once
salt-cloud -p ubuntu-container web-01 web-02 web-03

# Dry-run: show what would be created
salt-cloud -p ubuntu-container web-01 --no-deploy
```

### Managing Instances

Actions operate on running instances using the `-a` flag:

```bash
# Show detailed info
salt-cloud -a show_instance web-01

# Stop an instance
salt-cloud -a stop web-01

# Start an instance
salt-cloud -a start web-01

# Reboot an instance
salt-cloud -a reboot web-01
```

### Destroying Instances

```bash
# Destroy a single instance (stops it first if running, then deletes)
salt-cloud -d web-01

# Destroy multiple instances
salt-cloud -d web-01 web-02

# Skip the confirmation prompt
salt-cloud -d web-01 -y
```

---

## Map Files

Map files allow you to provision a whole environment in one command.

```yaml
# /etc/salt/cloud.maps.d/web-cluster.yaml

ubuntu-container:
  - web-01
  - web-02
  - web-03

db-server:
  - db-primary

# Inline profile overrides per instance
ubuntu-container:
  - lb-01:
      cpu: 2
      memory: 1GB
  - app-01:
      cpu: 4
      memory: 8GB
      cloud_init: |
        #cloud-config
        packages:
          - python3
          - gunicorn
```

Apply the map:

```bash
# Create everything in the map that doesn't exist yet
salt-cloud -m /etc/salt/cloud.maps.d/web-cluster.yaml

# Destroy everything defined in the map
salt-cloud -m /etc/salt/cloud.maps.d/web-cluster.yaml -d

# Dry-run
salt-cloud -m /etc/salt/cloud.maps.d/web-cluster.yaml --no-deploy
```

---

## Cloud-Init Integration

Pass cloud-init user data directly in the profile using the `cloud_init` key.
This is mapped to `user.user-data` in the Incus instance config.

```yaml
app-server:
  provider: my-incus
  image: ubuntu/22.04
  type: container
  cloud_init: |
    #cloud-config
    users:
      - name: deploy
        groups: sudo
        shell: /bin/bash
        sudo: ALL=(ALL) NOPASSWD:ALL
        ssh_authorized_keys:
          - ssh-ed25519 AAAA... deploy@example.com
    packages:
      - git
      - python3-pip
    runcmd:
      - pip3 install -r /opt/app/requirements.txt
      - systemctl enable --now app.service
```

> **Note:** Cloud-init support depends on the image. Most Ubuntu, Debian, and Alpine
> images support cloud-init. Check your image documentation for details.

---

## Cluster (Multi-Node) Placement

When the Incus server is part of a cluster, use `target` (or the legacy `location` key)
to place instances on a specific member.

```bash
# See available cluster members
salt-cloud --list-locations my-incus
```

```
my-incus:
  ----------
  incus:
    ----------
    node-1:
      ----------
      database:
          True
      message:
          Fully operational
      name:
          node-1
      status:
          Online
      url:
          https://10.0.1.1:8443
    node-2:
      ...
```

Profile targeting a specific node:

```yaml
node1-container:
  provider: my-incus
  image: ubuntu/22.04
  target: node-1          # place on node-1

node2-container:
  provider: my-incus
  image: ubuntu/22.04
  target: node-2          # place on node-2

auto-placed-container:
  provider: my-incus
  image: ubuntu/22.04
  # no target = Incus scheduler decides placement
```

---

## Salt Minion Deployment

By default (`deploy: true`), after an instance boots and obtains an IP address,
`salt-cloud` will:

1. SSH into the instance using the first available private IP.
2. Install the Salt minion.
3. Accept the minion key on the master.

To disable automatic minion deployment (useful when using cloud-init for this instead):

```yaml
my-profile:
  provider: my-incus
  image: ubuntu/22.04
  deploy: false
```

When `deploy: false`, `salt-cloud` still creates and starts the instance but skips
SSH-based minion installation.

---

## IP Wait Behaviour

After an instance starts, the driver can wait until the instance has a routable IPv4
address before returning. This ensures subsequent operations (SSH, minion deployment)
have a valid target.

| Parameter              | Default | Description                           |
|------------------------|---------|---------------------------------------|
| `wait_for_ip`          | `true`  | Enable/disable the IP wait loop       |
| `wait_timeout`         | `60`    | Maximum seconds to wait               |
| `wait_interval`        | `2`     | Seconds between polls                 |
| `fail_on_wait_timeout` | `false` | Raise an error if no IP after timeout |

```yaml
fast-start:
  provider: my-incus
  image: ubuntu/22.04
  wait_for_ip: true
  wait_timeout: 120          # wait up to 2 minutes
  wait_interval: 5           # poll every 5 seconds
  fail_on_wait_timeout: true # hard-fail if no IP
```

When `fail_on_wait_timeout: false` (default), a warning is logged but the instance is
still returned without IPs. This is appropriate when `deploy: false` and you don't
need the IP immediately.

---

## Configuration Reference

### Provider Keys

| Key                 | Required | Default                      | Description                                      |
|---------------------|----------|------------------------------|--------------------------------------------------|
| `driver`            | yes      | —                            | Must be `incus`                                  |
| `connection.type`   | no       | `unix`                       | `unix` or `https`                                |
| `connection.socket` | no       | `/var/lib/incus/unix.socket` | Path to Unix socket (type=unix)                  |
| `connection.url`    | no       | —                            | HTTPS URL, e.g. `https://host:8443` (type=https) |
| `connection.cert_storage.type` | no | `local_files`           | TLS storage mode: `local_files` or `sdb`         |
| `connection.cert_storage.cert` | no | —                       | Cert path (`local_files`) or `sdb://...` URI     |
| `connection.cert_storage.key` | no | —                        | Key path (`local_files`) or `sdb://...` URI      |
| `connection.cert_storage.verify` | no | `true`                | TLS verify bool/path (`local_files`) or `sdb://...` |

### Profile Keys

| Key                    | Required | Default       | Description                                         |
|------------------------|----------|---------------|-----------------------------------------------------|
| `provider`             | yes      | —             | Provider name defined in `cloud.providers.d/`       |
| `image`                | yes      | —             | Incus image alias (e.g. `ubuntu/22.04`)             |
| `type`                 | no       | `container`   | Instance type: `container`, `vm`, `virtual-machine` |
| `profiles`             | no       | `["default"]` | List of Incus profiles to apply                     |
| `cpu`                  | no       | —             | vCPU count → `limits.cpu`                           |
| `memory`               | no       | —             | Memory limit → `limits.memory` (e.g. `2GB`)         |
| `disk_size`            | no       | —             | Root disk size → `devices.root.size` (e.g. `20GB`)  |
| `storage_pool`         | no       | —             | Root disk pool → `devices.root.pool`                |
| `network`              | no       | —             | Network for eth0 device → `devices.eth0.network`    |
| `cloud_init`           | no       | —             | Cloud-init user-data → `user.user-data`             |
| `config`               | no       | `{}`          | Raw Incus config dict (passthrough)                 |
| `devices`              | no       | `{}`          | Raw Incus devices dict (passthrough)                |
| `target`               | no       | `""`          | Cluster member to place the instance on             |
| `wait_for_ip`          | no       | `true`        | Wait for IPv4 address after start                   |
| `wait_timeout`         | no       | `60`          | IP wait timeout in seconds                          |
| `wait_interval`        | no       | `2`           | IP wait poll interval in seconds                    |
| `fail_on_wait_timeout` | no       | `false`       | Raise on timeout instead of logging warning         |
| `deploy`               | no       | `true`        | Deploy salt-minion via SSH after boot               |

### Parameter Merge Precedence

When both high-level shortcuts (`cpu`, `memory`, etc.) and raw `config`/`devices` keys
are present, **high-level shortcuts take precedence**:

```yaml
my-profile:
  provider: my-incus
  image: ubuntu/22.04
  cpu: 4                        # wins → limits.cpu: "4"
  config:
    limits.cpu: "2"             # overridden by cpu: 4 above
    security.nesting: "true"    # kept as-is (no conflict)
```

---

## Troubleshooting

### Driver Not Found

```
ERROR: The incus cloud driver is not available: python-requests is required
```

Install the `requests` library:

```bash
pip install requests
# or with Salt's bundled Python:
/opt/saltstack/salt/bin/pip install requests
```

### Permission Denied on Unix Socket

```
[Errno 13] Permission denied: '/var/lib/incus/unix.socket'
```

The Salt master process must have access to the Incus socket:

```bash
# Add the salt user to the incus-admin group (Debian/Ubuntu)
usermod -aG incus-admin salt
# Then restart the salt-master
systemctl restart salt-master
```

### Instance Created but No IP Reported

The instance may not have cloud-init or `incus-agent` configured, or the network
interface may take longer than the default timeout.

Try increasing the timeout:

```yaml
my-profile:
  provider: my-incus
  image: ubuntu/22.04
  wait_timeout: 120
  wait_interval: 5
```

Or disable the IP wait and manage deployment separately:

```yaml
my-profile:
  provider: my-incus
  image: ubuntu/22.04
  wait_for_ip: false
  deploy: false
```

### HTTPS Certificate Errors

```
SSLError: certificate verify failed
```

Either provide the correct CA certificate:

```yaml
connection:
  cert_storage:
    verify: /path/to/your/ca.crt
```

Or temporarily disable verification for testing (**not for production**):

```yaml
connection:
  cert_storage:
    verify: false
```

### Instance Already Exists

Salt Cloud will refuse to create an instance if the name already exists in Incus.
Clean up the existing instance first:

```bash
salt-cloud -d existing-name -y
```

### Debug Logging

Run `salt-cloud` with `-l debug` to see full API request/response details:

```bash
salt-cloud -p ubuntu-container web-01 -l debug
```

This will print the full JSON body sent to and received from the Incus API, which is
useful for diagnosing payload or authentication issues.
