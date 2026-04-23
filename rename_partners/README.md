# rename_partners

Скрипты для:
- переименования партнёров через API
- синхронизации колонки Affiliate в Google Sheets после переименования

## Файлы
- `rename_partners.py` — основной скрипт переименования
- `sync_affiliate_column_with_api_check.py` — синхронизация Affiliate после успешного rename
- `.env` — локальные настройки, не хранится в Git
- `.env.example` — шаблон настроек
- `credentials.json` — Google OAuth client, не хранится в Git
- `token.json` — Google OAuth token, не хранится в Git

## Как подготовить
1. Скопировать `.env.example` в `.env`
2. Заполнить переменные окружения
3. Положить рядом `credentials.json`
4. Первый запуск создаст или обновит `token.json`

## Установка зависимостей
```bash
pip install -r requirements.txt

## Запуск
python rename_partners.py
python sync_affiliate_column_with_api_check.py