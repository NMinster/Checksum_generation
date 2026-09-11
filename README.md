# GEO checksum generator

A small command-line tool that computes the MD5 checksums GEO requires for
every raw and processed data file, and writes them straight into the
`file checksum` column of the GEO metadata spreadsheet.

It is built for the common situation where the data lives on a slow external
hard drive: hashing is done in large reads, every finished file is saved to a
CSV immediately, and re-running the command skips files that are already done.

## Setup

Python 3.9 or newer.

```bash
pip install -r requirements.txt
```

## Quick start: fully automatic

Keep the GEO metadata workbook on the external drive, in the folder that
holds the data files (subfolders are fine). Plug the drive in, then:

* **macOS**: double-click `run_geo_checksum.command` (the first time, right-click
  and choose Open, since it is not signed)
* **Windows**: double-click `run_geo_checksum.bat`
* **any terminal**: `python geo_checksum.py auto`

The tool then

1. finds the attached external drive (`/Volumes/*` on macOS, non-system drive
   letters on Windows, `/media` and `/run/media` on Linux),
2. searches it for an `.xlsx` that has `file name` and `file checksum` columns,
   which is how it recognises the GEO workbook (for example
   `Metadata for GEO submission.xlsx`),
3. shows you what it found and asks for confirmation,
4. hashes every file in the workbook's folder and subfolders, saving progress
   to `checksums.csv` next to the workbook so an interrupted run can resume,
5. rebuilds the `MD5 Checksums` tab: the **RAW FILES** block gets every
   sequencing file (`.fastq`, `.fq`, `.bam`, `.cram`, `.sra`, gzipped or not)
   and the **PROCESSED DATA FILES** block gets everything else (`.h5`, `.json`,
   `.csv`, `.png`, ...), each as a file name plus its MD5. Old entries in those
   two blocks are cleared first, titles and header rows are kept, the other
   tabs are untouched, and a `.bak` copy of the workbook is saved.

The blocks can be stacked (as in the official GEO template) or side by side
(RAW in columns A:B, PROCESSED in F:G). If the tab does not exist it is
created with the side-by-side layout.

If you would rather keep the file names you typed and only have the checksums
filled in next to them, use match mode:

```bash
python geo_checksum.py auto --mode match
```

If more than one drive or more than one candidate workbook is found, it stops
and tells you which ones, and you can point it at the right one:

```bash
python geo_checksum.py auto --drive /Volumes/SEQDATA
python geo_checksum.py auto --excel /Volumes/SEQDATA/project/GEO_metadata.xlsx
python geo_checksum.py auto --excel ... --root /Volumes/SEQDATA/project/data   # data in a different folder
python geo_checksum.py auto -y            # skip the confirmation prompt
```

The launchers install `openpyxl` on first run if it is missing. If the repo
was downloaded as a zip into Downloads, unzip it first; the launcher works
from wherever the folder sits.

## Manual usage

### 1. Scan the drive

```bash
python geo_checksum.py scan /Volumes/MyDrive/ProjectX --out checksums.csv
```

On Windows the path looks like `E:\ProjectX`. You can pass several folders or
individual files at once.

This walks the folder recursively, hashes every file (except obvious junk such
as `.DS_Store`, `Thumbs.db`, Excel lock files, Word/PowerPoint documents and
the tool's own outputs) and writes `checksums.csv` with the file name, MD5, size and full path. Progress and
an ETA are printed as it goes. If the scan is interrupted, run the same command
again and it picks up where it left off.

Useful options:

| option | meaning |
| --- | --- |
| `--pattern '*.fastq.gz'` | only hash matching files (repeatable; `--pattern '*'` for everything) |
| `--md5sum-file checksums.md5` | also write a plain `md5sum -c` style file |
| `--algorithm sha256` | use another hash (GEO wants MD5, the default) |
| `--no-recursive` | do not descend into subfolders |
| `--force` | re-hash files already in the CSV |

The tool skips macOS/Windows junk (`.DS_Store`, `._*` resource forks,
`Thumbs.db`, hidden folders) and warns if the same file name appears in more
than one folder, since GEO matches on file name alone.

### 2. Fill in the Excel sheet

Rebuild the checksum tab from the CSV (same as auto mode):

```bash
python geo_checksum.py fill checksums.csv --excel "Metadata for GEO submission.xlsx" --populate
```

Or only fill checksums next to file names already in the sheet:

```bash
python geo_checksum.py fill checksums.csv --excel GEO_metadata.xlsx
```

In that mode the tool looks for every header row in the workbook that has both a
`file name` and a `file checksum` column. The official GEO metadata template
has two such blocks, **RAW FILES** and **PROCESSED DATA FILES**, and both are
handled. For each file name listed, the matching checksum is written into the
checksum column. Matching is by base name and case-insensitive, and a full
path in the cell is fine.

A copy of the original workbook is saved as `GEO_metadata.bak.xlsx` before
anything is changed. Afterwards the tool reports:

* file names in the sheet that had no checksum (typo, or file not on the drive)
* files on the drive that are not listed in the sheet

Options:

| option | meaning |
| --- | --- |
| `--sheet Metadata` | only touch one sheet |
| `--name-col C --checksum-col E` | use explicit columns (letter or header text) instead of auto-detection |
| `--output filled.xlsx` | write to a new file instead of editing in place |
| `--overwrite` | replace checksums already present in the sheet |
| `--no-backup` | skip the `.bak` copy |

Scan and fill can be combined in one command:

```bash
python geo_checksum.py scan /Volumes/MyDrive/ProjectX --out checksums.csv --excel GEO_metadata.xlsx
```

### 3. (Optional) Verify before upload

```bash
python geo_checksum.py verify checksums.csv
```

Re-hashes every file in the CSV and reports any that changed or went missing.
Handy to run after copying files to a new location or right before uploading.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
