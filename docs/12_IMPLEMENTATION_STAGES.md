# 12_IMPLEMENTATION_STAGES.md

## 1. Назначение документа

Документ фиксирует:
- этапы реализации проекта;
- правильную очередность выполнения этапов;
- границы каждого этапа;
- зависимости между этапами;
- ожидаемый результат этапа;
- обязательные контрольные точки между этапами.

Документ не расписывает детальные атомарные задачи по файлам и модулям.
Подробная декомпозиция выполняется в отдельном документе:
- `13_DETAILED_TASK_BREAKDOWN.md`

---

## 2. Краткий итог

Реализация проекта должна идти поэтапно, от инфраструктурного и архитектурного каркаса к прикладной логике, затем к интерфейсу, далее к контролю качества и выпускной стабилизации.

Рекомендуемая обязательная последовательность этапов:

1. Foundation и bootstrap проекта  
2. Data model и persistence layer  
3. Auth, users, access control и stores  
4. Temporary files, file storage и secure download  
5. Runs orchestration, async execution, locking и polling  
6. WB module  
7. Ozon module  
8. Audit, history и logs read-side  
9. UI pages and end-to-end user flows  
10. Maintenance, retention, timeout reconciliation и operational hardening  
11. Full testing, smoke, acceptance stabilization и release readiness  

Такой порядок нужен, потому что:
- WB/Ozon нельзя корректно реализовывать до готовности run model и file model;
- UI нельзя полноценно доводить до готовности до появления audit/history/logs read-side;
- acceptance stabilization нельзя делать до сборки всей цепочки.

---

## 3. Общие правила этапности

## 3.1. Принцип зависимости снизу вверх

Каждый следующий этап должен опираться на завершённый предыдущий.

Нельзя качественно завершить:
- UI раньше run orchestration;
- run orchestration раньше data model;
- WB/Ozon раньше file storage и async execution;
- acceptance stabilization раньше полной сборки цепочки.

## 3.2. Принцип нерасширения scope

Ни один этап не должен расширять MVP.
Этапы служат только для последовательной реализации того, что уже зафиксировано в ТЗ и архитектурных документах.

## 3.3. Принцип “сначала скелет, потом логика, потом UX, потом стабилизация”

Реализация должна идти в следующем порядке:
1. скелет проекта;
2. хранилище и базовые сущности;
3. контроль доступа;
4. файловый контур;
5. execution contour;
6. marketplace business logic;
7. read-side and UI;
8. operational hardening;
9. тесты и приёмка.

## 3.4. Принцип этапной проверяемости

После каждого этапа должно быть возможно ответить на вопрос:
- что теперь уже работает;
- что ещё не реализовано;
- что нельзя начинать раньше;
- какой следующий этап теперь разрешён.

---

## 4. Этап 1. Foundation и bootstrap проекта

## 4.1. Цель этапа

Создать технический каркас проекта, на который будут опираться все последующие модули.

## 4.2. Что входит в этап

- базовая структура проекта;
- конфигурация приложения;
- базовая server runtime структура;
- подключение PostgreSQL;
- базовый migration mechanism;
- базовый web application skeleton;
- системные настройки времени/UTC/Europe-Helsinki display support;
- базовое логирование приложения;
- CLI bootstrap entrypoint;
- инициализация базовых ролей и permissions;
- создание первого администратора через CLI.

## 4.3. Что не входит в этап

Не входит:
- полная бизнес-логика WB/Ozon;
- полноценный UI;
- history/logs/detail audit pages;
- full async processing logic.

## 4.4. Результат этапа

По завершении этапа должен существовать:
- запускаемый backend skeleton;
- подключённая БД;
- применяемые миграции;
- CLI-инициализация системы;
- стартовые роли и permissions;
- возможность создать первого администратора.

## 4.5. Почему этап обязателен первым

Без этого этапа нельзя:
- начать согласованную работу с БД;
- внедрить access control;
- внедрить migrations;
- строить дальнейшие прикладные модули без технического хаоса.

---

## 5. Этап 2. Data model и persistence layer

## 5.1. Цель этапа

Реализовать все обязательные сущности БД и базовый persistence contour.

## 5.2. Что входит в этап

- все обязательные таблицы:
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
- FK, unique constraints, checks, indexes;
- репозитории/ORM mappings;
- UTC storage policy;
- базовые query/read/write abstractions.

## 5.3. Что не входит в этап

Не входит:
- полная бизнес-логика access;
- run execution logic;
- file storage implementation;
- UI pages;
- marketplace logic.

## 5.4. Результат этапа

По завершении этапа:
- схема БД должна быть полностью отражена в migrations;
- все обязательные сущности доступны через persistence layer;
- индексация под history/logs/detail audit предусмотрена;
- база готова к прикладной логике.

## 5.5. Зависимости

