from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Iterable
from urllib.parse import urlencode

from promo.access.presentation import MenuVisibilityViewModel, NoStoreStateViewModel
from promo.audit.presentation import RunPageReadModel
from promo.history.presentation import HistoryPageViewModel
from promo.logs.presentation import LogsPageViewModel
from promo.shared.enums import MarketplaceCode
from promo.stores.presentation import StoreListViewModel, StoreViewModel
from promo.temp_files.presentation import TemporaryFileListViewModel
from promo.users.presentation import UserDetailViewModel

SESSION_COOKIE_NAME = "promo_session_token"


@dataclass(slots=True, frozen=True)
class UiPageState:
    username: str
    role_name: str
    menu: MenuVisibilityViewModel
    no_store_state: NoStoreStateViewModel | None


def login_page(*, error_message: str | None = None) -> str:
    message = ""
    if error_message:
        message = f'<p class="message error" id="login-error">{escape(error_message)}</p>'
    body = f"""
    <main class="auth-card">
      <h1>Вход</h1>
      <p class="muted">Веб-программа расчёта скидок для Wildberries и Ozon</p>
      {message}
      <form id="login-form">
        <label>Username <input type="text" name="username" autocomplete="username" required></label>
        <label>Password <input type="password" name="password" autocomplete="current-password" required></label>
        <button type="submit">Войти</button>
      </form>
    </main>
    <script>
    document.getElementById("login-form").addEventListener("submit", async (event) => {{
      event.preventDefault();
      const form = event.currentTarget;
      const payload = {{
        username: form.username.value.trim(),
        password: form.password.value,
      }};
      const response = await fetch("/api/auth/login", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(payload),
      }});
      const body = await response.json().catch(() => ({{}}));
      const messageNode = document.getElementById("login-error") || document.createElement("p");
      messageNode.id = "login-error";
      messageNode.className = "message error";
      if (!response.ok) {{
        messageNode.textContent = body.error_message || "Не удалось выполнить вход";
        if (!messageNode.parentElement) {{
          form.before(messageNode);
        }}
        return;
      }}
      document.cookie = "{SESSION_COOKIE_NAME}=" + encodeURIComponent(body.session_token) + "; Path=/; SameSite=Lax";
      window.location.assign("/dashboard");
    }});
    </script>
    """
    return _document("Login", None, body)


def dashboard_page(state: UiPageState) -> str:
    no_store = ""
    if state.no_store_state is not None:
        cta = ""
        if state.no_store_state.show_create_store_cta:
            cta = '<p><a class="button-link" href="/stores/create">Создать магазин</a></p>'
        no_store = f"""
        <section class="panel">
          <h2>Пустое состояние</h2>
          <p>{escape(state.no_store_state.message)}</p>
          {cta}
        </section>
        """
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>Dashboard</h1>
        <p>Пользователь: <strong>{escape(state.username)}</strong></p>
        <p>Роль: <strong>{escape(state.role_name)}</strong></p>
        <p>Доступных магазинов: <strong>{state.menu.accessible_store_count}</strong></p>
      </section>
      <section class="panel">
        <h2>Быстрые переходы</h2>
        <ul class="link-list">
          {_menu_links(state.menu)}
        </ul>
      </section>
      {no_store}
    </main>
    """
    return _document("Dashboard", state, body)


def users_page(state: UiPageState, users: tuple[UserDetailViewModel, ...]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.username)}</td>
          <td>{escape(item.role_name)}</td>
          <td>{'Да' if item.is_blocked else 'Нет'}</td>
          <td>{_fmt_dt(item.created_at_utc)}</td>
          <td>{_fmt_dt(item.last_login_at_utc)}</td>
          <td>{item.accessible_store_count}</td>
          <td>{", ".join(escape(code) for code in item.permission_codes) or "-"}</td>
          <td>
            <a href="/users/{item.id}/edit">Редактировать</a>
            <button type="button" class="secondary action-button" data-action-path="/api/users/{item.id}/{'unblock' if item.is_blocked else 'block'}" data-action-method="POST">
              {'Разблокировать' if item.is_blocked else 'Заблокировать'}
            </button>
          </td>
        </tr>
        """
        for item in users
    ) or '<tr><td colspan="8">Пользователи отсутствуют</td></tr>'
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <div class="panel-header">
          <h1>Пользователи</h1>
          <a class="button-link" href="/users/create">Создать пользователя</a>
        </div>
        <table>
          <thead>
            <tr><th>Username</th><th>Role</th><th>Blocked</th><th>Created</th><th>Last login</th><th>Stores</th><th>Permissions</th><th>Actions</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
    </main>
    """
    return _document("Users", state, body)


def user_form_page(
    state: UiPageState,
    *,
    title: str,
    api_path: str,
    method: str,
    user: UserDetailViewModel | None = None,
) -> str:
    permissions = "" if user is None else ",".join(user.permission_codes)
    password_field = ""
    if user is None:
        password_field = '<label>Password <input type="password" name="password" required></label>'
    block_action = ""
    if user is not None:
        action_path = f"/api/users/{user.id}/{'unblock' if user.is_blocked else 'block'}"
        action_label = "Разблокировать" if user.is_blocked else "Заблокировать"
        block_action = f'<button type="button" data-action-path="{action_path}" class="secondary action-button">{action_label}</button>'
    store_access = ""
    permissions_panel = ""
    if user is not None:
        access_rows = "\n".join(
            f"<li>Store #{item.store_id}</li>"
            for item in user.store_access
        ) or "<li>Нет назначенных магазинов</li>"
        store_access = f"""
        <section class="panel">
          <h2>Store access</h2>
          <ul>{access_rows}</ul>
        </section>
        """
        permission_rows = "\n".join(
            f"""
            <li>
              <span>{escape(permission.code)}</span>
              <button type="button" class="secondary action-button" data-action-path="/api/users/{user.id}/permissions/{permission.code}" data-action-method="DELETE">Удалить</button>
            </li>
            """
            for permission in user.permissions
        ) or "<li>Нет назначенных permissions</li>"
        permissions_panel = f"""
        <section class="panel">
          <h2>Permissions</h2>
          <ul class="link-list">{permission_rows}</ul>
          <form class="grant-permission-form" data-user-id="{user.id}">
            <label>Permission code <input type="text" name="permission_code" placeholder="create_store"></label>
            <button type="submit">Назначить permission</button>
            <p class="message" data-form-message></p>
          </form>
        </section>
        """
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>{escape(title)}</h1>
        <form class="json-form" data-api-path="{escape(api_path)}" data-method="{escape(method)}" data-success-redirect="/users">
          <label>Username <input type="text" name="username" value="{escape('' if user is None else user.username)}" required></label>
          {password_field}
          <label>Role code
            <select name="role_code" required>
              {_options(("admin", "manager_lead", "manager"), None if user is None else user.role_code)}
            </select>
          </label>
          <label>Permission codes (через запятую)
            <input type="text" name="permission_codes" value="{escape(permissions)}" {"required" if user is None else ""}>
          </label>
          <div class="actions">
            <button type="submit">Сохранить</button>
            {block_action}
          </div>
          <p class="message" data-form-message></p>
        </form>
      </section>
      {store_access}
      {permissions_panel}
    </main>
    """
    return _document(title, state, body)


