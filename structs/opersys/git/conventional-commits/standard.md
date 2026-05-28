# Conventional Commit Standard

YukonSYS repositories should use Conventional Commits unless a repository has a
stricter local policy.

## Format

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Types

```text
feat
fix
docs
test
refactor
perf
build
ci
chore
revert
security
infra
ops
```

## Examples

```text
docs(github): add issue and PR template standards
infra(ansible): add inference service role defaults
fix(netbox): correct Thor AGX management interface facts
security(ssh): add Vault CA trust validation
```

## Rules

- Keep the subject line short and imperative.
- Use `BREAKING CHANGE:` in the footer for incompatible behavior.
- Use `security` for security-sensitive changes even when the diff is also
  infrastructure or documentation.
- Use `infra` for live-system automation, host configuration, network, storage,
  DNS, and source-of-truth changes.
- Use `ops` for runbooks, operational workflows, incident response, monitoring,
  and handoff mechanics.
- Reference issues or PRs in the body or footer when useful, not by hiding
  context in the subject.
