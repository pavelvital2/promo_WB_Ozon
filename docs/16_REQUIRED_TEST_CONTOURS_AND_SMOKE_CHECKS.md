# 16_REQUIRED_TEST_CONTOURS_AND_SMOKE_CHECKS.md

## 1. Назначение документа

Документ фиксирует:
- обязательные тестовые контуры проекта;
- минимально необходимый набор проверок;
- smoke-checks по ключевым этапам и подсистемам;
- критические позитивные, негативные и граничные сценарии;
- тестовые зоны, без которых MVP нельзя считать принятым.

Документ не задаёт конкретный фреймворк тестирования.
Он задаёт именно обязательное покрытие.

---

## 2. Краткий итог

Для данного проекта недостаточно проверить только happy path.
Обязательны проверки по следующим зонам:

1. bootstrap и базовая инициализация  
2. auth и users  
3. roles / permissions / user_store_access  
4. stores и archived store behavior  
5. temporary files и active set  
6. file storage / secure download / availability  
7. runs lifecycle / async / polling / locking  
8. WB business logic и workbook safety  
9. Ozon business logic и workbook safety  
10. summary/detail audit  
11. history / logs / detail audit read-side  
12. retention / purge / superseded / timeout reconciliation  
13. end-to-end smoke flows  

Минимальный принцип:
- если контур влияет на доступ, деньги, файл результата, историю или приёмку workbook, он должен быть покрыт тестами.

---

## 3. Общие правила тестирования

## 3.1. Обязательны три класса проверок

Для ключевых зон должны существовать:
- позитивные сценарии;
- негативные сценарии;
- граничные сценарии.

## 3.2. Обязательны уровни проверок

Минимально допустимы:
- unit tests для локальной бизнес-логики;
- integration tests для межмодульных контуров;
- smoke/e2e tests для ключевых пользовательских сценариев.

## 3.3. Что не допускается как “достаточное тестирование”

Недостаточно:
- проверить только вручную;
- проверить только один валидный файл;
- проверить только UI без backend инвариантов;
- проверить только status 200;
- проверить только “файл открылся”.

## 3.4. Критический принцип

Если логика влияет на:
- итоговую скидку WB;
- участие/цену Ozon;
- доступ к файлам;
- history/logs/detail audit;
- блокировки run;
то она должна иметь явную тестовую проверку.

---

## 4. Контур 1. Bootstrap и инициализация системы

## 4.1. Обязательные проверки

Нужно проверить:
- приложение стартует;
- БД подключается;
- миграции применяются на чистую БД;
- seed базовых ролей выполняется;
- seed базовых permissions выполняется;
- первый admin создаётся через CLI;
- веб-сценарий создания первого admin отсутствует.

## 4.2. Негативные сценарии

Нужно проверить:
- повторная инициализация не создаёт дубли ролей/permissions;
- создание первого admin с некорректными входными данными обрабатывается контролируемо.

## 4.3. Smoke-check этапа

Минимальный smoke:
1. применить миграции;
2. выполнить bootstrap;
3. проверить наличие admin / manager_lead / manager;
4. проверить наличие create_store / edit_store;
5. создать первого admin через CLI.

---

## 5. Контур 2. Auth и users

## 5.1. Обязательные проверки auth

Нужно проверить:
- успешный login;
- неуспешный login;
- blocked user login denial;
- logout;
- смену собственного пароля;
- обновление last_login_at_utc;
- логирование successful_login / failed_login / logout.

## 5.2. Обязательные проверки users

Нужно проверить:
- admin создаёт пользователя;
- admin редактирует пользователя;
- admin блокирует/разблокирует пользователя;
- admin назначает роль;
- admin назначает permissions;
- non-admin не может управлять пользователями.

## 5.3. Граничные сценарии

Нужно проверить:
- уникальность username;
- невозможность обойти blocked state;
- невозможность user-management без admin role.

## 5.4. Smoke-check этапа

1. войти admin;
2. создать пользователя;
3. назначить ему роль;
4. назначить permission;
5. выйти;
6. войти новым пользователем;
7. заблокировать пользователя;
8. убедиться, что повторный вход запрещён.

---

## 6. Контур 3. Access control

## 6.1. Обязательные проверки ролей

Нужно проверить:

### Admin
- видит все разделы;
- имеет полный доступ ко всем stores/runs/files/logs.

### Manager_lead
- не видит users;
- видит stores только при наличии create_store или edit_store;
- работает только в assigned store contour;
- не видит logs.

