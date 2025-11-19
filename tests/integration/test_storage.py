from conftest import (
    create_case_parametrize,
    check_json_equals,
    check_stdout_contains,
    check_local_shell
)

@create_case_parametrize("tests/integration/data/storage.yml")
def test_storage_create(case, setup_environment, run_salt_command):
    # Фильтруем только тесты на создание
    if case.get("pillars", {}).get("incus", {}).get("storage_pools", {}).get(list(case["pillars"]["incus"]["storage_pools"].keys())[0], {}).get("ensure") != "present":
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


@create_case_parametrize("tests/integration/data/storage.yml")
def test_storage_delete(case, setup_environment, run_salt_command):
    # Фильтруем только тесты на удаление
    if case.get("pillars", {}).get("incus", {}).get("storage_pools", {}).get(list(case["pillars"]["incus"]["storage_pools"].keys())[0], {}).get("ensure") != "absent":
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
