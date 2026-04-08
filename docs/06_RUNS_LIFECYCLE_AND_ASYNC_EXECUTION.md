# 06_RUNS_LIFECYCLE_AND_ASYNC_EXECUTION.md

## 1. Назначение документа

Документ фиксирует:
- модель сущности run как центрального объекта исполнения;
- жизненный цикл операций check и process;
- допустимые состояния lifecycle_status;
- допустимые business_result;
- правила автоматической валидации перед process;
- асинхронную модель выполнения через run + polling;
- правила блокировок по store_id + module_code;
- правила завершения run;
- правила conflict handling;
- правила timeout handling;
- правила статусов и отображения в UI.

Документ не описывает:
- детальную БД-схему;
- логику расчёта WB;
- логику обработки Ozon;
- маршруты UI;
- файловое хранение как отдельную тему.

---

## 2. Краткий итог

Каждая операция check и process существует только как отдельный run.
Check и process никогда не объединяются в одну запись истории.

Архитектурная модель исполнения следующая:
1. HTTP-запрос принимает команду.
2. Система проверяет доступ и базовые ограничения.
3. Система создаёт run в статусе `created`.
4. Система ставит run на асинхронное выполнение.
5. Исполнитель переводит run по допустимому lifecycle path.
6. UI получает статус через polling с интервалом 2 секунды.
7. После завершения пользователь получает:
   - lifecycle_status;
   - business_result;
   - short_result_text;
   - summary audit;
   - detail audit;
   - result file, если это успешный process.

Одновременно не допускаются два активных run по одной паре:
- store_id
- module_code

Блокировка обязательна.
Process всегда включает автоматическую валидацию, но эта валидация не создаёт отдельный run.

---

## 3. Роль сущности run в системе

Run является центральной сущностью исполнения и связывает между собой:
- store;
- user-инициатора;
- operation_type;
- lifecycle_status;
- business_result;
- input files;
- output file;
- summary audit;
- detail audit;
- system logs.

Каждый run должен быть:
- однозначно идентифицируемым;
- трассируемым;
- воспроизводимым;
- исторически сохраняемым;
- пригодным для повторного открытия из history.

Run не является:
- временным набором файлов;
- фоновым job without history;
- технической записью очереди без пользовательского значения.

Каждый run — это пользовательски значимая операция.

---

## 4. Operation types

Закрытый набор operation_type:
- check
- process

Запрещено:
- добавлять новые operation_type;
- трактовать auto-validation process как отдельный operation_type;
- трактовать process как разновидность check;
- объединять check/process в один тип с параметром dry_run.

---

## 5. Lifecycle model для check

## 5.1. Допустимые lifecycle_status для check

Закрытый набор:
- created
- checking
- completed
- failed

## 5.2. Допустимые business_result для check

Закрытый набор:
- check_passed
- check_passed_with_warnings
- check_failed

## 5.3. Смысл статусов

### `created`
Run создан, принят системой, но фактическое исполнение ещё не начато worker execution path.

### `checking`
Идёт выполнение check:
- читаются файлы;
- валидируется структура;
- выполняется нормализация;
- считается прогнозируемый результат;
- формируется аудит;
- output file не создаётся.

### `completed`
Check завершён прикладным образом.
Business result должен быть одним из:
- check_passed
- check_passed_with_warnings

### `failed`
Check завершён неуспешно.
Business result должен быть:
- check_failed

---

## 6. Lifecycle model для process

## 6.1. Допустимые lifecycle_status для process

Закрытый набор:
- created
- validating
- processing
- completed
- failed

## 6.2. Допустимые business_result для process

Закрытый набор:
- validation_failed
- completed
- completed_with_warnings
- failed

## 6.3. Смысл статусов

### `created`
Run создан и принят системой, но execution path ещё не начат.

### `validating`
Идёт обязательная автоматическая валидация перед process.
Это внутренняя фаза того же process-run.

