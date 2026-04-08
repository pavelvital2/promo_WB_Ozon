# 08_AUDIT_AND_LOGGING_ARCHITECTURE.md

## 1. Назначение документа

Документ фиксирует:
- архитектуру run-аудита;
- архитектуру системного логирования;
- различие между summary audit, detail audit и system logs;
- обязательные правила хранения и трассируемости;
- правила серверного поиска, фильтрации, сортировки и пагинации;
- обязательные поля и семантику audit/log records;
- требования к отображению аудита и логов в UI;
- тестовые и аудиторские инварианты по observability и explainability.

Документ не описывает:
- жизненный цикл runs как отдельную тему;
- файловое хранение как отдельную тему;
- UI-маршруты;
- бизнес-логику WB/Ozon beyond audit/log outputs.

---

## 2. Краткий итог

В системе существуют два разных контура наблюдаемости:

1. run audit  
2. system logs  

Они не взаимозаменяемы и не должны смешиваться.

Run audit делится на:
- summary audit;
- detail audit.

System logs фиксируют:
- системные и пользовательские события;
- события запуска/завершения;
- ошибки;
- действия управления пользователями, магазинами и файлами.

Run audit фиксирует:
- результат конкретной операции check/process;
- агрегированный итог;
- построчную детализацию;
- причины решений и предупреждений;
- объяснимость результата.

Обязательные архитектурные правила:
- и check, и process всегда формируют summary audit;
- и check, и process всегда формируют detail audit;
- detail audit полностью хранится в PostgreSQL;
- history, logs и detail audit работают только через server-side search/filter/sort/pagination;
- system logs и run audit должны иметь независимые read-side сценарии;
- run page должна опираться на audit, а не на system logs;
- logs page должна опираться на system_logs, а не на audit rows.

---

## 3. Общая модель observability

## 3.1. Два независимых контура

### Контур 1. Run audit
Отвечает на вопрос:
- что именно произошло в рамках конкретного check/process run;
- почему строка была обработана так, а не иначе;
- каков итоговый агрегированный результат;
- какие warning/error были в доменной обработке.

### Контур 2. System logs
Отвечает на вопрос:
- какие события происходили в системе;
- кто выполнил действие;
- когда стартовал/завершился run;
- какие ошибки возникали на системном уровне;
- какие административные и файловые события произошли.

## 3.2. Почему контуры нельзя смешивать

Если смешать их:
- detail audit перестанет быть понятным как объяснение бизнес-результата;
- system logs будут перегружены построчными данными;
- history/run page и logs page потеряют смысловое разделение;
- серверный поиск и пагинация станут неуправляемыми;
- реализация нарушит ТЗ о раздельном хранении и назначении сущностей.

---

## 4. Архитектура run audit

## 4.1. Состав run audit

Для каждого run обязательно существуют два уровня аудита:

1. `run_summary_audit`
2. `run_detail_audit`

Они должны формироваться и для:
- check
- process

## 4.2. Назначение summary audit

Summary audit нужен для:
- короткого агрегированного понимания результата;
- отображения ключевых итогов run;
- построения summary block на processing page и run page;
- объяснения результата без просмотра всех detail rows.

## 4.3. Назначение detail audit

Detail audit нужен для:
- полного построчного объяснения результата;
- диагностики ошибок строк;
- диагностики warning-level проблем;
- просмотра причин решений по строкам;
- server-side просмотра больших аудиторных наборов.

## 4.4. Общий принцип одинакового хранения check/process audit

Check-аудит и process-аудит должны храниться одинаковым способом:
- summary audit в `run_summary_audit`
- detail audit rows в `run_detail_audit`

Запрещено:
- хранить check audit в одном формате, а process audit в другом принципиально отличающемся механизме;
- хранить detail audit только во временных JSON-файлах;
- делать check audit “облегчённым” так, что он перестаёт объяснять результат.

---

## 5. Архитектура summary audit

