__version__ = "1.0.0"

from typing import Any, Callable, Collection, Optional

from opentelemetry import trace as trace_api
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from wrapt import wrap_function_wrapper

from openinference.instrumentation import (
    OITracer,
    TraceConfig,
)
from libre_agent.instrumentation._wrappers import (
    _ExecuteWrapper,
)

_instruments = ("libre_agent >= 0.0.0",)

class LibreAgentInstrumentor(BaseInstrumentor):  # type: ignore
    __slots__ = (
        "_original_execute_method",
        "_tracer",
    )

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        from libre_agent.reasoning_engine import LibreAgentEngine

        if not (tracer_provider := kwargs.get("tracer_provider")):
            tracer_provider = trace_api.get_tracer_provider()
        if not (config := kwargs.get("config")):
            config = TraceConfig()
        else:
            assert isinstance(config, TraceConfig)
        self._tracer = OITracer(
            trace_api.get_tracer(__name__, __version__, tracer_provider),
            config=config,
        )

        execute_wrapper = _ExecuteWrapper(tracer=self._tracer)
        self._original_execute_method = getattr(LibreAgentEngine, "execute", None)
        wrap_function_wrapper(
            module="libre_agent.reasoning_engine",
            name="LibreAgentEngine.execute",
            wrapper=execute_wrapper,
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        from libre_agent.reasoning_engine import LibreAgentEngine

        if self._original_execute_method is not None:
            LibreAgentEngine.execute = self._original_execute_method
            self._original_execute_method = None
