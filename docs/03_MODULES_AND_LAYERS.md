# 03_MODULES_AND_LAYERS.md

## 1. Назначение документа

Документ фиксирует:
- состав внутренних модулей системы;
- состав архитектурных слоёв;
- назначение сервисов и обработчиков;
- допустимые зависимости между модулями;
- внутренние технические компоненты, необходимые для реализации ТЗ;
- границы ответственности между модулями.

Документ не определяет:
- окончательную SQL-схему;
- точные маршруты UI;
- точные названия классов и файлов реализации;
- этапы и задачи проекта.

---

## 2. Краткий итог

Система должна быть реализована как модульный монолит с четырьмя основными слоями:

1. presentation layer  
2. application layer  
3. domain layer  
4. infrastructure layer  

Внутри этого монолита выделяются обязательные логические модули:

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

Каждый модуль должен иметь строго ограниченную зону ответственности.
Модули WB и Ozon должны быть полностью разделены на уровне use case, domain logic и Excel adapters.
Модули runs, audit, logs и file_storage являются общесистемными и обслуживают оба маркетплейса без смешения их бизнес-правил.

---

## 3. Слои архитектуры

## 3.1. Presentation layer

Назначение:
- принимать HTTP-запросы;
- рендерить страницы;
- принимать формы;
- инициировать сценарии;
- выполнять polling;
- формировать HTTP-ответы и сообщения интерфейсу.

Содержит:
- page handlers / controllers;
- form parsers;
- query parameter parsers;
- response mappers;
- table state mappers;
- download handlers;
- session-bound user context readers.

Не содержит:
- бизнес-расчётов;
- Excel-логики;
- прямой SQL-бизнес-логики;
- доменных правил access control;
- логики жизненного цикла run.

## 3.2. Application layer

Назначение:
- реализовывать прикладные сценарии;
- координировать работу модулей;
- проверять доступ к use case;
- управлять транзакциями;
- вызывать domain services;
- вызывать infrastructure adapters;
- формировать итог выполнения сценария.

Содержит:
- use cases;
- application services;
- command handlers;
- query handlers;
- orchestration coordinators;
- run lifecycle coordinators.

Не содержит:
- низкоуровневого чтения/записи Excel;
- конкретных SQL-реализаций;
- рендеринга HTML;
- независимого хранения состояния вне репозиториев.

## 3.3. Domain layer

Назначение:
- содержать обязательные бизнес-правила;
- нормализовать входные данные;
- рассчитывать результат;
- принимать решения по строкам;
- формировать summary/detail audit payload;
- определять short_result_text;
- определять business_result внутри допустимых наборов.

Содержит:
- domain services;
- pure calculation rules;
- validators;
- normalization rules;
- audit row composers;
- summary aggregators;
- domain enums и value objects.

Не содержит:
- HTTP-контроллеров;
- SQL-запросов;
- прямой работы с файловой системой;
- прямой работы с конкретной библиотекой Excel.

## 3.4. Infrastructure layer

Назначение:
- обеспечивать техническую реализацию хранения и ввода-вывода;
- читать и сохранять Excel;
- работать с БД;
- работать с файлами;
- работать с фоновой асинхронной задачей;
- обеспечивать hashing, logging и bootstrap.

Содержит:
- repositories;
- DB mappers;
- Excel readers/writers;
- filesystem storage adapters;
- background task executor;
- lock adapters;
- password hash adapter;
- CLI bootstrap executor;
- retention jobs;
- timezone/display helpers.

Не содержит:
- самовольной бизнес-логики;
- расширения жизненных статусов;
- самостоятельных доменных решений вне domain layer.

---

## 4. Обязательные модули системы

## 4.1. Модуль `shared`

Назначение:
- общие технические типы;
- общие исключения;
- общие базовые enum wrappers;
- clock abstraction;
- result wrappers;
- pagination primitives;
- sorting/filtering contracts;
- constants общего уровня.

Типовой состав:
- base errors;
- utc clock service interface;
- paging request / paging response models;
- filter specification primitives;
- generic operation result structures;
- common text/value normalization helpers, не завязанные на WB/Ozon-логику.

