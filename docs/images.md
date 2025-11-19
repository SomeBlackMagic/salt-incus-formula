# Incus Images State - Documentation

## Overview

The `incus.image_present` state provides declarative management of Incus images with full idempotency support.

**IMPORTANT**: The `name` parameter is **ALWAYS** used as the primary alias for the image in Incus. Additional aliases can be specified via the `aliases` parameter.

## Supported Parameters

| Parameter               | Type     | Required | Description                                                                |
|-------------------------|----------|----------|----------------------------------------------------------------------------|
| `name`                  | string   | ✓        | **State name** - ALWAYS becomes the primary alias for the image            |
| `fingerprint`           | string   | -        | Image fingerprint for precise lookup                                       |
| `source`                | dict/str | -        | Source for importing the image (dict with server/alias or local file path) |
| `auto_update`           | bool     | -        | Automatic image update                                                     |
| `public`                | bool     | -        | Public access to the image                                                 |
| `aliases`               | list     | -        | List of **additional** aliases (name is always included automatically)     |
| `properties`            | dict     | -        | Image properties (metadata)                                                |
| `expires_at`            | string   | -        | Expiration date (ISO 8601)                                                 |
| `compression_algorithm` | string   | -        | Compression algorithm                                                      |

### Understanding the `name` parameter:

```yaml
ubuntu2204:                      # ← State ID (for require/watch etc.)
  incus.image_present:
    # name defaults to state ID: "ubuntu2204"
    # This becomes the PRIMARY alias in Incus
    - source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04      # ← Used for importing from remote
        protocol: simplestreams
    - aliases:                   # ← ADDITIONAL aliases
        - ubuntu-latest
        - ubuntu-lts
```

The image will have 3 aliases in total: `ubuntu2204` (from name), `ubuntu-latest`, and `ubuntu-lts`.

## Working Logic

1. **Searching for existing image** (in order of priority):
   - By `fingerprint` (if specified) - most precise method
   - By `name` alias (via `/images/aliases` API)
   - By any alias in the `aliases` list (via API)
   - By `source.alias` (for remote imports)

2. **Importing image** (if not found and source is provided):
   - Remote: from `source.server` with specified `source.alias`
   - Local: from file at `source` path (if source is a string)
   - Automatically creates all aliases (`name` + additional from `aliases`)

3. **Reconciliation** (if image is found):
   - Comparing all specified parameters with current values
   - Updating only changed fields through API
   - Managing aliases: removing old ones, adding new ones
   - Idempotency: repeated runs do not cause changes

## Usage Examples

### Minimal Configuration

```yaml
incus:
  images:
    ubuntu2204:                    # ← State ID and PRIMARY alias
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04        # ← Used for importing
        protocol: simplestreams
      auto_update: true
```

Generates state:
```yaml
incus-image-ubuntu2204:
  incus.image_present:
    - name: ubuntu2204             # ← Becomes alias in Incus
    - source: {...}
    - auto_update: true
```

Result: Image will have ONE alias: `ubuntu2204`

### Configuration with Multiple Aliases

```yaml
incus:
  images:
    ubuntu2204:                    # ← PRIMARY alias (from name)
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true
      public: false
      aliases:                     # ← ADDITIONAL aliases
        - ubuntu-jammy
        - ubuntu-lts
        - ubuntu-latest
      properties:
        description: "Ubuntu 22.04 LTS"
        os: ubuntu
        release: "22.04"
```

Result: Image will have FOUR aliases: `ubuntu2204`, `ubuntu-jammy`, `ubuntu-lts`, `ubuntu-latest`

### Management by Fingerprint (Precise Lookup)

```yaml
incus:
  images:
    my-custom-image:               # ← PRIMARY alias
      fingerprint: "5edcb2f01c2bda1e0b1bb62c3cbe8c3405584f0a98b17dbbc208b470f947a355"
      public: true
      auto_update: false
      aliases:                     # ← ADDITIONAL aliases
        - custom-v1
        - production-base
```

Result: Image will have THREE aliases: `my-custom-image`, `custom-v1`, `production-base`

### Local File Import

