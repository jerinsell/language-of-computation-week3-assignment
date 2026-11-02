# ISBN Data Validation

Diagnosis of the `isbn` and `isbn13` columns in **books.csv** (10,000 rows, the Module 2 book list) and **books-batch2.csv** (31 rows, the second delivery). Every row was checked. **Neither file was changed and nothing was fixed.**

"Line" means the line in the file, counting the header as line 1.

## Summary

| | books.csv | books-batch2.csv |
|---|---|---|
| Rows | 10,000 | 31 |
| `isbn` valid exactly as written | 2,690 (27%) | 12 |
| `isbn` valid only after a formatting repair | 6,587 (leading zeros) | 10 (zeros, hyphens, spaces, lowercase x) |
| `isbn` not a valid ISBN-10 | 23 | 4 |
| `isbn` empty | 700 | 5 |
| `isbn13` valid exactly as written | **0** | 9 |
| `isbn13` in scientific notation (damaged) | 9,407 | 14 |
| `isbn13` not an ISBN at all | 8 | 0 |
| `isbn13` empty | 585 | 8 |
| Rows with no ISBN in either column | 565 | 3 |

**The biggest problems:**
- Almost every value in books.csv has been damaged by software that treated ISBNs as numbers instead of text.
- The `isbn` column lost its leading zeros.
- The `isbn13` column was turned into scientific notation, which throws away the last digit.
- Batch 2 adds hand-entry problems (hyphens, spaces, a lowercase `x`, a letter, an extra digit), a duplicated row, and ISBNs that belong to other books.

## How "valid" was decided

The International ISBN Agency defines two kinds of ISBN:

| | ISBN-10 (used until 2007) | ISBN-13 (used since 2007) |
|---|---|---|
| Length | 10 characters | 13 digits |
| Characters | 9 digits, then a digit or a capital **X** | digits only |
| Prefix | none | **978** or **979** |
| Last character | check digit (mod 11) | check digit (mod 10) |

The **last character is a check digit**: it is calculated from the others, so a typo is almost always detected.

- **ISBN-10:** multiply the 10 characters by 10, 9, 8 … 1 (X counts as 10) and add them up. The total must divide evenly by 11. Because the remainder can be 10, the check character can be **X**.
- **ISBN-13:** multiply the 13 digits alternately by 1 and 3 and add them up. The total must divide evenly by 10.
- **Converting:** a 978 ISBN-13 is `978` + the first 9 digits of the ISBN-10 + a new check digit. A 979 ISBN-13 has no ISBN-10.

A value was counted **valid** only if it has the right length, only allowed characters, the right prefix (ISBN-13) and a correct check digit. Hyphens and spaces are allowed when an ISBN is printed, but they are not part of the number, so they count as a formatting problem.

---

## books.csv: `isbn` column

| Problem | Rows | Example (line: value → what it should be) | What is wrong | Information still there? | Probable cause |
|---|---|---|---|---|---|
| Valid ISBN-10 | 2,690 | 10: `1416524797` (*Angels & Demons*) | Nothing | Yes | — |
| **Leading zero(s) lost** | 6,587 | 2: `439023483` → `0439023483` (*The Hunger Games*) | Shorter than 10 characters. Adding zeros back on the left gives a valid ISBN-10. | **Yes, fully.** An ISBN-10 is always 10 characters, so the number of missing zeros is known. | The column was read as a number, and numbers have no leading zeros. Same problem as the Week 1 zip codes. |
| **Wrong check digit (short)** | 14 | 917: `812971060` → padded `0812971060` (*Reading Lolita in Tehran*) | Even with zeros added, the check digit does not match. For this book it should be `X` (`081297106X`). | **Partly.** The first 9 digits usually agree with the row's isbn13, but you can't tell from the ISBN alone which character is wrong. | Bad check character in the source data. In several cases an `X` was lost when the column was made numeric. |
| **Wrong check digit (10 characters)** | 9 | 2779: `1416913184` (*Two-Way Street*); correct check digit would be `1` | Right length, but the check digit doesn't match. | **Partly**, same as above. | Typo or bad data upstream (Goodreads). |
| Empty | 700 | 107: *Bossypants* | No value | Nothing to recover | Book listed without an ISBN-10 (many have only an isbn13, or none). |

