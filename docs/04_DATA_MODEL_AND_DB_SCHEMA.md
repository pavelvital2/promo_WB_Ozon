# 04_DATA_MODEL_AND_DB_SCHEMA.md

## 1. Назначение документа

Документ фиксирует:
- полную модель данных системы;
- состав таблиц PostgreSQL;
- поля, типы, nullable/non-nullable требования;
- внешние ключи;
- уникальные ограничения;
- обязательные индексы;
- инварианты данных;
- правила согласованности между сущностями.

Документ опирается только на обязательные сущности ТЗ:
- users
- roles
- permissions
- user_permissions
- stores
- user_store_access
- runs
- run_files
- run_summary_audit
- run_detail_audit
- system_logs
- temporary_uploaded_files

Документ не добавляет новые бизнес-сущности MVP.

---

## 2. Краткий итог

База данных строится на PostgreSQL как основное транзакционное хранилище системы.

Обязательные свойства модели:
- все основные сущности имеют внутренний PK;
- все datetime хранятся в UTC;
- все исторические сущности сохраняются без физического удаления, кроме временных технических файлов и записей о них;
- архивирование применяется только к stores;
- блокировка применяется только к users;
- runs, audits и logs не архивируются и не деактивируются;
- detail audit полностью хранится в PostgreSQL;
- история, логи и detail audit поддерживают серверные search/filter/sort/page сценарии через явные индексы;
- run является центральной связующей сущностью между store, user, files, audits и logs.

---

## 3. Общие правила моделирования БД

## 3.1. Обязательные общие правила

1. Каждая таблица имеет первичный ключ `id`.
2. Все временные метки хранятся в UTC.
3. Все FK должны быть явными.
4. Все обязательные поля ТЗ должны быть отражены как NOT NULL, если в ТЗ не указано nullable.
5. Все уникальности из ТЗ должны быть выражены constraint-ами БД.
6. Индексы по search/filter/sort полям являются обязательными.
7. Исторические сущности не удаляются физически:
   - runs
   - run_files
   - run_summary_audit
   - run_detail_audit
   - system_logs
8. Исключение на физическое удаление допускается только для:
   - temporary_uploaded_files
   - физических временных файлов
   если это требуется по правилам очистки временного хранения.

## 3.2. Общие соглашения по типам

Рекомендуемые типы PostgreSQL:
- PK: `bigint` или `bigserial`
- строки короткие: `varchar(...)` или `text`
- datetime UTC: `timestamp with time zone`
- boolean: `boolean`
- JSON: `jsonb`
- enum: PostgreSQL enum type либо проверяемый string enum на уровне БД + приложения

Для жёстких закрытых наборов значений из ТЗ предпочтительна реализация через:
- PostgreSQL enum types,
или
- `varchar` + `CHECK`.

Требование документа:
- наборы значений должны быть закрыты и контролируемы БД, а не только приложением.

## 3.3. Общие соглашения по FK delete/update policy

Так как исторические сущности нельзя терять, для большинства FK применяется принцип:
- `ON DELETE RESTRICT` либо эквивалентный запрет удаления родителя,
- `ON UPDATE RESTRICT` либо стандартное отсутствие каскадного изменения бизнес-ключей.

Причина:
- система не должна разрушать историю запусков, аудита и логов.

---

## 4. Таблица `roles`

## 4.1. Назначение

Справочник базовых ролей пользователя.

## 4.2. Поля

- `id` — PK
- `code` — обязательное, уникальное
- `name` — обязательное, уникальное

## 4.3. Ограничения

- UNIQUE (`code`)
- UNIQUE (`name`)

## 4.4. Обязательные стартовые записи

- admin / Администратор
- manager_lead / Управляющий
- manager / Менеджер

## 4.5. Индексы

- PK index по `id`
- unique index по `code`
- unique index по `name`

## 4.6. Инварианты

1. Роль пользователя всегда одна.
2. Роль должна существовать до создания пользователя.
3. Удаление роли, на которую кто-либо ссылается, запрещено.

