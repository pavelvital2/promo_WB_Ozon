# 19_STATUS_HANDOFF_AFTER_R1_R5_2026_04_07.md

## 1. Назначение документа

Документ фиксирует контрольную точку проекта после завершения фаз `R1`-`R5` из remediation-плана.

Документ нужен для:
- безопасного возобновления оркестрации;
- фиксации уже закрытых обязательных расхождений;
- отделения завершённой remediation-фазы от следующей operational-фазы;
- краткого handoff между сессиями.

Документ не меняет ТЗ.
Документ не заменяет профильные архитектурные документы.

---

## 2. Текущий статус

На текущий момент закрыты:
- основной backend skeleton;
- accepted HTTP/web surface;
- acceptance contour;
- mandatory compliance remediation `R1`-`R5`.

Это означает:
- обязательные незакрытые пункты из `docs/otchet_07.04.26.txt`, возвращённые в roadmap документом `18_REMEDIATION_PLAN_AFTER_AUDIT_2026_04_07.md`, закрыты;
- проект больше не находится в состоянии "backend skeleton с нормативными дырами";
- следующая фаза теперь уже не remediation, а `R6. Autonomous Async Runtime and Operational Hardening`.

---

## 3. Что закрыто в remediation-фазе

### 3.1. R1. Bootstrap and Admin Compliance Recovery

Закрыто:
- рабочий CLI bootstrap первого администратора;
- полноценный admin user-management backend flow;
- admin-only enforcement для users/permissions/store-access;
- нормализованный admin/auth/user contour.

### 3.2. R2. File Intake and Workbook Safety Compliance

Закрыто:
- строгие file limits и upload composition validation;
- workbook safety validation для `WB` и `Ozon`;
- safe-save contract;
- controlled rejection для unsafe workbook scenarios.

### 3.3. R3. Result Lifecycle and Logging Compliance

Закрыто:
- полный supersede lifecycle старых result files;
- недоступность superseded outputs на read-side и download boundary;
- persisted logging для supersede transitions;
- mandatory system logging matrix;
- canonical structured error contract на основных boundary;
- persisted `system_error` для unexpected web-level failures.

### 3.4. R4. DB-Side Read Model Compliance

Закрыто:
- DB-side filtering/search/sort/pagination для `history`;
- DB-side filtering/search/sort/pagination для `logs`;
- DB-side filtering/search/sort/pagination для `detail audit`;
- live wiring без `Repository.list() + Python filtering` на целевых read-side путях.

### 3.5. R5. Mandatory UI Pages

Закрыто:
- обязательные HTML routes/pages по ТЗ;
- login/dashboard/users/stores/processing/history/logs/run page;
- role/access visibility rules;
- no-store behavior;
- exact run-page routing по `public_run_number`;
- обязательные page controls, включая pagination.

---

## 4. Что считается принятым состоянием проекта сейчас

Считаются принятыми следующие крупные блоки:
- Foundation/Data
- Auth/Access/Stores
- Files/Runs/Async
- Marketplace Processing
- Audit/History/UI Acceptance
- Persistence/HTTP Wiring
- Web App Surface
- E2E Acceptance Contour
- Acceptance Gaps Closure
- Mandatory Compliance Remediation `R1`-`R5`

Практический итог:
- backend/API/UI слой собран end-to-end;
- обязательные требования ТЗ, ранее пропущенные, возвращены и закрыты;
- проект готов к переходу в следующую фазу operational hardening.

---

## 5. Актуальные residual risks

Ниже перечислено то, что остаётся открытым после завершения `R1`-`R5`, но уже не является незакрытым обязательным remediation-блоком.

1. Async runtime всё ещё не автономный:
   - execution contour всё ещё опирается на in-process/internal hooks;
   - нет полного отделения web и worker runtime.

2. Maintenance contour не доведён до окончательного autonomous runtime:
   - cleanup/scheduler/runtime reconciliation остаются частью следующей фазы.

3. Часть operational observability остаётся best-effort:
   - `system_error` persisted, но runtime-wide operational contour ещё не завершён.

4. UI остаётся thin server-rendered MVP:
   - это принятый обязательный интерфейсный слой, но не production-polished frontend.

5. Acceptance contour остаётся `TestClient`-ориентированным:
   - это достаточно для принятого MVP/remediation scope;
   - это не browser/deploy-level E2E.

---

## 6. Следующая фаза на момент фиксации

Следующая фаза:

`R6. Autonomous Async Runtime and Operational Hardening`

### Цель

Перевести текущий execution contour из accepted MVP/remediation состояния в более автономный и эксплуатационно устойчивый runtime.

### Входит в фазу

- автономный worker contour;
- отделение worker execution от user-facing web surface;
- maintenance scheduler contour;
- timeout reconciliation;
- stronger operational observability;
- operational failure-path hardening.

### Не входит автоматически

Не входит без отдельного решения:
- новый функционал вне ТЗ;
- redesign UI;
- generic infrastructure expansion beyond documented scope.

---

## 7. Следующая атомарная задача на момент фиксации

Следующая атомарная задача должна быть:

`R6-A01. Автономный async runtime boundary`

### Ожидаемый результат

- запуск run execution без reliance на test/internal drain hook;
- более явное разделение web path и worker path;
- минимальный accepted operational contour для background execution;
- tests, доказывающие новый boundary.

---

## 8. Правила возобновления оркестрации

При возобновлении работы нужно считать актуальными следующие правила:

- активных агентов проверять регулярно;
- если блок не принят аудитом, он автоматически уходит на доработку;
- роль оркестратора не смешивается с ролями исполнителя, аудитора, тестировщика и документационного контура;
- следующая фаза после этого handoff уже не remediation, а `R6`.

---

## 9. Короткий handoff на момент фиксации

Если сессию нужно возобновить позже, достаточно передать:

- remediation `R1`-`R5` закрыты;
- следующий блок: `R6-A01. Автономный async runtime boundary`;
- current accepted surface уже включает backend, UI pages, DB-side read-side и structured logging/error contracts;
- remaining work относится к autonomous runtime и operational hardening, а не к незакрытым обязательным требованиям ТЗ.
