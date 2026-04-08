# 13_DETAILED_TASK_BREAKDOWN.md

## 1. Назначение документа

Документ фиксирует:
- подробные задачи по каждому этапу реализации;
- минимально достаточную декомпозицию для мультиагентной реализации;
- цель каждой задачи;
- ожидаемый результат;
- затрагиваемые модули;
- зависимости;
- критерий готовности.

Документ не меняет этапы, зафиксированные в:
- `12_IMPLEMENTATION_STAGES.md`

Документ не заменяет:
- ТЗ;
- архитектурные документы;
- acceptance criteria.

---

## 2. Правила использования задач

## 2.1. Единица исполнения

Одна задача должна быть:
- ограниченной по объёму;
- проверяемой отдельно;
- не размывать scope на несколько независимых подсистем;
- пригодной для отдельной постановки разработчику и отдельной проверки аудитором.

## 2.2. Правило зависимости

Задача может стартовать только если:
- завершены все её явные зависимости;
- завершён соответствующий этаповый базовый каркас.

## 2.3. Правило завершения

Задача считается завершённой только если:
- достигнут её результат;
- соблюдены инварианты ТЗ;
- выполнен критерий готовности;
- не нарушены соседние модули.

---

## 3. Этап 1. Foundation и bootstrap проекта

### S1-T01. Создать базовую структуру backend-проекта
**Цель:**  
Зафиксировать каркас проекта и модульное деление, пригодное для дальнейшей реализации.

**Результат:**  
Создана базовая структура каталогов/модулей приложения в соответствии с архитектурой:
- shared
- auth
- users
- access
- stores
- temp_files
- runs
- wb
- ozon
- audit
- logs
- history
- file_storage
- admin_cli
- system_maintenance

**Затрагиваемые модули:**  
- core/shared
- project root structure

**Зависимости:**  
- нет

**Критерий готовности:**  
- проект поднимается как приложение;
- модульная структура не противоречит `03_MODULES_AND_LAYERS.md`.

---

### S1-T02. Подключить конфигурацию приложения и окружения
**Цель:**  
Собрать единый конфигурационный контур приложения для VPS Ubuntu среды.

**Результат:**  
Есть централизованная конфигурация:
- DB connection
- storage paths
- timezone/display settings
- runtime settings
- logging settings

**Затрагиваемые модули:**  
- shared
- core config

**Зависимости:**  
- S1-T01

**Критерий готовности:**  
- приложение стартует с конфигурацией из окружения/конфигов;
- нет hardcoded production secrets в коде.

---

### S1-T03. Подключить PostgreSQL и migration framework
**Цель:**  
Подготовить технический контур схемы БД и управляемых миграций.

**Результат:**  
Есть:
- подключение PostgreSQL;
- рабочий migration mechanism;
- базовая цепочка миграций.

**Затрагиваемые модули:**  
- persistence/infrastructure
- shared

**Зависимости:**  
- S1-T02

**Критерий готовности:**  
- миграции применяются на чистую БД;
- схема может развиваться через контролируемые revisions.

---

### S1-T04. Реализовать базовый web application skeleton
**Цель:**  
Подготовить серверный каркас HTTP-приложения.

**Результат:**  
Есть:
- старт приложения;
- базовые route groups;
- middleware base;
- базовый error handling;
- health/start page skeleton.

**Затрагиваемые модули:**  
- presentation layer
- shared

**Зависимости:**  
- S1-T01
- S1-T02

**Критерий готовности:**  
- приложение отвечает на базовые HTTP-запросы;
- архитектурный слой presentation отделён от domain logic.

---

### S1-T05. Реализовать UTC/timezone базовые сервисы
**Цель:**  
Гарантировать единый стандарт времени для БД и UI.

**Результат:**  
Есть общий clock/time helper контур:
- UTC storage
- Europe/Helsinki display conversion

**Затрагиваемые модули:**  
- shared
- core

**Зависимости:**  
- S1-T01

**Критерий готовности:**  
- все новые datetime хранятся как UTC;
- есть единый технический механизм локального отображения.

---

### S1-T06. Реализовать базовое application logging
**Цель:**  
Подготовить технический контур логирования приложения.

**Результат:**  
Есть базовый runtime logging:
- application log sink
- severity handling
- structured logging base

**Затрагиваемые модули:**  
- logs
- shared
- infrastructure

**Зависимости:**  
- S1-T02
- S1-T04

**Критерий готовности:**  
- runtime ошибки и штатные события приложения логируются контролируемо;
- контур пригоден для последующей интеграции с `system_logs`.

---

### S1-T07. Реализовать CLI bootstrap entrypoint
**Цель:**  
Подготовить CLI-контур для инициализации системы.

**Результат:**  
Есть CLI-entrypoint для bootstrap действий.

**Затрагиваемые модули:**  
- admin_cli
- shared
- infrastructure

**Зависимости:**  
- S1-T03

**Критерий готовности:**  
- приложение допускает запуск CLI-команд инициализации.

---

### S1-T08. Реализовать seed базовых ролей и permissions
**Цель:**  
Гарантировать обязательное стартовое состояние модели доступа.

**Результат:**  
Автоматически создаются:
- admin
- manager_lead
- manager
- create_store
- edit_store

**Затрагиваемые модули:**  
- roles
- permissions
- admin_cli
- users/access

**Зависимости:**  
- S1-T07

**Критерий готовности:**  
- на чистой БД после инициализации существуют обязательные роли и permissions.

---

