"""Load a books CSV file into books.db, following rules.md.

Usage:
    python3 ingest.py books.csv

books.db and ingestion-log.json are created next to this script. Every run checks
every row, never creates duplicates, and appends one entry to ingestion-log.json.
No AI and no internet: the same file always gives the same result.

Rule numbers in comments (R1-R15, Q1-Q18) refer to rules.md.
"""
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "books.db"
LOG_PATH = HERE / "ingestion-log.json"

# Q1: all 23 columns are stored. Q2: how each one is stored.
COLUMNS = [
    "book_id", "goodreads_book_id", "best_book_id", "work_id", "books_count", "isbn", "isbn13",
    "authors", "original_publication_year", "original_title", "title", "language_code",
    "average_rating", "ratings_count", "work_ratings_count", "work_text_reviews_count",
    "ratings_1", "ratings_2", "ratings_3", "ratings_4", "ratings_5", "image_url", "small_image_url",
]
WHOLE_NUMBER_COLUMNS = [
    "book_id", "goodreads_book_id", "best_book_id", "work_id", "books_count",
    "original_publication_year", "ratings_count", "work_ratings_count", "work_text_reviews_count",
    "ratings_1", "ratings_2", "ratings_3", "ratings_4", "ratings_5",
]
DECIMAL_COLUMNS = ["average_rating"]
COUNT_COLUMNS = [  # Q3
    "books_count", "ratings_count", "work_ratings_count", "work_text_reviews_count",
    "ratings_1", "ratings_2", "ratings_3", "ratings_4", "ratings_5",
]
RATING_COLUMNS = ["ratings_1", "ratings_2", "ratings_3", "ratings_4", "ratings_5"]

# Q10: one fixed "what to do" sentence per rejection reason.
WHAT_TO_DO = {
    "isbn_check_digit": "Ask the supplier for the correct ISBN.",
    "isbn_short": "Ask the supplier for the correct ISBN.",
    "isbn_too_long": "Ask the supplier for the correct ISBN.",
    "isbn_bad_characters": "Ask the supplier for the correct ISBN.",
    "isbn_13_invalid": "Ask the supplier for the correct ISBN.",
    "isbn13_check_digit": "Ask the supplier for the correct ISBN-13.",
    "isbn13_bad_characters": "Ask the supplier for the correct ISBN-13.",
    "isbn_mismatch": "Ask the supplier which ISBN is right.",
    "isbn_conflict": "Check which book this ISBN really belongs to.",
    "book_id_conflict": "Check whether this book_id or this ISBN is wrong.",
    "no_isbn_no_book_id": "Ask the supplier for an ISBN or a book_id for this book.",
    "negative_count": "Ask the supplier for the correct counts.",
    "ratings_dont_add_up": "Ask the supplier for the correct rating counts.",
}


# ---------------------------------------------------------------------------
# ISBN arithmetic (R1)
# ---------------------------------------------------------------------------

def isbn10_is_valid(s):
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
    return total % 11 == 0


def isbn13_check_digit(first12):
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def isbn13_is_valid(s):
    return bool(re.fullmatch(r"97[89]\d{10}", s)) and isbn13_check_digit(s[:12]) == s[12]


def isbn10_to_isbn13(isbn10):
    core = "978" + isbn10[:9]
    return core + isbn13_check_digit(core)


def isbn13_to_isbn10(isbn13):
    """Only for 978 ISBN-13s; a 979 ISBN-13 has no ISBN-10 (R7)."""
    first9 = isbn13[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(first9))
    check = (11 - total % 11) % 11
    return first9 + ("X" if check == 10 else str(check))


SCIENTIFIC = re.compile(r"\d(\.\d+)?[eE][+-]?\d+")
DECIMAL_TEXT = re.compile(r"\d+\.\d+")


# ---------------------------------------------------------------------------
# Checking one row
# ---------------------------------------------------------------------------

