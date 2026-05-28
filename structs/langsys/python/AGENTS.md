# Python Language Standard

## Purpose

These rules define the default Python generation and review standard for agents
working in YukonSYS repositories. Apply them before creating or modifying
Python source, scripts, tests, build helpers, or Python-backed automation.

Repository-local tooling takes precedence. If `pyproject.toml`,
`.pre-commit-config.yaml`, `ruff.toml`, `mypy.ini`, `pytest.ini`, or CI policy
sets stricter rules, follow the repository-local rule.

## Source References

- PEP 8: https://peps.python.org/pep-0008/
- PEP 257: https://peps.python.org/pep-0257/
- Python typing specification: https://typing.python.org/en/latest/spec/
- Python Packaging User Guide `pyproject.toml` specification:
  https://packaging.python.org/en/latest/specifications/pyproject-toml/

## Baseline Style

- Follow PEP 8 unless repository-local tooling says otherwise.
- Use 4 spaces per indentation level. Never mix tabs and spaces.
- Prefer a line length of 88 characters when Black or Ruff formatting is used;
  otherwise use PEP 8 defaults: 79 characters for code and 72 for prose
  comments/docstrings.
- Prefer UTF-8 source without an encoding header unless compatibility requires
  one.
- Use ASCII identifiers and filenames unless a repository-local convention
  explicitly requires otherwise.
- Use LF line endings.
- Do not emit hidden characters, zero-width characters, or byte order marks.

## Imports

- Place imports at the top of the file after the module docstring and any
  `from __future__` imports.
- Group imports in this order with one blank line between groups:
  standard library, third-party packages, local application modules.
- Prefer absolute imports for package code.
- Avoid wildcard imports except for deliberate re-export modules with an
  explicit `__all__`.
- Do not add dependencies casually. Prefer the standard library for small
  scripts and automation unless a dependency materially improves correctness or
  maintainability.

## Naming

- Modules and packages: short lowercase names, with underscores only when they
  improve readability.
- Functions, variables, and methods: `lower_snake_case`.
- Classes and exceptions: `CapWords`; exception classes should normally end in
  `Error`.
- Constants: `UPPER_SNAKE_CASE`.
- Private implementation details: prefix with one underscore.
- Avoid names that shadow builtins unless the repository already uses that
  convention and the scope is tiny.

## Types

- Use type hints for new public functions, CLI parser helpers, dataclasses,
  return values, and non-obvious internal functions.
- Prefer built-in generic syntax on supported Python versions:
  `list[str]`, `dict[str, Any]`, `tuple[str, int]`.
- Use `from __future__ import annotations` in new modules unless repository
  policy says otherwise.
- Use `typing.Protocol`, `TypedDict`, `Literal`, `Self`, and precise unions
  when they improve API clarity.
- Avoid `Any` unless the boundary is genuinely dynamic; isolate it at parsing,
  JSON/YAML, subprocess, or third-party API boundaries.
- Do not use type annotations as decoration. If a type is obvious and local,
  keep the code readable.

## Docstrings and Comments

- Follow PEP 257 for docstrings.
- Add a module docstring for scripts, CLIs, libraries, and test modules with
  non-obvious purpose.
- Public classes and public functions should have docstrings unless their
  behavior is trivial and already clear from the name and types.
- Comments should explain why a decision exists, not restate what the code does.
- Keep operational safety notes near subprocess, filesystem, network, and
  credential-handling code.

## Error Handling

- Raise specific exceptions with actionable messages.
- Do not swallow exceptions silently.
- Preserve original exceptions with `raise ... from exc` when wrapping context.
- For CLIs, convert expected operational errors to clear stderr or JSON output
  and non-zero exit codes.
- Avoid broad `except Exception` unless it is at a process boundary and the
  handler records enough context to debug the failure.

## CLI and Script Standards

- Use `argparse` for standard-library CLIs.
- Provide `--help` text with clear names, defaults, and safety constraints.
- Put executable entrypoints behind:

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

- `main()` should return an integer exit status.
- Do not perform network, filesystem, subprocess, or credential side effects at
  import time.
- Prefer JSON output for machine-consumed status and concise text for human
  status.
- Shell out with `subprocess.run(..., check=False, capture_output=True,
  text=True, timeout=...)` when command output must be inspected.
- Avoid `shell=True`. If it is unavoidable, document why and constrain inputs.

## Filesystem, Network, and Secrets

- Treat credentials, tokens, private keys, vault values, and session IDs as
  secrets. Never print them.
- Use `pathlib.Path` for filesystem paths unless an API requires strings.
- Use temporary files or directories for tests; do not write to operator paths
  in unit tests.
- Validate and bound destructive operations. Prefer dry-run or preview modes
  when mutating infrastructure or state.
- Use explicit timeouts for network and subprocess operations.

## Data Models

- Use `dataclasses.dataclass(frozen=True)` for small immutable data containers.
- Use plain dictionaries at serialization boundaries, not as internal data
  models when fields are known.
- Keep JSON/YAML parsing and validation near the boundary where untrusted data
  enters the program.
- Prefer explicit render/parse functions that are easy to unit test.

## Formatting and Tooling

- Prefer Ruff for linting and import hygiene when available.
- Prefer Black-compatible formatting when the repository already uses Black.
- Do not hand-format against a formatter. Run or follow the formatter.
- Keep generated code deterministic. Avoid timestamps, random values, or host
  state in generated files unless required and documented.
- Do not commit generated caches such as `__pycache__/`, `.pytest_cache/`,
  `.mypy_cache/`, `.ruff_cache/`, or coverage output.

## Tests

- Add tests for new parsing, rendering, validation, planning, and CLI behavior.
- Prefer standard-library `unittest` when the repository has no stronger Python
  test framework preference.
- Use `pytest` only when the repository already uses it or explicitly adopts it.
- Use `unittest.mock` for subprocess, network, and external service boundaries.
- For async code, use `unittest.IsolatedAsyncioTestCase` or the repository's
  existing async test framework.
- Tests must not require live NetBox, DNS, SSH, QNAP, PDU, ATS, UPS, RouterOS,
  or production network access unless they are explicitly labeled live tests and
  gated out of default CI.

## Packaging

- Prefer `pyproject.toml` for Python project metadata and tool configuration.
- Keep runtime dependencies separate from development/test dependencies.
- Pin development tooling where reproducibility matters.
- Do not add model, cloud, telemetry, or hosted-service SDK dependencies without
  explicit change-control approval.

## Agent Generation Checklist

Before returning Python code, verify:
- The code imports cleanly.
- Formatting follows repository tooling or this standard.
- Public functions have useful names, type hints, and docstrings where needed.
- External commands and network calls have timeouts.
- Secrets are not printed or logged.
- Tests or validation commands are provided when behavior is non-trivial.
- The code remains portable across the target Python versions in the repo.