### S1-T09. Реализовать CLI-создание первого администратора
**Цель:**  
Выполнить обязательное требование ТЗ по созданию первого Admin.

**Результат:**  
Есть CLI-команда создания первого администратора.

**Затрагиваемые модули:**  
- admin_cli
- users
- auth

**Зависимости:**  
- S1-T08

**Критерий готовности:**  
- первый администратор может быть создан без веб-интерфейса;
- веб-сценарий создания первого admin отсутствует.

---

## 4. Этап 2. Data model и persistence layer

### S2-T01. Реализовать таблицы roles, permissions, users, user_permissions
**Цель:**  
Покрыть базовый контур идентификации и прав.

**Результат:**  
Схема и persistence доступны для:
- roles
- permissions
- users
- user_permissions

**Затрагиваемые модули:**  
- users
- auth
- access
- persistence

**Зависимости:**  
- S1-T03

**Критерий готовности:**  
- таблицы, FK, unique constraints и базовые индексы соответствуют `04_DATA_MODEL_AND_DB_SCHEMA.md`.

---

### S2-T02. Реализовать таблицы stores и user_store_access
**Цель:**  
Покрыть контур магазинов и store access.

**Результат:**  
Схема и persistence доступны для:
- stores
- user_store_access

**Затрагиваемые модули:**  
- stores
- access
- persistence

**Зависимости:**  
- S2-T01

**Критерий готовности:**  
- marketplace/status/store settings constraints соблюдены;
- составные уникальности созданы.

---

### S2-T03. Реализовать таблицу runs
**Цель:**  
Подготовить центральную сущность исполнения операций.

**Результат:**  
Таблица runs и persistence model готовы.

**Затрагиваемые модули:**  
- runs
- persistence

**Зависимости:**  
- S2-T02

**Критерий готовности:**  
- обязательные поля, индексы и ограничения runs созданы;
- lifecycle/business_result compatibility заложена в схему и/или persistence validations.

---

### S2-T04. Реализовать таблицы run_files и temporary_uploaded_files
**Цель:**  
Подготовить metadata-контур файлов.

**Результат:**  
Таблицы и persistence model готовы для:
- run_files
- temporary_uploaded_files

**Затрагиваемые модули:**  
- file_storage
- temp_files
- runs
- persistence

**Зависимости:**  
- S2-T03

**Критерий готовности:**  
- file metadata таблицы полностью соответствуют архитектурной модели;
- unique path/filename constraints созданы.

---

### S2-T05. Реализовать таблицы run_summary_audit и run_detail_audit
**Цель:**  
Подготовить persistence-контур полного run audit.

**Результат:**  
Есть таблицы и persistence model для summary/detail audit.

**Затрагиваемые модули:**  
- audit
- runs
- persistence

**Зависимости:**  
- S2-T03

**Критерий готовности:**  
- detail audit хранится в PostgreSQL;
- индексы под search/filter/sort/page заложены.

---

### S2-T06. Реализовать таблицу system_logs
**Цель:**  
Подготовить persistence-контур системных событий.

**Результат:**  
Есть таблица system_logs и persistence model.

**Затрагиваемые модули:**  
- logs
- persistence

**Зависимости:**  
- S2-T03

**Критерий готовности:**  
- обязательные поля и индексы logs соответствуют архитектуре;
- связь с users/stores/runs предусмотрена.

---

### S2-T07. Реализовать базовые repositories и read/write abstractions
**Цель:**  
Подготовить базовый persistence API для всех обязательных сущностей.

**Результат:**  
Есть репозитории/DAO/read adapters под все обязательные сущности.

**Затрагиваемые модули:**  
- all persistence-backed modules

**Зависимости:**  
- S2-T01
- S2-T02
- S2-T03
- S2-T04
- S2-T05
- S2-T06

**Критерий готовности:**  
- application layer может работать без прямых SQL в бизнес-логике.

---

## 5. Этап 3. Auth, users, access control и stores

### S3-T01. Реализовать password hashing и login/logout flow
**Цель:**  
Собрать минимальный безопасный auth flow.

**Результат:**  
Работают:
- login
- logout
- password hash verification
- blocked user denial

**Затрагиваемые модули:**  
- auth
- users
- logs

**Зависимости:**  
- S2-T07

**Критерий готовности:**  
- успешный и неуспешный входы различаются корректно;
- blocked user не получает сессию.

---

### S3-T02. Реализовать current session/user context
**Цель:**  
Сделать единый контекст авторизованного пользователя для UI и application layer.

**Результат:**  
Есть механизм получения:
- current user
- role
- permissions
- blocked state

**Затрагиваемые модули:**  
- auth
- access
- presentation

**Зависимости:**  
- S3-T01

**Критерий готовности:**  
- любой авторизованный endpoint может получить корректный user context.

---

### S3-T03. Реализовать change own password
**Цель:**  
Выполнить обязательный сценарий смены собственного пароля.

**Результат:**  
Пользователь может сменить пароль в рамках авторизованной сессии.

**Затрагиваемые модули:**  
- auth
- users

**Зависимости:**  
- S3-T02

**Критерий готовности:**  
- сценарий работает только для текущего пользователя;
- не появляется forbidden MVP функционал восстановления по email.

---

### S3-T04. Реализовать users management для admin
**Цель:**  
Собрать административный контур управления пользователями.

**Результат:**  
Admin может:
- создавать пользователей
- редактировать пользователей
- блокировать/разблокировать
- назначать роль
- назначать permissions

