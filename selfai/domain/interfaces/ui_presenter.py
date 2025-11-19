"""UI Presenter interface for user interface interactions.

This module defines the protocol for all UI implementations,
decoupling the presentation layer from business logic.
"""

from typing import Protocol, Literal


StatusLevel = Literal["success", "info", "warning", "error"]


class IUIPresenter(Protocol):
    """Protocol defining the interface for user interface presentations.

    This protocol abstracts away UI implementation details (terminal, GUI,
    web, etc.), allowing different presentation layers to be swapped.

    Following the Dependency Inversion Principle, application services
    depend on this abstraction, not on concrete UI implementations.

    Methods:
        status: Display a status message.
        stream_prefix: Display a prefix before streaming output.
        streaming_chunk: Display a chunk of streaming text.
        typing_animation: Display text with typing effect.
        start_spinner: Start a loading spinner.
        stop_spinner: Stop the loading spinner.
        confirm: Ask user for yes/no confirmation.
        choose_option: Present a list of options for selection.
        show_plan: Display a plan structure.
        clear: Clear the display.
    """

    def status(
        self,
        message: str,
        level: StatusLevel = "info",
    ) -> None:
        """Display a status message to the user.

        Args:
            message: The message text to display.
            level: Message severity level affecting visual presentation.
                - "success": Positive confirmation (green)
                - "info": Neutral information (blue)
                - "warning": Cautionary message (yellow)
                - "error": Error or failure (red)

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.status("Configuration loaded successfully", "success")
            ✓ Configuration loaded successfully
            >>> ui.status("API key not found", "error")
            ✗ API key not found
        """
        ...

    def stream_prefix(self, prefix: str) -> None:
        """Display a prefix label before streaming output begins.

        Typically used to show which LLM backend is generating the response.

        Args:
            prefix: Label text (e.g., "AnythingLLM", "CPU", "Planner").

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.stream_prefix("AnythingLLM")
            [AnythingLLM] ▶
        """
        ...

    def streaming_chunk(self, chunk: str) -> None:
        """Display a chunk of streaming text without newline.

        Used for real-time display of LLM generation.

        Args:
            chunk: Text chunk to display (word, token, or character).

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.stream_prefix("CPU")
            >>> for word in ["Hello", " ", "world", "!"]:
            ...     ui.streaming_chunk(word)
            [CPU] ▶ Hello world!
        """
        ...

    def typing_animation(self, text: str, delay: float = 0.01) -> None:
        """Display text with a typing animation effect.

        Args:
            text: Complete text to display.
            delay: Delay in seconds between each character.

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.typing_animation("Processing your request...")
            Processing your request...  # (appears character by character)
        """
        ...

    def start_spinner(self, message: str) -> None:
        """Start displaying a loading spinner with message.

        Args:
            message: Status message to display alongside spinner.

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.start_spinner("Loading model...")
            ⠋ Loading model...
        """
        ...

    def stop_spinner(self) -> None:
        """Stop and hide the loading spinner.

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.start_spinner("Processing...")
            >>> time.sleep(2)
            >>> ui.stop_spinner()
        """
        ...

    def confirm(
        self,
        prompt: str,
        default_yes: bool = True,
    ) -> bool:
        """Ask the user for yes/no confirmation.

        Args:
            prompt: Question to ask the user.
            default_yes: Default answer if user presses Enter without input.

        Returns:
            True if user confirms, False otherwise.

        Example:
            >>> ui = TerminalPresenter()
            >>> if ui.confirm("Proceed with plan execution?"):
            ...     print("Executing plan...")
            Proceed with plan execution? [Y/n]: y
            Executing plan...
        """
        ...

    def choose_option(
        self,
        prompt: str,
        options: list[str],
        default_index: int = 0,
    ) -> int:
        """Present a list of options and get user selection.

        Args:
            prompt: Question or instruction for the selection.
            options: List of option strings to display.
            default_index: Index of the default option (if Enter pressed).

        Returns:
            Index of the selected option (0-based).

        Raises:
            ValueError: If options list is empty.
            IndexError: If default_index is out of range.

        Example:
            >>> ui = TerminalPresenter()
            >>> backends = ["AnythingLLM", "QNN", "CPU"]
            >>> choice = ui.choose_option("Select LLM backend:", backends)
            Select LLM backend:
            1. AnythingLLM
            2. QNN
            3. CPU
            Your choice [1]: 2
            >>> print(backends[choice])
            QNN
        """
        ...

    def show_plan(self, plan_data: dict[str, object]) -> None:
        """Display a plan structure in a readable format.

        Args:
            plan_data: Plan dictionary containing subtasks and merge strategy.

        Example:
            >>> ui = TerminalPresenter()
            >>> plan = {
            ...     "subtasks": [
            ...         {"id": "S1", "title": "Analyze requirements"},
            ...         {"id": "S2", "title": "Design architecture"}
            ...     ],
            ...     "merge": {"strategy": "Combine analysis and design"}
            ... }
            >>> ui.show_plan(plan)
            Plan Overview:
            ├── S1: Analyze requirements
            └── S2: Design architecture
            Merge: Combine analysis and design
        """
        ...

    def clear(self) -> None:
        """Clear the display/screen.

        Example:
            >>> ui = TerminalPresenter()
            >>> ui.clear()
        """
        ...
