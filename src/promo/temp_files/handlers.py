from __future__ import annotations

from promo.shared.enums import ModuleCode
from promo.temp_files.contracts import TemporaryFileUploadForm
from promo.temp_files.presentation import TemporaryFileListViewModel, TemporaryFileViewModel
from promo.temp_files.service import TemporaryFileService


def upload_temp_file_handler(
    service: TemporaryFileService,
    uploaded_by_user_id: int,
    store_id: int,
    module_code: ModuleCode,
    form: TemporaryFileUploadForm,
) -> TemporaryFileViewModel:
    return service._to_view_model(service.upload_file(uploaded_by_user_id, store_id, module_code, form))


def replace_temp_file_handler(service: TemporaryFileService, file_id: int, form: TemporaryFileUploadForm) -> TemporaryFileViewModel:
    return service._to_view_model(service.replace_file(file_id, form))


def delete_temp_file_handler(service: TemporaryFileService, file_id: int) -> None:
    service.delete_file(file_id)


def list_active_temp_files_handler(
    service: TemporaryFileService,
    uploaded_by_user_id: int,
    store_id: int,
    module_code: ModuleCode,
) -> TemporaryFileListViewModel:
    return service.list_active_files(uploaded_by_user_id, store_id, module_code)

