"""OpenAI adapter request-shape checks. No live provider calls."""

from __future__ import annotations

from voltdesk.llm.openai_provider import _strict_json_schema


def test_strict_schema_requires_all_properties_without_changing_the_source() -> None:
    source = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "source_page": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "default": None,
            },
        },
        "required": ["value"],
    }

    strict = _strict_json_schema(source)

    assert strict["required"] == ["value", "source_page"]
    assert strict["additionalProperties"] is False
    assert "default" not in strict["properties"]["source_page"]
    assert source["required"] == ["value"]
    assert source["properties"]["source_page"]["default"] is None


def test_strict_schema_normalises_defs_and_ref_siblings() -> None:
    source = {
        "$defs": {
            "Field": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "quote": {"type": ["string", "null"]},
                },
                "required": ["value"],
            }
        },
        "type": "object",
        "properties": {
            "field": {"$ref": "#/$defs/Field", "description": "Extracted field"}
        },
    }

    strict = _strict_json_schema(source)

    assert strict["$defs"]["Field"]["required"] == ["value", "quote"]
    field = strict["properties"]["field"]
    assert "$ref" not in field
    assert field["description"] == "Extracted field"
    assert field["required"] == ["value", "quote"]
    assert field["additionalProperties"] is False