Запрет:
- в `shared` нельзя переносить WB/Ozon-логику ради “унификации”.

---

## 4.2. Модуль `auth`

Назначение:
- вход пользователя;
- выход пользователя;
- проверка авторизованной сессии;
- смена собственного пароля;
- фиксация успешного и неуспешного входа;
- проверка blocked user.

Application components:
- login use case;
- logout use case;
- change own password use case;
- current session resolver.

Domain components:
- password policy contract только в пределах минимально необходимой логики безопасности;
- authentication result model;
- blocked user access rule.

Infrastructure components:
- password hash adapter;
- session adapter;
- auth event logger.

Presentation components:
- login page handler;
- logout handler;
- change password page/action.

---

## 4.3. Модуль `users`

Назначение:
- создание пользователей;
- редактирование пользователей;
- блокировка/разблокировка пользователей;
- назначение ролей;
- назначение explicit permissions;
- просмотр списка пользователей.

Application components:
- create user use case;
- update user use case;
- block user use case;
- unblock user use case;
- assign role use case;
- assign user permissions use case;
- users list query use case.

Domain components:
- user edit validation;
- uniqueness validation for username;
- user state invariants.

Infrastructure components:
- users repository;
- roles repository;
- permissions repository;
- user_permissions repository.

Presentation components:
- users list page;
- create/edit user form handlers;
- block/unblock actions.

---

## 4.4. Модуль `access`

Назначение:
- проверка прав доступа по роли;
- проверка explicit permissions;
- проверка доступа к магазинам;
- определение доступных разделов интерфейса;
- enforcement доступа в use case.

Application components:
- authorization service;
- store access resolver;
- UI visibility resolver;
- permission check service.

Domain components:
- access policy rules;
- role capability matrix;
- user_store_access invariants;
- forbidden action rules.

Infrastructure components:
- access repositories or read services поверх users/permissions/stores tables;
- permission aggregation provider.

Presentation components:
- menu visibility provider;
- route guard integration;
- page-level access filter.

Важное правило:
- `access` принимает решение о праве, но не управляет самими store/user сущностями.

---

## 4.5. Модуль `stores`

Назначение:
- создание магазинов;
- редактирование магазинов;
- архивирование;
- восстановление;
- изменение store settings;
- выбор магазинов для UI;
- контроль недоступности archived store для новых запусков.

Application components:
- create store use case;
- update store use case;
- archive store use case;
- restore store use case;
- list stores use case;
- store selector query use case;
- update store settings use case.

Domain components:
- store uniqueness rules;
- marketplace-specific required fields;
- archived store invariants;
- created store auto-access rule для manager_lead с permission create_store.

Infrastructure components:
- stores repository;
- user_store_access repository.

Presentation components:
- stores list page;
- create/edit/archive/restore handlers;
- store selector loaders.

---

## 4.6. Модуль `temp_files`

Назначение:
- загрузка временных файлов;
- удаление файла из активного набора;
- замена файла;
- получение активного набора;
- контроль набора по паре user + store + module;
- вычисление input set signature;
- очистка истёкших временных файлов.

Application components:
- upload temporary file use case;
- delete temporary file use case;
- replace temporary file use case;
- get active temporary set use case;
- build current input set signature use case;
- purge expired temporary files use case.

Domain components:
- temporary set invariants;
- allowed file count rules;
- file size rules;
- allowed module-specific file composition rules;
- “same file” identity rules на основе sha256 + file_size_bytes;
- current active set semantics.

Infrastructure components:
- temporary_uploaded_files repository;
- temp filesystem adapter;
- file hash calculator;
- MIME/type validator;
- XLSX basic validator.

Presentation components:
- upload handlers;
- delete/replace handlers;
- active set widgets on processing pages.

---

## 4.7. Модуль `runs`

Назначение:
- создание run;
- orchestration check/process;
- lifecycle transitions;
- polling state reads;
- blocking/locking;
- timeout handling;
- finishing run;
- marking result file links;
- фиксация validation_was_auto_before_process.

