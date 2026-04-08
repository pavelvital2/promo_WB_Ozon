# 09_UI_PAGES_AND_ROUTES.md

## 1. Назначение документа

Документ фиксирует:
- обязательные страницы интерфейса;
- структуру навигации;
- page composition;
- обязательные пользовательские действия на экранах;
- пустые состояния;
- правила видимости разделов;
- маршруты UI;
- связь страниц с run/history/audit/file сценариями.

Документ не описывает:
- визуальный дизайн;
- CSS/UI-kit;
- детальную backend-реализацию;
- SQL;
- бизнес-логику расчёта WB/Ozon.

---

## 2. Краткий итог

В MVP обязательны следующие страницы:

- логин
- дашборд
- пользователи
- магазины
- обработка Wildberries
- обработка Ozon
- история запусков
- логи
- страница запуска / страница полного детального аудита

Навигация должна строиться по role/permission/store-access модели:
- недоступные разделы скрываются полностью;
- store-bound разделы показываются только при наличии формального права и доступных магазинов, если ТЗ не требует иного;
- пользователь без магазинов видит дашборд с пустым состоянием;
- история запусков для пользователя без магазинов не показывается;
- карточка запуска и полная страница аудита — один и тот же экран.

UI должен быть thin и server-driven:
- бизнес-логика не переносится на клиент;
- тяжёлые выборки делаются только серверно;
- polling run status выполняется каждые 2 секунды;
- history, logs и detail audit работают только через server-side search/filter/sort/pagination.

---

## 3. Общая модель навигации

## 3.1. Верхнеуровневые разделы

Система должна поддерживать следующие верхнеуровневые разделы:

1. Dashboard
2. Users
3. Stores
4. Wildberries Processing
5. Ozon Processing
6. Run History
7. Logs
8. Change Password / Profile action
9. Logout

## 3.2. Принцип скрытия разделов

Недоступные разделы:
- не показываются;
- не показываются disabled;
- не сопровождаются сообщением “нет прав”.

Это обязательное правило.

## 3.3. Принцип пустого состояния

Если раздел формально доступен пользователю, но внутри нет доступных магазинов, допускается пустое состояние:
- “Нет доступных магазинов”

Но для history действует отдельное правило:
- пользователь без магазинов историю не видит.

---

## 4. Канонический набор маршрутов

Ниже фиксируется канонический набор маршрутов уровня UI.
Точные path names могут быть уточнены при реализации, но логическая структура должна сохраниться.

## 4.1. Аутентификация

- `/login`
- `/logout`
- `/profile/password` или эквивалентный маршрут смены собственного пароля

## 4.2. Основные страницы

- `/`
- `/dashboard`

## 4.3. Пользователи

- `/users`
- `/users/create`
- `/users/{user_id}/edit`

Допускаются отдельные action endpoints для:
- block
- unblock
- assign role
- assign permissions

## 4.4. Магазины

- `/stores`
- `/stores/create`
- `/stores/{store_id}/edit`

Допускаются отдельные action endpoints для:
- archive
- restore
- assign users to store
- update store settings

## 4.5. Обработка Wildberries

- `/processing/wb`

## 4.6. Обработка Ozon

- `/processing/ozon`

## 4.7. История запусков

- `/runs`
- допускаются query params для search/filter/sort/page

## 4.8. Логи

- `/logs`
- допускаются query params для search/filter/sort/page

## 4.9. Страница run / full detail audit

- `/runs/{public_run_number}`  
или эквивалентный маршрут по внутреннему id, если во внешнем UI стабильно используется public_run_number

Предпочтительное правило:
- публично-ориентированный маршрут должен быть привязан к `public_run_number`, потому что именно он пользовательский идентификатор из ТЗ.

---

## 5. Страница логина

## 5.1. Назначение

Страница логина обеспечивает:
- ввод username
- ввод password
- вход в систему

## 5.2. Обязательные элементы

- поле username
- поле password
- кнопка “Войти”
- сообщение об ошибке при неуспешном входе

## 5.3. Поведение

При успешном входе:
- создаётся авторизованная сессия
- пишется system log successful_login
- обновляется last_login_at_utc
- выполняется переход на dashboard