### `processing`
Валидация process успешно пройдена, выполняется прикладная обработка:
- расчёт/изменение workbook;
- формирование результата;
- формирование summary/detail audit;
- сохранение output file.

### `completed`
Process завершён прикладным образом.
Business result должен быть:
- completed
- completed_with_warnings

### `failed`
Process завершён неуспешно.
Business result должен быть:
- validation_failed
- failed

---

## 7. Business_result semantics

## 7.1. Для check

### `check_passed`
Check завершился успешно без предупреждений, блокирующих качество результата.

### `check_passed_with_warnings`
Check завершился успешно, но есть предупреждения:
- по строкам;
- по входным данным;
- по частичным сценариям.

### `check_failed`
Check завершился неуспешно.
Причина — критическая ошибка сценария, не позволяющая считать запуск успешным.

## 7.2. Для process

### `validation_failed`
Автоматическая валидация перед process завершилась неуспешно.
Обработка файла не должна переходить в processing-path.

### `completed`
Process полностью завершён успешно без предупреждений, влияющих на итоговый характер результата.

### `completed_with_warnings`
Process завершён успешно, итоговый файл сформирован, но были предупреждения по строкам или частичным данным.

### `failed`
Process не смог завершиться успешно по причине системной или прикладной ошибки после этапа принятия run.

---

## 8. Допустимые переходы статусов

## 8.1. Check transitions

Допустимые переходы:

- `created -> checking`
- `checking -> completed`
- `checking -> failed`

Запрещены:
- `created -> completed` без execution path
- `created -> failed` без фиксации старта исполнения, кроме аварийного восстановительного сценария reconciliation
- любые возвраты назад
- переходы check в `validating` или `processing`

## 8.2. Process transitions

Допустимые переходы:

- `created -> validating`
- `validating -> processing`
- `validating -> failed`
- `processing -> completed`
- `processing -> failed`

Запрещены:
- `created -> processing` без validating
- `created -> completed`
- `validating -> completed`
- любые возвраты назад
- любые переходы process в `checking`

## 8.3. Финальные состояния

Финальными считаются:
- для check:
  - completed
  - failed
- для process:
  - completed
  - failed

После достижения финального состояния:
- polling должен прекращаться;
- run больше не должен менять lifecycle_status;
- business_result должен быть заполнен;
- finished_at_utc должен быть заполнен.

---

## 9. Nullability business_result по стадиям

До финального состояния:
- `business_result IS NULL`

После финального состояния:
- `business_result IS NOT NULL`

Это обязательный инвариант для:
- check
- process

Соответственно:
- `created`, `checking`, `validating`, `processing` -> `business_result = NULL`
- `completed`, `failed` -> `business_result != NULL`

---

## 10. Обязательная модель process auto-validation

## 10.1. Общий принцип

Process может запускаться без предварительного ручного check.
Но перед process всегда выполняется обязательная автоматическая валидация.

## 10.2. Архитектурный статус auto-validation

Auto-validation:
- является обязательной фазой process-run;
- отражается как `lifecycle_status = validating`;
- не создаёт отдельный run;
- не создаёт отдельную запись history;
- отображается внутри карточки process-run как вложенный внутренний этап.

## 10.3. Что делает auto-validation

Auto-validation должна:
- валидировать входной набор файлов;
- проверить обязательную структуру и допустимость операции;
- выполнить те проверки, которые необходимы до начала фактической записи output;
- завершить process как `validation_failed`, если безопасная обработка невозможна.

## 10.4. Что auto-validation не делает

Auto-validation не должна:
- создавать второй history record;
- подменять собой отдельный пользовательский check;
- менять operation_type;
- публиковаться как отдельный run.

## 10.5. Флаг `validation_was_auto_before_process`

Для process-run:
- должен быть `true`, если автоматическая валидация реально выполнялась как часть process
- по ТЗ для process это обязательное поведение, следовательно, на завершённом process-run ожидается `validation_was_auto_before_process = true`

Для check-run:
- всегда `false`

---

## 11. Модель run creation

