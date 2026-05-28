# Pull Request Templates

These templates define reusable pull request body standards for YukonSYS
repositories. GitHub supports multiple pull request templates when they are
stored in `.github/PULL_REQUEST_TEMPLATE/` and selected with the `template=`
query parameter.

Example:

```text
https://github.com/yukon-systems/<repo>/compare/<base>...<branch>?template=infrastructure-reconciliation.md
```

## Template Index

| Template | Use when |
| --- | --- |
| `generic-change.md` | The change does not fit a more specific template. |
| `code-change.md` | Source-code changes with tests, API impact, migration notes, and regression evidence. |
| `infrastructure-change.md` | Ansible, Terraform, host, network, storage, DNS, CI/CD, or environment changes that may affect live systems. |
| `infrastructure-reconciliation.md` | Reconciling live infrastructure, NetBox, inventory, cables, IPAM, services, or source-of-truth records. |
| `operational-documentation.md` | Adding or updating runbooks, status notes, standards, handoff notes, or operator-facing documentation. |
| `automation-tooling.md` | Adding or changing scripts, playbooks, generated checks, CI helpers, or operational automation. |
| `dependency-upgrade.md` | Library, package, base image, firmware, kernel, runtime, or service dependency upgrades. |
| `security-sensitive-change.md` | Authentication, authorization, secrets, cryptography, network exposure, hardening, audit, or scanning changes. |
| `emergency-change.md` | Break-glass or incident-driven changes where restoration speed is part of the risk model. |

## Standard Review Expectations

Every pull request should make the reviewer able to answer:

- What changed?
- Why is it needed now?
- What evidence supports the change?
- What was intentionally left out?
- What validation was run?
- What rollback or recovery path exists if the change is wrong?

For security-sensitive or infrastructure-sensitive work, do not include secret
values in the pull request body, screenshots, logs, or examples. Refer to secret
locations by name only.

For agentic or multi-worker changes, each PR should also identify the worker or
automation actor, the write scope it owned, and any shared-runtime hazards such
as global `/tmp` filenames, locks, or service ports.
