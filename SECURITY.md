# Security Policy

Do not open public issues or pull requests containing plaintext credentials,
private keys, tokens, passwords, keytabs, seed material, exploit-ready details,
or sensitive operational logs.

## Reporting

For vulnerabilities that can be discussed publicly without exposing sensitive
detail, use the `Security Finding` issue form.

For private vulnerabilities, contact the repository owner or use GitHub private
vulnerability reporting when it is enabled for the repository.

## Handling Rules

- Reference secret locations by backend, variable, or key ID only.
- Do not attach screenshots that expose credentials, tokens, private hostnames
  that are not already public, customer data, or sensitive infrastructure
  details.
- Prefer evidence summaries over raw logs when raw logs may include secrets.
- Record mitigation, validation, and rollback evidence in the linked issue or
  pull request after sensitive details have been removed.
