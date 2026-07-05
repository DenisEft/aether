"""Built-in plugins bundled with Aether.

Echo, FAQ, Classifier, Escalation, Form, Scheduler, KnowledgeBase.
All builtins are loaded automatically on startup.
"""

from app.plugins.builtin.echo import EchoPlugin
from app.plugins.builtin.faq import FaqPlugin
from app.plugins.builtin.classifier import ClassifierPlugin
from app.plugins.builtin.escalation import EscalationPlugin
from app.plugins.builtin.form import FormPlugin
from app.plugins.builtin.scheduler import SchedulerPlugin
from app.plugins.builtin.knowledge_base import KnowledgeBasePlugin

__all__ = [
    "EchoPlugin",
    "FaqPlugin",
    "ClassifierPlugin",
    "EscalationPlugin",
    "FormPlugin",
    "SchedulerPlugin",
    "KnowledgeBasePlugin",
]

# Standard builtin plugin list for auto-loading
BUILTIN_PLUGINS = [
    EchoPlugin,
    FaqPlugin,
    ClassifierPlugin,
    EscalationPlugin,
    FormPlugin,
    SchedulerPlugin,
    KnowledgeBasePlugin,
]