---

## 5. Таблица `permissions`

## 5.1. Назначение

Справочник дополнительных точечных прав.

## 5.2. Поля

- `id` — PK
- `code` — обязательное, уникальное
- `name` — обязательное, уникальное
- `description` — nullable

## 5.3. Ограничения

- UNIQUE (`code`)
- UNIQUE (`name`)

## 5.4. Обязательные стартовые записи

- create_store
- edit_store

## 5.5. Индексы

- PK index по `id`
- unique index по `code`
- unique index по `name`

## 5.6. Инварианты

1. Permission может быть назначен многим пользователям.
2. Удаление permission, который уже назначен, запрещено либо допускается только через controlled migration вне MVP.

---

## 6. Таблица `users`

## 6.1. Назначение

Основная сущность пользователя системы.

## 6.2. Поля

- `id` — PK
- `username` — обязательное, уникальное, индексируемое
- `password_hash` — обязательное
- `role_id` — обязательное, FK -> roles.id, индексируемое
- `is_blocked` — обязательное, default false, индексируемое
- `created_at_utc` — обязательное, индексируемое
- `updated_at_utc` — обязательное
- `last_login_at_utc` — nullable

## 6.3. Ограничения

- UNIQUE (`username`)
- FK (`role_id`) -> `roles(id)`

## 6.4. Индексы

- PK index по `id`
- unique index по `username`
- btree index по `role_id`
- btree index по `is_blocked`
- btree index по `created_at_utc`
- комбинированный индекс `(role_id, is_blocked)` допустим как техническое усиление для админского списка пользователей

## 6.5. Инварианты

1. Username уникален по всей системе.
2. Email не обязателен и не участвует в модели данных MVP.
3. Заблокированный пользователь остаётся в системе и истории.
4. Пользователь не удаляется физически, если с ним связаны runs/logs/stores.

---

## 7. Таблица `user_permissions`

## 7.1. Назначение

Связь many-to-many между users и permissions.

## 7.2. Поля

- `id` — PK
- `user_id` — обязательное, FK -> users.id, индексируемое
- `permission_id` — обязательное, FK -> permissions.id, индексируемое
- `created_at_utc` — обязательное

## 7.3. Ограничения

- UNIQUE (`user_id`, `permission_id`)
- FK (`user_id`) -> `users(id)`
- FK (`permission_id`) -> `permissions(id)`

## 7.4. Индексы

- PK index по `id`
- unique index по (`user_id`, `permission_id`)
- btree index по `user_id`
- btree index по `permission_id`

## 7.5. Инварианты

1. Один и тот же permission не может быть назначен одному пользователю дважды.
2. Permission-назначение не заменяет роль.
3. Для проверки доступа всегда учитываются и role, и permissions, и store access.

---

## 8. Таблица `stores`

## 8.1. Назначение

Магазины, привязанные к конкретному маркетплейсу и настройкам расчёта.

## 8.2. Поля

- `id` — PK
- `name` — обязательное
- `marketplace` — обязательное, индексируемое:
  - wb
  - ozon
- `status` — обязательное, индексируемое:
  - active
  - archived
- `wb_threshold_percent` — nullable для Ozon, обязательное для WB
- `wb_fallback_no_promo_percent` — nullable для Ozon, обязательное для WB
- `wb_fallback_over_threshold_percent` — nullable для Ozon, обязательное для WB
- `created_by_user_id` — обязательное, FK -> users.id
- `created_at_utc` — обязательное, индексируемое
- `updated_at_utc` — обязательное
- `archived_at_utc` — nullable
- `archived_by_user_id` — nullable, FK -> users.id

## 8.3. Ограничения

- UNIQUE (`marketplace`, `name`)
- FK (`created_by_user_id`) -> `users(id)`
- FK (`archived_by_user_id`) -> `users(id)`

## 8.4. Индексы

- PK index по `id`
- unique index по (`marketplace`, `name`)
- btree index по `marketplace`
- btree index по `status`
- btree index по `created_at_utc`
- btree index по `created_by_user_id`
- комбинированный индекс (`marketplace`, `status`)
- комбинированный индекс (`status`, `created_at_utc`)

