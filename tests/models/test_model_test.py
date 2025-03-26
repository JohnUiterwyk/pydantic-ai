"""This module contains tests for the testing module."""

from __future__ import annotations as _annotations

from datetime import timezone
from typing import Annotated, Any, Literal

import pytest
from annotated_types import Ge, Gt, Le, Lt, MaxLen, MinLen
from inline_snapshot import snapshot
from pydantic import BaseModel, Field

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    AudioUrl,
    BinaryContent,
    ImageUrl,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel, _chars, _JsonSchemaTestData  # pyright: ignore[reportPrivateUsage]
from pydantic_ai.usage import Usage

from ..conftest import IsNow, IsStr


def test_call_one():
    agent = Agent()
    calls: list[str] = []

    @agent.tool_plain
    async def ret_a(x: str) -> str:
        calls.append('a')
        return f'{x}-a'

    @agent.tool_plain
    async def ret_b(x: str) -> str:  # pragma: no cover
        calls.append('b')
        return f'{x}-b'

    result = agent.run_sync('x', model=TestModel(call_tools=['ret_a']))
    assert result.data == snapshot('{"ret_a":"a-a"}')
    assert calls == ['a']


def test_custom_result_text():
    agent = Agent()
    result = agent.run_sync('x', model=TestModel(custom_result_text='custom'))
    assert result.data == snapshot('custom')
    agent = Agent(result_type=tuple[str, str])
    with pytest.raises(AssertionError, match='Plain response not allowed, but `custom_result_text` is set.'):
        agent.run_sync('x', model=TestModel(custom_result_text='custom'))


def test_custom_result_args():
    agent = Agent(result_type=tuple[str, str])
    result = agent.run_sync('x', model=TestModel(custom_result_args=['a', 'b']))
    assert result.data == ('a', 'b')


def test_custom_result_args_model():
    class Foo(BaseModel):
        foo: str
        bar: int

    agent = Agent(result_type=Foo)
    result = agent.run_sync('x', model=TestModel(custom_result_args={'foo': 'a', 'bar': 1}))
    assert result.data == Foo(foo='a', bar=1)


def test_result_type():
    agent = Agent(result_type=tuple[str, str])
    result = agent.run_sync('x', model=TestModel())
    assert result.data == ('a', 'a')


def test_tool_retry():
    agent = Agent()
    call_count = 0

    @agent.tool_plain
    async def my_ret(x: int) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ModelRetry('First call failed')
        else:
            return str(x + 1)

    result = agent.run_sync('Hello', model=TestModel())
    assert call_count == 2
    assert result.data == snapshot('{"my_ret":"1"}')
    assert result.all_messages() == snapshot(
        [
            ModelRequest(parts=[UserPromptPart(content='Hello', timestamp=IsNow(tz=timezone.utc))]),
            ModelResponse(
                parts=[ToolCallPart(tool_name='my_ret', args={'x': 0}, tool_call_id=IsStr())],
                model_name='test',
                timestamp=IsNow(tz=timezone.utc),
            ),
            ModelRequest(
                parts=[
                    RetryPromptPart(
                        content='First call failed',
                        tool_name='my_ret',
                        timestamp=IsNow(tz=timezone.utc),
                        tool_call_id=IsStr(),
                    )
                ]
            ),
            ModelResponse(
                parts=[ToolCallPart(tool_name='my_ret', args={'x': 0}, tool_call_id=IsStr())],
                model_name='test',
                timestamp=IsNow(tz=timezone.utc),
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name='my_ret', content='1', tool_call_id=IsStr(), timestamp=IsNow(tz=timezone.utc)
                    )
                ]
            ),
            ModelResponse(
                parts=[TextPart(content='{"my_ret":"1"}')],
                model_name='test',
                timestamp=IsNow(tz=timezone.utc),
            ),
        ]
    )


def test_result_tool_retry_error_handled():
    class ResultModel(BaseModel):
        x: int
        y: str

    agent = Agent('test', result_type=ResultModel, retries=2)

    call_count = 0

    @agent.result_validator
    def validate_result(ctx: RunContext[None], result: ResultModel) -> ResultModel:
        nonlocal call_count
        call_count += 1
        raise ModelRetry('Fail')

    with pytest.raises(UnexpectedModelBehavior, match='Exceeded maximum retries'):
        agent.run_sync('Hello', model=TestModel())

    assert call_count == 3


def test_result_tool_retry_error_handled_with_custom_args(set_event_loop: None):
    class ResultModel(BaseModel):
        x: int
        y: str

    agent = Agent('test', result_type=ResultModel, retries=2)

    with pytest.raises(UnexpectedModelBehavior, match='Exceeded maximum retries'):
        agent.run_sync('Hello', model=TestModel(custom_result_args={'foo': 'a', 'bar': 1}))