Это центральный прикладной модуль исполнения.

Application components:
- create check run use case;
- create process run use case;
- get run status use case;
- get run page query use case;
- run lifecycle coordinator;
- active run conflict detector;
- process auto-validation coordinator;
- run completion finalizer;
- superseded result resolver.

Domain components:
- lifecycle transition rules;
- business_result compatibility rules;
- active run invariant;
- lock ownership semantics;
- completed/failed finalization invariants.

Infrastructure components:
- runs repository;
- run_files repository;
- background executor adapter;
- lock adapter;
- timeout monitor;
- task dispatch adapter.

Presentation components:
- check start endpoint;
- process start endpoint;
- polling endpoint;
- run page endpoint.

Важное правило:
- `runs` не выполняет расчёты WB/Ozon сам;
- `runs` координирует соответствующие processing modules.

---

## 4.8. Модуль `wb`

Назначение:
- полный прикладной и доменный контур обработки Wildberries.

Подконтуры:
- workbook intake;
- price file validation;
- promo files validation;
- row normalization;
- promo aggregation;
- discount calculation;
- threshold/fallback logic;
- audit generation;
- result workbook writing.

Application components:
- wb check execution service;
- wb process execution service;
- wb source files preparation service;
- wb result file builder coordinator.

Domain components:
- wb column resolver;
- wb row normalizer;
- wb promo row normalizer;
- wb critical validation rules;
- wb warning rules;
- wb promo aggregation service;
- wb discount calculation service;
- wb final decision service;
- wb summary audit builder;
- wb detail audit row builder;
- wb short result builder.

Infrastructure components:
- wb workbook reader;
- wb workbook safe writer;
- wb sheet selector;
- wb style-preserving write adapter in the limits technically supported;
- wb file structure verification adapter.

Presentation components:
- none unique beyond WB processing page bindings.

Запрет:
- никакая логика Ozon не должна попадать в модуль WB.

---

## 4.9. Модуль `ozon`

Назначение:
- полный прикладной и доменный контур обработки Ozon.

Подконтуры:
- workbook intake;
- required sheet validation;
- required columns-by-letter validation;
- row normalization;
- participation decision logic;
- output value composition for K and L;
- audit generation;
- result workbook writing.

Application components:
- ozon check execution service;
- ozon process execution service;
- ozon result file builder coordinator.

Domain components:
- ozon sheet validation rule;
- ozon letter-based column validation rule;
- ozon row normalizer;
- ozon decision engine;
- ozon reason classifier;
- ozon summary audit builder;
- ozon detail audit row builder;
- ozon short result builder.

Infrastructure components:
- ozon workbook reader;
- ozon workbook safe writer;
- ozon workbook structure preservation adapter;
- ozon cell-address writer for K/L only.

Presentation components:
- none unique beyond Ozon processing page bindings.

Запрет:
- никакая логика WB не должна попадать в модуль Ozon.

---

## 4.10. Модуль `audit`

Назначение:
- единый способ хранения и чтения summary audit и detail audit;
- серверная работа с детальным аудитом;
- подготовка данных для run page.

Application components:
- save run summary audit use case;
- save run detail audit batch use case;
- get run summary audit query;
- get run detail audit paged query;
- get run detail preview query.

Domain components:
- audit persistence contract;
- severity mapping contract;
- audit filtering/sorting specification.

Infrastructure components:
- run_summary_audit repository;
- run_detail_audit repository;
- bulk insert adapter;
- indexed audit query adapter.

Presentation components:
- run page summary block provider;
- detail preview table handler;
- full detail audit table handler.

---

## 4.11. Модуль `logs`

Назначение:
- запись системных событий;
- поиск/фильтрация/сортировка/пагинация логов;
- доступ к логам по правилам доступа.

Application components:
- log event writer service;
- logs search query use case;
- structured system error logging service.

Domain components:
- event type catalog;
- log severity rules;
- payload normalization rules.