**Затрагиваемые модули:**  
- users
- access
- logs
- presentation

**Зависимости:**  
- S3-T02

**Критерий готовности:**  
- ни один не-admin не может выполнять user management.

---

### S3-T05. Реализовать stores CRUD и store settings
**Цель:**  
Собрать контур управления магазинами.

**Результат:**  
Работают:
- create store
- edit store
- archive store
- restore store
- update store settings

**Затрагиваемые модули:**  
- stores
- access
- logs
- presentation

**Зависимости:**  
- S2-T07
- S3-T02

**Критерий готовности:**  
- store actions соответствуют role+permission+store access правилам;
- archived store model соблюдается.

---

### S3-T06. Реализовать user_store_access management
**Цель:**  
Реализовать назначение пользователей на магазины.

**Результат:**  
Admin может управлять привязкой user <-> store.

**Затрагиваемые модули:**  
- stores
- access
- users
- logs

**Зависимости:**  
- S3-T05

**Критерий готовности:**  
- только admin может менять user_store_access;
- доступ к store-bound объектам опирается на эти записи.

---

### S3-T07. Реализовать authorization policy layer
**Цель:**  
Вынести access decisions в отдельный application/domain контур.

**Результат:**  
Есть единые policy checks для:
- page access
- action access
- store-bound access
- admin overrides
- permission checks

**Затрагиваемые модули:**  
- access
- auth
- users
- stores

**Зависимости:**  
- S3-T04
- S3-T06

**Критерий готовности:**  
- access decisions не размазаны по UI;
- прямой URL не обходит ограничения.

---

### S3-T08. Реализовать UI visibility rules и no-store scenario
**Цель:**  
Собрать обязательное поведение интерфейса по скрытию разделов и пустым состояниям.

**Результат:**  
Реализованы:
- hidden sections
- no-store dashboard state
- manager/manager_lead menu rules
- history hidden for no-store user

**Затрагиваемые модули:**  
- access
- presentation
- stores

**Зависимости:**  
- S3-T07

**Критерий готовности:**  
- недоступные разделы скрыты;
- no-store scenario соответствует `05_ACCESS_CONTROL_MODEL.md`.

---

## 6. Этап 4. Temporary files, file storage и secure download

### S4-T01. Реализовать temp file upload pipeline
**Цель:**  
Собрать сценарий загрузки временных файлов.

**Результат:**  
Пользователь может загружать temp files в контур:
- user + store + module

**Затрагиваемые модули:**  
- temp_files
- file_storage
- access
- logs

**Зависимости:**  
- S3-T07

**Критерий готовности:**  
- upload учитывает доступ к store;
- metadata temp file сохраняется.

---

### S4-T02. Реализовать active temporary set model
**Цель:**  
Собрать модель одного активного набора на user+store+module.

**Результат:**  
Система может:
- читать активный набор;
- заменять состав набора;
- обеспечивать единственность активного набора.

**Затрагиваемые модули:**  
- temp_files
- file_storage

**Зависимости:**  
- S4-T01

**Критерий готовности:**  
- для одной пары user+store+module нет нескольких активных наборов.

---

### S4-T03. Реализовать delete/replace temp file scenarios
**Цель:**  
Дать пользователю управление активным набором до запуска.

**Результат:**  
Работают:
- delete temporary file
- replace temporary file

**Затрагиваемые модули:**  
- temp_files
- file_storage
- logs
- presentation

**Зависимости:**  
- S4-T02

**Критерий готовности:**  
- после delete/replace набор корректно перестраивается;
- операции журналируются.

---

### S4-T04. Реализовать file validation and limits layer
**Цель:**  
Контролировать размер, состав и тип загружаемых файлов.

**Результат:**  
Есть проверки:
- only .xlsx
- per-file size <= 25 MB
- WB total <= 100 MB
- WB promo count 1..20
- Ozon exactly 1 file

**Затрагиваемые модули:**  
- temp_files
- wb
- ozon
- shared

**Зависимости:**  
- S4-T01

**Критерий готовности:**  
- violations дают controlled structured error;
- invalid composition не проходит к запуску.

---

### S4-T05. Реализовать stored filename/path/hash generation
**Цель:**  
Собрать безопасную физическую модель хранения файлов.

**Результат:**  
Для каждого файла система умеет:
- вычислить SHA-256
- вычислить размер
- создать unique stored filename
- создать storage_relative_path

**Затрагиваемые модули:**  
- file_storage
- temp_files
- shared

**Зависимости:**  
- S4-T01

**Критерий готовности:**  
- path/filename collisions исключены;
- metadata соответствует фактическому физическому файлу.

---

### S4-T06. Реализовать run input file copy storage
**Цель:**  
Сделать воспроизводимое хранение input files per run.

**Результат:**  
При запуске run temp files копируются в:
- `/storage/runs/{module_code}/{store_id}/{public_run_number}/input/`

**Затрагиваемые модули:**  
- file_storage
- runs
- temp_files

**Зависимости:**  
- S4-T05

**Критерий готовности:**  
- разные runs имеют независимые физические input copies;
- ссылки на tmp files не используются как исторические input files.

---

### S4-T07. Реализовать secure download use case
**Цель:**  
Обеспечить безопасное скачивание файлов без прямого публичного URL.

**Результат:**  
Скачивание доступно только через backend access-checked flow.

**Затрагиваемые модули:**  
- file_storage
- access
- runs
- history
- logs

**Зависимости:**  
- S4-T06
- S3-T07

