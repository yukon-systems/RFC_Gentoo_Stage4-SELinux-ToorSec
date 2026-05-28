# Core GitHub Label Taxonomy

Use these labels as the baseline controlled vocabulary for YukonSYS
repositories. Repositories may add service-specific `area/*` labels, but should
avoid replacing the core taxonomy with ad hoc names.

## Type

```text
type/bug
type/feature
type/task
type/incident
type/problem
type/change
type/service-request
type/security
type/hardware
type/docs
```

## Priority

```text
priority/p0
priority/p1
priority/p2
priority/p3
priority/p4
```

## State

```text
state/needs-triage
state/accepted
state/blocked
state/in-progress
state/waiting-on-reporter
state/waiting-on-vendor
state/needs-approval
state/needs-validation
state/ready-to-close
```

## Risk

```text
risk/low
risk/medium
risk/high
risk/critical
```

## Area Examples

```text
area/ansible
area/dns
area/netbox
area/network
area/storage
area/power
area/security
area/github
area/docs
area/agentic-workflow
```

## Rules

- Prefer one `type/*` label per issue or PR.
- Use `priority/*` for urgency and `risk/*` for blast radius; do not conflate
  the two.
- Use `state/*` labels to represent workflow state, not the issue title.
- Add or rename labels through a documented change rather than one-off UI
  edits when the repository participates in shared automation.