Infrastructure components:
- system_logs repository;
- indexed log query adapter;
- rotating application log sink, если используется совместно с DB logging.

Presentation components:
- logs page handler;
- log filter/query binding.

---

## 4.12. Модуль `history`

Назначение:
- формирование списка запусков;
- поиск, фильтрация, сортировка, пагинация history;
- подготовка карточек строк history;
- связь history с file availability и run metadata.

Application components:
- runs history query use case;
- downloadable files availability query;
- history row composition service.

Domain components:
- history filter specification;
- history sort specification;
- run list visibility rules.

Infrastructure components:
- history read model adapter на основе runs + stores + users + run_files;
- optimized indexed queries.

Presentation components:
- history page handler;
- history filter/sort/page binder.

---

## 4.13. Модуль `file_storage`

Назначение:
- физическое размещение файлов;
- чтение/выдача файлов на скачивание;
- перевод файлов в unavailable;
- retention for run files;
- superseded result processing;
- secure download stream.

Application components:
- store uploaded temporary file service;
- copy files into run input service;
- store process result file service;
- mark file unavailable service;
- secure download use case;
- retention execution service.

Domain components:
- storage path building rules;
- file availability rules;
- unavailable reason rules;
- retention eligibility rules.

Infrastructure components:
- filesystem adapter;
- path resolver;
- streaming download adapter;
- sha256 calculator;
- safe overwrite prevention adapter.

Presentation components:
- download handlers for input/result files.

---

## 4.14. Модуль `admin_cli`

Назначение:
- инициализация системы через CLI;
- создание первого администратора;
- создание стартовых ролей;
- создание стартовых permissions;
- возможная первичная seed-инициализация справочных значений.

Application components:
- initialize system use case;
- create first admin use case;
- seed base roles/permissions use case.

Infrastructure components:
- CLI command adapter;
- terminal interaction adapter;
- bootstrap repositories.

Presentation components:
- отсутствуют.

---

## 4.15. Модуль `system_maintenance`

Назначение:
- системные технические операции без расширения MVP;
- очистка истёкших временных файлов;
- обработка retention run files;
- проверка согласованности доступности файлов;
- контроль hard-timeout задач;
- запись системных событий обслуживания.

Application components:
- purge expired temporary files job;
- run files retention job;
- timeout reconciliation job;
- consistency check service.

Infrastructure components:
- scheduler trigger внутри systemd-managed app environment;
- maintenance repositories;
- filesystem cleanup adapter.

Важно:
- этот модуль не является пользовательской подсистемой;
- он нужен только для обязательных требований хранения, timeout и журналирования.

---

## 5. Обязательные типы компонентов внутри модулей

Для единообразия проектирования в модулях допустимы следующие типы компонентов.

## 5.1. Use cases

Используются для завершённых пользовательских или системных сценариев.

Примеры типов:
- create_store;
- upload_temp_file;
- start_wb_check;
- start_ozon_process;
- view_run_history;
- download_result_file.

Правило:
- один use case реализует один завершённый сценарий с понятной точкой входа и точкой завершения.

## 5.2. Query services

Используются для чтения данных без модификации состояния.

Примеры:
- get run page;
- get history page;
- get logs page;
- get audit detail page.

Правило:
- query services не должны изменять состояние системы.

## 5.3. Domain services

Используются для:
- расчётов;
- классификации;
- нормализации;
- принятия решений;
- формирования аудита;
- проверки инвариантов.

Примеры:
- wb discount calculation service;
- ozon participation decision service;
- store access domain policy.

## 5.4. Repositories

Используются только как интерфейс чтения/записи сущностей и read models.

Правило:
- репозиторий не должен быть местом бизнес-логики;
- сложные условия поиска/сортировки допускаются как query repository/read model adapter.

## 5.5. Adapters

Используются для внешних и технических зависимостей:
- PostgreSQL;
- filesystem;
- session;
- hashing;
- Excel library;
- background execution;
- lock mechanism.

## 5.6. Builders / composers

Используются для:
- short_result_text;
- summary audit;
- detail audit payload;
- history row view model;
- run page view model.

