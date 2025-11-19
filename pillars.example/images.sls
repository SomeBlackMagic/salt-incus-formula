# ======================================================================
# Incus Images Configuration Example
# ======================================================================
# This pillar file demonstrates image management in Incus.
#
# Images are templates used to create instances. They can be:
# - Downloaded from remote servers (linuxcontainers.org, Ubuntu, etc.)
# - Imported from local files
# - Created from existing instances
# - Automatically updated or manually managed
#
# Usage:
#   1. Copy this file to your pillar directory
#   2. Customize the images according to your needs
#   3. Include in your top.sls or specific minion pillar
#   4. Apply with: salt '*' state.apply incus.images
# ======================================================================

incus:
  # ====================================================================
  # Images
  # ====================================================================
  images:
    # ------------------------------------------------------------------
    # Ubuntu Images
    # ------------------------------------------------------------------
    # Note: The key (ubuntu2204) becomes the PRIMARY alias in Incus
    # Additional aliases can be specified in the 'aliases' list
    ubuntu2204:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04        # Used for importing from remote
        protocol: simplestreams
      auto_update: true
      public: false
      aliases:                     # ADDITIONAL aliases (besides ubuntu2204)
        - ubuntu-jammy
        - ubuntu-lts
      properties:
        description: Ubuntu 22.04 LTS (Jammy Jellyfish)
        os: ubuntu
        release: "22.04"

    ubuntu2004:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/20.04
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Ubuntu 20.04 LTS (Focal Fossa)

    ubuntu2404:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/24.04
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Ubuntu 24.04 LTS (Noble Numbat)

    # ------------------------------------------------------------------
    # Debian Images
    # ------------------------------------------------------------------
    debian12:
      source:
        server: https://images.linuxcontainers.org
        alias: debian/12
        protocol: simplestreams
      auto_update: true
      public: false
      aliases:                     # ADDITIONAL aliases (besides debian12)
        - debian-bookworm
      properties:
        description: Debian 12 (Bookworm)

    debian11:
      source:
        server: https://images.linuxcontainers.org
        alias: debian/11
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Debian 11 (Bullseye)

    # ------------------------------------------------------------------
    # Alpine Linux Images
    # ------------------------------------------------------------------
    alpine-latest:
      source:
        server: https://images.linuxcontainers.org
        alias: alpine/edge
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Alpine Linux Edge (latest)

    alpine318:
      source:
        server: https://images.linuxcontainers.org
        alias: alpine/3.18
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Alpine Linux 3.18

    # ------------------------------------------------------------------
    # Rocky Linux / Enterprise Linux
    # ------------------------------------------------------------------
    rocky9:
      source:
        server: https://images.linuxcontainers.org
        alias: rocky/9
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Rocky Linux 9

    almalinux9:
      source:
        server: https://images.linuxcontainers.org
        alias: almalinux/9
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: AlmaLinux 9

    # ------------------------------------------------------------------
    # Arch Linux
    # ------------------------------------------------------------------
    archlinux:
      source:
        server: https://images.linuxcontainers.org
        alias: archlinux
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Arch Linux (rolling release)

    # ------------------------------------------------------------------
    # Fedora
    # ------------------------------------------------------------------
    fedora39:
      source:
        server: https://images.linuxcontainers.org
        alias: fedora/39
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Fedora 39

    # ------------------------------------------------------------------
    # Custom/Local Images
    # ------------------------------------------------------------------
    # Example: Import image from local file
    # The key "custom-ubuntu" becomes the primary alias
    custom-ubuntu:
      source: /opt/images/custom-ubuntu.tar.gz
      public: false
      properties:
        description: Custom Ubuntu image with pre-installed software
        os: ubuntu
        release: jammy
        architecture: amd64
      aliases:
        - custom-base
        - app-template

    # Example: Public shared image
    # The key "shared-base" becomes the primary alias
    shared-base:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      public: true  # Available to other projects/users
      auto_update: false
      properties:
        description: Shared base image for development

# ======================================================================
# Image Management Patterns
# ======================================================================

# Pattern 1: Production Images (Pinned versions, manual updates)
incus_production_images:
  images:
    prod-ubuntu:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: false  # Manual control for production
      public: false
      properties:
        description: Production Ubuntu 22.04 - manually updated
        environment: production
        managed_by: ops-team

    prod-debian:
      source:
        server: https://images.linuxcontainers.org
        alias: debian/12
        protocol: simplestreams
      auto_update: false
      public: false
      properties:
        description: Production Debian 12 - manually updated

# Pattern 2: Development Images (Auto-update enabled)
incus_development_images:
  images:
    dev-ubuntu:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true  # Always keep up-to-date for dev
      public: false
      properties:
        description: Development Ubuntu 22.04 - auto-updated

    dev-debian:
      source:
        server: https://images.linuxcontainers.org
        alias: debian/12
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Development Debian 12 - auto-updated