Зависит от:
- Этапа 1

Является базой для:
- Этапов 3–10

---

## 6. Этап 3. Auth, users, access control и stores

## 6.1. Цель этапа

Собрать полный контур авторизации, пользователей, ролей, permissions, store access и управления магазинами.

## 6.2. Что входит в этап

- login/logout;
- blocked user handling;
- change own password;
- users management для admin;
- role assignment;
- permission assignment;
- stores CRUD по правилам ТЗ;
- archive/restore stores;
- assignment users to stores;
- access policy enforcement;
- скрытие недоступных разделов;
- no-store user scenario;
- store settings editing for WB по правилам доступа.

## 6.3. Что не входит в этап

Не входит:
- file upload logic;
- run execution;
- WB/Ozon processing;
- history/logs pages in полном виде.

## 6.4. Результат этапа

По завершении этапа:
- можно авторизоваться;
- можно управлять пользователями согласно роли admin;
- можно управлять магазинами согласно роли/permissions;
- корректно работает role + permission + store access model;
- корректно работают visibility rules.

## 6.5. Зависимости

Зависит от:
- Этапа 2

Является обязательной базой для:
- запуска обработок;
- secure file access;
- history/logs scoping;
- UI navigation.

---

## 7. Этап 4. Temporary files, file storage и secure download

## 7.1. Цель этапа

Реализовать файловый контур системы:
- temporary uploads;
- run file storage;
- secure download;
- file availability model.

## 7.2. Что входит в этап

- temp uploads storage;
- active temporary set model;
- upload/delete/replace temp files;
- file size/count checks;
- SHA-256 calculation;
- stored filename/path generation;
- run input copy storage;
- result output storage contract;
- file metadata persistence;
- secure download use case;
- unavailable file behavior.

## 7.3. Что не входит в этап

Не входит:
- полная orchestration логика run;
- WB/Ozon business logic;
- full retention/reconciliation hardening beyond minimum foundations.

## 7.4. Результат этапа

По завершении этапа:
- пользователь может формировать active temp set;
- система умеет безопасно хранить tmp/input/output files;
- file metadata сохраняется корректно;
- прямой публичный доступ к файлам отсутствует;
- secure download model готова.

## 7.5. Зависимости

Зависит от:
- Этапа 3

Является базой для:
- Этапа 5
- Этапов 6–7
- Этапа 9

---

## 8. Этап 5. Runs orchestration, async execution, locking и polling

## 8.1. Цель этапа

Реализовать центральный execution contour:
- run creation;
- lifecycle transitions;
- background execution;
- store+module locking;
- polling;
- finalization.

## 8.2. Что входит в этап

- start check use case;
- start process use case;
- run creation;
- lifecycle status transitions;
- business_result finalization;
- process auto-validation framework;
- lock manager;
- active_run_conflict handling;
- background executor;
- polling status endpoint/query;
- timeout handling skeleton;
- run page basic metadata retrieval.

## 8.3. Что не входит в этап

Не входит:
- конкретная WB/Ozon processing logic;
- full audit content builders;
- full history/logs UI.

## 8.4. Результат этапа

По завершении этапа:
- система умеет создавать runs;
- run выполняется асинхронно;
- polling работает;
- блокировки по store+module соблюдаются;
- check/process lifecycle paths реализованы;
- execution framework готов принять marketplace engines.

## 8.5. Зависимости

Зависит от:
- Этапа 4

Является базой для:
- Этапов 6 и 7
- Этапов 8 и 9
- Этапа 10

---

## 9. Этап 6. Wildberries module

## 9.1. Цель этапа

Реализовать полный WB processing contour в соответствии с ТЗ.

## 9.2. Что входит в этап

- workbook intake WB;
- required columns validation;
- normalization rules;
- promo files validation;
- promo aggregation;
- exact decimal calculation;
- threshold/fallback logic;
- WB check flow;
- WB process flow;
- safe write to `Новая скидка`;
- WB summary audit builder;
- WB detail audit builder;
- WB short result builder.

## 9.3. Что не входит в этап

Не входит:
- Ozon logic;
- full logs/history UI;
- full retention hardening;
- общесистемная release stabilization.

## 9.4. Результат этапа

По завершении этапа:
- WB check работает;
- WB process работает;
- output workbook корректно сохраняется;
- только `Новая скидка` изменяется;
- WB summary/detail audit формируются;
- short result согласован с outcome.

## 9.5. Зависимости

Зависит от:
- Этапа 5

Может выполняться параллельно с:
- Этапом 7, если общий run framework стабилен

---

## 10. Этап 7. Ozon module

## 10.1. Цель этапа

Реализовать полный Ozon processing contour в соответствии с ТЗ.

## 10.2. Что входит в этап