def stores_page(state: UiPageState, stores: StoreListViewModel) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.name)}</td>
          <td>{escape(item.marketplace)}</td>
          <td>{escape(item.status)}</td>
          <td><a href="/stores/{item.id}/edit">Открыть</a></td>
        </tr>
        """
        for item in stores.items
    ) or '<tr><td colspan="4">Магазины отсутствуют</td></tr>'
    create_cta = '<a class="button-link" href="/stores/create">Создать магазин</a>' if state.menu.show_create_store_cta else ""
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <div class="panel-header">
          <h1>Магазины</h1>
          {create_cta}
        </div>
        <table>
          <thead>
            <tr><th>Название</th><th>Marketplace</th><th>Статус</th><th>Actions</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
    </main>
    """
    return _document("Stores", state, body)


def store_form_page(
    state: UiPageState,
    *,
    title: str,
    api_path: str,
    method: str,
    store: StoreViewModel | None = None,
    assigned_users: tuple[UserDetailViewModel, ...] = (),
    available_users: tuple[UserDetailViewModel, ...] = (),
) -> str:
    marketplace = "wb" if store is None else store.marketplace
    settings = ""
    if marketplace == "wb":
        settings = f"""
          <label>WB threshold <input type="number" name="wb_threshold_percent" value="{'' if store is None or store.wb_threshold_percent is None else store.wb_threshold_percent}"></label>
          <label>WB fallback no promo <input type="number" name="wb_fallback_no_promo_percent" value="{'' if store is None or store.wb_fallback_no_promo_percent is None else store.wb_fallback_no_promo_percent}"></label>
          <label>WB fallback over threshold <input type="number" name="wb_fallback_over_threshold_percent" value="{'' if store is None or store.wb_fallback_over_threshold_percent is None else store.wb_fallback_over_threshold_percent}"></label>
        """
    archive_actions = ""
    assignments = ""
    if store is not None:
        if store.can_archive:
            archive_actions += f'<button type="button" class="secondary action-button" data-action-path="/api/stores/{store.id}/archive">Архивировать</button>'
        if store.can_restore:
            archive_actions += f'<button type="button" class="secondary action-button" data-action-path="/api/stores/{store.id}/restore">Восстановить</button>'
        if store.marketplace == "wb" and store.can_edit:
            archive_actions += f'<button type="button" class="secondary action-button" data-settings-path="/api/stores/{store.id}/settings">Сохранить WB settings</button>'
        assigned_ids = {user.id for user in assigned_users}
        assignment_rows = "\n".join(
            f"""
            <li>
              <span>{escape(user.username)} ({escape(user.role_name)})</span>
              <button type="button" class="secondary action-button" data-action-path="/api/access/users/{user.id}/stores/{store.id}" data-action-method="DELETE">Удалить доступ</button>
            </li>
            """
            for user in assigned_users
        ) or "<li>Нет назначенных пользователей</li>"
        available_rows = "\n".join(
            f"""
            <li>
              <span>{escape(user.username)} ({escape(user.role_name)})</span>
              <button type="button" class="secondary action-button" data-action-path="/api/access/users/{user.id}/stores/{store.id}" data-action-method="POST">Назначить</button>
            </li>
            """
            for user in available_users
            if user.id not in assigned_ids
        ) or "<li>Нет пользователей для назначения</li>"
        assignments = f"""
        <section class="panel">
          <h2>Назначенные пользователи</h2>
          <ul class="link-list">{assignment_rows}</ul>
          <h3>Добавить пользователя</h3>
          <ul class="link-list">{available_rows}</ul>
        </section>
        """
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>{escape(title)}</h1>
        <form class="json-form store-form" data-api-path="{escape(api_path)}" data-method="{escape(method)}" data-success-redirect="/stores">
          <label>Название <input type="text" name="name" value="{escape('' if store is None else store.name)}" required></label>
          <label>Marketplace
            <select name="marketplace" {"disabled" if store is not None else ""}>
              {_options(("wb", "ozon"), marketplace)}
            </select>
          </label>
          {settings}
          <div class="actions">
            <button type="submit">Сохранить</button>
            {archive_actions}
          </div>
          <p class="message" data-form-message></p>
        </form>
      </section>
      {assignments}
    </main>
    """
    return _document(title, state, body)


def processing_page(
    state: UiPageState,
    *,
    title: str,
    module_code: str,
    stores: tuple[StoreViewModel, ...],
    selected_store_id: int | None,
    temp_files: TemporaryFileListViewModel | None,
    run_page: RunPageReadModel | None,
) -> str:
    selector_options = '\n'.join(
        f'<option value="{item.id}" {"selected" if item.id == selected_store_id else ""}>{escape(item.name)} ({escape(item.status)})</option>'
        for item in stores
    )
    no_store = ""
    if not stores:
        no_store = '<section class="panel"><h1>{}</h1><p>Нет доступных магазинов</p></section>'.format(escape(title))
        return _document(title, state, f"<main>{no_store}</main>")
    file_rows = ""
    if temp_files is not None:
        file_rows = "\n".join(
            f"""
            <tr>
              <td>{escape(item.original_filename)}</td>
              <td>{item.file_size_bytes}</td>
              <td>{_fmt_dt(item.uploaded_at_utc)}</td>
              <td>{escape(item.wb_file_kind or '-')}</td>
              <td>
                <button type="button" class="secondary temp-delete" data-file-id="{item.id}">Удалить</button>
                <form class="temp-replace-form" data-file-id="{item.id}">
                  <input type="file" name="file" accept=".xlsx" required>
                  {"<select name='wb_file_kind'><option value='price'>price</option><option value='promo'>promo</option></select>" if module_code == "wb" else ""}
                  <button type="submit" class="secondary">Заменить</button>
                </form>
              </td>
            </tr>
            """
            for item in temp_files.items
        ) or '<tr><td colspan="5">Активный набор пуст</td></tr>'
    preview = ""
    if run_page is not None:
        preview_rows = "\n".join(
            f"<tr><td>{item.row_number}</td><td>{escape(item.severity)}</td><td>{escape(item.decision_reason or '-')}</td><td>{escape(item.message)}</td></tr>"
            for item in run_page.detail_audit.items[:10]
        ) or '<tr><td colspan="4">Детальный аудит отсутствует</td></tr>'
        result_link = ""
        if run_page.run.result_file_id is not None and run_page.run.result_file_is_available:
            result_link = f'<a class="button-link" href="/api/run-files/{run_page.run.result_file_id}/download">Скачать результат</a>'
        preview = f"""
        <section class="panel">
          <h2>Последний запуск</h2>
          <p data-run-status data-run-id="{run_page.run.run_id}">
            <strong>{escape(run_page.run.public_run_number)}</strong>:
            <span data-run-field="lifecycle_status">{escape(run_page.run.lifecycle_status)}</span> /
            <span data-run-field="business_result">{escape(run_page.run.business_result or '-')}</span>
          </p>
          <p>{escape(run_page.run.short_result_text or '-')}</p>
          <p><a href="/runs/{escape(run_page.run.public_run_number)}">Открыть run page</a> {result_link}</p>
          <h3>Summary audit</h3>
          <pre>{escape(json.dumps(run_page.summary_audit_json or {}, ensure_ascii=False, indent=2))}</pre>
          <h3>Preview detail audit</h3>
          <table>
            <thead><tr><th>Row</th><th>Severity</th><th>Decision</th><th>Message</th></tr></thead>
            <tbody>{preview_rows}</tbody>
          </table>
        </section>
        """
    kind_field = ""
    if module_code == "wb":
        kind_field = """
        <label>WB file kind
          <select name="wb_file_kind">
            <option value="price">price</option>
            <option value="promo">promo</option>
          </select>
        </label>
        <p class="muted">Ограничения: 1 price, 1-20 promo, 25 МБ на файл, 100 МБ на набор.</p>
        """
    else:
        kind_field = '<p class="muted">Ограничение: ровно 1 файл .xlsx до 25 МБ.</p>'
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>{escape(title)}</h1>
        <form id="processing-store-form">
          <label>Магазин
            <select name="store_id">{selector_options}</select>
          </label>
          <button type="submit">Открыть</button>
        </form>
      </section>
      <section class="panel">
        <h2>Загрузка файлов</h2>
        <form id="upload-form" data-module-code="{module_code}">
          {kind_field}
          <label>Файл <input type="file" name="file" accept=".xlsx" required></label>
          <button type="submit">Загрузить</button>
          <p class="message" id="upload-message"></p>
        </form>
      </section>
      <section class="panel">
        <h2>Активный временный набор</h2>
        <table>
          <thead><tr><th>Файл</th><th>Размер</th><th>Загружен</th><th>Kind</th><th>Actions</th></tr></thead>
          <tbody>{file_rows}</tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Действия</h2>
        <p><button type="button" class="run-action" data-operation="check">Проверить</button></p>
        <p><button type="button" class="run-action" data-operation="process">Обработать</button></p>
        <p class="message" id="run-message"></p>
      </section>
      {preview}
    </main>
    <script>
    document.getElementById("processing-store-form").addEventListener("submit", (event) => {{
      event.preventDefault();
      const storeId = event.currentTarget.store_id.value;
      window.location.assign("/processing/{module_code}?store_id=" + encodeURIComponent(storeId));
    }});
    const uploadForm = document.getElementById("upload-form");
    const selectedStoreId = {json.dumps(selected_store_id)};
    async function fileToBase64(file) {{
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (const value of bytes) {{
        binary += String.fromCharCode(value);
      }}
      return btoa(binary);
    }}
    uploadForm?.addEventListener("submit", async (event) => {{
      event.preventDefault();
      if (!selectedStoreId) {{
        document.getElementById("upload-message").textContent = "Сначала выберите магазин";
        return;
      }}
      const file = uploadForm.file.files[0];
      if (!file) {{
        document.getElementById("upload-message").textContent = "Выберите файл";
        return;
      }}
      const payload = {{
        original_filename: file.name,
        content_base64: await fileToBase64(file),
        mime_type: file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }};
      const wbKindField = uploadForm.querySelector("[name=wb_file_kind]");
      if (wbKindField) {{
        payload.wb_file_kind = wbKindField.value;
      }}
      const response = await window.promoUi.apiFetch(`/api/temp-files?store_id=${{selectedStoreId}}&module_code={module_code}`, {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(payload),
      }});
      if (!response.ok) {{
        const body = await response.json().catch(() => ({{}}));
        document.getElementById("upload-message").textContent = body.error_message || "Не удалось загрузить файл";
        return;
      }}
      window.location.reload();
    }});
    document.querySelectorAll(".temp-delete").forEach((button) => button.addEventListener("click", async () => {{
      const response = await window.promoUi.apiFetch(`/api/temp-files/${{button.dataset.fileId}}`, {{method: "DELETE"}});
      if (response.ok) {{
        window.location.reload();
      }}
    }}));
    document.querySelectorAll(".run-action").forEach((button) => button.addEventListener("click", async () => {{
      if (!selectedStoreId) {{
        document.getElementById("run-message").textContent = "Сначала выберите магазин";
        return;
      }}
      const response = await window.promoUi.apiFetch(`/api/runs/${{button.dataset.operation}}`, {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{store_id: Number(selectedStoreId)}}),
      }});
      const body = await response.json().catch(() => ({{}}));
      if (!response.ok) {{
        document.getElementById("run-message").textContent = body.error_message || "Не удалось создать запуск";
        return;
      }}
      window.location.assign(`/runs/${{body.public_run_number}}`);
    }}));
    </script>
    """
    return _document(title, state, body)


