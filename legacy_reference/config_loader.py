import os
import re
import sys
import yaml
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _resolve_env_template(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_val = os.getenv(var_name)
        if env_val is None:
            return match.group(0)
        return env_val

    return ENV_VAR_PATTERN.sub(replace, value)


# --- Dataclasses for structured configuration ---
@dataclass
class NPUConfig:
    api_key: str
    base_url: str
    workspace_slug: str

@dataclass
class CPUConfig:
    model_path: str
    n_ctx: int
    n_gpu_layers: int

@dataclass
class SystemConfig:
    streaming_enabled: bool
    stream_timeout: float | None = None

@dataclass
class AgentConfig:
    default_agent: str

@dataclass
class PlannerProviderConfig:
    name: str
    type: str
    base_url: str
    model: str
    timeout: float
    max_tokens: int
    headers: Dict[str, str]


@dataclass
class PlannerConfig:
    enabled: bool
    execution_timeout: float
    providers: list[PlannerProviderConfig]

@dataclass
class MergeProviderConfig:
    name: str
    type: str
    base_url: str
    model: str
    timeout: float
    max_tokens: int
    headers: Dict[str, str]


@dataclass
class MergeConfig:
    enabled: bool
    providers: list[MergeProviderConfig]

@dataclass
class AppConfig:
    npu_provider: NPUConfig
    cpu_fallback: CPUConfig
    system: SystemConfig
    agent_config: AgentConfig
    planner: PlannerConfig
    merge: MergeConfig

# --- Loader Logic ---
def _normalize_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Accepts either the structured SelfAI config or the simple NPU config template."""

    if not isinstance(raw_config, dict):
        raise ValueError("Konfigurationsdatei enthält keine gültigen Schlüssel/Wert-Paare.")

    if 'npu_provider' in raw_config:
        # Already in structured format – ensure nested dicts exist.
        config_data = dict(raw_config)
        config_data.setdefault('cpu_fallback', {})
        config_data.setdefault('system', {})
        config_data.setdefault('agent_config', {})
        planner_section = config_data.setdefault('planner', {})
        if 'providers' not in planner_section:
            provider_entry = {
                'name': planner_section.get('name', 'planner-local'),
                'type': planner_section.get('type', 'local_ollama'),
                'base_url': planner_section.get('base_url', 'http://localhost:11434'),
                'model': planner_section.get('model', 'gemma3:1b'),
                'timeout': planner_section.get('timeout', 180.0),
                'max_tokens': planner_section.get('max_tokens', 768),
            }
            if 'headers' in planner_section:
                provider_entry['headers'] = planner_section['headers']
            if 'api_key_env' in planner_section:
                provider_entry['api_key_env'] = planner_section['api_key_env']
            if 'api_key_header' in planner_section:
                provider_entry['api_key_header'] = planner_section['api_key_header']
            planner_section['providers'] = [provider_entry]
        planner_section.setdefault('enabled', planner_section.get('enabled', False))
        planner_section.setdefault('execution_timeout', planner_section.get('execution_timeout', 120.0))
        merge_section = config_data.setdefault('merge', {})
        if 'providers' not in merge_section:
            merge_section['providers'] = []
        merge_section.setdefault('enabled', merge_section.get('enabled', False))
        return config_data

    # Fallback: treat it as the simple chatbot configuration
    base_url = raw_config.get('model_server_base_url') or raw_config.get('base_url')
    workspace_slug = raw_config.get('workspace_slug') or raw_config.get('workspace')
    stream_enabled = raw_config.get('stream')

    config_data = {
        'npu_provider': {
            'base_url': base_url or 'http://localhost:3001/api/v1',
            'workspace_slug': workspace_slug or 'default',
        },
        'cpu_fallback': raw_config.get('cpu_fallback') or {
            'model_path': 'Phi-3-mini-4k-instruct.Q4_K_M.gguf',
            'n_ctx': 4096,
            'n_gpu_layers': 0,
        },
        'system': {
            'streaming_enabled': True if stream_enabled is None else bool(stream_enabled),
            'stream_timeout': raw_config.get('stream_timeout'),
        },
        'agent_config': {
            'default_agent': raw_config.get('default_agent', 'code_helfer'),
        },
    }

    if 'planner' in raw_config:
        planner_section = raw_config.get('planner') or {}
        if not isinstance(planner_section, dict):
            raise ValueError("planner-Sektion muss ein Objekt sein")
        planner_section.setdefault(
            'enabled', bool(raw_config.get('planner_enabled', False))
        )
        planner_section.setdefault(
            'execution_timeout', raw_config.get('planner_execution_timeout', 120.0)
        )
        if 'providers' not in planner_section:
            planner_section['providers'] = [
                {
                    'name': 'planner-local',
                    'type': 'local_ollama',
                    'base_url': raw_config.get('planner_base_url', 'http://localhost:11434'),
                    'model': raw_config.get('planner_model', 'gemma3:1b'),
                    'timeout': raw_config.get('planner_timeout', 180.0),
                    'max_tokens': raw_config.get('planner_max_tokens', 768),
                }
            ]
        config_data['planner'] = planner_section
        merge_section = raw_config.get('merge') or {}
        if not isinstance(merge_section, dict):
            raise ValueError("merge-Sektion muss ein Objekt sein")
        merge_section.setdefault('enabled', bool(merge_section.get('enabled', False)))
        if 'providers' not in merge_section:
            merge_section['providers'] = []
        config_data['merge'] = merge_section
    else:
        config_data['planner'] = {
            'enabled': bool(raw_config.get('planner_enabled', False)),
            'execution_timeout': raw_config.get('planner_execution_timeout', 120.0),
            'providers': [
                {
                    'name': 'planner-local',
                    'type': 'local_ollama',
                    'base_url': raw_config.get('planner_base_url', 'http://localhost:11434'),
                    'model': raw_config.get('planner_model', 'gemma3:1b'),
                    'timeout': raw_config.get('planner_timeout', 180.0),
                    'max_tokens': raw_config.get('planner_max_tokens', 768),
                }
            ],
        }
        merge_section = raw_config.get('merge') or {}
        if not isinstance(merge_section, dict):
            merge_section = {}
        merge_section.setdefault('enabled', bool(merge_section.get('enabled', False)))
        merge_section.setdefault('providers', merge_section.get('providers', []))
        config_data['merge'] = merge_section

    # Preserve optional API key if present for fallback lookup later
    api_key = raw_config.get('api_key')
    if api_key:
        config_data['npu_provider']['api_key'] = api_key

    return config_data


def load_configuration(config_path: str = 'config.yaml') -> AppConfig:
    """
    Loads configuration from a YAML file and environment variables,
    validates them, and returns a structured AppConfig object.
    """
    # Load .env file for secrets
    load_dotenv()

    # --- Load YAML configuration file ---
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"'{config_path}' not found. "
            f"Please copy 'config.yaml.template' to '{config_path}' and configure it."
        )
    with open(config_path, 'r') as f:
        try:
            loaded_yaml = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing '{config_path}': {e}")

    config_data = _normalize_config(loaded_yaml or {})

    # --- Load secrets and validate ---
    env_api_key = os.getenv('API_KEY')
    file_api_key = None
    npu_section = config_data.get('npu_provider', {})
    if isinstance(npu_section, dict):
        file_api_key = npu_section.get('api_key')
    api_key = env_api_key or file_api_key

    if not api_key or api_key == "your-anythingllm-api-key":
        raise ValueError(
            "API_KEY is not set. "
            "Please set it in your .env file (copy from .env.example)."
        )

    # --- Create structured config, providing defaults where necessary ---
    try:
        npu_section = config_data.get('npu_provider', {})
        missing_npu_keys = [key for key in ('base_url', 'workspace_slug') if key not in npu_section or not npu_section.get(key)]
        if missing_npu_keys:
            raise ValueError(
                "Missing required NPU configuration keys: " + ", ".join(missing_npu_keys)
            )
        npu_config = NPUConfig(
            api_key=api_key,
            base_url=npu_section['base_url'],
            workspace_slug=npu_section['workspace_slug']
        )

        cpu_section = config_data.get('cpu_fallback', {})
        model_name = cpu_section.get('model_path', 'Phi-3-mini-4k-instruct.Q4_K_M.gguf')
        full_model_path = os.path.join('models', model_name)

        cpu_config = CPUConfig(
            model_path=full_model_path,
            n_ctx=cpu_section.get('n_ctx', 4096),
            n_gpu_layers=cpu_section.get('n_gpu_layers', 0)
        )

        system_section = config_data.get('system', {})
        system_config = SystemConfig(
            streaming_enabled=system_section.get('streaming_enabled', True),
            stream_timeout=system_section.get('stream_timeout')
        )

        planner_raw = config_data.get('planner', {})

        def _to_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _to_int(value: Any, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        provider_entries: List[PlannerProviderConfig] = []
        raw_providers: Iterable[Dict[str, Any]] = planner_raw.get('providers', [])
        for index, provider in enumerate(raw_providers, start=1):
            if not isinstance(provider, dict):
                raise ValueError("Planner provider-Eintrag muss ein Objekt sein")

            name = provider.get('name') or f"planner-{index}"
            provider_type = provider.get('type', 'local_ollama')
            base_url = provider.get('base_url')
            model = provider.get('model')
            if not base_url or not model:
                raise ValueError(
                    f"Planner provider '{name}' benötigt 'base_url' und 'model'"
                )

            timeout = _to_float(provider.get('timeout', planner_raw.get('timeout', 180.0)), 180.0)
            max_tokens = _to_int(provider.get('max_tokens', planner_raw.get('max_tokens', 768)), 768)

            headers_raw = provider.get('headers', {}) or {}
            if not isinstance(headers_raw, dict):
                raise ValueError(f"Planner provider '{name}' hat ungültige headers")

            resolved_headers: Dict[str, str] = {}
            for header_key, header_value in headers_raw.items():
                resolved_headers[header_key] = str(_resolve_env_template(header_value))

            api_key_env = provider.get('api_key_env')
            if api_key_env:
                api_value = os.getenv(api_key_env)
                if api_value:
                    header_name = provider.get('api_key_header', 'Authorization')
                    if header_name.lower() == 'authorization' and not api_value.startswith('Bearer '):
                        api_value = f"Bearer {api_value}"
                    resolved_headers.setdefault(header_name, api_value)

            provider_entries.append(
                PlannerProviderConfig(
                    name=name,
                    type=provider_type,
                    base_url=base_url,
                    model=model,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    headers=resolved_headers,
                )
            )

        planner_config = PlannerConfig(
            enabled=bool(planner_raw.get('enabled', False)),
            execution_timeout=_to_float(planner_raw.get('execution_timeout', 120.0), 120.0),
            providers=provider_entries,
        )

        merge_raw = config_data.get('merge', {}) or {}
        merge_provider_entries: List[MergeProviderConfig] = []
        raw_merge_providers: Iterable[Dict[str, Any]] = merge_raw.get('providers', []) or []
        for index, provider in enumerate(raw_merge_providers, start=1):
            if not isinstance(provider, dict):
                raise ValueError("Merge provider-Eintrag muss ein Objekt sein")

            name = provider.get('name') or f"merge-{index}"
            provider_type = provider.get('type', 'local_ollama')
            base_url = provider.get('base_url')
            model = provider.get('model')
            if not base_url or not model:
                raise ValueError(
                    f"Merge provider '{name}' benötigt 'base_url' und 'model'"
                )

            timeout = _to_float(provider.get('timeout', merge_raw.get('timeout', 180.0)), 180.0)
            max_tokens = _to_int(provider.get('max_tokens', merge_raw.get('max_tokens', 1536)), 1536)

            headers_raw = provider.get('headers', {}) or {}
            if not isinstance(headers_raw, dict):
                raise ValueError(f"Merge provider '{name}' hat ungültige headers")

            resolved_headers: Dict[str, str] = {}
            for header_key, header_value in headers_raw.items():
                resolved_headers[header_key] = str(_resolve_env_template(header_value))

            api_key_env = provider.get('api_key_env')
            if api_key_env:
                api_value = os.getenv(api_key_env)
                if api_value:
                    header_name = provider.get('api_key_header', 'Authorization')
                    if header_name.lower() == 'authorization' and not api_value.startswith('Bearer '):
                        api_value = f"Bearer {api_value}"
                    resolved_headers.setdefault(header_name, api_value)

            merge_provider_entries.append(
                MergeProviderConfig(
                    name=name,
                    type=provider_type,
                    base_url=base_url,
                    model=model,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    headers=resolved_headers,
                )
            )

        merge_config = MergeConfig(
            enabled=bool(merge_raw.get('enabled', False)),
            providers=merge_provider_entries,
        )

        agent_section = config_data.get('agent_config', {})
        agent_config = AgentConfig(
            default_agent=agent_section.get('default_agent', 'default')
        )

        return AppConfig(npu_config, cpu_config, system_config, agent_config, planner_config, merge_config)

    except KeyError as e:
        raise ValueError(f"Missing required key in '{config_path}': {e}")

# --- Example Usage ---
if __name__ == '__main__':
    print("Attempting to load configuration...")
    try:
        config = load_configuration()
        print("✔️ Configuration loaded successfully!")
        print("\n--- NPU Config ---")
        print(f"Base URL: {config.npu_provider.base_url}")
        print(f"Workspace: {config.npu_provider.workspace_slug}")
        print(f"API Key Loaded: {'Yes' if config.npu_provider.api_key else 'No'}")
        print("\n--- CPU Fallback Config ---")
        print(f"Model Path: {config.cpu_fallback.model_path}")
        print(f"Context Size: {config.cpu_fallback.n_ctx}")
        print("\n--- Planner Config ---")
        print(f"Enabled: {config.planner.enabled}")
        print(f"Execution Timeout: {config.planner.execution_timeout}")
        print(f"Providers: {len(config.planner.providers)} registriert")
        for provider in config.planner.providers:
            print(
                f"  - {provider.name} ({provider.type}) => {provider.base_url} / {provider.model}"
            )
        print("\n--- Merge Config ---")
        print(f"Enabled: {config.merge.enabled}")
        print(f"Providers: {len(config.merge.providers)} registriert")
        for provider in config.merge.providers:
            print(
                f"  - {provider.name} ({provider.type}) => {provider.base_url} / {provider.model}"
            )

    except (FileNotFoundError, ValueError) as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
