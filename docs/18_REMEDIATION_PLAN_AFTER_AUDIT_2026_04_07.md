# 18_REMEDIATION_PLAN_AFTER_AUDIT_2026_04_07.md

## 1. Назначение документа

Документ фиксирует:
- разбор расхождений из `docs/otchet_07.04.26.txt`;
- какие замечания уже устарели относительно текущего состояния проекта;
- какие обязательные требования ТЗ реально остаются незакрытыми;
- скорректированную следующую фазу работ;
- порядок remediation до состояния, пригодного для приёмки по ТЗ.

Документ не меняет ТЗ.
Документ не подменяет `12_IMPLEMENTATION_STAGES.md`.
Документ задаёт корректирующий execution-order поверх уже собранного backend skeleton.

---

## 2. Текущий статус проекта на момент старта remediation

На момент первоначальной фиксации документа были приняты следующие крупные блоки:
- Foundation/Data
- Auth/Access/Stores
- Files/Runs/Async
- Marketplace Processing
- Audit/History/UI Acceptance
- Persistence/HTTP Wiring
- Web App Surface
- E2E Acceptance Contour
- Acceptance Gaps Closure

Это означает:
- backend skeleton и HTTP surface уже собраны;
- acceptance contour уже существует;
- проект нельзя считать пустым каркасом;
- но проект всё ещё не соответствует ТЗ полностью.

Следовательно, дальнейшая работа должна идти не как “новая функциональность”, а как remediation обязательных незакрытых требований.

---

## 3. Классификация замечаний из внешнего отчёта

## 3.1. Замечания, которые уже частично или полностью устарели

Ниже перечислено то, что было справедливо для проверенного архива, но уже не полностью соответствует текущему live-state репозитория:
- отсутствует HTTP/web surface целиком;
- отсутствуют history/logs/audit API;
- отсутствует acceptance contour;
- отсутствует worker/internal boundary hardening;
- отсутствуют WB/Ozon process smoke scenarios;
- отсутствуют secure download и unavailable-file smoke scenarios.

Это не означает, что проект уже соответствует ТЗ.
Это означает только, что часть замечаний отчёта относится к более раннему снимку проекта.

## 3.2. Замечания, которые остаются обязательными незакрытыми блоками

Ниже перечислены требования ТЗ, которые должны быть возвращены в основной обязательный roadmap.

1. Полноценный рабочий CLI bootstrap первого администратора.
2. Полный user management:
   - создание пользователя;
   - редактирование пользователя;
   - блокировка/разблокировка;
   - назначение роли;
   - назначение permissions;
   - управление store access как завершённый admin flow.
3. DB-side filtering/search/sort/pagination для:
   - history;
   - logs;
   - detail audit.
4. Строгие file limits:
   - 25 МБ на файл;
   - 100 МБ суммарно на набор WB-файлов;
   - максимум 20 WB promo files.
5. Усиленная Excel validation и safe-save contract:
   - protected workbook;
   - protected worksheet;
   - risky formulas/write restrictions;
   - macros/xlsm risk;
   - external links;
   - unsafe-save detection.
6. Полный lifecycle старых result files:
   - новый successful process делает старый result superseded;
   - старый result становится недоступен;
   - событие журналируется;
   - read-side и download surface это отражают.
7. Полный обязательный набор system log events по ТЗ.
8. Единый structured error contract во всех API.
9. Полноценный обязательный UI из страниц ТЗ.
10. Production-grade async runtime:
   - автономный worker contour;
   - maintenance scheduling;
   - timeout reconciliation.

---

## 4. Что является следующим этапом теперь

Следующая фаза должна быть скорректирована.

Неправильно:
- сразу переходить в абстрактный “production hardening”;
- сразу уходить в расширение acceptance;
- сразу делать frontend без закрытия backend-обязательств.

Правильно:
- сначала вернуть в обязательный план незавершённые требования ТЗ;
- только после этого переходить к deep hardening и release readiness.

Следующая фаза теперь называется:

## 4.1. Mandatory Compliance Remediation

Эта фаза предшествует любому дальнейшему production hardening.

---

## 5. Скорректированный порядок следующих фаз

## 5.1. Фаза R1. Bootstrap and Admin Compliance Recovery

### Цель
Закрыть обязательные требования, которые должны были быть завершены ещё в ранних этапах.

### Входит в фазу
- рабочий CLI первого администратора;
- полноценный admin user-management backend flow;
- admin management по ролям и permissions;
- унификация structured error contract в admin/auth/user flows.

### Почему эта фаза идёт первой
Потому что:
- это прямые обязательные требования ТЗ;
- они не должны оставаться “потом” после web surface;
- часть acceptance по users сейчас недостоверна без этих flows.

### Критерий завершения
- первый admin реально создаётся через CLI;
- admin API/users flow завершён;
- non-admin не может выполнять admin actions;
- error contract единообразен в соответствующих API.

---

## 5.2. Фаза R2. File Intake and Workbook Safety Compliance

### Цель
Довести file-validation и workbook-safety до контрактов ТЗ.

### Входит в фазу
- file limits enforcement;
- WB/Ozon upload composition checks;
- workbook/worksheet protection checks;
- macros/xlsm risk rejection;
- external links handling policy;
- unsafe-save detection;
- точная Ozon template validation по буквенным позициям и sanity checks;
- WB safe-write guard по колонке `Новая скидка`.

