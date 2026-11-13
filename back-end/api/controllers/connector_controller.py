"""What the Claude connector can do for a person (TKT-72): see the categories, preview rows read from a document, and add
the rows they confirmed.

Everything is done as the signed-in person, in their own family. The rows come from an AI reading a photo or a statement,
so they are untrusted input and are checked with the same rules as the spreadsheet import. Only `add_rows` writes, and it
only adds transactions: nothing here can change or delete anything.
"""

import hashlib
import hmac
import json
import re
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from api.controllers.auth_controller import JWT_SECRET
from api.controllers.imports_controller import _category_lookup
from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
from api.repositories.categories_repo import lock_family
from api.repositories.families_repo import get_family
from api.repositories.imports_repo import (
    add_transactions,
    count_recent_additions,
    existing_transaction_keys,
    lookalike_transactions,
)
from api.services.import_service import FIRST_YEAR, MAX_CENTS, MAX_LABEL
from api.utils.category_names import name_key
from api.utils.clock import family_today, utc_now
from schemas.tables import Users

MAX_ROWS = 200  # a chat can send a lot at once; longer statements are sent in pieces
MAX_PROBLEMS_SHOWN = 50
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConnectorError(Exception):
    """Something the AI can read and act on (fix the rows, preview again)."""


def list_categories(db: Session, user: Users) -> list[dict]:
    return [
        {"name": category.name, "group": group_name}
        for category, group_name, _position in get_all_categories_repo(db, user.family_id)
    ]


def _read_row(raw, today: date, lookup: dict[str, str]) -> tuple[dict | None, list[str]]:
    """(the row as it will be saved, what is wrong with it)."""
    if not isinstance(raw, dict):
        return None, ["each row must be an object"]
    problems: list[str] = []

    day = None
    text = raw.get("date")
    if not isinstance(text, str) or not _ISO_DATE.match(text):
        problems.append("date must be written YYYY-MM-DD")
    else:
        try:
            day = date.fromisoformat(text)
        except ValueError:
            problems.append("date is not a real day")
        else:
            if day.year < FIRST_YEAR:
                problems.append("date is too old")
            elif day > today:
                problems.append("date cannot be in the future")

    label = raw.get("description")
    label = label.strip() if isinstance(label, str) else ""
    if not label:
        problems.append("description is required")
    elif len(label) > MAX_LABEL:
        problems.append(f"description has {len(label)} characters and the maximum is {MAX_LABEL}")
    elif "\x00" in label:
        problems.append("description has an invalid character")

    cents = raw.get("amount_cents")
    if isinstance(cents, bool) or not isinstance(cents, int):
        problems.append("amount_cents must be a whole number of cents (R$ 12,50 is 1250)")
        cents = None
    elif cents <= 0:
        problems.append("amount_cents must be positive; type says which way the money went")
    elif cents > MAX_CENTS:
        problems.append("amount_cents is too large")

    kind = raw.get("type", "debit")
    if kind not in ("debit", "credit"):
        problems.append('type must be "debit" (money out) or "credit" (money in)')

    category = raw.get("category")
    category_id = None
    if not isinstance(category, str) or not name_key(category):
        problems.append("category is required (use a name from list_categories)")
    else:
        category_id = lookup.get(name_key(category))
        if category_id is None:
            problems.append(f'category "{category[:60]}" is not one of the family\'s categories (see list_categories)')

    if problems:
        return None, problems
    return {"date": day.isoformat(), "label": label, "value": cents, "type": kind, "category_id": category_id}, []


PREVIEW_MINUTES = 15  # a preview is for the person to look at and answer; an old one is made again
MAX_ROWS_PER_HOUR = 1000  # of one person, however many calls: a brake on a chat that runs away
_PREVIEW_KEY = hashlib.sha256(b"money-budget-preview-v1" + JWT_SECRET.encode()).digest()  # not the login key itself


def _preview_id(user_id: UUID, rows: list[dict], expires: int) -> str:
    """Proves the rows were previewed: it covers exactly what would be saved and who for, and cannot be made without
    the server's secret. So the rows that get added are the ones that were shown."""
    body = json.dumps([user_id.hex, rows, expires], sort_keys=True, separators=(",", ":"))
    return f"{expires}.{hmac.new(_PREVIEW_KEY, body.encode(), hashlib.sha256).hexdigest()}"


def _preview_is_valid(preview_id, user_id: UUID, rows: list[dict]) -> bool:
    if not isinstance(preview_id, str):
        return False
    stamp, _, _signature = preview_id.partition(".")
    if not stamp.isascii() or not stamp.isdigit() or int(stamp) < int(utc_now().timestamp()):
        return False
    expected = _preview_id(user_id, rows, int(stamp))
    return hmac.compare_digest(preview_id.encode("utf-8", "replace"), expected.encode())


def _check(db: Session, user: Users, rows) -> tuple[list[dict], list[dict], list[dict]]:
    """(the checked rows, the same rows as they are shown at the same positions, the problems). Raises ConnectorError if there is nothing to check."""
    if not isinstance(rows, list) or not rows:
        raise ConnectorError("rows must be a non-empty list")
    if len(rows) > MAX_ROWS:
        raise ConnectorError(f"at most {MAX_ROWS} rows at a time; send the rest in another call")
    today = family_today(get_family(db, user.family_id).timezone)
    lookup, _visible, _by_alias = _category_lookup(db, user.family_id)
    names = {
        str(category.id): category.name for category, _group, _position in get_all_categories_repo(db, user.family_id)
    }
    checked: list[dict] = []
    shown: list[dict] = []
    problems: list[dict] = []
    for position, raw in enumerate(rows, start=1):
        row, found = _read_row(raw, today, lookup)
        if row is None:
            problems.extend({"row": position, "problem": message} for message in found)
            continue
        checked.append(row)
        shown.append(
            {
                "row": position,
                "date": row["date"],
                "description": row["label"],
                "amount_cents": row["value"],
                "type": row["type"],
                "category": names[row["category_id"]],
            }
        )
    return checked, shown, problems


