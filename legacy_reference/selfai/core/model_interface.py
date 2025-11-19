import yaml
from typing import List, Dict, Any
from openai import OpenAI

# A message is a dictionary with a role and content
Message = Dict[str, str]

class ModelInterface:
    """A generic interface to communicate with an OpenAI-compatible LLM."""
    def __init__(self, provider_name: str = "local-ollama"):
        """Initialize the model interface by reading from the main config file."""
        
        # Read the main configuration file
        try:
            with open("config_extended.yaml", "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            raise RuntimeError("Could not find config_extended.yaml. Please ensure it is in the root directory.")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing config_extended.yaml: {e}")

        # Find the specified provider in the planner configuration
        provider_config = None
        for provider in config.get("planner", {}).get("providers", []):
            if provider.get("name") == provider_name:
                provider_config = provider
                break
        
        if not provider_config:
            raise ValueError(f"Provider '{provider_name}' not found in config_extended.yaml under planner.providers")

        self.model = provider_config.get("model")
        base_url = provider_config.get("base_url")
        # For simplicity, we are not handling headers or API keys for local Ollama in this example
        # In a real application, you would fetch the api_key and headers here.
        api_key = "ollama" # Default for local Ollama

        if not self.model or not base_url:
            raise ValueError(f"Provider '{provider_name}' is missing 'model' or 'base_url' in the configuration.")

        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def chat_completion(self, messages: List[Message], temperature: float = 0.1) -> str:
        """Send messages to the language model and get a response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                # We ask for a JSON response, but will handle cases where it's not.
                response_format={"type": "json_object"} 
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[ModelInterface] Error calling LLM: {e}")
            # Return a stringified error to be handled by the agent
            return f"Error communicating with the model: {e}"