### Manager
- не видит users;
- не видит stores;
- не видит logs;
- работает только в assigned store contour.

## 6.2. Обязательные проверки permissions

Нужно проверить:
- manager_lead без create_store не может создать store;
- manager_lead с create_store может создать store;
- manager_lead без edit_store не может редактировать store;
- manager_lead с edit_store может редактировать только assigned active store.

## 6.3. Обязательные проверки user_store_access

Нужно проверить:
- manager/manager_lead видят только assigned stores;
- не видят чужую history;
- не видят чужой run page;
- не могут скачать файл чужого run;
- admin работает без обязательного user_store_access.

## 6.4. No-store scenario

Нужно проверить:
- пользователь без stores входит в систему;
- видит dashboard;
- видит “Нет доступных магазинов”;
- не видит history;
- не может запускать check/process;
- manager_lead с create_store видит возможность создать store.

## 6.5. Hidden sections

Нужно проверить:
- недоступные разделы скрыты;
- не показываются disabled;
- прямой URL не обходит backend authorization.

## 6.6. Smoke-check этапа

1. создать admin / manager_lead / manager;
2. создать 2 stores;
3. привязать manager только к одному store;
4. проверить меню и доступы каждого пользователя;
5. проверить, что manager не открывает чужой run/history/file.

---

## 7. Контур 4. Stores и archived store behavior

## 7.1. Обязательные проверки stores

Нужно проверить:
- create store;
- edit store;
- archive store;
- restore store;
- WB settings editing;
- uniqueness by (marketplace, name).

## 7.2. Archived store behavior

Нужно проверить:
- archived store виден в history context;
- archived store не попадает в selector новых запусков;
- archived store не редактируется;
- restore only by admin;
- manager_lead не архивирует и не восстанавливает store.

## 7.3. Граничные сценарии

Нужно проверить:
- одинаковые имена допустимы для разных marketplace;
- одинаковые имена недопустимы внутри одного marketplace;
- WB store требует обязательные WB settings;
- Ozon store не требует WB settings.

## 7.4. Smoke-check этапа

1. создать WB и Ozon store;
2. отредактировать WB settings;
3. архивировать один store;
4. проверить, что он исчез из selector запуска;
5. восстановить store под admin.

---

## 8. Контур 5. Temporary files и active set

## 8.1. Обязательные проверки upload

Нужно проверить:
- upload valid `.xlsx`;
- reject invalid extension/format;
- per-file size limit;
- WB total size limit;
- WB promo file count limit;
- Ozon single-file rule.

## 8.2. Обязательные проверки active set

Нужно проверить:
- один active set на user+store+module;
- delete temp file;
- replace temp file;
- повторная загрузка идентичного файла создаёт новый temporary object;
- любое изменение состава invalidates previous check semantics.

## 8.3. Purge behavior

Нужно проверить:
- temp files older than 24h очищаются;
- после purge набор считается пустым;
- purge журналируется.

## 8.4. Smoke-check этапа

1. загрузить temp files;
2. увидеть active set на processing page;
3. удалить один файл;
4. заменить файл;
5. проверить, что active set обновился;
6. симулировать TTL purge и проверить пустой набор.

---

## 9. Контур 6. File storage, secure download и availability

## 9.1. Обязательные проверки file metadata

Нужно проверить:
- original_filename сохраняется;
- stored_filename уникален;
- storage_relative_path корректен;
- file_size_bytes сохраняется;
- file_sha256 сохраняется;
- is_available / unavailable_reason работают.

## 9.2. Обязательные проверки run input/output

Нужно проверить:
- run input files копируются физически;
- два одинаковых runs имеют независимые input copies;
- check не создаёт output file;
- successful process создаёт output file;
- failed/validation_failed process не создаёт доступный result file.

## 9.3. Secure download

Нужно проверить:
- нет прямого публичного URL;
- file download проходит через backend authorization;
- foreign file denied;
- unavailable file denied;
- blocked user denied.

## 9.4. File availability UI

Нужно проверить:
- “Файл недоступен” отображается;
- download button disabled;
- причины unavailable корректно отражаются.

## 9.5. Smoke-check этапа

1. выполнить successful process;
2. скачать result file;
3. скачать input file;
4. сделать файл unavailable;
5. проверить disabled download и marker.

---

## 10. Контур 7. Runs lifecycle, async execution, locking и polling

## 10.1. Обязательные lifecycle tests

Нужно проверить:

