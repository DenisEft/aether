"""FormPlugin — state machine for filling multi-step forms."""

from __future__ import annotations

from app.plugins.base import (
    BaseServicePlugin,
    Intent,
    PluginContext,
    PluginManifest,
    PluginResult,
    PluginStatus,
    PluginHealth,
    Action,
)


class FormPlugin(BaseServicePlugin):
    """State-machine based form filling.

    Tracks which fields have been collected and asks for missing ones.
    Uses context.session_state to persist progress.
    """

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="form",
            name="Form Filler",
            version="1.0.0",
            description="Guides users through multi-step form completion.",
            intents=["form", "fill_form", "registration", "application"],
            is_builtin=True,
        )

    async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
        # Get form configuration from entities or session state
        form_name = intent.entities.get("form_name", "default")
        fields = intent.entities.get("fields", ["name", "email", "phone"])

        # Get current progress
        state = context.session_state.get(f"form_{form_name}", {})
        collected = state.get("collected", {})

        # Check which fields are still missing
        missing = [f for f in fields if f not in collected]

        if missing:
            next_field = missing[0]
            # Collect the current entity if provided
            if next_field in intent.entities:
                collected[next_field] = intent.entities[next_field]
                missing = missing[1:]

            if missing:
                next_field = missing[0]
                state["collected"] = collected
                state["current_field"] = next_field

                # Return context update for session state
                return PluginResult(
                    success=True,
                    text=f"Пожалуйста, укажите {next_field}:",
                    data={
                        "form_name": form_name,
                        "current_field": next_field,
                        "collected": collected,
                        "remaining_fields": missing,
                        "session_state": {f"form_{form_name}": state},
                    },
                    actions=[
                        Action(action_type="wait_for_input", payload={"field": next_field, "form": form_name}),
                    ],
                )

        # All fields collected — process the form
        return PluginResult(
            success=True,
            text=f"Форма '{form_name}' заполнена. Данные: {collected}",
            data={
                "form_name": form_name,
                "collected": collected,
                "completed": True,
            },
            actions=[
                Action(
                    action_type="call_api",
                    payload={
                        "endpoint": f"/api/v1/forms/{form_name}/submit",
                        "method": "POST",
                        "data": collected,
                    },
                ),
            ],
        )

    async def health_check(self) -> PluginHealth:
        return PluginHealth(status=PluginStatus.ACTIVE)
