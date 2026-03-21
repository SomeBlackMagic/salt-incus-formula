# ТЗ: Система управления TLS-ключами для Incus API

## 1. Обзор

Задача — добавить в formula поддержку клиентских TLS-сертификатов для
аутентификации в Incus REST API. Система должна поддерживать два сценария
хранения (локальные файлы и SDB) и три фазы жизненного цикла: генерацию
ключей, импорт в trust store Incus, и использование в salt-cloud.

**Основной флоу:**

1. Оператор вручную запускает `salt-call incus_pki.generate_keypair` до
   `state.apply`, ключевая пара создаётся и сохраняется в выбранное хранилище.
2. Во время применения formula при `incus:api_client:trust_import: true`
   сертификат импортируется в trust store локального Incus.
3. Для HTTPS-подключения `salt-cloud` использует те же cert/key из выбранного
   хранилища (local files или SDB).
 
---

## 2. Компоненты

### Новые файлы

| Файл                      | Тип              | Назначение                                                                   |
|---------------------------|------------------|------------------------------------------------------------------------------|
| `_modules/incus_pki.py`   | Execution module | Генерация ключей, чтение из хранилища, работа с Incus trust API              |
| `_states/incus_pki.py`    | State module     | Декларативное управление: `keypair_present`, `trust_present`, `trust_absent` |
| `tls.sls`                 | Salt state       | Оркестрация: вызывает состояния в правильном порядке                         |
| `pillars.example/tls.sls` | Pillar example   | Пример конфигурации                                                          |

### Изменяемые файлы

| Файл                | Изменение                                                       |
|---------------------|-----------------------------------------------------------------|
| `_modules/incus.py` | Добавить `trust_list`, `trust_get`, `trust_add`, `trust_remove` |
| `defaults.yaml`     | Добавить секцию `api_client` с дефолтами                        |
| `init.sls`          | Включить `tls.sls`                                              |
 
---

## 3. Структура Pillar

```yaml
incus:
  api_client:
    enabled: true
 
    # Хранилище для ключей
    storage:
      type: local_files    # "local_files" | "sdb"
      cert: /etc/salt/pki/incus/client.crt
      key:  /etc/salt/pki/incus/client.key
      # При type: sdb:
      # cert: sdb://vault/incus/client_cert
      # key:  sdb://vault/incus/client_key
 
    # Параметры генерации сертификата
    generate:
      cn:   salt-cloud
      days: 3650
 
    # Импорт в trust store Incus
    trust_import:    true
    trust_name:      salt-cloud
    trust_restricted: false
```

Каноничное имя флага импорта — `incus:api_client:trust_import`.

Секция `incus.connection` (уже существует) используется для HTTPS-подключения
salt-cloud — **без изменений**, просто указывает на те же cert/key.
 
---

## 4. Фаза 1 — Генерация ключей (`salt-call`)

### `incus_pki.generate_keypair`

**Назначение:** генерация EC P-384 ключевой пары и сохранение в хранилище.
Запускается оператором вручную перед применением formula.

**Сигнатура:**

```
incus_pki.generate_keypair(cn=None, days=None, storage=None, force=False)
```

**Поведение:**

- Читает `incus:api_client` из pillar, если параметры не переданы явно.
- Если сертификат уже существует в хранилище → возвращает
  `{"success": True, "changed": False}` (не перезаписывает).
- При `force=True` → перегенерирует всегда.
- Создаёт директории хранилища если не существуют.
- Права на файлы: cert `0644`, key `0600`.
- При `type: sdb` — пишет PEM-строки через `salt.utils.sdb.sdb_set`.

**Возвращает:**

```python
{
    "success": True | False,
    "changed": True | False,
    "comment": "...",
    "fingerprint": "sha256hex",  # опционально
    "error": "..."               # при success=False
}
```
 
---

## 5. Фаза 2 — Импорт в Incus trust store

### Новые функции в `_modules/incus.py`

Используют существующий `_client()` (Unix socket), вызываются через
`__salt__["incus.*"]`:

| Функция | Метод/Путь | Описание |
|---------|-----------|----------|
| `trust_list()` | `GET /1.0/certificates?recursion=1` | Список доверенных сертификатов |
| `trust_get(fingerprint)` | `GET /1.0/certificates/{fingerprint}` | Получить конкретный сертификат |
| `trust_add(cert_pem, name, restricted)` | `POST /1.0/certificates` | Добавить сертификат |
| `trust_remove(fingerprint)` | `DELETE /1.0/certificates/{fingerprint}` | Удалить сертификат |

Fingerprint — SHA-256 DER-кодировки сертификата, lowercase hex без двоеточий
(формат Incus API).

`trust_add` использует payload:

```json
{
  "type": "client",
  "certificate": "<PEM>",
  "name": "<trust_name>",
  "restricted": false
}
```

### Вспомогательные функции в `_modules/incus_pki.py`

```
incus_pki.trust_add_from_storage(name=None, storage=None, restricted=False)
```

**Поведение:**

