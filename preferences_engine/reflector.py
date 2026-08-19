from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from preferences_engine.classifier import parse_json
from preferences_engine.session import Session
from preferences_engine.config import (
    REFLECTOR_TEMPERATURE,
    REFLECTOR_PURPOSE,
    REFLECTION_TURN_COUNT,
)
from preferences_engine.policy import (
    view_policies,
    update_policies,
    archive_policies,
    create_new_policies
)


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
        self._system_prompt = ""

    def _handle_operation(self, operation: Operation) -> None:
        if operation.method == OperationMethod.EXIT:
            return

        handlers: dict[
            OperationMethod,
            Callable[[list[dict[str, Any]]], None],
        ] = {
            OperationMethod.VIEW: view_policies,
            OperationMethod.UPDATE: update_policies,
            OperationMethod.ARCHIVE: archive_policies,
            OperationMethod.CREATE: create_new_policies,
        }

        policies_data = handlers[operation.method](operation.request)

    def check_reflection_loop(
        self,
        ctx: Any,
        session: Session,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
        **kwargs,
    ) -> None:
        self._session = session

        if self._session.turn_count > REFLECTION_TURN_COUNT:
            while True:
                agent_choice = self._call_reflection_agent(
                    ctx,
                    classifier_provider,
                    classifier_model,
                    **kwargs,
                )

                operation = self._parse_agents_choice(agent_choice)

                if operation.method == OperationMethod.EXIT:
                    break

                self._handle_operation(operation)

    def _call_reflection_agent(
        self,
        ctx: Any,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
        **kwargs,
    ) -> str:
        chat_history = kwargs.get("conversation_history")

        return ctx.llm.complete_structured(
            instructions="This is a serious and attention needful task.",
            system_prompt=self._system_prompt,
            json_mode=True,
            input=chat_history,
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

        return Operation(
            method=method,
            request=request,
        )