- workbook intake Ozon;
- required sheet validation;
- required columns-by-letter validation;
- row normalization;
- row decision engine;
- K/L only writer;
- Ozon check flow;
- Ozon process flow;
- workbook safe save;
- Ozon summary audit builder;
- Ozon detail audit builder;
- Ozon short result builder.

## 10.3. Что не входит в этап

Не входит:
- WB logic;
- full logs/history UI;
- operational hardening outside Ozon contour.

## 10.4. Результат этапа

По завершении этапа:
- Ozon check работает;
- Ozon process работает;
- меняются только K и L;
- workbook остаётся пригодным для загрузки;
- Ozon summary/detail audit формируются;
- short result согласован с outcome.

## 10.5. Зависимости

Зависит от:
- Этапа 5

Может выполняться параллельно с:
- Этапом 6, если общий run framework стабилен

---

## 11. Этап 8. Audit, history и logs read-side

## 11.1. Цель этапа

Реализовать server-side контуры чтения для:
- run summary/detail;
- history;
- logs.

## 11.2. Что входит в этап

- save/read summary audit;
- save/read detail audit;
- detail audit search/filter/sort/page;
- history search/filter/sort/page;
- logs search/filter/sort/page;
- read models for run page;
- read models for history;
- read models for logs;
- module-specific detail audit column rendering model.

## 11.3. Что не входит в этап

Не входит:
- полный UI polishing;
- operational retention jobs;
- release hardening.

## 11.4. Результат этапа

По завершении этапа:
- history работает серверно;
- logs работают серверно;
- detail audit работает серверно;
- run page может быть собрана на полноценном read-side;
- explainability and observability contour завершён.

## 11.5. Зависимости

Зависит от:
- Этапов 6 и 7
- частично от Этапа 5

Является базой для:
- Этапа 9
- Этапа 11

---

## 12. Этап 9. UI pages and end-to-end user flows

## 12.1. Цель этапа

Собрать все обязательные страницы и пользовательские сценарии в законченный веб-интерфейс MVP.

## 12.2. Что входит в этап

- login page;
- dashboard;
- users page;
- stores page;
- WB processing page;
- Ozon processing page;
- run history page;
- logs page;
- run/detail page;
- menu/navigation visibility rules;
- empty states;
- polling behavior in UI;
- file availability indicators;
- end-to-end screen composition.

## 12.3. Что не входит в этап

Не входит:
- release hardening;
- final operational stabilization;
- full regression polishing beyond MVP needs.

## 12.4. Результат этапа

По завершении этапа:
- все обязательные страницы ТЗ существуют;
- доступы и скрытие разделов соблюдаются;
- processing flows доступны через UI;
- history/logs/run page доступны через UI;
- no-store and unavailable-file scenarios корректно отображаются.

## 12.5. Зависимости

Зависит от:
- Этапов 3–8

---

## 13. Этап 10. Maintenance, retention, timeout reconciliation и operational hardening

## 13.1. Цель этапа

Довести систему до эксплуатационно устойчивого состояния внутри границ MVP.

## 13.2. Что входит в этап

- temporary files auto purge;
- run files retention jobs;
- superseded result handling finalization;
- timeout reconciliation;
- consistency checks for file availability;
- system error logging for anomalies;
- log rotation integration;
- backup integration hooks;
- systemd/nginx deployment hardening;
- production-safe operational settings.

## 13.3. Что не входит в этап

Не входит:
- новые пользовательские функции;
- внешние интеграции;
- аналитика;
- уведомления;
- API маркетплейсов.

## 13.4. Результат этапа

По завершении этапа:
- временные файлы автоматически очищаются;
- retention rules соблюдаются;
- timeouts корректно завершают run;
- superseded outputs корректно переводятся в unavailable;
- deployment контур доведён до безопасной эксплуатации.

## 13.5. Зависимости

Зависит от:
- Этапов 4–9

---

## 14. Этап 11. Full testing, smoke, acceptance stabilization и release readiness

## 14.1. Цель этапа

Проверить, что система в целом соответствует ТЗ и готова к приёмке.

## 14.2. Что входит в этап

- unit tests для ключевых модулей;
- integration tests;
- role/access tests;
- WB tests;
- Ozon tests;
- file lifecycle tests;
- run lifecycle tests;
- history/logs/detail audit tests;
- smoke checks по ключевым пользовательским сценариям;
- acceptance verification against TЗ;
- correction of defects blocking MVP readiness.

## 14.3. Что не входит в этап

Не входит:
- разработка новых функций;
- расширение scope;
- изменение бизнес-логики.

## 14.4. Результат этапа

По завершении этапа:
- подтверждено соответствие ТЗ;
- ключевые сценарии работают end-to-end;
- критические дефекты устранены;
- система готова к выпуску как MVP.

## 14.5. Зависимости

Зависит от:
- Этапов 1–10

---

## 15. Зависимости между этапами