def _split_duplicates(db: Session, user: Users, checked: list[dict]) -> list[bool]:
    """For each row, whether the family already has it (same day, description, amount, category and type). Rows of the
    same call never count as duplicates of each other."""
    if not checked:
        return []
    days = [date.fromisoformat(row["date"]) for row in checked]
    saved = existing_transaction_keys(db, user.family_id, min(days), max(days))
    return [
        (date.fromisoformat(r["date"]), r["label"], r["value"], r["category_id"], r["type"]) in saved for r in checked
    ]


MAX_LOOKALIKES_SHOWN = 3


def _has_lookalike(row: dict) -> bool:
    return bool(row.get("similar_existing") or row.get("same_as_rows_in_this_call"))


def _flag_lookalikes(db: Session, user: Users, checked: list[dict], out_rows: list[dict]) -> None:
    """On each row that is `new`, say what looks like it: transactions the family already has, and earlier rows of this
    same call, on the same day with the same amount and type. They are only a warning, the person decides: two coffees
    for the same price on the same day are legitimate."""
    if not checked:
        return
    days = [date.fromisoformat(row["date"]) for row in checked]
    saved = lookalike_transactions(db, user.family_id, min(days), max(days))
    seen: dict[tuple, list[int]] = {}
    for row, out in zip(checked, out_rows):
        key = (date.fromisoformat(row["date"]), row["value"], row["type"])
        if out["status"] == "new":
            similar = saved.get(key, [])
            if similar:
                out["similar_existing"] = [
                    {"description": label, "category": category} for label, category in similar[:MAX_LOOKALIKES_SHOWN]
                ]
            if seen.get(key):
                out["same_as_rows_in_this_call"] = list(seen[key])
        seen.setdefault(key, []).append(out["row"])


def _problems_out(problems: list[dict]) -> dict:
    return {
        "problems": problems[:MAX_PROBLEMS_SHOWN],
        "problem_count": len(problems),
    }


def preview_rows(db: Session, user: Users, rows) -> dict:
    """Check the rows and say which ones the family already has. Saves nothing."""
    checked, shown, problems = _check(db, user, rows)
    if problems:
        return {
            "ok": False,
            "message": "Nothing can be added until these rows are fixed. Fix them and preview again.",
            **_problems_out(problems),
        }
    duplicate = _split_duplicates(db, user, checked)
    out_rows = []
    for row, is_duplicate in zip(shown, duplicate):
        out_rows.append({**row, "status": "already_exists" if is_duplicate else "new"})
    new = duplicate.count(False)
    _flag_lookalikes(db, user, checked, out_rows)
    return {
        "ok": True,
        "summary": {"new": new, "already_exist": len(duplicate) - new},
        "possible_duplicates": sum(1 for r in out_rows if r["status"] == "new" and _has_lookalike(r)),
        "rows": out_rows,
        "preview_id": _preview_id(user.id, checked, int(utc_now().timestamp()) + PREVIEW_MINUTES * 60),
        "next_step": "Show these rows to the person. Only after they confirm, call add_transactions with the same "
        "rows and this preview_id. Rows marked already_exists are skipped. Rows with similar_existing or "
        "same_as_rows_in_this_call look like duplicates (same day, amount and type but not the same description or "
        "category): show them to the person and ask whether to keep each one. Rows they do not want must be left "
        "out of the rows you send, and previewed again.",
    }


def add_rows(db: Session, user: Users, rows, preview_id) -> dict:
    """Add the rows that were previewed (and that the family does not have yet). All or nothing."""
    # The family is locked first so two calls with the same rows cannot both find them missing and both add them
    lock_family(db, user.family_id)
    checked, _shown, problems = _check(db, user, rows)
    if problems:
        db.rollback()
        return {"ok": False, "message": "Nothing was added: some rows are not valid.", **_problems_out(problems)}
    if not _preview_is_valid(preview_id, user.id, checked):
        db.rollback()
        return {
            "ok": False,
            "message": "Nothing was added: these rows were not previewed (or the preview is more than 15 minutes old). Call preview_transactions with exactly "
            "these rows, show the result to the person and ask for their confirmation first.",
        }
    duplicate = _split_duplicates(db, user, checked)
    new = [row for row, is_duplicate in zip(checked, duplicate) if not is_duplicate]
    if count_recent_additions(db, user.id) + len(new) > MAX_ROWS_PER_HOUR:
        db.rollback()
        return {
            "ok": False,
            "message": f"Nothing was added: at most {MAX_ROWS_PER_HOUR} transactions an hour can be added. Try later.",
        }
    # The transaction belongs to the person who is signed in (add_transactions gives it to them)
    add_transactions(db, user.family_id, user.id, new)
    db.commit()
    return {"ok": True, "added": len(new), "skipped_because_they_already_exist": len(checked) - len(new)}
