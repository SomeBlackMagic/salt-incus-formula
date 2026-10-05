# -*- coding: utf-8 -*-
# vim: ft=yaml
---
incus:
  enable: true

  pkg:
    name: incus

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