## 5.1. Хранилище

Summary audit хранится в таблице:
- `run_summary_audit`

Один run имеет:
- ровно один summary audit после завершения операции

## 5.2. Формат хранения

Summary audit хранится в:
- `audit_json` типа JSON/JSONB

Это допустимо, потому что:
- набор summary-показателей различается между WB и Ozon;
- ТЗ требует единый способ хранения, но не требует отдельной нормализованной таблицы под каждый показатель;
- summary нужен как агрегированная структура, пригодная для рендера и дальнейшего расширения без изменения бизнес-сущностей.

## 5.3. Обязательные свойства summary audit

Summary audit должен быть:
- воспроизводимым;
- человекообъяснимым;
- пригодным для рендера без пересчёта исходных workbook;
- связанным с конкретным run;
- полным для данного operation_type и module.

## 5.4. Структура summary audit на верхнем уровне

Независимо от модуля, верхний уровень summary audit должен содержать как минимум логические блоки:

- run context
- module context
- operation context
- totals / counters
- warnings / errors summary
- result interpretation block

Точная вложенная структура внутри `audit_json` может быть модульной, но смысловые блоки должны быть стабильны.

---

## 6. Архитектура detail audit

## 6.1. Хранилище

Detail audit полностью хранится в таблице:
- `run_detail_audit`

Это обязательное требование ТЗ.

## 6.2. Почему detail audit хранится построчно

Построчное хранение нужно, потому что:
- аудит может содержать до 200 000 строк на run;
- нужен server-side search/filter/sort/pagination;
- нужен выборочный доступ к строкам;
- нужен preview mode и full detail mode;
- нужен быстрый поиск по row_number/entity/message/reason.

## 6.3. Поля detail audit

Обязательные поля:
- row_number
- entity_key_1
- entity_key_2
- severity
- decision_reason
- message
- audit_payload_json

Этого набора достаточно, чтобы:
- индексировать основные колонки;
- хранить общий скелет аудита;
- держать модуль-специфичные детали в `audit_payload_json`.

## 6.4. Назначение `audit_payload_json`

`audit_payload_json` нужен для:
- хранения модуль-специфичных полей WB и Ozon;
- формирования таблицы detail audit для конкретного модуля;
- объяснения расчётных значений без раздувания общей таблицы десятками marketplace-specific колонок.

Это не нарушает ТЗ, потому что:
- обязательные общие поля detail audit сохранены явно;
- detail audit остаётся полностью в PostgreSQL;
- required UI columns могут извлекаться из payload для конкретного модуля.

---

## 7. Severity model

## 7.1. Закрытый набор severity для detail audit

- info
- warning
- error

## 7.2. Семантика severity

### `info`
Строка обработана без ошибки, запись используется для объяснения решения или обычного результата.

### `warning`
Есть отклонение, не блокирующее run целиком, но влияющее на строку, файл или качество результата.

### `error`
Есть ошибка уровня строки или записи, которая делает строку невалидной или отражает критичный дефект в контексте конкретной строки/объекта.

## 7.3. Важное различие

`error` в detail audit не обязательно означает, что весь run завершится как failed.
Например:
- строка может быть пропущена как ошибочная;
- сам run может завершиться completed_with_warnings или check_passed_with_warnings.

Глобальный исход run определяется:
- business_result;
- summary interpretation;
а не единичной detail row.

---

## 8. Decision reason model

## 8.1. Назначение decision_reason

`decision_reason` нужен для:
- краткой классификации причины обработки строки;
- фильтрации detail audit;
- группировки однотипных решений;
- объяснения поведения без чтения длинного message.

## 8.2. Глобального справочника в БД не требуется

ТЗ не требует отдельной сущности reason dictionary.
Следовательно:
- `decision_reason` хранится строкой;
- конкретные reason-коды стандартизируются на уровне модулей WB/Ozon и документации модулей;
- search/filter по `decision_reason` работает серверно.

