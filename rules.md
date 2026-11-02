# Ingestion Rules

*Drafted with assistance from Claude's suggestions, but edited, reviewed, and verified by me.*

These are the rules for loading a books CSV file into `books.db`. They are the only source of truth for `ingest.py`.

## Checking and repairing ISBNs

1. **ISBNs are text, never numbers.** A valid ISBN-10 is 9 digits followed by a digit or a capital X, with a correct mod-11 check digit. A valid ISBN-13 is 13 digits starting with 978 or 979, with a correct mod-10 check digit.

2. **Formatting is repaired, because nothing is guessed.** Before checking, remove spaces and hyphens from both ISBN columns, and change a lowercase `x` at the end of an ISBN-10 to `X`. The digits are all still there, so this is a certain repair. Record it as a warning so it shows up in the report.

3. **Lost leading zeros are repaired only when the result is valid.** If the `isbn` value is shorter than 10 characters, add zeros on the left until it is 10. If the padded value passes the check digit, use it. If it does not, the value is invalid (rule 8). An ISBN-10 is always 10 characters, so the number of missing zeros is known and this is not a guess.

4. **An ISBN-13 in the `isbn` column is moved, not rejected.** If the `isbn` value is a valid ISBN-13, treat it as the row's ISBN-13. Record a warning.

5. **Scientific-notation ISBN-13s are never trusted.** A value like `9.78043902348e+12` has lost its check digit and may have had its 12th digit rounded. Throw it away and rebuild the ISBN-13 from the row's valid ISBN-10. If the row has no valid ISBN-10, store the ISBN-13 as empty and record a warning: "isbn13 damaged, not recoverable". Working backwards from a rounded number is a guess, so it is never done.

6. **An `isbn13` value that is not an ISBN at all is dropped.** This means the wrong length, no 978/979 prefix, or written as a decimal (for example `76783609419.0`). Drop the value, rebuild the ISBN-13 from the ISBN-10 if there is a valid one, and record a warning.

7. **Missing ISBNs are filled in only when they can be calculated.** If a row has a valid ISBN-10 but no ISBN-13, calculate the ISBN-13 (978 + first 9 digits + new check digit). If a row has a valid 978 ISBN-13 but no ISBN-10, calculate the ISBN-10. A 979 ISBN-13 has no ISBN-10, so leave the ISBN-10 empty.

## Rejecting rows

8. **A value that is still invalid after rules 2–4 rejects the whole row.** This includes a wrong check digit, a letter in the middle, too many digits, and a short value that fails after padding. It also includes a 13-digit, 978/979 value in `isbn13` whose check digit is wrong. Never try to fix the bad digit: the check digit can sometimes "solve" it, but the answer can be another book's ISBN (for example, `04390A3483` becomes *The Hunger Games*). That is a guess, not a repair.

9. **A row whose ISBN-10 and ISBN-13 are different books is rejected.** If the ISBN-10 converts to a different ISBN-13 than the one in the row, there is no way to know which is right.

## Deciding whether a book is already in the database

10. **Two rows are the same book when they have the same ISBN-13** (after the repairs above). If a row has no usable ISBN, it is matched by the supplier's `book_id` instead, and it is loaded with the warning "no ISBN".

11. **ISBN conflicts are rejected.** If a row's ISBN-13 already belongs to a book in the database with a different `book_id`, reject the row. The same applies if a row has an ISBN-13 and its `book_id` is already in the database with a different ISBN-13. One ISBN can't be two books. (A row with no ISBN is not a conflict; see rule 13.)

12. **A book that arrives again unchanged is skipped.** If the book is already in the database and every field is the same, skip it and count it as "already exists". This includes a duplicate row later in the same file.

13. **A book that arrives again with changes is updated.** If the book is already in the database and some fields are different, update only those fields and record each one as old value → new value. An empty value in the new file never erases a value already in the database. For example, *Deathly Hallows* keeps its ISBN even though batch 2 left it blank.

