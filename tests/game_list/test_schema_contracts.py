"""Contract tests: every part of the OpenAPI schema must be documented.

These tests generate the full OpenAPI schema and assert that all tags,
operations, and query parameters carry non-empty descriptions.  They
start RED and turn GREEN progressively as the documentation issues land.
"""

from typing import Any

import pytest
from drf_spectacular.generators import SchemaGenerator

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})


@pytest.fixture(scope="module")
def openapi_schema() -> dict[str, Any]:
    """Generate the full OpenAPI schema once per test module."""
    schema: dict[str, Any] = SchemaGenerator().get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    return schema


def test_schema_tags_all_have_descriptions(openapi_schema: dict[str, Any]) -> None:
    """Every tag declared in SPECTACULAR_SETTINGS['TAGS'] must carry a non-empty description."""
    tags: list[dict[str, Any]] = openapi_schema.get("tags", [])
    assert tags, "Schema must declare at least one tag; populate SPECTACULAR_SETTINGS['TAGS']."
    missing = [t["name"] for t in tags if not str(t.get("description", "")).strip()]
    assert not missing, f"Tags missing descriptions: {missing}"


def test_schema_operations_all_have_descriptions(openapi_schema: dict[str, Any]) -> None:
    """Every HTTP operation exposed in the schema must carry a non-empty description."""
    paths: dict[str, Any] = openapi_schema.get("paths", {})
    missing: list[str] = []
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            if not str(operation.get("description", "")).strip():
                missing.append(f"{method.upper()} {path}")
    assert not missing, "Operations missing descriptions:\n" + "\n".join(f"  {m}" for m in sorted(missing))


def test_schema_query_parameters_all_have_descriptions(openapi_schema: dict[str, Any]) -> None:
    """Every query parameter on every operation must carry a non-empty description."""
    paths: dict[str, Any] = openapi_schema.get("paths", {})
    missing: list[str] = []
    for path, path_item in paths.items():
        # Exclude drf-spectacular's own schema/swagger endpoints — not our API surface.
        if path.startswith("/api/schema"):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            missing.extend(
                f"{method.upper()} {path} ?{param.get('name')}"
                for param in operation.get("parameters", [])
                if param.get("in") == "query" and not str(param.get("description", "")).strip()
            )
    assert not missing, "Query parameters missing descriptions:\n" + "\n".join(f"  {m}" for m in sorted(missing))
