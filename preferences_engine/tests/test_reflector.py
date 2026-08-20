"""Tests for the reflection agent loop (Phase 2).

Deterministic — no real LLM, no network. The frozen reflection prompt is stubbed
and the policy handlers are mocked, so these tests exercise the turn-loop
mechanics without touching the reflection files or the policy corpus.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from preferences_engine.reflector import Reflector, OperationMethod
from preferences_engine.session import Session


class _FakeLlm:
    """Scripted stand-in for ``ctx.llm``. Returns canned JSON strings in order;
    once exhausted, defaults to ``exit`` (fail-closed)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        text = (
            self._responses.pop(0)
            if self._responses
            else '{"method": "exit", "request": []}'
        )
        return SimpleNamespace(text=text, parsed=None)


def _ctx(responses):
    llm = _FakeLlm(responses)
    return SimpleNamespace(llm=llm), llm


class _Base(unittest.TestCase):
    def setUp(self):
        # Stub the frozen reflection prompt so tests never read the real
        # reflection/ files or policy corpus.
        patcher = mock.patch(
            "preferences_engine.reflector.get_prompt",
            return_value="<REFLECTION_PROMPT>",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.reflector = Reflector()


class TestParseAgentsChoice(_Base):
    def test_valid_view(self):
        op = self.reflector._parse_agents_choice(
            '{"method": "view", "request": [{"id": "x"}]}'
        )
        self.assertEqual(op.method, OperationMethod.VIEW)
        self.assertEqual(op.request, [{"id": "x"}])

    def test_exit(self):
        op = self.reflector._parse_agents_choice('{"method": "exit", "request": []}')
        self.assertEqual(op.method, OperationMethod.EXIT)
        self.assertEqual(op.request, [])

    def test_garbage_returns_exit(self):
        op = self.reflector._parse_agents_choice("not json at all")
        self.assertEqual(op.method, OperationMethod.EXIT)
        self.assertEqual(op.request, [])

    def test_non_object_returns_exit(self):
        op = self.reflector._parse_agents_choice('["a", "b"]')
        self.assertEqual(op.method, OperationMethod.EXIT)

    def test_unknown_method_returns_exit(self):
        op = self.reflector._parse_agents_choice('{"method": "hack", "request": []}')
        self.assertEqual(op.method, OperationMethod.EXIT)

    def test_request_not_list_returns_exit(self):
        op = self.reflector._parse_agents_choice('{"method": "view", "request": "nope"}')
        self.assertEqual(op.method, OperationMethod.EXIT)

    def test_request_item_not_dict_returns_exit(self):
        op = self.reflector._parse_agents_choice('{"method": "view", "request": [42]}')
        self.assertEqual(op.method, OperationMethod.EXIT)


class TestRenderTranscript(_Base):
    def test_renders_user_and_assistant(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        out = self.reflector._render_transcript(history)
        self.assertIn("USER: hello", out)
        self.assertIn("ASSISTANT: hi there", out)
        self.assertIn("End of current conversation.", out)

    def test_multimodal_content_normalized(self):
        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "see this image"},
                    {"type": "image_url", "image_url": {"url": "https://x"}},
                ],
            },
        ]
        out = self.reflector._render_transcript(history)
        self.assertIn("USER: see this image", out)
        self.assertNotIn("image_url", out)

    def test_skips_tool_and_system(self):
        history = [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "tool result"},
        ]
        out = self.reflector._render_transcript(history)
        self.assertNotIn("sys prompt", out)
        self.assertNotIn("tool result", out)
        self.assertIn("USER: hi", out)

    def test_non_dict_turn_skipped(self):
        history = [{"role": "user", "content": "hi"}, "garbage", 42, None]
        out = self.reflector._render_transcript(history)
        self.assertIn("USER: hi", out)


class TestDialogueToBlocks(_Base):
    def test_empty_returns_empty_block(self):
        blocks = self.reflector._dialogue_to_blocks([])
        self.assertEqual(blocks, [{"type": "text", "text": ""}])

    def test_turns_rendered_to_single_block(self):
        turns = [
            {"role": "assistant", "content": '{"method": "view", "request": []}'},
            {"role": "tool", "content": '[{"id": "x"}]'},
        ]
        blocks = self.reflector._dialogue_to_blocks(turns)
        self.assertEqual(len(blocks), 1)
        self.assertIn("[assistant]", blocks[0]["text"])
        self.assertIn("[tool]", blocks[0]["text"])


