# Aff Partners Info — Google Apps Script

Скрипт автоматизации для Google Sheets `Aff Partners info`.

## Что делает

Скрипт обрабатывает изменения в Google Таблице и выполняет несколько автоматизаций:

1. Обработка статусов сделок на листе `Approves partner's deals`
   - реагирует на изменение `Approval status`
   - отправляет уведомления в Slack
   - создаёт и обновляет Slack-треды
   - добавляет реакции по статусам
   - переносит approved-сделки в `Monthly Partner's active campaigns`

2. Синхронизация `Monthly Partner's active campaigns` → План/Факт
   - переносит FF / Setup fee сделки в таблицу План/Факт
   - использует `unique_key`
   - обновляет существующие строки, а не создаёт дубли

3. Partner Base → Справочник Affilka
   - синхронизирует `Aff manager`
   - пишет изменения в лист `affiliate_change`

4. Поиск партнёров → статистика
   - считает новые сайты
   - считает пинги
   - обновляет статистику по периодам и Aff manager

5. Автоматический сброс чекбоксов
   - функция `resetSearchPingCheckboxesForNewPeriod`
   - запускается по time-based trigger

## Основные листы

В активной таблице:

- `Approves partner's deals`
- `Monthly Partner's active campaigns`
- `Partner Base`
- `Поиск партнёров`
- `Поиск партнеров стат.`
- `SlackLog`
- `MonthlyAlertLog`

Во внешней таблице План/Факт:

- `SEO Обзорники`
- `Справочник Affilka`
- `affiliate_change`

## Триггеры

В проекте используются триггеры:

| Тип | Функция | Назначение |
|---|---|---|
| On edit | `onEdit` | Основная обработка изменений в таблице |
| Time-based | `resetSearchPingCheckboxesForNewPeriod` | Сброс чекбоксов нового периода |

## Script Properties

В Apps Script должны быть заданы свойства:

```text
SLACK_BOT_TOKEN=
SLACK_CHANNEL=
MONTHLY_ALERT_WEBHOOK_URL=