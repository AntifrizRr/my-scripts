# Integration Automation Toolkit

This portfolio repository contains Google Apps Script and Python utilities for partner operations automation, spreadsheet synchronization, and operational notifications.

## What the project demonstrates
- integration with a partner platform API
- operational spreadsheet workflows in Google Sheets
- Slack-based approval and notification flows
- reporting synchronization and audit logging
- idempotent processing with retry-aware error handling

## Core workflows
1. Approval workflow on the operational sheet
2. Monthly campaign synchronization into the reporting spreadsheet
3. Partner-base updates into the affiliate reference sheet
4. Search-partner statistics and period-based counters

## Script Properties
The Apps Script project expects the following properties:

| Property | Required | Purpose | Safe example |
|---|---|---|---|
| PF_SPREADSHEET_ID | Yes | Target reporting spreadsheet identifier | example-spreadsheet-id |
| PF_PLATFORM_NAME | Optional | Platform label for reporting rows | partner-platform |
| SLACK_BOT_TOKEN | Yes | Slack bot token for outgoing messages | xoxb-example |
| SLACK_CHANNEL | Yes | Slack channel or conversation id | C1234567890 |
| MONTHLY_ALERT_WEBHOOK_URL | Optional | Webhook used for monthly alerts | https://example.invalid/webhook |
| SLACK_ON_APPROVAL_MENTION | Optional | Mention used for approval notifications | <@example> |
| SLACK_ANALYST_MENTION | Optional | Mention used for analyst notifications | <@analyst> |
| SLACK_DEFAULT_STATUS_MENTION | Optional | Default mention for status changes | <@ops> |
| AFF_MANAGER_STATUS_TAGS_JSON | Optional | Mapping of aff manager values to Slack mentions | {"ops":"<@ops>"} |

## Security approach
- Keep real secrets and internal identifiers out of the repository.
- Load configuration through Script Properties rather than hard-coded constants.
- Use synthetic demo data for public examples.

## Local setup
1. Copy the Apps Script configuration example.
2. Add the required Script Properties in the Apps Script editor.
3. Keep credentials and production identifiers local and private.
