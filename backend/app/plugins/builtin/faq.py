"""FaqPlugin — answers frequently asked questions using AI."""

from app.plugins.base import PluginManifest
from app.plugins.prompt_driver import PromptDrivenPlugin


class FaqPlugin(PromptDrivenPlugin):
    """FAQ plugin — prompt-driven answers from knowledge base."""

    def __init__(self):
        super().__init__(
            manifest=PluginManifest(
                id="faq",
                name="FAQ",
                version="1.0.0",
                description="Answers frequently asked questions from the knowledge base.",
                intents=["faq", "question", "help"],
                capabilities=[],
                is_builtin=True,
                is_prompt_driven=True,
            ),
            system_prompt="""You are a helpful FAQ assistant for {tenant_id}.
Answer the user's question based on the knowledge base and your training.
Be concise and accurate. If you don't know the answer, say so and suggest contacting support.
Language: {language}""",
            examples=[
                {
                    "role": "user",
                    "content": "How do I reset my password?",
                },
                {
                    "role": "assistant",
                    "content": "To reset your password, go to Settings → Security → Change Password. If you can't log in, use the 'Forgot password' link on the login page.",
                },
            ],
        )
