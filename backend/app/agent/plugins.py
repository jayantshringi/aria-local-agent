"""Dynamic plugin loader for user-defined tools in ~/.aria/plugins/."""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from app.agent.base_tool import BaseTool
from app.agent.registry import tool_registry
from app.config import get_settings

logger = logging.getLogger("aria.agent.plugins")


def load_plugins_from_directory(plugin_dir: Path | None = None) -> list[str]:
    """
    Scan plugin_dir for Python files (.py) and dynamically register
    any discovered BaseTool subclasses into the ToolRegistry.
    """
    settings = get_settings()
    target_dir = plugin_dir if plugin_dir is not None else settings.plugins_dir_path

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        return []

    loaded_tool_names: list[str] = []

    for file_path in target_dir.glob("*.py"):
        if file_path.name.startswith("_") or file_path.name.startswith("."):
            continue

        module_name = f"aria_plugin_{file_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load plugin spec for {file_path}")
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find all BaseTool subclasses defined in this module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                    and not inspect.isabstract(attr)
                ):
                    try:
                        tool_instance = attr()
                        tool_registry.register(tool_instance)
                        loaded_tool_names.append(tool_instance.name)
                        logger.info(
                            f"Loaded plugin tool '{tool_instance.name}' ({tool_instance.risk_level.value}) from {file_path.name}"
                        )
                    except Exception as inst_err:
                        logger.error(
                            f"Failed to instantiate plugin tool class {attr_name} in {file_path.name}: {inst_err}"
                        )

        except Exception as e:
            logger.error(f"Failed to load plugin module {file_path.name}: {e}", exc_info=True)

    return loaded_tool_names