## 8.5. CHECK / инварианты

Обязательный инвариант для marketplace-specific полей:

### Для `marketplace = 'wb'`
Обязательно:
- `wb_threshold_percent IS NOT NULL`
- `wb_fallback_no_promo_percent IS NOT NULL`
- `wb_fallback_over_threshold_percent IS NOT NULL`

### Для `marketplace = 'ozon'`
Допустимо:
- все три WB-поля NULL

Желательно зафиксировать CHECK constraint или эквивалентную проверку:
- если `marketplace='wb'`, то все WB поля заданы;
- если `marketplace='ozon'`, то WB поля могут быть NULL.

## 8.6. Дополнительные числовые ограничения

Для WB-полей допустим CHECK:
- значение integer
- диапазон 0..100

Причина:
- это согласуется с природой процента скидки;
- не меняет бизнес-логику;
- усиливает целостность данных.

## 8.7. Инварианты

1. Архивированный магазин сохраняется в истории.
2. Архивированный магазин не участвует в новых runs.
3. Архивированный магазин не редактируется.
4. Восстановление доступно только через controlled сценарий.
5. Название уникально в пределах marketplace.

---

## 9. Таблица `user_store_access`

## 9.1. Назначение

Связь many-to-many между users и stores.

## 9.2. Поля

- `id` — PK
- `user_id` — обязательное, FK -> users.id, индексируемое
- `store_id` — обязательное, FK -> stores.id, индексируемое
- `created_at_utc` — обязательное

## 9.3. Ограничения

- UNIQUE (`user_id`, `store_id`)
- FK (`user_id`) -> `users(id)`
- FK (`store_id`) -> `stores(id)`

## 9.4. Индексы

- PK index по `id`
- unique index по (`user_id`, `store_id`)
- btree index по `user_id`
- btree index по `store_id`
- комбинированный индекс (`store_id`, `user_id`) допустим для обратных выборок

## 9.5. Инварианты

1. Одна и та же пара user/store не может быть создана дважды.
2. Доступ к store определяется только этой связью в сочетании с ролью/permissions.
3. Администратор логически имеет полный доступ ко всем магазинам независимо от наличия записей в user_store_access; это правило прикладного слоя, а не требование к обязательному заполнению таблицы.

---

## 10. Таблица `runs`

## 10.1. Назначение

Центральная сущность всех операций check/process.

## 10.2. Поля

- `id` — PK
- `public_run_number` — обязательное, уникальное, индексируемое
- `store_id` — обязательное, FK -> stores.id, индексируемое
- `initiated_by_user_id` — обязательное, FK -> users.id, индексируемое
- `operation_type` — обязательное, индексируемое:
  - check
  - process
- `lifecycle_status` — обязательное, индексируемое
- `business_result` — nullable, индексируемое
- `module_code` — обязательное, индексируемое:
  - wb
  - ozon
- `input_set_signature` — обязательное, индексируемое
- `started_at_utc` — обязательное, индексируемое
- `finished_at_utc` — nullable, индексируемое
- `short_result_text` — nullable
- `result_file_id` — nullable, FK -> run_files.id
- `validation_was_auto_before_process` — обязательное, default false
- `created_at_utc` — обязательное
- `updated_at_utc` — обязательное

## 10.3. Ограничения

- UNIQUE (`public_run_number`)
- FK (`store_id`) -> `stores(id)`
- FK (`initiated_by_user_id`) -> `users(id)`
- FK (`result_file_id`) -> `run_files(id)` — отложенно, с учётом порядка вставки/обновления

## 10.4. Индексы

- PK index по `id`
- unique index по `public_run_number`
- btree index по `store_id`
- btree index по `initiated_by_user_id`
- btree index по `operation_type`
- btree index по `lifecycle_status`
- btree index по `business_result`
- btree index по `module_code`
- btree index по `input_set_signature`
- btree index по `started_at_utc`
- btree index по `finished_at_utc`

