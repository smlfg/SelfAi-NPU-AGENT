import json
from typing import List, Dict

from selfai.core.model_interface import ModelInterface, Message
from selfai.tools.tool_registry import get_tool, get_all_tool_schemas

class Agent:
    """The main agent class that orchestrates the tool-calling loop."""
    def __init__(self, provider_name: str = "local-ollama"):
        """Initializes the agent with a model interface and tools."""
        self.model = ModelInterface(provider_name=provider_name)
        self.tools = {schema['name']: get_tool(schema['name']) for schema in get_all_tool_schemas()}
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Builds the system prompt with tool descriptions."""
        tool_schemas = get_all_tool_schemas()
        tools_json_str = json.dumps(tool_schemas, indent=2)

        return f"""You are a helpful assistant that has access to a set of tools. 
Your job is to determine if a tool can help answer the user's request. 
If a tool is useful, you must respond with a JSON object representing the tool call. 
If no tool is appropriate, you must respond with a regular text-based answer.

**Here are the available tools:**
```json
{tools_json_str}
```

**Rules for Tool Use:**
1. If you decide to use a tool, your response MUST be a single JSON object and nothing else. No additional text, explanations, or markdown formatting.
2. The JSON object must have the following format:
```json
{{
    "tool_name": "<name_of_the_tool>",
    "arguments": {{
        "<arg_name_1>": "<value_1>",
        "<arg_name_2>": "<value_2>"
    }}
}}
```
3. If no tool is suitable for the user's request, provide a helpful, text-based answer as a normal chatbot would."""

    def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """Executes a tool and returns the result as a string."""
        print(f"[Agent] Executing tool: '{tool_name}' with arguments: {arguments}")
        tool = self.tools.get(tool_name)
        if not tool:
            return f'Error: Tool "{tool_name}" not found.'
        try:
            return tool.run(**arguments)
        except Exception as e:
            return f"Error executing tool {tool_name}: {e}"

    def run(self, user_input: str) -> str:
        """Runs the main agent loop."""
        history: List[Message] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        # 1. First call to the model
        print("[Agent] Thinking...")
        llm_response_str = self.model.chat_completion(history)

        # 2. Check if the response is a tool call
        try:
            # A response starting with '{' is likely a JSON tool call
            if llm_response_str.strip().startswith('{'):
                tool_call = json.loads(llm_response_str)
                if "tool_name" in tool_call and "arguments" in tool_call:
                    print(f"[Agent] Decided to call tool: {tool_call['tool_name']}")
                    
                    # 3. Execute the tool
                    tool_result = self._execute_tool(
                        tool_name=tool_call["tool_name"],
                        arguments=tool_call["arguments"]
                    )

                    # 4. (Future Improvement) Send result back to LLM for a final response
                    # For now, we just return the tool's output directly.
                    return tool_result
        except json.JSONDecodeError:
            # Not a valid JSON, so treat it as a direct answer
            pass

        # 5. If it wasn't a valid tool call, return the response as the final answer
        print("[Agent] Responded directly.")
        return llm_response_str
