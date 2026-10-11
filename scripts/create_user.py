"""Create or promote a VersionWise AI user from the command line.

Privileged roles (document_manager, admin) can ONLY be granted here —
the public /auth/register endpoint always creates role=user.

Usage (from backend/, venv active):
    python ../scripts/create_user.py --email you@example.com \
        --name "Your Name" --password 's3cret!' --role admin

Existing email -> role is updated instead of duplicated.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.models import User, UserRole  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--role", choices=[r.value for r in UserRole], default="user")
    args = p.parse_args()

    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as s:
        user = s.execute(select(User).where(User.email == args.email.lower())).scalar_one_or_none()
        if user is None:
            user = User(
                email=args.email.lower(),
                full_name=args.name,
                password_hash=hash_password(args.password),
                role=UserRole(args.role),
            )
            s.add(user)
            action = "created"
        else:
            user.role = UserRole(args.role)
            user.full_name = args.name
            user.password_hash = hash_password(args.password)
            action = "updated"
        s.commit()
        print(f"User {action}: {user.email} (role={user.role.value}, id={user.id})")


if __name__ == "__main__":
    main()