Обязательные комбинированные индексы для history и run orchestration:
- (`store_id`, `module_code`, `lifecycle_status`)
- (`store_id`, `module_code`, `started_at_utc DESC`)
- (`operation_type`, `lifecycle_status`)
- (`business_result`, `started_at_utc DESC`)
- (`initiated_by_user_id`, `started_at_utc DESC`)

## 10.5. Закрытые наборы значений

### `operation_type`
- check
- process

### Для `operation_type = check`
Допустимые `lifecycle_status`:
- created
- checking
- completed
- failed

Допустимые `business_result`:
- check_passed
- check_passed_with_warnings
- check_failed

### Для `operation_type = process`
Допустимые `lifecycle_status`:
- created
- validating
- processing
- completed
- failed

Допустимые `business_result`:
- validation_failed
- completed
- completed_with_warnings
- failed

## 10.6. CHECK-инварианты по совместимости полей

Нужно зафиксировать БД-инварианты или эквивалентные транзакционные проверки:

1. Если `operation_type='check'`, то `lifecycle_status` может быть только:
   - created/checking/completed/failed

2. Если `operation_type='process'`, то `lifecycle_status` может быть только:
   - created/validating/processing/completed/failed

3. Если `lifecycle_status IN ('created','checking','validating','processing')`, то `business_result IS NULL`

4. Если `lifecycle_status IN ('completed','failed')`, то `business_result` должен быть заполнен

5. Если `operation_type='check'`, то `validation_was_auto_before_process = false`

6. Если `operation_type='check'`, то `result_file_id IS NULL`

7. Если `operation_type='process'` и `business_result IN ('validation_failed','failed')`, то `result_file_id IS NULL`

8. Если `operation_type='process'` и `business_result IN ('completed','completed_with_warnings')`, то `result_file_id` может быть NOT NULL только после успешного сохранения output file

## 10.7. Инвариант marketplace/module

Так как магазин жёстко определяет маркетплейс и модуль, прикладной слой обязан обеспечивать:
- для store.marketplace='wb' -> runs.module_code='wb'
- для store.marketplace='ozon' -> runs.module_code='ozon'

Это должен проверять application layer перед созданием run.
При необходимости может быть усилено через DB trigger, но не за счёт добавления новой сущности.

## 10.8. Инварианты

1. Один run = одна операция = один history record.
2. Check и process никогда не делят одну запись.
3. Process может иметь встроенную auto-validation, но она не создаёт отдельный run.
4. `public_run_number` является пользовательским идентификатором run для UI и логов.
5. `input_set_signature` фиксирует конкретный набор входных файлов.
6. Исторические run не удаляются.

---

## 11. Таблица `run_files`

## 11.1. Назначение

Хранение метаданных файлов, связанных с конкретным run:
- входных;
- выходных.

## 11.2. Поля

- `id` — PK
- `run_id` — обязательное, FK -> runs.id, индексируемое
- `file_role` — обязательное, индексируемое
- `original_filename` — обязательное
- `stored_filename` — обязательное, уникальное
- `storage_relative_path` — обязательное, уникальное
- `mime_type` — обязательное
- `file_size_bytes` — обязательное
- `file_sha256` — обязательное, индексируемое
- `uploaded_at_utc` — обязательное, индексируемое
- `expires_at_utc` — nullable, индексируемое
- `is_available` — обязательное, default true, индексируемое
- `unavailable_reason` — nullable:
  - expired
  - superseded
  - deleted_by_retention_rule
- `created_at_utc` — обязательное

## 11.3. Допустимые `file_role`

### Для WB
- wb_price_input
- wb_promo_input
- wb_result_output

### Для Ozon
- ozon_input
- ozon_result_output

## 11.4. Ограничения

- FK (`run_id`) -> `runs(id)`
- UNIQUE (`stored_filename`)
- UNIQUE (`storage_relative_path`)

## 11.5. Индексы