**Критерий готовности:**  
- foreign/unavailable file download блокируется;
- direct public URL access отсутствует.

---

### S4-T08. Реализовать unavailable file presentation model
**Цель:**  
Собрать единый способ отражения недоступности файла в metadata/UI.

**Результат:**  
Есть модель:
- is_available
- unavailable_reason
- disabled download behavior
- “Файл недоступен” marker

**Затрагиваемые модули:**  
- file_storage
- history
- presentation

**Зависимости:**  
- S4-T07

**Критерий готовности:**  
- UI может корректно отобразить недоступность файла без чтения физического storage напрямую.

---

## 7. Этап 5. Runs orchestration, async execution, locking и polling

### S5-T01. Реализовать run creation use cases для check/process
**Цель:**  
Подготовить стартовые сценарии создания runs.

**Результат:**  
Есть:
- create check run
- create process run

**Затрагиваемые модули:**  
- runs
- access
- temp_files
- logs

**Зависимости:**  
- S4-T06
- S3-T07

**Критерий готовности:**  
- run создаётся с корректным operation_type/module/store/user/input signature.

---

### S5-T02. Реализовать lifecycle transition layer
**Цель:**  
Собрать централизованный контроль статусов runs.

**Результат:**  
Есть единый transition service для:
- check lifecycle
- process lifecycle

**Затрагиваемые модули:**  
- runs

**Зависимости:**  
- S5-T01

**Критерий готовности:**  
- недопустимые transitions невозможны;
- business_result не заполняется до финального состояния.

---

### S5-T03. Реализовать background execution dispatcher
**Цель:**  
Сделать асинхронную модель исполнения вместо долгого HTTP.

**Результат:**  
HTTP создаёт run и передаёт его в background execution.

**Затрагиваемые модули:**  
- runs
- infrastructure
- shared

**Зависимости:**  
- S5-T01

**Критерий готовности:**  
- API создания run укладывается в целевое время принятия;
- полная обработка не выполняется синхронно в HTTP.

---

### S5-T04. Реализовать store+module locking и active_run_conflict
**Цель:**  
Гарантировать запрет двух активных runs по одной паре.

**Результат:**  
Есть lock manager и conflict detection.

**Затрагиваемые модули:**  
- runs
- shared
- infrastructure

**Зависимости:**  
- S5-T03

**Критерий готовности:**  
- второй active run на тот же store+module не стартует;
- возвращается active_run_conflict.

---

### S5-T05. Реализовать polling status read model
**Цель:**  
Дать UI способ наблюдать состояние run.

**Результат:**  
Есть polling endpoint/query model, возвращающий:
- lifecycle_status
- business_result
- short_result_text

**Затрагиваемые модули:**  
- runs
- presentation

**Зависимости:**  
- S5-T02
- S5-T03

**Критерий готовности:**  
- polling работает до финального состояния;
- intermediate and final states читаются корректно.

---

### S5-T06. Реализовать process auto-validation framework
**Цель:**  
Собрать обязательную validating phase для process runs.

**Результат:**  
Process path поддерживает:
- created -> validating -> processing / failed

**Затрагиваемые модули:**  
- runs
- wb
- ozon

**Зависимости:**  
- S5-T02
- S5-T03

**Критерий готовности:**  
- process не может перейти в processing без validating;
- validating не создаёт отдельный run.

---

### S5-T07. Реализовать run completion/finalization base
**Цель:**  
Собрать единый механизм финализации run.

**Результат:**  
Система умеет:
- завершать run
- ставить business_result
- сохранять short_result_text
- закрывать lifecycle
- освобождать lock

**Затрагиваемые модули:**  
- runs
- logs

**Зависимости:**  
- S5-T04
- S5-T05

**Критерий готовности:**  
- completed/failed states консистентны;
- lock не остаётся висеть после завершения.

---

## 8. Этап 6. Wildberries module

### S6-T01. Реализовать WB workbook intake и required columns validation
**Цель:**  
Подготовить надёжное чтение WB входных файлов.

**Результат:**  
Система умеет:
- открыть price workbook
- открыть promo workbooks
- выбрать первый лист
- проверить required columns

**Затрагиваемые модули:**  
- wb
- file_storage

**Зависимости:**  
- S5-T06

**Критерий готовности:**  
- обязательные колонки price/promo распознаются корректно;
- invalid workbook scenarios обнаруживаются.

---

### S6-T02. Реализовать WB normalization layer
**Цель:**  
Собрать каноническую нормализацию Артикул WB и чисел.

**Результат:**  
Есть единая WB normalizer logic для:
- Артикул WB
- Текущая цена
- Плановая цена
- Загружаемая скидка

**Затрагиваемые модули:**  
- wb

**Зависимости:**  
- S6-T01

**Критерий готовности:**  
- `.0` removal, trim, numeric cleanup работают согласно ТЗ.

---

### S6-T03. Реализовать WB promo validation и aggregation
**Цель:**  
Собрать корректную агрегацию по акциям.

**Результат:**  
Есть WB promo aggregation:
- MIN discount
- MAX plan price
- only valid promo rows participate

**Затрагиваемые модули:**  
- wb

**Зависимости:**  
- S6-T02

**Критерий готовности:**  
- агрегация по нормализованному Артикулу WB корректна;
- invalid promo rows/files отражаются отдельно.

---

### S6-T04. Реализовать WB discount calculation engine
**Цель:**  
Собрать точную формулу и гибридную логику WB.

