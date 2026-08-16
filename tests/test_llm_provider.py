import json

from app.infrastructure.llm_provider import normalize_json_content, schema_instruction


def test_normalize_json_content_removes_markdown_fence() -> None:
    content = '```json\n{"status":"готово"}\n```'

    assert normalize_json_content(content) == '{"status":"готово"}'


def test_normalize_json_content_preserves_plain_json() -> None:
    content = '  {"status":"готово"}  '

    assert normalize_json_content(content) == '{"status":"готово"}'


def test_schema_instruction_keeps_russian_text() -> None:
    instruction = schema_instruction(
        {
            "type": "object",
            "description": "Результат проверки",
        }
    )

    assert json.loads(instruction)["description"] == "Результат проверки"
    assert "Результат проверки" in instruction
