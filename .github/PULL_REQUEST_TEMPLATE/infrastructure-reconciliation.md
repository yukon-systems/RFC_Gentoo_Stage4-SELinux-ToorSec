## Summary

<!-- What infrastructure or source-of-truth records changed? Keep this to 2-5 bullets. -->

- 

## Source Of Truth

<!-- Identify authoritative systems and evidence used: NetBox, live host output, switch/router state, BMC, UPS/PDU/ATS UI, labels, invoices, etc. -->

- Authoritative system:
- Live evidence:
- Operator-supplied facts:

## Scope

<!-- List sites, racks, hosts, VMs, containers, IPs, services, cables, power devices, or inventory classes touched. -->

- 

## Changes Applied

<!-- Distinguish creates, updates, moves, and no-op/idempotence results. -->

Created:

- 

Updated:

- 

Moved/Reassigned:

- 

Not changed:

- 

## Safety And Blast Radius

<!-- State snapshots, backups, read-only checks, write gates, and anything intentionally avoided. -->

- [ ] Snapshot or backup captured where appropriate.
- [ ] No secrets were added to source control or NetBox comments.
- [ ] No destructive inventory cleanup was performed without explicit approval.
- [ ] Power-control, network-control, or credential changes are explicitly called out if present.

## Validation

<!-- Commands run and results observed. Include idempotence checks where applicable. -->

- [ ] Live inventory comparison:
- [ ] Source-of-truth query:
- [ ] Dry-run/idempotence:
- [ ] Reachability or service check:

## Gaps And Follow-Up

<!-- What remains unknown or intentionally deferred? -->

- 

## Rollback

<!-- How to restore the previous source-of-truth or live state if this is wrong. -->


## Reviewer Checklist

- [ ] The PR separates verified facts from assumptions.
- [ ] The source-of-truth system remains internally consistent.
- [ ] The change does not hide stale records that still need review.
- [ ] Follow-up work is explicit and owned.
