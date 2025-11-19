{% from tpldir ~ "/map.jinja" import incus with context %}

{% set flags = [] %}

{% if incus.global.lxcfs.modules.get("loadavg", False) %}
{% do flags.append("--enable-loadavg") %}
{% endif %}
{% if incus.global.lxcfs.modules.get("cfs", False) %}
{% do flags.append("--enable-cfs") %}
{% endif %}
{% if incus.global.lxcfs.modules.get("memory", False) %}
{% do flags.append("--enable-memory") %}
{% endif %}
{% if incus.global.lxcfs.modules.get("cpuset", False) %}
{% do flags.append("--enable-cpuset") %}
{% endif %}
{% if incus.global.lxcfs.modules.get("sysinfo", False) %}
{% do flags.append("--enable-sysinfo") %}
{% endif %}
{% if incus.global.lxcfs.modules.get("pidfd", False) %}
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
