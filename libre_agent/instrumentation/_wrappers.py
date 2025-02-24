from inspect import signature
from typing import Any, Callable, Mapping, Tuple, Dict

from opentelemetry import context as context_api
from opentelemetry import trace as trace_api
from opentelemetry.util.types import AttributeValue

from openinference.instrumentation import safe_json_dumps, get_attributes_from_context
from openinference.semconv.trace import (
    SpanAttributes,
    MessageAttributes,
    ToolCallAttributes,
    OpenInferenceSpanKindValues
)

# span attributes
INPUT_MIME_TYPE = SpanAttributes.INPUT_MIME_TYPE
INPUT_VALUE = SpanAttributes.INPUT_VALUE
OUTPUT_MIME_TYPE = SpanAttributes.OUTPUT_MIME_TYPE
OUTPUT_VALUE = SpanAttributes.OUTPUT_VALUE
OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND

def _strip_method_args(arguments: Mapping[str, Any]) -> dict:
    return {key: value for key, value in arguments.items() if key not in ("self", "cls")}


def _get_input_value(method: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    method_signature = signature(method)
    bound_args = method_signature.bind(*args, **kwargs)
    bound_args.apply_defaults()
    arguments = bound_args.arguments
    arguments = _strip_method_args(arguments)
    return safe_json_dumps(arguments)

class _ExecuteWrapper:
    def __init__(self, tracer: trace_api.Tracer) -> None:
        self._tracer = tracer

    def __call__(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        if context_api.get_value(context_api._SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)

        span_name = f"{instance.__class__.__name__}.execute"
        attributes: Dict[str, AttributeValue] = {
            OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.CHAIN.value,
            INPUT_VALUE: _get_input_value(wrapped, *args, **kwargs),
        }
        # explicitly add key input parameters for better observability
        for key in ("mode", "ape_config"):
            if key in kwargs:
                if key == "ape_config":
                    attributes[key] = safe_json_dumps(kwargs[key])
                else:
                    attributes[key] = kwargs[key]
        # update using a dict conversion of the iterator from get_attributes_from_context
        attributes.update(dict(get_attributes_from_context()))
        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                result = wrapped(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace_api.StatusCode.ERROR)
                raise
            span.set_attribute(OUTPUT_VALUE, str(result))
        return result

class _ReasonWrapper:
    def __init__(self, tracer: trace_api.Tracer) -> None:
        self._tracer = tracer

    def __call__(
            self,
            wrapped: Callable[..., Any],
            instance: Any,
            args: Tuple[Any, ...],
            kwargs: Mapping[str, Any],
    ) -> Any:
        if context_api.get_value(context_api._SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)
        span_name = f"{instance.__class__.__name__}.reason"
        attributes: Dict[str, AttributeValue] = {
            OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.CHAIN.value,
            INPUT_VALUE: _get_input_value(wrapped, *args, **kwargs)
        }
        attributes.update(dict(get_attributes_from_context()))

        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                result = wrapped(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace_api.StatusCode.ERROR)
                raise
            span.set_attribute(OUTPUT_VALUE, str(result))

            return result


class _ToolWrapper:
    def __init__(self, tracer: trace_api.Tracer) -> None:
        self._tracer = tracer

    def __call__(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        if context_api.get_value(context_api._SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)

        span_name = f"{instance.__class__.__name__}.run"
        attributes: Dict[str, AttributeValue] = {
            OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.TOOL.value,
            "tool.name": getattr(instance, 'name', instance.__class__.__name__),
            INPUT_VALUE: _get_input_value(wrapped, *args, **kwargs),
            INPUT_MIME_TYPE: "application/json",
            "tool.mode": instance.mode,
        }

        if hasattr(instance, 'description'):
            attributes["tool.description"] = instance.description

        attributes.update(dict(get_attributes_from_context()))

        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            output_value = ""
            try:
                result = wrapped(*args, **kwargs)
                output_value = safe_json_dumps(result)
            except Exception as e:
                output_value = safe_json_dumps({"error": str(e)})
                span.record_exception(e)
                span.set_status(trace_api.StatusCode.ERROR)
                raise
            finally:
                span.set_attribute(OUTPUT_VALUE, output_value)
                span.set_attribute(OUTPUT_MIME_TYPE, "application/json")
            return result

class _ChatCycleWrapper:
    def __init__(self, tracer: trace_api.Tracer) -> None:
        self._tracer = tracer

    def __call__(
        self,
        wrapped: Callable[..., Any],
        instance: Any,  # This will be the ChatCycle instance
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        if context_api.get_value(context_api._SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)

        span_name = f"{instance.__class__.__name__}.run"
        attributes: Dict[str, AttributeValue] = {
            SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.LLM.value,
        }

        attributes.update(dict(get_attributes_from_context()))

        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                chat_response = wrapped(*args, **kwargs)

                # Input Messages (using the stored prompt_messages)
                attributes[SpanAttributes.LLM_INPUT_MESSAGES] = [
                    safe_json_dumps({
                        MessageAttributes.MESSAGE_ROLE: message["role"],
                        MessageAttributes.MESSAGE_CONTENT: message["content"],
                    }) for message in instance.prompt_messages
                ]

                # Tools (using the stored tools_info)
                if instance.tools_info:
                    attributes[SpanAttributes.LLM_TOOLS] = safe_json_dumps(instance.tools_info)

                if instance.chat_request.tool_choice:
                    attributes["llm.tool_choice"] = instance.chat_request.tool_choice

                if instance.chat_request.model:
                    attributes[SpanAttributes.LLM_MODEL_NAME] = instance.chat_request.model

                # Output Messages (if present)
                if chat_response and chat_response.content:
                    attributes[SpanAttributes.LLM_OUTPUT_MESSAGES] = safe_json_dumps([{
                        MessageAttributes.MESSAGE_ROLE: chat_response.role,
                        MessageAttributes.MESSAGE_CONTENT: chat_response.content,
                    }])

                # Tool Calls (if present)
                if chat_response and chat_response.tool_calls:
                    tool_calls_list = []
                    for tool_call in chat_response.tool_calls:
                        tool_call_attributes = {
                            ToolCallAttributes.TOOL_CALL_ID: tool_call.id,
                            ToolCallAttributes.TOOL_CALL_FUNCTION_NAME: tool_call.function.name,
                            ToolCallAttributes.TOOL_CALL_FUNCTION_ARGUMENTS_JSON: safe_json_dumps(tool_call.function.arguments),
                        }
                        tool_calls_list.append(safe_json_dumps(tool_call_attributes))
                    attributes[SpanAttributes.LLM_FUNCTION_CALL] = tool_calls_list

                # Add token counts
                span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, instance.input_tokens)
                span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, instance.output_tokens)
                span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL, instance.total_tokens)

                # Set all attributes
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            except Exception as e:
                span.record_exception(e)
                span.set_status(trace_api.StatusCode.ERROR)
                raise

            return chat_response
