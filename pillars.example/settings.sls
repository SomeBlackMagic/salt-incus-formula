# ======================================================================
# Incus Server Settings Configuration Examples
# ======================================================================
# This file contains examples of all available Incus server settings
# that can be managed via Salt states.
#
# Settings control various aspects of the Incus server including:
# - Network and API configuration (core.*)
# - Image management (images.*)
# - Cluster configuration (cluster.*)
# - Storage configuration (storage.*)
# - MAAS integration (maas.*)
# - Backups, logging, and more
# ======================================================================

# ======================================================================
# Configuration Approaches: server_settings vs server_settings_individual
# ======================================================================
#
# There are TWO main ways to manage Incus server settings:
#
# 1. server_settings - BULK CONFIGURATION
#    - Updates multiple settings in a SINGLE state call
#    - Simpler and more compact
#    - All settings applied together (atomic)
#    - Creates ONE state ID: incus-server-settings
#    - Use for: initial setup, related settings groups
#
# 2. server_settings_individual - INDIVIDUAL MANAGEMENT
#    - Each setting is a SEPARATE state with its own ID
#    - More flexible and granular control
#    - Supports ensure: present/absent per setting
#    - Each setting can have dependencies
#    - Use for: fine-grained control, conditional settings
#
# COMPARISON:
# +------------------------+----------------------+---------------------------+
# | Aspect                 | server_settings      | server_settings_individual|
# +------------------------+----------------------+---------------------------+
# | Number of states       | 1 for all settings   | 1 per setting             |
# | Simplicity             | ✅ More compact       | ❌ More verbose            |
# | Flexibility            | ❌ Limited            | ✅ Maximum                 |
# | ensure: absent         | ❌ Not supported      | ✅ Supported               |
# | Dependencies (require) | ❌ Only for all       | ✅ Per setting             |
# | Conditional logic      | ❌ More complex       | ✅ Easier                  |
# | Use case               | Bulk updates         | Fine-grained control      |
# +------------------------+----------------------+---------------------------+
#
# YOU CAN USE BOTH! They complement each other:
# - Use server_settings for common base configuration
# - Use server_settings_individual for specific/conditional settings
#
# Example:
#   incus:
#     # Base config for ALL servers
#     server_settings:
#       config:
#         images.auto_update_cached: "true"
#
#     # Specific settings per server
#     server_settings_individual:
#       {% if grains['environment'] == 'production' %}
#       https_api:
#         ensure: present
#         key: core.https_address
#         value: "[::]:8443"
#       {% endif %}
#
# ======================================================================