При неуспешном входе:
- пишется system log failed_login
- пользователь остаётся на странице логина
- показывается контролируемое сообщение об ошибке

## 5.4. Особый случай blocked user

Если пользователь заблокирован:
- вход не разрешается;
- должна быть показана контролируемая ошибка;
- доступ в авторизованные разделы не возникает.

---

## 6. Дашборд

## 6.1. Назначение

Дашборд — стартовая страница после логина.

## 6.2. Обязательные элементы

Минимально:
- приветственный/контекстный блок пользователя
- быстрые переходы в доступные разделы
- блок состояния доступных магазинов
- блок последних запусков или быстрых переходов, если это не противоречит scope

ТЗ не требует отдельной расширенной аналитики dashboard.
Следовательно:
- дашборд должен оставаться простым и функциональным.

## 6.3. Поведение для пользователя без магазинов

Пользователь без магазинов:
- может войти;
- видит dashboard;
- видит сообщение:
  - “Нет доступных магазинов”

## 6.4. Поведение для manager_lead с create_store и без магазинов

Такой пользователь:
- видит dashboard;
- видит “Нет доступных магазинов”;
- видит возможность перейти к созданию магазина.

---

## 7. Страница “Пользователи”

## 7.1. Доступ

Видит только admin.

## 7.2. Назначение

Управление пользователями:
- создание;
- редактирование;
- блокировка/разблокировка;
- назначение ролей;
- назначение permissions.

## 7.3. Обязательные элементы списка

Таблица пользователей должна показывать как минимум:
- username
- role
- blocked status
- created_at
- last_login_at
- actions

## 7.4. Обязательные действия

- создать пользователя
- открыть редактирование пользователя
- заблокировать
- разблокировать
- изменить роль
- изменить набор permissions

## 7.5. Пагинация и фильтры

ТЗ прямо не требует server-side таблицу пользователей.
Следовательно:
- допускается проектное решение без сложной таблицы поиска, если это не противоречит нефункциональным ограничениям.

Но для практической устойчивости рекомендуется серверная пагинация и фильтрация по аналогии с остальными административными разделами.

## 7.6. Ограничения

Не допускается:
- самосоздание первого администратора через веб;
- сценарий reset password by email;
- принудительная смена пароля;
- self-service recovery.

---

## 8. Страница “Магазины”

## 8.1. Доступ

Видят:
- admin
- manager_lead только если имеет хотя бы одно право:
  - create_store
  - edit_store

Manager не видит страницу.

## 8.2. Назначение

Управление магазинами:
- просмотр списка магазинов;
- создание;
- редактирование;
- архивирование;
- восстановление;
- изменение настроек;
- назначение пользователей на магазины.

## 8.3. Обязательные колонки списка

По умолчанию:
- название магазина
- маркетплейс
- статус

Пример формата:
- VitalEmb — Wildberries — Активен
- VitalEmb — Ozon — Архивирован

## 8.4. Действия администратора

Admin может:
- создавать store
- редактировать любой active store
- архивировать store
- восстанавливать archived store
- назначать пользователей на магазины
- изменять settings всех магазинов

## 8.5. Действия управляющего

Manager_lead может:
- создавать store только с permission create_store
- редактировать только доступный active store и только с permission edit_store
- изменять settings WB только при edit_store и доступном store

Не может:
- архивировать
- восстанавливать
- назначать пользователей на stores
- редактировать недоступный store
- редактировать archived store

## 8.6. Пустое состояние

Если manager_lead формально видит раздел магазинов, но у него:
- нет доступных магазинов;
- есть create_store;

он должен видеть возможность создать магазин.

---

## 9. Страница обработки Wildberries

## 9.1. Доступ

Видят:
- admin
- manager_lead
- manager

Но usable только при наличии доступного active WB store.

## 9.2. Назначение

Страница обеспечивает полный пользовательский сценарий WB:
- выбрать магазин;
- загрузить файлы;
- видеть текущий активный набор;
- удалить/заменить файл;
- запустить check;
- запустить process;
- видеть summary audit;
- видеть preview detail audit;
- перейти на full run page;
- скачать результат после успешного process.

## 9.3. Обязательные элементы

### Блок выбора магазина
- selector доступных WB stores
- archived stores не должны попадать в selector новых запусков

