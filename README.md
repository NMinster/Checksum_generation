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

## Quick start (no computer skills needed)

1. Put the GEO metadata Excel sheet (for example
   `Metadata for GEO submission.xlsx`) in the same folder as the data files on
   the external drive, e.g. `E:\GEO submission_spatial`.
2. Close the Excel sheet if it is open.
3. Double-click the launcher in this folder:
   * **Windows**: `run_geo_checksum.bat`
   * **Mac**: `run_geo_checksum.command` (the first time, right-click it and
     choose Open, because it is not signed)
4. A window opens and asks for the folder. Copy the folder's path from the
   File Explorer address bar (or drag the folder into the window on a Mac),
   paste it, and press Enter.
5. It shows what it found and asks you to press Enter to start. Hashing takes
   roughly one to two minutes per 10 GB on a USB drive; you can close the
   window at any time and run it again later, it carries on where it stopped.
6. When it says **Done**, open the Excel sheet: the `MD5 Checksums` tab now has
   every file with its checksum.

What it does to the sheet:

* Sequencing files (`.fastq`, `.fastq.gz`, `.fq`, `.bam`, `.cram`, `.sra`) go
  under **RAW FILES**; everything else (`.h5`, `.json`, `.parquet`, `.png`,
  `.csv`, ...) goes under **PROCESSED DATA FILES**.
* **Anything you already typed into the tab is kept.** A file name that is
  already there gets its checksum filled in (or corrected if it was wrong),
  files that are not listed yet are added at the bottom of the right block, and
  names in the sheet that have no matching file in the folder are left alone
  and listed at the end so you can check them.
* Titles, header rows and the other tabs are not touched. A copy of the
  original is saved next to it as `... .bak.xlsx` before anything is changed.
* The blocks can be stacked (official GEO template) or side by side (RAW in
  columns A:B, PROCESSED in F:G). If there is no checksum tab, one is created.

If the first launcher run says Python is missing, install it from
https://www.python.org/downloads/ (on Windows tick "Add python.exe to PATH")
and double-click the launcher again. The launcher installs the one extra
package it needs (`openpyxl`) by itself.

Things it handles on a real drive:

* **Folder at the top of the drive** (files directly in `E:\`): only the
  files directly in it are used, so other backup folders on the drive are not
  swept in.
* **Fastq "files" that are really folders** (some download tools create a
  folder named `X_R1_001.fastq.gz` with the file inside): the folder is
  entered and the file inside is hashed under its own name. A note lists such
  folders, since GEO needs the files, not the folders.
* **Sheet still open in Excel** when hashing finishes: you are asked to close
  it and press Enter. If nobody is there to answer, the result is saved as
  `... (with checksums).xlsx` next to the original so nothing is lost.

## Command-line use

Everything above is also available without the prompts:

```bash
python geo_checksum.py auto                      # find the drive and workbook automatically
python geo_checksum.py auto --excel "E:\GEO submission_spatial\Metadata for GEO submission.xlsx"
python geo_checksum.py auto --replace            # wipe the RAW / PROCESSED blocks and rebuild them
python geo_checksum.py auto --mode match         # only fill checksums next to names already listed
python geo_checksum.py auto -y                   # skip the confirmation prompt
```

Auto mode looks for an attached external drive (`/Volumes/*` on macOS,
non-system drive letters on Windows, `/media` and `/run/media` on Linux),
searches it for an `.xlsx` that has `file name` and `file checksum` columns,
and uses that workbook's folder as the data root. If more than one drive or
workbook is found it lists them so you can pick with `--drive` or `--excel`;
`--root` points at a data folder other than the workbook's.

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

Add the files in the CSV to the checksum tab, keeping existing entries (same as
auto mode; add `--replace` to rebuild the blocks from scratch):

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