# Pattern 3: VM Images
incus_vm_images:
  images:
    ubuntu-vm:
      source:
        server: https://cloud-images.ubuntu.com/releases
        alias: 22.04
        protocol: simplestreams
      auto_update: true
      public: false
      compression_algorithm: zstd
      properties:
        description: Ubuntu 22.04 Cloud image for VMs

    debian-vm:
      source:
        server: https://images.linuxcontainers.org
        alias: debian/12/cloud
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Debian 12 Cloud image for VMs

# Pattern 4: Multiple Aliases Strategy
# The key becomes the PRIMARY alias, with additional aliases in the list
incus_multi_alias_images:
  images:
    ubuntu2204:                      # PRIMARY alias
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true
      public: false
      aliases:                       # ADDITIONAL aliases
        - ubuntu-jammy
        - ubuntu-lts
        - ubuntu-latest
        - ubuntu
      properties:
        description: Ubuntu 22.04 with multiple convenient aliases

# Pattern 5: Custom Built Images
incus_custom_images:
  images:
    # Web server base image
    webserver-base:
      source: /opt/images/webserver-base.tar.gz
      public: false
      properties:
        description: Custom web server base with Nginx and PHP
        role: webserver
        nginx_version: "1.24"
        php_version: "8.2"
        build_date: "2024-01-15"

    # Database server base image
    database-base:
      source: /opt/images/database-base.tar.gz
      public: false
      properties:
        description: Custom database server base with PostgreSQL
        role: database
        postgresql_version: "15"
        build_date: "2024-01-15"

# Pattern 6: Testing Images
incus_testing_images:
  images:
    # Latest/Edge versions for testing
    ubuntu-dev:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/devel
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Ubuntu development version for testing

    fedora-rawhide:
      source:
        server: https://images.linuxcontainers.org
        alias: fedora/rawhide
        protocol: simplestreams
      auto_update: true
      public: false
      properties:
        description: Fedora Rawhide for bleeding edge testing

# Pattern 7: Minimal Images for CI/CD
incus_ci_images:
  images:
    # Minimal Alpine for fast CI
    ci-alpine:
      source:
        server: https://images.linuxcontainers.org
        alias: alpine/3.18
        protocol: simplestreams
      auto_update: true
      public: false
      compression_algorithm: zstd
      properties:
        description: Minimal Alpine for CI/CD pipelines
        purpose: ci-cd
        size: minimal

    # Ubuntu minimal for CI
    ci-ubuntu:
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04/minimal
        protocol: simplestreams
      auto_update: true
      public: false
      compression_algorithm: zstd
      properties:
        description: Minimal Ubuntu for CI/CD pipelines

# ======================================================================
# Image Configuration Options
# ======================================================================
#
# name: (required - the pillar key)
#   - ALWAYS becomes the PRIMARY alias for the image in Incus
#   - Also used as state identifier in Salt
#
# source: (required for new images)
#   - Dict with server/alias/protocol for remote images
#   - String path for local file import
#   - source.alias is used only for importing (NOT as image alias)
#
# fingerprint: (optional)
#   - Specific image fingerprint for exact version lookup
#
# auto_update: (optional, default: false)
#   - true: Automatically update image from source
#   - false: Keep image at current version
#
# public: (optional, default: false)
#   - true: Image accessible to all projects/users
#   - false: Image private to current project
#
# aliases: (optional)
#   - List of ADDITIONAL aliases for the image
#   - The pillar key (name) is ALWAYS added as primary alias
#
# properties: (optional)
#   - Dict of custom properties (metadata)
#   - Useful for filtering, searching, documentation
#   - description should be in properties, not at top level
#
# expires_at: (optional)
#   - ISO 8601 timestamp when image expires
#
# compression_algorithm: (optional)
#   - Compression: gzip, zstd, bzip2, lzma, xz, none
#   - zstd recommended for best performance/ratio
#
# ======================================================================
# Remote Image Servers
# ======================================================================
#
# Linux Containers (primary source):
#   server: https://images.linuxcontainers.org
#   protocol: simplestreams
#   - Most distributions available
#   - Both container and VM images
#   - Well maintained and updated
#
# Ubuntu Cloud Images:
#   server: https://cloud-images.ubuntu.com/releases
#   protocol: simplestreams
#   - Official Ubuntu cloud images
#   - Optimized for VM use
#
# Custom/Private Servers:
#   - Can host own image server
#   - Use simplestreams protocol
#   - Useful for enterprise deployments
#
# ======================================================================
# Best Practices
# ======================================================================
#
# 1. Image Updates:
#    - Enable auto_update for dev/test environments
#    - Disable auto_update for production (manual control)
#    - Test image updates before production deployment
#
# 2. Aliases:
#    - Use descriptive, version-specific aliases
#    - Maintain compatibility aliases for automation
#    - Document alias conventions
#
# 3. Storage:
#    - Use compression (zstd) to save space
#    - Monitor image storage usage
#    - Clean up unused images regularly
#
# 4. Security:
#    - Only use images from trusted sources
#    - Verify fingerprints for critical images
#    - Keep images updated for security patches
#
# 5. Custom Images:
#    - Document custom image contents
#    - Version custom images
#    - Store sources/build scripts in version control
#
# 6. Properties:
#    - Add metadata for searchability
#    - Track build dates and versions
#    - Document image purposes and owners
#
# ======================================================================
