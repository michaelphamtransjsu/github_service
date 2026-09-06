from pathlib import Path

import yaml
from openapi_spec_validator import validate


def test_openapi_document_is_valid_31() -> None:
    document = yaml.safe_load(Path("openapi.yaml").read_text())

    assert document["openapi"].startswith("3.1.")
    validate(document)


def test_all_assignment_operations_have_ids_and_error_contracts() -> None:
    document = yaml.safe_load(Path("openapi.yaml").read_text())
    operations = [
        operation
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "patch", "delete"}
    ]

    assert len(operations) == 11
    assert len({operation["operationId"] for operation in operations}) == len(operations)
    for operation in operations:
        assert any(code in operation["responses"] for code in ("4XX", "422"))
