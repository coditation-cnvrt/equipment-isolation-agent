"""Guardrail ordering tests for the agent loop.

``_ensure_pipeline`` walks the pipeline forward from wherever the model stopped.
Its ORDER matters: run.py runs instrument context at stage 7, before evidence at
stage 8, so evidence is always built from data that already carries it. The agent
must converge on the same order even when the model skips a tool.

These run offline with a stub session -- no graph, no API key.
"""
import os
import unittest
from unittest import mock

import equipment_isolation.agent.loop as loop


class _StubSession:
    """Everything present except instrument context and evidence."""

    def __init__(self):
        self.boundary_data = {"x": 1}
        self.candidate_data = {"x": 1}
        self.bbox_data = {"x": 1}
        self.isolation_obligations = {}
        self.relief_analysis = {}
        self.instrument_context = None
        self.evidence_data = None
        self.validation_data = {"x": 1}
        self.downstream_impact = {}
        self.final_payload = {"data": [{}]}
        self.loto_procedure = {}
        self.config = type("C", (), {"equipment_tag": "N7"})()
        self.trace = []

    def record(self, tool, args, result, error=None):
        self.trace.append({"tool": tool, "args": args, "result": result, "error": error})


class _Part:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text


class _Response:
    def __init__(self, parts):
        self.candidates = [type("Candidate", (), {"content": type("Content", (), {"parts": parts})()})()]


class _Models:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs["model"])
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class GuardrailOrderingTests(unittest.TestCase):
    def _forced_calls(self, session):
        calls = []
        original = loop.call_tool
        loop.call_tool = lambda _session, name, args=None: (calls.append(name), {})[1]
        try:
            loop._ensure_pipeline(session, True, lambda *a, **k: None)
        finally:
            loop.call_tool = original
        return calls

    def test_instrument_context_is_forced_when_the_model_skips_it(self):
        calls = self._forced_calls(_StubSession())
        self.assertIn("analyze_instrument_context", calls)

    def test_instrument_context_is_forced_before_evidence(self):
        # This is the ordering run.py guarantees structurally (stage 7 -> 8).
        calls = self._forced_calls(_StubSession())
        self.assertLess(
            calls.index("analyze_instrument_context"),
            calls.index("build_evidence"),
            "evidence must never be built before instrument context",
        )

    def test_already_present_instrument_context_is_not_re_forced(self):
        session = _StubSession()
        session.instrument_context = {"status": "completed", "instruments": []}
        self.assertNotIn("analyze_instrument_context", self._forced_calls(session))

    def test_nothing_is_forced_when_the_session_is_already_complete(self):
        session = _StubSession()
        session.instrument_context = {"status": "completed"}
        session.evidence_data = {"x": 1}
        self.assertEqual(self._forced_calls(session), [])

    def test_transient_model_errors_retry_then_fallback(self):
        unavailable = loop.errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "down"}})
        success = object()
        models = _Models([unavailable, unavailable, unavailable, success])
        client = type("Client", (), {"models": models})()
        events = []

        with mock.patch.dict(os.environ, {"GEMINI_FALLBACK_MODEL": "fallback-model"}), mock.patch.object(loop.time, "sleep"):
            response, used_model = loop._generate_with_resilience(
                client,
                model="primary-model",
                contents=[],
                config=object(),
                on_event=lambda kind, payload: events.append((kind, payload)),
            )

        self.assertIs(response, success)
        self.assertEqual(used_model, "fallback-model")
        self.assertEqual(models.calls, ["primary-model", "primary-model", "primary-model", "fallback-model"])
        self.assertEqual([kind for kind, _ in events].count("model_retry"), 2)
        self.assertIn("model_fallback", [kind for kind, _ in events])

    def test_boundary_infrastructure_failure_stops_without_retry_or_guardrail(self):
        call = type("FunctionCall", (), {"name": "fetch_boundary", "args": {"equipment_tag": "N7"}})()
        response = _Response([_Part(function_call=call)])
        models = _Models([response])
        client = type("Client", (), {"models": models})()
        session = _StubSession()
        session.boundary_data = None
        events = []

        with mock.patch.object(loop.genai, "Client", return_value=client), \
             mock.patch.object(loop, "call_tool", return_value={"error": "ConnectionTimeoutError: graph unavailable"}) as tool, \
             mock.patch.object(loop, "_ensure_pipeline") as guardrail:
            result = loop.run_agent(session, model="primary-model", api_key="key", on_event=lambda kind, payload: events.append((kind, payload)))

        tool.assert_called_once()
        guardrail.assert_not_called()
        self.assertEqual(result["steps_used"], 1)
        self.assertEqual(result["forced"], [])
        self.assertEqual(result["orchestration_error"]["kind"], "pipeline_prerequisite_failed")
        self.assertIn("pipeline_error", [kind for kind, _ in events])

    def test_model_failure_is_recorded_and_deterministic_guardrail_runs(self):
        unavailable = loop.errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "down"}})
        session = _StubSession()
        session.validation_data = {"assurance_status": "not_isolated", "isolation_validation": {"terminal": True}}

        with mock.patch.object(loop.genai, "Client", return_value=object()), \
             mock.patch.object(loop, "_generate_with_resilience", side_effect=unavailable), \
             mock.patch.object(loop, "_ensure_pipeline", return_value=["validate", "finalize_plan"]) as guardrail:
            result = loop.run_agent(session, model="primary-model", api_key="key")

        guardrail.assert_called_once()
        self.assertEqual(result["assurance_status"], "not_isolated")
        self.assertEqual(result["orchestration_error"]["code"], 503)
        self.assertEqual(result["forced"], ["validate", "finalize_plan"])


if __name__ == "__main__":
    unittest.main()
