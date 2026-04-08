# 20_STATUS_HANDOFF_AFTER_R6_2026_04_07.md

## 1. Назначение документа

Документ фиксирует контрольную точку проекта после завершения `R6`.

Документ нужен для:
- безопасного перехода от operational hardening к release/deployment contour;
- handoff между сессиями после закрытия `R6-A01`-`R6-A03`;
- отделения завершённого runtime hardening от следующей release-фазы.

Документ не меняет ТЗ.
Документ не заменяет `12_IMPLEMENTATION_STAGES.md` и `13_DETAILED_TASK_BREAKDOWN.md`.

---

## 2. Текущий статус

На текущий момент закрыты:
- основной MVP skeleton;
- mandatory remediation `R1`-`R5`;
- operational hardening baseline `R6-A01`-`R6-A03`.

Это означает:
- обязательные нормативные расхождения из внешнего аудита закрыты;
- текущий runtime больше не является только тестовым/informal contour;
- следующий шаг теперь относится к release/deployment readiness, а не к remediation или базовому runtime hardening.

---

## 3. Что закрыто в R6

### 3.1. R6-A01. Автономный async runtime boundary

Закрыто:
- автономный in-process worker runtime;
- явное разделение web path и worker path;
- thread-safe queue с blocking wait;
- execution без reliance на manual internal drain как primary mechanism.

### 3.2. R6-A02. Maintenance scheduler и timeout reconciliation

Закрыто:
- автономный in-process maintenance scheduler;
- periodic purge/retention/reconciliation contour;
- hard-timeout finalization для stuck runs;
- persisted logging для timeout reconciliation.

### 3.3. R6-A03. Operational resilience и multi-job/runtime failure-path hardening

Закрыто:
- multi-job autonomous processing proof;
- worker survival after unexpected job exception;
- maintenance survival after task exception;
- persisted runtime `system_error` для worker/maintenance failure-paths;
- исправление live-path `system_logs.id` collision.

---

## 4. Что считается принятым состоянием проекта сейчас

Считается принятым:
- backend/API/UI слой собран end-to-end;
- runtime/maintenance contour автономен в рамках current in-process architecture;
- key failure-path resilience и observability baseline присутствуют;
- проект доведён до состояния, в котором следующий логичный этап уже связан с release/deployment contour.

---

## 5. Актуальные residual risks после R6

1. Runtime и maintenance остаются `in-process/single-node`.
2. Нет внешнего брокера, distributed coordination и cross-process worker model.
3. Нет полного deployment contour для Ubuntu VPS + nginx + systemd.
4. Нет зафиксированного deployment/runtime baseline:
   - systemd service behavior
   - nginx integration expectations
   - storage path permissions
   - runtime configuration safety
   - log rotation hooks
5. Acceptance contour остаётся `TestClient`-ориентированным, а не deploy-level smoke.

---

## 6. Следующая фаза

Следующая фаза:

`R7. Release Readiness and Deployment Contour`

### Цель

Довести проект от accepted runtime baseline до состояния, пригодного для безопасного развёртывания и выпускной приёмки в целевой среде ТЗ:
- Ubuntu VPS
- nginx
- systemd
- PostgreSQL
- без Docker

### Входит в фазу

- deployment/runtime hardening baseline;
- systemd-ready app/service contour;
- nginx integration baseline;
- storage/log/runtime permission safety;
- release smoke and deployment-oriented readiness checks.

### Не входит автоматически

- новый функционал вне ТЗ;
- миграция на внешние очереди/распределённый runtime;
- UI redesign;
- инфраструктурный overbuild beyond target environment.

---

## 7. Следующая атомарная задача

Следующая атомарная задача должна быть:

`R7-A01. Deployment/runtime hardening baseline`

### Ожидаемый результат

- baseline для Ubuntu VPS + nginx + systemd зафиксирован в коде/артефактах проекта;
- runtime configuration и storage paths готовы к безопасной эксплуатации;
- есть минимальные deployment/runtime smoke checks;
- проект можно готовить к выпускной приёмке без Docker.

---

## 8. Короткий handoff

Если оркестрацию нужно возобновить позже, достаточно передать:

- `R1`-`R5` закрыты;
- `R6-A01`-`R6-A03` закрыты;
- следующая фаза: `R7. Release Readiness and Deployment Contour`;
- следующий блок: `R7-A01. Deployment/runtime hardening baseline`.