## 11.1. Что делает HTTP на старте run

При старте check/process HTTP/application layer должен:
1. проверить авторизацию;
2. проверить, что пользователь не blocked;
3. проверить access rights;
4. проверить store status;
5. проверить module/store consistency;
6. проверить состав активного временного набора;
7. проверить лимиты файлов;
8. проверить active run conflict;
9. создать run;
10. записать стартовое событие в system_logs;
11. передать run в асинхронное исполнение;
12. вернуть UI ответ “принято в обработку”.

## 11.2. Что HTTP не должен делать

HTTP-слой не должен:
- выполнять полную обработку Excel;
- ждать финального результата;
- формировать detail audit;
- делать долгую синхронную работу вместо background execution.

---

## 12. Active run semantics

## 12.1. Что считается активным run

Активным считается run, который ещё не достиг финального состояния.

Для check активные состояния:
- created
- checking

Для process активные состояния:
- created
- validating
- processing

## 12.2. Что считается неактивным run

Неактивным считается run, находящийся в:
- completed
- failed

## 12.3. Зачем нужен признак активности

Он используется для:
- блокировки параллельных операций;
- предотвращения конфликта по store+module;
- корректного UI состояния;
- run scheduling;
- reconciliation при сбоях.

---

## 13. Блокировки и конкурентность

## 13.1. Уровень блокировки

Блокировка устанавливается на пару:
- store_id
- module_code

Это обязательное правило ТЗ.

## 13.2. Запрещённые параллельные сценарии

Запрещено одновременно:
- два process по одной паре store+module;
- check и process по одной паре store+module;
- два любых активных run по одной паре store+module.

Итоговое обязательное правило:
- одновременно не допускаются два активных run по одной паре store + module.

## 13.3. Разрешённые параллельные сценарии

Разрешены:
- операции по разным магазинам;
- операции по разным парам store+module, если это не один и тот же магазин.

Так как marketplace жёстко определяет модуль магазина:
- для WB store возможен только module_code=wb
- для Ozon store возможен только module_code=ozon

Практически это означает сериализацию по самому магазину.

## 13.4. Active run conflict

Если найден другой активный run по той же паре store+module:
- новый run не должен быть принят к исполнению;
- интерфейсу должна возвращаться структурированная ошибка:
  - `error_code = active_run_conflict`

## 13.5. Архитектурное место проверки конфликта

Проверка обязательна:
1. до создания/принятия нового run;
2. при захвате execution lock перед фактическим началом выполнения;
3. в reconciliation logic при аномальных сценариях.

Это нужно для защиты от гонок между параллельными HTTP-запросами.

---

## 14. Модель асинхронного выполнения

## 14.1. Общая схема

Асинхронная модель состоит из трёх уровней:

1. acceptance layer  
   - принимает запрос;
   - создаёт run;
   - отдаёт быстрый ответ пользователю.

2. execution layer  
   - выполняет check/process;
   - переводит статусы;
   - пишет audits/files/logs.

3. status observation layer  
   - UI polling;
   - чтение статуса run;
   - обновление страницы.

## 14.2. Асинхронный контракт

Требования ТЗ:
- операции check и process выполняются асинхронно;
- HTTP-запрос только создаёт run и ставит задачу на выполнение;
- результат возвращается через polling статуса.

Следовательно, любая реализация, где HTTP ждёт полное выполнение операции, считается нарушением ТЗ.

## 14.3. Минимальный acceptance response

После успешного старта run UI должен получить как минимум:
- идентификатор run для дальнейшего polling;
- текущий lifecycle_status;
- подтверждение, что запуск принят в обработку.

---

## 15. Polling contract

## 15.1. Обязательность polling

Polling обязателен.
UI не должен ждать финальный ответ в исходном POST/GET.

## 15.2. Интервал polling

Фиксированный интервал:
- 2 секунды

## 15.3. Когда polling продолжается

### Для check
Пока lifecycle_status не равен:
- completed
- failed