For **19 of the 23** wrong-check-digit rows, the first 9 digits match the row's isbn13, allowing for the rounding described below, so only the check character is bad. In 2 rows (lines 4323 and 8553) the digits disagree with isbn13 in a way that isn't rounding, and 2 rows have no isbn13 to compare.

## books.csv: `isbn13` column

**Not one isbn13 value in books.csv is valid as written.**

| Problem | Rows | Example | What is wrong | Information still there? | Probable cause |
|---|---|---|---|---|---|
| **Scientific notation, matches the row's isbn** | 9,238 | 2: `9.78043902348e+12` (true value `9780439023481`) | Stored as a decimal number with only **12 significant digits**, so the 13th digit (the check digit) is gone. In **4,204** of these rows, the 12th digit was also **rounded up** (it shows one higher than the truth). Example, line 11, *Pride and Prejudice*: true `9780679783268`, stored `9.78067978327e+12`. | **Only with help from the isbn column.** The real ISBN-13 can be rebuilt from a valid (or zero-padded) ISBN-10 in the same row. On its own, the value can't tell you its 12th or 13th digit. | The column was treated as a decimal (float) number and written out in a shortened format. |
| **Scientific notation, no usable isbn in the row** | 156 | 261: `9.78067172365e+12` (*How to Win Friends and Influence People*) | Same damage, but nothing to rebuild it from. Working backwards: 45 rows have **one** possible ISBN-13, 84 have **two** (rounded or not), and 27 have **none** (no real ISBN-13 rounds to that value). | **No.** Any repair is a guess, and in 84 rows a coin flip. | Same as above. |
| **Scientific notation, but a different book than isbn** | 13 | 623: isbn `446612707` vs isbn13 `9.78055381395e+12` (*Nights in Rodanthe*) | Both columns hold an ISBN, but they're for different books (probably different editions). | Can't tell which one is right | Editions mixed up in the source data. |
| **Not an ISBN** | 8 | 959: `76783609419.0`; 2895: `6.45573003012e+11`; 8175: `195170342.0` | Too short, no 978/979 prefix. Most look like **UPC barcodes** (11–12 digits). Line 1444 is a cut-off ISBN-13 (`97893806587`), and line 8175 is the ISBN-10 put in the wrong column. All are stored as decimals (`.0` or `e+11`). | No ISBN-13 to recover | Wrong code entered, then made numeric. |
| Empty | 585 | 107: *Bossypants* | No value | — | No ISBN-13 known |

**Rounding makes different books look identical.** **262 isbn13 values** in books.csv are shared by **two different books**. For example, *To Kill a Mockingbird* (`9780061120084`) and *A Tree Grows in Brooklyn* (`9780061120077`) were both stored as `9.78006112008e+12`. So isbn13 as written **cannot** be used to tell books apart.

---

## books-batch2.csv: `isbn` column

