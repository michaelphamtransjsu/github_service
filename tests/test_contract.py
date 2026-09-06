from pathlib import Path

import yaml
from openapi_spec_validator import validate

from app.main import app


def test_openapi_document_is_valid_31():
    document = yaml.safe_load(Path("openapi.yaml").read_text())
    assert document["openapi"].startswith("3.1.")
    validate(document)


def operations(document):
    return {
        (path, method)
        for path, item in document["paths"].items()
        for method in item
        if method in {"get", "post", "patch", "delete"}
    }


def test_checked_in_operations_match_application():
    checked = yaml.safe_load(Path("openapi.yaml").read_text())
    assert operations(checked) == operations(app.openapi())
    assert len(operations(checked)) == 9
    assert "CommentUpdate" not in checked["components"]["schemas"]
    assert "CommentId" not in checked["components"]["parameters"]
    for path, method in operations(checked):
        operation = checked["paths"][path][method]
        assert operation["operationId"]
        assert "400" in operation["responses"]
        for response in operation["responses"].values():
            if "$ref" in response and not response["$ref"].endswith(
                (
                    "BadRequest",
                    "Unauthorized",
                    "NotFound",
                    "PayloadTooLarge",
                    "RateLimited",
                    "UpstreamUnavailable",
                    "UpstreamTimeout",
                )
            ):
                raise AssertionError("error response does not use reusable Error schema")