**Результат:**  
Реализованы:
- calculated_discount
- final_discount_pre_threshold
- threshold branch
- fallback_no_promo
- fallback_over_threshold
- final range checks

**Затрагиваемые модули:**  
- wb

**Зависимости:**  
- S6-T03

**Критерий готовности:**  
- float не используется в финальном расчёте;
- `ceil((1 - max_plan_price / current_price) * 100)` реализован строго.

---

### S6-T05. Реализовать WB detail audit builder
**Цель:**  
Собрать полный построчный explainability-контур WB.

**Результат:**  
WB detail audit строится с обязательными колонками и reason semantics.

**Затрагиваемые модули:**  
- wb
- audit

**Зависимости:**  
- S6-T04

**Критерий готовности:**  
- detail audit WB содержит все обязательные UI-поля;
- entity_key_1 = Артикул WB, если он есть.

---

### S6-T06. Реализовать WB summary audit и short result builder
**Цель:**  
Собрать агрегированный итог WB run.

**Результат:**  
Формируются:
- WB summary counters
- WB short_result_text

**Затрагиваемые модули:**  
- wb
- audit
- runs

**Зависимости:**  
- S6-T05

**Критерий готовности:**  
- summary покрывает весь обязательный набор показателей;
- short result согласован с summary/business_result.

---

### S6-T07. Реализовать WB check execution path
**Цель:**  
Собрать полноценный WB check.

**Результат:**  
WB check:
- валидирует набор
- считает модель результата
- формирует audits
- не пишет output file

**Затрагиваемые модули:**  
- wb
- runs
- audit

**Зависимости:**  
- S6-T06

**Критерий готовности:**  
- check не меняет workbook;
- корректно завершается как check_passed/check_passed_with_warnings/check_failed.

---

### S6-T08. Реализовать WB safe write и process execution path
**Цель:**  
Собрать полноценный WB process.

**Результат:**  
WB process:
- проходит validating
- проверяет safe write
- меняет только `Новая скидка`
- сохраняет output workbook

**Затрагиваемые модули:**  
- wb
- runs
- file_storage
- audit

**Зависимости:**  
- S6-T07

**Критерий готовности:**  
- output workbook пригоден для дальнейшего использования;
- only `Новая скидка` changes;
- unsafe write blocks process correctly.

---

## 9. Этап 7. Ozon module

### S7-T01. Реализовать Ozon workbook intake и required sheet/column validation
**Цель:**  
Подготовить корректное чтение Ozon workbook.

**Результат:**  
Система умеет:
- открыть workbook
- найти лист `Товары и цены`
- проверить J/K/L/O/P/R по буквенным позициям

**Затрагиваемые модули:**  
- ozon
- file_storage

**Зависимости:**  
- S5-T06

**Критерий готовности:**  
- column-by-letter validation работает строго по ТЗ.

---

### S7-T02. Реализовать Ozon normalization layer
**Цель:**  
Собрать каноническую нормализацию J/O/P/R.

**Результат:**  
Есть единая Ozon normalizer logic:
- `*` -> missing
- empty -> missing
- None -> missing
- invalid numeric -> missing

**Затрагиваемые модули:**  
- ozon

**Зависимости:**  
- S7-T01

**Критерий готовности:**  
- нормализация работает одинаково для check и process.

---

### S7-T03. Реализовать Ozon row decision engine
**Цель:**  
Собрать обязательную последовательность правил Ozon.

**Результат:**  
Реализованы rules:
- missing_min_price
- no_stock
- no_boost_prices
- use_max_boost_price
- use_min_price
- below_min_price_threshold
- insufficient_ozon_input_data

**Затрагиваемые модули:**  
- ozon

**Зависимости:**  
- S7-T02

**Критерий готовности:**  
- порядок правил соответствует ТЗ и не изменён.

---

### S7-T04. Реализовать Ozon detail audit builder
**Цель:**  
Собрать полный построчный explainability-контур Ozon.

**Результат:**  
Ozon detail audit формируется с обязательными UI-полями.

**Затрагиваемые модули:**  
- ozon
- audit

**Зависимости:**  
- S7-T03

**Критерий готовности:**  
- detail audit Ozon содержит обязательные колонки;
- entity_key_1 заполняется по правилу OzonID/SKU/Артикул.

---

### S7-T05. Реализовать Ozon summary audit и short result builder
**Цель:**  
Собрать агрегированный итог Ozon run.

**Результат:**  
Формируются:
- Ozon summary counters
- Ozon short_result_text

**Затрагиваемые модули:**  
- ozon
- audit
- runs

**Зависимости:**  
- S7-T04

**Критерий готовности:**  
- summary покрывает весь обязательный набор Ozon показателей;
- short result согласован с summary/business_result.

---

### S7-T06. Реализовать Ozon check execution path
**Цель:**  
Собрать полноценный Ozon check.

**Результат:**  
Ozon check:
- валидирует workbook
- моделирует K/L result
- формирует audits
- не пишет output file

**Затрагиваемые модули:**  
- ozon
- runs
- audit

**Зависимости:**  
- S7-T05

**Критерий готовности:**  
- check не меняет workbook;
- корректно завершается как check_passed/check_passed_with_warnings/check_failed.

---

### S7-T07. Реализовать Ozon K/L writer и process execution path
**Цель:**  
Собрать полноценный Ozon process.

**Результат:**  
Ozon process:
- проходит validating
- пишет только K/L
- сохраняет workbook пригодным для обратной загрузки

**Затрагиваемые модули:**  
- ozon
- runs
- file_storage
- audit

