import pytest
import yaml
import subprocess
import json
import tempfile
import shutil
from pathlib import Path


# ============================================================
# PyTest options
# ============================================================

def pytest_addoption(parser):
    group = parser.getgroup("salt")

    repo_root = Path(__file__).resolve().parents[2]

    group.addoption(
        "--salt-file-root",
        action="store",
        default=str(repo_root),
        help="Salt file_root pointing to the formula root",
    )

    integration_root = Path(__file__).resolve().parent
    group.addoption(
        "--salt-pillar-root",
        action="store",
        default=str(integration_root / "_pillars"),
        help="Salt pillar_root for tests",
    )

    group.addoption(
        "--salt-modules",
        action="store",
        default=str(repo_root / "_modules"),
        help="Salt _modules directory",
    )

    group.addoption(
        "--salt-states",
        action="store",
        default=str(repo_root / "_states"),
        help="Salt _states directory",
    )

    group.addoption(
        "--salt-log-level",
        action="store",
        default="error",
        choices=["quiet", "info", "warning", "error", "critical", "debug"],
        help="Salt log level for console output (default: error)",
    )


# ============================================================
# Temporary Salt minion configuration
# ============================================================

@pytest.fixture(scope="session")
def salt_temp_dir(request):
    repo_root = Path(request.config.getoption("--salt-file-root"))
    pillar_root = Path(request.config.getoption("--salt-pillar-root"))
    module_dir = Path(request.config.getoption("--salt-modules"))
    states_dir = Path(request.config.getoption("--salt-states"))
    renderer_dir = Path(__file__).resolve().parent / "_renderers"

    tmp_dir = Path(tempfile.mkdtemp(prefix="salt-minion-"))
    cache_dir = tmp_dir / "cache"


    (tmp_dir / "pki" / "minion").mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)


    (tmp_dir / "minion_id").write_text("test-minion\n")


    (tmp_dir / "pki" / "minion" / "minion.pem").touch()


    minion_config = f"""id: test-minion
root_dir: {tmp_dir}

file_client: local
cachedir: {cache_dir}
renderers: incus_jinja, jinja, yaml

render_pipes: True

file_roots:
  base:
    - {repo_root}

pillar_roots:
  base:
    - {pillar_root}

module_dirs:
  - {module_dir}

states_dirs:
  - {states_dir}

renderer_dirs:
  - {renderer_dir}

log_file: {tmp_dir}/minion.log
"""

    (tmp_dir / "minion").write_text(minion_config)

    yield tmp_dir


    shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Collect salt paths
# ============================================================

@pytest.fixture(scope="session")
def salt_paths(salt_temp_dir, request):
    return {
        "config_dir": str(salt_temp_dir),
        "log_level": request.config.getoption("--salt-log-level"),
    }


# ============================================================
# YAML data provider
# ============================================================