def check_isbns(raw10, raw13, problems, warnings):
    """Apply R2-R9 and Q4, Q5, Q16, Q17. Returns (isbn10, isbn13); either may be None."""
    isbn10 = None
    isbn13_from_isbn_column = None
    isbn13_from_isbn13_column = None
    damaged13 = None

    # R2: formatting repairs on both columns
    c10 = re.sub(r"[\s-]", "", raw10)
    if c10 != raw10:
        warnings.append(f"isbn '{raw10}': removed spaces/hyphens")
    if c10.endswith("x"):
        c10 = c10[:-1] + "X"
        warnings.append(f"isbn '{raw10}': changed lowercase x to X")
    c13 = re.sub(r"[\s-]", "", raw13)
    if c13 != raw13:
        warnings.append(f"isbn13 '{raw13}': removed spaces/hyphens")

    # isbn column (R3, R4, R8)
    if c10 == "":
        pass
    elif re.fullmatch(r"\d{9}[\dX]", c10):
        if isbn10_is_valid(c10):
            isbn10 = c10
        else:
            problems.append(("isbn_check_digit", f"isbn '{raw10}': check digit is wrong"))
    elif re.fullmatch(r"\d{0,8}[\dX]", c10):
        padded = c10.zfill(10)
        if isbn10_is_valid(padded):
            isbn10 = padded
            warnings.append(f"isbn '{raw10}': restored leading zero(s) -> {padded}")
        else:
            problems.append(("isbn_short", f"isbn '{raw10}': too short, and not valid even after adding leading zeros ({padded})"))
    elif re.fullmatch(r"\d{13}", c10):
        if isbn13_is_valid(c10):
            isbn13_from_isbn_column = c10
            warnings.append(f"isbn '{raw10}': is an ISBN-13, used as the isbn13")
        else:
            problems.append(("isbn_13_invalid", f"isbn '{raw10}': 13 digits but not a valid ISBN-13"))
    elif re.fullmatch(r"\d+", c10):
        problems.append(("isbn_too_long", f"isbn '{raw10}': too many digits ({len(c10)})"))
    else:
        problems.append(("isbn_bad_characters", f"isbn '{raw10}': contains characters that are not allowed in an ISBN"))

    # isbn13 column (R5, R6, R8, Q17)
    if c13 == "":
        pass
    elif SCIENTIFIC.fullmatch(c13) and len(str(int(Decimal(c13)))) == 13:
        damaged13 = c13                                            # R5: never trusted
    elif SCIENTIFIC.fullmatch(c13):
        warnings.append(f"isbn13 '{raw13}': scientific notation, wrong length, not an ISBN; dropped")  # R6
    elif DECIMAL_TEXT.fullmatch(c13):
        warnings.append(f"isbn13 '{raw13}': written as a decimal, not an ISBN; dropped")   # R6
    elif re.search(r"[A-Za-z]", c13):
        problems.append(("isbn13_bad_characters", f"isbn13 '{raw13}': contains a letter"))  # Q17
    elif re.fullmatch(r"97[89]\d{10}", c13):
        if isbn13_is_valid(c13):
            isbn13_from_isbn13_column = c13
        else:
            problems.append(("isbn13_check_digit", f"isbn13 '{raw13}': check digit is wrong"))  # R8
    elif re.fullmatch(r"\d{13}", c13):
        warnings.append(f"isbn13 '{raw13}': no 978/979 prefix, not an ISBN; dropped")        # R6
    else:
        warnings.append(f"isbn13 '{raw13}': wrong length, not an ISBN; dropped")             # R6

    # Q5: an ISBN-13 in both columns
    isbn13 = isbn13_from_isbn13_column or isbn13_from_isbn_column
    if isbn13_from_isbn_column and isbn13_from_isbn13_column and isbn13_from_isbn_column != isbn13_from_isbn13_column:
        problems.append(("isbn_mismatch", f"isbn '{raw10}' and isbn13 '{raw13}' are two different ISBN-13s"))
        return None, None

    # R9: ISBN-10 and ISBN-13 must be the same book
    if isbn10 and isbn13 and isbn10_to_isbn13(isbn10) != isbn13:
        problems.append(("isbn_mismatch",
                         f"isbn '{raw10}' is ISBN-13 {isbn10_to_isbn13(isbn10)}, but isbn13 is '{raw13}': different books"))
        return None, None

    # R5 + Q4: rebuild a damaged ISBN-13 from the ISBN-10, or give up
    if damaged13 is not None:
        if isbn10:
            rebuilt = isbn10_to_isbn13(isbn10)
            note = f"isbn13 '{raw13}': scientific notation (damaged), rebuilt from isbn as {rebuilt}"
            stored_as = int(Decimal(damaged13))
            # What the supplier's software would have stored: 12 significant digits,
            # rounded to the nearest, with an exact 5 going to the even digit.
            kept, dropped = divmod(int(rebuilt), 10)
            if dropped > 5 or (dropped == 5 and kept % 2 == 1):
                kept += 1
            if stored_as != kept * 10:
                note += "; the damaged value did not match the isbn (it may be a different edition)"
            warnings.append(note)
            isbn13 = rebuilt
        elif not isbn13:
            warnings.append(f"isbn13 '{raw13}': damaged, not recoverable; stored as empty")

    # R7 + Q16: fill in what can be calculated
    if isbn10 and not isbn13:
        isbn13 = isbn10_to_isbn13(isbn10)
        if damaged13 is None:
            warnings.append(f"isbn13 calculated from isbn: {isbn13}")
    if isbn13 and not isbn10 and isbn13.startswith("978"):
        isbn10 = isbn13_to_isbn10(isbn13)
        warnings.append(f"isbn calculated from isbn13: {isbn10}")

    return isbn10, isbn13