def history_page(state: UiPageState, history: HistoryPageViewModel, *, current_query: dict[str, object | None]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td><a href="/runs/{escape(item.public_run_number)}">{escape(item.public_run_number)}</a></td>
          <td>{escape(item.store_name)}</td>
          <td>{escape(item.module_code)}</td>
          <td>{escape(item.initiated_by_username)}</td>
          <td>{escape(item.operation_type)}</td>
          <td>{escape(item.lifecycle_status)}</td>
          <td>{escape(item.business_result or '-')}</td>
          <td>{escape(item.short_result_text or '-')}</td>
        </tr>
        """
        for item in history.items
    ) or '<tr><td colspan="8">История пуста</td></tr>'
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>История запусков</h1>
        <form method="get" class="filter-grid">
          <label>Search <input type="text" name="search" value="{escape(str(current_query.get('search') or ''))}"></label>
          <label>Store ID <input type="number" name="store_id" value="{escape(str(current_query.get('store_id') or ''))}"></label>
          <label>User ID <input type="number" name="initiated_by_user_id" value="{escape(str(current_query.get('initiated_by_user_id') or ''))}"></label>
          <label>Marketplace <select name="marketplace">{_options_with_blank(("wb", "ozon"), _to_str(current_query.get("marketplace")))}</select></label>
          <label>Module <select name="module_code">{_options_with_blank(("wb", "ozon"), _to_str(current_query.get("module_code")))}</select></label>
          <label>Operation <select name="operation_type">{_options_with_blank(("check", "process"), _to_str(current_query.get("operation_type")))}</select></label>
          <label>Status <input type="text" name="lifecycle_status" value="{escape(str(current_query.get('lifecycle_status') or ''))}"></label>
          <label>Business result <input type="text" name="business_result" value="{escape(str(current_query.get('business_result') or ''))}"></label>
          <label>Store status <select name="store_status">{_options_with_blank(("active", "archived"), _to_str(current_query.get("store_status")))}</select></label>
          <label>Started from UTC <input type="text" name="started_from_utc" value="{escape(str(current_query.get('started_from_utc') or ''))}"></label>
          <label>Started to UTC <input type="text" name="started_to_utc" value="{escape(str(current_query.get('started_to_utc') or ''))}"></label>
          <label>Sort <select name="sort_field">{_options(("started_at_utc", "finished_at_utc", "public_run_number", "store_name", "initiated_by_username", "operation_type", "lifecycle_status", "business_result"), _to_str(current_query.get("sort_field")) or "started_at_utc")}</select></label>
          <label>Descending <select name="descending">{_options(("true", "false"), "true" if current_query.get("descending") else "false")}</select></label>
          <label>Page size <select name="page_size">{_options(("25", "50", "100"), str(current_query.get("page_size") or history.page_size))}</select></label>
          <input type="hidden" name="page" value="1">
          <div class="actions"><button type="submit">Применить</button></div>
        </form>
        <table>
          <thead><tr><th>Run</th><th>Store</th><th>Module</th><th>By</th><th>Operation</th><th>Status</th><th>Result</th><th>Summary</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        {_pagination("/runs", history.page, history.page_size, history.total_items, current_query)}
      </section>
    </main>
    """
    return _document("Run History", state, body)


def logs_page(state: UiPageState, logs: LogsPageViewModel, *, current_query: dict[str, object | None]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{_fmt_dt(item.event_time_utc)}</td>
          <td>{escape(item.severity)}</td>
          <td>{escape(item.event_type)}</td>
          <td>{escape(item.username or '-')}</td>
          <td>{escape(item.store_name or '-')}</td>
          <td>{escape(item.public_run_number or '-')}</td>
          <td>{escape(item.message)}</td>
        </tr>
        """
        for item in logs.items
    ) or '<tr><td colspan="7">Логи отсутствуют</td></tr>'
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>Logs</h1>
        <form method="get" class="filter-grid">
          <label>Search <input type="text" name="search" value="{escape(str(current_query.get('search') or ''))}"></label>
          <label>User ID <input type="number" name="user_id" value="{escape(str(current_query.get('user_id') or ''))}"></label>
          <label>Store ID <input type="number" name="store_id" value="{escape(str(current_query.get('store_id') or ''))}"></label>
          <label>Module <select name="module_code">{_options_with_blank(("wb", "ozon"), _to_str(current_query.get("module_code")))}</select></label>
          <label>Event type <input type="text" name="event_type" value="{escape(str(current_query.get('event_type') or ''))}"></label>
          <label>Severity <select name="severity">{_options_with_blank(("debug", "info", "warning", "error"), _to_str(current_query.get("severity")))}</select></label>
          <label>Run ID <input type="number" name="run_id" value="{escape(str(current_query.get('run_id') or ''))}"></label>
          <label>Public run number <input type="text" name="public_run_number" value="{escape(str(current_query.get('public_run_number') or ''))}"></label>
          <label>From UTC <input type="text" name="event_from_utc" value="{escape(str(current_query.get('event_from_utc') or ''))}"></label>
          <label>To UTC <input type="text" name="event_to_utc" value="{escape(str(current_query.get('event_to_utc') or ''))}"></label>
          <label>Sort <select name="sort_field">{_options(("event_time_utc", "severity", "event_type", "username", "store_name"), _to_str(current_query.get("sort_field")) or "event_time_utc")}</select></label>
          <label>Descending <select name="descending">{_options(("true", "false"), "true" if current_query.get("descending") else "false")}</select></label>
          <label>Page size <select name="page_size">{_options(("25", "50", "100"), str(current_query.get("page_size") or logs.page_size))}</select></label>
          <input type="hidden" name="page" value="1">
          <div class="actions"><button type="submit">Применить</button></div>
        </form>
        <table>
          <thead><tr><th>Time</th><th>Severity</th><th>Event</th><th>User</th><th>Store</th><th>Run</th><th>Message</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        {_pagination("/logs", logs.page, logs.page_size, logs.total_items, current_query)}
      </section>
    </main>
    """
    return _document("Logs", state, body)


def run_page(state: UiPageState, model: RunPageReadModel, *, current_query: dict[str, object | None]) -> str:
    result_action = ""
    if model.run.result_file_id is not None:
        if model.run.result_file_is_available:
            result_action = (
                f'<p><a class="button-link" href="/api/run-files/{model.run.result_file_id}/download">'
                "Скачать результат"
                "</a></p>"
            )
        else:
            result_action = (
                "<p class=\"muted\">Результат недоступен"
                f" ({escape(model.run.result_file_unavailable_reason or 'unknown')})"
                "</p>"
            )
    file_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.file_role)}</td>
          <td>{escape(item.original_filename)}</td>
          <td>{item.file_size_bytes}</td>
          <td>{'Да' if item.is_available else 'Нет'}</td>
          <td>{escape(item.unavailable_reason or '-')}</td>
          <td>{f'<a href="/api/run-files/{item.id}/download">Скачать</a>' if item.is_available else '<span class="muted">Файл недоступен</span>'}</td>
        </tr>
        """
        for item in model.files
    ) or '<tr><td colspan="6">Файлы отсутствуют</td></tr>'
    detail_rows = "\n".join(
        f"""
        <tr>
          <td>{item.row_number}</td>
          <td>{escape(item.entity_key_1 or '-')}</td>
          <td>{escape(item.entity_key_2 or '-')}</td>
          <td>{escape(item.severity)}</td>
          <td>{escape(item.decision_reason or '-')}</td>
          <td>{escape(item.message)}</td>
        </tr>
        """
        for item in model.detail_audit.items
    ) or '<tr><td colspan="6">Детальный аудит отсутствует</td></tr>'
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>Run {escape(model.run.public_run_number)}</h1>
        <dl class="details-grid" data-run-status data-run-id="{model.run.run_id}">
          <dt>Store</dt><dd>{escape(model.run.store_name)}</dd>
          <dt>Marketplace</dt><dd>{escape(model.run.marketplace)}</dd>
          <dt>Module</dt><dd>{escape(model.run.module_code)}</dd>
          <dt>Initiated by</dt><dd>{escape(model.run.initiated_by_username)}</dd>
          <dt>Operation</dt><dd>{escape(model.run.operation_type)}</dd>
          <dt>Started</dt><dd>{_fmt_dt(model.run.started_at_utc)}</dd>
          <dt>Finished</dt><dd>{_fmt_dt(model.run.finished_at_utc)}</dd>
          <dt>Status</dt><dd><span data-run-field="lifecycle_status">{escape(model.run.lifecycle_status)}</span></dd>
          <dt>Result</dt><dd><span data-run-field="business_result">{escape(model.run.business_result or '-')}</span></dd>
          <dt>Summary</dt><dd>{escape(model.run.short_result_text or '-')}</dd>
        </dl>
        {result_action}
      </section>
      <section class="panel">
        <h2>Файлы запуска</h2>
        <table>
          <thead><tr><th>Role</th><th>Filename</th><th>Size</th><th>Available</th><th>Reason</th><th>Download</th></tr></thead>
          <tbody>{file_rows}</tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Summary audit</h2>
        <pre>{escape(json.dumps(model.summary_audit_json or {}, ensure_ascii=False, indent=2))}</pre>
      </section>
      <section class="panel">
        <h2>Detail audit</h2>
        <form method="get" class="filter-grid">
          <label>Search <input type="text" name="search" value="{escape(str(current_query.get('search') or ''))}"></label>
          <label>Severity <input type="text" name="severity" value="{escape(str(current_query.get('severity') or ''))}"></label>
          <label>Decision reason <input type="text" name="decision_reason" value="{escape(str(current_query.get('decision_reason') or ''))}"></label>
          <label>Row from <input type="number" name="row_number_from" value="{escape(str(current_query.get('row_number_from') or ''))}"></label>
          <label>Row to <input type="number" name="row_number_to" value="{escape(str(current_query.get('row_number_to') or ''))}"></label>
          <label>Has entity key 1 <select name="has_entity_key_1">{_options_with_blank(("true", "false"), _bool_to_query(current_query.get("has_entity_key_1")))}</select></label>
          <label>Sort <select name="sort_field">{_options(("row_number", "severity", "decision_reason", "entity_key_1"), _to_str(current_query.get("sort_field")) or "row_number")}</select></label>
          <label>Descending <select name="descending">{_options(("true", "false"), "true" if current_query.get("descending") else "false")}</select></label>
          <label>Page size <select name="page_size">{_options(("25", "50", "100"), str(current_query.get("page_size") or model.detail_audit.page_size))}</select></label>
          <input type="hidden" name="page" value="1">
          <div class="actions"><button type="submit">Применить</button></div>
        </form>
        <table>
          <thead><tr><th>Row</th><th>Entity 1</th><th>Entity 2</th><th>Severity</th><th>Decision</th><th>Message</th></tr></thead>
          <tbody>{detail_rows}</tbody>
        </table>
        {_pagination(f"/runs/{model.run.public_run_number}", model.detail_audit.page, model.detail_audit.page_size, model.detail_audit.total_items, current_query)}
      </section>
    </main>
    """
    return _document(f"Run {model.run.public_run_number}", state, body)