## 8.3. Использование в фильтрах

Detail audit должен поддерживать фильтр по:
- `decision_reason`

Это обязательное требование ТЗ.

---

## 9. Message model

## 9.1. Назначение `message`

`message` — это обязательное человекочитаемое пояснение по detail row или system log row.

## 9.2. Требования к detail audit message

Message detail audit должен:
- быть понятен человеку;
- описывать конкретное отклонение или результат;
- быть самодостаточен в пределах строки;
- не требовать чтения исходного кода для понимания причины.

## 9.3. Требования к system log message

System log message должен:
- описывать событие;
- указывать его смысл;
- быть пригодным для поиска и диагностики;
- не дублировать detail audit буквально.

---

## 10. Entity keys в detail audit

## 10.1. Назначение entity keys

`entity_key_1` и `entity_key_2` нужны для:
- поиска и фильтрации;
- связи detail row с конкретной бизнес-сущностью строки;
- удобного поиска по артикулу / идентификатору.

## 10.2. Обязательные правила для WB

Для Wildberries:
- в `entity_key_1` должен использоваться Артикул WB, если он есть.

## 10.3. Обязательные правила для Ozon

Для Ozon:
- в `entity_key_1` должен использоваться OzonID/SKU/Артикул в приоритетном порядке доступности.

## 10.4. Entity_key_2

`entity_key_2` остаётся дополнительным полем для вторичного идентификатора или вспомогательной привязки, если это требуется модульному payload.

ТЗ не задаёт жёсткого обязательного наполнения для `entity_key_2`, поэтому:
- оно не должно становиться обязательным во всех строках;
- но должно использоваться последовательно там, где оно помогает explainability.

---

## 11. Модульные требования к detail audit колонкам

## 11.1. Wildberries

Для WB обязательны колонки UI:
- row_number
- Артикул WB
- Текущая цена
- min_discount
- max_plan_price
- calculated_discount
- final_discount_pre_threshold
- final_discount
- severity
- decision_reason
- message

Следствие для архитектуры:
- эти поля должны быть доступны для рендера detail table из комбинации:
  - общих колонок `run_detail_audit`
  - `audit_payload_json`

## 11.2. Ozon

Для Ozon обязательны колонки UI:
- row_number
- OzonID/SKU/Артикул
- min_price
- min_boost
- max_boost
- stock
- final_participation
- final_promo_price
- severity
- decision_reason
- message

Следствие:
- payload Ozon detail audit должен стабильно хранить эти поля в пригодном для рендера виде.

## 11.3. Архитектурное правило

UI-таблица detail audit не должна требовать повторного чтения исходного workbook для вывода обязательных колонок.
Все нужные данные должны уже быть сохранены в audit layer.

---

## 12. Preview detail audit и full detail audit

## 12.1. Preview mode

На processing page должен отображаться:
- краткий предварительный просмотр detail audit

Preview mode:
- не заменяет полный detail audit;
- использует те же данные `run_detail_audit`;
- должен быть ограниченным по объёму;
- не должен загружать весь набор detail rows.

## 12.2. Full detail mode

Полная страница run/detail audit должна:
- использовать server-side pagination;
- использовать server-side search/filter/sort;
- работать по полному набору detail rows данного run.

## 12.3. Один и тот же экран run/detail

ТЗ фиксирует, что:
- карточка запуска и страница полного детального аудита — это один и тот же экран.

Следовательно, архитектура должна позволять на одном экране:
- summary block;
- run metadata;
- file actions;
- preview/full detail table behavior;
- итоговый статус.

---

## 13. Server-side search/filter/sort/page для detail audit

## 13.1. Обязательность

Все операции над detail audit должны выполняться серверно.
Загрузка всего audit в клиент:
- запрещена.

## 13.2. Обязательный поиск

Поиск обязателен по:
- row_number
- entity_key_1
- entity_key_2
- message
- decision_reason

