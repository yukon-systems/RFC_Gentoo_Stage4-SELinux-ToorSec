## Summary

<!-- What infrastructure changed? Keep this to 2-5 bullets. -->

-

## Change Class

- [ ] Standard repeatable change.
- [ ] Normal planned change.
- [ ] Emergency change.
- [ ] Documentation or source-of-truth only.

## Scope

<!-- List sites, racks, hosts, VMs, containers, IPs, networks, storage, DNS, services, repos, or CI systems touched. -->

-

## Source Of Truth And Evidence

Authoritative systems:

-

Live evidence:

-

Operator-supplied facts:

-

## Safety Model

- [ ] Check-mode, dry-run, or read-only evidence was used where possible.
- [ ] Write operations require explicit operator intent.
- [ ] No SELinux dependency was introduced unless explicitly requested.
- [ ] Secrets are referenced by backend/path name only, never by value.
- [ ] Blast radius and dependencies are documented.

## Validation

- [ ] Syntax/static checks:
- [ ] Dry-run/check-mode:
- [ ] Live apply or smoke test:
- [ ] Idempotence check:

## Rollback / Recovery

Rollback trigger:

Rollback steps:

Post-rollback validation:

## Agent / Multi-Worker Notes

<!-- Required when Forge, Codex, or another automation worker participated. -->

Worker or agent:

Owned write scope:

Shared-resource hazards:

## Reviewer Checklist

- [ ] The PR separates verified facts from assumptions.
- [ ] The change is idempotent or explains why not.
- [ ] The rollback path is executable by an operator.
- [ ] Follow-up work is explicit and owned.