**Зависимости:**  
- S7-T06

**Критерий готовности:**  
- только K и L изменяются;
- workbook structure не ломается;
- forced recalc не используется.

---

## 10. Этап 8. Audit, history и logs read-side

### S8-T01. Реализовать audit persistence write path
**Цель:**  
Собрать единый механизм записи summary/detail audit.

**Результат:**  
WB и Ozon execution paths сохраняют:
- run_summary_audit
- run_detail_audit

**Затрагиваемые модули:**  
- audit
- wb
- ozon
- runs

**Зависимости:**  
- S6-T08
- S7-T07

**Критерий готовности:**  
- и check, и process записывают audit консистентно.

---

### S8-T02. Реализовать detail audit read-side с server-side controls
**Цель:**  
Собрать страницу detail audit без client-side полной загрузки.

**Результат:**  
Есть detail audit query layer с:
- search
- filters
- sort
- pagination

**Затрагиваемые модули:**  
- audit
- presentation

**Зависимости:**  
- S8-T01

**Критерий готовности:**  
- detail audit до 200k строк обслуживается серверно;
- required filters/search/sort поддерживаются.

---

### S8-T03. Реализовать system_logs write path
**Цель:**  
Собрать единый механизм записи обязательных системных событий.

**Результат:**  
Пишутся:
- auth events
- store/user events
- file events
- run start/finish/error events
- purge/retention/superseded events

**Затрагиваемые модули:**  
- logs
- auth
- users
- stores
- file_storage
- runs
- system_maintenance

**Зависимости:**  
- S3-T04
- S4-T03
- S5-T07
- S6-T08
- S7-T07

**Критерий готовности:**  
- обязательный набор event_type покрыт.

---

### S8-T04. Реализовать logs read-side с server-side controls
**Цель:**  
Собрать полнофункциональный logs page backend.

**Результат:**  
Есть logs query layer с:
- search
- filters
- sort
- pagination

**Затрагиваемые модули:**  
- logs
- presentation
- access

**Зависимости:**  
- S8-T03

**Критерий готовности:**  
- logs page может работать только на server-side;
- non-admin access denied.

---

### S8-T05. Реализовать history read-side
**Цель:**  
Собрать единый источник списка запусков.

**Результат:**  
Есть history query layer с:
- search
- filters
- sort
- pagination
- joins to store/user/file metadata

**Затрагиваемые модули:**  
- history
- runs
- file_storage
- access
- presentation

**Зависимости:**  
- S8-T01
- S8-T03

**Критерий готовности:**  
- history строится из runs, а не из logs;
- access scoping выполняется на сервере.

---

### S8-T06. Реализовать run page read model
**Цель:**  
Собрать единый источник данных для страницы run/detail audit.

**Результат:**  
Есть run page query model, объединяющая:
- run metadata
- summary audit
- detail audit query
- run files metadata

**Затрагиваемые модули:**  
- runs
- audit
- file_storage
- presentation

**Зависимости:**  
- S8-T02
- S8-T05

**Критерий готовности:**  
- run page может быть построена без перечитывания workbook и без использования logs как primary source.

---

## 11. Этап 9. UI pages and end-to-end user flows

### S9-T01. Реализовать login/logout/change password pages
**Цель:**  
Собрать UI auth contour.

**Результат:**  
Есть страницы и сценарии:
- login
- logout
- change own password

**Затрагиваемые модули:**  
- auth
- presentation

**Зависимости:**  
- S3-T03

**Критерий готовности:**  
- auth UX соответствует MVP и не содержит forbidden recovery flows.

---

### S9-T02. Реализовать dashboard и menu visibility
**Цель:**  
Собрать стартовый экран и роль-зависимую навигацию.

**Результат:**  
Работают:
- dashboard
- hidden sections
- no-store empty state
- role-based menu

**Затрагиваемые модули:**  
- presentation
- access
- stores

**Зависимости:**  
- S3-T08

**Критерий готовности:**  
- навигация соответствует `09_UI_PAGES_AND_ROUTES.md`.

---

### S9-T03. Реализовать users page
**Цель:**  
Собрать административный UI для user management.

**Результат:**  
Admin может через UI:
- видеть список пользователей
- создавать/редактировать
- блокировать/разблокировать
- назначать role/permissions

**Затрагиваемые модули:**  
- users
- presentation
- access

**Зависимости:**  
- S3-T04
- S9-T02

**Критерий готовности:**  
- users page недоступна не-admin.

---

### S9-T04. Реализовать stores page
**Цель:**  
Собрать UI управления магазинами.

**Результат:**  
Через UI работают:
- store list
- create/edit
- archive/restore
- assign users
- edit settings

**Затрагиваемые модули:**  
- stores
- access
- presentation

**Зависимости:**  
- S3-T06
- S9-T02

**Критерий готовности:**  
- manager/manager_lead restrictions соблюдены;
- archived store behavior корректен.

---

### S9-T05. Реализовать Wildberries processing page
**Цель:**  
Собрать полный пользовательский сценарий WB.

**Результат:**  
На странице доступны:
- store selection
- temp file upload/delete/replace
- check/process actions
- polling status
- summary preview
- detail preview
- link to run page
- result download

**Затрагиваемые модули:**  
- wb
- runs
- temp_files
- file_storage
- presentation

**Зависимости:**  
- S6-T08
- S8-T06

**Критерий готовности:**  
- WB flow полностью работает через UI end-to-end.

---

