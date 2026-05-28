## Summary

<!-- What automation changed? Keep this to 2-5 bullets. -->

- 

## Purpose

<!-- Why is this automation needed, and what manual or unreliable workflow does it replace? -->


## Scope

<!-- List files, commands, playbooks, services, or workflows touched. -->

- 

## Safety Model

<!-- Describe write gates, dry-run behavior, idempotence, secret handling, and failure behavior. -->

- [ ] Defaults are read-only, dry-run, or otherwise safe where practical.
- [ ] Write operations require explicit operator intent.
- [ ] Secret values are not logged, committed, or printed.
- [ ] Failure modes are clear and actionable.

## Validation

<!-- Paste command names and summarize results. Do not include secrets. -->

- [ ] Syntax/static checks:
- [ ] Unit or fixture checks:
- [ ] Dry-run or read-only live checks:
- [ ] Apply/live checks, if applicable:

## Rollback

<!-- How do we undo or disable this automation if it behaves incorrectly? -->


## Operational Notes

<!-- Include scheduling, host dependencies, package dependencies, privileges, or follow-up tasks. -->


## Reviewer Checklist

- [ ] The automation is scoped to the stated target.
- [ ] The default path is safe for repeated runs.
- [ ] Validation covers the risky behavior, not just syntax.
- [ ] The rollback path is realistic.
