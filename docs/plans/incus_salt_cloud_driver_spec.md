# Technical Specification v2

## Salt Cloud Driver for Incus (`_clouds/incus.py`)

Status: Draft v2 (corrected)  
Last updated: 2026-03-13

## 1. Purpose

Implement a Salt Cloud driver for Incus that provisions and manages both:

- containers
- virtual machines

The driver is a thin orchestration layer between `salt-cloud` and the existing execution module:

- `_clouds/incus.py` -> orchestration and Salt Cloud contract
- `_modules/incus.py` -> Incus API transport and low-level operations

High-level architecture:

```text
salt-cloud
    |
    v
_clouds/incus.py
    |
    v
__salt__["incus.*"]
    |
    v
_modules/incus.py
    |
    v
Incus daemon (unix socket or HTTPS)
```

## 2. Scope

The driver MUST support:

- provider/profile/map workflow of Salt Cloud
- multiple Incus providers (multi-server)
- unix socket and HTTPS connections
- container and VM provisioning
- lifecycle operations (create, destroy, start, stop, reboot)
- passthrough Incus `config` and `devices`
- cluster target placement
- deterministic output shape for Salt Cloud node-listing functions

Out of scope in this version:

- snapshots lifecycle from cloud driver
- image publishing
- scheduling/placement automation
- async task queue in driver

## 3. Sources of Truth

This specification is normative against:

- Salt Cloud driver authoring docs
- Salt Cloud map format docs
- Salt Cloud CLI docs
- Current `_modules/incus.py` function names and return shapes

Important: the project currently has no `docs/text` directory. Official Salt docs are used as the primary reference for cloud driver contract.

## 4. Current Execution Module Contract (Actual Names)

The cloud driver MUST call existing execution module functions with exact names:

| Driver operation | Execution module function |
| --- | --- |
| list images | `incus.image_list` |
| list sizes/profiles | `incus.profile_list` |
| list locations | `incus.cluster_member_list` |
| list instances | `incus.instance_list` |
| show instance | `incus.instance_get` |
| create instance | `incus.instance_create` |
| delete instance | `incus.instance_delete` |
| start instance | `incus.instance_start` |
| stop instance | `incus.instance_stop` |
| reboot instance | `incus.instance_restart` |
| wait guest readiness | `incus.instance_wait_ready` |
| network leases (optional for IP) | `incus.network_lease_list` |

`incus.instance_info` and `incus.cluster_members` are not valid names in current codebase and MUST NOT be used.

## 5. Salt Cloud Concepts and Config Files

### 5.1 Provider configuration

File:

```text
/etc/salt/cloud.providers.d/incus.conf
```

Example:

```yaml
incus01:
  driver: incus
  connection:
    type: unix
    socket: /var/lib/incus/unix.socket

incus02:
  driver: incus
  connection:
    type: https
    url: https://incus02:8443
    cert: /etc/salt/incus/client.crt
    key: /etc/salt/incus/client.key
    verify: true
```

Provider connection settings MUST be passed to execution-module calls in a deterministic way (see section 8).

### 5.2 Profile configuration

File:

```text
/etc/salt/cloud.profiles.d/incus.conf
```

Example:

```yaml
ubuntu-small:
  provider: incus01
  image: images:ubuntu/22.04
  type: vm
  profiles:
    - default
    - vm
  cpu: 2
  memory: 4GB
  disk_size: 20GB
  storage_pool: default
  network: default
  cloud_init: |
    #cloud-config
    packages:
      - nginx
```

### 5.3 Map configuration (canonical format)

File:

```text
cloud-map.sls
```

Canonical Salt Cloud map format:

```yaml
ubuntu-small:
  - web01
  - web02

ubuntu-db:
  - db01
```

Provision command:

```bash
salt-cloud -m cloud-map.sls
```

## 6. Required Driver Functions

The following functions MUST be implemented in `_clouds/incus.py`:

- `__virtual__()`
- `get_configured_provider()`
- `avail_images(call=None)`
- `avail_sizes(call=None)`
- `avail_locations(call=None)`
- `list_nodes(call=None)`
- `list_nodes_full(call=None)`
- `list_nodes_select(call=None)`
- `show_instance(name, call=None)`
- `create(vm_)`
- `destroy(name, call=None)`
- `start(name, call=None)`
- `stop(name, call=None)`
- `reboot(name, call=None)`