incus:
  # ====================================================================
  # Server Settings - Bulk Configuration
  # ====================================================================
  # Merges specified settings with existing configuration.
  # Only updates the keys you specify, preserves others.
  server_settings:
    config:
      # ------------------------------------------------------------------
      # Core Settings (core.*)
      # ------------------------------------------------------------------
      # HTTPS API server configuration
      core.https_address: "[::]:8443"                    # Listen address for HTTPS (IPv6/IPv4)
      # core.https_address: "0.0.0.0:8443"              # IPv4 only
      # core.https_address: "192.168.1.100:8443"        # Specific interface

      # Trust password for adding new clients
      core.trust_password: "changeme"                    # Password for client authentication

      # TLS configuration
      # core.https_allowed_headers: ""                   # Allowed HTTP headers
      # core.https_allowed_methods: ""                   # Allowed HTTP methods
      # core.https_allowed_origin: ""                    # CORS allowed origin
      # core.https_allowed_credentials: "true"           # Allow credentials in CORS
      # core.https_trusted_proxy: ""                     # Trusted proxy addresses

      # Proxy configuration
      # core.proxy_http: "http://proxy.example.com:3128" # HTTP proxy
      # core.proxy_https: "http://proxy.example.com:3128" # HTTPS proxy
      # core.proxy_ignore_hosts: "localhost,127.0.0.1"   # Hosts to bypass proxy

      # Remote access
      # core.remote_token_expiry: "3600"                 # Remote token expiration (seconds)

      # Shutdown timeout
      # core.shutdown_timeout: "5"                       # Timeout for graceful shutdown (minutes)

      # Background operations
      # core.bgp_address: ""                             # BGP router address
      # core.bgp_asn: ""                                 # BGP autonomous system number
      # core.dns_address: ""                             # DNS server address

      # ------------------------------------------------------------------
      # Image Settings (images.*)
      # ------------------------------------------------------------------
      # Automatic image updates
      images.auto_update_cached: "true"                  # Auto-update cached images
      images.auto_update_interval: "12"                  # Hours between update checks

      # Image compression
      images.compression_algorithm: "zstd"               # Compression: gzip, zstd, bzip2, lzma, xz, none

      # Remote image caching
      images.remote_cache_expiry: "10"                   # Days to cache remote images

      # Image download limits
      # images.default_architecture: ""                  # Default architecture for images

      # ------------------------------------------------------------------
      # Cluster Settings (cluster.*)
      # ------------------------------------------------------------------
      # Cluster networking
      # cluster.https_address: "192.168.1.100:8443"      # Address for cluster communication
      # cluster.offline_threshold: "120"                 # Seconds before member considered offline

      # Cluster images
      # cluster.images_minimal_replica: "3"              # Minimum image replicas in cluster

      # Cluster healing
      # cluster.healing_threshold: "0"                   # Threshold for healing operations

      # Cluster join token
      # cluster.max_voters: "3"                          # Maximum voters in cluster
      # cluster.max_standby: "2"                         # Maximum standby members

      # ------------------------------------------------------------------
      # Storage Settings (storage.*)
      # ------------------------------------------------------------------
      # Default storage locations
      # storage.backups_volume: "backups"                # Volume for backups
      # storage.images_volume: "images"                  # Volume for images

      # ZFS configuration
      # storage.zfs_pool_name: "incus"                   # ZFS pool name

      # ------------------------------------------------------------------
      # MAAS Integration (maas.*)
      # ------------------------------------------------------------------
      # MAAS API configuration
      # maas.api.url: "http://maas.example.com:5240/MAAS" # MAAS API URL
      # maas.api.key: "MAAS_API_KEY_HERE"                 # MAAS API key

      # Machine settings
      # maas.machine.domain: "maas"                       # Default domain for machines

      # ------------------------------------------------------------------
      # Backups (backups.*)
      # ------------------------------------------------------------------
      # Backup compression
      # backups.compression_algorithm: "gzip"             # Compression for backups

      # ------------------------------------------------------------------
      # Candid Authentication (candid.*)
      # ------------------------------------------------------------------
      # External authentication via Candid
      # candid.api.url: "https://candid.example.com"      # Candid API URL
      # candid.api.key: "CANDID_API_KEY"                  # Candid API key
      # candid.domains: "example.com"                     # Allowed domains
      # candid.expiry: "3600"                             # Token expiry (seconds)

      # ------------------------------------------------------------------
      # OCI Registry (oci.*)
      # ------------------------------------------------------------------
      # OCI registry configuration for image distribution
      # oci.port: "8444"                                  # OCI registry port

      # ------------------------------------------------------------------
      # Metrics (metrics.*)
      # ------------------------------------------------------------------
      # Metrics and monitoring
      # metrics.authentication: "true"                    # Require auth for metrics
      # metrics.address: "[::]:8444"                      # Metrics endpoint address

      # ------------------------------------------------------------------
      # Miscellaneous Settings
      # ------------------------------------------------------------------
      # Syslog integration
      # syslog.socket: "/dev/log"                         # Syslog socket path

      # User configuration
      # user.* : ""                                       # User-defined key-value pairs

  # ====================================================================
  # Server Settings - Individual Management
  # ====================================================================
  # Manage individual settings one at a time.
  # Useful for fine-grained control or when settings need different states.
  server_settings_individual:

    # Example: Enable HTTPS API
    https_api:
      ensure: present                                    # present or absent
      key: core.https_address
      value: "[::]:8443"

    # Example: Set trust password
    trust_password:
      ensure: present
      key: core.trust_password
      value: "mysecretpassword"

    # Example: Configure auto-update interval
    auto_update:
      ensure: present
      key: images.auto_update_interval
      value: "6"                                         # Check every 6 hours

    # Example: Set compression algorithm
    compression:
      ensure: present
      key: images.compression_algorithm
      value: "zstd"

    # Example: Remove a setting (revert to default)
    remove_old_setting:
      ensure: absent
      key: some.deprecated.setting

    # Example: Cluster configuration
    cluster_address:
      ensure: present
      key: cluster.https_address
      value: "192.168.1.100:8443"

    cluster_offline:
      ensure: present
      key: cluster.offline_threshold
      value: "120"

    # Example: Storage configuration
    backups_volume:
      ensure: present
      key: storage.backups_volume
      value: "backups"

    images_volume:
      ensure: present
      key: storage.images_volume
      value: "images"

  # ====================================================================
  # Server Settings - Managed (Exact Match)
  # ====================================================================
  # WARNING: This replaces ALL server settings with exactly what's specified.
  # Any settings not listed here will be REMOVED and reverted to defaults.
  # Use this only when you want complete control over server configuration.
  #
  # To enable managed mode, uncomment the following:
  #
  # server_settings:
  #   managed: true
  #   managed_config:
  #     # Only these settings will exist, everything else will be removed
  #     core.https_address: "[::]:8443"
  #     core.trust_password: "secret"
  #     images.auto_update_cached: "true"
  #     images.auto_update_interval: "12"
  #     images.compression_algorithm: "zstd"


