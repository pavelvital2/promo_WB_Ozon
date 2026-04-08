# 15_STAGE_DONE_CRITERIA.md

## 1. Назначение документа

Документ фиксирует:
- критерии завершения каждого этапа;
- обязательные выходные артефакты этапа;
- обязательные проверки на выходе этапа;
- условия, при которых этап нельзя считать завершённым;
- правила перехода к следующему этапу.

Документ не подменяет:
- этапы реализации из `12_IMPLEMENTATION_STAGES.md`;
- подробные задачи из `13_DETAILED_TASK_BREAKDOWN.md`;
- обязательные тестовые контуры из отдельного тестового документа.

---

## 2. Краткий итог

Этап считается завершённым только если одновременно выполнены все условия:

1. реализован заявленный объём этапа;  
2. соблюдены архитектурные инварианты;  
3. не нарушен ТЗ;  
4. существуют обязательные артефакты этапа;  
5. пройдены обязательные проверки этапа;  
6. нет открытых блокирующих дефектов внутри границ этапа;  
7. следующий этап действительно может стартовать без скрытых архитектурных пробелов.

Критически важно:
- “код написан” не означает “этап завершён”;
- “страница открывается” не означает “этап завершён”;
- “happy path работает” не означает “этап завершён”;
- “мы потом дотестируем” не означает “этап завершён”.

---

## 3. Общие правила завершения этапов

## 3.1. Правило полноты

Этап завершён только тогда, когда покрыты все обязательные задачи этапа, а не только их часть.

## 3.2. Правило непротиворечивости

Этап нельзя считать завершённым, если:
- его реализация противоречит ТЗ;
- его реализация противоречит архитектурным документам;
- он требует скрытого допущения, которого нет в ТЗ.

## 3.3. Правило проверяемости

Этап должен завершаться состоянием, которое:
- можно проверить отдельно;
- можно показать аудитору;
- можно использовать как базу для следующего этапа.

## 3.4. Правило неразрушения соседних контуров

Этап нельзя считать завершённым, если при его реализации:
- сломаны ранее завершённые этапы;
- нарушены инварианты runs/access/files/audit;
- появились скрытые cross-module regressions.

## 3.5. Правило блокирующих дефектов

Если внутри границ этапа остаются блокирующие дефекты, этап не закрывается.

Блокирующим считается дефект, который:
- ломает основной результат этапа;
- ломает следующий этап;
- делает поведение противоречащим ТЗ;
- делает результат невоспроизводимым или небезопасным.

---

## 4. Этап 1 считается завершённым, если

## 4.1. Обязательные артефакты

Должны существовать:
- базовая структура backend-проекта;
- централизованный конфигурационный контур;
- рабочее подключение PostgreSQL;
- рабочий migration mechanism;
- стартовый web application skeleton;
- UTC/time helper base;
- базовое application logging;
- CLI bootstrap entrypoint;
- seed базовых ролей и permissions;
- CLI-создание первого администратора.

## 4.2. Обязательные проверки

Нужно подтвердить:
- приложение стартует;
- БД доступна;
- миграции применяются;
- bootstrap роли и permissions создаются;
- первый admin создаётся через CLI;
- веб-сценарий создания первого admin отсутствует.

## 4.3. Этап 1 не считается завершённым, если

- проект не поднимается;
- migrations не работают;
- роли/permissions не инициализируются;
- первый admin нельзя создать через CLI;
- конфигурация хаотична или завязана на hardcoded production settings;
- нет базового runtime skeleton для следующих этапов.

---

## 5. Этап 2 считается завершённым, если

## 5.1. Обязательные артефакты

Должны существовать:
- все 12 обязательных сущностей БД;
- миграции для всех обязательных таблиц;
- FK, unique constraints, indexes и checks;
- persistence layer для обязательных сущностей;
- базовые repository/read/write abstractions.

## 5.2. Обязательные проверки

Нужно подтвердить:
- users/roles/permissions/user_permissions реализованы;
- stores/user_store_access реализованы;
- runs реализованы;
- run_files/temporary_uploaded_files реализованы;
- run_summary_audit/run_detail_audit реализованы;
- system_logs реализованы;
- timestamps хранятся в UTC;
- индексы под history/logs/detail audit присутствуют.

## 5.3. Этап 2 не считается завершённым, если

- отсутствует хотя бы одна обязательная сущность;
- detail audit не предусмотрен в PostgreSQL;
- run model неполон;
- file metadata tables неполны;
- constraints и indexes отсутствуют или критически неполны;
- persistence layer не позволяет строить application logic без прямого SQL в бизнес-слое.

