from sqlalchemy import select
from sqlalchemy.orm import Session


def next_source_id(db: Session, model, prefix: str, width: int) -> str:
    identifiers = db.scalars(select(model.id)).all()
    highest = 0
    for identifier in identifiers:
        if identifier.startswith(prefix) and identifier[len(prefix) :].isdigit():
            highest = max(highest, int(identifier[len(prefix) :]))
    return f"{prefix}{highest + 1:0{width}d}"
