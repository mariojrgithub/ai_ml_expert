from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    mongo_uri: str = 'mongodb://localhost:27017'
    mongo_db: str = 'engineering_copilot'
    ollama_base_url: str = 'http://localhost:11434'
    general_model: str = 'llama3.1:8b'
    code_model: str = 'qwen2.5-coder:7b'
    embedding_model: str = 'nomic-embed-text'
    web_search_enabled: bool = False
    mcp_transport: str = 'stdio'
    mcp_server_command: str = ''
    mcp_server_args: str = ''
    mcp_web_search_tool: str = 'web_search'
    agent_port: int = 8000

settings = Settings()