---

## 6. Этап 3 считается завершённым, если

## 6.1. Обязательные артефакты

Должны существовать:
- login/logout flow;
- blocked user handling;
- change own password;
- users management для admin;
- stores management по ТЗ;
- assignment users to stores;
- authorization policy layer;
- role/permission/store-access enforcement;
- hidden sections behavior;
- no-store user behavior.

## 6.2. Обязательные проверки

Нужно подтвердить:
- admin может управлять пользователями;
- manager_lead и manager не могут управлять пользователями;
- role + permissions + user_store_access работают совместно;
- stores actions соблюдают роль/permission/store rules;
- archived store restrictions соблюдаются;
- no-store scenario работает;
- hidden sections скрываются, а не disabled;
- manager не видит stores и logs;
- manager_lead не видит users;
- logs доступны только admin.

## 6.3. Этап 3 не считается завершённым, если

- access control реализован частично;
- store-bound access проверяется только на UI;
- permissions не участвуют в реальном enforcement;
- no-store scenario отсутствует;
- hidden sections заменены disabled sections;
- archived store restrictions не соблюдаются;
- любой не-admin может делать admin-only действия.

---

## 7. Этап 4 считается завершённым, если

## 7.1. Обязательные артефакты

Должны существовать:
- temp upload pipeline;
- active temporary set model;
- delete/replace temp file actions;
- file size/count/type validation;
- stored filename/path/hash generation;
- run input copy storage;
- secure download flow;
- file availability metadata model.

## 7.2. Обязательные проверки

Нужно подтвердить:
- temp files грузятся и сохраняются в tmp contour;
- active set один на user+store+module;
- delete/replace меняют active set корректно;
- WB and Ozon file limits enforced;
- run input files копируются физически;
- tmp files не используются как единственный источник history;
- download защищён access checks;
- unavailable file model существует.

## 7.3. Этап 4 не считается завершённым, если

- tmp/input/output смешаны;
- нет active set semantics;
- run input files не копируются физически;
- прямой публичный доступ к файлам возможен;
- file limits не проверяются;
- file metadata не согласованы с фактическим storage behavior.

---

## 8. Этап 5 считается завершённым, если

## 8.1. Обязательные артефакты

Должны существовать:
- create check/process run use cases;
- lifecycle transition layer;
- background execution dispatcher;
- store+module locking;
- active_run_conflict handling;
- polling status read model;
- process auto-validation framework;
- run completion/finalization base.

## 8.2. Обязательные проверки

Нужно подтвердить:
- check создаёт отдельный run;
- process создаёт отдельный run;
- process проходит через validating;
- HTTP не выполняет долгую обработку синхронно;
- polling реально нужен и работает;
- одновременно нельзя запустить два active runs по одной паре store+module;
- locks снимаются после завершения;
- business_result заполняется только в финальном состоянии.

## 8.3. Этап 5 не считается завершённым, если

- async execution формальный, а не реальный;
- process не имеет validating phase;
- locking не защищает от гонок;
- polling не отражает реальные промежуточные состояния;
- lifecycle transitions допускают недопустимые комбинации;
- check/process по сути merged в один flow.

---

## 9. Этап 6 считается завершённым, если

## 9.1. Обязательные артефакты

Должны существовать:
- WB workbook intake;
- WB required columns validation;
- WB normalization;
- WB promo validation;
- WB aggregation;
- WB exact calculation engine;
- WB detail audit builder;
- WB summary audit builder;
- WB short result builder;
- WB check path;
- WB process path;
- WB safe write path.

## 9.2. Обязательные проверки

Нужно подтвердить:
- ровно 1 price file и 1..20 promo files обрабатываются корректно;
- первый лист используется по правилу ТЗ;
- required columns проверяются;
- normalization совпадает с ТЗ;
- aggregation считает MIN discount и MAX plan price;
- formula реализована строго;
- float не используется в финальном расчёте;
- threshold/fallback logic реализована в правильном порядке;
- check не создаёт output file;
- process меняет только `Новая скидка`;
- unsafe write correctly stops process;
- WB workbook остаётся пригодным.

## 9.3. Этап 6 не считается завершённым, если

- WB logic работает только на части сценариев;
- formula or fallback order отличаются от ТЗ;
- используется float;
- workbook ломается;
- меняются лишние колонки;
- detail audit или summary audit неполны;
- short result не согласован с outcome.

---

## 10. Этап 7 считается завершённым, если

## 10.1. Обязательные артефакты

