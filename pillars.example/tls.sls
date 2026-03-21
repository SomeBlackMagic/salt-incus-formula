incus:
  api_client:
    enabled: true

    storage:
      # local_files | sdb
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      # For SDB storage:
      # type: sdb
      # cert: sdb://vault/incus/client_cert
      # key: sdb://vault/incus/client_key

    generate:
      cn: salt-cloud
      days: 3650

    trust_import: true
    trust_name: salt-cloud
    trust_restricted: false

  # salt-cloud / execution-module HTTPS connection should point
  # to the same certificate/key material.
  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: true