### S9-T06. Реализовать Ozon processing page
**Цель:**  
Собрать полный пользовательский сценарий Ozon.

**Результат:**  
На странице доступны:
- store selection
- temp file upload/delete/replace
- check/process actions
- polling status
- summary preview
- detail preview
- link to run page
- result download

**Затрагиваемые модули:**  
- ozon
- runs
- temp_files
- file_storage
- presentation

**Зависимости:**  
- S7-T07
- S8-T06

**Критерий готовности:**  
- Ozon flow полностью работает через UI end-to-end.

---

### S9-T07. Реализовать history page
**Цель:**  
Собрать UI для server-side history.

**Результат:**  
Есть history UI с:
- search
- filters
- sort
- pagination
- переходом на run page

**Затрагиваемые модули:**  
- history
- presentation
- access

**Зависимости:**  
- S8-T05

**Критерий готовности:**  
- default page size и default sort соблюдены;
- no-store user history не видит.

---

### S9-T08. Реализовать logs page
**Цель:**  
Собрать UI для system logs.

**Результат:**  
Есть logs UI с:
- search
- filters
- sort
- pagination

**Затрагиваемые модули:**  
- logs
- presentation
- access

**Зависимости:**  
- S8-T04

**Критерий готовности:**  
- только admin имеет доступ;
- logs page не читает detail audit вместо system logs.

---

### S9-T09. Реализовать run/detail audit page
**Цель:**  
Собрать единый экран карточки запуска и полной страницы аудита.

**Результат:**  
На одном экране доступны:
- run metadata
- files block
- summary audit
- full detail audit table
- module-specific columns
- download actions

**Затрагиваемые модули:**  
- runs
- audit
- file_storage
- presentation

**Зависимости:**  
- S8-T06

**Критерий готовности:**  
- run page и full detail audit page не раздвоены;
- unavailable file behavior отображается корректно.

---

## 12. Этап 10. Maintenance, retention, timeout reconciliation и operational hardening

### S10-T01. Реализовать temporary files auto purge
**Цель:**  
Выполнить обязательное правило очистки temp files через 24 часа.

**Результат:**  
Есть purge job для:
- expired temp files
- metadata cleanup temp contour

**Затрагиваемые модули:**  
- system_maintenance
- temp_files
- file_storage
- logs

**Зависимости:**  
- S4-T03

**Критерий готовности:**  
- temp files очищаются автоматически;
- событие журналируется.

---

### S10-T02. Реализовать run files retention execution
**Цель:**  
Собрать контур обработки истечения срока доступности run files.

**Результат:**  
Есть retention job для:
- expired run files
- metadata availability update
- physical deletion by rule

**Затрагиваемые модули:**  
- system_maintenance
- file_storage
- logs

**Зависимости:**  
- S4-T08
- S8-T03

**Критерий готовности:**  
- file availability and UI marker согласованы;
- history records не удаляются.

---

### S10-T03. Реализовать superseded result handling
**Цель:**  
Выполнить правило недоступности старого успешного результата после нового successful process.

**Результат:**  
Новый successful process:
- помечает старый output as superseded
- сохраняет historical run
- пишет system log

**Затрагиваемые модули:**  
- runs
- file_storage
- logs

**Зависимости:**  
- S5-T07
- S6-T08
- S7-T07

**Критерий готовности:**  
- superseded logic работает для WB и Ozon одинаково на уровне run/file model.

---

### S10-T04. Реализовать timeout reconciliation
**Цель:**  
Не допустить зависания активных runs в вечных промежуточных статусах.

**Результат:**  
Есть механизм завершения run по hard-timeout:
- check -> check_failed
- process -> failed

**Затрагиваемые модули:**  
- system_maintenance
- runs
- logs

**Зависимости:**  
- S5-T07

**Критерий готовности:**  
- timed-out runs получают финальный статус;
- locks освобождаются.

---

### S10-T05. Реализовать consistency checks по file availability и anomalies
**Цель:**  
Собрать контроль несогласованных технических состояний.

**Результат:**  
Есть system error/anomaly handling для:
- missing physical file with available metadata
- competing successful result anomaly
- broken file/link state

**Затрагиваемые модули:**  
- system_maintenance
- file_storage
- runs
- logs

**Зависимости:**  
- S10-T02
- S10-T03

**Критерий готовности:**  
- anomalies не остаются без system log и контролируемого поведения.

---

### S10-T06. Реализовать deployment/runtime hardening
**Цель:**  
Подготовить приложение к эксплуатации на Ubuntu VPS.

**Результат:**  
Настроены:
- systemd service behavior
- nginx integration expectations
- storage path permissions
- runtime configuration safety
- log rotation integration hooks

**Затрагиваемые модули:**  
- deployment/runtime
- logs
- shared

**Зависимости:**  
- S10-T05

**Критерий готовности:**  
- приложение готово к развёртыванию без Docker в целевой среде ТЗ.

---

## 13. Этап 11. Full testing, smoke, acceptance stabilization и release readiness

### S11-T01. Реализовать unit tests для access/auth/users/stores
**Цель:**  
Проверить критический административный контур.

**Результат:**  
Есть unit/functional coverage для:
- auth
- role/permission/store access
- users
- stores

**Затрагиваемые модули:**  
- auth
- users
- access
- stores
- tests

**Зависимости:**  
- S9-T04

**Критерий готовности:**  
- ключевые role/access сценарии автоматизированно проверяются.

---

### S11-T02. Реализовать WB test contour
**Цель:**  
Проверить WB-контур на формулу, workbook safety и outcomes.

