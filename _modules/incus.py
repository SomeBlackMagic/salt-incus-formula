"""
Salt execution module for managing Incus containers and VMs via API.

This module provides functions to interact with Incus API for managing:
- Instances (containers and VMs)
- Instance snapshots
- Storage pools and volumes
- Networks
- Profiles
- Cluster members

Supports both local (Unix socket) and remote (HTTPS) connections.

:configuration: Can be configured via pillar or minion config:
    
    incus:
      connection:
        type: unix  # or https
        socket: /var/lib/incus/unix.socket  # for unix type
        # For HTTPS type:
        # url: https://incus.example.com:8443
        # cert: /path/to/client.crt
        # key: /path/to/client.key
        # verify: True  # or False or /path/to/ca.crt

:depends: requests
"""

import json
import logging
import socket
import time
from urllib.parse import quote, urljoin

try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.connection import HTTPConnection
    from requests.packages.urllib3.connectionpool import HTTPConnectionPool
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

log = logging.getLogger(__name__)

__virtualname__ = "incus"


def __virtual__():
    if not HAS_REQUESTS:
        return False, "python-requests is required"
    return __virtualname__


# ==============================================================
# DEFAULT CONFIG + DEEP MERGE
# ==============================================================

INCUS_SOCKET_PATH = "/var/lib/incus/unix.socket"

DEFAULT_CFG = {
    "connection": {
        "type": "unix",                  # "unix" | "https"
        "socket": INCUS_SOCKET_PATH,     # path to unix socket
        "url": None,                     # https URL for remote, e.g. https://incus.example.com:8443
        "cert": None,                    # client cert
        "key": None,                     # client key
        "verify": True,                  # verify=True|False|/path/to/ca.crt
    }
}


def deep_merge(base, override):
    """
    Recursively merge override into base.
    """
    for k, v in override.items():
        if (
            k in base
            and isinstance(base[k], dict)
            and isinstance(v, dict)
        ):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


# ==============================================================
# UNIX SOCKET BACKEND
# ==============================================================

class UnixHTTPConnection(HTTPConnection):
    """
    HTTPConnection over Unix socket.
    """

    def __init__(self, unix_socket=INCUS_SOCKET_PATH, **kwargs):
        # host/port are dummy values, used only for format
        super().__init__("localhost", **kwargs)
        self.unix_socket = unix_socket

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.unix_socket)


class UnixHTTPConnectionPool(HTTPConnectionPool):
    """
    Connection pool returning UnixHTTPConnection.
    """

    ConnectionCls = UnixHTTPConnection

    def __init__(self, socket_path=INCUS_SOCKET_PATH, **kwargs):
        super().__init__("localhost", **kwargs)
        self.socket_path = socket_path

    def _new_conn(self):
        return self.ConnectionCls(unix_socket=self.socket_path)


class UnixSocketPoolManager:
    """
    Minimal PoolManager-compatible object for HTTPAdapter.

    Requests/HTTPAdapter expects poolmanager to have connection_from_host() method,
    which we implement here, returning UnixHTTPConnectionPool.
    """

    def __init__(self, socket_path=INCUS_SOCKET_PATH):
        self.socket_path = socket_path

    def connection_from_host(self, host, port=None, scheme="http", pool_kwargs=None):
        # host/port/scheme are ignored — we always use unix socket
        return UnixHTTPConnectionPool(self.socket_path)

    def connection_from_url(self, url, pool_kwargs=None):
        # url is ignored — we always use unix socket
        return UnixHTTPConnectionPool(self.socket_path)


class UnixHTTPAdapter(HTTPAdapter):
    """
    Requests adapter for Incus via unix socket.
    """

    def __init__(self, socket_path=INCUS_SOCKET_PATH, **kwargs):
        self.socket_path = socket_path
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        # substitute our custom PoolManager instead of the standard one
        self.poolmanager = UnixSocketPoolManager(self.socket_path)

    def proxy_manager_for(self, *args, **kwargs):
        # proxies are not applicable for unix socket
        return None

    def request_url(self, request, proxies):
        # Actual transport is AF_UNIX, URL is only needed for formal HTTP
        return "http://localhost" + request.path_url


# ==============================================================
# CLIENT
# ==============================================================

class IncusClient:
    def __init__(self, config=None):
        self.config = config or self._load_config()
        self.session = self._create_session()
        self.base_url = self._get_base_url()

    def _load_config(self):
        pillar_cfg = __salt__.get("config.get", lambda *_: {})("incus", {})
        return deep_merge(DEFAULT_CFG.copy(), pillar_cfg)

    def _create_session(self):
        session = requests.Session()
        conn = self.config.get("connection", {})
        ctype = conn.get("type", "unix")

        # ============================================
        # LOCAL UNIX SOCKET
        # ============================================
        if ctype == "unix":
            adapter = UnixHTTPAdapter(conn.get("socket", INCUS_SOCKET_PATH))

            # Just in case, disable TLS/proxy inheritance from environment
            session.verify = False
            session.cert = None
            session.trust_env = False

            # Mount adapter on both schemes so that any https transitions
            # inside requests don't bypass our adapter
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            return session

        # ============================================
        # REMOTE HTTPS
        # ============================================
        elif ctype == "https":
            if conn.get("cert") and conn.get("key"):
                session.cert = (conn["cert"], conn["key"])
            session.verify = conn.get("verify", True)
            return session

        raise ValueError(f"Unsupported connection type: {ctype}")

    def _get_base_url(self):
        conn = self.config.get("connection", {})
        ctype = conn.get("type", "unix")

        if ctype == "unix":
            # host is dummy, only path /1.0 matters
            return "http://localhost/1.0"

        if ctype == "https":
            url = conn.get("url")
            if not url:
                raise ValueError("HTTPS connection requires url=")
            return url.rstrip("/") + "/1.0"

        raise ValueError(f"Unsupported connection type: {ctype}")

    # ==========================================================
    # REQUEST API
    # ==========================================================

    def _request(self, method, endpoint, data=None, params=None):
        # Build URL: if endpoint is empty, use base_url as-is
        # Otherwise join with slash separator
        if endpoint:
            url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        else:
            url = self.base_url

        try:
            response = self.session.request(
                method,
                url,
                json=data,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:

            # Enhanced error logging for 5xx errors
            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code

                # Log detailed information for server errors (5xx)
                if 500 <= status_code < 600:
                    log.error("=" * 60)
                    log.error("Incus API Server Error (HTTP %d)", status_code)
                    log.error("=" * 60)
                    log.error("Request URL: %s %s", method, url)
                    log.error("Request params: %s", params)
                    log.error("Request data (JSON): %s", json.dumps(data, indent=2) if data else "None")

                    try:
                        error_body = e.response.json()
                        log.error("Response body: %s", json.dumps(error_body, indent=2))

                        # Extract error message from Incus API response
                        if isinstance(error_body, dict):
                            if "error" in error_body:
                                log.error("Incus error message: %s", error_body["error"])
                            if "metadata" in error_body and isinstance(error_body["metadata"], dict):
                                if "err" in error_body["metadata"]:
                                    log.error("Incus metadata error: %s", error_body["metadata"]["err"])
                    except Exception:
                        # If response is not JSON, log raw text
                        log.error("Response body (raw): %s", e.response.text)

                    log.error("=" * 60)

            return {
                "error": str(e),
                "error_code": getattr(getattr(e, "response", None), "status_code", None),
            }

    def _wait_for_operation(self, operation_url, timeout=300, interval=1):
        """
        Wait for an Incus async operation to finish.

        :param operation_url: e.g. "/1.0/operations/abc-123"
        :param timeout: maximum seconds to wait
        :param interval: poll interval
        :return: dict {
            "success": bool,
            "operation": <operation dict>,
            "error": <error or None>
        }

        Incus operation states:
          100 - Operation created
          101 - Started
          103 - Running
          200 - Success
          400 - Failure
        """

        client = _client()
        started = time.time()

        # Operations must begin with /1.0/operations
        if not operation_url.startswith("/1.0/operations/"):
            return {
                "success": False,
                "error": f"Invalid operation URL: {operation_url}"
            }

        while True:
            # Timeout
            if time.time() - started > timeout:
                return {
                    "success": False,
                    "error": "Timeout waiting for operation to finish"
                }

            # Query operation state
            result = client._sync_request("GET", operation_url.replace("/1.0/", "/"))

            if result.get("error_code") != 0:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "operation": result,
                }

            # Structure: result["metadata"] contains the operation itself
            op = result.get("metadata", {})
            status_code = op.get("status_code")

            # Running: 100, 101, 103
            if status_code in (100, 101, 103):
                time.sleep(interval)
                continue

            # Success
            if status_code == 200:
                return result

            # Failure
            if status_code == 400:
                return {
                    "success": False,
                    "operation": op,
                    "error": op.get("err", "Operation failed"),
                }

            # Unknown code (just in case)
            return {
                "success": False,
                "operation": op,
                "error": f"Unexpected status_code: {status_code}"
            }

    def _sync_request(self, method, endpoint, data=None, params=None):
        result = self._request(method, endpoint, data=data, params=params)

        if result.get('error_code', "")!= 0:
            return result

        if result.get("type") == "async":
            op = result.get("operation")
            if op:
                return self._wait_for_operation(op)

        return result


def _client():
    return IncusClient()

# ========== Instance Management Functions ==========

def instance_list(recursion=0):
    """
    List all instances (containers and VMs)

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_list
        salt '*' incus.instance_list recursion=1

    :param recursion: Recursion level (0=URLs, 1=basic info, 2=full info)
    :return: List of instances
    """
    client = _client()
    result = client._request('GET', '/instances', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'instances': result.get('metadata', [])}