def load_yaml_cases(path: str):
    full = Path(path).expanduser().resolve()
    if not full.exists():
        raise FileNotFoundError(f"Data provider not found: {full}")
    with open(full, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def create_case_parametrize(yaml_path: str):
    cases = load_yaml_cases(yaml_path)
    ids = [case.get("name", f"case_{i}") for i, case in enumerate(cases)]
    return pytest.mark.parametrize("case", cases, ids=ids)


# ============================================================
# Helpers
# ============================================================

def run_salt_call(command: str | list, pillars: dict | None, paths):
    log_file = Path(paths["config_dir"]) / "salt-call.log"
    log_level = paths.get("log_level", "error")

    cmd = [
        "salt-call",
        "--local",
        "-l", log_level,
        "--config-dir", paths["config_dir"],
        "--log-file", str(log_file),
        "--log-file-level", "debug",
        "--out=json",
    ]


    if isinstance(command, str):
        cmd.extend(command.split())
    else:
        cmd.extend(command)

    if pillars:
        cmd.append(f"pillar={json.dumps(pillars)}")

    result = subprocess.run(cmd, capture_output=True, text=True)


    result.log_file = str(log_file)

    return result


def run_local_shell(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


# ============================================================
# Result class
# ============================================================

class SaltCallResult:
    def __init__(self, exit_code: int, stdout: str, stderr: str, log_file: str):
        self.exit_code = exit_code
        self.exit_error = stderr if stderr.strip() else None
        self.stdout = stdout
        self.stderr = stderr
        self.log_file = log_file
        self._body = None

    @property
    def body(self):
        """Парсит JSON из stdout и кэширует результат"""
        if self._body is None:
            try:
                self._body = json.loads(self.stdout) if self.stdout else {}
            except Exception as e:
                raise ValueError(
                    f"Failed to parse salt-call JSON output: {e}\nOutput:\n{self.stdout}"
                )
        return self._body


# ============================================================
# Verification methods
# ============================================================

def check_json_equals(result: SaltCallResult, checks: dict):
    if not checks:
        return

    for path, expected_value in checks.items():
        obj = result.body
        for key in path.split("."):
            if key not in obj:
                raise AssertionError(f"JSON path '{path}' not found in response.")
            obj = obj[key]
        assert obj == expected_value, (
            f"JSON mismatch at '{path}': expected {expected_value}, got {obj}"
        )


def check_stdout_contains(result: SaltCallResult, patterns: list, should_contain: bool = True):
    if not patterns:
        return

    for pattern in patterns:
        if should_contain:
            assert pattern in result.stdout, f"'{pattern}' not in salt-call output"
        else:
            assert pattern not in result.stdout, f"'{pattern}' unexpectedly found in output"


def check_local_shell(commands: list):
    if not commands:
        return

    for item in commands:
        r = run_local_shell(item["cmd"])

        if r.returncode != 0 and not item.get("expect_stderr"):
            raise AssertionError(
                f"Local command failed with exit code {r.returncode}:\n{r.stderr}"
            )

        if r.stderr.strip() and not item.get("expect_stderr"):
            raise AssertionError(
                f"Local command produced stderr:\n{r.stderr}"
            )

        for s in item.get("expect_stdout", []):
            assert s in r.stdout, f"'{s}' not found in stdout"

        for s in item.get("expect_not_stdout", []):
            assert s not in r.stdout, f"'{s}' unexpectedly found in stdout"

        for s in item.get("expect_stderr", []):
            assert s in r.stderr, f"'{s}' not found in stderr"


def run_setup(setup_commands: list):
    if not setup_commands:
        return

    for cmd in setup_commands:
        try:
            result = run_local_shell(cmd)
            if result.returncode != 0:
                raise AssertionError(
                    f"Setup command failed: {cmd}\n"
                    f"  returncode: {result.returncode}\n"
                    f"  stderr: {result.stderr}"
                )
        except Exception as e:
            raise AssertionError(f"Setup command raised exception: {cmd}\n  error: {e}")


def run_cleanup(cleanup_commands: list):
    for cmd in cleanup_commands:
        try:
            result = run_local_shell(cmd)
            if result.returncode != 0:
                print(f"Warning: cleanup command failed: {cmd}")
                print(f"  stderr: {result.stderr}")
        except Exception as e:
            print(f"Warning: cleanup command raised exception: {cmd}")
            print(f"  error: {e}")


# ============================================================
# run_salt_command fixture
# ============================================================

@pytest.fixture
def setup_environment():
    def _runner(commands: list = None):
        if commands:
            run_setup(commands)

    return _runner


@pytest.fixture
def run_salt_command(salt_paths, request):
    cleanup_commands = []

    def _runner(name: str, command: str | list, pillars: dict = None, cleanup: list = None):
        nonlocal cleanup_commands

        if cleanup:
            cleanup_commands = cleanup

        subprocess_result = run_salt_call(command, pillars, salt_paths)

        result = SaltCallResult(
            exit_code=subprocess_result.returncode,
            stdout=subprocess_result.stdout,
            stderr=subprocess_result.stderr,
            log_file=subprocess_result.log_file
        )

        if result.exit_error:
            raise AssertionError(
                f"salt-call produced stderr:\n{result.exit_error}"
            )

        # log_file = Path(result.log_file)
        # if log_file.exists():
        #     log_content = log_file.read_text()
        #     if log_content.strip():
        #         print(f"\n{'='*60}\nSalt logs from: {log_file}\n{'='*60}")
        #         print(log_content)
        #         print('='*60)

        return result

    yield _runner

    if cleanup_commands:
        run_cleanup(cleanup_commands)
