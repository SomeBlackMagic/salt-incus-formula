# -*- coding: utf-8 -*-
# vim: ft=sls

incus-lxcfs-clean-service-dead:
  service.dead:
    - name: incus-lxcfs.service
    - enable: False

incus-lxcfs-clean-override-absent:
  file.absent:
    - name: /etc/systemd/system/incus-lxcfs.service.d
    - require:
      - service: incus-lxcfs-clean-service-dead