## 13.3. Обязательные фильтры

Фильтры обязаны поддерживать:
- severity
- decision_reason
- диапазон row_number

Дополнительно допускается:
- фильтр по наличию/отсутствию ключевых идентификаторов

## 13.4. Обязательная сортировка

Сортировка обязательна по:
- row_number
- severity
- decision_reason
- entity_key_1

## 13.5. Пагинация

Пагинация detail audit:
- обязательна;
- должна быть серверной;
- должна быть рассчитана на большой объём данных.

Размеры страницы могут быть спроектированы проектно, но без нарушения принципа server-side pagination.

---

## 14. Архитектура system logs

## 14.1. Назначение system logs

System logs предназначены для фиксации событий системы и действий пользователя.

Они отвечают на вопросы:
- кто выполнил действие;
- когда оно произошло;
- к какому store/run относится событие;
- каков тип события;
- какова его severity;
- каково текстовое описание события;
- есть ли дополнительный payload.

## 14.2. Что system logs не должны делать

System logs не должны:
- хранить полный построчный аудит обработки;
- заменять detail audit;
- использоваться как основной источник таблицы run detail;
- становиться единственным источником объяснения результата run.

---

## 15. Обязательные system events

Минимальный обязательный набор событий:

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

Допускается внутренняя дополнительная детализация event_type, если не ломается обязательный набор.

---

## 16. Severity model для system logs

## 16.1. Закрытый набор

- info
- warning
- error

## 16.2. Семантика

### `info`
Обычное штатное событие:
- login success
- logout
- file upload
- normal completion

### `warning`
Событие, указывающее на нежелательное, но не катастрофическое состояние:
- completion with warnings
- fallback operational notices, если это системно значимо
- cleanup notices, требующие внимания

### `error`
Системная или прикладная ошибка:
- process_error
- system_error
- consistency anomaly
- timeout failure
- storage inconsistency

---

## 17. Payload model для system logs

## 17.1. Назначение `payload_json`

`payload_json` в system_logs нужен для:
- хранения структурированных технических деталей события;
- диагностики;
- связи с file/run/store specifics;
- записи служебной информации без раздувания основных колонок.

## 17.2. Ограничения

Payload:
- не должен заменять message;
- не должен быть единственным способом понять событие;
- не должен использоваться как скрытое место для несогласованных доменных данных.

Message остаётся основным человекочитаемым описанием.
Payload — дополнительный технический контекст.

---

## 18. Трассируемость run

## 18.1. Цепочка трассируемости

Для любого run должна восстанавливаться полная цепочка:

1. кто инициировал run  
2. для какого store  
3. какого operation_type  
4. с каким lifecycle outcome  
5. с каким business_result  
6. с какими input files  
7. с каким output file, если он есть  
8. с каким summary audit  
9. с каким detail audit  
10. с какими system log events  

## 18.2. Обязательное правило

Run считается трассируемым, если по нему можно открыть:
- summary audit;
- detail audit;
- file metadata;
- связанные log events.

Даже если файл уже недоступен, metadata и history должны сохраняться.

---

## 19. Разделение read-side сценариев

## 19.1. Run page read-side

Run page должна читать данные из:
- runs
- run_summary_audit
- run_detail_audit
- run_files

Дополнительно допускается чтение system_logs для связанных служебных событий, но:
- logs не должны заменять audit blocks;
- основной источник страницы — run/audit/file data.

## 19.2. Logs page read-side

Logs page должна читать данные из:
- system_logs
- users
- stores
- runs

Она не должна использовать detail audit как основной источник.

## 19.3. History page read-side

History page должна читать:
- runs
- stores
- users
- file availability metadata

Она не должна пытаться собирать историю из system_logs.

---

## 20. Server-side search/filter/sort/page для logs

## 20.1. Обязательность

Для logs page обязательны:
- server-side search
- server-side filters
- server-side sorting
- server-side pagination

