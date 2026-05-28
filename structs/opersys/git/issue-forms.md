# GitHub Issue Forms

These issue forms define reusable YukonSYS intake standards for GitHub
repositories.

## Template Index

| Template | Use when |
| --- | --- |
| `.github/ISSUE_TEMPLATE/bug.yml` | Reporting incorrect behavior, regressions, or broken documentation. |
| `.github/ISSUE_TEMPLATE/task.yml` | Tracking bounded implementation, documentation, or operations work. |
| `.github/ISSUE_TEMPLATE/change_request.yml` | Requesting planned infrastructure, service, security, or automation changes. |
| `.github/ISSUE_TEMPLATE/incident.yml` | Capturing active or recent incidents. |
| `.github/ISSUE_TEMPLATE/problem.yml` | Investigating recurring incidents, unknown root cause, or systemic defects. |
| `.github/ISSUE_TEMPLATE/service_request.yml` | Requesting access, provisioning, DNS, certificate, repository, or routine service work. |
| `.github/ISSUE_TEMPLATE/security_finding.yml` | Tracking non-private security findings that are safe for repository discussion. |
| `.github/ISSUE_TEMPLATE/hardware_fault.yml` | Tracking server, storage, network, power, cabling, or peripheral faults. |
| `.github/ISSUE_TEMPLATE/rfc_design_proposal.yml` | Proposing a design, architecture change, standard, or operating model. |

## Standard Expectations

- Do not include plaintext secrets, private keys, tokens, passwords, keytabs, or
  sensitive screenshots.
- Use exact timestamps when incident or maintenance timing matters.
- Separate verified evidence from assumptions.
- Use the repository private security disclosure path when public discussion
  would expose exploit-ready detail.
- Keep labels aligned with `structs/opersys/git/labels/core-labels.md`.