## Running and reporting

14. **Every row is checked on every run, and the same file always gives the same result.** Running the same file twice must not create duplicates. On the second run, every row is either skipped or rejected again for the same reason.

15. **The report must let the reader know, the next morning, whether everything was handled and what to fix.** For each run, show:
    - when it ran and which file;
    - how many rows were read, loaded, updated, skipped and rejected, and a check that loaded + updated + skipped + rejected = read;
    - every rejected row with its line number, `book_id`, title, the original ISBN values, the reason, and what to do about it (for example, "ask the supplier for the correct ISBN");
    - every warning (repairs, dropped values, books loaded with no ISBN), so nothing changes without anyone seeing it.

## Answers to Claude's questions (Part 4)

These answers are part of the rules.

- **Q1 – Columns stored:** all 23 columns from the CSV go into `books.db`.
- **Q2 – How columns are stored:**
  - Stored as **whole numbers:** `book_id`, `goodreads_book_id`, `best_book_id`, `work_id`, `books_count`, `original_publication_year`, `ratings_count`, `work_ratings_count`, `work_text_reviews_count`, `ratings_1` to `ratings_5`. A year written `2008.0` is stored as `2008`.
  - Stored as a **decimal:** `average_rating`.
  - Everything else is **text**, including both ISBN columns (rule 1).
  - An empty number cell is stored as empty.
  - A cell that should be a number but isn't (for example `abc`) is stored as empty, with a warning.
