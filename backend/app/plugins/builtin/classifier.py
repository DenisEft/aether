"""ClassifierPlugin — classifies user messages into categories."""

from app.plugins.base import PluginManifest
from app.plugins.prompt_driver import PromptDrivenPlugin


class ClassifierPlugin(PromptDrivenPlugin):
    """Prompt-driven classifier — categorizes incoming messages."""

    def __init__(self):
        super().__init__(
            manifest=PluginManifest(
                id="classifier",
                name="Message Classifier",
                version="1.0.0",
                description="Classifies user messages into predefined categories for routing.",
                intents=["classify", "categorize"],
                capabilities=[],
                is_builtin=True,
                is_prompt_driven=True,
            ),
            system_prompt="""You are a message classifier. Categorize the user's message into one of:
- greeting: Hello, hi, good morning
- question: General inquiry
- complaint: Negative feedback or problem report
- order: Order-related (status, tracking, new order)
- document: Document requests or submissions
- other: None of the above

Respond with JSON: {"category": "...", "confidence": 0.0-1.0}""",
        )