- PK index по `id`
- btree index по `run_id`
- btree index по `file_role`
- unique index по `stored_filename`
- unique index по `storage_relative_path`
- btree index по `file_sha256`
- btree index по `uploaded_at_utc`
- btree index по `expires_at_utc`
- btree index по `is_available`
- комбинированный индекс (`run_id`, `file_role`)
- комбинированный индекс (`is_available`, `expires_at_utc`)
- комбинированный индекс (`run_id`, `is_available`)

## 11.6. Инварианты

1. Для каждого run входные файлы сохраняются как отдельные физические копии.
2. Дедупликация по хэшу между разными run запрещена.
3. `is_available=false` не удаляет историческую запись.
4. Если `is_available=false`, то `unavailable_reason` должен быть заполнен.
5. Если `is_available=true`, то `unavailable_reason IS NULL`.

## 11.7. Инварианты по составу файлов

Прикладной слой обязан обеспечить:

### Для WB run
- ровно 1 файл `wb_price_input`
- для check/process: от 1 до 20 файлов `wb_promo_input`
- для успешного process: не более 1 файла `wb_result_output`

### Для Ozon run
- ровно 1 файл `ozon_input`
- для успешного process: не более 1 файла `ozon_result_output`

Эти ограничения являются прикладными инвариантами.
Часть из них может быть усилена partial unique index-ами, если выбранный порядок записи это позволяет.

---

## 12. Таблица `run_summary_audit`

## 12.1. Назначение

Хранение сводного аудита run.

## 12.2. Поля

- `id` — PK
- `run_id` — обязательное, уникальное, FK -> runs.id, индексируемое
- `audit_json` — обязательное, JSONB
- `created_at_utc` — обязательное

## 12.3. Ограничения

- UNIQUE (`run_id`)
- FK (`run_id`) -> `runs(id)`

## 12.4. Индексы

- PK index по `id`
- unique index по `run_id`

## 12.5. Инварианты

1. Один run имеет не более одного summary audit.
2. Summary audit обязателен и для check, и для process.
3. Структура `audit_json` зависит от модуля, но хранится единообразно.

---

## 13. Таблица `run_detail_audit`

## 13.1. Назначение

Хранение полного построчного аудита run.

## 13.2. Поля

- `id` — PK
- `run_id` — обязательное, FK -> runs.id, индексируемое
- `row_number` — обязательное, индексируемое
- `entity_key_1` — nullable, индексируемое
- `entity_key_2` — nullable, индексируемое
- `severity` — обязательное, индексируемое:
  - info
  - warning
  - error
- `decision_reason` — nullable, индексируемое
- `message` — обязательное
- `audit_payload_json` — обязательное, JSONB
- `created_at_utc` — обязательное

## 13.3. Ограничения

- FK (`run_id`) -> `runs(id)`

## 13.4. Индексы

Минимально обязательные:
- PK index по `id`
- btree index по `run_id`
- btree index по `row_number`
- btree index по `entity_key_1`
- btree index по `entity_key_2`
- btree index по `severity`
- btree index по `decision_reason`

Обязательные комбинированные индексы для server-side работы:
- (`run_id`, `row_number`)
- (`run_id`, `severity`)
- (`run_id`, `decision_reason`)
- (`run_id`, `entity_key_1`)
- (`run_id`, `row_number`, `severity`)

Для поиска по тексту:
- полнотекстовый индекс либо trigram index по `message`
- trigram/текстовый индекс по `decision_reason`
- при необходимости trigram по `entity_key_1` и `entity_key_2`

## 13.5. Инварианты

1. Detail audit обязателен для check и process.
2. Хранение detail audit вне БД вместо БД запрещено.
3. Для WB в `entity_key_1` должен использоваться Артикул WB, если он есть.
4. Для Ozon в `entity_key_1` должен использоваться OzonID/SKU/Артикул по приоритету доступности.
5. Таблица должна поддерживать до 200 000 строк на один run без client-side выгрузки всего набора.

## 13.6. Уточнение по уникальности

