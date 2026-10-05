# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as incus with context %}

{%- set pkg = incus.get("pkg") | default({}, true) %}
{%- set service = incus.get("service") | default({}, true) %}

incus-service-clean-service-dead:
  service.dead:
    - name: {{ service.get("name", "incus") }}
    - enable: False

incus-package-clean-pkg-removed:
  pkg.removed:
    - name: {{ pkg.get("name", "incus") }}
    - require:
      - service: incus-service-clean-service-dead