```yaml
incus:
  images:
    custom-ubuntu:                 # ← PRIMARY alias
      source: /opt/images/custom-ubuntu.tar.gz
      public: false
      properties:
        os: ubuntu
        release: jammy
        architecture: amd64
      aliases:                     # ← ADDITIONAL aliases
        - base-image
        - app-template
```

### Using in Other States (Requisites)

```yaml
incus:
  images:
    ubuntu2204:                    # ← This becomes the alias
      source:
        alias: ubuntu/22.04
        server: https://images.linuxcontainers.org
        protocol: simplestreams

  instances:
    mycontainer:
      source:
        type: image
        alias: ubuntu2204          # ← Use the name as alias
      require:
        - incus: incus-image-ubuntu2204    # ← State ID
```

## Important Notes

### The `name` Parameter Becomes an Alias

**Key Concept**: In this implementation, the `name` parameter serves dual purpose:
1. It's the unique state identifier in Salt (for requisites)
2. **It ALWAYS becomes an alias** for the image in Incus

**Example:**
```yaml
ubuntu2204:                      # ← State ID
  incus.image_present:
    # name defaults to "ubuntu2204"
    # Image will have alias "ubuntu2204" in Incus
    - source: {...}
```

### The `aliases` Parameter Adds Additional Aliases

The `aliases` parameter specifies **additional** aliases beyond the primary `name`:

```yaml
ubuntu2204:                      # ← PRIMARY alias (from name)
  incus.image_present:
    - aliases:                   # ← ADDITIONAL aliases
        - ubuntu-jammy
        - ubuntu-lts
    - source: {...}
```

Total aliases: `ubuntu2204`, `ubuntu-jammy`, `ubuntu-lts`

### Source Alias vs Image Aliases

- `source.alias`: Used only for **importing** from remote server
- `name` + `aliases`: Actual **aliases in Incus** after import

```yaml
my-ubuntu:                       # ← Alias in Incus
  incus.image_present:
    - source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04      # ← Only for import, NOT an alias in Incus
        protocol: simplestreams
```

After import, the image will have alias `my-ubuntu` (not `ubuntu/22.04`)

## Troubleshooting

### Image is Constantly Being Reimported

**Cause**: State cannot find the existing image by its alias.

**Diagnosis**:
```bash
# Check image aliases
incus image alias list
```

**Solution**:
1. Ensure the image has an alias matching the state `name`
2. Or use `fingerprint` for precise lookup
3. Or check and update the `name` in pillar to match existing alias

**Example Fix**:
```yaml
# If image has alias "ubuntu/22.04" but state name is "ubuntu2204"
# Option 1: Change name to match existing alias
ubuntu/22.04:                    # Match existing alias
  incus.image_present:
    - source: {...}

# Option 2: Let state create new alias
ubuntu2204:                      # New alias will be created
  incus.image_present:
    - fingerprint: abc123...     # Use fingerprint to find image
    - aliases:
        - ubuntu-jammy
```

### Changes Show Modifications on Every Run

**Cause**: Alias configuration in pillar doesn't match actual aliases in Incus.

**Diagnosis**:
```bash
# Check current image aliases
incus image alias list
incus image show <fingerprint>
```

**Solution**:
Ensure aliases in pillar match what should exist in Incus:
```yaml
ubuntu2204:
  incus.image_present:
    - aliases:                   # These PLUS name will be ALL aliases
        - ubuntu-jammy           # If image has other aliases, they'll be removed
```

### State ID Conflicts

**Problem**: `Error: Conflicting state IDs`

**Cause**: Two images with the same `name` or state ID.

**Solution**:
```yaml
# Bad - duplicate names
ubuntu:
  incus.image_present:
    - name: ubuntu

ubuntu-22:
  incus.image_present:
    - name: ubuntu    # ← Conflict!

# Good - unique names
ubuntu2004:
  incus.image_present:
    - name: ubuntu2004

ubuntu2204:
  incus.image_present:
    # name defaults to "ubuntu2204"
    # Image will have alias "ubuntu2204" in Incus
    - source: {...}
```

## See Also

- [Incus Images API](https://linuxcontainers.org/incus/docs/main/rest-api/#images)
- [Salt States Documentation](https://docs.saltproject.io/en/latest/ref/states/all/)
- [Image State Module Source](states/incus/_states/incus.py)
- [Image Execution Module Source](states/incus/_modules/incus.py)