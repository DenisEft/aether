"""Plugin Loader — discover plugins from DB and filesystem."""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

from app.plugins.base import (
    BaseServicePlugin,
    Capability,
    PluginManifest,
    PluginPermission,
)
from app.plugins.prompt_driver import PromptDrivenPlugin
from app.plugins.registry import PluginRegistry, get_registry

logger = logging.getLogger("aether.plugins.loader")


class PluginLoader:
    """Discovers and loads plugins from multiple sources.

    Sources (in priority order):
    1. Built-in plugins (bundled with Aether)
    2. Filesystem plugins (plugin.json in plugins directory)
    3. Database plugins (ServiceDefinition entries)
    """

    def __init__(self, registry: PluginRegistry | None = None):
        self.registry = registry or get_registry()
        self._plugin_dir = Path(__file__).parent / "builtin"

    # ── Builtin discovery ─────────────────────────────────────

    async def load_builtins(self) -> list[BaseServicePlugin]:
        """Load all built-in plugins from the builtin/ directory."""
        plugins = []

        # Import all builtin plugin modules
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir.exists():
            for file in builtin_dir.glob("*.py"):
                if file.name.startswith("_"):
                    continue
                module_name = f"app.plugins.builtin.{file.stem}"
                try:
                    module = importlib.import_module(module_name)
                    # Find plugin classes in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseServicePlugin)
                            and attr is not BaseServicePlugin
                            and attr is not PromptDrivenPlugin
                        ):
                            plugin = attr()
                            await self.registry.register(plugin)
                            await self.registry.activate(plugin.manifest.id)
                            plugins.append(plugin)
                            logger.info(f"Loaded builtin plugin: {plugin.manifest.id}")
                except Exception as e:
                    logger.exception(f"Failed to load builtin plugin {module_name}: {e}")

        return plugins

    # ── Filesystem discovery ──────────────────────────────────

    async def load_from_filesystem(self, plugins_dir: str | Path) -> list[BaseServicePlugin]:
        """Load plugins from a filesystem directory.

        Each plugin is a directory or a plugin.json file.
        """
        plugins = []
        plugins_path = Path(plugins_dir)

        if not plugins_path.exists():
            logger.warning(f"Plugin directory not found: {plugins_path}")
            return plugins

        for plugin_dir in plugins_path.iterdir():
            if not plugin_dir.is_dir():
                continue

            manifest_path = plugin_dir / "plugin.json"
            if not manifest_path.exists():
                continue

            try:
                plugin = await self._load_plugin_from_dir(plugin_dir)
                await self.registry.register(plugin)
                await self.registry.activate(plugin.manifest.id)
                plugins.append(plugin)
            except Exception as e:
                logger.exception(f"Failed to load plugin from {plugin_dir}: {e}")

        return plugins

    async def _load_plugin_from_dir(self, plugin_dir: Path) -> BaseServicePlugin:
        """Load a single plugin from its directory."""
        manifest_path = plugin_dir / "plugin.json"

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        manifest = self._parse_manifest(manifest_data)

        # Check if it's a Python plugin or prompt-driven
        main_file = plugin_dir / "plugin.py"
        if main_file.exists():
            # Python plugin — import dynamically
            spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}", main_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseServicePlugin)
                    and attr is not BaseServicePlugin
                ):
                    return attr(manifest=manifest)

            raise ValueError(f"No BaseServicePlugin found in {main_file}")
        else:
            # Prompt-driven plugin
            system_prompt = manifest_data.get("system_prompt", "")
            examples = manifest_data.get("examples", [])
            tools_data = manifest_data.get("tools", [])
            tools = [self._parse_tool_definition(t) for t in tools_data]

            return PromptDrivenPlugin(
                manifest=manifest,
                system_prompt=system_prompt,
                examples=examples,
                tools=tools,
            )

    # ── Database loading ──────────────────────────────────────

    async def load_from_db(self, session) -> list[BaseServicePlugin]:
        """Load plugins from ServiceDefinition entries in the database."""
        from sqlalchemy import select

        from app.models.services import ServiceDefinition

        plugins = []

        result = await session.execute(
            select(ServiceDefinition).where(ServiceDefinition.is_active == True)
        )
        definitions = result.scalars().all()

        for definition in definitions:
            try:
                manifest = PluginManifest(
                    id=definition.plugin_id,
                    name=definition.display_name,
                    version=definition.version or "1.0.0",
                    description=definition.description or "",
                    capabilities=[
                        Capability(name=c, display_name=c, description="")
                        for c in (definition.capabilities or [])
                    ],
                    is_builtin=definition.is_builtin,
                    is_prompt_driven=True,
                )

                # DB plugins are always prompt-driven
                config = definition.config_schema or {}
                plugin = PromptDrivenPlugin(
                    manifest=manifest,
                    system_prompt=config.get("system_prompt", ""),
                    examples=config.get("examples", []),
                    tools=[self._parse_tool_definition(t) for t in config.get("tools", [])],
                )

                await self.registry.register(plugin)
                await self.registry.activate(manifest.id)
                plugins.append(plugin)
            except Exception as e:
                logger.exception(f"Failed to load DB plugin {definition.plugin_id}: {e}")

        return plugins

    # ── All sources ───────────────────────────────────────────

    async def load_all(self, session=None) -> list[BaseServicePlugin]:
        """Load plugins from all sources."""
        all_plugins = []

        # 1. Builtins (always load first)
        builtins = await self.load_builtins()
        all_plugins.extend(builtins)

        # 2. Filesystem plugins
        fs_plugins = await self.load_from_filesystem(self._plugin_dir.parent)
        all_plugins.extend(fs_plugins)

        # 3. Database plugins (if session provided)
        if session:
            db_plugins = await self.load_from_db(session)
            all_plugins.extend(db_plugins)

        logger.info(f"Loaded {len(all_plugins)} plugins total")
        return all_plugins

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _parse_manifest(data: dict[str, Any]) -> PluginManifest:
        """Parse manifest from plugin.json dict."""
        return PluginManifest(
            id=data["id"],
            name=data.get("name", data["id"]),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            license=data.get("license", "MIT"),
            capabilities=[
                Capability(
                    name=c.get("name", ""),
                    display_name=c.get("display_name", c.get("name", "")),
                    description=c.get("description", ""),
                    input_schema=c.get("input_schema", {}),
                    output_schema=c.get("output_schema", {}),
                    examples=c.get("examples", []),
                )
                for c in data.get("capabilities", [])
            ],
            intents=data.get("intents", []),
            permissions=[PluginPermission(p) for p in data.get("permissions", [])],
            dependencies=data.get("dependencies", {}),
            config_schema=data.get("config_schema", {}),
            is_builtin=data.get("is_builtin", False),
            is_prompt_driven=data.get("is_prompt_driven", False),
        )

    @staticmethod
    def _parse_tool_definition(data: dict[str, Any]) -> Any:
        """Parse tool definition from JSON."""
        from app.plugins.base import ToolDefinition

        return ToolDefinition(
            name=data["name"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            returns=data.get("returns", {}),
            endpoint=data.get("endpoint", ""),
            method=data.get("method", "POST"),
            auth_required=data.get("auth_required", False),
            rate_limit_per_minute=data.get("rate_limit_per_minute", 60),
        )
