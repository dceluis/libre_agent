from inspect import signature
from typing import Any, Callable, Mapping, Tuple, Dict

from opentelemetry import context as context_api
from opentelemetry import trace as trace_api
from opentelemetry.util.types import AttributeValue

from openinference.instrumentation import safe_json_dumps, get_attributes_from_context
from openinference.semconv.trace import SpanAttributes

# span attributes
INPUT_MIME_TYPE = SpanAttributes.INPUT_MIME_TYPE
INPUT_VALUE = SpanAttributes.INPUT_VALUE
OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND

# define a custom span kind for execution instrumentation
EXECUTE = "EXECUTE"


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
            OPENINFERENCE_SPAN_KIND: EXECUTE,
            INPUT_VALUE: _get_input_value(wrapped, *args, **kwargs),
        }
        # explicitly add key input parameters for better observability
        for key in ("mode", "skip_recall", "ape_config"):
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
            span.set_attribute("execute_output", str(result))
        return result
