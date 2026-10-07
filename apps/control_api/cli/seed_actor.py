from __future__ import annotations

import argparse
import asyncio

from core.config.settings import get_settings
from core.db.engine import create_async_engine_from_settings, dispose_engine
from core.db.session import create_session_factory, reset_session_factory
from core.domain.actors.models import Actor, ApiToken
from core.domain.actors.tokens import generate_token, hash_token
from core.domain.enums import ActorKind, ActorRole


async def _seed(kind: str, name: str, roles: list[str]) -> None:
    settings = get_settings()
    create_async_engine_from_settings(settings)
    factory = create_session_factory()
    token = generate_token()
    async with factory() as session, session.begin():
        actor = Actor(
            kind=ActorKind(kind),
            name=name,
            roles=roles,
            active=True,
        )
        session.add(actor)
        await session.flush()
        session.add(ApiToken(actor_id=actor.id, token_hash=hash_token(token)))
    print(token)
    await dispose_engine()
    reset_session_factory()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed an API actor and print a bearer token")
    parser.add_argument("--kind", default="HUMAN")
    parser.add_argument("--name", required=True)
    parser.add_argument("--roles", default="OPERATOR,APPROVER")
    args = parser.parse_args()
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    for role in roles:
        ActorRole(role)
    asyncio.run(_seed(args.kind, args.name, roles))


if __name__ == "__main__":
    main()