**Результат:**  
Есть тесты для:
- normalization
- aggregation
- formula
- fallback logic
- unsafe write
- check/process outcomes

**Затрагиваемые модули:**  
- wb
- tests

**Зависимости:**  
- S6-T08

**Критерий готовности:**  
- критические WB business rules покрыты.

---

### S11-T03. Реализовать Ozon test contour
**Цель:**  
Проверить Ozon-контур на column-by-letter, rule order и workbook safety.

**Результат:**  
Есть тесты для:
- required sheet/columns
- normalization
- decision logic
- K/L only write
- process/check outcomes

**Затрагиваемые модули:**  
- ozon
- tests

**Зависимости:**  
- S7-T07

**Критерий готовности:**  
- критические Ozon business rules покрыты.

---

### S11-T04. Реализовать run lifecycle and async tests
**Цель:**  
Проверить execution contour.

**Результат:**  
Есть тесты для:
- lifecycle transitions
- active_run_conflict
- polling
- auto-validation
- timeout behavior
- finalization

**Затрагиваемые модули:**  
- runs
- system_maintenance
- tests

**Зависимости:**  
- S10-T04

**Критерий готовности:**  
- execution model соответствует `06_RUNS_LIFECYCLE_AND_ASYNC_EXECUTION.md`.

---

### S11-T05. Реализовать file lifecycle and retention tests
**Цель:**  
Проверить файловый контур.

**Результат:**  
Есть тесты для:
- temp uploads
- active set
- input copies
- output files
- unavailable markers
- superseded
- retention/purge

**Затрагиваемые модули:**  
- temp_files
- file_storage
- system_maintenance
- tests

**Зависимости:**  
- S10-T03

**Критерий готовности:**  
- файловые правила соответствуют `07_FILE_STORAGE_AND_RETENTION.md`.

---

### S11-T06. Реализовать history/logs/detail audit read-side tests
**Цель:**  
Проверить server-side наблюдаемость и explainability.

**Результат:**  
Есть тесты для:
- history search/filter/sort/page
- logs search/filter/sort/page
- detail audit search/filter/sort/page
- access scoping
- no client-side full load assumptions

**Затрагиваемые модули:**  
- history
- logs
- audit
- tests

**Зависимости:**  
- S9-T09

**Критерий готовности:**  
- read-side правила работают и не обходят access model.

---

### S11-T07. Реализовать end-to-end smoke suite
**Цель:**  
Проверить ключевые пользовательские сценарии MVP целиком.

**Результат:**  
Есть smoke checks для:
- login
- user/store admin actions
- WB check/process
- Ozon check/process
- history
- logs
- run page
- file download/unavailable behavior

**Затрагиваемые модули:**  
- all major modules
- tests

**Зависимости:**  
- S11-T01
- S11-T02
- S11-T03
- S11-T04
- S11-T05
- S11-T06

**Критерий готовности:**  
- ключевые e2e пользовательские сценарии проходят на целевой сборке.

---

### S11-T08. Провести acceptance stabilization against TЗ
**Цель:**  
Финально сверить систему с ТЗ и устранить блокирующие отклонения.

**Результат:**  
Есть завершённый acceptance pass:
- критические дефекты устранены
- scope не расширен
- MVP готов к выпуску

**Затрагиваемые модули:**  
- all modules
- QA/audit/review

**Зависимости:**  
- S11-T07

**Критерий готовности:**  
- система соответствует acceptance criteria ТЗ;
- нет открытых критических отклонений от нормативной логики.

---

## 14. Критические межмодульные зависимости

Ниже фиксируются зависимости, которые оркестратор обязан учитывать при постановке задач:

1. `runs` зависит от готовности `temp_files`, `file_storage`, `access`
2. `wb` и `ozon` зависят от готовности `runs`
3. `history` зависит от готовности `runs`, `file_storage`, `access`
4. `logs` write path зависит почти от всех прикладных модулей
5. `run page` зависит от `runs + audit + file_storage`
6. `maintenance` зависит от `runs + file_storage + logs`
7. `UI processing pages` зависят от готовности соответствующих processing modules и run read-side

---

## 15. Что должен делать оркестратор с этим документом

Оркестратор обязан:
- брать задачи по одной или малыми связанными пакетами;
- не объединять несвязанные задачи ради “ускорения”;
- следить, чтобы разработчик не выходил за объём конкретной задачи;
- выдавать аудитору задачу проверки именно против критерия готовности;
- выдавать тестировщику задачу построения проверок против критерия готовности.

---

## 16. Что должен проверить аудитор по декомпозиции

Аудитор обязан проверить:

1. Что задачи реально покрывают все этапы.
2. Что ни одна задача не расширяет scope MVP.
3. Что задачи достаточно атомарны для независимой проверки.
4. Что WB и Ozon декомпозированы отдельно.
5. Что execution contour выделен отдельно от marketplace logic.
6. Что UI не поставлен раньше нужных backend dependencies.
7. Что maintenance и acceptance не пропущены.
8. Что критерии готовности у задач конкретны и проверяемы.

---

## 17. Граница текущего документа

Данный документ фиксирует:
- полную задачную декомпозицию по этапам.

Следующий документ должен раскрыть:
- критические риски;
- ограничения;
- точки, где особенно важно не нарушить ТЗ;
- контрольные запреты и уязвимые места проекта.

Имя следующего файла:
- `14_RISKS_LIMITS_AND_CONTROL_POINTS.md`