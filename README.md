# GEO checksum tool

Adds every data file in a folder, with its MD5 checksum, to the
**MD5 Checksums** tab of the GEO metadata Excel sheet in that same folder.
Anything already in the sheet is kept.

## How to use it

1. **Get the tool.** Click the green **Code** button on this page, choose
   **Download ZIP**, then unzip it (right-click the zip, "Extract All").
2. **Get the files ready.** The GEO Excel sheet (for example
   `Metadata for GEO submission.xlsx`) must be in the same folder as the data
   files, e.g. `E:\GEO submission_spatial`. Close Excel.
3. **Click the button.** In the unzipped folder double-click
   * `START_HERE_Windows.bat` on Windows, or
   * `START_HERE_Mac.command` on a Mac (the first time, right-click it and
     choose *Open*).

   The first time it may install Python by itself; if it asks you to close
   the window and click again, do that.
4. **Tell it the folder.** Paste the folder path (in File Explorer, click the
   address bar, Ctrl+C) and press Enter. Or just press Enter to pick the
   folder in a window.

That's it. It hashes the files (about 1 to 2 minutes per 10 GB on a USB
drive) and then says **DONE** with what it added. You can close the window at
any time; the next run carries on where it stopped.

## What it does to the Excel sheet

* Sequencing files (`.fastq`, `.fastq.gz`, `.fq`, `.bam`, `.cram`, `.sra`) go
  under **RAW FILES**. Everything else (`.h5`, `.json`, `.parquet`, `.png`,
  `.csv`, ...) goes under **PROCESSED DATA FILES**.
* **Nothing you typed is overwritten.** A file already listed gets its checksum
  filled in only if that cell is empty. Files not listed yet are added at the
  bottom of the right block. If a checksum in the sheet does not match the
  file, or a listed name has no file in the folder, it tells you and leaves
  the row alone.
* Titles, headers and the other tabs are not touched. A copy of the sheet as
  it was before is saved in the tool's `_work` folder, and no extra files are
  put in your data folder.

Command-line options, how it finds the drive on its own, and other details are
in [docs/ADVANCED.md](docs/ADVANCED.md).
