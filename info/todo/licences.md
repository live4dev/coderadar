# Licence scanner

The scanner must:
- detect dependencies from common manifest and lock files across major ecosystems
- identify direct and transitive dependencies when possible
- detect dependency licenses and normalize them to SPDX identifiers
- mark unknown licenses and flag risky licenses for review
- store results in SQLite
- produce both structured JSON output and a human-readable summary
- be modular, so new ecosystems and future vulnerability scanning can be added easily

For each repository, report:
- total dependencies
- direct vs transitive counts
- detected licenses
- unknown licenses
- risky licenses
- repository-level license risk score