def instance_get(name):
    """
    Get instance information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_get mycontainer

    :param name: Instance name
    :return: Instance information
    """
    client = _client()
    result = client._request('GET', f'/instances/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'instance': result.get('metadata', {})}


def instance_create(name, source=None, instance_type='container', config=None, devices=None, profiles=None, ephemeral=False):
    """
    Create a new instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_create mycontainer source="{'type':'image','alias':'ubuntu/22.04'}"
        salt '*' incus.instance_create myvm instance_type=virtual-machine source="{'type':'image','alias':'ubuntu/22.04'}"

    :param name: Instance name
    :param source: Source configuration (image, copy, migration, none)
    :param instance_type: Instance type (container or virtual-machine)
    :param config: Instance configuration
    :param devices: Device configuration
    :param profiles: List of profiles to apply
    :param ephemeral: Whether instance is ephemeral
    :return: Result
    """
    client = _client()

    data = {
        'name': name,
        'type': instance_type,
        'ephemeral': ephemeral
    }

    if source:
        data['source'] = source

    if config:
        data['config'] = config

    if devices:
        data['devices'] = devices

    if profiles:
        data['profiles'] = profiles

    result = client._sync_request('POST', '/instances', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} created successfully'}


def instance_delete(name, force=False):
    """
    Delete an instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_delete mycontainer
        salt '*' incus.instance_delete mycontainer force=True

    :param name: Instance name
    :param force: Force deletion
    :return: Result
    """
    client = _client()

    # Stop instance if running and force is True
    if force:
        instance_info = instance_get(name)
        if instance_info.get('success') and instance_info.get('instance', {}).get('status') == 'Running':
            instance_stop(name, force=True)

    result = client._sync_request('DELETE', f'/instances/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} deleted successfully'}


def instance_update(name, config=None, devices=None, profiles=None):
    """
    Update instance configuration

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_update mycontainer config="{'limits.cpu':'2'}"

    :param name: Instance name
    :param config: Configuration to update
    :param devices: Devices to update
    :param profiles: Profiles to apply
    :return: Result
    """
    client = _client()

    # Get current instance config
    current = instance_get(name)
    if not current.get('success'):
        return current

    instance_data = current['instance']

    # Update fields
    if config:
        instance_data['config'].update(config)

    if devices:
        # Deep merge devices: update properties within existing devices
        for dev_name, dev_conf in devices.items():
            if dev_name in instance_data['devices']:
                # Device exists, merge properties
                instance_data['devices'][dev_name].update(dev_conf)
            else:
                # New device, add it
                instance_data['devices'][dev_name] = dev_conf

    if profiles is not None:
        instance_data['profiles'] = profiles

    result = client._sync_request('PUT', f'/instances/{quote(name)}', data=instance_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} updated successfully'}


def instance_start(name, force=False, stateful=False):
    """
    Start an instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_start mycontainer

    :param name: Instance name
    :param force: Force start
    :param stateful: Restore state
    :return: Result
    """
    client = _client()

    data = {
        'action': 'start',
        'force': force,
        'stateful': stateful
    }

    result = client._sync_request('PUT', f'/instances/{quote(name)}/state', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} started successfully'}


def instance_stop(name, force=False, stateful=False, timeout=30):
    """
    Stop an instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_stop mycontainer
        salt '*' incus.instance_stop mycontainer force=True

    :param name: Instance name
    :param force: Force stop
    :param stateful: Save state
    :param timeout: Timeout in seconds
    :return: Result
    """
    client = _client()

    data = {
        'action': 'stop',
        'force': force,
        'stateful': stateful,
        'timeout': timeout
    }

    result = client._sync_request('PUT', f'/instances/{quote(name)}/state', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} stopped successfully'}


def instance_restart(name, force=False, timeout=30):
    """
    Restart an instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_restart mycontainer

    :param name: Instance name
    :param force: Force restart
    :param timeout: Timeout in seconds
    :return: Result
    """
    client = _client()

    data = {
        'action': 'restart',
        'force': force,
        'timeout': timeout
    }

    result = client._sync_request('PUT', f'/instances/{quote(name)}/state', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {name} restarted successfully'}


def instance_wait_ready(name, timeout=300, interval=2):
    """
    Wait for instance to be fully ready (incus-agent is responsive)

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_wait_ready myvm
        salt '*' incus.instance_wait_ready myvm timeout=600

    :param name: Instance name
    :param timeout: Maximum seconds to wait (default: 300)
    :param interval: Poll interval in seconds (default: 2)
    :return: Result dict with success status
    """
    client = _client()
    started = time.time()

    log.info(f"Waiting for instance '{name}' to become ready (timeout: {timeout}s)")

    while time.time() - started < timeout:
        # Try to execute a simple command to check if incus-agent is ready
        data = {
            'command': ['/bin/true'],
            'wait-for-websocket': False,
            'interactive': False
        }

        result = client._sync_request('POST', f'/instances/{quote(name)}/exec', data=data)

        # If exec succeeds, the agent is ready
        if result.get('error_code') == 0:
            elapsed = time.time() - started
            log.info(f"Instance '{name}' is ready after {elapsed:.1f}s")
            return {
                'success': True,
                'message': f'Instance {name} is ready',
                'elapsed_time': elapsed
            }

        # Log the error for debugging
        error_msg = result.get('error', 'Unknown error')
        log.debug(f"Instance '{name}' not ready yet: {error_msg}")

        # Wait before next check
        time.sleep(interval)

    # Timeout reached
    elapsed = time.time() - started
    log.warning(f"Timeout waiting for instance '{name}' to become ready ({elapsed:.1f}s)")
    return {
        'success': False,
        'error': f'Timeout waiting for instance to become ready after {elapsed:.1f}s'
    }


# ========== Instance Snapshot Management Functions ==========

def instance_snapshot_list(instance, recursion=0):
    """
    List snapshots of an instance

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_list mycontainer
        salt '*' incus.instance_snapshot_list mycontainer recursion=1

    :param instance: Instance name
    :param recursion: Recursion level (0=URLs, 1=basic info, 2=full info)
    :return: List of snapshots
    """
    client = _client()
    result = client._request('GET', f'/instances/{quote(instance)}/snapshots',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'snapshots': result.get('metadata', [])}


def instance_snapshot_get(instance, snapshot_name):
    """
    Get information about an instance snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_get mycontainer snap1

    :param instance: Instance name
    :param snapshot_name: Snapshot name
    :return: Snapshot information
    """
    client = _client()
    result = client._request('GET', f'/instances/{quote(instance)}/snapshots/{quote(snapshot_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'snapshot': result.get('metadata', {})}


def instance_snapshot_create(instance, snapshot_name, stateful=False, description=''):
    """
    Create a snapshot of an instance

    Snapshots capture the state of an instance at a point in time.
    They can be stateless (filesystem only) or stateful (includes runtime state/memory).

    Stateless snapshots:
    - Support both containers and VMs
    - Only capture filesystem state
    - Fast to create and restore
    - Smaller storage footprint
    - Instance can be stopped or running

    Stateful snapshots:
    - Only supported for virtual machines
    - Include memory and runtime state
    - VM must be running for stateful snapshot
    - Larger size than stateless snapshots
    - Slower to create and restore

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_create mycontainer snap1
        salt '*' incus.instance_snapshot_create mycontainer before-update description="Before system update"
        salt '*' incus.instance_snapshot_create myvm running-state stateful=True description="VM with running state"

    :param instance: Instance name
    :param snapshot_name: Snapshot name
    :param stateful: Whether to include runtime state (only for VMs)
    :param description: Snapshot description
    :return: Result
    """
    client = _client()

    data = {
        'name': snapshot_name,
        'stateful': stateful
    }

    if description:
        data['description'] = description

    result = client._sync_request('POST', f'/instances/{quote(instance)}/snapshots', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} of instance {instance} created successfully'}


def instance_snapshot_rename(instance, snapshot_name, new_name):
    """
    Rename an instance snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_rename mycontainer snap1 snap2

    :param instance: Instance name
    :param snapshot_name: Current snapshot name
    :param new_name: New snapshot name
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/instances/{quote(instance)}/snapshots/{quote(snapshot_name)}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} renamed to {new_name} successfully'}


def instance_snapshot_restore(instance, snapshot_name, stateful=None):
    """
    Restore an instance to a previous snapshot state

    This operation will revert the instance to the state captured in the snapshot.
    The instance is typically stopped during restoration.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_restore mycontainer snap1
        salt '*' incus.instance_snapshot_restore myvm running-state stateful=True

    :param instance: Instance name
    :param snapshot_name: Snapshot name to restore from
    :param stateful: Whether to restore runtime state (only for stateful snapshots)
    :return: Result
    """
    client = _client()

    data = {
        'restore': snapshot_name
    }

    if stateful is not None:
        data['stateful'] = stateful

    result = client._sync_request('PUT', f'/instances/{quote(instance)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Instance {instance} restored from snapshot {snapshot_name} successfully'}


def instance_snapshot_delete(instance, snapshot_name):
    """
    Delete an instance snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_delete mycontainer snap1

    :param instance: Instance name
    :param snapshot_name: Snapshot name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/instances/{quote(instance)}/snapshots/{quote(snapshot_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} of instance {instance} deleted successfully'}


def instance_snapshot_update(instance, snapshot_name, description=None, expires_at=None):
    """
    Update instance snapshot metadata

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_update mycontainer snap1 description="Updated description"
        salt '*' incus.instance_snapshot_update mycontainer snap1 expires_at="2024-12-31T23:59:59Z"

    :param instance: Instance name
    :param snapshot_name: Snapshot name
    :param description: New description
    :param expires_at: Expiry date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
    :return: Result
    """
    client = _client()

    # Get current snapshot config
    current = client._request('GET', f'/instances/{quote(instance)}/snapshots/{quote(snapshot_name)}')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get snapshot')}

    snapshot_data = current.get('metadata', {})

    # Update fields
    if description is not None:
        snapshot_data['description'] = description

    if expires_at is not None:
        snapshot_data['expires_at'] = expires_at

    result = client._sync_request('PUT', f'/instances/{quote(instance)}/snapshots/{quote(snapshot_name)}',
                                  data=snapshot_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} updated successfully'}


def instance_snapshot_publish(instance, snapshot_name, properties=None, public=False, aliases=None):
    """
    Publish an instance snapshot as an image

    Create a reusable image from an instance snapshot. This allows you to
    create templates from configured instances.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_snapshot_publish mycontainer snap1
        salt '*' incus.instance_snapshot_publish mycontainer snap1 properties="{'os':'ubuntu','release':'22.04'}" public=True
        salt '*' incus.instance_snapshot_publish mycontainer snap1 aliases="['ubuntu-configured','web-template']"

    :param instance: Instance name
    :param snapshot_name: Snapshot name
    :param properties: Image properties dictionary
    :param public: Whether the image should be public
    :param aliases: List of image aliases
    :return: Result with image fingerprint
    """
    client = _client()

    data = {
        'public': public,
        'source': {
            'type': 'snapshot',
            'name': f'{instance}/{snapshot_name}'
        }
    }

    if properties:
        data['properties'] = properties

    if aliases:
        data['aliases'] = [{'name': a} if isinstance(a, str) else a for a in aliases]

    result = client._sync_request('POST', '/images', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    # Extract fingerprint from result
    metadata = result.get('metadata', {})
    fingerprint = metadata.get('fingerprint', 'unknown')

    return {
        'success': True,
        'message': f'Snapshot {snapshot_name} published as image successfully',
        'fingerprint': fingerprint
    }


# ========== Storage Management Functions ==========

def storage_pool_list(recursion=0):
    """
    List all storage pools

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_list

    :param recursion: Recursion level
    :return: List of storage pools
    """
    client = _client()
    result = client._request('GET', '/storage-pools', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'pools': result.get('metadata', [])}


def storage_pool_create(name, driver, config=None, description=''):
    """
    Create a storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_create mypool dir config="{'source':'/var/lib/incus/storage-pools/mypool'}"

    :param name: Pool name
    :param driver: Storage driver (dir, zfs, btrfs, lvm, ceph)
    :param config: Pool configuration
    :param description: Pool description
    :return: Result
    """
    client = _client()

    data = {
        'name': name,
        'driver': driver,
        'config': config or {},
        'description': description
    }

    result = client._sync_request('POST', '/storage-pools', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Storage pool {name} created successfully'}


def storage_pool_get(name):
    """
    Get storage pool information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_get mypool

    :param name: Pool name
    :return: Storage pool information
    """
    client = _client()
    result = client._request('GET', f'/storage-pools/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'pool': result.get('metadata', {})}


def storage_pool_update(name, config=None, description=None):
    """
    Update storage pool configuration

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_update mypool config="{'rsync.bwlimit':'100'}"

    :param name: Pool name
    :param config: Configuration to update
    :param description: Pool description to update
    :return: Result
    """
    client = _client()

    # Get current pool config
    current = client._request('GET', f'/storage-pools/{quote(name)}')
    if 'error' in current:
        return {'success': False, 'error': current['error']}

    pool_data = current.get('metadata', {})

    # Update fields
    if config:
        pool_data['config'].update(config)

    if description is not None:
        pool_data['description'] = description

    result = client._sync_request('PUT', f'/storage-pools/{quote(name)}', data=pool_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Storage pool {name} updated successfully'}


def storage_pool_rename(name, new_name):
    """
    Rename a storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_rename mypool mynewpool

    :param name: Current pool name
    :param new_name: New pool name
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/storage-pools/{quote(name)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Storage pool {name} renamed to {new_name} successfully'}


def storage_pool_resources(name):
    """
    Get storage pool resource usage information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_resources mypool

    :param name: Pool name
    :return: Storage pool resource information
    """
    client = _client()
    result = client._request('GET', f'/storage-pools/{quote(name)}/resources')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'resources': result.get('metadata', {})}


def storage_pool_delete(name):
    """
    Delete a storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' incus.storage_pool_delete mypool

    :param name: Pool name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/storage-pools/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Storage pool {name} deleted successfully'}


def volume_list(pool, recursion=0):
    """
    List volumes in a storage pool

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_list default

    :param pool: Pool name
    :param recursion: Recursion level
    :return: List of volumes
    """
    client = _client()
    result = client._request('GET', f'/storage-pools/{quote(pool)}/volumes',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'volumes': result.get('metadata', [])}


def volume_create(pool, name, volume_type='custom', config=None, description=''):
    """
    Create a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_create default myvolume

    :param pool: Pool name
    :param name: Volume name
    :param volume_type: Volume type (custom, image, container, virtual-machine)
    :param config: Volume configuration
    :param description: Volume description
    :return: Result
    """
    client = _client()

    data = {
        'name': name,
        'type': volume_type,
        'config': config or {},
        'description': description
    }

    result = client._sync_request('POST', f'/storage-pools/{quote(pool)}/volumes/{volume_type}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {name} created successfully'}


def volume_get(pool, name, volume_type='custom'):
    """
    Get storage volume information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_get default myvolume

    :param pool: Pool name
    :param name: Volume name
    :param volume_type: Volume type
    :return: Volume information
    """
    client = _client()
    result = client._request('GET',
                            f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'volume': result.get('metadata', {})}


def volume_update(pool, name, volume_type='custom', config=None, description=None):
    """
    Update storage volume configuration

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_update default myvolume config="{'size':'20GiB'}"

    :param pool: Pool name
    :param name: Volume name
    :param volume_type: Volume type
    :param config: Configuration to update
    :param description: Volume description to update
    :return: Result
    """
    client = _client()

    # Get current volume config
    current = client._request('GET',
                             f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(name)}')
    if 'error' in current:
        return {'success': False, 'error': current['error']}

    volume_data = current.get('metadata', {})

    # Update fields
    if config:
        volume_data['config'].update(config)

    if description is not None:
        volume_data['description'] = description

    result = client._sync_request('PUT',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(name)}',
                                  data=volume_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {name} updated successfully'}


def volume_rename(pool, name, new_name, volume_type='custom'):
    """
    Rename a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_rename default myvolume mynewvolume

    :param pool: Pool name
    :param name: Current volume name
    :param new_name: New volume name
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(name)}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {name} renamed to {new_name} successfully'}


def volume_copy(source_pool, source_volume, target_pool=None, target_volume=None,
                volume_type='custom', config=None):
    """
    Copy a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_copy default vol1 target_pool=default target_volume=vol2

    :param source_pool: Source pool name
    :param source_volume: Source volume name
    :param target_pool: Target pool name (defaults to source_pool)
    :param target_volume: Target volume name (defaults to source_volume)
    :param volume_type: Volume type
    :param config: Volume configuration for the copy
    :return: Result
    """
    client = _client()

    target_pool = target_pool or source_pool
    target_volume = target_volume or source_volume

    data = {
        'name': target_volume,
        'source': {
            'pool': source_pool,
            'name': source_volume,
            'type': volume_type
        },
        'config': config or {}
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(target_pool)}/volumes/{volume_type}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {source_volume} copied to {target_volume} successfully'}


def volume_create_from_snapshot(pool, volume, snapshot_name, new_volume_name,
                                 volume_type='custom', config=None):
    """
    Create a new volume from a snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_create_from_snapshot default myvolume snap1 restored_volume

    :param pool: Pool name
    :param volume: Source volume name
    :param snapshot_name: Snapshot name to create from
    :param new_volume_name: Name for the new volume
    :param volume_type: Volume type
    :param config: Volume configuration for the new volume
    :return: Result
    """
    client = _client()

    data = {
        'name': new_volume_name,
        'source': {
            'pool': pool,
            'name': volume,
            'type': volume_type,
            'snapshot': snapshot_name
        },
        'config': config or {}
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {new_volume_name} created from snapshot {snapshot_name} successfully'}


def volume_move(source_pool, source_volume, target_pool, target_volume=None,
                volume_type='custom'):
    """
    Move a storage volume to another pool

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_move pool1 vol1 pool2
        salt '*' incus.volume_move pool1 vol1 pool2 target_volume=vol2

    :param source_pool: Source pool name
    :param source_volume: Source volume name
    :param target_pool: Target pool name
    :param target_volume: Target volume name (defaults to source_volume)
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()

    target_volume = target_volume or source_volume

    data = {
        'name': target_volume,
        'pool': target_pool
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(source_pool)}/volumes/{volume_type}/{quote(source_volume)}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {source_volume} moved to pool {target_pool} successfully'}


def volume_snapshot_list(pool, volume, volume_type='custom', recursion=0):
    """
    List snapshots of a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_list default myvolume
        salt '*' incus.volume_snapshot_list default myvolume recursion=1

    :param pool: Pool name
    :param volume: Volume name
    :param volume_type: Volume type
    :param recursion: Recursion level
    :return: List of snapshots
    """
    client = _client()
    result = client._request('GET',
                            f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}/snapshots',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'snapshots': result.get('metadata', [])}


def volume_snapshot_create(pool, volume, snapshot_name, volume_type='custom', description=''):
    """
    Create a snapshot of a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_create default myvolume snap1

    :param pool: Pool name
    :param volume: Volume name
    :param snapshot_name: Snapshot name
    :param volume_type: Volume type
    :param description: Snapshot description
    :return: Result
    """
    client = _client()

    data = {
        'name': snapshot_name,
        'description': description
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}/snapshots',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} of volume {volume} created successfully'}


def volume_snapshot_get(pool, volume, snapshot_name, volume_type='custom'):
    """
    Get information about a volume snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_get default myvolume snap1

    :param pool: Pool name
    :param volume: Volume name
    :param snapshot_name: Snapshot name
    :param volume_type: Volume type
    :return: Snapshot information
    """
    client = _client()
    result = client._request('GET',
                            f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}/snapshots/{quote(snapshot_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'snapshot': result.get('metadata', {})}


def volume_snapshot_rename(pool, volume, snapshot_name, new_name, volume_type='custom'):
    """
    Rename a volume snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_rename default myvolume snap1 snap2

    :param pool: Pool name
    :param volume: Volume name
    :param snapshot_name: Current snapshot name
    :param new_name: New snapshot name
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}/snapshots/{quote(snapshot_name)}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} renamed to {new_name} successfully'}


def volume_snapshot_restore(pool, volume, snapshot_name, volume_type='custom'):
    """
    Restore a volume to a previous snapshot state

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_restore default myvolume snap1

    :param pool: Pool name
    :param volume: Volume name
    :param snapshot_name: Snapshot name to restore from
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()

    data = {
        'restore': snapshot_name
    }

    result = client._sync_request('PUT',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}',
                                  data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {volume} restored from snapshot {snapshot_name} successfully'}


def volume_snapshot_delete(pool, volume, snapshot_name, volume_type='custom'):
    """
    Delete a volume snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_snapshot_delete default myvolume snap1

    :param pool: Pool name
    :param volume: Volume name
    :param snapshot_name: Snapshot name
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(volume)}/snapshots/{quote(snapshot_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Snapshot {snapshot_name} of volume {volume} deleted successfully'}


def volume_delete(pool, name, volume_type='custom'):
    """
    Delete a storage volume

    CLI Example:

    .. code-block:: bash

        salt '*' incus.volume_delete default myvolume

    :param pool: Pool name
    :param name: Volume name
    :param volume_type: Volume type
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE',
                                  f'/storage-pools/{quote(pool)}/volumes/{volume_type}/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Volume {name} deleted successfully'}


# ========== Network Management Functions ==========

def network_list(recursion=0):
    """
    List all networks

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_list

    :param recursion: Recursion level
    :return: List of networks
    """
    client = _client()
    result = client._request('GET', '/networks', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'networks': result.get('metadata', [])}


def network_create(name, network_type='bridge', config=None, description=''):
    """
    Create a network

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_create mybr0 config="{'ipv4.address':'10.0.0.1/24','ipv4.nat':'true'}"

    :param name: Network name
    :param network_type: Network type (bridge, macvlan, sriov, ovn, physical)
    :param config: Network configuration
    :param description: Network description
    :return: Result
    """
    client = _client()

    data = {
        'name': name,
        'type': network_type,
        'config': config or {},
        'description': description
    }

    result = client._sync_request('POST', '/networks', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network {name} created successfully'}


def network_get(name):
    """
    Get network information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_get mybr0

    :param name: Network name
    :return: Network information
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'network': result.get('metadata', {})}


def network_delete(name):
    """
    Delete a network

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_delete mybr0

    :param name: Network name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/networks/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network {name} deleted successfully'}


def network_update(name, config):
    """
    Update network configuration

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_update mybr0 config="{'ipv4.nat':'false'}"

    :param name: Network name
    :param config: Configuration to update
    :return: Result
    """
    client = _client()

    # Get current network config
    current = client._request('GET', f'/networks/{quote(name)}')
    if 'error' in current:
        return {'success': False, 'error': current['error']}

    network_data = current.get('metadata', {})
    network_data['config'].update(config)

    result = client._sync_request('PUT', f'/networks/{quote(name)}', data=network_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network {name} updated successfully'}


def network_rename(name, new_name):
    """
    Rename a network

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_rename mybr0 mybr1

    :param name: Current network name
    :param new_name: New network name
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/networks/{quote(name)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network {name} renamed to {new_name} successfully'}


def network_state(name):
    """
    Get network state information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_state mybr0

    :param name: Network name
    :return: Network state information
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(name)}/state')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'state': result.get('metadata', {})}


def network_lease_list(name):
    """
    List DHCP leases for a network

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_lease_list mybr0

    :param name: Network name
    :return: List of DHCP leases
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(name)}/leases')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'leases': result.get('metadata', [])}


# ========== Network ACL Management Functions ==========

def network_acl_list(recursion=0):
    """
    List all network ACLs

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_list
        salt '*' incus.network_acl_list recursion=1

    :param recursion: Recursion level
    :return: List of network ACLs
    """
    client = _client()
    result = client._request('GET', '/network-acls', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'acls': result.get('metadata', [])}


def network_acl_get(name):
    """
    Get network ACL information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_get myacl

    :param name: ACL name
    :return: ACL information
    """
    client = _client()
    result = client._request('GET', f'/network-acls/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'acl': result.get('metadata', {})}


def network_acl_create(name, config=None, description='', egress=None, ingress=None):
    """
    Create a network ACL

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_create myacl
        salt '*' incus.network_acl_create myacl ingress="[{'action':'allow','source':'10.0.0.0/24'}]"

    :param name: ACL name
    :param config: ACL configuration
    :param description: ACL description
    :param egress: List of egress rules
    :param ingress: List of ingress rules
    :return: Result
    """
    client = _client()

    data = {
        'name': name,
        'config': config or {},
        'description': description,
        'egress': egress or [],
        'ingress': ingress or []
    }

    result = client._sync_request('POST', '/network-acls', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network ACL {name} created successfully'}


def network_acl_update(name, config=None, description=None, egress=None, ingress=None):
    """
    Update network ACL

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_update myacl ingress="[{'action':'deny','source':'192.168.1.0/24'}]"

    :param name: ACL name
    :param config: Configuration to update
    :param description: Description to update
    :param egress: Egress rules to update
    :param ingress: Ingress rules to update
    :return: Result
    """
    client = _client()

    # Get current ACL config
    current = network_acl_get(name)
    if not current.get('success'):
        return current

    acl_data = current['acl']

    if config:
        acl_data['config'].update(config)

    if description is not None:
        acl_data['description'] = description

    if egress is not None:
        acl_data['egress'] = egress

    if ingress is not None:
        acl_data['ingress'] = ingress

    result = client._sync_request('PUT', f'/network-acls/{quote(name)}', data=acl_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network ACL {name} updated successfully'}


def network_acl_delete(name):
    """
    Delete a network ACL

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_delete myacl

    :param name: ACL name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/network-acls/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network ACL {name} deleted successfully'}


def network_acl_rename(name, new_name):
    """
    Rename a network ACL

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_acl_rename myacl myacl2

    :param name: Current ACL name
    :param new_name: New ACL name
    :return: Result
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/network-acls/{quote(name)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network ACL {name} renamed to {new_name} successfully'}


# ========== Network Forward Management Functions ==========

def network_forward_list(network, recursion=0):
    """
    List network forwards

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_forward_list mybr0

    :param network: Network name
    :param recursion: Recursion level
    :return: List of forwards
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(network)}/forwards',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'forwards': result.get('metadata', [])}


def network_forward_get(network, listen_address):
    """
    Get network forward information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_forward_get mybr0 10.0.0.1

    :param network: Network name
    :param listen_address: Listen address
    :return: Forward information
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(network)}/forwards/{quote(listen_address)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'forward': result.get('metadata', {})}


def network_forward_create(network, listen_address, config=None, description='', ports=None):
    """
    Create a network forward

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_forward_create mybr0 10.0.0.1 ports="[{'listen_port':'80','protocol':'tcp','target_address':'10.0.0.2','target_port':'8080'}]"

    :param network: Network name
    :param listen_address: Listen address
    :param config: Forward configuration
    :param description: Forward description
    :param ports: List of port forwards
    :return: Result
    """
    client = _client()

    data = {
        'listen_address': listen_address,
        'config': config or {},
        'description': description,
        'ports': ports or []
    }

    result = client._sync_request('POST', f'/networks/{quote(network)}/forwards', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network forward {listen_address} created successfully'}


def network_forward_update(network, listen_address, config=None, description=None, ports=None):
    """
    Update network forward

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_forward_update mybr0 10.0.0.1 ports="[{'listen_port':'443','protocol':'tcp','target_address':'10.0.0.3','target_port':'8443'}]"

    :param network: Network name
    :param listen_address: Listen address
    :param config: Configuration to update
    :param description: Description to update
    :param ports: Ports to update
    :return: Result
    """
    client = _client()

    # Get current forward config
    current = network_forward_get(network, listen_address)
    if not current.get('success'):
        return current

    forward_data = current['forward']

    if config:
        forward_data['config'].update(config)

    if description is not None:
        forward_data['description'] = description

    if ports is not None:
        forward_data['ports'] = ports

    result = client._sync_request('PUT', f'/networks/{quote(network)}/forwards/{quote(listen_address)}',
                                  data=forward_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network forward {listen_address} updated successfully'}


def network_forward_delete(network, listen_address):
    """
    Delete a network forward

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_forward_delete mybr0 10.0.0.1

    :param network: Network name
    :param listen_address: Listen address
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/networks/{quote(network)}/forwards/{quote(listen_address)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network forward {listen_address} deleted successfully'}


# ========== Network Peer Management Functions ==========

def network_peer_list(network, recursion=0):
    """
    List network peers

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_peer_list mybr0

    :param network: Network name
    :param recursion: Recursion level
    :return: List of peers
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(network)}/peers',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'peers': result.get('metadata', [])}


def network_peer_get(network, peer_name):
    """
    Get network peer information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_peer_get mybr0 peer1

    :param network: Network name
    :param peer_name: Peer name
    :return: Peer information
    """
    client = _client()
    result = client._request('GET', f'/networks/{quote(network)}/peers/{quote(peer_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'peer': result.get('metadata', {})}


def network_peer_create(network, peer_name, config=None, description='', target_network=None, target_project=None):
    """
    Create a network peer

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_peer_create mybr0 peer1 target_network=othernet target_project=otherproject

    :param network: Network name
    :param peer_name: Peer name
    :param config: Peer configuration
    :param description: Peer description
    :param target_network: Target network name
    :param target_project: Target project name
    :return: Result
    """
    client = _client()

    data = {
        'name': peer_name,
        'config': config or {},
        'description': description
    }

    if target_network:
        data['target_network'] = target_network

    if target_project:
        data['target_project'] = target_project

    result = client._sync_request('POST', f'/networks/{quote(network)}/peers', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network peer {peer_name} created successfully'}


def network_peer_update(network, peer_name, config=None, description=None, target_network=None, target_project=None):
    """
    Update network peer

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_peer_update mybr0 peer1 description="Updated peer"

    :param network: Network name
    :param peer_name: Peer name
    :param config: Configuration to update
    :param description: Description to update
    :param target_network: Target network to update
    :param target_project: Target project to update
    :return: Result
    """
    client = _client()

    # Get current peer config
    current = network_peer_get(network, peer_name)
    if not current.get('success'):
        return current

    peer_data = current['peer']

    if config:
        peer_data['config'].update(config)

    if description is not None:
        peer_data['description'] = description

    if target_network is not None:
        peer_data['target_network'] = target_network

    if target_project is not None:
        peer_data['target_project'] = target_project

    result = client._sync_request('PUT', f'/networks/{quote(network)}/peers/{quote(peer_name)}',
                                  data=peer_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network peer {peer_name} updated successfully'}


def network_peer_delete(network, peer_name):
    """
    Delete a network peer

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_peer_delete mybr0 peer1

    :param network: Network name
    :param peer_name: Peer name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/networks/{quote(network)}/peers/{quote(peer_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network peer {peer_name} deleted successfully'}


# ========== Network Zone Management Functions ==========

def network_zone_list(recursion=0):
    """
    List all network zones

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_list
        salt '*' incus.network_zone_list recursion=1

    :param recursion: Recursion level
    :return: List of network zones
    """
    client = _client()
    result = client._request('GET', '/network-zones', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'zones': result.get('metadata', [])}


def network_zone_get(zone):
    """
    Get network zone information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_get example.com

    :param zone: Zone name
    :return: Zone information
    """
    client = _client()
    result = client._request('GET', f'/network-zones/{quote(zone)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'zone': result.get('metadata', {})}


def network_zone_create(zone, config=None, description=''):
    """
    Create a network zone

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_create example.com
        salt '*' incus.network_zone_create example.com config="{'dns.nameservers':'ns1.example.com'}"

    :param zone: Zone name
    :param config: Zone configuration
    :param description: Zone description
    :return: Result
    """
    client = _client()

    data = {
        'name': zone,
        'config': config or {},
        'description': description
    }

    result = client._sync_request('POST', '/network-zones', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone {zone} created successfully'}


def network_zone_update(zone, config=None, description=None):
    """
    Update network zone

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_update example.com config="{'dns.nameservers':'ns2.example.com'}"

    :param zone: Zone name
    :param config: Configuration to update
    :param description: Description to update
    :return: Result
    """
    client = _client()

    # Get current zone config
    current = network_zone_get(zone)
    if not current.get('success'):
        return current

    zone_data = current['zone']

    if config:
        zone_data['config'].update(config)

    if description is not None:
        zone_data['description'] = description

    result = client._sync_request('PUT', f'/network-zones/{quote(zone)}', data=zone_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone {zone} updated successfully'}


def network_zone_delete(zone):
    """
    Delete a network zone

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_delete example.com

    :param zone: Zone name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/network-zones/{quote(zone)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone {zone} deleted successfully'}


# ========== Network Zone Record Management Functions ==========

def network_zone_record_list(zone, recursion=0):
    """
    List network zone records

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_record_list example.com

    :param zone: Zone name
    :param recursion: Recursion level
    :return: List of zone records
    """
    client = _client()
    result = client._request('GET', f'/network-zones/{quote(zone)}/records',
                            params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'records': result.get('metadata', [])}


def network_zone_record_get(zone, record_name):
    """
    Get network zone record information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_record_get example.com www

    :param zone: Zone name
    :param record_name: Record name
    :return: Record information
    """
    client = _client()
    result = client._request('GET', f'/network-zones/{quote(zone)}/records/{quote(record_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'record': result.get('metadata', {})}


def network_zone_record_create(zone, record_name, config=None, description='', entries=None):
    """
    Create a network zone record

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_record_create example.com www entries="[{'type':'A','value':'192.168.1.1'}]"

    :param zone: Zone name
    :param record_name: Record name
    :param config: Record configuration
    :param description: Record description
    :param entries: List of DNS entries
    :return: Result
    """
    client = _client()

    data = {
        'name': record_name,
        'config': config or {},
        'description': description,
        'entries': entries or []
    }

    result = client._sync_request('POST', f'/network-zones/{quote(zone)}/records', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone record {record_name} created successfully'}


def network_zone_record_update(zone, record_name, config=None, description=None, entries=None):
    """
    Update network zone record

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_record_update example.com www entries="[{'type':'A','value':'192.168.1.2'}]"

    :param zone: Zone name
    :param record_name: Record name
    :param config: Configuration to update
    :param description: Description to update
    :param entries: Entries to update
    :return: Result
    """
    client = _client()

    # Get current record config
    current = network_zone_record_get(zone, record_name)
    if not current.get('success'):
        return current

    record_data = current['record']

    if config:
        record_data['config'].update(config)

    if description is not None:
        record_data['description'] = description

    if entries is not None:
        record_data['entries'] = entries

    result = client._sync_request('PUT', f'/network-zones/{quote(zone)}/records/{quote(record_name)}',
                                  data=record_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone record {record_name} updated successfully'}


def network_zone_record_delete(zone, record_name):
    """
    Delete a network zone record

    CLI Example:

    .. code-block:: bash

        salt '*' incus.network_zone_record_delete example.com www

    :param zone: Zone name
    :param record_name: Record name
    :return: Result
    """
    client = _client()
    result = client._sync_request('DELETE', f'/network-zones/{quote(zone)}/records/{quote(record_name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Network zone record {record_name} deleted successfully'}


# ========== Profile Management Functions ==========

def profile_list(recursion=0):
    """
    List all profiles

    Profiles are used to store configuration that can be applied to instances
    at creation time. They can contain both configuration options and devices.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_list
        salt '*' incus.profile_list recursion=1

    :param recursion: Recursion level (0=URLs, 1=basic info, 2=full info)
    :return: Dictionary with 'success' status and 'profiles' list
    """
    client = _client()
    result = client._request('GET', '/profiles', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'profiles': result.get('metadata', [])}


def profile_get(name):
    """
    Get profile information

    Retrieve detailed information about a specific profile including
    its configuration, devices, and which instances are using it.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_get default
        salt '*' incus.profile_get myprofile

    :param name: Profile name
    :return: Dictionary with 'success' status and 'profile' information
    """
    client = _client()
    result = client._request('GET', f'/profiles/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'profile': result.get('metadata', {})}


def profile_create(name, config=None, devices=None, description=''):
    """
    Create a new profile

    Profiles allow you to define common configurations that can be applied
    to multiple instances. This is useful for standardizing settings like
    CPU limits, memory limits, network devices, and disk devices.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_create myprofile
        salt '*' incus.profile_create myprofile config="{'limits.cpu':'2','limits.memory':'4GB'}"
        salt '*' incus.profile_create webserver config="{'limits.cpu':'4'}" devices="{'eth0':{'type':'nic','network':'lxdbr0'}}"
        salt '*' incus.profile_create dbserver description="Database server profile" config="{'limits.memory':'8GB'}"

    :param name: Profile name
    :param config: Profile configuration (e.g., {'limits.cpu':'2','limits.memory':'4GB'})
    :param devices: Device configuration (e.g., {'eth0':{'type':'nic','network':'lxdbr0'}})
    :param description: Profile description
    :return: Dictionary with 'success' status and message
    """
    client = _client()

    data = {
        'name': name,
        'config': config or {},
        'devices': devices or {},
        'description': description
    }

    result = client._sync_request('POST', '/profiles', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Profile {name} created successfully'}


def profile_update(name, config=None, devices=None, description=None):
    """
    Update profile configuration

    Modify an existing profile's configuration, devices, or description.
    The changes will affect all instances using this profile upon restart.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_update myprofile config="{'limits.memory':'4GB'}"
        salt '*' incus.profile_update myprofile devices="{'root':{'path':'/','pool':'default','type':'disk'}}"
        salt '*' incus.profile_update myprofile description="Updated description"
        salt '*' incus.profile_update myprofile config="{'limits.cpu':'4'}" devices="{'eth0':{'type':'nic','network':'mybr0'}}"

    :param name: Profile name
    :param config: Configuration to update (merged with existing config)
    :param devices: Devices to update (merged with existing devices)
    :param description: Description to update (replaces existing description)
    :return: Dictionary with 'success' status and message
    """
    client = _client()

    # Get current profile config
    current = profile_get(name)
    if not current.get('success'):
        return current

    profile_data = current['profile']

    # Update fields
    if config:
        profile_data['config'].update(config)

    if devices:
        # Deep merge devices: update properties within existing devices
        for dev_name, dev_conf in devices.items():
            if dev_name in profile_data['devices']:
                # Device exists, merge properties
                profile_data['devices'][dev_name].update(dev_conf)
            else:
                # New device, add it
                profile_data['devices'][dev_name] = dev_conf

    if description is not None:
        profile_data['description'] = description

    result = client._sync_request('PUT', f'/profiles/{quote(name)}', data=profile_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Profile {name} updated successfully'}


def profile_rename(name, new_name):
    """
    Rename a profile

    Rename an existing profile. All instances using this profile will
    automatically use the new name.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_rename myprofile mynewprofile
        salt '*' incus.profile_rename old-web-profile web-profile

    :param name: Current profile name
    :param new_name: New profile name
    :return: Dictionary with 'success' status and message
    """
    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/profiles/{quote(name)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Profile {name} renamed to {new_name} successfully'}


def profile_copy(name, new_name, description=None):
    """
    Copy a profile to a new profile

    Create a duplicate of an existing profile with a new name.
    Optionally provide a new description.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_copy default myprofile
        salt '*' incus.profile_copy webserver webserver-backup description="Backup of webserver profile"

    :param name: Source profile name
    :param new_name: New profile name
    :param description: Optional description for the new profile
    :return: Dictionary with 'success' status and message
    """
    client = _client()

    # Get source profile
    source = profile_get(name)
    if not source.get('success'):
        return source

    profile_data = source['profile']

    # Prepare data for new profile
    data = {
        'name': new_name,
        'config': profile_data.get('config', {}),
        'devices': profile_data.get('devices', {}),
        'description': description if description is not None else profile_data.get('description', '')
    }

    result = client._sync_request('POST', '/profiles', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Profile {name} copied to {new_name} successfully'}


def profile_delete(name):
    """
    Delete a profile

    Remove a profile from the system. The profile must not be in use
    by any instances before deletion.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.profile_delete myprofile
        salt '*' incus.profile_delete old-profile

    :param name: Profile name
    :return: Dictionary with 'success' status and message
    """
    client = _client()
    result = client._sync_request('DELETE', f'/profiles/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Profile {name} deleted successfully'}


# ========== Cluster Management Functions ==========

def cluster_info():
    """
    Get cluster information

    CLI Example:

    .. code-block:: bash

        salt '*' incus.cluster_info

    :return: Cluster information
    """
    client = _client()
    result = client._request('GET', '/cluster')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'cluster': result.get('metadata', {})}


def cluster_member_list(recursion=0):
    """
    List cluster members

    CLI Example:

    .. code-block:: bash

        salt '*' incus.cluster_member_list

    :param recursion: Recursion level
    :return: List of cluster members
    """
    client = _client()
    result = client._request('GET', '/cluster/members', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'members': result.get('metadata', [])}


def cluster_member_add(name, address, cluster_password=None):
    """
    Add a cluster member

    CLI Example:

    .. code-block:: bash

        salt '*' incus.cluster_member_add node2 192.168.1.101

    :param name: Member name
    :param address: Member address
    :param cluster_password: Cluster password
    :return: Result
    """
    client = _client()

    data = {
        'server_name': name,
        'server_address': address
    }

    if cluster_password:
        data['cluster_password'] = cluster_password

    result = client._sync_request('POST', '/cluster/members', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Cluster member {name} added successfully'}


def cluster_member_remove(name, force=False):
    """
    Remove a cluster member

    CLI Example:

    .. code-block:: bash

        salt '*' incus.cluster_member_remove node2

    :param name: Member name
    :param force: Force removal
    :return: Result
    """
    client = _client()

    params = {}
    if force:
        params['force'] = '1'

    result = client._sync_request('DELETE', f'/cluster/members/{quote(name)}', params=params)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Cluster member {name} removed successfully'}

# ========== Image Management Functions ==========

def image_list(recursion=0):
    """
    List all images

    CLI Example:

        salt '*' incus.image_list
        salt '*' incus.image_list recursion=1
    """
    client = _client()
    result = client._request('GET', '/images', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'images': result.get('metadata', [])}


def image_get(fingerprint):
    """
    Get image information

    CLI Example:

        salt '*' incus.image_get <fingerprint>
    """
    client = _client()
    result = client._request('GET', f'/images/{quote(fingerprint)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'image': result.get('metadata', {})}


def image_delete(fingerprint):
    """
    Delete an image

    CLI Example:

        salt '*' incus.image_delete <fingerprint>
    """
    client = _client()
    result = client._sync_request('DELETE', f'/images/{quote(fingerprint)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Image {fingerprint} deleted successfully'}


def image_create_from_file(filename, public=False, properties=None, auto_update=False, aliases=None):
    """
    Upload a local .tar.xz/.tar.gz or qcow2 as an image.

    Incus API:
      POST /1.0/images
        Content-Type: multipart/form-data

    CLI Example:

        salt '*' incus.image_create_from_file /tmp/rootfs.tar.xz
        salt '*' incus.image_create_from_file /tmp/rootfs.tar.xz public=True aliases="['myimage']"
    """
    client = _client()
    url = client.base_url + "/images"

    try:
        with open(filename, 'rb') as f:
            files = {'file': f}

            headers_data = {
                'X-Incus-public': '1' if public else '0',
            }

            if properties:
                for key, value in properties.items():
                    headers_data[f'X-Incus-properties.{key}'] = str(value)

            response = client.session.post(url, files=files, headers=headers_data, timeout=600)
            response.raise_for_status()
            result = response.json()
    except FileNotFoundError:
        return {'success': False, 'error': f'File not found: {filename}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

    if result.get('type') == 'async':
        op_result = client._wait_for_operation(result['operation'])

        # Check for errors
        if op_result.get("error_code") != 0:
            return {'success': False, 'error': op_result.get('error', 'Unknown error')}

        metadata = op_result.get("metadata", {})
        if isinstance(metadata, dict) and "metadata" in metadata:
            metadata = metadata.get("metadata", {})

        fingerprint = metadata.get('fingerprint')

        # Add aliases if specified
        if aliases and fingerprint:
            for alias_name in aliases:
                alias_data = {
                    'name': alias_name,
                    'target': fingerprint
                }
                alias_result = client._sync_request('POST', '/images/aliases', data=alias_data)
                if alias_result.get('error_code') != 0:
                    log.warning(f"Failed to add alias {alias_name}: {alias_result.get('error')}")

        return {'success': True, 'fingerprint': fingerprint, 'metadata': metadata}

    return {'success': True, 'metadata': result.get('metadata', {})}


def image_create_from_remote(
    server,
    alias=None,
    protocol="simplestreams",
    image_type=None,
    name=None,
    fingerprint=None,
    project=None,
    auto_update=False,
    public=False,
    aliases=None,
    profiles=None,
    properties=None,
    compression_algorithm=None,
    expires_at=None,
    format=None,
    secret=None,
    certificate=None,
    url=None,
):
    """
    Create an image by pulling from a remote server.

    Example:
        salt '*' incus.image_create_from_remote images: ubuntu/22.04

        Fully matches Incus/LXD REST API:
      POST /1.0/images

    API reference:
      https://linuxcontainers.org/incus/docs/main/rest-api/#post-10images

    Only the "source" part is mandatory.

    All other fields are optional and will be included only if specified.
    The result is ALWAYS an async operation.
    """

    # ============
    # VALIDATION
    # ============

    # Mandatory: server
    if not server or not isinstance(server, str):
        return {
            "success": False,
            "error": "Parameter 'server' is required and must be a string"
        }

    # Mandatory: alias XOR fingerprint
    if not alias and not fingerprint:
        return {
            "success": False,
            "error": "Either 'alias' or 'fingerprint' must be provided"
        }

    if alias and fingerprint:
        return {
            "success": False,
            "error": "Only one of 'alias' or 'fingerprint' may be provided"
        }

    # Mandatory protocol
    VALID_PROTOCOLS = ("simplestreams", "incus", "lxd", "direct")
    if protocol not in VALID_PROTOCOLS:
        return {
            "success": False,
            "error": f"Invalid protocol '{protocol}'. Must be one of {VALID_PROTOCOLS}"
        }

    # Optional: type for source (Incus allows "instance", "image")
    if image_type and image_type not in ("container", "virtual-machine", "instance", "image"):
        return {
            "success": False,
            "error": "Invalid image_type. Valid: container, virtual-machine, instance, image"
        }

    # ============
    # BUILD REQUEST
    # ============

    client = _client()

    # Base body
    data = {
        "auto_update": auto_update,
        "public": public,
        "source": {
            "type": "image",
            "mode": "pull",
            "server": server,
            "protocol": protocol,
        }
    }

    # Optional source fields
    if alias:
        data["source"]["alias"] = alias
    if fingerprint:
        data["source"]["fingerprint"] = fingerprint
    if image_type:
        data["source"]["image_type"] = image_type
    if name:
        data["source"]["name"] = name
    if project:
        data["source"]["project"] = project
    if secret:
        data["source"]["secret"] = secret
    if certificate:
        data["source"]["certificate"] = certificate
    if url:
        data["source"]["url"] = url

    # Optional top-level fields
    if properties:
        data["properties"] = properties

    if compression_algorithm:
        data["compression_algorithm"] = compression_algorithm

    if expires_at:
        data["expires_at"] = expires_at

    if format:
        data["format"] = format

    # Perform request
    result = client._sync_request("POST", "/images", data=data)

    # Error always indicated by error_code != 0
    if result.get("error_code") != 0:
        return {
            "success": False,
            "error": result.get("error", "Unknown error"),
        }

    # For async operations (image imports), result.metadata contains the operation
    # and operation.metadata contains the actual result (with fingerprint)
    metadata = result.get("metadata", {})

    # If metadata contains operation metadata, extract it
    if isinstance(metadata, dict) and "metadata" in metadata:
        metadata = metadata.get("metadata", {})

    fingerprint = metadata.get('fingerprint')

    # Add aliases after image is created
    if aliases and fingerprint:
        for alias_name in aliases:
            alias_data = {
                'name': alias_name,
                'target': fingerprint
            }
            alias_result = client._sync_request('POST', '/images/aliases', data=alias_data)
            if alias_result.get('error_code') != 0:
                log.warning(f"Failed to add alias {alias_name}: {alias_result.get('error')}")

    # Add profiles if specified (via image update)
    if profiles and fingerprint:
        update_data = {
            'profiles': profiles
        }
        update_result = image_update(fingerprint, update_data)
        if not update_result.get('success'):
            log.warning(f"Failed to set profiles on image: {update_result.get('error')}")

    return {'success': True, 'fingerprint': fingerprint, 'metadata': metadata}


def image_update_properties(fingerprint, properties):
    """
    Update image properties

    CLI Example:

        salt '*' incus.image_update_properties <fp> properties="{'os':'ubuntu'}"
    """
    client = _client()

    current = client._request('GET', f'/images/{quote(fingerprint)}')
    if 'error' in current:
        return {'success': False, 'error': current['error']}

    data = current.get('metadata', {})
    data['properties'] = data.get('properties', {})
    data['properties'].update(properties)

    result = client._sync_request('PUT', f'/images/{quote(fingerprint)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'message': f'Image {fingerprint} updated successfully'}


def image_update(fingerprint, update_body):
    """
    Update image metadata (public, auto_update, aliases, properties, etc.)

    CLI Example:

        salt '*' incus.image_update <fp> update_body="{'public': True, 'auto_update': True}"
        salt '*' incus.image_update <fp> update_body="{'aliases': ['myimage', 'latest']}"

    :param fingerprint: Image fingerprint
    :param update_body: Dictionary with fields to update
    :return: Result dict
    """
    client = _client()

    # Get current image data
    current = client._request('GET', f'/images/{quote(fingerprint)}')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get image')}

    data = current.get('metadata', {})

    # Handle aliases separately via /images/aliases API
    # Make a copy to avoid modifying the original
    update_body_copy = dict(update_body)
    desired_aliases = update_body_copy.pop('aliases', None)

    # Update other fields
    for key, value in update_body_copy.items():
        data[key] = value

    # Send PUT request for other fields (if any)
    if update_body_copy:
        result = client._sync_request('PUT', f'/images/{quote(fingerprint)}', data=data)

        if result.get('error_code') != 0:
            return {'success': False, 'error': result.get('error', 'Failed to update image')}

    # Handle aliases separately using /images/aliases API
    if desired_aliases is not None:
        # Get current aliases from the API (not from image metadata)
        all_aliases_result = client._request('GET', '/images/aliases', params={'recursion': 1})
        if all_aliases_result.get('error_code') != 0:
            return {'success': False, 'error': 'Failed to get current aliases'}

        # Filter aliases for this image
        current_aliases = []
        for alias_obj in all_aliases_result.get('metadata', []):
            if isinstance(alias_obj, dict) and alias_obj.get('target') == fingerprint:
                alias_name = alias_obj.get('name')
                if alias_name:
                    current_aliases.append(alias_name)

        # Determine which aliases to add and remove
        to_add = [a for a in desired_aliases if a not in current_aliases]
        to_remove = [a for a in current_aliases if a not in desired_aliases]

        # Remove old aliases
        for alias_name in to_remove:
            del_result = client._sync_request('DELETE', f'/images/aliases/{quote(alias_name)}')
            if del_result.get('error_code') != 0:
                log.warning(f"Failed to delete alias {alias_name}: {del_result.get('error')}")

        # Add new aliases
        for alias_name in to_add:
            alias_data = {
                'name': alias_name,
                'target': fingerprint
            }
            add_result = client._sync_request('POST', '/images/aliases', data=alias_data)
            if add_result.get('error_code') != 0:
                return {'success': False, 'error': f"Failed to add alias {alias_name}: {add_result.get('error')}"}

    return {'success': True, 'message': f'Image {fingerprint} updated successfully'}


def image_set_public(fingerprint, public=True):
    """
    Set image public or private

    CLI Example:

        salt '*' incus.image_set_public <fp> public=True
    """
    client = _client()

    current = client._request('GET', f'/images/{quote(fingerprint)}')
    if 'error' in current:
        return {'success': False, 'error': current['error']}

    data = current.get('metadata', {})
    data['public'] = public

    result = client._sync_request('PUT', f'/images/{quote(fingerprint)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {
        'success': True,
        'message': f'Image {fingerprint} set to {"public" if public else "private"}'
    }


def image_alias_list(recursion=0):
    """
    List all image aliases

    CLI Example:

        salt '*' incus.image_alias_list
        salt '*' incus.image_alias_list recursion=1
    """
    client = _client()
    result = client._request('GET', '/images/aliases', params={'recursion': recursion})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result['error']}

    return {'success': True, 'aliases': result.get('metadata', [])}


def image_alias_get(name):
    """
    Get image alias information

    CLI Example:

        salt '*' incus.image_alias_get ubuntu/22.04
    """
    if not name:
        return {'success': False, 'error': 'Alias name is required'}

    client = _client()
    result = client._request('GET', f'/images/aliases/{quote(str(name))}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to get alias')}

    return {'success': True, 'alias': result.get('metadata', {})}


def image_alias_create(name, target, description=''):
    """
    Create an image alias

    CLI Example:

        salt '*' incus.image_alias_create myimage <fingerprint>
        salt '*' incus.image_alias_create ubuntu/custom abc123def description="Custom Ubuntu image"
    """
    if not name:
        return {'success': False, 'error': 'Alias name is required'}
    if not target:
        return {'success': False, 'error': 'Target fingerprint is required'}

    client = _client()

    data = {
        'name': name,
        'target': target
    }

    if description:
        data['description'] = description

    result = client._sync_request('POST', '/images/aliases', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to create alias')}

    return {'success': True, 'message': f'Image alias {name} created successfully'}


def image_alias_update(name, target=None, description=None):
    """
    Update an image alias

    CLI Example:

        salt '*' incus.image_alias_update myimage target=<new_fingerprint>
        salt '*' incus.image_alias_update myimage description="Updated description"
    """
    if not name:
        return {'success': False, 'error': 'Alias name is required'}

    client = _client()

    # Get current alias
    current = client._request('GET', f'/images/aliases/{quote(name)}')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get alias')}

    alias_data = current.get('metadata', {})

    # Update fields
    if target is not None:
        alias_data['target'] = target

    if description is not None:
        alias_data['description'] = description

    result = client._sync_request('PUT', f'/images/aliases/{quote(name)}', data=alias_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to update alias')}

    return {'success': True, 'message': f'Image alias {name} updated successfully'}


def image_alias_rename(name, new_name):
    """
    Rename an image alias

    CLI Example:

        salt '*' incus.image_alias_rename oldname newname
    """
    if not name or not new_name:
        return {'success': False, 'error': 'Both old and new alias names are required'}

    client = _client()

    data = {
        'name': new_name
    }

    result = client._sync_request('POST', f'/images/aliases/{quote(name)}', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to rename alias')}

    return {'success': True, 'message': f'Image alias {name} renamed to {new_name} successfully'}


def image_alias_delete(name):
    """
    Delete an image alias

    CLI Example:

        salt '*' incus.image_alias_delete ubuntu/22.04
    """
    if not name:
        return {'success': False, 'error': 'Alias name is required'}

    client = _client()
    result = client._sync_request('DELETE', f'/images/aliases/{quote(name)}')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to delete alias')}

    return {'success': True, 'message': f'Image alias {name} deleted successfully'}


def image_copy(fingerprint, target_server=None, target_certificate=None, target_secret=None, aliases=None, public=False, auto_update=False):
    """
    Copy an image to another server or within the same server

    CLI Example:

        salt '*' incus.image_copy <fingerprint> aliases="['myimage-copy']"
        salt '*' incus.image_copy <fingerprint> target_server=https://target:8443 aliases="['remote-copy']"
    """
    if not fingerprint:
        return {'success': False, 'error': 'Fingerprint is required'}

    client = _client()

    # Get source image
    source_result = client._request('GET', f'/images/{quote(fingerprint)}')
    if source_result.get('error_code') != 0:
        return {'success': False, 'error': source_result.get('error', 'Failed to get source image')}

    source_image = source_result.get('metadata', {})

    data = {
        'source': {
            'type': 'copy',
            'fingerprint': fingerprint
        },
        'public': public,
        'auto_update': auto_update
    }

    if target_server:
        data['source']['server'] = target_server
        data['source']['mode'] = 'pull'
        data['source']['protocol'] = 'incus'

        if target_certificate:
            data['source']['certificate'] = target_certificate
        if target_secret:
            data['source']['secret'] = target_secret

    result = client._sync_request('POST', '/images', data=data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to copy image')}

    metadata = result.get('metadata', {})
    if isinstance(metadata, dict) and 'metadata' in metadata:
        metadata = metadata.get('metadata', {})

    new_fingerprint = metadata.get('fingerprint', fingerprint)

    # Add aliases to the new image
    if aliases and new_fingerprint:
        for alias_name in aliases:
            alias_data = {
                'name': alias_name,
                'target': new_fingerprint
            }
            alias_result = client._sync_request('POST', '/images/aliases', data=alias_data)
            if alias_result.get('error_code') != 0:
                log.warning(f"Failed to add alias {alias_name}: {alias_result.get('error')}")

    return {'success': True, 'fingerprint': new_fingerprint, 'message': f'Image {fingerprint} copied successfully'}


def image_export(fingerprint, target_path=None):
    """
    Export an image to a file

    CLI Example:

        salt '*' incus.image_export <fingerprint> target_path=/tmp/image.tar.gz
    """
    if not fingerprint:
        return {'success': False, 'error': 'Fingerprint is required'}

    client = _client()
    url = f'{client.base_url}/images/{quote(fingerprint)}/export'

    try:
        response = client.session.get(url, stream=True, timeout=600)
        response.raise_for_status()

        # If target_path not specified, return the content
        if not target_path:
            return {'success': True, 'content': response.content}

        # Save to file
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return {'success': True, 'message': f'Image {fingerprint} exported to {target_path}'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def image_refresh(fingerprint):
    """
    Refresh an image (update from remote source)

    This triggers an update of the image from its original source if auto_update is enabled.

    CLI Example:

        salt '*' incus.image_refresh <fingerprint>
    """
    if not fingerprint:
        return {'success': False, 'error': 'Fingerprint is required'}

    client = _client()

    # Refresh is done by sending a PATCH request
    result = client._sync_request('PATCH', f'/images/{quote(fingerprint)}', data={})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to refresh image')}

    return {'success': True, 'message': f'Image {fingerprint} refreshed successfully'}


def image_secret_create(fingerprint):
    """
    Create a secret for image access

    This creates a one-time secret that can be used to access a private image
    without authentication. Useful for sharing private images temporarily.

    CLI Example:

        salt '*' incus.image_secret_create <fingerprint>
    """
    if not fingerprint:
        return {'success': False, 'error': 'Fingerprint is required'}

    client = _client()

    result = client._sync_request('POST', f'/images/{quote(fingerprint)}/secret', data={})

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to create image secret')}

    metadata = result.get('metadata', {})
    if isinstance(metadata, dict) and 'metadata' in metadata:
        metadata = metadata.get('metadata', {})

    return {'success': True, 'secret': metadata}


# ========== Settings Management Functions ==========

def settings_get():
    """
    Get Incus server global configuration settings

    Retrieves the current global configuration for the Incus server.
    These settings control various aspects of server behavior including
    images auto-update, clustering, HTTPS address, and more.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.settings_get

    :return: Dictionary with 'success' status and 'settings' configuration

    Example return value:

    .. code-block:: python

        {
            'success': True,
            'settings': {
                'config': {
                    'core.https_address': '[::]:8443',
                    'core.trust_password': 'secret',
                    'images.auto_update_cached': 'true',
                    'images.auto_update_interval': '6'
                }
            }
        }
    """
    client = _client()
    result = client._request('GET', '')

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to get settings')}

    return {'success': True, 'settings': result.get('metadata', {})}


def settings_update(config):
    """
    Update Incus server global configuration settings

    Modify global configuration options for the Incus server.
    This function merges the provided configuration with existing settings.

    Common configuration keys:
    - core.https_address: HTTPS address and port (e.g., ':8443', '[::]:8443')
    - core.trust_password: Password for adding new clients
    - images.auto_update_cached: Enable/disable automatic image updates ('true'/'false')
    - images.auto_update_interval: Hours between image update checks
    - images.compression_algorithm: Compression for images (e.g., 'gzip', 'zstd')
    - images.remote_cache_expiry: Days to cache remote images
    - cluster.https_address: Address for cluster communication
    - storage.backups_volume: Storage volume for backups
    - storage.images_volume: Storage volume for images

    CLI Example:

    .. code-block:: bash

        salt '*' incus.settings_update config="{'images.auto_update_interval':'12'}"
        salt '*' incus.settings_update config="{'core.https_address':'[::]:8443','images.auto_update_cached':'true'}"

    :param config: Dictionary of configuration key-value pairs to update
    :return: Dictionary with 'success' status and message

    Example usage:

    .. code-block:: python

        # Enable HTTPS on all interfaces
        incus.settings_update({'core.https_address': '[::]:8443'})

        # Configure image auto-update
        incus.settings_update({
            'images.auto_update_cached': 'true',
            'images.auto_update_interval': '12'
        })

        # Set compression algorithm
        incus.settings_update({'images.compression_algorithm': 'zstd'})
    """
    if not config or not isinstance(config, dict):
        return {'success': False, 'error': 'config parameter must be a dictionary'}

    client = _client()

    # Get current settings
    current = client._request('GET', '')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get current settings')}

    settings_data = current.get('metadata', {})

    # Update config
    if 'config' not in settings_data:
        settings_data['config'] = {}

    settings_data['config'].update(config)

    # Send update request
    result = client._sync_request('PUT', '', data=settings_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to update settings')}

    return {'success': True, 'message': 'Server settings updated successfully'}


def settings_set(key, value):
    """
    Set a single Incus server configuration setting

    Convenience function to set a single configuration key without
    needing to provide a full configuration dictionary.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.settings_set core.https_address '[::]:8443'
        salt '*' incus.settings_set images.auto_update_interval 12
        salt '*' incus.settings_set images.compression_algorithm zstd

    :param key: Configuration key name
    :param value: Configuration value (will be converted to string)
    :return: Dictionary with 'success' status and message

    Example usage:

    .. code-block:: python

        # Enable HTTPS
        incus.settings_set('core.https_address', '[::]:8443')

        # Set auto-update interval
        incus.settings_set('images.auto_update_interval', '12')

        # Set trust password
        incus.settings_set('core.trust_password', 'mysecret')
    """
    if not key or not isinstance(key, str):
        return {'success': False, 'error': 'key parameter must be a non-empty string'}

    return settings_update({key: str(value)})


def settings_unset(key):
    """
    Unset (remove) a single Incus server configuration setting

    Remove a configuration key from the server settings, reverting it
    to its default value.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.settings_unset core.trust_password
        salt '*' incus.settings_unset images.auto_update_interval

    :param key: Configuration key name to remove
    :return: Dictionary with 'success' status and message

    Example usage:

    .. code-block:: python

        # Remove trust password (disable password authentication)
        incus.settings_unset('core.trust_password')

        # Reset auto-update interval to default
        incus.settings_unset('images.auto_update_interval')
    """
    if not key or not isinstance(key, str):
        return {'success': False, 'error': 'key parameter must be a non-empty string'}

    client = _client()

    # Get current settings
    current = client._request('GET', '')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get current settings')}

    settings_data = current.get('metadata', {})

    # Remove key from config
    if 'config' in settings_data and key in settings_data['config']:
        del settings_data['config'][key]
    else:
        return {'success': False, 'error': f'Configuration key "{key}" not found'}

    # Send update request
    result = client._sync_request('PUT', '', data=settings_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to update settings')}

    return {'success': True, 'message': f'Configuration key "{key}" unset successfully'}


def settings_replace(config):
    """
    Replace entire Incus server configuration

    Replace the entire server configuration with the provided settings.
    Unlike settings_update(), this function does NOT merge with existing
    settings - it completely replaces them. Use with caution.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.settings_replace config="{'core.https_address':'[::]:8443','images.auto_update_cached':'true'}"

    :param config: Dictionary of configuration key-value pairs (replaces all settings)
    :return: Dictionary with 'success' status and message

    Example usage:

    .. code-block:: python

        # Replace all settings with minimal config
        incus.settings_replace({
            'core.https_address': '[::]:8443',
            'images.auto_update_cached': 'true'
        })

    Warning:
        This function replaces ALL server configuration settings.
        Any settings not included in the config parameter will be
        removed and reverted to defaults. Use settings_update()
        instead if you want to modify specific settings.
    """
    if not config or not isinstance(config, dict):
        return {'success': False, 'error': 'config parameter must be a dictionary'}

    client = _client()

    # Get current settings structure
    current = client._request('GET', '')
    if current.get('error_code') != 0:
        return {'success': False, 'error': current.get('error', 'Failed to get current settings')}

    settings_data = current.get('metadata', {})

    # Replace config entirely
    settings_data['config'] = config

    # Send update request
    result = client._sync_request('PUT', '', data=settings_data)

    if result.get('error_code') != 0:
        return {'success': False, 'error': result.get('error', 'Failed to replace settings')}

    return {'success': True, 'message': 'Server settings replaced successfully'}


# ========== Cloud-init Status Functions ==========

def instance_check_cloudinit_enabled(name):
    """
    Check if cloud-init is enabled in the instance.

    This function checks if cloud-init package is installed by trying to execute
    'cloud-init --version' command inside the instance.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_check_cloudinit_enabled myvm

    :param name: Instance name
    :return: Result dict with success status and enabled flag
    """
    client = _client()

    # Try to execute cloud-init --version command
    data = {
        'command': ['cloud-init', '--version'],
        'wait-for-websocket': False,
        'interactive': False,
        'environment': {}
    }

    try:
        result = client._sync_request('POST', f'/instances/{quote(name)}/exec', data=data)

        # If command succeeds (exit code 0), cloud-init is installed
        if result.get('error_code') == 0:
            return {
                'success': True,
                'enabled': True,
                'message': 'cloud-init is installed and available'
            }
        else:
            # Command failed, cloud-init is not available
            return {
                'success': True,
                'enabled': False,
                'message': 'cloud-init is not installed or not available'
            }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to check cloud-init status: {str(e)}'
        }


def instance_get_cloudinit_status(name):
    """
    Get cloud-init status from the instance.

    This function executes 'cloud-init status' command inside the instance
    to get the current cloud-init status.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_get_cloudinit_status myvm

    :param name: Instance name
    :return: Result dict with success status, cloud-init status and details
    """
    client = _client()

    # Execute cloud-init status command
    data = {
        'command': ['cloud-init', 'status'],
        'wait-for-websocket': False,
        'interactive': False,
        'environment': {},
        'record-output': True
    }

    try:
        result = client._sync_request('POST', f'/instances/{quote(name)}/exec', data=data)

        if result.get('error_code') != 0:
            return {
                'success': False,
                'error': f"Failed to execute cloud-init status: {result.get('error', 'Unknown error')}"
            }

        # Get the operation metadata to extract output
        metadata = result.get('metadata', {})
        return_code = metadata.get('return', -1)

        # Parse status from output
        # cloud-init status returns different statuses: done, running, error, disabled
        # We need to get the actual output to determine the status
        output = metadata.get('output', {})

        return {
            'success': True,
            'return_code': return_code,
            'metadata': metadata
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get cloud-init status: {str(e)}'
        }


def instance_wait_cloudinit(name, timeout=600, interval=5):
    """
    Wait for cloud-init to complete in the instance.

    This function polls cloud-init completion by checking marker files,
    avoiding potentially blocking commands.

    CLI Example:

    .. code-block:: bash

        salt '*' incus.instance_wait_cloudinit myvm
        salt '*' incus.instance_wait_cloudinit myvm timeout=900 interval=10

    :param name: Instance name
    :param timeout: Maximum seconds to wait (default: 600)
    :param interval: Poll interval in seconds (default: 5)
    :return: Result dict with success status and cloud-init result
    """
    client = _client()
    started = time.time()

    log.info(f"Waiting for cloud-init to complete on instance '{name}' (timeout: {timeout}s)")

    while time.time() - started < timeout:
        try:
            # Check for boot-finished marker file - this is the most reliable indicator
            # that cloud-init has completed (successfully or with errors)
            check_data = {
                'command': ['test', '-f', '/var/lib/cloud/instance/boot-finished'],
                'wait-for-websocket': False,
                'interactive': False,
                'environment': {}
            }

            check_result = client._sync_request('POST', f'/instances/{quote(name)}/exec', data=check_data)

            # DEBUG: Log API response
            log.debug(f"DEBUG: API error_code={check_result.get('error_code')}, metadata_present={check_result.get('metadata') is not None}")

            if check_result.get('error_code') != 0:
                log.debug(f"Failed to check cloud-init marker on '{name}': {check_result.get('error')}")
                time.sleep(interval)
                continue

            # Get the return code from metadata
            # Note: Incus API returns nested structure: result['metadata']['metadata']['return']
            metadata = check_result.get('metadata', {})
            inner_metadata = metadata.get('metadata', {})
            return_code = inner_metadata.get('return', -1)

            # DEBUG: Log metadata details
            log.warning(f"DEBUG: return_code={return_code}, inner_metadata_keys={list(inner_metadata.keys()) if inner_metadata else []}")

            # If boot-finished exists (return code 0), cloud-init has completed
            if return_code == 0:
                elapsed = time.time() - started
                log.info(f"cloud-init completed on '{name}' after {elapsed:.1f}s (boot-finished file exists)")
                return {
                    'success': True,
                    'status': 'done',
                    'message': f'cloud-init completed on {name}',
                    'elapsed_time': elapsed
                }

            # boot-finished doesn't exist yet - still running
            log.debug(f"cloud-init still running on '{name}' (boot-finished check return_code={return_code}), waiting...")

        except Exception as e:
            log.debug(f"Exception while checking cloud-init status on '{name}': {str(e)}")

        # Wait before next check
        time.sleep(interval)

    # Timeout reached
    elapsed = time.time() - started
    log.warning(f"Timeout waiting for cloud-init on instance '{name}' ({elapsed:.1f}s)")
    return {
        'success': False,
        'status': 'timeout',
        'error': f'Timeout waiting for cloud-init to complete after {elapsed:.1f}s'
    }