- **Q3 – Other reasons to reject a row:**
  - Any count is negative. The counts are `books_count`, `ratings_count`, `work_ratings_count`, `work_text_reviews_count` and `ratings_1` to `ratings_5`.
  - `ratings_1` + `ratings_2` + `ratings_3` + `ratings_4` + `ratings_5` does not equal `work_ratings_count`.
  - Nothing else rejects a row except the ISBN rules.
  - If any of `ratings_1`–`ratings_5` or `work_ratings_count` is empty (including a cell emptied because it wasn't a number), the "add up" check is skipped for that row.
- **Q13 – Fractions in whole-number columns:** a value like `2008.5` or `12.7` in a whole-number column is treated the same as "not a number": stored as empty, with a warning. (`2008.0` is a whole number.)
- **Q14 – Comparing for changes:** a re-delivered book is compared using the values as they would be stored, after repairs and conversion. So `2008.0` and `2008`, or `439023483` and `0439023483`, are the same.
- **Q15 – More than one problem:** a rejected row lists every reason it was rejected, not just the first.
- **Q16 – Warnings for calculated ISBNs:** calculating a missing ISBN-10 or ISBN-13 (rule 7) records a warning, like every other repair (rules 2–6).
- **Q17 – A letter in the isbn13 column:** if the `isbn13` value contains a letter (for example `97804390A3481`), the row is rejected, the same as rule 8. It is not dropped under rule 6.
- **Q18 – Valid ISBN but no `book_id`:** the row is matched by its ISBN (rule 10). If it is a new book, it is loaded with an empty `book_id`. A later delivery of the same ISBN that has a `book_id` fills it in (rule 13).
- **Q4 – Damaged ISBN-13 that points to a different book:** rule 5 wins. A scientific-notation ISBN-13 is always thrown away and rebuilt from the ISBN-10, even when its digits don't match the ISBN-10. The row is loaded with a warning saying the damaged isbn13 disagreed with the isbn.
- **Q5 – ISBN-13 in both columns:** if the `isbn` column holds a valid ISBN-13 (rule 4) and the `isbn13` column also holds a valid ISBN-13, load the row if they are the same, and reject it under rule 9 if they differ.
- **Q6 – A book's ISBN arrives later:** if a book is stored with no ISBN and a later row with the same `book_id` brings a valid ISBN, that is an update (rule 13), not a conflict.
- **Q7 – No ISBN and no `book_id`:** reject the row; there is nothing to match it on.
- **Q8 – Repeated warnings:** warnings are recorded only for rows that were loaded or updated in that run. A skipped row gets no warnings.
- **Q9 – Which fields are compared for changes:** every column stored.
- **Q10 – "What to do" text:** one fixed sentence per rejection reason is fine.
- **Q11 – Line numbers:** the header is line 1, so the first book is on line 2.
- **Q12 – Missing or extra columns:** load what is there. A missing column is treated as empty in every row. Extra columns that are not among the 23 are ignored.

## Examples

| # | Where from | `isbn` value | `isbn13` value | What my rules say happens |
|---|---|---|---|---|
| 1 | books.csv, *The Hunger Games* | `0439023483` | — | Valid. Load; calculate ISBN-13 `9780439023481` (rules 1, 7) |
| 2 | books.csv, *The Hunger Games* | `439023483` | `9.78043902348e+12` | Pad to `0439023483`; throw away isbn13 and rebuild `9780439023481`. Load with warnings (rules 3, 5) |
| 3 | batch 2, *Salt and Ember* | `0-450-19827-8` | `9780450198274` | Remove hyphens; both valid and match. Load with warning (rule 2) |
| 4 | batch 2, *A Field Guide to Quiet Places* | `␣162 001 4750␣` | `9781620014752` | Remove spaces → `1620014750`; matches isbn13. Load with warning (rule 2) |
| 5 | batch 2, *Winter Orchard* | `031200009x` | `9780312000097` | Change `x` to `X`; matches. Load with warning (rule 2) |
| 6 | batch 2, *An Atlas of Small Kindnesses* | `9781982147600` | — | Valid ISBN-13 in the wrong column: use it as the ISBN-13, calculate ISBN-10. Load with warning (rules 4, 7) |
| 7 | batch 2, *Notes from the Night Ferry* | — | `9798351220413` | Valid 979 ISBN-13; no ISBN-10 exists. Load (rules 1, 7) |
| 8 | batch 2, *Small Hours* | `1854433017` | — | Wrong check digit. **Reject** (rule 8) |
| 9 | batch 2, *The Glass Aviary* | `04390A3483` | — | Letter in the middle. **Reject**; don't "solve" it (rule 8) |
| 10 | batch 2, *Borrowed Light* | `15287463097` | — | 11 digits. **Reject** (rule 8) |
| 11 | made up | `0439023484` | — | One digit off from a real ISBN; check digit fails. **Reject** (rule 8) |
| 12 | made up | — | `9780439023482` | Looks like an ISBN-13, but the check digit is wrong. **Reject** (rule 8) |
| 13 | batch 2, *Tides of Marrow Bay* | `1555550126` | `9781555550134` | Both valid, but different books. **Reject** (rule 9) |
| 14 | books.csv, *How to Win Friends…* | — | `9.78067172365e+12` | Damaged isbn13 and nothing to rebuild from. Store no ISBN; match by `book_id`. Load with warnings (rules 5, 10) |
| 15 | books.csv, *The Complete Anne of Green Gables* | `553609416` | `76783609419.0` | isbn13 is not an ISBN: drop it. Pad isbn, rebuild ISBN-13. Load with warnings (rules 3, 6) |
| 16 | batch 2, *Paper Moons* (book_id 10013) | `1416524797` | — | Valid, but that ISBN already belongs to *Angels & Demons* (book_id 9). **Reject** (rule 11) |
| 17 | batch 2, *The Lantern Keeper's Daughter* (second copy of the row) | `1528746309` | `9781528746304` | Same as the row above it. **Skip** as already exists (rule 12) |
| 18 | batch 2, *1984* (already loaded from books.csv) | `451524934` | `9.78045152494e+12` | Same book; only the rating counts changed. **Update** those fields (rule 13) |
| 19 | batch 2, *Harry Potter and the Deathly Hallows* | — | — | No ISBN, so match by `book_id` 25; already loaded. Keep the existing ISBN; nothing else changed. **Skip** (rules 10, 12, 13) |