ТЗ не требует уникальности строки по (`run_id`, `row_number`), поэтому её нельзя навязывать на уровне БД как обязательную.
Причина:
- у одного row_number может потребоваться несколько audit rows разных severity/reason.

---

## 14. Таблица `system_logs`

## 14.1. Назначение

Хранение системных и пользовательских событий.

## 14.2. Поля

- `id` — PK
- `event_time_utc` — обязательное, индексируемое
- `user_id` — nullable, FK -> users.id, индексируемое
- `store_id` — nullable, FK -> stores.id, индексируемое
- `run_id` — nullable, FK -> runs.id, индексируемое
- `module_code` — nullable, индексируемое:
  - wb
  - ozon
- `event_type` — обязательное, индексируемое
- `severity` — обязательное, индексируемое:
  - info
  - warning
  - error
- `message` — обязательное
- `payload_json` — nullable, JSONB

## 14.3. Ограничения

- FK (`user_id`) -> `users(id)`
- FK (`store_id`) -> `stores(id)`
- FK (`run_id`) -> `runs(id)`

## 14.4. Индексы

Минимально обязательные:
- PK index по `id`
- btree index по `event_time_utc`
- btree index по `user_id`
- btree index по `store_id`
- btree index по `run_id`
- btree index по `module_code`
- btree index по `event_type`
- btree index по `severity`

Обязательные комбинированные индексы для logs page:
- (`event_time_utc DESC`)
- (`severity`, `event_time_utc DESC`)
- (`event_type`, `event_time_utc DESC`)
- (`user_id`, `event_time_utc DESC`)
- (`store_id`, `event_time_utc DESC`)
- (`run_id`, `event_time_utc DESC`)
- (`module_code`, `event_time_utc DESC`)

Для поиска:
- индекс для текстового поиска по `message`
- быстрый join/search по username и public_run_number обеспечивается индексами на `users.username` и `runs.public_run_number`

## 14.5. Инварианты

1. Логи не заменяют run audit.
2. Логи не архивируются и не деактивируются.
3. Event types должны покрывать обязательные события из ТЗ.
4. Manager не имеет доступа к logs page, но записи логов про его действия могут существовать.

---

## 15. Таблица `temporary_uploaded_files`

## 15.1. Назначение

Хранение временных загруженных файлов активного набора до создания run.

## 15.2. Поля

- `id` — PK
- `uploaded_by_user_id` — обязательное, FK -> users.id, индексируемое
- `store_id` — обязательное, FK -> stores.id, индексируемое
- `module_code` — обязательное, индексируемое:
  - wb
  - ozon
- `original_filename` — обязательное
- `stored_filename` — обязательное, уникальное
- `storage_relative_path` — обязательное, уникальное
- `mime_type` — обязательное
- `file_size_bytes` — обязательное
- `file_sha256` — обязательное, индексируемое
- `uploaded_at_utc` — обязательное, индексируемое
- `expires_at_utc` — обязательное, индексируемое
- `is_active_in_current_set` — обязательное, default true
- `created_at_utc` — обязательное

## 15.3. Ограничения

- FK (`uploaded_by_user_id`) -> `users(id)`
- FK (`store_id`) -> `stores(id)`
- UNIQUE (`stored_filename`)
- UNIQUE (`storage_relative_path`)

## 15.4. Индексы

- PK index по `id`
- btree index по `uploaded_by_user_id`
- btree index по `store_id`
- btree index по `module_code`
- btree index по `file_sha256`
- btree index по `uploaded_at_utc`
- btree index по `expires_at_utc`

Обязательные комбинированные индексы:
- (`uploaded_by_user_id`, `store_id`, `module_code`)
- (`uploaded_by_user_id`, `store_id`, `module_code`, `is_active_in_current_set`)
- (`expires_at_utc`, `is_active_in_current_set`)
- (`store_id`, `module_code`, `uploaded_by_user_id`, `uploaded_at_utc DESC`)

## 15.5. Инварианты

1. Временные файлы существуют в контуре:
   - user + store + module