---

## 6. Допустимые зависимости между модулями

Ниже фиксируются допустимые направления зависимостей.

## 6.1. Общие правила

Разрешено:
- presentation -> application
- application -> domain
- application -> infrastructure interfaces/adapters
- infrastructure -> external libraries

Запрещено:
- domain -> presentation
- domain -> concrete infrastructure
- WB domain -> Ozon domain
- Ozon domain -> WB domain
- logs -> wb/ozon business logic
- history -> изменение состояния run

## 6.2. Модульные зависимости

### `auth`
Может зависеть от:
- shared
- users
- logs
- access

### `users`
Может зависеть от:
- shared
- access
- logs

### `access`
Может зависеть от:
- shared
- users
- stores

### `stores`
Может зависеть от:
- shared
- access
- logs

### `temp_files`
Может зависеть от:
- shared
- stores
- access
- file_storage
- logs

### `runs`
Может зависеть от:
- shared
- stores
- access
- temp_files
- audit
- logs
- file_storage
- wb
- ozon

### `wb`
Может зависеть от:
- shared
- audit
- file_storage только через application coordination, не для принятия бизнес-решений

### `ozon`
Может зависеть от:
- shared
- audit
- file_storage только через application coordination, не для принятия бизнес-решений

### `audit`
Может зависеть от:
- shared

### `logs`
Может зависеть от:
- shared

### `history`
Может зависеть от:
- shared
- access
- runs
- stores
- users
- file_storage read metadata

### `file_storage`
Может зависеть от:
- shared
- logs

### `admin_cli`
Может зависеть от:
- shared
- auth
- users
- access
- stores
- logs

### `system_maintenance`
Может зависеть от:
- shared
- temp_files
- file_storage
- runs
- logs

---

## 7. Разделение обработчиков check и process

Для обоих маркетплейсов должны существовать раздельные application handlers:

### Wildberries
- wb check start handler
- wb check execution handler
- wb process start handler
- wb process execution handler

### Ozon
- ozon check start handler
- ozon check execution handler
- ozon process start handler
- ozon process execution handler

Причина разделения:
- разные lifecycle paths;
- разные business_result rules;
- process содержит встроенную auto-validation;
- check не формирует output file;
- process формирует output file.

Допускается переиспользование внутренних подэтапов, но не допускается архитектурное слияние check/process в один handler с неявной веткой.

---

## 8. Сервисы жизненного цикла run

Внутри модуля `runs` должны быть выделены отдельные сервисы.

## 8.1. Run creation service

Назначение:
- создать запись run в статусе created;
- зафиксировать инициатора, магазин, тип операции, модуль, input signature;
- подготовить run к асинхронному исполнению.

## 8.2. Run dispatch service

Назначение:
- передать run на backend execution;
- не выполнять тяжёлую логику внутри HTTP.

## 8.3. Run lock service

Назначение:
- проверить active run conflict;
- установить блокировку;
- снять блокировку после завершения или аварии.

## 8.4. Run transition service

Назначение:
- переводить lifecycle_status только по разрешённым переходам;
- не допускать недопустимых комбинаций lifecycle_status и business_result.

## 8.5. Run completion service

Назначение:
- завершить run;
- записать business_result;
- записать short_result_text;
- связать result_file_id;
- установить finished_at_utc;
- инициировать superseded handling для process output.

## 8.6. Run polling query service

Назначение:
- возвращать UI только необходимое состояние:
  - lifecycle_status;
  - business_result;
  - short_result_text;
  - возможно признаки готовности summary/result.

---

## 9. Внутренние компоненты Excel-обработки

ТЗ запрещает ломать структуру рабочих файлов, поэтому Excel-обработка должна быть разложена на отдельные технические компоненты.

## 9.1. Общие Excel adapters

Допустимы:
- workbook open adapter;
- workbook validity probe;
- workbook save adapter;
- protected/unsafe workbook detector;
- sheet access adapter.

## 9.2. WB-specific Excel components