| Problem | Rows | Example (line: value) | What is wrong | Information still there? | Probable cause |
|---|---|---|---|---|---|
| Valid ISBN-10 | 12 | 4: `0439139600` (*Goblet of Fire*) | Nothing (this delivery even kept the leading zero) | Yes | — |
| Leading zero(s) lost | 7 | 6: `441773028` → `0441773028` (*The Long Walk Home*) | Same as books.csv | Yes, fully | Same as books.csv |
| **Hyphens** | 1 | 30: `0-450-19827-8` (*Salt and Ember*) | Printed form with hyphens; valid once they're removed | Yes, fully | Copied from a book cover or catalogue |
| **Spaces** | 1 | 31: `␣162 001 4750␣` (*A Field Guide to Quiet Places*) | Spaces inside and around it; valid once removed (`1620014750`) | Yes, fully | Typed or pasted by hand |
| **Lowercase x** | 1 | 27: `031200009x` (*Winter Orchard*) | The check character must be a capital X; valid as `031200009X` | Yes, fully | Typed by hand |
| **ISBN-13 in the ISBN-10 column** | 1 | 18: `9781982147600` (*An Atlas of Small Kindnesses*) | A valid ISBN-13 in the wrong column | Yes, but it belongs in isbn13 | Entered in the wrong column |
| **Wrong check digit** | 1 | 11: `1854433017` (*Small Hours*); check digit should be `6` | Doesn't pass the check | **No.** You can't know which digit is the typo. | Typo |
| **Illegal character** | 1 | 3: `04390A3483` (*The Glass Aviary*) | A letter in the middle. The check digit allows exactly one fill-in (`A`→`2`), but that gives `0439023483`, **which is *The Hunger Games*'s ISBN.** | **No.** The "repair" points to a different book, so it's a guess and probably wrong. | Typo, or a misread scan |
| **Too long** | 1 | 20: `15287463097` (*Borrowed Light*) | 11 digits. Removing one digit gives only one valid ISBN-10, `1528746309`, **which is *The Lantern Keeper's Daughter*'s ISBN** (lines 14–15). | **No.** Same trap: the "repair" is another book. | Extra keystroke, or a copy-paste from the row above |
| Empty | 5 | 2: *Bossypants* | No value | — | No ISBN-10 known |

## books-batch2.csv: `isbn13` column

| Problem | Rows | Example | What is wrong | Information still there? |
|---|---|---|---|---|
| Valid ISBN-13 | 9 | 4: `9780439139601` (*Goblet of Fire*); 10: `9798351220413` (a valid 979 ISBN, which has no ISBN-10) | Nothing, except see the mismatch below | Yes |
| Scientific notation | 14 | 5: `9.78140130858e+12` (*The Five People You Meet in Heaven*) | Same damage as books.csv. All 14 can be rebuilt from the row's isbn; one (line 13, *1984*) had its 12th digit rounded up. | Only with the isbn column |
| Empty | 8 | 3: *The Glass Aviary* | — | — |

**ISBN-10 and ISBN-13 disagree:** line 16, *Tides of Marrow Bay*. Both values are valid, but isbn `1555550126` converts to `9781555550127`, while the row says `9781555550134`. They are two different books, and nothing says which is right.

---

## Other things found that affect loading

These aren't broken ISBN values, but they'll matter when the rules are written in Part 3:

1. **An exact duplicate row:** lines 14 and 15 of batch 2 (*The Lantern Keeper's Daughter*, book_id 10001) are identical.
2. **The same ISBN on two different titles:** batch 2 line 24, *Paper Moons* (book_id 10013), has `1416524797`, the ISBN of *Angels & Demons* (book_id 9, which is on line 21 of batch 2 and also in books.csv).
3. **Books with no ISBN at all:** 565 in books.csv and 3 in batch 2 (*Bossypants*, *Untitled Manuscript*, *Harry Potter and the Deathly Hallows*). Something other than an ISBN would be needed to tell these books apart.
4. **Batch 2 re-delivers 16 books already in books.csv** (same book_id):
   - **10 are identical.**
   - **4 have updated rating counts:** *The Five People You Meet in Heaven*, *Animal Farm*, *1984* and *City of Glass*.
   - **1 has better ISBNs:** *Goblet of Fire* now has the leading zero and a full, valid isbn13.
   - **1 has lost its ISBNs:** *Deathly Hallows* had `545010225` / `9.78054501022e+12` in books.csv but is blank in batch 2.
5. **14 batch 2 books are new** (book_ids 10001–10014).
