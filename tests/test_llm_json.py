import pytest

from src.llm_json import extract_json_list


def test_plain_list():
    assert extract_json_list('[{"a": 1}, {"a": 2}]', dict) == [{"a": 1}, {"a": 2}]


def test_ignores_text_after_the_json():
    text = '[[0, 2], [1]]\n\nGroups [0, 2] cover the same story.'
    assert extract_json_list(text, list) == [[0, 2], [1]]


def test_ignores_text_with_brackets_before_the_json():
    text = 'Here are the [2] results:\n[{"a": 1}, {"a": 2}]'
    assert extract_json_list(text, dict) == [{"a": 1}, {"a": 2}]


def test_markdown_fence():
    assert extract_json_list('```json\n[{"a": 1}]\n```', dict) == [{"a": 1}]


def test_loose_lists_without_outer_brackets():
    assert extract_json_list("[0, 3], [1], [2]", list) == [[0, 3], [1], [2]]


def test_loose_objects_without_outer_brackets():
    assert extract_json_list('{"a": 1},\n{"a": 2}', dict) == [{"a": 1}, {"a": 2}]


def test_truncated_list_keeps_complete_items_in_order():
    text = '[{"a": 1, "tags": ["x"]}, {"a": 2}, {"a": 3, "summ'
    assert extract_json_list(text, dict) == [{"a": 1, "tags": ["x"]}, {"a": 2}]


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json_list("Sorry, I cannot help with that.", dict)


def test_list_of_wrong_type_raises():
    with pytest.raises(ValueError):
        extract_json_list('["a", "b"]', dict)