### Check
- created -> checking -> completed
- created -> checking -> failed

### Process
- created -> validating -> processing -> completed
- created -> validating -> failed
- created -> validating -> processing -> failed

## 10.2. Business_result tests

Нужно проверить:
- business_result NULL до финального состояния;
- business_result заполнен после финального состояния;
- check использует только check_* results;
- process использует только process-specific results.

## 10.3. Locking tests

Нужно проверить:
- второй active run на тот же store+module запрещён;
- check во время process запрещён;
- process во время check запрещён;
- runs по разным stores разрешены.

## 10.4. Polling tests

Нужно проверить:
- polling возвращает промежуточные статусы;
- polling завершается на completed/failed;
- UI получает business_result и short_result_text после завершения.

## 10.5. Timeout tests

Нужно проверить:
- hard-timeout для check;
- hard-timeout для process;
- run получает финальный failed-state;
- lock освобождается;
- system log пишется.

## 10.6. Smoke-check этапа

1. запустить check;
2. увидеть checking в polling;
3. дождаться completed/failed;
4. запустить process;
5. увидеть validating, затем processing;
6. убедиться, что parallel second run blocked.

---

## 11. Контур 8. Wildberries business logic

## 11.1. Обязательные input tests

Нужно проверить:
- отсутствует file price -> критическая ошибка;
- отсутствуют promo files -> критическая ошибка;
- invalid xlsx -> критическая ошибка;
- missing required columns -> критическая ошибка;
- duplicate Артикул WB in price file -> критическая ошибка;
- all promo files invalid -> критическая ошибка.

## 11.2. Обязательные normalization tests

Нужно проверить:
- trim article;
- remove `.0`;
- empty article -> missing;
- spaces/NBSP cleanup in numbers;
- comma-to-dot normalization;
- invalid numeric values -> missing.

## 11.3. Обязательные aggregation tests

Нужно проверить:
- grouping by normalized article;
- MIN promo discount;
- MAX plan price;
- invalid promo rows excluded;
- multiple promo files aggregated correctly.

## 11.4. Обязательные formula tests

Нужно проверить:
- exact formula:
  - `ceil((1 - max_plan_price / current_price) * 100)`
- no float in final calculation;
- correct ceil behavior;
- correct MIN(min_discount, calculated_discount);
- correct threshold branch;
- correct fallback_no_promo branch;
- correct ordinary branch.

## 11.5. Обязательные range tests

Нужно проверить:
- итог integer;
- диапазон 0..100;
- out-of-range handling reflected in audit.

## 11.6. Workbook safety tests

Нужно проверить:
- меняется только `Новая скидка`;
- row order preserved;
- workbook remains usable;
- unsafe write scenarios fail correctly;
- formula/protected column edge cases handled safely.

## 11.7. WB outcomes tests

Нужно проверить:
- check_passed
- check_passed_with_warnings
- check_failed
- validation_failed
- completed
- completed_with_warnings
- failed

## 11.8. WB audit tests

Нужно проверить:
- required WB summary counters;
- required WB detail columns;
- detail entity_key_1 = Артикул WB when available;
- WB short result consistency.

## 11.9. Smoke-check WB

1. загрузить валидный WB набор;
2. выполнить check;
3. проверить summary and detail;
4. выполнить process;
5. скачать output;
6. убедиться, что изменилась только `Новая скидка`.

---

## 12. Контур 9. Ozon business logic

## 12.1. Обязательные input tests

Нужно проверить:
- no file -> критическая ошибка;
- more than one file -> критическая ошибка;
- invalid xlsx -> критическая ошибка;
- missing sheet `Товары и цены` -> критическая ошибка;
- missing required columns by letter -> критическая ошибка;
- impossible safe save -> критическая ошибка.

## 12.2. Обязательные column-position tests

Нужно проверить:
- J/K/L/O/P/R проверяются по буквам;
- headers 1–3 only additional check;
- нестандартная шапка 1–3 допустима, если структура сохраняется.

## 12.3. Обязательные normalization tests

Нужно проверить:
- `*` -> missing;
- empty -> missing;
- None -> missing;
- invalid numeric -> missing;
- numeric cleanup with spaces/commas.

## 12.4. Обязательные decision engine tests

Нужно проверить строго по порядку:
- missing_min_price
- no_stock
- no_boost_prices
- use_max_boost_price
- use_min_price
- below_min_price_threshold
- insufficient_ozon_input_data

И отдельно проверить, что порядок правил не нарушен.

