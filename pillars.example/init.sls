incus:
  enable: true
  repo:

    debian:
      name: 'deb [arch=amd64] https://EXAMPLE/INCUS/DEBIAN bookworm main'
      human_name: 'Incus repository (example)'
      uri: 'https://EXAMPLE/INCUS/DEBIAN'
      dist: 'bookworm'
      comps:
        - main
      key_url: 'https://EXAMPLE/KEY.gpg'
    redhat:
      name: 'incus'
      baseurl: 'https://EXAMPLE/INCUS/RHEL/$releasever/$basearch'
      gpgkey: 'https://EXAMPLE/KEY.gpg'

  pkg:
    name: incus
    deps:
      - qemu-kvm
      - lxcfs
      - zfsutils-linux

  service:
    name: incus
    enable: true

  images:
    ubuntu2204:
      alias: ubuntu/22.04
      source:
        server: https://images.linuxcontainers.org
        alias: ubuntu/22.04
        protocol: simplestreams
      auto_update: true
      public: false
      description: Ubuntu 22.04 LTS

    debian12:
      alias: debian/12
      source:
        server: https://images.linuxcontainers.org
        alias: debian/12
        protocol: simplestreams
      auto_update: true
      public: false
      description: Debian 12 (Bookworm)

  instances:
    web-container:
      instance_type: container
      source:
        type: image
        alias: ubuntu/22.04
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
      profiles:
        - default
      ephemeral: false

  instance_snapshots:
    web-before-update:
      instance: web-container
      name: before-system-update
      stateful: false
      description: Snapshot before OS update

  storage:
    default:
      name: default
      config:
        driver: zfs
        source: tank/incus

  networks:
    - name: incusbr0
      config:
        ipv4.address: 10.0.0.1/24
        ipv4.nat: "true"
        ipv6.address: none

  profiles:
    - name: default
      config:
        limits.cpu: "2"
        limits.memory: 2GiB
      devices:
        root:
          type: disk
          path: /
          pool: default