Notes:

- Driver virtual name MUST be `incus`.
- Action functions MUST honor Salt Cloud call modes (`action`, `function`).
- Errors MUST raise `salt.utils.cloud.CloudError`.

## 7. Output Contract for Node Listing

### 7.1 `list_nodes()`

Returns minimal normalized metadata:

```python
{
  "web01": {
    "id": "web01",
    "image": "images:ubuntu/22.04",
    "size": "default",
    "state": "running",
    "private_ips": ["10.0.0.10"],
    "public_ips": []
  }
}
```

### 7.2 `list_nodes_full()`

Returns the same top-level keying by VM name, but with additional raw/normalized fields needed by Salt Cloud UI and debugging.

### 7.3 `list_nodes_select()`

MUST delegate to Salt helper selection logic (standard Salt Cloud behavior) and support `--select` semantics.

## 8. Multi-Provider Context Passing

To support multiple Incus servers in one cloud run, each cloud-driver call MUST execute with the selected provider context.

Required strategy:

1. Resolve provider using Salt Cloud internals for current VM/action.
2. Build per-call execution kwargs so `_modules/incus.py` uses this provider configuration for this call only.
3. Never rely on one global static `incus` minion config for multi-provider cloud operations.

Implementation note:

- If `_modules/incus.py` currently cannot accept per-call connection overrides, this is a blocker.
- Either extend execution-module API with an optional `connection` argument, or add a dedicated context shim in cloud driver.
- Driver MUST fail fast with `CloudError` if provider context cannot be resolved/applied.

## 9. Supported Profile Parameters

The driver MUST support these profile keys:

| Parameter | Description |
| --- | --- |
| `image` | Incus image alias/fingerprint source |
| `type` | `container` or `vm` (`virtual-machine`) |
| `profiles` | Incus profile list |
| `cpu` | maps to `limits.cpu` |
| `memory` | maps to `limits.memory` |
| `disk_size` | root disk size |
| `storage_pool` | root disk pool |
| `network` | primary network name |
| `cloud_init` | user-data mapped to `user.user-data` |
| `config` | passthrough config |
| `devices` | passthrough devices |
| `target` | cluster placement target |
| `wait_for_ip` | bool, default `true` |
| `wait_timeout` | seconds, default `60` |
| `wait_interval` | seconds, default `2` |
| `wait_for_agent` | bool, default `false` |
| `fail_on_wait_timeout` | bool, default `false` |

## 10. Parameter Precedence and Merging Rules

Config resolution precedence MUST be deterministic:

1. provider defaults
2. profile values
3. map-level overrides / CLI overrides

Payload merge rules:

- `final_config = deep_merge(raw_config, generated_config)`
- `final_devices = deep_merge(raw_devices, generated_devices)`

Rationale: explicit high-level parameters (`cpu`, `memory`, `cloud_init`, `disk_size`, `network`) take precedence over raw passthrough keys.

## 11. Instance Payload Construction

### 11.1 Type mapping

- `container` -> `container`
- `vm` or `virtual-machine` -> `virtual-machine`
- unknown value -> `CloudError`

### 11.2 Source mapping

`image` is required for create:

```python
source = {"type": "image", "alias": image}
```

### 11.3 Generated config mapping

- `cpu` -> `config["limits.cpu"] = str(cpu)`
- `memory` -> `config["limits.memory"] = str(memory)`
- `cloud_init` -> `config["user.user-data"] = cloud_init`

### 11.4 Generated devices mapping

- if `disk_size` or `storage_pool` present, create/update root disk device
- if `network` present, create/update `eth0` NIC device

Expected payload example:

```json
{
  "name": "web01",
  "type": "virtual-machine",
  "source": {
    "type": "image",
    "alias": "images:ubuntu/22.04"
  },
  "profiles": ["default"],
  "config": {
    "limits.cpu": "2",
    "limits.memory": "4GB",
    "user.user-data": "#cloud-config\npackages:\n  - nginx\n"
  },
  "devices": {
    "root": {
      "type": "disk",
      "pool": "default",
      "path": "/",
      "size": "20GB"
    },
    "eth0": {
      "type": "nic",
      "network": "default"
    }
  }
}
```

