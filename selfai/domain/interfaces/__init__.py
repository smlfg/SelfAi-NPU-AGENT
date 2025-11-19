"""Domain interfaces (ports) for dependency inversion.

This module defines abstract protocols that infrastructure adapters must implement.
Following the Dependency Inversion Principle, high-level domain logic depends on
these abstractions, not on concrete implementations.

Protocols:
    - ILLMProvider: Language model inference interface
    - IStorageRepository: Persistent storage interface
    - IUIPresenter: User interface presentation interface
    - IPlannerService: Planning service interface
    - IToolProvider: Tool execution interface

Example:
    >>> from selfai.domain.interfaces import ILLMProvider
    >>> class MyLLMAdapter(ILLMProvider):
    ...     def generate_response(self, prompt: str) -> str:
    ...         return "Implemented response"
"""

from selfai.domain.interfaces.llm_provider import ILLMProvider
from selfai.domain.interfaces.storage import IStorageRepository
from selfai.domain.interfaces.ui_presenter import IUIPresenter
from selfai.domain.interfaces.planner import IPlannerService
from selfai.domain.interfaces.tool_provider import IToolProvider

__all__ = [
    "ILLMProvider",
    "IStorageRepository",
    "IUIPresenter",
    "IPlannerService",
    "IToolProvider",
]
