# GitHub Templates Compliance Standard

This standard adapts the operator-provided template catalog into YukonSYS
repository conventions. It defines the minimum useful GitHub template set,
metadata expectations, and operating rules for human and agentic workers.

## Purpose

GitHub templates should make every issue and pull request reviewable without
requiring private context from a chat session, terminal scrollback, or a single
operator's memory.

The standard has two layers:

- GitHub-consumed files under `.github/ISSUE_TEMPLATE/` and
  `.github/PULL_REQUEST_TEMPLATE/`.
- Reusable source definitions under `structs/` for labels, commit style,
  template metadata, and future wiki/SRE/ITIL/runbook families.

## Operating Profile

YukonSYS infrastructure work commonly includes live hosts, NetBox/IPAM/DCIM,
DNS, power devices, BMCs, Ansible, container runtimes, GitHub automation,
Forge/Codex workers, and hardware that may be physically re-cabled during a
maintenance window.

Templates therefore must emphasize:

- Evidence before completion claims.
- Clear separation of verified facts, assumptions, and desired state.
- Exact validation commands with observed result summaries.
- Rollback or recovery paths for every live-system change.
- Secret safety: no plaintext credentials, private keys, tokens, keytabs,
  seed material, vault payloads, or sensitive screenshots.
- Source-of-truth safety: identify whether NetBox, Git, live host state,
  vendor UI, labels, or operator-supplied observations are authoritative.
- Agentic safety: identify the worker or automation actor and its owned write
  scope when a change is produced by Forge, Codex, or another worker.

## GitHub Pull Request Templates

Required baseline PR templates:

```text
.github/PULL_REQUEST_TEMPLATE/generic-change.md
.github/PULL_REQUEST_TEMPLATE/code-change.md
.github/PULL_REQUEST_TEMPLATE/infrastructure-change.md
.github/PULL_REQUEST_TEMPLATE/infrastructure-reconciliation.md
.github/PULL_REQUEST_TEMPLATE/operational-documentation.md
.github/PULL_REQUEST_TEMPLATE/automation-tooling.md
.github/PULL_REQUEST_TEMPLATE/dependency-upgrade.md
.github/PULL_REQUEST_TEMPLATE/security-sensitive-change.md
.github/PULL_REQUEST_TEMPLATE/emergency-change.md
```

Minimum sections for new PR templates:

```text
Summary
Linked Work / Context
Scope
Validation Evidence
Risk And Rollback
Security / Secrets / Privacy
Reviewer Checklist
```

Infrastructure-sensitive PR templates should also include:

```text
Source Of Truth And Evidence
Safety Model
Agent / Multi-Worker Notes
Post-Merge Tasks
```

## GitHub Issue Forms

Required baseline issue forms:

```text
.github/ISSUE_TEMPLATE/bug.yml
.github/ISSUE_TEMPLATE/task.yml
.github/ISSUE_TEMPLATE/change_request.yml
.github/ISSUE_TEMPLATE/incident.yml
.github/ISSUE_TEMPLATE/problem.yml
.github/ISSUE_TEMPLATE/service_request.yml
.github/ISSUE_TEMPLATE/security_finding.yml
.github/ISSUE_TEMPLATE/hardware_fault.yml
.github/ISSUE_TEMPLATE/rfc_design_proposal.yml
```

Issue forms should use controlled labels and required fields rather than
free-form issue bodies. Repositories consuming these forms should install the
core label taxonomy from `structs/opersys/git/labels/core-labels.md`.

## Many-Forge And Shared Workloads

When multiple Forge workers or other agents are operating in parallel:

- Every worker should declare a worktree path, branch, and owned write scope.
- Shared resources must be named per worker or per branch. Avoid global
  hardcoded paths such as `/tmp/tool.out` when tests can run concurrently.
- Pull requests should identify any temporary files, locks, service ports,
  host aliases, or external state used during validation.
- Durable progress should be posted to the approved memory/notification channel
  for the active operation.
- A final integrator should verify the combined diff instead of assuming each
  worker's local success is sufficient.

## Template Metadata Contract

Reusable templates under `structs/` should include metadata that can be parsed
or indexed later:

```yaml
template_id:
template_family:
title:
version:
status: draft|active|deprecated
owner_role:
applies_to:
audience:
source_basis:
classification:
required_fields:
optional_fields:
validation_rules:
related_templates:
review_cadence:
last_reviewed:
change_control:
```

## Labels

Labels should be treated as a controlled vocabulary. Do not invent ad hoc
labels in a single issue or PR if the label belongs in the shared taxonomy.

Minimum label families:

- `type/*`
- `priority/*`
- `state/*`
- `risk/*`
- `area/*`

See `structs/opersys/git/labels/core-labels.md`.

## Commit Messages

Use Conventional Commits for automation-friendly commit messages unless a repo
has a stricter local policy. See
`structs/opersys/git/conventional-commits/standard.md`.

## Source Basis

- GitHub Docs: issue and pull request templates.
- GitHub Docs: default community health files.
- Conventional Commits 1.0.0.
- Google SRE: service-level objectives and operational reliability patterns.
- NIST SP 800-61 and SP 800-218 for incident response and secure SDLC context.
- OWASP ASVS and OpenAPI for application/API review context.

Future expansion should add SRE, ITIL, wiki, runbook, secure SDLC, hardware,
and public SITREP template families under `structs/opersys/` and
`structs/hwsys/` without weakening the GitHub baseline defined here.