def convert_number(column, raw, warnings):
    """Q2, Q13: whole numbers and decimals; anything else is stored empty with a warning."""
    text = raw.strip()
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        warnings.append(f"{column} '{raw}': not a number; stored as empty")
        return None
    if not value.is_finite():
        warnings.append(f"{column} '{raw}': not a number; stored as empty")
        return None
    if column in WHOLE_NUMBER_COLUMNS:
        if value != value.to_integral_value():
            warnings.append(f"{column} '{raw}': not a whole number; stored as empty")
            return None
        return int(value)
    return float(value)


def check_row(row):
    """Returns (record, problems, warnings). record holds the values as they would be stored."""
    problems, warnings = [], []
    raw = {c: (row.get(c) or "") for c in COLUMNS}          # Q12: missing column = empty

    record = {}
    for c in COLUMNS:
        if c in WHOLE_NUMBER_COLUMNS or c in DECIMAL_COLUMNS:
            record[c] = convert_number(c, raw[c], warnings)
        elif c not in ("isbn", "isbn13"):
            record[c] = raw[c] if raw[c] != "" else None
    record["isbn"], record["isbn13"] = check_isbns(raw["isbn"], raw["isbn13"], problems, warnings)

    # Q3: counts
    negative = [c for c in COUNT_COLUMNS if record[c] is not None and record[c] < 0]
    if negative:
        problems.append(("negative_count", "negative count in " + ", ".join(negative)))
    ratings = [record[c] for c in RATING_COLUMNS]
    if record["work_ratings_count"] is not None and all(r is not None for r in ratings):
        if sum(ratings) != record["work_ratings_count"]:
            problems.append(("ratings_dont_add_up",
                             f"ratings_1-5 add up to {sum(ratings)}, but work_ratings_count is {record['work_ratings_count']}"))

    # Q7
    if record["isbn13"] is None and record["book_id"] is None and not any(
            code.startswith("isbn") for code, _ in problems):
        problems.append(("no_isbn_no_book_id", "no ISBN and no book_id, so the book can't be identified"))

    return record, problems, warnings


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def open_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    types = {c: ("INTEGER" if c in WHOLE_NUMBER_COLUMNS else "REAL" if c in DECIMAL_COLUMNS else "TEXT")
             for c in COLUMNS}
    cols = ",\n    ".join(f"{c} {types[c]}" for c in COLUMNS)
    con.execute(f"CREATE TABLE IF NOT EXISTS books (\n    id INTEGER PRIMARY KEY,\n    {cols}\n)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS books_isbn13 ON books(isbn13) WHERE isbn13 IS NOT NULL")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS books_book_id ON books(book_id) WHERE book_id IS NOT NULL")
    return con


def find(con, column, value):
    if value is None:
        return None
    return con.execute(f"SELECT * FROM books WHERE {column} = ?", (value,)).fetchone()


def describe(existing):
    return f"book_id {existing['book_id']} ({existing['title']})"


def match(con, record, problems):
    """R10, R11, Q6, Q18. Returns the existing row for this book, or None if it is new."""
    by_isbn = find(con, "isbn13", record["isbn13"])
    by_id = find(con, "book_id", record["book_id"])
    if record["isbn13"] is not None:
        if by_isbn is not None and record["book_id"] is not None and by_isbn["book_id"] is not None \
                and by_isbn["book_id"] != record["book_id"]:
            problems.append(("isbn_conflict",
                             f"ISBN {record['isbn13']} already belongs to {describe(by_isbn)}"))
        if by_id is not None and by_id["isbn13"] is not None and by_id["isbn13"] != record["isbn13"]:
            problems.append(("book_id_conflict",
                             f"book_id {record['book_id']} is already in the database with ISBN {by_id['isbn13']}"))
        return by_isbn or by_id
    return by_id