class TestReflectionLoop(_Base):
    def test_below_threshold_does_nothing(self):
        ctx, llm = _ctx([])
        session = Session(session_id="s1", turn_count=5)
        self.reflector.check_reflection_loop(
            ctx, session, conversation_history=[{"role": "user", "content": "hi"}]
        )
        self.assertEqual(len(llm.calls), 0)

    def test_no_history_returns(self):
        ctx, llm = _ctx([])
        session = Session(session_id="s1", turn_count=16)
        self.reflector.check_reflection_loop(ctx, session, conversation_history=None)
        self.assertEqual(len(llm.calls), 0)

    def test_view_then_exit(self):
        ctx, llm = _ctx(
            [
                '{"method": "view", "request": [{"id": "local_first"}]}',
                '{"method": "exit", "request": []}',
            ]
        )
        session = Session(session_id="s1", turn_count=16)

        with mock.patch(
            "preferences_engine.reflector.view_policies",
            return_value=[{"id": "local_first", "found": True}],
        ) as vp:
            self.reflector.check_reflection_loop(
                ctx, session, conversation_history=[{"role": "user", "content": "prefer cheap stuff"}]
            )

        self.assertEqual(vp.call_count, 1)
        self.assertEqual(len(llm.calls), 2)
        # Turn 1 input is an empty block; turn 2 carries the prior dialogue.
        self.assertEqual(llm.calls[0]["input"], [{"type": "text", "text": ""}])
        turn2 = llm.calls[1]["input"][0]["text"]
        self.assertIn("[assistant]", turn2)
        self.assertIn("[tool]", turn2)
        self.assertIn("local_first", turn2)
        # The system prompt carries the frozen prompt + the transcript.
        self.assertIn("<REFLECTION_PROMPT>", llm.calls[0]["system_prompt"])
        self.assertIn("prefer cheap stuff", llm.calls[0]["system_prompt"])

    def test_view_then_update_then_exit(self):
        ctx, llm = _ctx(
            [
                '{"method": "view", "request": [{"id": "local_first"}]}',
                '{"method": "update", "request": [{"id": "local_first", "priority": 95}]}',
                '{"method": "exit", "request": []}',
            ]
        )
        session = Session(session_id="s1", turn_count=16)

        with mock.patch(
            "preferences_engine.reflector.view_policies",
            return_value=[{"id": "local_first", "found": True}],
        ) as vp, mock.patch(
            "preferences_engine.reflector.update_policies",
            return_value=[{"id": "local_first", "updated": True}],
        ) as up:
            self.reflector.check_reflection_loop(
                ctx, session, conversation_history=[{"role": "user", "content": "hi"}]
            )

        self.assertEqual(vp.call_count, 1)
        self.assertEqual(up.call_count, 1)
        self.assertEqual(len(llm.calls), 3)

    def test_garbage_response_breaks_loop(self):
        ctx, llm = _ctx(["not json at all"])
        session = Session(session_id="s1", turn_count=16)
        self.reflector.check_reflection_loop(
            ctx, session, conversation_history=[{"role": "user", "content": "hi"}]
        )
        # Garbage -> parse returns EXIT -> loop breaks after one turn.
        self.assertEqual(len(llm.calls), 1)

    def test_exhausted_responses_default_to_exit(self):
        ctx, llm = _ctx(
            ['{"method": "view", "request": [{"id": "x"}]}']
        )
        session = Session(session_id="s1", turn_count=16)
        with mock.patch(
            "preferences_engine.reflector.view_policies",
            return_value=[{"id": "x", "found": False}],
        ):
            self.reflector.check_reflection_loop(
                ctx, session, conversation_history=[{"role": "user", "content": "hi"}]
            )
        # After the scripted view, the fake LLM emits a default exit.
        self.assertEqual(len(llm.calls), 2)


if __name__ == "__main__":
    unittest.main()
