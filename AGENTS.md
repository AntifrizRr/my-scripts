# AGENTS.md

## Repository guidance
- Never commit secrets, credentials, tokens, webhook URLs, or internal spreadsheet identifiers.
- Keep production trigger names intact when editing Apps Script.
- Preserve backward compatibility for existing spreadsheet columns and rename marks when possible.
- Run available checks before proposing changes.
- Treat data loss, duplicate processing, secret exposure, and silent partial writes as P1 findings.
- Use only manually reviewed and anonymized data examples in the public repository.
