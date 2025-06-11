from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import User


async def check_username_or_email_exists(
    session: AsyncSession, username: str | None = None, email: str | None = None
) -> str | None:
    """
    Check if a username or email exists in the database.

    Args:
        username (str): The username to check.
        email (str): The email to check.
        session (AsyncSession): The database session.

    Returns:
        str | None: 'user already exists' if the username exists,
                    'email already exists' if the email exists,
                    None if neither exists.
    """
    user = await session.exec(
        select(User).where(or_(User.username == username, User.email == email))
    )
    result = user.first()

    if not result:
        return None
    elif result.username == username:
        return 'Username already exists.'
    else:
        return 'Email already exists.'