## 12. Cluster Placement (`target`)

If profile sets:

```yaml
target: node1
```

Driver MUST pass cluster target to Incus create call.

Blocking dependency:

- Current `_modules/incus.py:instance_create` has no explicit `target` argument.
- Before final driver rollout, execution module MUST support target forwarding (query parameter or equivalent Incus API mechanism).
- Until that support exists, create with `target` MUST fail with clear `CloudError`.

## 13. Create Workflow

`create(vm_)` MUST:

1. resolve provider/profile/map parameters
2. validate required parameters (`image`, `type`)
3. build payload (section 11)
4. call `incus.instance_create(...)`
5. optionally wait for readiness/IP (section 14)
6. return `show_instance(name)` normalized output

## 14. Waiting Strategy

Defaults:

- interval: 2s
- timeout: 60s

Behavior:

1. Poll `incus.instance_get(name)` until status is running or timeout.
2. If `wait_for_agent=true`, call `incus.instance_wait_ready(name, timeout, interval)`.
3. If `wait_for_ip=true` and network is known, try resolving lease via `incus.network_lease_list(network)` and match by hostname/instance name.
4. On timeout:
   - if `fail_on_wait_timeout=true`: raise `CloudError`
   - else: log warning and return instance metadata without blocking further

## 15. Lifecycle Operations

Required behavior:

- `destroy(name, call=None)` -> `incus.instance_delete`
- `start(name, call=None)` -> `incus.instance_start`
- `stop(name, call=None)` -> `incus.instance_stop`
- `reboot(name, call=None)` -> `incus.instance_restart`

All operations MUST:

- validate instance existence where needed
- map execution-module failure to `CloudError`
- return Salt Cloud-compatible response structure

## 16. Error Handling and Logging

The driver MUST:

- raise `salt.utils.cloud.CloudError` for operational failures
- include provider name and instance name in error context
- use `log = logging.getLogger(__name__)`
- log start/end/failure for create and destroy
- never log private keys, cert contents, or cloud-init secrets

## 17. TDD Delivery Workflow (Mandatory)

For each behavior/module increment:

1. write failing tests first
2. pause for validation/review
3. implement minimal logic to pass tests
4. refactor safely while tests stay green

No implementation work starts before failing tests exist for that increment.

## 18. Test Matrix

### 18.1 Unit tests (`tests/unit/clouds/test_incus.py`)

Must cover:

- `__virtual__` registration and dependency checks
- provider resolution and `get_configured_provider`
- mapping of driver operations to exact `incus.*` function names
- payload builder for container and VM
- config/devices merge precedence
- `target` behavior (supported vs unsupported path)
- wait loop success/timeout branches
- `CloudError` mapping on execution-module failures
- output shape of `list_nodes`, `list_nodes_full`, `list_nodes_select`
- action/function `call` dispatch behavior

### 18.2 Integration tests

Must validate:

- `salt-cloud --list-providers`
- `salt-cloud --list-images incus`
- `salt-cloud --list-sizes incus`
- `salt-cloud --list-locations incus`
- `salt-cloud -p ubuntu-small testvm`
- destroy/start/stop/reboot against real Incus
- both connection types (`unix`, `https`) in provider configs

## 19. Acceptance Criteria

The change is complete when all are true:

- driver functions in section 6 are implemented
- multi-provider behavior works in one run
- container and VM creation both work
- errors are surfaced as `CloudError`
- unit and integration tests pass
- smoke CLI commands from section 18.2 succeed

## 20. Expected Code Size

Estimated cloud driver size:

- `350-700` lines in `_clouds/incus.py`

This range includes normalization, wait logic, and provider context handling.

## 21. Future Improvements

Planned follow-ups:

- snapshot operations in cloud driver
- multi-network provisioning
- multi-disk provisioning
- smarter host scheduling
- optional asynchronous operation polling model

## 22. References

- Salt Cloud driver authoring: https://docs.saltproject.io/en/latest/topics/cloud/writing.html
- Salt Cloud map files: https://docs.saltproject.io/en/latest/topics/cloud/map.html
- Salt Cloud CLI reference: https://docs.saltproject.io/en/latest/ref/cli/salt-cloud.html