### Почему эта фаза идёт второй
Потому что:
- это влияет на деньги, workbook safety и приёмку результата;
- acceptance без этого остаётся только каркасной.

### Критерий завершения
- лимиты файлов enforced;
- unsafe workbook scenarios отклоняются контролируемо;
- WB/Ozon workbook validation соответствует ТЗ;
- тесты покрывают positive, negative и edge workbook cases.

---

## 5.3. Фаза R3. Result Lifecycle and Logging Compliance

### Цель
Довести file lifecycle и system logging до полного соответствия ТЗ.

### Входит в фазу
- полный supersede предыдущего successful result;
- корректный unavailable lifecycle старого result file;
- журналирование supersede и cleanup событий;
- журналирование upload/replace/delete/download событий;
- журналирование auth/admin/run/store событий в полном объёме обязательной матрицы ТЗ.

### Почему эта фаза идёт третьей
Потому что:
- file lifecycle и logging уже частично собраны;
- теперь их нужно довести до полного нормативного контракта.

### Критерий завершения
- новый successful process автоматически supersede старый result;
- старый result нельзя скачать;
- history/run page/download surface отражают это корректно;
- обязательный event set покрыт в `system_logs`.

---

## 5.4. Фаза R4. DB-Side Read Model Compliance

### Цель
Переделать read-side с Python-side filtering на DB-side filtering/search/sort/pagination.

### Входит в фазу
- query objects / SQL read adapters для history;
- query objects / SQL read adapters для logs;
- query objects / SQL read adapters для detail audit;
- page size / sort / filter semantics на стороне БД;
- тесты на большие выборки и server-side behavior.

### Почему эта фаза идёт четвёртой
Потому что:
- это обязательное требование ТЗ;
- текущий read-side функционально есть, но не соответствует контракту производительности и архитектуры хранения.

### Критерий завершения
- history/logs/detail audit не фильтруются в Python после полного `list()`;
- search/filter/sort/pagination уходит в БД;
- acceptance и integration tests подтверждают DB-side behavior.

---

## 5.5. Фаза R5. Mandatory UI Pages

### Цель
Собрать обязательный веб-интерфейс из страниц ТЗ поверх уже принятого HTTP surface.

### Входит в фазу
- login page;
- dashboard;
- users page;
- stores page;
- processing WB page;
- processing Ozon page;
- run history page;
- logs page;
- run/detail audit page.

### Почему эта фаза не должна идти раньше R1–R4
Потому что:
- иначе UI будет строиться поверх ещё не доведённых обязательных backend contracts;
- это зафиксирует незавершённые требования в пользовательском слое.

### Критерий завершения
- все обязательные страницы ТЗ существуют;
- hidden sections/no-store behavior отражены в реальном UI;
- ключевые пользовательские сценарии работают не только через API, но и через страницы.

---

## 5.6. Фаза R6. Autonomous Async Runtime and Operational Hardening

### Цель
Перевести current skeleton execution contour в более автономный operational contour.

### Входит в фазу
- автономный worker execution path;
- maintenance scheduler contour;
- timeout reconciliation;
- stronger operational observability;
- production-safe runtime separation between web and worker.

### Почему эта фаза идёт после обязательных remediation-фаз
Потому что:
- это уже не закрытие базового обязательного MVP-требования, а доведение до эксплуатационной зрелости.

### Критерий завершения
- run execution не требует тестового/internal drain hook;
- maintenance выполняется автономно;
- runtime устойчивее к operational failure paths.

---

## 6. Статус remediation-фазы сейчас

Фазы `R1`-`R5` закрыты.

Закрыты следующие remediation-задачи:
- `R1-A01. Рабочий CLI bootstrap первого администратора`
- `R1-A02. Полный user management backend flow`
- `R2-A01. Строгие file limits и upload composition validation`
- `R2-A02. Усиленная Excel validation и safe-save contract`
- `R3-A01. Полный lifecycle supersede старых result files и недоступность предыдущих outputs`
- `R3-A02. Полный mandatory system logging matrix и унификация structured error contract`
- `R4-A01. DB-side filtering/search/sort/pagination для history/logs/detail audit/read-side`
- `R5-A01. Обязательные UI pages и маршруты по ТЗ`

Следующий шаг после завершения remediation-фазы:

`R6-A01. Автономный async runtime boundary`

Актуальная handoff-фиксация состояния вынесена в:
- `19_STATUS_HANDOFF_AFTER_R1_R5_2026_04_07.md`

---

## 7. Что не должно быть следующим шагом

До завершения фаз `R1`–`R5` не должно считаться приоритетом:
- generic production hardening как отдельная фаза;
- browser/frontend polish;
- расширение acceptance сверх обязательных незакрытых требований;
- инфраструктурный рефакторинг без прямой связи с ТЗ.

---

## 8. Правило использования этого документа

Пока все обязательные remediation-фазы `R1`–`R5` не закрыты:
- проект нельзя считать готовым к приёмке по ТЗ;
- любые новые фазы должны оцениваться против этого remediation backlog;
- оркестратор не должен объявлять backend skeleton “достаточным”, если обязательные нормативные требования остаются незакрытыми.

---

## 9. Итог

Основной backend skeleton уже собран.
Mandatory remediation-фаза завершена.
Следующая фаза теперь:

- было: `Mandatory Compliance Remediation`
- стало: `R6. Autonomous Async Runtime and Operational Hardening`

Дальнейшая работа теперь допустимо смещается в:
- автономный runtime hardening;
- operational resilience;
- release readiness.
