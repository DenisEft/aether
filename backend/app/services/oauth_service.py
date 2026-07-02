"""OAuth service: authorization URLs, token exchange, user info for Google/Yandex/VK."""

from __future__ import annotations

import logging
import secrets

import httpx

logger = logging.getLogger("aether.oauth")

# Provider OAuth 2.0 endpoints
PROVIDER_CONFIG = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
    "yandex": {
        "authorize_url": "https://oauth.yandex.ru/authorize",
        "token_url": "https://oauth.yandex.ru/token",
        "userinfo_url": "https://login.yandex.ru/info",
        "scope": "login:email login:info",
    },
    "vk": {
        "authorize_url": "https://id.vk.com/authorize",
        "token_url": "https://id.vk.com/oauth/token",
        "userinfo_url": "https://id.vk.com/oauth/user_info",
        "scope": "email vkid.personal_info",
    },
}


class OAuthService:
    """OAuth 2.0 service for social login providers."""

    def __init__(self, client_id: str = "", client_secret: str = "", frontend_url: str = ""):
        self._client_id = client_id
        self._client_secret = client_secret
        self._frontend_url = frontend_url
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._http.aclose()

    def _get_client_id(self, provider: str) -> str:
        """Get client_id for provider from attributes or env vars."""
        attr_name = f"_client_id_{provider}"
        if hasattr(self, attr_name):
            return getattr(self, attr_name)
        return self._client_id

    def _get_client_secret(self, provider: str) -> str:
        """Get client_secret for provider from attributes or env vars."""
        attr_name = f"_client_secret_{provider}"
        if hasattr(self, attr_name):
            return getattr(self, attr_name)
        return self._client_secret

    async def get_authorization_url(
        self,
        provider: str,
        redirect_uri: str,
    ) -> str:
        """Generate the OAuth authorization URL with CSRF state."""
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        cfg = PROVIDER_CONFIG[provider]
        state = secrets.token_urlsafe(32)

        params = {
            "client_id": self._get_client_id(provider),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": cfg["scope"],
            "state": state,
        }

        # Build URL
        from urllib.parse import urlencode

        auth_url = f"{cfg['authorize_url']}?{urlencode(params)}"

        return auth_url

    async def exchange_code(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange authorization code for tokens. Returns user info dict."""
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        cfg = PROVIDER_CONFIG[provider]
        token_data = {
            "client_id": self._get_client_id(provider),
            "client_secret": self._get_client_secret(provider),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        # Exchange code for access token
        resp = await self._http.post(
            cfg["token_url"],
            data=token_data,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        token_result = resp.json()

        access_token = token_result.get("access_token")
        if not access_token:
            raise ValueError(f"No access_token in response from {provider}")

        # Fetch user info
        user_info = await self._fetch_user_info(provider, access_token)

        return {
            "provider": provider,
            "email": user_info.get("email"),
            "name": user_info.get("name", ""),
            "avatar_url": user_info.get("picture") or user_info.get("avatar_url", ""),
            "provider_user_id": user_info.get("sub")
            or user_info.get("id")
            or user_info.get("user_id", ""),
            "raw": user_info,
        }

    async def _fetch_user_info(self, provider: str, access_token: str) -> dict:
        """Fetch user info from the provider's userinfo endpoint."""
        cfg = PROVIDER_CONFIG[provider]
        headers = {"Authorization": f"Bearer {access_token}"}

        # VK has a different userinfo API
        if provider == "vk":
            resp = await self._http.post(
                cfg["userinfo_url"],
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                data={"client_id": self._get_client_id(provider), "access_token": access_token},
            )
        else:
            resp = await self._http.get(cfg["userinfo_url"], headers=headers)

        resp.raise_for_status()
        return resp.json()


# Global instance (created at app startup with settings)
oauth_service: OAuthService | None = None


def get_oauth_service() -> OAuthService:
    """Get or create the global OAuth service instance."""
    global oauth_service
    if oauth_service is None:
        from app.config import settings

        oauth_service = OAuthService(
            frontend_url=settings.FRONTEND_URL,
        )
    return oauth_service
