# Google Sheets and Slack Automation

This directory contains the Google Apps Script part of the project.

It was created for an operational workflow built around Google Sheets, Slack notifications, and reporting synchronization.

## Main workflows

1. React to status changes in an operational spreadsheet.
2. Send Slack notifications when defined conditions are met.
3. Copy approved records to another sheet.
4. Synchronize reporting and reference data.
5. Store technical processing information in log sheets.

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
| AFF_MANAGER_STATUS_TAGS_JSON | Optional | Mapping of manager values to Slack mentions | {"ops":"<@ops>"} |

## Workbook example

The repository does not generate a demonstration workbook.

A manually anonymized example can be added to [`example-data`](example-data). The example should preserve only the structure needed to understand the workflow and must not contain real company data or identifiers.

## Local setup

1. Copy the Apps Script configuration example.
2. Add the required Script Properties in the Apps Script editor.
3. Keep credentials and production identifiers local and private.
