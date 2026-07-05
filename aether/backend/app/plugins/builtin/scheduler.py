"""SchedulerPlugin — AI-driven appointment and booking scheduling."""

from app.plugins.base import PluginManifest
from app.plugins.prompt_driver import PromptDrivenPlugin


class SchedulerPlugin(PromptDrivenPlugin):
    """Prompt-driven scheduler — understands time/date intents and manages bookings."""

    def __init__(self):
        super().__init__(
            manifest=PluginManifest(
                id="scheduler",
                name="Scheduler",
                version="1.0.0",
                description="AI-driven appointment and booking scheduling.",
                intents=["booking", "schedule", "appointment", "reservation"],
                capabilities=[],
                is_builtin=True,
                is_prompt_driven=True,
            ),
            system_prompt="""You are a scheduling assistant for {tenant_id}.
Help the user schedule appointments and bookings.

Rules:
- Today's date is available in context
- If user doesn't specify date, ask for it
- If user doesn't specify time, suggest available slots
- Confirm all details before finalizing
- Store bookings with: name, date, time, service_type

Respond conversationally. Ask clarifying questions when needed.
Language: {language}""",
            examples=[
                {
                    "role": "user",
                    "content": "I need to book a consultation for tomorrow",
                },
                {
                    "role": "assistant",
                    "content": "I'd be happy to help you book a consultation! What time works best for you tomorrow? We have slots available from 9:00 to 18:00.",
                },
                {
                    "role": "user",
                    "content": "11 am would be perfect",
                },
                {
                    "role": "assistant",
                    "content": "Great! I've booked your consultation for tomorrow at 11:00. Is there anything else you need?",
                },
            ],
        )