2. Для одной пары:
   - uploaded_by_user_id
   - store_id
   - module_code  
   существует только один текущий активный временный набор

3. Параллельные активные наборы для одной и той же пары user+store+module запрещены

4. Файл считается тем же только по комбинации:
   - file_sha256
   - file_size_bytes  
   но новая загрузка создаёт новый временный объект, даже если содержимое и имя совпадают

5. После очистки сроком 24 часа набор считается пустым

## 15.6. Важное уточнение по реализации одного активного набора

Так как отдельной сущности “temporary set” в ТЗ нет, active set реализуется как выборка всех строк:
- одного user
- одного store
- одного module
- `is_active_in_current_set = true`

Это допустимо, потому что:
- не вводится новая бизнес-сущность;
- соблюдается модель ТЗ;
- состояние набора восстанавливается по строкам таблицы.

---

## 16. Связи между сущностями

## 16.1. Users / roles / permissions / user_permissions

- `users.role_id` -> `roles.id`
- `user_permissions.user_id` -> `users.id`
- `user_permissions.permission_id` -> `permissions.id`

Кардинальности:
- role 1 -> N users
- user N <-> N permissions через user_permissions

## 16.2. Users / stores / user_store_access

- `stores.created_by_user_id` -> `users.id`
- `stores.archived_by_user_id` -> `users.id`
- `user_store_access.user_id` -> `users.id`
- `user_store_access.store_id` -> `stores.id`

Кардинальности:
- user 1 -> N created stores
- user 1 -> N archived stores
- user N <-> N stores через user_store_access

## 16.3. Stores / runs

- `runs.store_id` -> `stores.id`

Кардинальность:
- store 1 -> N runs

## 16.4. Users / runs

- `runs.initiated_by_user_id` -> `users.id`

Кардинальность:
- user 1 -> N runs

## 16.5. Runs / run_files

- `run_files.run_id` -> `runs.id`
- `runs.result_file_id` -> `run_files.id`

Кардинальности:
- run 1 -> N run_files
- run 0..1 -> 1 result file reference

Уточнение:
- `runs.result_file_id` должен ссылаться только на `run_files.id`, принадлежащий тому же run и являющийся output file. Это прикладной инвариант.

## 16.6. Runs / audits

- `run_summary_audit.run_id` -> `runs.id`
- `run_detail_audit.run_id` -> `runs.id`

Кардинальности:
- run 1 -> 0..1 summary audit во время выполнения, 1 после завершения
- run 1 -> N detail audit rows

## 16.7. Users / stores / runs / system_logs

- `system_logs.user_id` -> `users.id`
- `system_logs.store_id` -> `stores.id`
- `system_logs.run_id` -> `runs.id`

Кардинальности:
- user/store/run 1 -> N system_logs

## 16.8. Users / stores / temporary_uploaded_files

- `temporary_uploaded_files.uploaded_by_user_id` -> `users.id`
- `temporary_uploaded_files.store_id` -> `stores.id`

Кардинальности:
- user 1 -> N temporary files
- store 1 -> N temporary files

---

## 17. Логические read-model зависимости для поиска и страниц

ТЗ требует server-side search/filter/sort/page. Для этого БД-модель должна поддерживать эффективные join-выборки.

## 17.1. History page

Источники:
- `runs`
- `stores`
- `users`
- `run_files` (для original filename / availability)

Обязательный поиск:
- `runs.public_run_number`
- `stores.name`
- `run_files.original_filename`
- `runs.short_result_text`
- `users.username`

## 17.2. Logs page

Источники:
- `system_logs`
- `users`
- `stores`
- `runs`

Обязательный поиск:
- `system_logs.message`
- `users.username`
- `runs.public_run_number`

## 17.3. Run detail audit page

Источник:
- `run_detail_audit`
- при необходимости метаданные run из `runs`

Обязательный поиск:
- `row_number`
- `entity_key_1`
- `entity_key_2`
- `message`
- `decision_reason`

---

## 18. Правила целостности для файлов и доступности

## 18.1. Доступность run files