### Блок загрузки файлов
- один файл цен
- от 1 до 20 файлов акций
- отображение ограничений по количеству и размеру

### Блок активного временного набора
- список текущих файлов
- original filename
- размер
- время загрузки
- действия удалить / заменить

### Блок действий
- кнопка “Проверить” (check)
- кнопка “Обработать” (process)

### Блок статуса запуска
- lifecycle_status
- business_result после завершения
- short_result_text

### Блок summary audit
- агрегированные показатели WB

### Блок preview detail audit
- краткий предварительный просмотр detail audit

### Блок результата
- кнопка перехода на полную страницу run/audit
- кнопка скачивания результата после successful process и доступности файла

## 9.4. Поведение при устаревшем check

Отдельного ручного подтверждения перед process:
- не требуется

Система должна:
- автоматически выполнить новую validation;
- при необходимости показать, что прежний check недействителен;
- при неуспешной validation завершить process как validation_failed.

## 9.5. Пустое состояние

Если у пользователя нет доступных active WB stores:
- страница может быть скрыта из меню;
- если экран формально открыт, допускается пустое состояние:
  - “Нет доступных магазинов”

---

## 10. Страница обработки Ozon

## 10.1. Доступ

Видят:
- admin
- manager_lead
- manager

Но usable только при наличии доступного active Ozon store.

## 10.2. Назначение

Страница обеспечивает сценарий Ozon:
- выбрать магазин;
- загрузить 1 файл;
- видеть активный временный набор;
- удалить/заменить файл;
- запустить check;
- запустить process;
- видеть summary audit;
- видеть preview detail audit;
- перейти на полную страницу run/audit;
- скачать result file после successful process.

## 10.3. Обязательные элементы

### Блок выбора магазина
- selector доступных active Ozon stores

### Блок загрузки файла
- ровно 1 файл .xlsx
- отображение ограничений размера

### Блок активного временного набора
- текущий файл
- размер
- время загрузки
- удалить / заменить

### Блок действий
- “Проверить”
- “Обработать”

### Блок статуса
- lifecycle_status
- business_result
- short_result_text

### Блок summary audit
- агрегированные показатели Ozon

### Блок preview detail audit
- краткий preview detail audit

### Блок результата
- переход на run page
- скачивание result file после successful process и доступности

## 10.4. Пустое состояние

Если доступных active Ozon stores нет:
- раздел может быть скрыт;
- при формальном доступе допускается пустое состояние:
  - “Нет доступных магазинов”

---

## 11. Общий UX контракт страниц обработки

## 11.1. До запуска

Пользователь должен иметь возможность:
- выбрать store;
- собрать активный набор файлов;
- удалить файл;
- заменить файл;
- видеть состав текущего набора.

## 11.2. Во время выполнения

Пользователь должен видеть:
- принятый run;
- текущий lifecycle_status;
- polling обновление каждые 2 секунды;
- отсутствие необходимости вручную обновлять страницу.

## 11.3. После завершения

Пользователь должен видеть:
- business_result;
- short_result_text;
- summary audit;
- preview detail audit;
- переход на полный run page;
- result download при наличии result file.

## 11.4. При ошибке

Пользователь должен видеть:
- контролируемый итоговый статус;
- короткую причину;
- отсутствие недопустимых действий вроде скачивания отсутствующего result file.

---

## 12. Страница истории запусков

## 12.1. Доступ

Видят:
- admin — все runs
- manager_lead — только runs доступных stores
- manager — только runs доступных stores

Пользователь без магазинов:
- не видит историю.

## 12.2. Назначение

History — единый список всех run записей типов:
- check
- process

## 12.3. Обязательные элементы

### Поиск
По полям:
- public_run_number
- store name
- original filename
- short_result_text
- username инициатора

### Фильтры
- магазин
- пользователь
- маркетплейс
- модуль
- тип операции
- lifecycle_status
- business_result
- дата
- архивный / активный магазин

### Сортировка
По полям:
- started_at_utc
- finished_at_utc
- public_run_number
- store name
- initiated_by_user username
- operation_type
- lifecycle_status
- business_result

### Пагинация
По умолчанию:
- от новых к старым
- 50 на страницу

Допустимые page size:
- 25
- 50
- 100

## 12.4. Таблица истории

