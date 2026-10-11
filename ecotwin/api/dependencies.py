from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ecotwin.auth.jwt import verify_token
from ecotwin.config import get_settings
from ecotwin.db.models import UserAccount
from ecotwin.db.session import session_dependency
from ecotwin.errors import TwinError

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session=Depends(session_dependency),
):
    if not credentials:
        raise TwinError("UNAUTHORIZED", "Bearer access token required", 401)
    settings = get_settings()
    subject = verify_token(credentials.credentials, settings)
    session.execute(
        insert(UserAccount)
        .values(identity_issuer=settings.issuer, identity_subject=subject)
        .on_conflict_do_nothing(index_elements=["identity_issuer", "identity_subject"])
    )
    session.commit()
    return session.scalar(
        select(UserAccount).where(
            UserAccount.identity_issuer == settings.issuer, UserAccount.identity_subject == subject
        )
    )
