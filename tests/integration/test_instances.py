import pytest
from conftest import (
    create_case_parametrize,
    check_json_equals,
    check_stdout_contains,
    check_local_shell, run_local_shell
)

from conftest import run_local_shell

def setup_module(module):
    run_local_shell("incus image copy images: ubuntu/22.04 local: --alias ubuntu-22.04")
    run_local_shell("incus image copy images: ubuntu/22.04/cloud local: --alias ubuntu-22.04-vm")

    run_local_shell("echo setup > /tmp/sm")
    print(f"[SETUP MODULE] {module.__file__}")

def teardown_module(module):
    # run_local_shell("incus image delete ubuntu-22.04")
    # run_local_shell("incus image delete ubuntu-22.04-vm")
    run_local_shell("echo teardown > /tmp/tm")
    print(f"[TEARDOWN MODULE] {module.__file__}")


@create_case_parametrize("tests/integration/data/instances.yml")
def test_instances_create(case, setup_environment, run_salt_command):

    setup_environment(case.get("setup"))

    result = run_salt_command(
        name=case["name"],
        command=case["command"],
        pillars=case.get("pillars"),
        cleanup=case.get("cleanup")
    )

    expected = case.get("expected", {})


    if "json_equals" in expected:
        check_json_equals(result, expected["json_equals"])


    if "salt_output_contains" in expected:
        check_stdout_contains(result, expected["salt_output_contains"], should_contain=True)


    if "salt_output_not_contains" in expected:
        check_stdout_contains(result, expected["salt_output_not_contains"], should_contain=False)


    if "local_shell" in expected:
        check_local_shell(expected["local_shell"])
