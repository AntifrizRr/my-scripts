# Manually anonymized workbook example

This directory is reserved for a manually prepared workbook that helps explain the Google Sheets workflow.

Recommended file name:

```text
workflow_example.xlsx
```

## What to preserve

Keep only the parts that help a reviewer understand the automation:

- relevant sheet structure;
- column names used by the script;
- a small number of representative rows;
- status values and relationships between fields;
- formatting only where it helps explain the workflow.

## What to remove or replace

Before committing the file:

- replace company, project, partner, campaign, and employee names;
- replace all IDs, emails, domains, URLs, Slack mentions, and account names;
- remove credentials, tokens, webhook URLs, spreadsheet IDs, and API endpoints;
- remove unnecessary rows and historical data;
- remove comments, notes, hidden sheets, hidden rows, and hidden columns;
- remove named ranges, external links, data connections, queries, and macros;
- check formulas for embedded identifiers or internal sheet names;
- clear document properties such as author, company, manager, and last editor;
- open the finished copy and review every visible sheet before publishing.

The example should be understandable without access to the original company systems and should not contain data copied directly from production.
