incus:
  enable: true

  api_client:
    enabled: true
    storage:
      type: sdb
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
    generate:
      cn: salt-cloud
      days: 3650
    trust_import: true
    trust_name: salt-cloud
    trust_restricted: false

  # HTTPS API access uses the same cert/key from SDB.
  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      type: sdb
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
      verify: sdb://vault/incus/ca_cert