### Для process
Пока lifecycle_status не равен:
- completed
- failed

## 15.4. Когда polling прекращается

Polling прекращается после получения одного из финальных состояний:
- completed
- failed

## 15.5. Что UI обязан показывать при polling

UI обязан показывать:
- текущий lifecycle_status;
- итоговый business_result после завершения;
- short_result_text после завершения.

Дополнительно допускается:
- вложенное отображение auto-validation для process;
- блок summary audit;
- preview detail audit, если данные уже готовы на финальном экране.

---

## 16. Временные требования и таймауты

## 16.1. Целевое время ответа API на создание run

- до 5 секунд

Это означает:
- acceptance path должен быть быстрым;
- тяжёлая обработка не должна выполняться в HTTP синхронно.

## 16.2. Целевое время выполнения check

- до 60 секунд

## 16.3. Целевое время выполнения process

- до 180 секунд

## 16.4. Hard timeout backend task

Для check:
- 300 секунд

Для process:
- 600 секунд

## 16.5. Последствия hard timeout

Если backend execution превысил hard timeout:
- run должен быть завершён в финальное состояние `failed`
- business_result:
  - для check -> `check_failed`
  - для process -> `failed`
- должен быть записан system log о системной ошибке / timeout failure
- lock должен быть снят
- частично созданные временные технические артефакты не должны оставлять run в неопределённом состоянии

---

## 17. Правила завершения check

## 17.1. Успешное завершение

Check завершает run как:
- `lifecycle_status = completed`
- `business_result = check_passed`  
или
- `lifecycle_status = completed`
- `business_result = check_passed_with_warnings`

Обязательно должны существовать:
- short_result_text
- run_summary_audit
- run_detail_audit rows

Не должно существовать:
- result output file
- result_file_id

## 17.2. Неуспешное завершение

Check завершает run как:
- `lifecycle_status = failed`
- `business_result = check_failed`

Обязательно:
- краткая причина в short_result_text
- system log события завершения с ошибкой
- аудит должен быть сформирован настолько полно, насколько это возможно в рамках достигнутой стадии

## 17.3. Граница check

Check не записывает изменения в result workbook.
Даже если check моделирует итог, это только аудиторная и проверочная операция.

---

## 18. Правила завершения process

## 18.1. Validation failed

Если auto-validation process не пройдена:
- `lifecycle_status = failed`
- `business_result = validation_failed`
- `validation_was_auto_before_process = true`
- output file не создаётся
- result_file_id = NULL
- short_result_text содержит короткую причину
- summary/detail audit должны объяснять причину неуспеха настолько, насколько это возможно

## 18.2. Successful completion

Если process успешно завершён:
- `lifecycle_status = completed`
- `business_result = completed`  
или
- `lifecycle_status = completed`
- `business_result = completed_with_warnings`

Обязательно:
- output file создан и сохранён
- result_file_id заполнен
- summary audit записан
- detail audit записан
- short_result_text заполнен

## 18.3. Failed after processing start

Если ошибка произошла уже после стадии validating и/или во время processing:
- `lifecycle_status = failed`
- `business_result = failed`
- output file не должен считаться доступным успешным результатом
- run должен завершиться согласованно
- lock должен быть снят
- system log обязателен

---

## 19. Rules for short_result_text

## 19.1. Назначение

`short_result_text` — это короткая человекочитаемая строка для:
- списка запусков;
- dashboard;
- карточки run;
- результата polling после завершения.

## 19.2. Обязательность

После завершения run:
- `short_result_text` должен быть заполнен

Во время активного выполнения:
- может быть NULL

## 19.3. Содержание

Для успешных run:
- короткая итоговая сводка по ТЗ модуля

Для неуспешных run:
- короткая причина ошибки

---

## 20. Input set signature и недействительность старого check

## 20.1. Назначение input_set_signature

`input_set_signature` фиксирует конкретный активный набор входных файлов, по которому запущен run.

Он используется для:
- воспроизводимости run;
- проверки актуальности предыдущего check;
- исторического сопоставления с конкретным набором файлов.