## 20.2. Обязательный поиск

Поиск обязателен по:
- message
- username
- public_run_number

## 20.3. Обязательные фильтры

Фильтры:
- дата
- пользователь
- магазин
- модуль
- event_type
- severity
- run_id/public_run_number

## 20.4. Логика комбинирования

Все фильтры комбинируются по логике:
- AND

Это обязательное правило и для logs, и для history.

## 20.5. Сортировка

Обязательная сортировка по:
- event_time_utc
- severity
- event_type
- username
- store name

## 20.6. Пагинация

Пагинация обязательна.
По умолчанию:
- сортировка от новых к старым
- размер страницы 50

Допустимые размеры страницы:
- 25
- 50
- 100

---

## 21. Server-side search/filter/sort/page для history в контексте observability

Хотя history отдельно не является частью audit/log storage, observability архитектура зависит от корректной истории.

History должна:
- использовать run metadata как единый источник списка операций;
- поддерживать server-side search/filter/sort/page;
- не пересобираться из логов;
- не заменяться summary audit.

Обязательный поиск:
- public_run_number
- store name
- original filename
- short_result_text
- username инициатора

---

## 22. Summary audit как источник ключевых метрик

## 22.1. Wildberries

Summary audit WB обязан включать показатели:
- всего строк
- успешно обработано
- предупреждения
- пропущено строк
- найдено в акциях
- не найдено в акциях
- применён fallback_no_promo
- применён fallback_over_threshold
- итог взят из min_discount
- итог взят из calculated_discount
- невалидные строки акций
- невалидные файлы акций

## 22.2. Ozon

Summary audit Ozon обязан включать:
- всего строк данных
- успешно обработано
- предупреждения
- участвуют
- не участвуют
- нет минимальной цены
- нет остатка
- нет бустов
- use_max_boost_price
- use_min_price
- below_min_price_threshold
- изменено строк

## 22.3. Архитектурное следствие

Summary audit builders WB/Ozon обязаны сохранять эти показатели так, чтобы UI не пересчитывал их из detail rows.

---

## 23. Short result и его связь с audit

## 23.1. Short result не заменяет summary audit

`short_result_text` нужен для:
- списка запусков;
- dashboard;
- верхнего блока карточки run.

Но он не заменяет:
- summary audit;
- detail audit.

## 23.2. Источник short result

Short result должен быть логически согласован с summary audit и business_result.
Нельзя допускать ситуацию, когда:
- short result сообщает одно;
- summary audit показывает другое;
- business_result указывает на третье.

---

## 24. Архитектурные инварианты explainability

Ниже перечислены обязательные инварианты explainability:

1. Любой завершённый run имеет summary audit.
2. Любой завершённый run имеет detail audit.
3. Detail audit полностью хранится в PostgreSQL.
4. Run page не зависит от исходного workbook для объяснения результата.
5. Summary audit отображает ключевые counters без пересчёта.
6. Detail audit поддерживает поиск, фильтрацию, сортировку и пагинацию серверно.
7. Logs page и run page используют разные источники данных.
8. System logs не дублируют весь detail audit.
9. Detail audit не используется как суррогат system logs.
10. Severity и decision_reason стандартизированы и пригодны для фильтрации.

---

## 25. Error and anomaly observability

## 25.1. Ошибки выполнения

Если run завершился с ошибкой:
- должен быть финальный business_result;
- должен быть short_result_text с короткой причиной;
- должен существовать system log ошибки;
- audit должен быть сохранён настолько полно, насколько это возможно по стадии отказа.

## 25.2. Consistency anomalies

При несогласованностях должны логироваться system errors, включая, например:
- competing successful result anomaly;
- missing physical file при `is_available=true`;
- failure to persist audit after run completion attempt;
- timeout-induced forced finalization.

## 25.3. Принцип наблюдаемости отказов

