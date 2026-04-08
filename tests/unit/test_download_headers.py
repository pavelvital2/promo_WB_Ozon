from promo.presentation.app import _attachment_content_disposition


def test_attachment_content_disposition_supports_non_ascii_filename() -> None:
    header = _attachment_content_disposition("Шаблон обновления цен.xlsx")

    assert header.startswith('attachment; filename="')
    assert 'filename*=UTF-8\'\'' in header
    assert "%D0%A8" in header
    assert "Шаблон" not in header.split("filename=", 1)[1].split(";", 1)[0]
