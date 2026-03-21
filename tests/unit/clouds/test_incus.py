"""
Unit tests for _clouds/incus.py — Salt Cloud driver for Incus.

Covers Section 18.1 of incus_salt_cloud_driver_spec.md:
  - __virtual__ registration and dependency checks
  - provider resolution and get_configured_provider
  - mapping of driver operations to exact incus.* function names
  - payload builder for container and VM
  - config/devices merge precedence
  - target behavior (supported vs unsupported path)
  - wait loop success/timeout branches
  - CloudError mapping on execution-module failures
  - output shape of list_nodes, list_nodes_full, list_nodes_select
  - action/function call dispatch behavior
  - show_instance, start, stop, reboot call dispatch
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Minimal Salt stubs so the module can be imported without a real Salt install
# ---------------------------------------------------------------------------

def _make_salt_stubs():
    salt_mod = types.ModuleType("salt")
    sys.modules.setdefault("salt", salt_mod)

    # salt.config
    cfg_mod = types.ModuleType("salt.config")
    cfg_mod.is_provider_configured = MagicMock(return_value={"connection": {"type": "unix"}})
    cfg_mod.check_driver_dependencies = MagicMock(return_value=True)
    sys.modules.setdefault("salt.config", cfg_mod)
    salt_mod.config = cfg_mod

    # salt.utils
    utils_mod = types.ModuleType("salt.utils")
    sys.modules.setdefault("salt.utils", utils_mod)
    salt_mod.utils = utils_mod

    # salt.utils.cloud
    cloud_mod = types.ModuleType("salt.utils.cloud")
    cloud_mod.fire_event = MagicMock()
    cloud_mod.filter_event = MagicMock(return_value={})
    cloud_mod.list_nodes_select = MagicMock(return_value={})
    cloud_mod.get_deploy_kwargs = MagicMock(return_value={})
    cloud_mod.deploy_linux = MagicMock(return_value=True)
    sys.modules.setdefault("salt.utils.cloud", cloud_mod)
    utils_mod.cloud = cloud_mod

    # salt.exceptions
    exc_mod = types.ModuleType("salt.exceptions")

    class SaltCloudException(Exception):
        pass

    class SaltCloudSystemExit(Exception):
        pass

    class SaltCloudNotFound(Exception):
        pass

    exc_mod.SaltCloudException = SaltCloudException
    exc_mod.SaltCloudSystemExit = SaltCloudSystemExit
    exc_mod.SaltCloudNotFound = SaltCloudNotFound
    sys.modules.setdefault("salt.exceptions", exc_mod)
    salt_mod.exceptions = exc_mod

    return salt_mod, exc_mod


_salt_mod, _exc_mod = _make_salt_stubs()

# Now import the cloud driver
import importlib
import os
import sys

# Insert the project root so _clouds.incus can be found
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import _clouds.incus as incus_driver

# Inject dunder globals that Salt normally injects at runtime
incus_driver.__opts__ = {
    "sock_dir": "/var/run/salt/master",
    "transport": "zeromq",
    "query.selection": [],
}
incus_driver.__active_provider_name__ = "my-incus"
incus_driver.__utils__ = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(responses=None):
    """Return a mock IncusClient whose _request returns items from responses list."""
    client = MagicMock(spec=incus_driver.IncusClient)
    if responses is not None:
        client._request.side_effect = responses
    return client


def _ok(metadata=None):
    """Successful Incus API response."""
    return {"type": "sync", "error_code": 0, "metadata": metadata}


def _err(msg="oops", code=500):
    return {"error": msg, "error_code": code}


# ---------------------------------------------------------------------------
# 1. __virtual__ registration
# ---------------------------------------------------------------------------

class TestVirtual(unittest.TestCase):

    def test_returns_virtualname_when_requests_available(self):
        original = incus_driver.HAS_REQUESTS
        try:
            incus_driver.HAS_REQUESTS = True
            result = incus_driver.__virtual__()
            self.assertEqual(result, "incus")
        finally:
            incus_driver.HAS_REQUESTS = original

    def test_returns_false_when_requests_missing(self):
        original = incus_driver.HAS_REQUESTS
        try:
            incus_driver.HAS_REQUESTS = False
            result = incus_driver.__virtual__()
            self.assertFalse(result[0])
        finally:
            incus_driver.HAS_REQUESTS = original


# ---------------------------------------------------------------------------
# 2. deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge(unittest.TestCase):

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 0}, "b": 5}
        result = incus_driver.deep_merge(base, override)
        self.assertEqual(result, {"a": {"x": 1, "y": 99, "z": 0}, "b": 5})

    def test_override_wins_for_non_dict(self):
        base = {"k": "old"}
        result = incus_driver.deep_merge(base, {"k": "new"})
        self.assertEqual(result["k"], "new")


# ---------------------------------------------------------------------------
# 2b. SDB-backed TLS values
# ---------------------------------------------------------------------------

class TestSdbConnectionResolution(unittest.TestCase):

    def setUp(self):
        self._orig_utils = getattr(incus_driver, "__utils__", {})
        incus_driver.__utils__ = {}

    def tearDown(self):
        incus_driver.__utils__ = self._orig_utils

    def test_resolve_connection_value_from_sdb_key(self):
        getter = MagicMock(return_value="CERTDATA")
        incus_driver.__utils__ = {"sdb.get": getter}

        value, from_sdb = incus_driver._resolve_connection_value(
            {
                "cert_storage": {
                    "type": "sdb",
                    "cert": "sdb://vault/incus/cert",
                }
            },
            "cert",
        )

        self.assertTrue(from_sdb)
        self.assertEqual(value, "CERTDATA")
        getter.assert_called_once_with("sdb://vault/incus/cert")

    def test_resolve_connection_value_from_inline_sdb_uri(self):
        getter = MagicMock(return_value="false")
        incus_driver.__utils__ = {"sdb.get": getter}

        value, from_sdb = incus_driver._resolve_connection_value(
            {
                "cert_storage": {
                    "type": "local_files",
                    "verify": "sdb://vault/incus/verify",
                }
            },
            "verify",
            True,
        )

        self.assertTrue(from_sdb)
        self.assertEqual(value, "false")
        getter.assert_called_once_with("sdb://vault/incus/verify")

    def test_resolve_connection_value_from_legacy_flat_sdb_key(self):
        getter = MagicMock(return_value="CERTDATA")
        incus_driver.__utils__ = {"sdb.get": getter}

        value, from_sdb = incus_driver._resolve_connection_value(
            {"cert_sdb": "sdb://vault/incus/cert"},
            "cert",
        )

        self.assertTrue(from_sdb)
        self.assertEqual(value, "CERTDATA")
        getter.assert_called_once_with("sdb://vault/incus/cert")

    def test_https_session_materializes_sdb_certs_and_cleanup(self):
        cert_pem = "-----BEGIN CERTIFICATE-----\nCERTDATA\n-----END CERTIFICATE-----\n"
        key_pem = "-----BEGIN PRIVATE KEY-----\nKEYDATA\n-----END PRIVATE KEY-----\n"
        ca_pem = "-----BEGIN CERTIFICATE-----\nCADATA\n-----END CERTIFICATE-----\n"

        mapping = {
            "sdb://vault/incus/cert": cert_pem,
            "sdb://vault/incus/key": key_pem,
            "sdb://vault/incus/ca": ca_pem,
        }
        incus_driver.__utils__ = {"sdb.get": MagicMock(side_effect=lambda uri: mapping[uri])}

        client = incus_driver.IncusClient(
            {
                "connection": {
                    "type": "https",
                    "url": "https://incus.example.com:8443",
                    "cert_storage": {
                        "type": "sdb",
                        "cert": "sdb://vault/incus/cert",
                        "key": "sdb://vault/incus/key",
                        "verify": "sdb://vault/incus/ca",
                    },
                }
            }
        )

        cert_path, key_path = client.session.cert
        verify_path = client.session.verify

        self.assertTrue(os.path.exists(cert_path))
        self.assertTrue(os.path.exists(key_path))
        self.assertTrue(os.path.exists(verify_path))

        client.close()

        self.assertFalse(os.path.exists(cert_path))
        self.assertFalse(os.path.exists(key_path))
        self.assertFalse(os.path.exists(verify_path))

    def test_verify_sdb_false_string_is_coerced_to_bool(self):
        incus_driver.__utils__ = {"sdb.get": MagicMock(return_value="false")}

        client = incus_driver.IncusClient(
            {
                "connection": {
                    "type": "https",
                    "url": "https://incus.example.com:8443",
                    "cert_storage": {
                        "type": "sdb",
                        "verify": "sdb://vault/incus/verify",
                    },
                }
            }
        )

        self.assertIs(client.session.verify, False)
        client.close()


# ---------------------------------------------------------------------------
# 3. get_configured_provider
# ---------------------------------------------------------------------------

class TestGetConfiguredProvider(unittest.TestCase):

    def test_calls_is_provider_configured(self):
        with patch.object(
            incus_driver.config,
            "is_provider_configured",
            return_value={"connection": {"type": "unix"}},
        ) as mock_cfg:
            result = incus_driver.get_configured_provider()
            self.assertTrue(mock_cfg.called)
            self.assertIn("connection", result)


# ---------------------------------------------------------------------------
# 4. _extract_ips
# ---------------------------------------------------------------------------

class TestExtractIps(unittest.TestCase):

    def test_extracts_global_ipv4(self):
        network = {
            "eth0": {
                "addresses": [
                    {"family": "inet", "scope": "global", "address": "10.0.0.5"},
                    {"family": "inet6", "scope": "global", "address": "::1"},
                ]
            },
            "lo": {
                "addresses": [
                    {"family": "inet", "scope": "local", "address": "127.0.0.1"}
                ]
            },
        }
        ips = incus_driver._extract_ips(network)
        self.assertEqual(ips, ["10.0.0.5"])

    def test_empty_on_no_network(self):
        self.assertEqual(incus_driver._extract_ips({}), [])
        self.assertEqual(incus_driver._extract_ips(None), [])


# ---------------------------------------------------------------------------
# 5. _get_node_state
# ---------------------------------------------------------------------------

class TestGetNodeState(unittest.TestCase):

    def test_known_codes(self):
        self.assertEqual(incus_driver._get_node_state(103), "running")
        self.assertEqual(incus_driver._get_node_state(102), "stopped")
        self.assertEqual(incus_driver._get_node_state(400), "error")

    def test_unknown_code(self):
        self.assertEqual(incus_driver._get_node_state(999), "unknown")


# ---------------------------------------------------------------------------
# 6. list_nodes output shape
# ---------------------------------------------------------------------------

class TestListNodes(unittest.TestCase):

    def _instance_response(self):
        return _ok([
            {
                "name": "web01",
                "status": "Running",
                "profiles": ["default"],
                "expanded_config": {"image.description": "Ubuntu 22.04"},
            }
        ])

    def _state_response(self):
        return _ok({
            "status": "Running",
            "network": {
                "eth0": {
                    "addresses": [
                        {"family": "inet", "scope": "global", "address": "10.0.0.10"}
                    ]
                }
            },
        })

    def test_returns_normalized_shape(self):
        client = MagicMock()
        client._request.side_effect = [self._instance_response(), self._state_response()]

        with patch.object(incus_driver, "_client", return_value=client):
            nodes = incus_driver.list_nodes()

        self.assertIn("web01", nodes)
        node = nodes["web01"]
        self.assertEqual(node["id"], "web01")
        self.assertEqual(node["state"], "running")
        self.assertIn("private_ips", node)
        self.assertIn("public_ips", node)
        self.assertEqual(node["public_ips"], [])

    def test_raises_on_action_call(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.list_nodes(call="action")

    def test_returns_empty_on_api_error(self):
        client = MagicMock()
        client._request.return_value = _err()
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.list_nodes()
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# 7. list_nodes_full output shape
# ---------------------------------------------------------------------------

class TestListNodesFull(unittest.TestCase):

    def test_returns_keyed_by_name(self):
        client = MagicMock()
        client._request.return_value = _ok([{"name": "vm01", "status": "Running"}])
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.list_nodes_full()
        self.assertIn("vm01", result)

    def test_raises_on_action_call(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.list_nodes_full(call="action")


# ---------------------------------------------------------------------------
# 8. Payload builder — container
# ---------------------------------------------------------------------------

class TestPayloadBuilderContainer(unittest.TestCase):

    def _make_vm(self, **extra):
        base = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
        }
        base.update(extra)
        return base

    def _run_create(self, vm_, client):
        with patch.object(incus_driver, "_client", return_value=client):
            return incus_driver.create(vm_)

    def _setup_client(self):
        client = MagicMock()
        # create → ok async, start → ok async
        ok_async = {"type": "async", "error_code": None, "operation": "/1.0/operations/abc"}
        ok_op = _ok({"status_code": 200})
        # _sync_request is called for POST /instances and PUT /state
        client._sync_request.return_value = _ok({})
        # _wait_for_ip uses _request internally — simulate IP immediately available
        client._request.return_value = _ok({
            "status": "Running",
            "network": {
                "eth0": {"addresses": [{"family": "inet", "scope": "global", "address": "10.1.1.1"}]}
            }
        })
        return client

    def test_default_type_is_container(self):
        client = self._setup_client()
        vm_ = self._make_vm()
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["type"], "container")

    def test_type_vm_maps_to_virtual_machine(self):
        client = self._setup_client()
        vm_ = self._make_vm(type="vm")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["type"], "virtual-machine")

    def test_type_virtual_machine_passthrough(self):
        client = self._setup_client()
        vm_ = self._make_vm(type="virtual-machine")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["type"], "virtual-machine")

    def test_unknown_type_raises(self):
        client = self._setup_client()
        vm_ = self._make_vm(type="hypervisor")
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.create(vm_)

    def test_cpu_mapped_to_limits_cpu(self):
        client = self._setup_client()
        vm_ = self._make_vm(cpu=4)
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["config"]["limits.cpu"], "4")

    def test_memory_mapped_to_limits_memory(self):
        client = self._setup_client()
        vm_ = self._make_vm(memory="4GB")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["config"]["limits.memory"], "4GB")

    def test_cloud_init_mapped_to_user_data(self):
        client = self._setup_client()
        vm_ = self._make_vm(cloud_init="#cloud-config\npackages: [nginx]")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertIn("user.user-data", payload["config"])

    def test_disk_size_creates_root_device(self):
        client = self._setup_client()
        vm_ = self._make_vm(disk_size="20GB", storage_pool="default")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertIn("root", payload["devices"])
        self.assertEqual(payload["devices"]["root"]["size"], "20GB")
        self.assertEqual(payload["devices"]["root"]["pool"], "default")

    def test_network_creates_eth0_device(self):
        client = self._setup_client()
        vm_ = self._make_vm(network="incusbr0")
        self._run_create(vm_, client)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertIn("eth0", payload["devices"])
        self.assertEqual(payload["devices"]["eth0"]["network"], "incusbr0")

    def test_image_required(self):
        client = self._setup_client()
        vm_ = {"name": "testvm", "deploy": False}
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.create(vm_)


# ---------------------------------------------------------------------------
# 9. Config/devices merge precedence
# ---------------------------------------------------------------------------

class TestMergePrecedence(unittest.TestCase):

    def _setup_client(self):
        client = MagicMock()
        client._sync_request.return_value = {"error_code": None, "metadata": {}}
        client._request.return_value = {"error_code": None, "metadata": {
            "status": "Running",
            "network": {"eth0": {"addresses": [
                {"family": "inet", "scope": "global", "address": "10.0.0.1"}
            ]}}
        }}
        return client

    def test_generated_overrides_raw_config(self):
        """cpu/memory/cloud_init override raw config keys of the same name."""
        client = self._setup_client()
        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "cpu": 8,
            # raw config sets limits.cpu to 2; generated (cpu=8) should win
            "config": {"limits.cpu": "2", "security.nesting": "true"},
        }
        with patch.object(incus_driver, "_client", return_value=client):
            incus_driver.create(vm_)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload["config"]["limits.cpu"], "8")
        # raw config keys that are not overridden should survive
        self.assertEqual(payload["config"]["security.nesting"], "true")

    def test_raw_devices_preserved_when_no_generated(self):
        client = self._setup_client()
        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "devices": {"gpu0": {"type": "gpu"}},
        }
        with patch.object(incus_driver, "_client", return_value=client):
            incus_driver.create(vm_)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertIn("gpu0", payload["devices"])


# ---------------------------------------------------------------------------
# 10. Target / cluster placement
# ---------------------------------------------------------------------------

class TestTargetPlacement(unittest.TestCase):

    def _setup_client(self):
        client = MagicMock()
        client._sync_request.return_value = {"error_code": None, "metadata": {}}
        client._request.return_value = {"error_code": None, "metadata": {
            "status": "Running",
            "network": {"eth0": {"addresses": [
                {"family": "inet", "scope": "global", "address": "10.0.0.1"}
            ]}}
        }}
        return client

    def test_target_added_to_payload(self):
        client = self._setup_client()
        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "target": "node01",
        }
        with patch.object(incus_driver, "_client", return_value=client):
            incus_driver.create(vm_)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload.get("target"), "node01")

    def test_no_target_when_not_set(self):
        client = self._setup_client()
        vm_ = {"name": "testvm", "image": "ubuntu/22.04", "deploy": False}
        with patch.object(incus_driver, "_client", return_value=client):
            incus_driver.create(vm_)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertNotIn("target", payload)

    def test_legacy_location_accepted(self):
        client = self._setup_client()
        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "location": "node02",
        }
        with patch.object(incus_driver, "_client", return_value=client):
            incus_driver.create(vm_)
        payload = client._sync_request.call_args_list[0][1]["data"]
        self.assertEqual(payload.get("target"), "node02")


# ---------------------------------------------------------------------------
# 11. Wait loop: success and timeout branches
# ---------------------------------------------------------------------------

class TestWaitForIp(unittest.TestCase):

    def _running_with_ip(self):
        return {"error_code": None, "metadata": {
            "status": "Running",
            "network": {"eth0": {"addresses": [
                {"family": "inet", "scope": "global", "address": "10.1.2.3"}
            ]}}
        }}

    def _stopped(self):
        return {"error_code": None, "metadata": {"status": "Stopped", "network": {}}}

    def test_returns_ip_when_instance_running(self):
        client = MagicMock()
        client._request.return_value = self._running_with_ip()
        ips = incus_driver._wait_for_ip(client, "testvm", timeout=5, interval=0)
        self.assertEqual(ips, ["10.1.2.3"])

    def test_returns_empty_on_timeout(self):
        client = MagicMock()
        client._request.return_value = self._stopped()
        ips = incus_driver._wait_for_ip(client, "testvm", timeout=0, interval=0)
        self.assertEqual(ips, [])

    def test_fail_on_wait_timeout_raises(self):
        client = MagicMock()
        client._sync_request.return_value = {"error_code": None, "metadata": {}}
        client._request.return_value = self._stopped()

        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "wait_for_ip": True,
            "wait_timeout": 0,
            "fail_on_wait_timeout": True,
        }
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.create(vm_)

    def test_no_raise_when_fail_on_timeout_false(self):
        client = MagicMock()
        client._sync_request.return_value = {"error_code": None, "metadata": {}}
        client._request.return_value = self._stopped()

        vm_ = {
            "name": "testvm",
            "image": "ubuntu/22.04",
            "deploy": False,
            "wait_for_ip": True,
            "wait_timeout": 0,
            "fail_on_wait_timeout": False,
        }
        with patch.object(incus_driver, "_client", return_value=client):
            # Should not raise, just return node with empty IPs
            node = incus_driver.create(vm_)
        self.assertEqual(node["private_ips"], [])


# ---------------------------------------------------------------------------
# 12. Destroy — call dispatch
# ---------------------------------------------------------------------------

class TestDestroy(unittest.TestCase):

    def test_raises_if_not_action(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.destroy("testvm", call="function")

    def test_raises_not_found(self):
        client = MagicMock()
        client._request.return_value = _err("not found", 404)
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudNotFound):
                incus_driver.destroy("missing", call="action")

    def test_stops_running_instance_before_delete(self):
        client = MagicMock()
        # GET instance → Running
        client._request.return_value = _ok({"status": "Running"})
        # stop and delete succeed
        client._sync_request.return_value = _ok({})
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.destroy("testvm", call="action")
        self.assertTrue(result["testvm"]["destroyed"])
        # first sync_request is stop, second is delete
        stop_call = client._sync_request.call_args_list[0]
        self.assertIn("stop", stop_call[1]["data"]["action"])

    def test_returns_destroyed_true(self):
        client = MagicMock()
        client._request.return_value = _ok({"status": "Stopped"})
        client._sync_request.return_value = _ok({})
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.destroy("testvm", call="action")
        self.assertEqual(result, {"testvm": {"destroyed": True}})


# ---------------------------------------------------------------------------
# 13. show_instance — call dispatch and output shape
# ---------------------------------------------------------------------------

class TestShowInstance(unittest.TestCase):

    def test_raises_if_not_action(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.show_instance("testvm", call="function")

    def test_raises_not_found(self):
        client = MagicMock()
        client._request.return_value = _err("not found", 404)
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudNotFound):
                incus_driver.show_instance("missing", call="action")

    def test_returns_normalized_shape(self):
        client = MagicMock()
        instance_resp = _ok({
            "name": "testvm",
            "status": "Running",
            "profiles": ["default"],
            "expanded_config": {"image.description": "Ubuntu 22.04"},
        })
        state_resp = _ok({
            "network": {
                "eth0": {"addresses": [{"family": "inet", "scope": "global", "address": "10.0.0.5"}]}
            }
        })
        client._request.side_effect = [instance_resp, state_resp]
        with patch.object(incus_driver, "_client", return_value=client):
            node = incus_driver.show_instance("testvm", call="action")
        self.assertEqual(node["id"], "testvm")
        self.assertEqual(node["state"], "running")
        self.assertEqual(node["private_ips"], ["10.0.0.5"])
        self.assertEqual(node["public_ips"], [])


# ---------------------------------------------------------------------------
# 14. start / stop / reboot — call dispatch
# ---------------------------------------------------------------------------

class TestLifecycle(unittest.TestCase):

    def test_start_raises_if_not_action(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.start("testvm", call="function")

    def test_stop_raises_if_not_action(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.stop("testvm", call="function")

    def test_reboot_raises_if_not_action(self):
        with self.assertRaises(_exc_mod.SaltCloudSystemExit):
            incus_driver.reboot("testvm", call="function")

    def test_start_sends_start_action(self):
        client = MagicMock()
        client._sync_request.return_value = _ok({})
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.start("testvm", call="action")
        self.assertTrue(result["testvm"]["started"])
        data = client._sync_request.call_args[1]["data"]
        self.assertEqual(data["action"], "start")

    def test_stop_sends_stop_action(self):
        client = MagicMock()
        client._sync_request.return_value = _ok({})
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.stop("testvm", call="action")
        self.assertTrue(result["testvm"]["stopped"])
        data = client._sync_request.call_args[1]["data"]
        self.assertEqual(data["action"], "stop")

    def test_reboot_sends_restart_action(self):
        client = MagicMock()
        client._sync_request.return_value = _ok({})
        with patch.object(incus_driver, "_client", return_value=client):
            result = incus_driver.reboot("testvm", call="action")
        self.assertTrue(result["testvm"]["rebooted"])
        data = client._sync_request.call_args[1]["data"]
        self.assertEqual(data["action"], "restart")

    def test_start_raises_on_api_error(self):
        client = MagicMock()
        client._sync_request.return_value = _err("start failed", 500)
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.start("testvm", call="action")

    def test_stop_raises_on_api_error(self):
        client = MagicMock()
        client._sync_request.return_value = _err("stop failed", 500)
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.stop("testvm", call="action")

    def test_reboot_raises_on_api_error(self):
        client = MagicMock()
        client._sync_request.return_value = _err("restart failed", 500)
        with patch.object(incus_driver, "_client", return_value=client):
            with self.assertRaises(_exc_mod.SaltCloudException):
                incus_driver.reboot("testvm", call="action")


if __name__ == "__main__":
    unittest.main()
