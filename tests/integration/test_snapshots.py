from conftest import (
    create_case_parametrize,
    check_json_equals,
    check_stdout_contains,
    check_local_shell
)

@create_case_parametrize("tests/integration/data/snapshots.yml")
def test_snapshots_create(case, setup_environment, run_salt_command):

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


@create_case_parametrize("tests/integration/data/snapshots.yml")
def test_snapshots_delete(case, setup_environment, run_salt_command):
    if case.get("pillars", {}).get("incus", {}).get("instance_snapshots", {}).get(list(case["pillars"]["incus"]["instance_snapshots"].keys())[0], {}).get("ensure") != "absent":
        return

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


@create_case_parametrize("tests/integration/data/snapshots.yml")
def test_snapshots_restore(case, setup_environment, run_salt_command):
    if case.get("pillars", {}).get("incus", {}).get("instance_snapshots", {}).get(list(case["pillars"]["incus"]["instance_snapshots"].keys())[0], {}).get("ensure") != "restored":
        return

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
