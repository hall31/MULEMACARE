"""HealthOS partner bridge client — async HTTP with HMAC-SHA256 signature.

Implements:
- Signature: timestamp + nonce + method + path + sha256(body)
- Nonce anti-replay: 5-minute Redis cache
- Retry logic: exponential backoff (3 attempts)
- Graceful fallback: if HealthOS down, return error with fallback hint
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class HealthOSClientError(Exception):
    """HealthOS client error."""

    pass


class HealthOSAuthError(HealthOSClientError):
    """Authentication or signature validation error."""

    pass


class HealthOSTimeoutError(HealthOSClientError):
    """HealthOS request timeout."""

    pass


class HealthOSNonceReplayError(HealthOSClientError):
    """Nonce has already been used (anti-replay protection)."""

    pass


class HealthOSClient:
    """Async HTTP client for HealthOS partner eligibility API."""

    NONCE_CACHE_TTL = 300  # 5 minutes
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF_BASE = 0.5  # seconds
    SIGNATURE_ALGO = "SHA256"
    REQUEST_TIMEOUT = 10.0  # Fallback timeout if not configured

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self.settings = get_settings()
        self.redis = redis_client
        self.timeout = self.settings.healthos_timeout_ms / 1000.0

    async def init_redis(self) -> None:
        """Initialize Redis connection for nonce cache."""
        if not self.redis:
            try:
                self.redis = await aioredis.from_url(
                    self.settings.redis_url,
                    encoding="utf8",
                    decode_responses=True,
                )
                logger.info("Redis connection established for HealthOS nonce cache")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure random nonce."""
        return secrets.token_hex(16)  # 32-char hex string

    async def _check_nonce_replay(self, nonce: str) -> None:
        """Check if nonce has been used before (anti-replay protection).

        Raises HealthOSNonceReplayError if nonce already seen.
        """
        if not self.redis:
            # Redis not available — log warning, but continue without replay protection
            logger.warning("Redis not available for nonce replay check; proceeding without protection")
            return

        cache_key = f"healthos:nonce:{nonce}"
        exists = await self.redis.get(cache_key)
        if exists:
            raise HealthOSNonceReplayError(f"Nonce {nonce} has already been used")

        # Mark nonce as used
        await self.redis.setex(cache_key, self.NONCE_CACHE_TTL, "1")

    def _compute_signature(
        self,
        timestamp: int,
        nonce: str,
        method: str,
        path: str,
        body_sha256: str,
    ) -> str:
        """Compute HMAC-SHA256 signature.

        Signature formula: timestamp + nonce + method + path + body_sha256
        Signed with HEALTHOS_PARTNER_API_KEY
        """
        message = f"{timestamp}|{nonce}|{method}|{path}|{body_sha256}"
        signature = hmac.new(
            self.settings.healthos_partner_api_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    async def _retry_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Execute HTTP request with exponential backoff retry."""
        last_error = None
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, **kwargs)
                    return response
            except httpx.TimeoutException as e:
                last_error = HealthOSTimeoutError(f"HealthOS request timeout: {e}")
                if attempt < self.RETRY_ATTEMPTS - 1:
                    backoff = self.RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        f"HealthOS {method} {url} timeout (attempt {attempt + 1}/"
                        f"{self.RETRY_ATTEMPTS}), retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
            except httpx.RequestError as e:
                last_error = HealthOSClientError(f"HealthOS request failed: {e}")
                if attempt < self.RETRY_ATTEMPTS - 1:
                    backoff = self.RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        f"HealthOS {method} {url} error (attempt {attempt + 1}/"
                        f"{self.RETRY_ATTEMPTS}), retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)

        raise last_error or HealthOSClientError("HealthOS request failed")

    async def get_eligibility(
        self,
        healthos_patient_id: str,
    ) -> dict[str, Any]:
        """Fetch member eligibility from HealthOS.

        GET /api/v1/partner/eligibility?patient_id=...

        Returns:
            dict with keys:
            - patient_id: HealthOS patient ID
            - eligible: bool
            - coverage_start: ISO date or None
            - coverage_end: ISO date or None
            - plan_name: str or None
            - error: str (fallback hint if HealthOS down)
        """
        if not self.settings.mulemacare_healthos_bridge_enabled:
            raise HealthOSClientError("HealthOS bridge is disabled")

        if not self.settings.healthos_base_url or not self.settings.healthos_partner_api_key:
            raise HealthOSClientError(
                "HealthOS configuration incomplete (base_url or api_key missing)"
            )

        timestamp = int(time.time())
        nonce = self._generate_nonce()

        # Check nonce replay
        await self._check_nonce_replay(nonce)

        method = "GET"
        path = f"/api/v1/partner/eligibility"
        body_sha256 = hashlib.sha256(b"").hexdigest()  # Empty GET body
        signature = self._compute_signature(timestamp, nonce, method, path, body_sha256)

        headers = {
            "X-Timestamp": str(timestamp),
            "X-Nonce": nonce,
            "X-Signature": signature,
            "X-Signature-Algo": self.SIGNATURE_ALGO,
            "Content-Type": "application/json",
        }

        url = f"{self.settings.healthos_base_url}{path}?patient_id={healthos_patient_id}"

        try:
            response = await self._retry_request(
                method,
                url,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"HealthOS eligibility fetch successful for patient {healthos_patient_id}")
                return {
                    "patient_id": healthos_patient_id,
                    "eligible": data.get("eligible", False),
                    "coverage_start": data.get("coverage_start"),
                    "coverage_end": data.get("coverage_end"),
                    "plan_name": data.get("plan_name"),
                }
            elif response.status_code == 404:
                logger.warning(f"HealthOS patient {healthos_patient_id} not found")
                return {
                    "patient_id": healthos_patient_id,
                    "eligible": False,
                    "coverage_start": None,
                    "coverage_end": None,
                    "plan_name": None,
                    "error": "Patient not found in HealthOS",
                }
            else:
                logger.error(
                    f"HealthOS eligibility error: {response.status_code} {response.text}"
                )
                return {
                    "patient_id": healthos_patient_id,
                    "eligible": None,
                    "error": f"HealthOS returned {response.status_code}",
                }

        except HealthOSTimeoutError as e:
            logger.error(f"HealthOS timeout: {e}")
            return {
                "patient_id": healthos_patient_id,
                "eligible": None,
                "error": "HealthOS service timeout — fallback to manual review",
            }
        except Exception as e:
            logger.error(f"HealthOS client error: {e}")
            return {
                "patient_id": healthos_patient_id,
                "eligible": None,
                "error": f"HealthOS service unavailable: {str(e)}",
            }

    async def create_preauth_intent(
        self,
        cssa_id: str,
        healthos_patient_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Create a pre-authorization intent on HealthOS.

        POST /api/v1/partner/preauth-intent
        Body: {cssa_id, patient_id, reason}

        Always returns PENDING_REVIEW — never auto-approve. Decision
        is made by ActionCenter HITL.

        Returns:
            dict with keys:
            - ok: bool
            - proposal_id: str or None (HealthOS proposal ID)
            - status: str (PENDING_REVIEW)
            - error: str (fallback hint if HealthOS down)
        """
        if not self.settings.mulemacare_healthos_bridge_enabled:
            raise HealthOSClientError("HealthOS bridge is disabled")

        if not self.settings.healthos_base_url or not self.settings.healthos_partner_api_key:
            raise HealthOSClientError(
                "HealthOS configuration incomplete (base_url or api_key missing)"
            )

        timestamp = int(time.time())
        nonce = self._generate_nonce()

        # Check nonce replay
        await self._check_nonce_replay(nonce)

        method = "POST"
        path = f"/api/v1/partner/preauth-intent"
        body = {
            "cssa_id": cssa_id.upper(),
            "patient_id": healthos_patient_id,
            "reason": reason,
        }
        body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        signature = self._compute_signature(timestamp, nonce, method, path, body_sha256)

        headers = {
            "X-Timestamp": str(timestamp),
            "X-Nonce": nonce,
            "X-Signature": signature,
            "X-Signature-Algo": self.SIGNATURE_ALGO,
            "Content-Type": "application/json",
        }

        url = f"{self.settings.healthos_base_url}{path}"

        try:
            response = await self._retry_request(
                method,
                url,
                headers=headers,
                content=body_bytes,
            )

            if response.status_code == 201:
                data = response.json()
                logger.info(
                    f"HealthOS preauth intent created for CSSA {cssa_id}, "
                    f"proposal_id={data.get('proposal_id')}"
                )
                return {
                    "ok": True,
                    "proposal_id": data.get("proposal_id"),
                    "status": "PENDING_REVIEW",
                }
            else:
                logger.error(
                    f"HealthOS preauth error: {response.status_code} {response.text}"
                )
                return {
                    "ok": False,
                    "proposal_id": None,
                    "status": "PENDING_REVIEW",
                    "error": f"HealthOS returned {response.status_code}",
                }

        except HealthOSTimeoutError as e:
            logger.error(f"HealthOS timeout: {e}")
            return {
                "ok": False,
                "proposal_id": None,
                "status": "PENDING_REVIEW",
                "error": "HealthOS service timeout — fallback to manual creation",
            }
        except Exception as e:
            logger.error(f"HealthOS client error: {e}")
            return {
                "ok": False,
                "proposal_id": None,
                "status": "PENDING_REVIEW",
                "error": f"HealthOS service unavailable: {str(e)}",
            }


# Global client instance
_client: HealthOSClient | None = None


async def get_healthos_client() -> HealthOSClient:
    """Dependency: get or create HealthOS client with Redis."""
    global _client
    if _client is None:
        _client = HealthOSClient()
        await _client.init_redis()
    return _client


async def close_healthos_client() -> None:
    """Clean up HealthOS client on shutdown."""
    global _client
    if _client:
        await _client.close()
        _client = None