Минимально должна показывать:
- public_run_number
- started_at / finished_at
- store
- marketplace/module
- initiated_by
- operation_type
- lifecycle_status
- business_result
- short_result_text
- действия перехода на run page
- file availability indicators, если они выводятся в списке

## 12.5. Поведение фильтров

Все фильтры комбинируются по логике:
- AND

---

## 13. Страница логов

## 13.1. Доступ

Видит:
- только admin

## 13.2. Назначение

Просмотр system_logs с server-side search/filter/sort/pagination.

## 13.3. Обязательные элементы

### Поиск
- message
- username
- public_run_number

### Фильтры
- дата
- пользователь
- магазин
- модуль
- event_type
- severity
- run_id/public_run_number

### Сортировка
- event_time_utc
- severity
- event_type
- username
- store name

### Пагинация
По умолчанию:
- новые сверху
- 50 на страницу

Размеры:
- 25
- 50
- 100

## 13.4. Таблица логов

Минимально должна показывать:
- event_time
- severity
- event_type
- user
- store
- run/public_run_number
- message

## 13.5. Ограничения

Manager_lead и Manager:
- не видят раздел;
- не получают доступ по прямому URL;
- не получают partial view logs.

---

## 14. Страница run / full detail audit

## 14.1. Назначение

Это единый экран, который объединяет:
- “карточку запуска”
- “полную страницу детального аудита”

Отдельный второй экран под карточку запуска:
- не требуется.

## 14.2. Доступ

Видят:
- admin — любой run
- manager_lead — только run доступного store
- manager — только run доступного store

## 14.3. Обязательные блоки страницы

### Блок 1. Основные данные run
- public_run_number
- store
- marketplace/module
- operation_type
- initiated_by
- started_at
- finished_at
- lifecycle_status
- business_result
- short_result_text

### Блок 2. Файлы run
- input files
- result file, если есть
- indicators доступности/недоступности
- download actions для доступных файлов

### Блок 3. Summary audit
- агрегированный summary block по модулю

### Блок 4. Detail audit table
- полный detail audit
- search/filter/sort/page серверно

## 14.4. Detail audit controls

Обязательные элементы:
- поиск
- фильтр severity
- фильтр decision_reason
- фильтр row_number range
- сортировка
- пагинация

## 14.5. Module-aware columns

### Для WB
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

### Для Ozon
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

## 14.6. Поведение при недоступном файле

Если файл недоступен:
- должна отображаться надпись “Файл недоступен”
- кнопка скачивания disabled
- должен быть отдельный признак недоступности

---

## 15. Страница смены собственного пароля

## 15.1. Доступ

Все авторизованные и не заблокированные пользователи.

## 15.2. Назначение

Смена собственного пароля в рамках авторизованной сессии.

## 15.3. Обязательные элементы

- текущее значение пароля, если принято проектно
- новый пароль
- подтверждение нового пароля
- кнопка сохранения

## 15.4. Ограничения

В MVP не входят:
- forgot password
- recovery by email
- forced password reset
- admin-free recovery flow

---

## 16. Навигация по ролям

## 16.1. Admin menu

Должен видеть:
- Dashboard
- Users
- Stores
- Wildberries
- Ozon
- Run History
- Logs
- Change Password
- Logout

## 16.2. Manager_lead menu

Должен видеть:
- Dashboard
- Stores — только при create_store или edit_store
- Wildberries — только если есть формальный доступ к разделу и/или доступные WB stores
- Ozon — только если есть формальный доступ к разделу и/или доступные Ozon stores
- Run History — только если есть доступные stores
- Change Password
- Logout

Не видит:
- Users
- Logs

## 16.3. Manager menu

Должен видеть:
- Dashboard
- Wildberries — только если есть доступные WB stores
- Ozon — только если есть доступные Ozon stores
- Run History — только если есть доступные stores
- Change Password
- Logout

Не видит:
- Users
- Stores
- Logs

---

## 17. Page-level access behavior

## 17.1. Если раздел скрыт

Он:
- не отображается в меню;
- не должен быть доступен действием из интерфейса.

## 17.2. Если прямой URL открыт без права

Доступ должен быть отклонён на backend authorization level.

## 17.3. Если формальное право есть, но магазинов нет

