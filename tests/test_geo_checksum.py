import hashlib
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geo_checksum as gc  # noqa: E402


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


@pytest.fixture
def drive(tmp_path):
    """A fake external drive with raw and processed files in subfolders."""
    raw = tmp_path / "drive" / "raw"
    proc = tmp_path / "drive" / "processed"
    raw.mkdir(parents=True)
    proc.mkdir(parents=True)
    files = {
        raw / "sampleA_R1.fastq.gz": b"AAAA" * 1000,
        raw / "sampleA_R2.fastq.gz": b"CCCC" * 1000,
        proc / "counts.txt": b"gene\tcount\nX\t1\n",
        raw / ".DS_Store": b"junk",
        raw / "._sampleA_R1.fastq.gz": b"applejunk",
        raw / "notes.docx": b"not a data file",
    }
    for p, data in files.items():
        p.write_bytes(data)
    return tmp_path / "drive", files


@pytest.fixture
def geo_workbook(tmp_path):
    """Mimic the GEO metadata template: two sections with their own header rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Metadata"
    rows = [
        ["SERIES"],
        ["title", "My study"],
        [],
        ["RAW FILES"],
        ["file name", "file type", "file checksum", "instrument model"],
        ["sampleA_R1.fastq.gz", "fastq", None, "NovaSeq"],
        ["sampleA_R2.fastq.gz", "fastq", None, "NovaSeq"],
        ["missing_R1.fastq.gz", "fastq", None, "NovaSeq"],
        [],
        ["PROCESSED DATA FILES"],
        ["file name", "file type", "file checksum"],
        ["counts.txt", "txt", None],
    ]
    for r in rows:
        ws.append(r)
    path = tmp_path / "GEO_metadata.xlsx"
    wb.save(path)
    return path


def test_scan_hashes_only_data_files(drive, tmp_path):
    root, files = drive
    out = tmp_path / "checksums.csv"
    records = gc.scan(root, out, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    names = {r.file_name for r in records}
    assert names == {"sampleA_R1.fastq.gz", "sampleA_R2.fastq.gz", "counts.txt"}
    by_name = {r.file_name: r for r in records}
    assert by_name["sampleA_R1.fastq.gz"].checksum == md5(b"AAAA" * 1000)
    assert by_name["counts.txt"].checksum == md5(b"gene\tcount\nX\t1\n")
    # CSV round-trips
    assert {r.file_name for r in gc.read_checksum_csv(out)} == names


def test_scan_resumes_from_cache(drive, tmp_path, monkeypatch):
    root, _ = drive
    out = tmp_path / "checksums.csv"
    gc.scan(root, out, gc.DEFAULT_PATTERNS, "md5", quiet=True)

    calls = []
    real = gc.hash_file
    monkeypatch.setattr(gc, "hash_file", lambda p, a, progress=None: calls.append(p) or real(p, a))
    gc.scan(root, out, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    assert calls == []  # everything served from cache

    # Modifying a file invalidates just that entry
    target = root / "processed" / "counts.txt"
    target.write_bytes(b"different")
    gc.scan(root, out, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    assert [p.name for p in calls] == ["counts.txt"]

    # --force re-hashes everything
    calls.clear()
    gc.scan(root, out, gc.DEFAULT_PATTERNS, "md5", force=True, quiet=True)
    assert len(calls) == 3


def test_custom_pattern(drive, tmp_path):
    root, _ = drive
    records = gc.scan(root, None, ["*.docx"], "md5", quiet=True)
    assert [r.file_name for r in records] == ["notes.docx"]


def test_fill_geo_template_sections(drive, geo_workbook, tmp_path):
    root, _ = drive
    records = gc.scan(root, None, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    summary = gc.fill_workbook(geo_workbook, records, quiet=True)

    assert {n for _, _, n in summary["filled"]} == {
        "sampleA_R1.fastq.gz", "sampleA_R2.fastq.gz", "counts.txt"}
    assert [n for _, _, n in summary["missing"]] == ["missing_R1.fastq.gz"]
    assert summary["unused"] == []

    ws = openpyxl.load_workbook(geo_workbook)["Metadata"]
    assert ws["C6"].value == md5(b"AAAA" * 1000)
    assert ws["C7"].value == md5(b"CCCC" * 1000)
    assert ws["C8"].value is None
    assert ws["C12"].value == md5(b"gene\tcount\nX\t1\n")
    # header rows untouched
    assert ws["C5"].value == "file checksum"
    assert ws["C11"].value == "file checksum"
    # backup written
    assert (tmp_path / "GEO_metadata.bak.xlsx").exists()


def test_fill_does_not_overwrite_without_flag(drive, geo_workbook):
    root, _ = drive
    wb = openpyxl.load_workbook(geo_workbook)
    wb["Metadata"]["C6"].value = "deadbeef"
    wb.save(geo_workbook)

    records = gc.scan(root, None, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    summary = gc.fill_workbook(geo_workbook, records, quiet=True, backup=False)
    assert ("Metadata", 6, "sampleA_R1.fastq.gz") in summary["missing"]
    assert openpyxl.load_workbook(geo_workbook)["Metadata"]["C6"].value == "deadbeef"

    gc.fill_workbook(geo_workbook, records, quiet=True, backup=False, overwrite=True)
    assert openpyxl.load_workbook(geo_workbook)["Metadata"]["C6"].value == md5(b"AAAA" * 1000)


def test_fill_explicit_columns_and_output(drive, tmp_path):
    root, _ = drive
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Sample", "Filename", "MD5"])
    ws.append(["A", "raw/sampleA_R1.fastq.gz", None])
    ws.append(["B", "SAMPLEA_R2.FASTQ.GZ", None])
    src = tmp_path / "sheet.xlsx"
    wb.save(src)

    records = gc.scan(root, None, gc.DEFAULT_PATTERNS, "md5", quiet=True)
    out = tmp_path / "sheet_filled.xlsx"
    summary = gc.fill_workbook(src, records, name_col="Filename", checksum_col="C",
                               output=out, quiet=True)
    assert len(summary["filled"]) == 2
    ws2 = openpyxl.load_workbook(out).active
    assert ws2["C2"].value == md5(b"AAAA" * 1000)   # path in cell -> basename match
    assert ws2["C3"].value == md5(b"CCCC" * 1000)   # case-insensitive match
    assert openpyxl.load_workbook(src).active["C2"].value is None  # source untouched


def test_cli_end_to_end(drive, geo_workbook, tmp_path):
    root, _ = drive
    out = tmp_path / "checksums.csv"
    md5file = tmp_path / "checksums.md5"
    rc = gc.main(["scan", str(root), "--out", str(out), "--md5sum-file", str(md5file),
                  "--excel", str(geo_workbook), "--no-backup", "-q"])
    assert rc == 0
    ws = openpyxl.load_workbook(geo_workbook)["Metadata"]
    assert ws["C12"].value == md5(b"gene\tcount\nX\t1\n")
    lines = md5file.read_text().splitlines()
    assert f"{md5(b'AAAA' * 1000)}  sampleA_R1.fastq.gz" in lines

    assert gc.main(["verify", str(out), "-q"]) == 0
    (root / "raw" / "sampleA_R2.fastq.gz").write_bytes(b"changed")
    assert gc.main(["verify", str(out), "-q"]) == 1

    # fill returns 2 when the sheet lists a file we have no checksum for
    assert gc.main(["fill", str(out), "--excel", str(geo_workbook), "--no-backup", "-q"]) == 2


# --------------------------------------------------------------------------- #
# auto mode
# --------------------------------------------------------------------------- #

@pytest.fixture
def fake_drive(tmp_path):
    """An 'external drive' with the GEO workbook sitting next to the data files."""
    drive = tmp_path / "Volumes" / "SEQDATA"
    proj = drive / "GEO_submission"
    (proj / "fastq").mkdir(parents=True)
    (proj / "fastq" / "s1_R1.fastq.gz").write_bytes(b"AAAA" * 10)
    (proj / "fastq" / "s1_R2.fastq.gz").write_bytes(b"CCCC" * 10)
    (proj / "counts.txt").write_bytes(b"x")
    (drive / "unrelated.xlsx").write_bytes(b"not a workbook")  # must be ignored

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["RAW FILES"])
    ws.append(["file name", "file type", "file checksum"])
    ws.append(["s1_R1.fastq.gz", "fastq", None])
    ws.append(["s1_R2.fastq.gz", "fastq", None])
    ws.append([])
    ws.append(["PROCESSED DATA FILES"])
    ws.append(["file name", "file type", "file checksum"])
    ws.append(["counts.txt", "txt", None])
    wb.save(proj / "GEO_metadata.xlsx")

    wb2 = openpyxl.Workbook()
    wb2.active.append(["Sample", "Notes"])
    wb2.save(proj / "lab_notes.xlsx")  # xlsx without checksum columns: ignored
    return drive


def test_find_geo_workbooks(fake_drive):
    found = gc.find_geo_workbooks(fake_drive)
    assert [p.name for p in found] == ["GEO_metadata.xlsx"]


def test_auto_detects_drive_and_fills_workbook(fake_drive, monkeypatch):
    monkeypatch.setattr(gc, "candidate_drives", lambda: [fake_drive])
    summary = gc.auto(assume_yes=True, quiet=True)
    wb_path = fake_drive / "GEO_submission" / "GEO_metadata.xlsx"
    assert summary["workbook"] == wb_path
    # Default mode rebuilds the sheet: fastq files under RAW, everything else
    # (including lab_notes.xlsx, which may be processed data) under PROCESSED.
    assert summary["raw"] == ["s1_R1.fastq.gz", "s1_R2.fastq.gz"]
    assert summary["processed"] == ["counts.txt", "lab_notes.xlsx"]
    ws = openpyxl.load_workbook(wb_path).active
    assert ws["A3"].value == "s1_R1.fastq.gz" and ws["C3"].value == md5(b"AAAA" * 10)
    assert ws["A4"].value == "s1_R2.fastq.gz"
    assert ws["A8"].value == "counts.txt" and ws["C8"].value == md5(b"x")
    assert ws["A9"].value == "lab_notes.xlsx"

    # match mode only fills checksums next to names already present
    ws["A9"].value = None
    ws["C3"].value = ws["C4"].value = ws["C8"].value = None
    openpyxl.load_workbook(wb_path)  # sanity
    wb = openpyxl.load_workbook(wb_path)
    wb.active["C3"].value = None
    wb.save(wb_path)
    summary = gc.auto(assume_yes=True, quiet=True, mode="match")
    assert {n for _, _, n in summary["filled"]} == {"s1_R1.fastq.gz"}
    assert summary["missing"] == []
    assert (wb_path.parent / "checksums.csv").exists()
    assert (wb_path.parent / "checksums.md5").exists()
    assert (wb_path.parent / "GEO_metadata.bak.xlsx").exists()


def test_auto_no_drive(monkeypatch):
    monkeypatch.setattr(gc, "candidate_drives", lambda: [])
    with pytest.raises(SystemExit, match="No external drive"):
        gc.auto(assume_yes=True, quiet=True)


def test_auto_two_drives_picks_the_one_with_workbook(fake_drive, tmp_path, monkeypatch):
    other = tmp_path / "Volumes" / "BACKUP"
    other.mkdir()
    monkeypatch.setattr(gc, "candidate_drives", lambda: [other, fake_drive])
    summary = gc.auto(assume_yes=True, quiet=True)
    assert summary["workbook"].parent.parent == fake_drive


def test_auto_explicit_excel_skips_detection(fake_drive, monkeypatch):
    monkeypatch.setattr(gc, "candidate_drives", lambda: (_ for _ in ()).throw(AssertionError))
    wb_path = fake_drive / "GEO_submission" / "GEO_metadata.xlsx"
    rc = gc.main(["auto", "--excel", str(wb_path), "-y", "-q"])
    assert rc == 0


def test_candidate_drives_runs_on_this_platform():
    # Just make sure the platform-specific probing does not blow up.
    assert isinstance(gc.candidate_drives(), list)


# --------------------------------------------------------------------------- #
# populate mode, side-by-side layout as in the real "MD5 Checksums" tab
# --------------------------------------------------------------------------- #

@pytest.fixture
def side_by_side_workbook(tmp_path):
    """RAW FILES in A:B (header row 4), PROCESSED DATA FILES in F:G (header row 5),
    with stale entries that must be replaced."""
    wb = openpyxl.Workbook()
    wb.active.title = "Metadata"
    ws = wb.create_sheet("MD5 Checksums")
    ws["A3"] = "RAW FILES"
    ws["A4"], ws["B4"] = "file name", "file checksum"
    ws["A5"], ws["B5"] = "old_R1.fastq", "0" * 32
    ws["A6"], ws["B6"] = "old_R2.fastq", "1" * 32
    ws["F4"] = "PROCESSED DATA FILES"
    ws["F5"], ws["G5"] = "file name", "file checksum"
    ws["F6"], ws["G6"] = "old_matrix.h5", "2" * 32
    path = tmp_path / "Metadata for GEO submission.xlsx"
    wb.save(path)
    return path


def _records(names):
    return [gc.ChecksumRecord(n, md5(n.encode()), "md5", 1, 0.0, f"/drive/{n}") for n in names]


def test_populate_side_by_side(side_by_side_workbook):
    names = ["CG3_S1_L001_R1_001.fastq", "CG3_S1_L001_R2_001.fastq", "C4_S1_L002_R1_001.fastq",
             "CG3_filtered_feature_bc_matrix.h5", "CG3_scalefactors_json.json",
             "CG3_tissue_positions.csv", "CG3_tissue_hires_image.png"]
    summary = gc.populate_workbook(side_by_side_workbook, _records(names), quiet=True, backup=False)
    assert summary["sheet"] == "MD5 Checksums"
    assert summary["raw"] == ["C4_S1_L002_R1_001.fastq", "CG3_S1_L001_R1_001.fastq",
                              "CG3_S1_L001_R2_001.fastq"]
    assert len(summary["processed"]) == 4

    wb = openpyxl.load_workbook(side_by_side_workbook)
    assert wb.sheetnames == ["Metadata", "MD5 Checksums"]
    ws = wb["MD5 Checksums"]
    # headers and titles untouched
    assert ws["A3"].value == "RAW FILES" and ws["A4"].value == "file name"
    assert ws["F4"].value == "PROCESSED DATA FILES" and ws["G5"].value == "file checksum"
    # raw block rewritten from row 5
    assert ws["A5"].value == "C4_S1_L002_R1_001.fastq"
    assert ws["B5"].value == md5(b"C4_S1_L002_R1_001.fastq")
    assert ws["A7"].value == "CG3_S1_L001_R2_001.fastq"
    assert ws["A8"].value is None  # stale rows gone
    # processed block rewritten from row 6
    assert ws["F6"].value == "CG3_filtered_feature_bc_matrix.h5"
    assert ws["G6"].value == md5(b"CG3_filtered_feature_bc_matrix.h5")
    assert ws["F9"].value == "CG3_tissue_positions.csv"
    assert ws["F10"].value is None
    # nothing was written between the blocks
    assert all(ws.cell(row=r, column=c).value is None for r in range(5, 12) for c in (3, 4, 5))


def test_match_mode_side_by_side(side_by_side_workbook):
    records = _records(["old_R1.fastq", "old_R2.fastq", "old_matrix.h5"])
    summary = gc.fill_workbook(side_by_side_workbook, records, quiet=True, backup=False,
                               overwrite=True)
    assert {n for _, _, n in summary["filled"]} == {"old_R1.fastq", "old_R2.fastq", "old_matrix.h5"}
    assert summary["missing"] == []
    ws = openpyxl.load_workbook(side_by_side_workbook)["MD5 Checksums"]
    assert ws["B6"].value == md5(b"old_R2.fastq")
    assert ws["G6"].value == md5(b"old_matrix.h5")


def test_populate_creates_sheet_when_missing(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Metadata"
    path = tmp_path / "Metadata for GEO submission.xlsx"
    wb.save(path)
    gc.populate_workbook(path, _records(["a_R1.fastq.gz", "b.txt"]), quiet=True, backup=False)
    ws = openpyxl.load_workbook(path)["MD5 Checksums"]
    assert ws["A3"].value == "RAW FILES" and ws["A5"].value == "a_R1.fastq.gz"
    assert ws["F3"].value == "PROCESSED DATA FILES" and ws["F5"].value == "b.txt"


def test_populate_stacked_layout_grows_without_clobbering(geo_workbook):
    # Stacked GEO template: 3 raw slots, then PROCESSED block. Writing 5 raw files
    # must push the processed block down rather than overwrite it.
    names = [f"s{i}_R1.fastq.gz" for i in range(5)] + ["counts.txt"]
    gc.populate_workbook(geo_workbook, _records(names), sheet="Metadata", quiet=True, backup=False)
    ws = openpyxl.load_workbook(geo_workbook)["Metadata"]
    col_a = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert col_a.index("PROCESSED DATA FILES") > col_a.index("s4_R1.fastq.gz")
    assert col_a[col_a.index("PROCESSED DATA FILES") + 2] == "counts.txt"


def test_is_raw_file():
    assert gc.is_raw_file("x.fastq") and gc.is_raw_file("x.fq.gz") and gc.is_raw_file("x.BAM")
    assert not gc.is_raw_file("x.h5") and not gc.is_raw_file("x.json")
    assert not gc.is_raw_file("x.fastq.md5")


# --------------------------------------------------------------------------- #
# real-world drive quirks
# --------------------------------------------------------------------------- #

def test_folder_named_like_fastq_is_descended(tmp_path, capsys):
    root = tmp_path / "data"
    d = root / "H4_S1_L002_R1_001.fastq.gz"
    d.mkdir(parents=True)
    (d / "H4_S1_L002_R1_001.fastq.gz").write_bytes(b"reads")
    (root / "H4_scalefactors_json.json").write_bytes(b"{}")
    (root / "other_folder").mkdir()
    (root / "other_folder" / "ignored.txt").write_bytes(b"x")

    records = gc.scan(root, None, gc.DEFAULT_PATTERNS, "md5", recursive=False)
    assert sorted(r.file_name for r in records) == ["H4_S1_L002_R1_001.fastq.gz",
                                                    "H4_scalefactors_json.json"]
    err = capsys.readouterr().err
    assert "folders, not files" in err and "H4_S1_L002_R1_001.fastq.gz" in err


def test_save_falls_back_when_workbook_open_in_excel(side_by_side_workbook, monkeypatch):
    import openpyxl.workbook.workbook as wbmod
    real_save = wbmod.Workbook.save
    target = str(side_by_side_workbook)

    def locked_save(self, filename):
        if str(filename) == target:
            raise PermissionError(13, "Permission denied", target)
        return real_save(self, filename)

    monkeypatch.setattr(wbmod.Workbook, "save", locked_save)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    summary = gc.populate_workbook(side_by_side_workbook, _records(["a_R1.fastq"]),
                                   quiet=True, backup=False)
    alt = side_by_side_workbook.with_name("Metadata for GEO submission (with checksums).xlsx")
    assert summary["workbook"] == alt and alt.exists()
    assert openpyxl.load_workbook(alt)["MD5 Checksums"]["A5"].value == "a_R1.fastq"


def test_excel_lock_file_detection(side_by_side_workbook):
    assert gc.excel_lock_file(side_by_side_workbook) is None
    lock = side_by_side_workbook.with_name("~$" + side_by_side_workbook.name)
    lock.write_bytes(b"")
    assert gc.excel_lock_file(side_by_side_workbook) == lock
    # and the lock file is never treated as a workbook or hashed
    assert gc.find_geo_workbooks(side_by_side_workbook.parent) == [side_by_side_workbook]
    assert not gc._matches(lock.name, ["*"])


def test_auto_at_drive_root_skips_unrelated_folders(tmp_path, monkeypatch, capsys):
    drive = tmp_path / "E"
    (drive / "Old Backups").mkdir(parents=True)
    (drive / "Old Backups" / "photo.jpg").write_bytes(b"jpg")
    (drive / "H4_S1_L002_R1_001.fastq.gz").write_bytes(b"reads")
    (drive / "H4_tissue_positions.parquet").write_bytes(b"pq")
    wb = openpyxl.Workbook()
    wb.active.title = "Metadata"
    ws = wb.create_sheet("MD5 Checksums")
    ws["A3"] = "RAW FILES"; ws["A4"], ws["B4"] = "file name", "file checksum"
    ws["F4"] = "PROCESSED DATA FILES"; ws["F5"], ws["G5"] = "file name", "file checksum"
    wb.save(drive / "Metadata for GEO submission.xlsx")
    (drive / "~$Metadata for GEO submission.xlsx").write_bytes(b"")
    monkeypatch.setattr(gc, "candidate_drives", lambda: [drive])

    summary = gc.auto(assume_yes=True, quiet=True)
    assert summary["raw"] == ["H4_S1_L002_R1_001.fastq.gz"]
    assert summary["processed"] == ["H4_tissue_positions.parquet"]  # photo.jpg not hashed
    err = capsys.readouterr().err
    assert "Old Backups" in err and "--recursive" in err
    assert "open in Excel" in err

    summary = gc.auto(assume_yes=True, quiet=True, recursive=True)
    assert "photo.jpg" in summary["processed"]


def test_pick_workbook_prefers_geo_folder(tmp_path):
    a = tmp_path / "Old Backups" / "sample inventory.xlsx"
    b = tmp_path / "GEO submission_spatial" / "Metadata for GEO submission.xlsx"
    assert gc._pick_workbook([a, b]) == b
    c = tmp_path / "GEO submission_spatial" / "Metadata for GEO submission (with checksums).xlsx"
    with pytest.raises(SystemExit, match="more than one"):
        gc._pick_workbook([b, c])