def password_page(state: UiPageState) -> str:
    body = """
    <main class="page-grid">
      <section class="panel">
        <h1>Смена пароля</h1>
        <form class="json-form" data-api-path="/api/auth/change-password" data-method="POST" data-success-message="Пароль обновлён">
          <label>Текущий пароль <input type="password" name="current_password" required></label>
          <label>Новый пароль <input type="password" name="new_password" required></label>
          <label>Подтверждение нового пароля <input type="password" name="confirm_new_password" required></label>
          <button type="submit">Сохранить</button>
          <p class="message" data-form-message></p>
        </form>
      </section>
    </main>
    """
    return _document("Change Password", state, body)


def error_page(title: str, message: str, *, state: UiPageState | None = None) -> str:
    body = f"""
    <main class="page-grid">
      <section class="panel">
        <h1>{escape(title)}</h1>
        <p>{escape(message)}</p>
      </section>
    </main>
    """
    return _document(title, state, body)


def _document(title: str, state: UiPageState | None, body: str) -> str:
    nav = ""
    header = ""
    if state is not None:
        nav = f"""
        <nav class="side-nav">
          <p class="brand">promo</p>
          <ul class="link-list">{_menu_links(state.menu)}</ul>
          <p class="muted">{escape(state.username)} · {escape(state.role_name)}</p>
          <p><a href="/profile/password">Change Password</a></p>
          <p><a href="/logout">Logout</a></p>
        </nav>
        """
        header = '<div class="shell">'
    else:
        header = '<div class="shell shell-auth">'
    return f"""<!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(title)}</title>
        <style>{_styles()}</style>
      </head>
      <body>
        {header}
          {nav}
          <div class="content">
            {body}
          </div>
        </div>
        <script>{_shared_script()}</script>
      </body>
    </html>
    """


