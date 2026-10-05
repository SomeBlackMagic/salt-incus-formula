# -*- coding: utf-8 -*-
# vim: ft=yaml
---
incus:
  enable: true

  repo:
    enable: true
    channel: stable

  pkg:
    name: incus
    deps:
      - python3-cryptography
      - lxcfs

  service:
    name: incus
    enable: true

  global:
    lxcfs:
      enable: false

  images: {}
  instances: {}
  storage_pools: {}
  networks: {}
  profiles: {}
  server_settings: {}
  server_settings_individual: {}