Должны существовать:
- Ozon workbook intake;
- required sheet validation;
- column-by-letter validation;
- Ozon normalization;
- row decision engine;
- Ozon detail audit builder;
- Ozon summary audit builder;
- Ozon short result builder;
- Ozon check path;
- Ozon process path;
- K/L only writer;
- safe workbook save path.

## 10.2. Обязательные проверки

Нужно подтвердить:
- ровно один файл обязателен;
- лист `Товары и цены` обязателен;
- J/K/L/O/P/R определяются по буквенным позициям;
- обработка начинается со строки 4;
- `*`, empty, None трактуются как missing;
- порядок правил Ozon строго сохранён;
- process меняет только K и L;
- workbook остаётся пригодным для обратной загрузки;
- forced recalculation не используется;
- Ozon summary/detail audit полны;
- short result согласован с outcome.

## 10.3. Этап 7 не считается завершённым, если

- validation колонок идёт только по текстовым заголовкам;
- нарушен порядок правил;
- меняются колонки кроме K/L;
- workbook становится непригодным;
- detail audit/summary audit неполны;
- process/check outcomes не согласованы с ТЗ.

---

## 11. Этап 8 считается завершённым, если

## 11.1. Обязательные артефакты

Должны существовать:
- audit write path;
- detail audit read-side;
- system_logs write path;
- logs read-side;
- history read-side;
- run page read model.

## 11.2. Обязательные проверки

Нужно подтвердить:
- и check, и process сохраняют summary audit;
- и check, и process сохраняют detail audit;
- detail audit хранится в PostgreSQL;
- logs пишутся по обязательным event types;
- history строится из runs, а не из logs;
- logs page строится из system_logs, а не из audit;
- run page строится из run/audit/files, а не из logs;
- detail audit search/filter/sort/page серверные;
- logs search/filter/sort/page серверные;
- history search/filter/sort/page серверные.

## 11.3. Этап 8 не считается завершённым, если

- detail audit хранится не в БД;
- history/logs/detail audit загружаются целиком на клиент;
- logs и audit смешаны;
- run page требует повторного чтения workbook для основных колонок;
- access scoping для history/logs/run page не соблюдается.

---

## 12. Этап 9 считается завершённым, если

## 12.1. Обязательные артефакты

Должны существовать все обязательные страницы:
- login
- dashboard
- users
- stores
- processing/wb
- processing/ozon
- runs
- logs
- run/detail page
- change own password flow

## 12.2. Обязательные проверки

Нужно подтвердить:
- navigation соответствует роли/permissions;
- hidden sections работают;
- no-store dashboard scenario работает;
- history hidden for no-store user;
- WB processing page end-to-end usable;
- Ozon processing page end-to-end usable;
- history page работает серверно;
- logs page доступна только admin;
- run page и full audit page — один экран;
- unavailable file indicator отображается;
- polling статуса работает в UI.

## 12.3. Этап 9 не считается завершённым, если

- отсутствует хотя бы одна обязательная страница;
- run page раздвоена на два разных экрана вопреки ТЗ;
- hidden sections не соблюдаются;
- no-store scenario не доведён;
- processing pages формально есть, но не дают пройти end-to-end flow;
- UI дублирует бизнес-логику клиента.

---

## 13. Этап 10 считается завершённым, если

## 13.1. Обязательные артефакты

Должны существовать:
- temp files auto purge;
- run files retention execution;
- superseded result handling;
- timeout reconciliation;
- anomaly consistency checks;
- deployment/runtime hardening baseline.

## 13.2. Обязательные проверки

Нужно подтвердить:
- temp files автоматически очищаются через 24 часа;
- purge журналируется;
- expired/unavailable run files отражаются в metadata и UI;
- новый successful process переводит старый result в superseded;
- timeout завершает run финально и освобождает lock;
- anomalies логируются как system errors;
- historical records не теряются;
- deployment baseline готов для Ubuntu VPS + nginx + systemd.

## 13.3. Этап 10 не считается завершённым, если

- temp purge отсутствует;
- retention только “на бумаге”;
- superseded outputs не помечаются корректно;
- timeout может оставлять run зависшим;
- anomalies не фиксируются в logs;
- file availability model расходится с фактическим storage behavior.

---

## 14. Этап 11 считается завершённым, если

## 14.1. Обязательные артефакты

Должны существовать:
- unit/functional test suites по основным контурам;
- WB test contour;
- Ozon test contour;
- run lifecycle tests;
- file lifecycle tests;
- history/logs/detail audit tests;
- e2e smoke suite;
- acceptance verification result against TЗ.

## 14.2. Обязательные проверки