def _menu_links(menu: MenuVisibilityViewModel) -> str:
    links: list[str] = []
    if menu.show_dashboard:
        links.append('<li><a href="/dashboard">Dashboard</a></li>')
    if menu.show_users:
        links.append('<li><a href="/users">Users</a></li>')
    if menu.show_stores:
        links.append('<li><a href="/stores">Stores</a></li>')
    if menu.show_wb:
        links.append('<li><a href="/processing/wb">Wildberries</a></li>')
    if menu.show_ozon:
        links.append('<li><a href="/processing/ozon">Ozon</a></li>')
    if menu.show_history:
        links.append('<li><a href="/runs">Run History</a></li>')
    if menu.show_logs:
        links.append('<li><a href="/logs">Logs</a></li>')
    return "\n".join(links)


def _styles() -> str:
    return """
    :root {
      --bg: #f4f1ea;
      --panel: #fffaf2;
      --line: #d3c8b3;
      --text: #1f1d19;
      --muted: #6b6558;
      --accent: #8f5a29;
      --danger: #a12d23;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #efe5d2, var(--bg)); color: var(--text); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .shell { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
    .shell-auth { display: block; }
    .side-nav { padding: 24px; border-right: 1px solid var(--line); background: rgba(255,255,255,0.6); }
    .brand { margin: 0 0 24px; font-size: 28px; text-transform: lowercase; letter-spacing: 0.08em; }
    .content { padding: 24px; }
    .page-grid { display: grid; gap: 16px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 18px; box-shadow: 0 6px 20px rgba(90,72,42,0.08); }
    .panel-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    .auth-card { max-width: 440px; margin: 10vh auto; background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 24px; box-shadow: 0 10px 30px rgba(90,72,42,0.12); }
    .link-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
    label { display: grid; gap: 6px; margin-bottom: 12px; font-weight: 600; }
    input, select, button, textarea { font: inherit; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line); background: #fff; }
    button, .button-link { display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; background: var(--accent); color: #fff; border: none; cursor: pointer; border-radius: 999px; }
    .secondary { background: #f1e5d0; color: var(--text); border: 1px solid var(--line); }
    .button-link:hover { text-decoration: none; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 16px; }
    .message { min-height: 1.2em; color: var(--muted); }
    .message.error { color: var(--danger); }
    .muted { color: var(--muted); }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
    .details-grid { display: grid; grid-template-columns: 180px 1fr; gap: 8px 12px; margin: 0; }
    .details-grid dt { font-weight: 700; }
    .details-grid dd { margin: 0; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f8f2e8; padding: 12px; border-radius: 10px; }
    .pagination { margin-top: 12px; color: var(--muted); }
    @media (max-width: 960px) {
      .shell { grid-template-columns: 1fr; }
      .side-nav { border-right: 0; border-bottom: 1px solid var(--line); }
      .details-grid { grid-template-columns: 1fr; }
    }
    """