- first sheet selector;
- required columns resolver by header names;
- price rows reader;
- promo rows reader;
- safe write checker for “Новая скидка”;
- wb result writer that changes only target column;
- wb structure preservation adapter.

## 9.3. Ozon-specific Excel components

- required sheet resolver for “Товары и цены”;
- required column letter verifier for J/K/L/O/P/R;
- row reader from row 4;
- K/L only writer;
- workbook structure preservation adapter for Ozon upload safety.

---

## 10. Сервисы аудита и краткого результата

И для WB, и для Ozon должны существовать отдельные builders:

### Summary audit builders
- wb summary audit builder
- ozon summary audit builder

### Detail audit builders
- wb detail audit row builder
- ozon detail audit row builder

### Short result builders
- wb short result builder
- ozon short result builder

Архитектурное правило:
- summary audit и short result не должны собираться в presentation layer;
- они формируются на domain/application boundary и сохраняются как часть run outcome.

---

## 11. Сервисы history, logs и detail audit read-side

Для тяжёлых таблиц нужны отдельные query-oriented компоненты.

## 11.1. History read service

Должен поддерживать:
- search;
- AND-combined filters;
- server-side sorting;
- pagination 25/50/100.

## 11.2. Logs read service

Должен поддерживать:
- search;
- filters;
- sort;
- pagination;
- ограничение доступа для manager.

## 11.3. Detail audit read service

Должен поддерживать:
- search по row_number/entity/message/decision_reason;
- filters по severity/decision_reason/range;
- server-side sort;
- pagination;
- preview mode для processing page;
- full mode для run page.

---

## 12. Внутренние технические компоненты, допустимые сверх бизнес-сущностей

ТЗ запрещает расширять бизнес-сущности без необходимости, но допускает внутренние технические компоненты.
Ниже фиксируются допустимые внутренние технические компоненты.

1. background task executor
2. lock manager
3. transaction manager
4. clock service
5. file hash service
6. path builder
7. pagination/sort/filter specification helpers
8. workbook validation adapters
9. consistency checker for superseded results
10. retention execution service
11. timeout reconciliation service
12. secure download stream adapter

Эти компоненты:
- не вводят новые пользовательские сущности;
- не меняют контракт MVP;
- являются допустимой внутренней технической реализацией.

---

## 13. Запреты по модульной организации

Запрещается:

1. Делать единый “universal marketplace engine” для WB и Ozon.
2. Делать единый “process anything” handler без разделения WB/Ozon.
3. Смешивать audit storage и system logs в одной сущности.
4. Реализовывать history, logs и detail audit без выделенных read-side компонентов.
5. Переносить важную логику доступа в presentation layer.
6. Делать file download вне централизованного secure file_storage/use-case слоя.
7. Делать temp files и run files одним и тем же контуром хранения.
8. Прятать жизненный цикл run внутри Excel adapters.
9. Делать process как “check + silent write” без отдельного process lifecycle.
10. Хранить крупный detail audit только в памяти текущего процесса без записи в БД.

---

## 14. Что должно быть проверено аудитором по этому документу

Аудитор при проверке архитектуры и реализации должен отдельно проверить:

1. Что WB и Ozon разнесены по отдельным модулям.
2. Что check и process разнесены по отдельным use case и execution paths.
3. Что runs не содержит бизнес-логики расчёта WB/Ozon.
4. Что Excel adapters не принимают бизнес-решения вместо domain layer.
5. Что history/logs/detail audit реализованы как отдельные read-side сценарии.
6. Что access control вынесен в отдельный модуль, а не размазан по UI.
7. Что temp files, run input files и run output files имеют разные контуры.
8. Что system_maintenance существует только как технический контур и не расширяет MVP.
9. Что недопустимые зависимости между модулями не появились.
10. Что нет скрытого универсального движка, меняющего поведение ТЗ.

---

## 15. Граница текущего документа

Данный документ фиксирует только состав модулей, слоёв и компонентов.

Следующим документом должна быть полная модель данных и структура БД:
- обязательные таблицы;
- поля;
- связи;
- индексы;
- ограничения;
- инварианты.