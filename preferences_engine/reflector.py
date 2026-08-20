import json

from typing import Any
from enum import StrEnum
from dataclasses import dataclass
from collections.abc import Callable

from preferences_engine.prompt import get_prompt
from preferences_engine.classifier import parse_json
from preferences_engine.session import Session
from preferences_engine.config import (
    REFLECTOR_TEMPERATURE,
    REFLECTOR_PURPOSE,
    REFLECTION_TURN_COUNT,
    MAX_REFLECTION_STEPS
)
from preferences_engine.policy import (
    ResultPolicies,
    view_policies,
    update_policies,
    archive_policies,
    create_new_policies
)

type AgentInputType = list[dict[str, Any]]


class OperationMethod(StrEnum):
    VIEW = "view"
    UPDATE = "update"
    ARCHIVE = "archive"
    CREATE = "create"
    EXIT = "exit"


@dataclass(frozen=True)
class Operation:
    method: OperationMethod
    request: list[dict[str, Any]]


class Reflector:
    def __init__(self):
        self._session: Session | None = None
        self._turn_count = 0
        self._cooldown = 0

        self._get_prompt()

    def _get_prompt(self) -> None:
        self._system_prompt = get_prompt("reflection")

    def check_reflection_loop(
        self,
        ctx: Any,
        session: Session,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
        **kwargs,
    ) -> None:
        self._session = session

        if self._session.turn_count <= REFLECTION_TURN_COUNT:
            return

        main_chat_history: AgentInputType = kwargs.get("conversation_history")
        if not main_chat_history or len(main_chat_history) < self._turn_count:
            return

        history_transcript = self._render_transcript(main_chat_history)
        agent_turns: AgentInputType = []

        for _ in MAX_REFLECTION_STEPS:
            input_blocks = self._dialogue_to_blocks(agent_turns)
            agent_choice = self._call_reflection_agent(
                ctx,
                self._system_prompt + history_transcript,
                input_blocks,
                classifier_provider,
                classifier_model,
            )

            operation = self._parse_agents_choice(agent_choice)
            if operation.method == OperationMethod.EXIT:
                break

            policies_to_agents = self._handle_operation(operation)

            agent_turns.append({
                "role": "assistant",
                "content": agent_choice
            })
            agent_turns.append({
                "role": "tool",
                "content": json.dumps(policies_to_agents)
            })

    def _render_transcript(self, conversation_history: AgentInputType) -> str:
        header = "\n\nCONVERSATION TRANSCRIPT:\n\n"
        content = ""

        for turn in conversation_history:
            active = turn.get("role")
            if active == "user":
                content += "USER: " + turn.get("content") + "\n"
            elif active == "assistant":
                content += "ASSISTANT: " + turn.get("content") + "\n"

        return header + content + "\n\n" + "End of current conversation."

    def _dialogue_to_blocks(self, agents_turn: AgentInputType) -> AgentInputType:
        if not agents_turn:
            return [{"type": "text", "text": ""}]  # empty, turn 1
        text = "\n\n".join(f"[{t['role']}]\n{t['content']}" for t in agents_turn)
        return [{"type": "text", "text": text}]

    def _call_reflection_agent(
        self,
        ctx: Any,
        system_prompt_and_history: str,
        agent_turn_msgs: AgentInputType,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
    ) -> str:

        per_turn_instruct = ("Review the conversation and maintain the policy library."
                             "Return exactly one operation (view/update/create/archive/exit).")

        return ctx.llm.complete_structured(
            instructions=per_turn_instruct,
            system_prompt=system_prompt_and_history,
            json_mode=True,
            input=agent_turn_msgs,
            temperature=REFLECTOR_TEMPERATURE,
            purpose=REFLECTOR_PURPOSE,
            provider=classifier_provider,
            model=classifier_model,
        )

    def _parse_agents_choice(self, agents_turn: str) -> Operation:
        raw = parse_json(agents_turn)

        method = OperationMethod(raw["method"])
        request = raw.get("request", [])

        if not isinstance(request, list):
            return Operation(method=OperationMethod.EXIT, request=[])

        for query in request:
            if not isinstance(query, dict):
                return Operation(method=OperationMethod.EXIT, request=[])

        return Operation(
            method=method,
            request=request,
        )

    def _handle_operation(self, operation: Operation) -> ResultPolicies:
        if operation.method == OperationMethod.EXIT:
            return []

        handlers: dict[
            OperationMethod,
            Callable[[list[dict[str, Any]]]],
        ] = {
            OperationMethod.VIEW: view_policies,
            OperationMethod.UPDATE: update_policies,
            OperationMethod.ARCHIVE: archive_policies,
            OperationMethod.CREATE: create_new_policies,
        }

        return handlers[operation.method](operation.request)