Нужно подтвердить:
- ключевые access scenarios покрыты тестами;
- WB business rules покрыты тестами;
- Ozon business rules покрыты тестами;
- async/lifecycle/timeout/lock scenarios покрыты тестами;
- file lifecycle/superseded/retention covered;
- history/logs/detail audit server-side behavior verified;
- smoke suite проходит;
- критические дефекты закрыты;
- acceptance соответствует ТЗ.

## 14.3. Этап 11 не считается завершённым, если

- нет smoke checks;
- нет проверки WB/Ozon критической логики;
- нет проверки access model;
- нет проверки run lifecycle;
- acceptance проведён формально без фактической сверки с ТЗ;
- остаются открытые критические дефекты.

---

## 15. Общие обязательные артефакты на выходе каждого этапа

Для каждого этапа, в пределах его объёма, должны существовать:

1. Реализация заявленных задач  
2. Актуальные миграции/конфигурации, если этап их затрагивает  
3. Минимально достаточные тесты или smoke-проверки этапа  
4. Логически завершённый модульный результат  
5. Подтверждение, что инварианты ТЗ не нарушены  
6. Основание для перехода к следующему этапу  

---

## 16. Общие запреты на ложное закрытие этапа

Этап запрещено закрывать по основаниям:

- “код уже написан”
- “вроде работает у разработчика локально”
- “happy path проходит”
- “остальное потом доделаем”
- “UI пока временный”
- “errors/retention/logs потом подключим”
- “audit можно пока не хранить в БД”
- “access потом ужесточим”
- “async пока псевдо-async”

Все такие формулировки означают, что этап не завершён.

---

## 17. Что считается блокирующим дефектом этапа

Блокирующим дефектом этапа считается любой дефект, который:

1. Ломает основной результат этапа  
2. Делает невозможным корректный старт следующего этапа  
3. Нарушает ТЗ  
4. Нарушает критический архитектурный инвариант  
5. Ломает безопасность, доступ или целостность данных  
6. Делает результат невоспроизводимым  
7. Ломает workbook safety в WB/Ozon  

---

## 18. Условия перехода к следующему этапу

Следующий этап можно начинать только если:

1. Предыдущий этап закрыт по критериям данного документа  
2. Нет открытых блокирующих дефектов предыдущего этапа  
3. Нет архитектурных пробелов, перекладываемых “на потом”  
4. Следующий этап не требует скрытого рефакторинга уже закрытого этапа  
5. Оркестратор и аудитор подтвердили, что база для следующего этапа реально готова  

---

## 19. Что должен делать оркестратор при приёмке этапа

Оркестратор обязан проверить:

1. Закрыты ли все задачи этапа  
2. Есть ли обязательные выходные артефакты  
3. Пройдены ли обязательные проверки этапа  
4. Нет ли scope drift  
5. Нет ли скрытого переноса обязательной части этапа на будущее  
6. Может ли следующий этап начинаться без архитектурного долга  

---

## 20. Что должен делать аудитор при приёмке этапа

Аудитор обязан проверить:

1. Соответствие этапа ТЗ  
2. Соответствие этапа архитектурным документам  
3. Отсутствие запрещённых упрощений  
4. Отсутствие незаявленного расширения MVP  
5. Наличие обязательных инвариантов этапа  
6. Корректность оснований, по которым этап хотят считать завершённым  

---

## 21. Что должен делать тестировщик при приёмке этапа

Тестировщик обязан проверить:

1. Реальный проверяемый результат этапа  
2. Наличие negative paths, а не только happy path  
3. Наличие smoke-проверки этапа  
4. Отсутствие ложного green-state при незавершённом функционале  
5. Готовность этапа как базы для следующего этапа  

---

## 22. Контрольная таблица “этап закрыт / не закрыт”

Этап считается **закрытым**, если:
- есть все артефакты;
- пройдены все обязательные проверки;
- нет блокирующих дефектов;
- следующий этап может стартовать.

Этап считается **не закрытым**, если:
- отсутствует хотя бы один обязательный результат;
- не пройдена хотя бы одна обязательная проверка;
- остался хотя бы один блокирующий дефект;
- следующий этап потребует срочно переделывать предыдущий.

---

## 23. Граница текущего документа

Данный документ фиксирует:
- критерии завершения этапов;
- обязательные выходные артефакты;
- условия перехода между этапами;
- запреты на ложное закрытие этапа.

Следующий документ должен раскрыть:
- обязательные тестовые контуры;
- smoke-checks;
- минимальный набор проверок по ключевым зонам;
- coverage, без которого MVP нельзя считать принятым.

Имя следующего файла:
- `16_REQUIRED_TEST_CONTOURS_AND_SMOKE_CHECKS.md`