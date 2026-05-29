from __future__ import annotations

from typing import Dict, Callable, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaskHandler:
    name: str
    handler: Callable
    description: str = ""
    version: str = "1.0.0"


class TaskRegistry:
    def __init__(self):
        self._handlers: Dict[str, TaskHandler] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        version: str = "1.0.0",
    ):
        if name in self._handlers:
            logger.warning(f"Task handler '{name}' already exists, overwriting")
        
        self._handlers[name] = TaskHandler(
            name=name,
            handler=handler,
            description=description,
            version=version,
        )
        logger.info(f"Registered task handler: {name} v{version}")

    def get(self, name: str) -> Optional[TaskHandler]:
        return self._handlers.get(name)

    def list_handlers(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "description": handler.description,
                "version": handler.version,
            }
            for name, handler in self._handlers.items()
        }

    def unregister(self, name: str):
        if name in self._handlers:
            del self._handlers[name]
            logger.info(f"Unregistered task handler: {name}")


registry = TaskRegistry()
