{#-
  Install Incus and its OS-level dependencies.
  Supports both Debian and RedHat families.
  Package lists are defined via map.jinja (defaults + pillar overrides).
-#}
{% from tpldir ~ "/map.jinja" import incus with context %}

{% if incus.enable %}

  {% set os_family = grains.get("os_family") %}
  {% set codename = grains.get("oscodename", "bookworm") %}
  {% set repo = incus.get("repo") | default({}, true) %}
  {% set repo_debian = repo.get("debian") | default({}, true) %}
  {% set repo_redhat = repo.get("redhat") | default({}, true) %}
  {% set pkg = incus.get("pkg") | default({}, true) %}
  {% set service = incus.get("service") | default({}, true) %}
  {% set incus_version = incus.get("version", None) %}
  {% set pkg_name = pkg.get("name", "incus") %}
  {% set db_file = '/var/lib/incus/database/local.db' %}

  {#- Debian/Ubuntu repository setup -#}
  {% if repo.get("enable") and os_family == "Debian" %}
    {% set arch = repo_debian.get("architecture", "amd64") %}
    {% set repo_channel = repo.get("channel", "stable") %}
    {% set key_url = repo_debian.get("key_url", "https://pkgs.zabbly.com/key.asc") %}

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

incus-repo:
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
  {% if repo.get("enable") and os_family == "RedHat" %}
  {% set repo_name = repo_redhat.get("name", "incus-stable") %}
  {% set baseurl = repo_redhat.get("baseurl", "https://pkgs.zabbly.com/incus/stable/rpm/$releasever/$basearch") %}
  {% set gpgkey = repo_redhat.get("gpgkey", "https://pkgs.zabbly.com/key.asc") %}
  {% set repo_enabled = repo_redhat.get("enabled", 1) %}
  {% set gpgcheck = repo_redhat.get("gpgcheck", 1) %}

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
    {% if repo.get("enable") %}
    - refresh: True
    {% if os_family == "Debian" %}
    - require:
      - file: incus-repo
    {% elif os_family == "RedHat" %}
    - require:
      - pkgrepo: incus-repo
    {% endif %}
    {% endif %}


incus-service:
  service.running:
    - name: {{ service.get("name", "incus") }}
    - enable: {{ service.get("enable", True) }}
    - require:
      - pkg: incus-package

incus-init:
  cmd.run:
    - name: incus admin init --minimal
    - unless: test -f {{ db_file }}
    - require:
      - service: incus-service

  {#- Install dependencies -#}
  {% if pkg.get("deps") %}
incus-deps:
  pkg.installed:
    - pkgs: {{ pkg.get("deps") | tojson }}
    - require:
      - pkg: incus-package
  {% endif %}

{% endif %}
