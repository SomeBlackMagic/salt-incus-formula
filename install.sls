{#-
  Install Incus and its OS-level dependencies.
  Supports both Debian and RedHat families.
  Package lists are defined via map.jinja (defaults + pillar overrides).
-#}
{% from tpldir ~ "/map.jinja" import incus with context %}

{% if incus.enable %}
  
  {% set os_family = grains.get("os_family") %}
  {% set codename = grains.get("oscodename", "bookworm") %}
  {% set incus_version = incus.get("version", None) %}
  {% set pkg_name = incus.pkg.get("name", "incus") %}
  {% set db_file = '/var/lib/incus/database/global/db.bin' %}

  {#- Debian/Ubuntu repository setup -#}
  {% if incus.repo.enable and os_family == "Debian" %}
    {% set arch = incus.repo.debian.get("architecture", "amd64") %}
    {% set repo_channel = incus.repo.get("channel", "stable") %}
    {% set key_url = incus.repo.debian.get("key_url", "https://pkgs.zabbly.com/key.asc") %}

incus-keyring-directory:
  file.directory:
    - name: /etc/apt/keyrings
    - user: root
    - group: root
    - mode: '0755'
    - makedirs: True

incus-repo-key:
  file.managed:
    - name: /etc/apt/keyrings/zabbly.asc
    - source: {{ key_url }}
    - skip_verify: True
    - mode: '0644'
    - user: root
    - group: root
    - require:
      - file: incus-keyring-directory

incus-repo-list:
  file.managed:
    - name: /etc/apt/sources.list.d/zabbly-incus-{{ repo_channel }}.sources
    - user: root
    - group: root
    - mode: '0644'
    - contents: |
        Enabled: yes
        Types: deb
        URIs: https://pkgs.zabbly.com/incus/{{ repo_channel }}
        Suites: {{ codename }}
        Components: main
        Architectures: {{ arch }}
        Signed-By: /etc/apt/keyrings/zabbly.asc
    - require:
      - file: incus-repo-key
  {% endif %}

  {#- RedHat/CentOS/Fedora repository setup -#}
  {% if incus.repo.enable and os_family == "RedHat" %}
  {% set repo_name = incus.repo.redhat.get("name", "incus-stable") %}
  {% set baseurl = incus.repo.redhat.get("baseurl", "https://pkgs.zabbly.com/incus/stable/rpm/$releasever/$basearch") %}
  {% set gpgkey = incus.repo.redhat.get("gpgkey", "https://pkgs.zabbly.com/key.asc") %}
  {% set repo_enabled = incus.repo.redhat.get("enabled", 1) %}
  {% set gpgcheck = incus.repo.redhat.get("gpgcheck", 1) %}

incus-repo:
  pkgrepo.managed:
    - name: {{ repo_name }}
    - humanname: Incus Repository
    - baseurl: {{ baseurl }}
    - gpgkey: {{ gpgkey }}
    - enabled: {{ repo_enabled }}
    - gpgcheck: {{ gpgcheck }}
  {% endif %}

{#- Install main Incus package -#}
incus-package:
  pkg.installed:
    - name: {{ pkg_name }}
    {% if incus_version %}
    - version: {{ incus_version }}
    {% endif %}
    {% if incus.repo.enable %}
    - refresh: True
    {% if os_family == "Debian" %}
    - require:
      - file: incus-repo-list
    {% elif os_family == "RedHat" %}
    - require:
      - pkgrepo: incus-repo
    {% endif %}
  {% endif %}


incus-database-present:
  file.exists:
    - name: {{ db_file }}

incus-init:
  cmd.run:
    - name: incus admin init --minimal
    - unless: test -f {{ db_file }}
    - require:
      - file: incus-database-present

  {#- Install dependencies -#}
  {% if incus.pkg.deps %}
incus-deps:
  pkg.installed:
    - pkgs: {{ incus.pkg.deps | tojson }}
    - require:
      - pkg: incus-package
  {% endif %}

{% endif %}
