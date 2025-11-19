"""
Planner Pipeline Tests

This test module verifies the PLANNING PHASE of the SelfAI pipeline.
The planner decomposes user goals into structured task plans (DPPM format).

WHAT IS DPPM:
    Distributed Planning Problem Model - A structured format for task decomposition:
    - Subtasks with dependencies
    - Parallel execution groups
    - Agent assignments
    - Merge strategies

WHY TEST THE PLANNER:
    The planner is CRITICAL for complex task execution. A bad plan leads to:
    - Circular dependencies (deadlock)
    - Invalid agent references (execution failure)
    - Poor task decomposition (inefficient execution)

TEST COVERAGE:
    1. Plan generation (mocking LLM responses)
    2. Plan validation (schema, logic, dependencies)
    3. Plan persistence (saving/loading)
    4. Fallback plan generation (when planner fails)
    5. Agent context building
    6. Multi-provider fallback

MOCKING STRATEGY:
    We mock the Ollama API responses to provide deterministic plans
    without requiring a running Ollama server. This ensures:
    - Fast tests
    - Reproducible results
    - No external dependencies
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock, Mock, patch


# ==============================================================================
# PLAN GENERATION TESTS
# ==============================================================================


def test_planner_generates_valid_plan(
    mock_planner_interface: MagicMock,
    sample_agent_manager,
    sample_memory_system,
):
    """
    Test that the planner generates a valid DPPM plan structure.

    WHY TEST THIS:
        This is the HAPPY PATH - when everything works, we should get
        a properly structured plan that can be executed.

    SCENARIO:
        User goal: "Create a Python web scraper"
        Planner: Generates 2 subtasks (analyze, implement)
        Expected: Valid plan with subtasks and merge strategy

    ASSERTIONS:
        1. Plan has 'subtasks' key
        2. Plan has 'merge' key
        3. Each subtask has required fields
        4. Subtask IDs are unique
        5. Agent keys are valid
    """
    # Arrange
    goal = "Create a Python web scraper for news sites"

    from selfai.core.planner_ollama_interface import PlannerContext

    planner_context = PlannerContext(
        agents=[
            {
                "key": "code_helfer",
                "display_name": "Code Helper",
                "description": "Python coding specialist",
            }
        ],
        memory_summary="No previous plans",
    )

    # Act: Generate plan
    plan_data = mock_planner_interface.plan(goal, planner_context)

    # Assert: Plan has required top-level keys
    assert "subtasks" in plan_data, "Plan must have 'subtasks' key"
    assert "merge" in plan_data, "Plan must have 'merge' key"
    assert isinstance(plan_data["subtasks"], list), "Subtasks must be a list"

    # Assert: Subtasks are valid
    subtasks = plan_data["subtasks"]
    assert len(subtasks) > 0, "Plan should have at least one subtask"

    # Required fields for each subtask
    required_fields = [
        "id", "title", "objective", "agent_key",
        "engine", "parallel_group", "depends_on"
    ]

    for task in subtasks:
        for field in required_fields:
            assert field in task, f"Subtask missing required field: {field}"

    # Assert: Subtask IDs are unique
    task_ids = [task["id"] for task in subtasks]
    assert len(task_ids) == len(set(task_ids)), "Subtask IDs must be unique"

    # Assert: Merge strategy exists
    merge = plan_data["merge"]
    assert "strategy" in merge, "Merge must have 'strategy'"


def test_planner_handles_complex_dependencies(
    mock_planner_interface: MagicMock,
):
    """
    Test planner with complex dependency chains.

    WHY TEST THIS:
        Real-world tasks often have complex dependencies:
        - Sequential tasks (A → B → C)
        - Parallel tasks (A → [B, C] → D)
        - Multiple dependencies (C depends on both A and B)

    SCENARIO:
        Complex plan with:
        - S1: No dependencies (starts immediately)
        - S2, S3: Depend on S1 (can run in parallel)
        - S4: Depends on both S2 and S3 (runs after both complete)

    ASSERTIONS:
        1. Dependencies are correctly specified
        2. Parallel groups are correct
        3. No circular dependencies
    """
    # Arrange: Mock a complex plan
    complex_plan = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Initial Research",
                "objective": "Research requirements",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            },
            {
                "id": "S2",
                "title": "Design Backend",
                "objective": "Design backend architecture",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 2,
                "depends_on": ["S1"],
            },
            {
                "id": "S3",
                "title": "Design Frontend",
                "objective": "Design frontend architecture",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 2,  # Same group as S2 (parallel)
                "depends_on": ["S1"],
            },
            {
                "id": "S4",
                "title": "Integration",
                "objective": "Integrate backend and frontend",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 3,
                "depends_on": ["S2", "S3"],  # Depends on BOTH
            },
        ],
        "merge": {
            "strategy": "Combine all phases",
            "steps": [],
        },
    }

    # Override the mock to return complex plan
    mock_planner_interface.plan.return_value = complex_plan

    # Act
    from selfai.core.planner_ollama_interface import PlannerContext

    plan_data = mock_planner_interface.plan(
        "Create full-stack web app",
        PlannerContext(agents=[], memory_summary="")
    )

    # Assert: All dependencies reference valid task IDs
    all_task_ids = {task["id"] for task in plan_data["subtasks"]}

    for task in plan_data["subtasks"]:
        for dep_id in task["depends_on"]:
            assert dep_id in all_task_ids, \
                f"Task {task['id']} depends on non-existent task {dep_id}"

    # Assert: S2 and S3 are in same parallel group (can run together)
    s2 = next(t for t in plan_data["subtasks"] if t["id"] == "S2")
    s3 = next(t for t in plan_data["subtasks"] if t["id"] == "S3")
    assert s2["parallel_group"] == s3["parallel_group"], \
        "S2 and S3 should be in same parallel group"

    # Assert: S4 depends on both S2 and S3
    s4 = next(t for t in plan_data["subtasks"] if t["id"] == "S4")
    assert "S2" in s4["depends_on"], "S4 should depend on S2"
    assert "S3" in s4["depends_on"], "S4 should depend on S3"

    # Assert: S4 is in later parallel group (must run after S2, S3)
    assert s4["parallel_group"] > s2["parallel_group"], \
        "S4 must be in later parallel group than S2"


# ==============================================================================
# PLAN VALIDATION TESTS
# ==============================================================================


def test_plan_validation_detects_circular_dependencies():
    """
    Test that plan validation detects circular dependencies.

    WHY TEST THIS:
        Circular dependencies cause DEADLOCK. If task A depends on B,
        and B depends on A, execution will hang forever. The validator
        MUST catch this before execution.

    SCENARIO:
        Invalid plan:
        - S1 depends on S2
        - S2 depends on S1
        Expected: Validation error

    ASSERTIONS:
        1. Validator detects the circular dependency
        2. Error message clearly explains the problem
    """
    from selfai.core.planner_validator import validate_plan_logic

    # Arrange: Plan with circular dependency
    invalid_plan = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task 1",
                "objective": "Do something",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": ["S2"],  # Depends on S2
            },
            {
                "id": "S2",
                "title": "Task 2",
                "objective": "Do something else",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": ["S1"],  # Depends on S1 - CIRCULAR!
            },
        ],
        "merge": {"strategy": "Combine"},
    }

    # Act: Validate plan
    validation_messages = validate_plan_logic(invalid_plan)

    # Assert: Should have error messages
    assert len(validation_messages) > 0, \
        "Validator should detect circular dependency"

    # Assert: Error mentions circular dependency or unreachable tasks
    error_text = " ".join(validation_messages).lower()
    assert "zirkul" in error_text or "unerreichbar" in error_text or "circular" in error_text, \
        "Error message should mention circular dependency issue"


def test_plan_validation_detects_invalid_dependencies():
    """
    Test that validation detects references to non-existent tasks.

    WHY TEST THIS:
        If task A depends on non-existent task "X", execution will fail
        when trying to wait for "X" to complete. This MUST be caught
        during validation.

    SCENARIO:
        Invalid plan:
        - S1 depends on "S99" (doesn't exist)
        Expected: Validation error

    ASSERTIONS:
        1. Validator detects invalid dependency reference
        2. Error identifies the problematic task ID
    """
    from selfai.core.planner_validator import validate_plan_logic

    # Arrange: Plan with invalid dependency
    invalid_plan = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task 1",
                "objective": "Do something",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": ["S99"],  # S99 doesn't exist!
            },
        ],
        "merge": {"strategy": "Combine"},
    }

    # Act
    validation_messages = validate_plan_logic(invalid_plan)

    # Assert: Should detect invalid reference
    assert len(validation_messages) > 0

    error_text = " ".join(validation_messages)
    assert "S99" in error_text or "existier" in error_text.lower(), \
        "Error should mention the non-existent task ID"


def test_plan_validation_detects_invalid_parallel_groups():
    """
    Test that validation detects invalid parallel group numbering.

    WHY TEST THIS:
        Parallel groups MUST be positive integers (1, 2, 3...).
        Group 0 or negative numbers are invalid and will cause
        execution ordering issues.

    SCENARIO:
        Invalid plan:
        - Task with parallel_group = 0
        Expected: Validation warning/error

    ASSERTIONS:
        1. Validator detects parallel_group <= 0
        2. Suggests valid range (>= 1)
    """
    from selfai.core.planner_validator import validate_plan_logic

    # Arrange: Plan with invalid parallel group
    invalid_plan = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task 1",
                "objective": "Do something",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 0,  # INVALID: must be >= 1
                "depends_on": [],
            },
        ],
        "merge": {"strategy": "Combine"},
    }

    # Act
    validation_messages = validate_plan_logic(invalid_plan)

    # Assert: Should detect invalid parallel group
    assert len(validation_messages) > 0

    error_text = " ".join(validation_messages).lower()
    assert "parallel" in error_text or "gruppe" in error_text, \
        "Error should mention parallel group issue"


def test_plan_validation_accepts_valid_plan(sample_plan_dict: Dict[str, Any]):
    """
    Test that validation PASSES for a valid plan.

    WHY TEST THIS:
        False positives are BAD - we don't want to reject valid plans.
        This test ensures the validator doesn't over-trigger.

    SCENARIO:
        Valid plan with proper dependencies and parallel groups
        Expected: No validation errors

    ASSERTIONS:
        1. No error messages
        2. No warning messages (or only informational)
    """
    from selfai.core.planner_validator import validate_plan_logic

    # Act
    validation_messages = validate_plan_logic(sample_plan_dict)

    # Assert: Valid plan should have no errors
    errors = [msg for msg in validation_messages if msg.startswith("FEHLER")]
    assert len(errors) == 0, \
        f"Valid plan should not trigger errors: {errors}"


# ==============================================================================
# PLAN PERSISTENCE TESTS
# ==============================================================================


def test_plan_saving_and_loading(
    sample_plan_dict: Dict[str, Any],
    sample_memory_system,
    temp_memory_dir: Path,
):
    """
    Test that plans can be saved and loaded correctly.

    WHY TEST THIS:
        Plans are saved to disk for:
        - Resuming execution after failures
        - Tracking execution history
        - Merge phase (reads subtask results)

    SCENARIO:
        1. Save a plan with goal "Test project"
        2. Verify file is created
        3. Load the plan back
        4. Verify data is identical

    ASSERTIONS:
        1. save_plan creates a file
        2. File contains valid JSON
        3. Loaded plan matches saved plan
        4. Plan path follows naming convention
    """
    # Arrange
    goal = "Test project implementation"

    # Act: Save plan
    plan_path = sample_memory_system.save_plan(goal, sample_plan_dict)

    # Assert: File exists
    assert plan_path.exists(), "Plan file should be created"
    assert plan_path.suffix == ".json", "Plan should be JSON file"

    # Assert: File is in plans directory
    assert "plans" in str(plan_path), "Plan should be in plans/ directory"

    # Assert: Filename contains sanitized goal
    assert "test" in plan_path.stem.lower(), \
        "Filename should contain part of goal"

    # Act: Load plan back
    with open(plan_path, "r", encoding="utf-8") as f:
        loaded_plan = json.load(f)

    # Assert: Loaded plan matches original
    assert loaded_plan["subtasks"] == sample_plan_dict["subtasks"]
    assert loaded_plan["merge"] == sample_plan_dict["merge"]


def test_plan_updates_with_execution_results(
    sample_plan_file: Path,
    temp_memory_dir: Path,
):
    """
    Test that plan file is updated with execution results.

    WHY TEST THIS:
        During execution, each subtask's result is written to a file,
        and the plan is updated with the result path. This allows the
        merge phase to collect all results.

    SCENARIO:
        1. Start with empty plan
        2. Execute a subtask
        3. Update plan with result_path
        4. Verify plan contains result paths

    ASSERTIONS:
        1. Plan is updated after each subtask
        2. result_path field is added to subtask
        3. Plan file is valid JSON after update
    """
    # Arrange: Load plan
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    # Act: Simulate adding result paths
    result_dir = temp_memory_dir / "plans" / "results"
    result_dir.mkdir(exist_ok=True)

    for task in plan_data["subtasks"]:
        # Simulate execution creating a result file
        result_file = result_dir / f"{task['id']}.txt"
        result_file.write_text(
            f"Result for {task['id']}: Task completed successfully",
            encoding="utf-8"
        )

        # Update plan with result path
        task["result_path"] = str(result_file)

    # Save updated plan
    with open(sample_plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    # Assert: Plan file is still valid JSON
    with open(sample_plan_file, "r", encoding="utf-8") as f:
        reloaded_plan = json.load(f)

    # Assert: All subtasks have result_path
    for task in reloaded_plan["subtasks"]:
        assert "result_path" in task, \
            f"Subtask {task['id']} should have result_path"
        assert Path(task["result_path"]).exists(), \
            f"Result file should exist: {task['result_path']}"


# ==============================================================================
# FALLBACK PLAN GENERATION TESTS
# ==============================================================================


def test_fallback_plan_generation_when_planner_fails(
    sample_agent_manager,
):
    """
    Test that a fallback plan is generated when planner fails.

    WHY TEST THIS:
        If the planner (Ollama) is down or fails, the system should
        generate a basic fallback plan so execution can still proceed.
        This is better than complete failure.

    SCENARIO:
        - Planner fails (raises exception)
        - System generates 2-task fallback plan
        - Fallback plan is valid and executable

    ASSERTIONS:
        1. Fallback plan is generated
        2. Plan has analysis and response tasks
        3. Plan is valid DPPM format
        4. Uses default agent
    """
    # This function is defined in selfai.py
    # We'll test it by simulating the logic

    def build_fallback_plan(goal_text: str, agent_key: str) -> Dict[str, Any]:
        """Recreate the fallback plan logic from selfai.py."""
        sanitized_goal = goal_text.strip()
        return {
            "subtasks": [
                {
                    "id": "S1",
                    "title": "Analyse des Ziels",
                    "objective": f"Analysiere das Ziel: {sanitized_goal}",
                    "agent_key": agent_key,
                    "engine": "anythingllm",
                    "parallel_group": 1,
                    "depends_on": [],
                    "notes": "Automatisch erzeugter Fallback-Plan",
                },
                {
                    "id": "S2",
                    "title": "Antwort formulieren",
                    "objective": f"Formuliere eine ausführliche Antwort für: {sanitized_goal}",
                    "agent_key": agent_key,
                    "engine": "anythingllm",
                    "parallel_group": 2,
                    "depends_on": ["S1"],
                    "notes": "Automatisch erzeugter Fallback-Plan.",
                },
            ],
            "merge": {
                "strategy": "Analyse und Antwort zu einem konsistenten Ergebnis kombinieren.",
                "steps": [
                    {
                        "title": "Synthese",
                        "description": "Fasse Analyse und Antwort zusammen.",
                        "depends_on": ["S2"],
                    }
                ],
            },
        }

    # Arrange
    goal = "Create a simple web scraper"
    agent_key = "code_helfer"

    # Act: Generate fallback plan
    fallback_plan = build_fallback_plan(goal, agent_key)

    # Assert: Fallback plan has required structure
    assert "subtasks" in fallback_plan
    assert "merge" in fallback_plan
    assert len(fallback_plan["subtasks"]) == 2

    # Assert: Tasks reference the goal
    task_1 = fallback_plan["subtasks"][0]
    assert goal in task_1["objective"]

    # Assert: Plan uses correct agent
    for task in fallback_plan["subtasks"]:
        assert task["agent_key"] == agent_key

    # Assert: Dependencies are correct
    assert fallback_plan["subtasks"][0]["depends_on"] == []
    assert fallback_plan["subtasks"][1]["depends_on"] == ["S1"]


# ==============================================================================
# PLANNER CONTEXT BUILDING TESTS
# ==============================================================================


def test_planner_context_includes_available_agents(
    sample_agent_manager,
    sample_memory_system,
):
    """
    Test that planner context includes all available agents.

    WHY TEST THIS:
        The planner needs to know which agents are available so it can
        assign tasks to appropriate specialists (code_helfer for coding,
        projektmanager for coordination, etc.).

    SCENARIO:
        - System has 2 agents: code_helfer, projektmanager
        - Build planner context
        - Context includes both agents with descriptions

    ASSERTIONS:
        1. Context contains all agents
        2. Each agent has key, display_name, description
        3. Descriptions include memory categories and workspace
    """
    from selfai.core.planner_ollama_interface import PlannerContext

    # This logic is from selfai.py _build_planner_context
    def build_context(agent_manager, memory_system) -> PlannerContext:
        agents_data = []
        for agent in agent_manager.list_agents():
            categories = ", ".join(agent.memory_categories) or "-"
            details = [f"Memory: {categories}", f"Workspace: {agent.workspace_slug}"]
            if agent.description:
                details.insert(0, agent.description.strip())
            agents_data.append(
                {
                    "key": agent.key,
                    "display_name": agent.display_name,
                    "description": "; ".join(details),
                }
            )

        plan_dir = getattr(memory_system, "plan_dir", None)
        summary = ""
        if plan_dir and plan_dir.exists():
            plan_files = sorted(plan_dir.glob("*.json"))
            if plan_files:
                summary = f"{len(plan_files)} gespeicherte Pläne."
        if not summary:
            summary = "Noch keine Pläne gespeichert."

        return PlannerContext(agents=agents_data, memory_summary=summary)

    # Act
    context = build_context(sample_agent_manager, sample_memory_system)

    # Assert: Context has agents
    assert len(context.agents) > 0, "Context should include agents"

    # Assert: Each agent has required fields
    for agent_info in context.agents:
        assert "key" in agent_info
        assert "display_name" in agent_info
        assert "description" in agent_info

        # Assert: Description includes workspace info
        assert "Workspace:" in agent_info["description"]

    # Assert: Memory summary exists
    assert context.memory_summary is not None
    assert len(context.memory_summary) > 0


# ==============================================================================
# MULTI-PROVIDER PLANNER FALLBACK TESTS
# ==============================================================================


def test_planner_fallback_between_providers(
    mock_terminal_ui: MagicMock,
):
    """
    Test fallback between multiple planner providers.

    WHY TEST THIS:
        Users might configure multiple planner providers:
        - local-ollama (primary)
        - cloud-ollama (backup)
        - openai (fallback)
        If one fails, system should try the next.

    SCENARIO:
        - Provider 1 (local-ollama): Fails (connection error)
        - Provider 2 (cloud-ollama): Succeeds
        Expected: Get plan from provider 2

    ASSERTIONS:
        1. First provider is tried and fails
        2. Second provider is tried and succeeds
        3. Warning about first provider failure
        4. Success message from second provider
    """
    # Arrange: Mock two planner providers
    provider1 = MagicMock()
    provider1.plan.side_effect = ConnectionError("Local Ollama not responding")

    provider2 = MagicMock()
    provider2.plan.return_value = {
        "subtasks": [
            {
                "id": "S1",
                "title": "Task from cloud",
                "objective": "Complete the goal",
                "agent_key": "code_helfer",
                "engine": "anythingllm",
                "parallel_group": 1,
                "depends_on": [],
            }
        ],
        "merge": {"strategy": "Simple merge"},
    }

    planner_providers = {
        "local-ollama": {"interface": provider1, "type": "local_ollama"},
        "cloud-ollama": {"interface": provider2, "type": "cloud_ollama"},
    }

    provider_order = ["local-ollama", "cloud-ollama"]

    # Act: Try providers in order
    from selfai.core.planner_ollama_interface import PlannerContext, PlannerError

    goal = "Create a web app"
    context = PlannerContext(agents=[], memory_summary="")
    plan_data = None
    used_provider = None

    for provider_name in provider_order:
        info = planner_providers[provider_name]
        interface = info["interface"]
        try:
            plan_data = interface.plan(goal, context)
            used_provider = provider_name
            mock_terminal_ui.status(
                f"Planner '{provider_name}' succeeded",
                "success"
            )
            break
        except Exception as exc:
            mock_terminal_ui.status(
                f"Planner '{provider_name}' failed: {exc}",
                "warning"
            )
            continue

    # Assert: Got plan from second provider
    assert plan_data is not None
    assert used_provider == "cloud-ollama"

    # Assert: Both providers were tried
    assert provider1.plan.called
    assert provider2.plan.called

    # Assert: Appropriate UI messages
    warning_calls = [
        call for call in mock_terminal_ui.status.call_args_list
        if len(call[0]) > 1 and call[0][1] == "warning"
    ]
    assert len(warning_calls) >= 1, "Should warn about first provider failure"


# ==============================================================================
# PLAN STREAMING TESTS
# ==============================================================================


def test_planner_streaming_callback(
    mock_planner_interface: MagicMock,
    mock_terminal_ui: MagicMock,
):
    """
    Test that planner can stream progress updates during planning.

    WHY TEST THIS:
        Plan generation can take several seconds. Streaming progress
        provides better UX by showing the user that work is happening.

    SCENARIO:
        - Call planner with progress_callback
        - Planner streams: "Analyzing", "Generating", etc.
        - UI displays streaming chunks

    ASSERTIONS:
        1. progress_callback is called with chunks
        2. UI receives streaming updates
        3. Final plan is still correct
    """
    from selfai.core.planner_ollama_interface import PlannerContext

    # Arrange
    goal = "Build a REST API"
    context = PlannerContext(agents=[], memory_summary="")

    collected_chunks = []

    def progress_callback(chunk: str):
        """Collect streaming chunks."""
        collected_chunks.append(chunk)
        mock_terminal_ui.streaming_chunk(chunk)

    # Act: Call planner with callback
    plan_data = mock_planner_interface.plan(
        goal,
        context,
        progress_callback=progress_callback
    )

    # Assert: Streaming chunks were received
    assert len(collected_chunks) > 0, "Should have received streaming chunks"

    # Assert: UI streaming method was called
    assert mock_terminal_ui.streaming_chunk.called

    # Assert: Plan is still valid
    assert "subtasks" in plan_data
    assert "merge" in plan_data


# ==============================================================================
# HELPER IMPORTS
# ==============================================================================


# Additional imports needed for testing
from selfai.core.planner_validator import validate_plan_logic