## 20.2. Изменение состава файлов

Любое из перечисленного делает предыдущий check недействительным:
- удаление файла;
- добавление файла;
- замена файла;
- повторная загрузка файла с тем же именем, но иным содержимым;
- повторная загрузка файла с тем же содержимым, но иным именем;
- повторная загрузка файла с тем же именем и тем же содержимым, если создан новый временный объект.

## 20.3. Поведение process при устаревшем check

Если пользователь запустил process по набору, для которого предыдущий ручной check уже неактуален:
- отдельного ручного подтверждения не требуется;
- система автоматически выполняет новую встроенную validation;
- при неуспешной validation process завершается как `validation_failed`.

Важно:
- это не требует существования предыдущего check-run;
- process всегда самодостаточен в части обязательной auto-validation.

---

## 21. Superseded result handling

## 21.1. Общий принцип

Повторный process по тем же или иным файлам разрешён всегда.
Новый успешный process по store+module может сделать предыдущий успешный result устаревшим.

## 21.2. Что происходит при новом успешном process

Если появился новый успешный process result по той же паре store+module:
- старый output file помечается как недоступный;
- `unavailable_reason = superseded`
- historical run сохраняется
- событие пишется в system_logs

## 21.3. Что считается текущим успешным результатом

При корректной работе, так как нет двух параллельных активных run по одной паре store+module:
- текущим успешным результатом является последний успешный process run этой пары

Если произошла техническая аномалия и два успешных process всё же конкурируют:
- текущим успешным считается тот, у которого `later finished_at_utc`
- второй результат должен быть помечен как superseded
- в system_logs пишется ошибка согласованности

---

## 22. Error contract для run-related сценариев

Система должна возвращать структурированную ошибку с полями:
- `error_code`
- `error_message`
- `details` (nullable)

## 22.1. Обязательные run-related error_code

- access_denied
- validation_failed
- system_error
- archived_store_forbidden
- permission_denied
- file_limit_exceeded
- active_run_conflict

## 22.2. Когда применяются

### `access_denied`
Нет права на store-bound объект или действие.

### `permission_denied`
Нет нужного permission при формально допустимой роли.

### `archived_store_forbidden`
Попытка нового запуска по archived store.

### `file_limit_exceeded`
Нарушены лимиты по количеству/размеру файлов.

### `active_run_conflict`
Есть другой активный run по store+module.

### `validation_failed`
Не пройдена обязательная проверка входных данных или структуры.

### `system_error`
Внутренняя системная ошибка исполнения.

---

## 23. Execution orchestration phases

Ниже фиксируется канонический execution path.

## 23.1. Check execution phases

1. Принятие run
2. Захват lock
3. Переход `created -> checking`
4. Чтение активного набора файлов
5. Копирование input files в run/input
6. Выполнение check logic модуля
7. Формирование summary audit
8. Формирование detail audit
9. Формирование short_result_text
10. Запись финального статуса
11. Запись system log о завершении
12. Освобождение lock

## 23.2. Process execution phases

1. Принятие run
2. Захват lock
3. Переход `created -> validating`
4. Чтение активного набора файлов
5. Копирование input files в run/input
6. Выполнение auto-validation
7. Если validation failed:
   - сформировать audit/short result
   - завершить run как failed/validation_failed
   - записать logs
   - освободить lock
8. Если validation passed:
   - переход `validating -> processing`
9. Выполнение process logic
10. Сохранение output file
11. Формирование summary audit
12. Формирование detail audit
13. Формирование short_result_text
14. Завершение run
15. Superseded handling для старого успешного результата
16. Запись system log о завершении
17. Освобождение lock

---

## 24. Требования к устойчивости исполнения

## 24.1. Crash safety

Если процесс исполнения оборвался аварийно:
- run не должен оставаться бесконечно в активном состоянии;
- должен существовать механизм reconciliation / timeout finalization;
- lock не должен удерживаться бесконечно;
- UI не должен бесконечно ждать финальный статус без возможности завершения.