def _shared_script() -> str:
    return """
    window.promoUi = {
      getSessionToken() {
        const match = document.cookie.match(/(?:^|; )promo_session_token=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : null;
      },
      async apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        const token = window.promoUi.getSessionToken();
        if (token) {
          headers.set("X-Session-Token", token);
        }
        return fetch(url, {...options, headers});
      },
    };
    document.querySelectorAll(".json-form").forEach((form) => form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {};
      for (const element of form.elements) {
        if (!(element instanceof HTMLElement) || !element.getAttribute || !element.name) {
          continue;
        }
        if (element.type === "button" || element.type === "submit") {
          continue;
        }
        let value = element.value;
        if (element.name === "permission_codes") {
          value = value ? value.split(",").map((item) => item.trim()).filter(Boolean) : [];
        } else if (element.type === "number") {
          value = value === "" ? null : Number(value);
        }
        payload[element.name] = value;
      }
      if (Object.prototype.hasOwnProperty.call(payload, "confirm_new_password")) {
        if (payload.new_password !== payload.confirm_new_password) {
          const message = form.querySelector("[data-form-message]");
          if (message) {
            message.textContent = "Подтверждение пароля не совпадает";
            message.classList.add("error");
          }
          return;
        }
        delete payload.confirm_new_password;
      }
      if (form.classList.contains("store-form") && form.dataset.method === "PATCH" && payload.marketplace) {
        delete payload.marketplace;
      }
      const response = await window.promoUi.apiFetch(form.dataset.apiPath, {
        method: form.dataset.method || "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const message = form.querySelector("[data-form-message]");
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (message) {
          message.textContent = body.error_message || "Операция завершилась ошибкой";
          message.classList.add("error");
        }
        return;
      }
      if (message) {
        message.textContent = form.dataset.successMessage || "Сохранено";
        message.classList.remove("error");
      }
      if (form.dataset.successRedirect) {
        window.location.assign(form.dataset.successRedirect);
      }
    }));
    document.querySelectorAll(".action-button").forEach((button) => button.addEventListener("click", async () => {
      const apiPath = button.dataset.actionPath;
      if (!apiPath) {
        return;
      }
      const response = await window.promoUi.apiFetch(apiPath, {method: button.dataset.actionMethod || "POST"});
      if (response.ok) {
        window.location.reload();
      }
    }));
    document.querySelectorAll(".grant-permission-form").forEach((form) => form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const permissionCode = form.permission_code.value.trim();
      if (!permissionCode) {
        return;
      }
      const response = await window.promoUi.apiFetch(`/api/users/${form.dataset.userId}/permissions/${encodeURIComponent(permissionCode)}`, {method: "POST"});
      const body = await response.json().catch(() => ({}));
      const message = form.querySelector("[data-form-message]");
      if (!response.ok) {
        if (message) {
          message.textContent = body.error_message || "Не удалось назначить permission";
          message.classList.add("error");
        }
        return;
      }
      window.location.reload();
    }));
    document.querySelectorAll("[data-settings-path]").forEach((button) => button.addEventListener("click", async () => {
      const form = button.closest("form");
      if (!form) {
        return;
      }
      const payload = {
        wb_threshold_percent: form.wb_threshold_percent.value === "" ? null : Number(form.wb_threshold_percent.value),
        wb_fallback_no_promo_percent: form.wb_fallback_no_promo_percent.value === "" ? null : Number(form.wb_fallback_no_promo_percent.value),
        wb_fallback_over_threshold_percent: form.wb_fallback_over_threshold_percent.value === "" ? null : Number(form.wb_fallback_over_threshold_percent.value),
      };
      const response = await window.promoUi.apiFetch(button.dataset.settingsPath, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        window.location.reload();
      }
    }));
    document.querySelectorAll("[data-run-status]").forEach((container) => {
      const runId = container.dataset.runId;
      if (!runId) {
        return;
      }
      const lifecycleNode = container.querySelector("[data-run-field=lifecycle_status]");
      const resultNode = container.querySelector("[data-run-field=business_result]");
      const refresh = async () => {
        const response = await window.promoUi.apiFetch(`/api/runs/${runId}/status`);
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (lifecycleNode) {
          lifecycleNode.textContent = payload.lifecycle_status;
        }
        if (resultNode) {
          resultNode.textContent = payload.business_result || "-";
        }
        if (!["completed", "failed"].includes(payload.lifecycle_status)) {
          window.setTimeout(refresh, 2000);
        }
      };
      if (lifecycleNode && !["completed", "failed"].includes(lifecycleNode.textContent.trim())) {
        window.setTimeout(refresh, 2000);
      }
    });
    document.querySelectorAll(".temp-replace-form").forEach((form) => form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const file = form.file.files[0];
      if (!file) {
        return;
      }
      const payload = {
        original_filename: file.name,
        content_base64: await fileToBase64(file),
        mime_type: file.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      };
      if (form.wb_file_kind) {
        payload.wb_file_kind = form.wb_file_kind.value;
      }
      const response = await window.promoUi.apiFetch(`/api/temp-files/${form.dataset.fileId}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        window.location.reload();
      }
    }));
    """


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat()