## 12.5. Ozon write tests

Нужно проверить:
- меняются только K и L;
- K = `Да` или пусто;
- L = число или пусто;
- workbook remains uploadable;
- forced recalculation не используется.

## 12.6. Ozon outcomes tests

Нужно проверить:
- check_passed
- check_passed_with_warnings
- check_failed
- validation_failed
- completed
- completed_with_warnings
- failed

## 12.7. Ozon audit tests

Нужно проверить:
- required Ozon summary counters;
- required Ozon detail columns;
- entity_key_1 filled by OzonID/SKU/Артикул priority;
- Ozon short result consistency.

## 12.8. Smoke-check Ozon

1. загрузить валидный Ozon файл;
2. выполнить check;
3. проверить summary and detail;
4. выполнить process;
5. скачать output;
6. убедиться, что изменены только K и L.

---

## 13. Контур 10. Audit и short result consistency

## 13.1. Обязательные проверки summary audit

Нужно проверить:
- summary audit создаётся для check;
- summary audit создаётся для process;
- summary содержит required counters модуля;
- summary согласован с business_result.

## 13.2. Обязательные проверки detail audit

Нужно проверить:
- detail audit создаётся для check;
- detail audit создаётся для process;
- detail audit полностью хранится в PostgreSQL;
- required fields and payload present;
- module-specific UI columns доступны из audit without workbook reread.

## 13.3. Short result consistency

Нужно проверить:
- short_result_text заполнен после завершения run;
- short_result_text согласован с summary;
- short_result_text согласован с business_result.

## 13.4. Smoke-check

1. выполнить по одному successful и failed run для WB/Ozon;
2. сравнить business_result, summary и short_result_text;
3. убедиться, что противоречий нет.

---

## 14. Контур 11. History / logs / detail audit read-side

## 14.1. History tests

Нужно проверить:
- search по public_run_number;
- search по store name;
- search по original filename;
- search по short_result_text;
- search по username инициатора;
- required filters;
- AND combination;
- sorting;
- pagination 25/50/100;
- default new-to-old, page size 50.

## 14.2. Logs tests

Нужно проверить:
- search по message;
- search по username;
- search по public_run_number;
- filters:
  - date
  - user
  - store
  - module
  - event_type
  - severity
  - run_id/public_run_number
- AND combination;
- sorting;
- pagination 25/50/100;
- only admin access.

## 14.3. Detail audit tests

Нужно проверить:
- search по row_number/entity_key_1/entity_key_2/message/decision_reason;
- filters by severity / decision_reason / row range;
- sorting by required fields;
- server-side pagination;
- preview mode;
- full mode.

## 14.4. Access-scoped read-side tests

Нужно проверить:
- manager/manager_lead видят только свои stores in history;
- foreign run page denied;
- logs denied for non-admin;
- no-store user history hidden.

## 14.5. Smoke-check

1. создать набор runs;
2. открыть history и применить filters/search/sort/page;
3. открыть logs и применить filters/search/sort/page;
4. открыть run page и detail audit with filters.

---

## 15. Контур 12. Retention, purge, superseded, timeout reconciliation

## 15.1. Temporary purge tests

Нужно проверить:
- temp files older than 24h are purged;
- metadata cleaned/updated correctly;
- system log written;
- processing page shows empty set after purge.

## 15.2. Run file retention tests

Нужно проверить:
- expired files become unavailable;
- UI marker appears;
- download denied;
- historical run preserved.

## 15.3. Superseded result tests

Нужно проверить:
- новый successful process делает старый result unavailable;
- old run preserved;
- unavailable_reason = superseded;
- log written.

## 15.4. Timeout reconciliation tests

Нужно проверить:
- active run exceeding hard-timeout gets final failure;
- lock released;
- system log written;
- run not left forever active.

## 15.5. Anomaly tests

Нужно проверить:
- missing physical file with available metadata handled safely;
- consistency anomaly logged;
- later finished_at_utc wins in competing successful result anomaly.

## 15.6. Smoke-check

1. выполнить successful process;
2. выполнить ещё один successful process на тот же store;
3. проверить superseded old result;
4. симулировать timeout;
5. проверить final failed state and released lock.

---

## 16. Контур 13. UI smoke suite

## 16.1. Обязательные end-to-end сценарии

Минимальный e2e smoke suite должен включать:

