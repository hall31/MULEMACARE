"""Identification en trois facteurs au comptoir (R1) : QR, photo, code SMS.

Blocage (règle ID-03 en données, version en vigueur au jour local) : les codes faux se cumulent
sur la CARTE (``cards.failed_code_count``) ; au seuil, la carte est bloquée
(``cards.blocked_until``) et l'identification passe à ``bloquee``. Un code juste remet le
compteur à zéro.

Un code faux répond 422/423 mais son effet DOIT être validé : ``verify_code`` RENVOIE donc
l'erreur au lieu de la lever, et la route la rend sans annuler la transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.engine import RowMapping

from api.claims import rulebook
from api.claims.common import (
    clinic_provider,
    code_matches,
    ensure_in_scope,
    hash_code,
    local_date,
    new_code,
    seconds_until,
)
from api.claims.errors import (
    ClaimsError,
    card_blocked,
    code_expired,
    identification_incomplete,
    not_found,
    transition_forbidden,
    unknown_card,
    wrong_code,
)
from api.claims.ports import ClaimsRuntime
from api.claims.repository import ClaimsRepository
from api.claims.schemas import (
    Beneficiary,
    CodeSent,
    Identification,
    StartIdentificationRequest,
)
from api.core.context import RequestContext


class IdentificationService:
    def __init__(self, ctx: RequestContext, runtime: ClaimsRuntime) -> None:
        self._ctx = ctx
        self._rt = runtime
        self._repo = ClaimsRepository(ctx.session, ctx.principal.organization_id)

    async def _now_and_today(self) -> tuple[datetime, str]:
        return self._rt.clock.now(), await self._repo.timezone()

    async def _blocked(self, card: RowMapping, now: datetime, timezone: str) -> ClaimsError | None:
        until = card["blocked_until"]
        if until is None or until <= now:
            return None
        policy = await rulebook.code_policy(
            self._ctx.session, self._repo.org, local_date(now, timezone)
        )
        return card_blocked(
            seconds_until(until, now), policy.max_failures, int(policy.block.total_seconds() // 60)
        )

    async def _view(self, row: RowMapping, now: datetime, timezone: str) -> Identification:
        person = await self._repo.beneficiary(
            row["person_id"], row["member_id"], local_date(now, timezone)
        )
        if person is None:
            raise not_found()
        return Identification(
            id=row["id"],
            status=row["status"],
            qr_verified=row["qr_verified"],
            photo_confirmed=row["photo_confirmed"],
            code_verified=row["verified_at"] is not None,
            # Photo : aucun stockage d'objets dans le pays n'est encore branché (Q-L5-06).
            beneficiary=Beneficiary(photo_url=None, **dict(person)),
        )

    async def _load(self, identification_id: UUID, *, for_update: bool = False) -> RowMapping:
        row = await self._repo.identification(identification_id, for_update=for_update)
        if row is None:
            raise not_found()
        ensure_in_scope(self._ctx, row["provider_id"])
        return row

    async def start(self, body: StartIdentificationRequest) -> Identification:
        provider = clinic_provider(self._ctx)
        now, timezone = await self._now_and_today()
        if body.qr_payload is not None:
            card_id = await self._rt.qr_verifier.resolve(
                body.qr_payload,
                at=now,
                session=self._ctx.session,
                organization_id=self._repo.org,
            )
            card = await self._repo.card(card_id) if card_id is not None else None
        else:
            card = await self._repo.holder_card(body.member_number or "")
        if card is None or card["status"] != "active":
            raise unknown_card()
        blocked = await self._blocked(card, now, timezone)
        if blocked is not None:
            raise blocked
        identification_id = await self._repo.insert_identification(
            card_id=card["id"],
            provider_id=provider,
            operator=self._ctx.principal.user_id,
            qr_verified=body.qr_payload is not None,
            started_at=now,
        )
        return await self._view(await self._load(identification_id), now, timezone)

    async def confirm_photo(self, identification_id: UUID, *, confirmed: bool) -> Identification:
        row = await self._load(identification_id, for_update=True)
        now, timezone = await self._now_and_today()
        if row["status"] != "ouverte" or row["photo_confirmed"] is not None:
            raise transition_forbidden("La photo de cette identification a déjà été traitée.")
        await self._repo.update_identification(
            identification_id,
            photo_confirmed=confirmed,
            status="ouverte" if confirmed else "identite_refusee",
        )
        return await self._view(await self._load(identification_id), now, timezone)

    async def send_code(self, identification_id: UUID) -> CodeSent:
        row = await self._load(identification_id, for_update=True)
        now, timezone = await self._now_and_today()
        card = await self._repo.card(row["card_id"])
        if card is None:
            raise unknown_card()
        blocked = await self._blocked(card, now, timezone)
        if blocked is not None:
            raise blocked
        if row["status"] != "ouverte" or row["verified_at"] is not None:
            raise transition_forbidden("Cette identification n'attend plus de code.")
        if row["photo_confirmed"] is not True:
            raise identification_incomplete("La photo doit être confirmée avant le code SMS.")
        holder = await self._repo.holder_phone(row["member_id"])
        if holder is None or holder["phone_e164"] is None:
            raise identification_incomplete("Aucun téléphone n'est enregistré pour l'adhérent.")
        code = new_code()
        expires_at = now + self._rt.sms_code_validity
        await self._repo.update_identification(
            identification_id,
            code_hash=hash_code(code),
            code_sent_at=now,
            code_expires_at=expires_at,
        )
        await self._repo.insert_sms(
            person_id=holder["person_id"], related_id=row["id"], sent_at=now
        )
        await self._rt.sms_sender.send_code(phone_e164=str(holder["phone_e164"]), code=code)
        return CodeSent(sent_at=now, expires_at=expires_at)

    async def verify_code(self, identification_id: UUID, code: str) -> Identification | ClaimsError:
        row = await self._load(identification_id, for_update=True)
        now, timezone = await self._now_and_today()
        card = await self._repo.card(row["card_id"], for_update=True)
        if card is None:
            raise unknown_card()
        blocked = await self._blocked(card, now, timezone)
        if blocked is not None:
            return blocked
        if row["status"] != "ouverte" or row["code_hash"] is None:
            raise identification_incomplete(
                "Aucun code n'est en attente pour cette identification.", status_code=422
            )
        if row["code_expires_at"] is None or row["code_expires_at"] <= now:
            raise code_expired()

        if code_matches(code, row["code_hash"]):
            await self._repo.update_card(card["id"], failed=0, blocked_until=None)
            verified = bool(row["qr_verified"]) and row["photo_confirmed"] is True
            await self._repo.update_identification(
                identification_id,
                code_hash=None,
                verified_at=now,
                status="verifiee" if verified else "ouverte",
            )
            return await self._view(await self._load(identification_id), now, timezone)

        policy = await rulebook.code_policy(
            self._ctx.session, self._repo.org, local_date(now, timezone)
        )
        failures = int(card["failed_code_count"]) + 1
        attempts = int(row["code_failed_attempts"]) + 1
        if failures >= policy.max_failures:
            until = now + policy.block
            await self._repo.update_card(card["id"], failed=0, blocked_until=until)
            await self._repo.update_identification(
                identification_id, code_failed_attempts=attempts, status="bloquee", code_hash=None
            )
            return card_blocked(
                seconds_until(until, now),
                policy.max_failures,
                int(policy.block.total_seconds() // 60),
            )
        await self._repo.update_card(
            card["id"], failed=failures, blocked_until=card["blocked_until"]
        )
        await self._repo.update_identification(identification_id, code_failed_attempts=attempts)
        return wrong_code(policy.max_failures - failures)
