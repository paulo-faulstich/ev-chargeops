from typing import Any

from app.main import app


def _operation(path: str, method: str) -> dict[str, Any]:
    return app.openapi()["paths"][path][method]


def test_import_openapi_declares_shared_auth_error_responses() -> None:
    operations = (
        _operation("/v1/import-batches/preview", "post"),
        _operation("/v1/import-batches", "post"),
        _operation("/v1/import-batches", "get"),
        _operation("/v1/import-batches/{batch_id}", "get"),
    )

    for operation in operations:
        responses = operation["responses"]
        assert responses["401"] == {
            "description": "Invalid or missing bearer token.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HttpErrorResponse"}
                }
            },
        }
        assert responses["403"] == {
            "description": "Organization membership required.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HttpErrorResponse"}
                }
            },
        }


def test_import_detail_openapi_declares_not_found_response() -> None:
    responses = _operation("/v1/import-batches/{batch_id}", "get")["responses"]

    assert responses["404"] == {
        "description": "Import batch not found.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HttpErrorResponse"}
            }
        },
    }