def changes_for(existing, record):
    """R12, R13, Q9, Q14: compare stored values; an empty new value never erases."""
    return [{"field": c, "old": existing[c], "new": record[c]}
            for c in COLUMNS if record[c] is not None and record[c] != existing[c]]


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def ingest(csv_path):
    entry = {
        "ran_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "file": csv_path.name,
        "file_path": str(csv_path),
        "database": DB_PATH.name,
        "counts": {"read": 0, "loaded": 0, "updated": 0, "skipped_already_exists": 0, "rejected": 0},
        "rejected_rows": [],
        "skipped_rows": [],
        "updated_rows": [],
        "warnings": [],
    }
    con = open_db()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):        # Q11: header is line 1
            entry["counts"]["read"] += 1
            record, problems, warnings = check_row(row)
            existing = None
            if not any(code in ("isbn_mismatch",) for code, _ in problems) and (
                    record["isbn13"] is not None or record["book_id"] is not None):
                existing = match(con, record, problems)
            ident = {"line": line, "book_id": (row.get("book_id") or None), "title": (row.get("title") or None)}

            if problems:                                                 # Q15: every reason
                entry["counts"]["rejected"] += 1
                entry["rejected_rows"].append({
                    **ident,
                    "isbn": row.get("isbn") or "", "isbn13": row.get("isbn13") or "",
                    "reasons": [text for _, text in problems],
                    "what_to_do": sorted({WHAT_TO_DO[code] for code, _ in problems}),
                })
                continue

            if record["isbn13"] is None:
                warnings.append("no ISBN (identified by book_id)")      # R10

            if existing is None:
                con.execute(f"INSERT INTO books ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                            [record[c] for c in COLUMNS])
                entry["counts"]["loaded"] += 1
                status = "loaded"
            else:
                changes = changes_for(existing, record)
                if not changes:                                          # R12
                    entry["counts"]["skipped_already_exists"] += 1
                    entry["skipped_rows"].append({**ident, "reason": f"already in the database as {describe(existing)}, nothing changed"})
                    continue                                             # Q8: no warnings for skipped rows
                con.execute(f"UPDATE books SET {', '.join(ch['field'] + ' = ?' for ch in changes)} WHERE id = ?",
                            [ch["new"] for ch in changes] + [existing["id"]])
                entry["counts"]["updated"] += 1
                entry["updated_rows"].append({**ident, "changes": changes})
                status = "updated"
            for w in warnings:                                           # Q8, R15
                entry["warnings"].append({**ident, "status": status, "warning": w})
    con.commit()
    con.close()

    c = entry["counts"]
    entry["counts_add_up"] = c["loaded"] + c["updated"] + c["skipped_already_exists"] + c["rejected"] == c["read"]
    return entry


def append_to_log(entry):
    """Create the log if it doesn't exist, append if it does, never overwrite earlier runs."""
    runs = []
    if LOG_PATH.exists():
        try:
            runs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sys.exit(f"{LOG_PATH.name} exists but is not valid JSON. Nothing was written; fix or move it first.")
        if not isinstance(runs, list):
            sys.exit(f"{LOG_PATH.name} is not a list of runs. Nothing was written; fix or move it first.")
    runs.append(entry)
    tmp = LOG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, LOG_PATH)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 ingest.py <books CSV file>")
    csv_path = Path(sys.argv[1]).resolve()
    if not csv_path.is_file():
        sys.exit(f"File not found: {sys.argv[1]}")
    entry = ingest(csv_path)
    append_to_log(entry)
    c = entry["counts"]
    print(f"{entry['file']}: read {c['read']}, loaded {c['loaded']}, updated {c['updated']}, "
          f"skipped (already exist) {c['skipped_already_exists']}, rejected {c['rejected']}")
    print(f"Warnings: {len(entry['warnings'])}.  Counts add up: {'yes' if entry['counts_add_up'] else 'NO'}")
    print(f"Database: {DB_PATH.name}   Log: {LOG_PATH.name}")


if __name__ == "__main__":
    main()