## 24.2. Idempotency boundary

HTTP-запрос старта run не должен автоматически выполнять повтор одного и того же run при сетевых повторах без явного нового действия пользователя.

Но повторный отдельный process по тем же файлам допустим как новый самостоятельный run.

## 24.3. No silent success

Нельзя считать run успешно завершённым, если:
- status дошёл до completed,
но
- audit не записан,
или
- process result file не сохранён при успешном process,
или
- result_file_id не согласован с реальным output file.

---

## 25. Что должно отображаться в UI по run

## 25.1. Во время выполнения

UI должен отображать:
- operation_type
- lifecycle_status
- store
- module
- initiated_by
- started time
- для process — фазу validating/processing через lifecycle_status

## 25.2. После завершения

UI должен отображать:
- lifecycle_status
- business_result
- short_result_text
- summary audit
- preview detail audit
- ссылку на полную страницу аудита
- result file download, если есть доступный output file
- состояние input files/result files

## 25.3. Для failed/validation_failed

UI должен отображать:
- финальный failure state
- короткую причину
- аудит, если он сформирован
- отсутствие result file как нормальное следствие failure path

---

## 26. Обязательные системные события, связанные с runs

Для run lifecycle обязаны логироваться как минимум:

- check_started
- check_finished
- process_started
- process_finished
- process_finished_with_warnings
- process_error
- old_result_removed_on_new_success
- system_error

При необходимости допускается более подробная внутренняя детализация логов, но без изменения обязательного набора.

---

## 27. Что должно быть проверено тестами

## 27.1. Lifecycle tests

Нужно проверить:
- корректные transitions для check
- корректные transitions для process
- запрет недопустимых transitions
- business_result nullability до и после завершения

## 27.2. Conflict tests

Нужно проверить:
- запрет второго активного run на тот же store+module
- запрет check во время process
- запрет process во время check
- разрешение запусков по разным stores

## 27.3. Process validation tests

Нужно проверить:
- process всегда входит в validating
- validating failure даёт `failed + validation_failed`
- успешный validating переводит в processing
- auto-validation не создаёт отдельный run

## 27.4. Timeout tests

Нужно проверить:
- hard-timeout для check
- hard-timeout для process
- корректный failure status
- снятие lock
- запись system log

## 27.5. Polling tests

Нужно проверить:
- polling возвращает промежуточные статусы
- polling прекращается на completed/failed
- UI получает business_result после завершения

## 27.6. Superseded result tests

Нужно проверить:
- новый успешный process делает старый result unavailable
- historical run сохраняется
- событие логируется
- later finished_at_utc побеждает при аномальном конфликте

---

## 28. Что должен проверить аудитор

Аудитор обязан отдельно проверить:

1. Что check и process существуют как отдельные runs.
2. Что process всегда проходит через `validating`.
3. Что auto-validation не создаёт отдельный history record.
4. Что нет недопустимых lifecycle transitions.
5. Что `business_result` не заполняется до финального состояния.
6. Что output file не создаётся для check.
7. Что successful process без output file невозможен.
8. Что active run conflict реально блокирует параллельные операции.
9. Что lock снимается при success, failure и timeout.
10. Что superseded result logic реализована.
11. Что polling соответствует контракту 2 секунды и финальным состояниям.
12. Что archived store не допускается к новым runs.
13. Что structured error contract соблюдается.
14. Что HTTP не выполняет долгую синхронную обработку вместо асинхронной модели.

---

## 29. Граница текущего документа

Данный документ фиксирует:
- run model;
- lifecycle;
- async execution;
- polling;
- locking;
- timeout handling.

Следующий документ должен раскрыть:
- временные файлы;
- input/output files per run;
- storage paths;
- retention;
- deletion rules;
- superseded file handling;
- UI-поведение при недоступных файлах.

Имя следующего файла:
- `07_FILE_STORAGE_AND_RETENTION.md`