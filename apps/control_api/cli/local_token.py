"""Local single-user sign-in: keep one owner account and one token for this machine.

`make dev` runs this so a solo developer never has to create actors or paste tokens.
The token is stored in ``var/olympus/local-token`` (git-ignored, mode 600) and reused
while it stays valid; a new one is issued only when it is missing, revoked or unknown.
Refuses to run unless ``OLYMPUS_ENV=local``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from core.config.settings import get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

OWNER_NAME = "you"
OWNER_ROLES = [ActorRole.OPERATOR.value, ActorRole.APPROVER.value]


async def _owner(session: AsyncSession) -> Actor:
    actor = (
        await session.execute(select(Actor).where(Actor.name == OWNER_NAME))
    ).scalar_one_or_none()
    if actor is None:
        actor = Actor(kind=ActorKind.HUMAN, name=OWNER_NAME, roles=OWNER_ROLES, active=True)
        session.add(actor)
        await session.flush()
    else:
        actor.kind = ActorKind.HUMAN
        actor.active = True
        actor.roles = sorted(set(actor.roles) | set(OWNER_ROLES))
    return actor


async def _token_valid(session: AsyncSession, actor: Actor, token: str) -> bool:
    row = (
        await session.execute(select(ApiToken).where(ApiToken.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    return (
        row is not None
        and row.actor_id == actor.id
        and row.revoked_at is None
        and row.expires_at is None
    )


async def ensure_local_token(token_file: Path) -> str:
    settings = get_settings()
    create_async_engine_from_settings(settings)
    factory = create_session_factory()
    try:
        async with factory() as session, session.begin():
            actor = await _owner(session)
            saved = token_file.read_text().strip() if token_file.exists() else ""
            if saved and await _token_valid(session, actor, saved):
                return saved
            token = generate_token()
            session.add(ApiToken(actor_id=actor.id, token_hash=hash_token(token)))
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token + "\n")
        os.chmod(token_file, 0o600)
        return token
    finally:
        await dispose_engine()
        reset_session_factory()


def main() -> None:
    parser = argparse.ArgumentParser(description="Print this machine's local sign-in token")
    parser.add_argument("--file", default="var/olympus/local-token")
    args = parser.parse_args()
    if get_settings().olympus_env != "local":
        print("local_token only runs with OLYMPUS_ENV=local", file=sys.stderr)
        raise SystemExit(2)
    print(asyncio.run(ensure_local_token(Path(args.file))))


if __name__ == "__main__":
    main()
