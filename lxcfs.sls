{% from tpldir ~ "/map.jinja" import incus with context %}
{% set global_config = incus.get("global") | default({}, true) %}
{% set lxcfs_config = global_config.get("lxcfs") | default({}, true) %}
{% set lxcfs_modules = lxcfs_config.get("modules") | default({}, true) %}

{% set flags = [] %}

{% if lxcfs_modules.get("loadavg", False) %}
{% do flags.append("--enable-loadavg") %}
{% endif %}
{% if lxcfs_modules.get("cfs", False) %}
{% do flags.append("--enable-cfs") %}
{% endif %}
{% if lxcfs_modules.get("memory", False) %}
{% do flags.append("--enable-memory") %}
{% endif %}
{% if lxcfs_modules.get("cpuset", False) %}
{% do flags.append("--enable-cpuset") %}
{% endif %}
{% if lxcfs_modules.get("sysinfo", False) %}
{% do flags.append("--enable-sysinfo") %}
{% endif %}
{% if lxcfs_modules.get("pidfd", False) %}
{% do flags.append("--enable-pidfd") %}
{% endif %}

{% set exec_line = "/opt/incus/bin/lxcfs " + " ".join(flags) + " /var/lib/incus-lxcfs" %}


# ------------------------------------------------------------------------------
# Override directory
# ------------------------------------------------------------------------------
incus-lxcfs-override-dir:
  file.directory:
    - name: /etc/systemd/system/incus-lxcfs.service.d
    - user: root
    - group: root
    - mode: 0755


# ------------------------------------------------------------------------------
# override.conf
# ------------------------------------------------------------------------------
incus-lxcfs-override-file:
  file.managed:
    - name: /etc/systemd/system/incus-lxcfs.service.d/override.conf
    - user: root
    - group: root
    - mode: 0644
    - contents: |
        [Service]
        ExecStart=
        ExecStart={{ exec_line }}
    - require:
      - file: incus-lxcfs-override-dir


# ------------------------------------------------------------------------------
# daemon-reload via systemctl
# ------------------------------------------------------------------------------
incus-lxcfs-daemon-reload:
  module.run:
    - name: service.systemctl_reload
    - onchanges:
      - file: incus-lxcfs-override-file


# ------------------------------------------------------------------------------
# Service restart
# ------------------------------------------------------------------------------
incus-lxcfs-service:
  service.running:
    - name: incus-lxcfs.service
    - enable: True
    - reload: True
    - restart: True
    - onchanges:
      - module: incus-lxcfs-daemon-reload
