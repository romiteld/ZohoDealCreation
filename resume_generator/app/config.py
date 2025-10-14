import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Azure OpenAI (from existing deployment)
    AZURE_OPENAI_ENDPOINT = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://eastus2.api.cognitive.microsoft.com/"
    )
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    AZURE_OPENAI_API_VERSION = os.getenv(
        "AZURE_OPENAI_API_VERSION",
        "2024-08-01-preview"
    )

    # Zoho CRM (reuse existing OAuth proxy)
    ZOHO_OAUTH_SERVICE_URL = os.getenv(
        "ZOHO_OAUTH_SERVICE_URL",
        "https://well-zoho-oauth-v2.azurewebsites.net"
    )
    ZOHO_DEFAULT_OWNER_EMAIL = os.getenv(
        "ZOHO_DEFAULT_OWNER_EMAIL",
        "daniel.romitelli@emailthewell.com"
    )

    # API Configuration
    API_KEY = os.getenv("API_KEY")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8002))

    # Optional: Redis caching
    AZURE_REDIS_CONNECTION_STRING = os.getenv("AZURE_REDIS_CONNECTION_STRING")

settings = Settings()