# ======================================================================
# Common Configuration Patterns
# ======================================================================

# Pattern 1: Basic Setup (HTTPS + Auto-updates)
# incus:
#   server_settings:
#     config:
#       core.https_address: "[::]:8443"
#       core.trust_password: "changeme"
#       images.auto_update_cached: "true"
#       images.auto_update_interval: "12"

# Pattern 2: Cluster Configuration
# incus:
#   server_settings:
#     config:
#       core.https_address: "[::]:8443"
#       cluster.https_address: "192.168.1.100:8443"
#       cluster.offline_threshold: "120"
#       cluster.images_minimal_replica: "3"

# Pattern 3: Production Setup with Compression
# incus:
#   server_settings:
#     config:
#       core.https_address: "0.0.0.0:8443"
#       core.trust_password: "strong_password_here"
#       images.auto_update_cached: "true"
#       images.auto_update_interval: "6"
#       images.compression_algorithm: "zstd"
#       images.remote_cache_expiry: "30"
#       storage.backups_volume: "backups"
#       backups.compression_algorithm: "zstd"

# Pattern 4: Behind Proxy
# incus:
#   server_settings:
#     config:
#       core.https_address: "[::]:8443"
#       core.proxy_http: "http://proxy.internal:3128"
#       core.proxy_https: "http://proxy.internal:3128"
#       core.proxy_ignore_hosts: "localhost,127.0.0.1,.local"

# Pattern 5: Disable Auto-updates
# incus:
#   server_settings_individual:
#     disable_auto_update:
#       ensure: absent
#       key: images.auto_update_cached

# Pattern 6: Mixed Approach (Base + Specific Settings)
# Use server_settings for common configuration across all servers,
# and server_settings_individual for environment-specific or conditional settings
#
# incus:
#   # Common base configuration for ALL servers
#   server_settings:
#     config:
#       images.auto_update_cached: "true"
#       images.auto_update_interval: "12"
#       images.compression_algorithm: "zstd"
#
#   # Specific settings based on conditions
#   server_settings_individual:
#     # Production servers only - enable HTTPS
#     {% if grains['environment'] == 'production' %}
#     https_api:
#       ensure: present
#       key: core.https_address
#       value: "[::]:8443"
#
#     trust_password:
#       ensure: present
#       key: core.trust_password
#       value: {{ pillar['incus_prod_password'] }}
#     {% endif %}
#
#     # Cluster servers only - cluster configuration
#     {% if 'cluster' in grains['roles'] %}
#     cluster_address:
#       ensure: present
#       key: cluster.https_address
#       value: {{ grains['ipv4'][0] }}:8443
#
#     cluster_threshold:
#       ensure: present
#       key: cluster.offline_threshold
#       value: "120"
#
#     cluster_replicas:
#       ensure: present
#       key: cluster.images_minimal_replica
#       value: "3"
#     {% endif %}
#
#     # Development servers - disable HTTPS
#     {% if grains['environment'] == 'development' %}
#     no_https:
#       ensure: absent
#       key: core.https_address
#
#     no_password:
#       ensure: absent
#       key: core.trust_password
#     {% endif %}
#
#     # Remove deprecated settings everywhere
#     cleanup_old_setting:
#       ensure: absent
#       key: old.deprecated.config