def test_json_schema_test_data():
    class NestedModel(BaseModel):
        foo: str
        bar: int

    class TestModel(BaseModel):
        my_str: str
        my_str_long: Annotated[str, MinLen(10)]
        my_str_short: Annotated[str, MaxLen(1)]
        my_int: int
        my_int_gt: Annotated[int, Gt(5)]
        my_int_ge: Annotated[int, Ge(5)]
        my_int_lt: Annotated[int, Lt(-5)]
        my_int_le: Annotated[int, Le(-5)]
        my_int_range: Annotated[int, Gt(5), Lt(15)]
        my_float: float
        my_float_gt: Annotated[float, Gt(5.0)]
        my_float_lt: Annotated[float, Lt(-5.0)]
        my_bool: bool
        my_bytes: bytes
        my_fixed_tuple: tuple[int, str]
        my_var_tuple: tuple[int, ...]
        my_list: list[str]
        my_dict: dict[str, int]
        my_set: set[str]
        my_set_min_len: Annotated[set[str], MinLen(5)]
        my_list_min_len: Annotated[list[str], MinLen(5)]
        my_lit_int: Literal[1]
        my_lit_ints: Literal[1, 2, 3]
        my_lit_str: Literal['a']
        my_lit_strs: Literal['a', 'b', 'c']
        my_any: Any
        nested: NestedModel
        union: int | list[int]
        optional: str | None
        with_example: int = Field(json_schema_extra={'examples': [1234]})
        max_len_zero: Annotated[str, MaxLen(0)]
        is_null: None
        not_required: str = 'default'

    json_schema = TestModel.model_json_schema()
    data = _JsonSchemaTestData(json_schema).generate()
    assert data == snapshot(
        {
            'my_str': 'a',
            'my_str_long': 'aaaaaaaaaa',
            'my_str_short': 'a',
            'my_int': 0,
            'my_int_gt': 6,
            'my_int_ge': 5,
            'my_int_lt': -6,
            'my_int_le': -5,
            'my_int_range': 6,
            'my_float': 0.0,
            'my_float_gt': 6.0,
            'my_float_lt': -6.0,
            'my_bool': False,
            'my_bytes': 'a',
            'my_fixed_tuple': [0, 'a'],
            'my_var_tuple': [0],
            'my_list': ['a'],
            'my_dict': {'additionalProperty': 0},
            'my_set': ['a'],
            'my_set_min_len': ['b', 'c', 'd', 'e', 'f'],
            'my_list_min_len': ['g', 'g', 'g', 'g', 'g'],
            'my_lit_int': 1,
            'my_lit_ints': 1,
            'my_lit_str': 'a',
            'my_lit_strs': 'a',
            'my_any': 'g',
            'union': 6,
            'optional': 'g',
            'with_example': 1234,
            'max_len_zero': '',
            'is_null': None,
            'nested': {'foo': 'g', 'bar': 6},
        }
    )
    TestModel.model_validate(data)


def test_json_schema_test_data_additional():
    class TestModel(BaseModel, extra='allow'):
        x: int
        additional_property: str = Field(alias='additionalProperty')

    json_schema = TestModel.model_json_schema()
    data = _JsonSchemaTestData(json_schema).generate()
    assert data == snapshot({'x': 0, 'additionalProperty': 'a', 'additionalProperty_': 'a'})
    TestModel.model_validate(data)


def test_chars_wrap():
    class TestModel(BaseModel):
        a: Annotated[set[str], MinLen(4)]

    json_schema = TestModel.model_json_schema()
    data = _JsonSchemaTestData(json_schema, seed=len(_chars) - 2).generate()
    assert data == snapshot({'a': ['}', '~', 'aa', 'ab']})


def test_prefix_unique():
    json_schema = {
        'type': 'array',
        'uniqueItems': True,
        'prefixItems': [{'type': 'string'}, {'type': 'string'}],
    }
    data = _JsonSchemaTestData(json_schema).generate()
    assert data == snapshot(['a', 'b'])


def test_max_items():
    json_schema = {
        'type': 'array',
        'items': {'type': 'string'},
        'maxItems': 0,
    }
    data = _JsonSchemaTestData(json_schema).generate()
    assert data == snapshot([])


@pytest.mark.parametrize(
    'content',
    [
        AudioUrl(url='https://example.com'),
        ImageUrl(url='https://example.com'),
        BinaryContent(data=b'', media_type='image/png'),
    ],
)
def test_different_content_input(content: AudioUrl | ImageUrl | BinaryContent):
    agent = Agent()
    result = agent.run_sync('x', model=TestModel(custom_result_text='custom'))
    assert result.data == snapshot('custom')
    assert result.usage() == snapshot(Usage(requests=1, request_tokens=51, response_tokens=1, total_tokens=52))