Инварианты:
- `is_available=true` означает, что файл должен существовать физически и быть доступным к скачиванию при наличии прав
- `is_available=false` означает, что скачивание запрещено, а UI показывает “Файл недоступен”

Причины недоступности:
- expired
- superseded
- deleted_by_retention_rule

## 18.2. Result file and superseded logic

При появлении нового успешного process result по тому же store+module:
- старый успешный output file переводится в `is_available=false`
- `unavailable_reason='superseded'`
- сам historical run сохраняется

Если гонка всё же произошла по технической ошибке:
- текущим успешным результатом считается run с более поздним `finished_at_utc`
- второй результат становится superseded
- в `system_logs` пишется ошибка согласованности

---

## 19. Обязательные event_type для `system_logs`

ТЗ перечисляет обязательные события. В БД/словаре event_type должны поддерживаться как минимум:

- successful_login
- failed_login
- logout
- user_created
- user_updated
- user_blocked
- user_unblocked
- store_created
- store_updated
- store_archived
- store_restored
- store_settings_changed
- file_uploaded
- temporary_file_deleted
- temporary_file_replaced
- check_started
- check_finished
- process_started
- process_finished
- process_finished_with_warnings
- process_error
- result_downloaded
- source_file_downloaded
- temporary_files_auto_purged
- old_result_removed_on_new_success
- system_error

Допустимо хранить `event_type` как string/enum, но набор обязательных событий должен покрываться полностью.

---

## 20. Обязательные decision/severity наборы

## 20.1. Severity в `run_detail_audit`
Закрытый набор:
- info
- warning
- error

## 20.2. Severity в `system_logs`
Закрытый набор:
- info
- warning
- error

## 20.3. Decision_reason
ТЗ не задаёт единый глобальный закрытый справочник decision_reason для всех модулей.
Следовательно:
- отдельная таблица decision_reason не требуется;
- `decision_reason` хранится строкой;
- но модульные наборы reason должны быть стандартизированы в коде и документации соответствующих модулей.

Это не является расширением бизнес-сущностей.

---

## 21. Транзакционные требования к БД-модели

Следующие сценарии должны выполняться транзакционно на прикладном уровне:

1. Создание run:
- проверка допустимости запуска
- запись run
- запись system log о старте

2. Завершение check/process:
- запись summary audit
- запись detail audit
- запись result file metadata при наличии
- обновление run
- запись system log о завершении

3. Superseded result handling:
- определение текущего старого успешного результата
- перевод старого output file в unavailable
- логирование события
- завершение нового run

4. Удаление/замена temp file:
- изменение статуса active set
- обновление/добавление записи temp file
- логирование события

---

## 22. Что должно быть проверено аудитором по БД-модели

Аудитор обязан отдельно проверить:

1. Что все 12 обязательных сущностей ТЗ присутствуют.
2. Что не добавлены новые бизнес-сущности вне ТЗ.
3. Что runs содержит все обязательные поля.
4. Что совместимость `operation_type` / `lifecycle_status` / `business_result` контролируется.
5. Что run_detail_audit хранится в PostgreSQL, а не только во внешних файлах.
6. Что таблицы history/logs/detail audit индексированы под server-side работу.
7. Что temp files и run files разделены.
8. Что archived store не удаляется и не ломает историю.
9. Что system_logs и audit разделены по таблицам.
10. Что есть достаточные ограничения целостности для file availability и уникальностей.
11. Что `users.username` уникален.
12. Что `stores` уникальны по (`marketplace`, `name`).
13. Что `user_permissions` и `user_store_access` имеют составные уникальности.
14. Что timestamps хранятся в UTC.

---

## 23. Граница текущего документа

Настоящий документ фиксирует только модель данных и структуру БД.

Следующим документом должен идти:
- `05_ACCESS_CONTROL_MODEL.md`

В нём должны быть раскрыты:
- роли;
- permissions;
- user_store_access;
- матрица доступа;
- скрытие разделов;
- правила доступа к history/logs/download/run pages;
- правила пользователя без магазинов.