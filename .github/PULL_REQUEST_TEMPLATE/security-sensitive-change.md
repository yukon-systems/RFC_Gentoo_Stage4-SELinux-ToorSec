## Summary

<!-- What security-sensitive behavior changed? Keep this to 2-5 bullets. -->

-

## Security Domain

- [ ] Authentication or identity.
- [ ] Authorization, policy, RBAC, sudo, HBAC, or ACLs.
- [ ] Secrets, certificates, keys, or vault integration.
- [ ] Network exposure, firewall, VPN, proxy, or bastion path.
- [ ] Cryptography, signing, hashing, or token handling.
- [ ] Scanning, audit, logging, or detection.
- [ ] Hardening or compliance.

## Threat / Risk Context

<!-- What threat, finding, incident, or control gap does this address? -->

-

## Secret Handling

- [ ] No plaintext secret values are committed.
- [ ] Private keys, tokens, passwords, keytabs, seed material, and vault payloads are excluded.
- [ ] Secret references use backend names, variable names, or key IDs only.
- [ ] Logs, screenshots, test fixtures, and examples were checked for secret leakage.

## Validation

- [ ] Static checks:
- [ ] Unit or fixture tests:
- [ ] Negative/denial-path tests:
- [ ] Live read-only checks:
- [ ] Live apply checks, if applicable:

## Rollback / Break-Glass

Rollback path:

Break-glass path:

Access preserved:

## Reviewer Checklist

- [ ] Least privilege is preserved or improved.
- [ ] Failure modes fail closed where appropriate.
- [ ] Auditability is preserved.
- [ ] Recovery access is documented without exposing credentials.