1. login admin  
2. create user  
3. create store  
4. assign user to store  
5. login manager/manager_lead  
6. upload files  
7. run WB check  
8. run WB process  
9. run Ozon check  
10. run Ozon process  
11. open history  
12. open run page  
13. download source/result files  
14. verify logs as admin  
15. verify unavailable file behavior  
16. logout  

## 16.2. Особые UI smoke cases

Дополнительно обязательно:
- blocked user denied;
- no-store user dashboard empty state;
- archived store absent from new-run selector;
- manager no logs access;
- manager no stores access.

---

## 17. Минимальный smoke-check по этапам

## 17.1. После Этапа 1
- migrations ok
- bootstrap ok
- first admin CLI ok

## 17.2. После Этапа 2
- all required tables exist
- constraints and indexes applied

## 17.3. После Этапа 3
- login/access/store actions ok
- hidden sections ok
- no-store scenario ok

## 17.4. После Этапа 4
- temp upload ok
- active set ok
- secure download base ok

## 17.5. После Этапа 5
- async run creation ok
- polling ok
- locking ok

## 17.6. После Этапа 6
- WB check/process happy path ok
- workbook safety basic ok

## 17.7. После Этапа 7
- Ozon check/process happy path ok
- workbook safety basic ok

## 17.8. После Этапа 8
- history/logs/detail audit server-side ok

## 17.9. После Этапа 9
- full UI MVP flow ok

## 17.10. После Этапа 10
- purge/retention/superseded/timeout ok

## 17.11. После Этапа 11
- full smoke suite green

---

## 18. Что считается обязательным minimum test coverage

Минимально обязательным считается покрытие, при котором проверены:

1. Все role/access critical paths  
2. Оба processing modules: WB и Ozon  
3. Оба operation types: check и process  
4. Workbook safety for WB and Ozon  
5. Async execution + lock + timeout  
6. File lifecycle + secure download  
7. Audit/logs/history/detail audit server-side behavior  
8. Purge/retention/superseded behavior  
9. Key end-to-end user journeys  

Если хотя бы один из этих блоков не покрыт, MVP нельзя считать надёжно принятым.

---

## 19. Что должен проверить тестировщик отдельно

Тестировщик обязан отдельно проверить:

1. Нет ли участков, проверенных только вручную без воспроизводимого сценария.
2. Нет ли логики, критичной для денег/доступа/файлов, но не покрытой тестом.
3. Нет ли ложного green-status при отсутствии negative tests.
4. Нет ли client-side зависимого поведения там, где ТЗ требует server-side.
5. Нет ли расхождения между acceptance smoke и реальными архитектурными ограничениями.

---

## 20. Что должен проверить аудитор отдельно

Аудитор обязан отдельно проверить:

1. Что тестовые контуры действительно соответствуют ТЗ.
2. Что нет пропущенных критических зон:
   - WB formula
   - Ozon rule order
   - access model
   - run locking
   - workbook safety
   - detail audit in PostgreSQL
3. Что smoke suite покрывает основные пользовательские сценарии.
4. Что tests проверяют не только happy path.
5. Что maintenance scenarios не исключены из тестового объёма.

---

## 21. Что должен делать оркестратор с этим документом

Оркестратор обязан:
- не считать этап закрытым без соответствующего smoke-check;
- не считать проект готовым без полного обязательного test contour;
- выдавать тестировщику задачи по контурам, а не “проверь всё”;
- проверять, что каждый критический модуль получил свой минимум проверок.

---

## 22. Финальный критерий тестовой достаточности

Тестовая достаточность для MVP достигнута только если одновременно подтверждено:

- access model соблюдается;
- WB logic корректна;
- Ozon logic корректна;
- async execution корректен;
- files lifecycle корректен;
- history/logs/detail audit работают серверно;
- workbook contracts не нарушаются;
- purge/retention/superseded/timeout не ломают систему;
- ключевые e2e flows проходят.

---

## 23. Граница текущего документа

Данный документ фиксирует:
- обязательные тестовые контуры;
- smoke-checks;
- минимально обязательный coverage для приёмки MVP.

На этом базовый комплект проектной документации завершён.

Следующий отдельный документ нужен только в одном случае:
- если требуется зафиксировать реально критические пробелы ТЗ, которые невозможно закрыть архитектурой без самостоятельного домысливания.

Имя такого документа:
- `17_OPEN_ARCHITECTURAL_QUESTIONS.md`

Если пробелов нет или они не критичны, отдельный документ `17_OPEN_ARCHITECTURAL_QUESTIONS.md` можно не создавать.