Показывается пустое состояние:
- “Нет доступных магазинов”

Исключение:
- history скрывается для пользователя без магазинов.

---

## 18. UI состояния ошибок и отказов

## 18.1. Структурированные ошибки

Интерфейс должен уметь показывать контролируемые ошибки по контракту:
- error_code
- error_message
- details

## 18.2. Обязательные сценарии

- access_denied
- validation_failed
- system_error
- archived_store_forbidden
- permission_denied
- file_limit_exceeded
- active_run_conflict

## 18.3. Поведение UI

UI не должен:
- показывать raw traceback;
- переходить в неконсистентное состояние;
- продолжать polling бесконечно после финального статуса;
- показывать кнопку скачивания для недоступного файла.

---

## 19. Query parameter contract для таблиц

Для history, logs и detail audit допускается общий принцип query parameters:

- `q` — строка поиска
- `page`
- `page_size`
- `sort_by`
- `sort_dir`
- filter params по обязательным полям

Точные имена параметров могут быть уточнены в реализации, но должны быть:
- стабильными;
- серверно обрабатываемыми;
- пригодными для восстановления состояния страницы после reload/share.

---

## 20. Page refresh and state persistence

## 20.1. History / Logs / Detail audit

После обновления страницы должно сохраняться текущее состояние:
- filters
- sort
- page
- search query

Это желательно для UX и не противоречит ТЗ.

## 20.2. Processing pages

На processing page после завершения run желательно сохранять:
- выбранный store
- текущее состояние активного temp set
- видимость последнего результата

Но активный набор всё равно определяется сервером как текущий фактический active set.

---

## 21. Обязательные пустые состояния

Нужно предусмотреть минимум следующие пустые состояния:

1. Нет доступных магазинов на dashboard
2. Нет доступных магазинов на processing page
3. Пустая history result set после применения фильтров
4. Пустая logs result set после применения фильтров
5. Пустой detail audit result set после применения фильтров
6. Нет доступных файлов для скачивания
7. Временный набор пуст после auto-purge или до первой загрузки

---

## 22. Что должно быть проверено тестами

## 22.1. Navigation tests

Нужно проверить:
- admin sees full menu
- manager_lead menu depends on permissions
- manager does not see stores/users/logs
- no inaccessible sections are shown

## 22.2. Processing page tests

Нужно проверить:
- WB page supports required file composition
- Ozon page supports single-file scenario
- temp set visible
- delete/replace available
- check/process actions visible only where allowed
- polling updates status

## 22.3. Run page tests

Нужно проверить:
- run page accessible only for permitted runs
- summary audit rendered
- detail audit server-side controls work
- unavailable file shown correctly
- module-specific columns rendered correctly

## 22.4. History/logs tests

Нужно проверить:
- required search/filter/sort/page
- default page size and sort
- AND combination of filters
- no-store user does not see history
- non-admin cannot access logs

## 22.5. Empty-state tests

Нужно проверить:
- no-store dashboard state
- no-store processing state
- empty table states
- temp-set empty state after purge

---

## 23. Что должен проверить аудитор

Аудитор обязан отдельно проверить:

1. Что реализованы все обязательные страницы из ТЗ.
2. Что run page и full audit page — один экран.
3. Что недоступные разделы скрываются, а не disabled.
4. Что history, logs и detail audit работают серверно.
5. Что page defaults соблюдены:
   - history/logs default sort new-to-old
   - default page size 50
6. Что menu visibility соответствует role/permission rules.
7. Что no-store user scenario реализован корректно.
8. Что archived stores отсутствуют в selector для новых запусков.
9. Что processing pages не выходят за scope MVP.
10. Что UI не дублирует бизнес-логику клиента.
11. Что download buttons корректно блокируются для unavailable files.

---

## 24. Граница текущего документа

Данный документ фиксирует:
- обязательные страницы;
- маршруты;
- состав экранов;
- навигацию;
- пустые состояния;
- page-level UI contract.

Следующий документ должен раскрыть:
- поток работы Wildberries;
- check/process pipeline WB;
- входные файлы;
- этапы нормализации и расчёта;
- summary/detail audit semantics WB;
- critical errors and warnings WB.

Имя следующего файла:
- `10_WB_PROCESSING_FLOW.md`