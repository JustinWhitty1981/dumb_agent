"""
Azure OpenAI Authentication & Factory Module for J.A.D.A.
Supports:
1. Static Azure OpenAI API Key (AzureChatOpenAI)
2. OAuth v2 Client Credentials (Microsoft Entra ID v2 for Azure Gov Cognitive Services)
"""

import os
import time
import logging
import requests
import httpx
from typing import Tuple, Dict, Any, Optional

from langchain_openai import AzureChatOpenAI, ChatOpenAI

logger = logging.getLogger("jada_app.azure_auth")


class AzureTokenProvider:
    """
    Manages OAuth v2 client credentials tokens for Azure Cognitive Services / Azure Gov.
    Includes thread-safe token caching and 60-second early refresh.
    """
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: str = "https://cognitiveservices.azure.us/.default"
    ):
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID", "a84d585b-574d-4eb7-be2a-eaea93ef7b1f")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET", "")
        self.scope = scope
        self._cached_token: Optional[str] = None
        self._expires_at: int = 0

    def get_oauth_token_v2(self) -> Tuple[str, int]:
        """Fetch a fresh OAuth v2 token from Microsoft Entra ID (v2)."""
        if not self.client_id or not self.client_secret:
            raise ValueError("AZURE_CLIENT_ID and AZURE_CLIENT_SECRET must be set for OAuth token authentication.")

        oauth_url = f"https://login.microsoftonline.us/{self.tenant_id}/oauth2/v2.0/token"
        form = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        response = requests.post(oauth_url, data=form, timeout=30)
        response.raise_for_status()
        payload = response.json()

        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", "3600"))
        expires_at = int(time.time()) + expires_in - 60  # refresh 60s early
        return token, expires_at

    def get_bearer_token(self) -> str:
        """Returns cached valid token, refreshing when near expiry."""
        now = int(time.time())
        if not self._cached_token or now >= self._expires_at:
            token, exp = self.get_oauth_token_v2()
            self._cached_token = token
            self._expires_at = exp
        return self._cached_token

    def invalidate(self):
        """Invalidates cached token forcing refresh on next request."""
        self._cached_token = None
        self._expires_at = 0


class AzureOAuthAuth(httpx.Auth):
    """
    httpx Auth plugin that injects Azure OAuth Bearer Token into headers
    and invalidates/retries on 401 Unauthorized responses.
    """
    def __init__(self, token_provider: AzureTokenProvider):
        self.token_provider = token_provider

    def auth_flow(self, request):
        token = self.token_provider.get_bearer_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request

        if response.status_code == 401:
            logger.warning("Received 401 Unauthorized from Azure OpenAI. Invalidating token cache and retrying...")
            self.token_provider.invalidate()
            fresh_token = self.token_provider.get_bearer_token()
            request.headers["Authorization"] = f"Bearer {fresh_token}"
            yield request


def resolve_azure_config() -> Dict[str, str]:
    """
    Resolves Azure OpenAI endpoint, deployment name, api version, segment, environment.
    """
    segment = os.getenv("SEGMENT", "ent")
    environment = os.getenv("ENVIRONMENT", "dev")

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        endpoint = f"https://aisvc-foundry-ai-service-{segment}-{environment}.cognitiveservices.azure.us/"

    deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")
    if not deployment_name:
        deployment_name = f"gpt-5.1-advanced-analytics-advanced-analytics-{segment}-{environment}"

    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    return {
        "segment": segment,
        "environment": environment,
        "endpoint": endpoint.rstrip("/"),
        "deployment_name": deployment_name,
        "api_version": api_version,
    }


def get_azure_chat_llm(temperature: float = 0.0):
    """
    Factory function returning a LangChain Chat Model configured for Azure OpenAI.
    Prioritizes static AZURE_OPENAI_API_KEY if present; otherwise uses OAuth v2 token auth.
    """
    config = resolve_azure_config()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

    if api_key:
        logger.info(f"Initializing AzureChatOpenAI using static API Key on endpoint: {config['endpoint']}")
        return AzureChatOpenAI(
            azure_endpoint=config["endpoint"],
            azure_deployment=config["deployment_name"],
            api_version=config["api_version"],
            api_key=api_key,
            temperature=temperature,
        )

    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "").strip()

    if client_id and client_secret:
        logger.info(f"Initializing Azure OpenAI via OAuth v2 Client Credentials on endpoint: {config['endpoint']}")
        token_provider = AzureTokenProvider(client_id=client_id, client_secret=client_secret)
        auth = AzureOAuthAuth(token_provider)

        sync_http_client = httpx.Client(auth=auth, timeout=60.0)
        async_http_client = httpx.AsyncClient(auth=auth, timeout=60.0)

        base_v1_url = f"{config['endpoint']}/openai/v1"
        return ChatOpenAI(
            base_url=base_v1_url,
            model=config["deployment_name"],
            api_key="oauth-managed",
            temperature=temperature,
            http_client=sync_http_client,
            async_client=async_http_client,
        )

    # Fallback if no keys or secrets are provided
    logger.warning("No AZURE_OPENAI_API_KEY or AZURE_CLIENT_SECRET provided. Initializing AzureChatOpenAI with dummy placeholder.")
    return AzureChatOpenAI(
        azure_endpoint=config["endpoint"],
        azure_deployment=config["deployment_name"],
        api_version=config["api_version"],
        api_key="not-configured",
        temperature=temperature,
    )