def _options(values: Iterable[str], selected: str | None) -> str:
    return "\n".join(
        f'<option value="{escape(value)}" {"selected" if value == selected else ""}>{escape(value)}</option>'
        for value in values
    )


def _options_with_blank(values: Iterable[str], selected: str | None) -> str:
    return '<option value=""></option>' + _options(values, selected)


def _to_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _bool_to_query(value: object | None) -> str | None:
    if value in (None, ""):
        return None
    return "true" if value is True or value in ("true", "True", 1, "1") else "false"


def _pagination(base_path: str, page: int, page_size: int, total_items: int, current_query: dict[str, object | None]) -> str:
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    prev_link = '<span class="button-link secondary disabled" aria-disabled="true">Предыдущая</span>'
    next_link = '<span class="button-link secondary disabled" aria-disabled="true">Следующая</span>'
    if page > 1:
        prev_link = f'<a class="button-link secondary" rel="prev" href="{escape(_page_href(base_path, current_query, page - 1))}">Предыдущая</a>'
    if page < total_pages:
        next_link = f'<a class="button-link secondary" rel="next" href="{escape(_page_href(base_path, current_query, page + 1))}">Следующая</a>'
    return f'''
    <div class="pagination">
      <p>Страница {page} из {total_pages}, размер {page_size}, всего {total_items}</p>
      <div class="actions">{prev_link}{next_link}</div>
    </div>
    '''


def _page_href(base_path: str, current_query: dict[str, object | None], page: int) -> str:
    params: dict[str, str] = {"page": str(page)}
    for key, value in current_query.items():
        if key == "page" or value in (None, "", False):
            continue
        if value is True:
            params[key] = "true"
            continue
        params[key] = str(value)
    return base_path + "?" + urlencode(params)
