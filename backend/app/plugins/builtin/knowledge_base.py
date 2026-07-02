"""KnowledgeBasePlugin — searches the tenant's knowledge base for answers."""

from app.plugins.base import PluginManifest
from app.plugins.prompt_driver import PromptDrivenPlugin


class KnowledgeBasePlugin(PromptDrivenPlugin):
    """Prompt-driven knowledge base search and retrieval."""

    def __init__(self):
        super().__init__(
            manifest=PluginManifest(
                id="knowledge_base",
                name="Knowledge Base",
                version="1.0.0",
                description="Searches the tenant's knowledge base for relevant information.",
                intents=["knowledge_base", "document_search", "search", "find_document"],
                capabilities=[],
                is_builtin=True,
                is_prompt_driven=True,
            ),
            system_prompt="""You are a knowledge base assistant for {tenant_id}.
Search the available knowledge base and documents to answer the user's question.

Rules:
- Cite sources when providing information
- If information is not in the knowledge base, say so clearly
- Suggest related topics that might help
- Be accurate — don't make up information

Language: {language}""",
            examples=[
                {
                    "role": "user",
                    "content": "What is our return policy?",
                },
                {
                    "role": "assistant",
                    "content": "According to our policy (document: Return Policy v2.1), items can be returned within 30 days of purchase with the original receipt. For digital products, returns are accepted within 14 days.",
                },
            ],
        )
