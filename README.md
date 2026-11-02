# Week 3 Assignment

This is my Module 3 assignment for MSAI-5523.

## How to run the ingestion

`ingest.py` loads a books CSV file into `books.db`, following the rules in `rules.md`. Each run adds an entry to `ingestion-log.json`. Both files are created in this folder. You need Python 3, which comes with macOS (no extra packages, no internet).

### 1. Open the Terminal

Press **⌘ Command + Space**, type **Terminal**, and press **Return**.

### 2. Go to this folder

Copy this line into the Terminal and press **Return**:

```bash
cd ~/Desktop/"grad school"/assignments/"language-of-computation:week1-assingment"/week3-assignment
```

In Finder this folder shows as **Desktop › grad school › assignments › language-of-computation/week1-assingment › week3-assignment**. Finder shows a `/` in the folder name, but the Terminal sees it as a `:`, which is why the command uses a colon.

If the line doesn't work, type `cd ` (with a space after it), drag the **week3-assignment** folder from Finder into the Terminal window, and press **Return**.

To check you're in the right place, run:

```bash
ls
```

You should see `books.csv`, `books-batch2.csv`, `ingest.py` and `report.html` in the list.

### 3. Run the ingestion

Run each command and press **Return**, in this order:

```bash
python3 ingest.py books.csv
```

```bash
python3 ingest.py books.csv
```

```bash
python3 ingest.py books-batch2.csv
```

After each run the Terminal prints how many rows were read, loaded, updated, skipped (already exist) and rejected, and whether the counts add up.

### 4. Open the report

Open `report.html` in your browser. Either double-click it in Finder, or run:

```bash
open report.html
```

Click **Open ingestion-log.json** and choose `ingestion-log.json` from this folder. The runs are shown newest first, with each run's numbers and the rows that were not loaded. The page works without a server or internet.

### Starting over

To rebuild from nothing (for example after changing `rules.md` and `ingest.py`), delete the database and the log, then repeat step 3:

```bash
rm books.db ingestion-log.json
```