Ни один значимый отказ не должен заканчиваться “молчаливым” состоянием без:
- system log;
- финального статуса run;
- короткого сообщения для UI.

---

## 26. Ограничения по объёму и производительности

## 26.1. Detail audit large volume

ТЗ допускает:
- до 200 000 строк detail audit на один run

Следовательно, архитектура обязана:
- использовать batch insert;
- использовать индексы;
- использовать server-side page/filter/sort;
- избегать full in-memory rendering in UI.

## 26.2. Logs and history responsiveness

Открытие:
- history: до 3 секунд
- logs: до 3 секунд
- detail audit page: до 3 секунд при server-side pagination

Следовательно:
- read-side запросы должны быть индексно-ориентированными;
- joins должны быть ограничены нужным минимумом;
- нельзя строить страницу через загрузку всех строк.

---

## 27. Что должно логироваться обязательно по стадиям run

## 27.1. На старте check

Обязательно:
- event_type = check_started
- user_id
- store_id
- run_id
- module_code
- message

## 27.2. На завершении check

Обязательно:
- event_type = check_finished
- severity в зависимости от outcome
- run_id
- business_result
- short_result summary in message/payload

## 27.3. На старте process

Обязательно:
- event_type = process_started
- user_id
- store_id
- run_id
- module_code

## 27.4. На успешном завершении process

Обязательно:
- event_type = process_finished  
или
- process_finished_with_warnings
- run_id
- business_result
- result file context, если применимо

## 27.5. При process error

Обязательно:
- event_type = process_error
- severity = error
- run_id
- diagnostic payload

---

## 28. Что должно быть проверено тестами

## 28.1. Summary audit tests

Нужно проверить:
- summary audit создаётся для check
- summary audit создаётся для process
- WB counters сохраняются полностью
- Ozon counters сохраняются полностью
- summary соответствует business_result

## 28.2. Detail audit tests

Нужно проверить:
- detail audit создаётся для check
- detail audit создаётся для process
- required common fields сохранены
- entity_key_1 заполнен по правилам WB/Ozon
- payload содержит обязательные UI-поля модуля
- search/filter/sort/page работают серверно

## 28.3. Logs tests

Нужно проверить:
- обязательные event types пишутся
- severity корректна
- log search работает по message/username/public_run_number
- filters combine by AND
- pagination and sorting work server-side

## 28.4. Separation tests

Нужно проверить:
- run page строится не из logs
- logs page строится не из detail audit
- history строится не из logs
- detail audit не хранится только в JSON-файле

## 28.5. Failure observability tests

Нужно проверить:
- failed run has system log
- timeout produces log and final status
- anomaly scenarios produce error log
- unavailable files do not break run page observability

---

## 29. Что должен проверить аудитор

Аудитор обязан отдельно проверить:

1. Что summary audit и detail audit существуют и для check, и для process.
2. Что detail audit хранится в PostgreSQL, а не только во внешних файлах.
3. Что system_logs отделены от audit.
4. Что run page использует audit как основной источник.
5. Что logs page использует system_logs как основной источник.
6. Что detail audit поддерживает required search/filter/sort/page серверно.
7. Что logs поддерживают required search/filter/sort/page серверно.
8. Что summary counters WB и Ozon покрывают обязательные показатели ТЗ.
9. Что `entity_key_1` заполняется по правилам WB/Ozon.
10. Что ошибки и аномалии не остаются без system log.
11. Что short_result_text согласован с business_result и summary audit.
12. Что preview/full detail modes не ломают server-side модель.

---

## 30. Граница текущего документа

Данный документ фиксирует:
- run audit;
- summary/detail audit;
- system logs;
- explainability;
- observability;
- server-side read rules.

Следующий документ должен раскрыть:
- UI-страницы;
- маршруты;
- page composition;
- действия и элементы экранов;
- пустые состояния;
- правила отображения по ролям.

Имя следующего файла:
- `09_UI_PAGES_AND_ROUTES.md`