1. Читает cert из хранилища.
2. Вычисляет fingerprint.
3. Вызывает `trust_list()` → проверяет наличие fingerprint.
4. Если уже есть → `{"changed": False}` (идемпотентность).
5. Если fingerprint есть, но `name`/`restricted` отличаются от desired state
   → выполняет `recreate` (`trust_remove` + `trust_add`).
6. Если fingerprint нет → вызывает `trust_add()`.

```
incus_pki.trust_present_check(cert_pem=None, storage=None)
```

Возвращает `True / False / None` (None — ошибка подключения к Incus).

```
incus_pki.trust_remove_from_storage(storage=None)
```

Зеркальная функция: находит по fingerprint, удаляет если найден.

```
incus_pki.cert_get(storage=None)
incus_pki.key_get(storage=None)
incus_pki.cert_fingerprint(cert_pem=None, storage=None)
```
 
---

## 6. Модуль состояний `_states/incus_pki.py`

### `keypair_present(name, storage=None, generate=None, force=False)`

| Сценарий | `result` | `changed` | Действие |
|----------|----------|-----------|---------|
| Cert уже в хранилище | `True` | `False` | ничего |
| Cert отсутствует, `test=True` | `None` | — | сообщение "would generate" |
| Cert отсутствует, `test=False` | `True` | `True` | генерирует и сохраняет |
| Ошибка генерации/записи | `False` | `False` | сообщение об ошибке |

### `trust_present(name, storage=None, restricted=False)`

| Сценарий | `result` | `changed` | Действие |
|----------|----------|-----------|---------|
| Уже в trust store | `True` | `False` | ничего |
| Нет cert в хранилище | `False` | `False` | ошибка |
| Fingerprint есть, но `name/restricted` отличаются, `test=True` | `None` | — | сообщение "would recreate" |
| Fingerprint есть, но `name/restricted` отличаются, `test=False` | `True` | `True` | удаляет и добавляет заново |
| Не в trust, `test=True` | `None` | — | сообщение "would add" |
| Не в trust, `test=False` | `True` | `True` | импортирует |
| API ошибка | `False` | `False` | сообщение об ошибке |

### `trust_absent(name, storage=None)`

Зеркальная логика: проверяет по fingerprint, удаляет если найден.
Поддерживает `test=True`.
 
---

## 7. `tls.sls` — оркестрация

```jinja
{%- from tpldir ~ "/map.jinja" import incus with context %}
{%- set api_client = incus.get("api_client", {}) %}
{%- set storage    = api_client.get("storage", {}) %}

{%- if api_client.get("enabled", False) and api_client.get("trust_import", False) %}
incus-api-client-trust:
  incus_pki.trust_present:
    - name: {{ api_client.get("trust_name", "salt-cloud") }}
    - storage: {{ storage | tojson }}
    - restricted: {{ api_client.get("trust_restricted", False) }}
    - require:
      - service: incus-service   # Incus должен быть запущен
{%- endif %}
```

`tls.sls` не генерирует ключевую пару автоматически: по основному флоу
генерация выполняется отдельно через `salt-call incus_pki.generate_keypair`.
Предусловие: состояние `incus-service` уже присутствует в highstate
(обычно через `incus.enable: true`).
 
---

## 8. `defaults.yaml` — новая секция

```yaml
default:
  api_client:
    enabled: false
    storage:
      type: local_files
      cert: /etc/salt/pki/incus/client.crt
      key:  /etc/salt/pki/incus/client.key
    generate:
      cn:   salt-cloud
      days: 3650
    trust_import:    false
    trust_name:      salt-cloud
    trust_restricted: false
```
 
---

## 9. Зависимости

| Библиотека     | Где используется        | Обоснование                                                                   |
|----------------|-------------------------|-------------------------------------------------------------------------------|
| `cryptography` | `_modules/incus_pki.py` | Генерация EC-ключей, вычисление fingerprint. Входит в зависимости Salt ≥ 3006 |
 
---

## 10. Требования к реализации

1. **Идемпотентность** — все функции и состояния безопасно вызывать повторно.
2. **`test=True`** — все state-функции поддерживают dry-run:
   `result=None`, пустые `changes`, описательный `comment`.
3. **Изоляция хранилищ** — логика `local_files` / `sdb` сосредоточена в
   helper-функциях `_storage_read` / `_storage_write`, не размазана по коду.
4. **Нет дублирования** — клиентский код (UnixSocket, HTTPS session) уже есть
   в `_modules/incus.py`; `incus_pki.py` вызывает `incus.trust_*` через
   `__salt__`.
5. **Логирование** — все операции логируются через `log.info` / `log.error`.
6. **Права доступа** — key: `0600`, cert: `0644`, директории: `0700`.
7. **Контракт exec-функций** — возвращают единый формат:
   `success`, `changed`, `comment`, опционально `fingerprint`, `error`.
8. **Поведение trust drift** — при несовпадении `name/restricted` используется
   стратегия `recreate` (delete + add).
9. **Отсутствие cert в хранилище** — для `trust_present` это ошибка:
   `result=False`, `changes={}`, понятный `comment`.