Ниже фиксируется каноническая цепочка зависимостей:

### Этап 1 -> Этап 2
Сначала foundation, затем полная модель данных.

### Этап 2 -> Этап 3
Auth/access/stores невозможны без готовой схемы БД.

### Этап 3 -> Этап 4
Файловый контур должен строиться уже в контексте реальной модели доступа.

### Этап 4 -> Этап 5
Run orchestration должен работать поверх реального файлового контура.

### Этап 5 -> Этапы 6 и 7
Marketplace modules должны встраиваться в готовую execution framework.

### Этапы 6 и 7 -> Этап 8
History/logs/detail audit read-side должны строиться на уже существующем run/audit output.

### Этап 8 -> Этап 9
UI должен опираться на готовые read-side сценарии.

### Этап 9 -> Этап 10
Operational hardening доводится на уже собранной системе.

### Этап 10 -> Этап 11
Acceptance stabilization возможна только на эксплуатационно доведённой сборке.

---

## 16. Допустимая параллельность этапов

## 16.1. Что можно выполнять параллельно

После завершения Этапа 5 допускается параллельное выполнение:
- Этапа 6 (WB)
- Этапа 7 (Ozon)

После достаточной готовности read-side допускается частичный параллелизм:
- финализация Этапа 8
- отдельные части Этапа 9

## 16.2. Что нельзя выполнять параллельно

Нельзя безопасно выполнять параллельно:
- Этап 2 до завершения Этапа 1
- Этап 5 до готовности Этапа 4
- Этап 9 до появления реального history/logs/run read-side
- Этап 11 до завершения operational hardening

---

## 17. Контрольные точки между этапами

## 17.1. После Этапа 1

Должно быть подтверждено:
- проект поднимается;
- БД подключается;
- migrations запускаются;
- CLI bootstrap работает.

## 17.2. После Этапа 2

Должно быть подтверждено:
- все обязательные сущности существуют;
- constraints и indexes применены;
- persistence layer готов.

## 17.3. После Этапа 3

Должно быть подтверждено:
- login/access/store model работает;
- hidden sections соблюдаются;
- no-store scenario работает.

## 17.4. После Этапа 4

Должно быть подтверждено:
- active temp set работает;
- file metadata сохраняется;
- secure download model реализована.

## 17.5. После Этапа 5

Должно быть подтверждено:
- runs создаются;
- polling работает;
- locking работает;
- active_run_conflict реализован.

## 17.6. После Этапов 6 и 7

Должно быть подтверждено:
- WB и Ozon independently work in check/process paths;
- audit и short result формируются;
- workbook safety соблюдается.

## 17.7. После Этапа 8

Должно быть подтверждено:
- history/logs/detail audit работают серверно.

## 17.8. После Этапа 9

Должно быть подтверждено:
- полный UI MVP доступен пользователю.

## 17.9. После Этапа 10

Должно быть подтверждено:
- retention, purge, timeout and anomaly handling operationally stable.

## 17.10. После Этапа 11

Должно быть подтверждено:
- система соответствует ТЗ и готова к приёмке.

---

## 18. Критические ошибки этапности

Ниже перечислены ошибки в sequencing, которых нельзя допускать:

1. Начинать UI как основной фронт работ до готовности execution/read-side.
2. Реализовывать WB/Ozon в отрыве от общей run-модели.
3. Делать file logic без полноценной access model.
4. Откладывать индексы и read-side до самого конца.
5. Смешивать release hardening с незавершённой бизнес-логикой.
6. Считать проект готовым без full end-to-end smoke.
7. Делать acceptance до завершения retention/timeout/superseded scenarios.

---

## 19. Что должен использовать оркестратор

Оркестратор должен использовать этот документ для:
- выбора текущего этапа;
- запрета преждевременного старта следующего этапа;
- определения допустимого параллелизма;
- проверки, какие документы обязательны к чтению агентом в конкретной задаче;
- постановки scoped задач разработчику, аудитору и тестировщику.

---

## 20. Что должен проверить аудитор по этапности

Аудитор должен проверить:

1. Что этапы реализуются в правильной последовательности.
2. Что WB/Ozon не начали до готовности run framework.
3. Что UI не заявлен завершённым до готовности history/logs/detail audit.
4. Что operational hardening не пропущен.
5. Что acceptance stabilization не сделан формально без полного smoke и regression.
6. Что ни один этап не расширил scope MVP.

---

## 21. Граница текущего документа

Данный документ фиксирует:
- этапы реализации;
- очередность этапов;
- зависимости;
- границы этапов;
- контрольные точки.

Следующий документ должен раскрыть:
- подробные задачи по этапам;
- для каждой задачи:
  - цель
  - результат
  - затрагиваемые модули
  - зависимости
  - критерий готовности

Имя следующего файла:
- `13_DETAILED_TASK_BREAKDOWN.md`