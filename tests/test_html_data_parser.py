import subprocess
import sys
from pathlib import Path


def test_parser_finds_mm_yy_and_writes_files(tmp_path: Path):
    html_dir = tmp_path / "html"
    html_dir.mkdir()

    (html_dir / "sample.html").write_text(
        """
        <html>
          <body>
            expiry 08/29 and full 12/2027.
            <script>var a = '11/99';</script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"

    cmd = [
        sys.executable,
        "html_data_parser.py",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--only-text",
        "--no-prompt",
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)

    assert "Файлов проверено: 1" in completed.stdout
    csv_path = out_dir / "matches.csv"
    uniq_path = out_dir / "unique_values.txt"
    combo_path = out_dir / "cards_mm_yy_cvc.txt"
    assert csv_path.exists()
    assert uniq_path.exists()
    assert combo_path.exists()

    csv_content = csv_path.read_text(encoding="utf-8")
    assert "08/29" in csv_content
    assert "12/2027" in csv_content
    assert "11/99" not in csv_content


def test_parser_by_message_processes_entries_sequentially_and_exports_combo(tmp_path: Path):
    html_dir = tmp_path / "html"
    html_dir.mkdir()

    (html_dir / "chat.html").write_text(
        """
        <html><body>
          <div>status: new info</div>
          <div>number: 4111 1111 1111 1111</div>
          <div>mm/yy: 10/27</div>
          <div>cvc: 123</div>

          <div>hello, next message without sensitive data</div>
        </body></html>
        """,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--by-message",
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    csv_content = (out_dir / "matches.csv").read_text(encoding="utf-8")
    assert "message" in csv_content
    assert "10/27" in csv_content

    combos = (out_dir / "cards_mm_yy_cvc.txt").read_text(encoding="utf-8")
    assert "4111111111111111|10/27|123" in combos


def test_parser_uses_current_directory_when_input_dir_omitted(tmp_path: Path):
    (tmp_path / "sample.html").write_text("<html><body>expiry 09/29</body></html>", encoding="utf-8")
    out_dir = tmp_path / "out"
    script_path = Path(__file__).resolve().parents[1] / "html_data_parser.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--out-dir",
        str(out_dir),
        "--only-text",
        "--no-prompt",
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert "Файлов проверено: 1" in completed.stdout
    csv_content = (out_dir / "matches.csv").read_text(encoding="utf-8")
    assert "09/29" in csv_content


def test_parser_prompts_for_input_dir_and_combo_file(tmp_path: Path):
    html_dir = tmp_path / "html_prompt"
    html_dir.mkdir()
    (html_dir / "chat.html").write_text(
        "<html><body>number: 4111 1111 1111 1111 mm/yy: 10/27 cvc: 123</body></html>",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    script_path = Path(__file__).resolve().parents[1] / "html_data_parser.py"
    combo_abs = tmp_path / "custom_output.txt"

    cmd = [
        sys.executable,
        str(script_path),
        "--out-dir",
        str(out_dir),
        "--only-text",
    ]
    answers = f"{html_dir}\n{combo_abs}\n"
    subprocess.run(cmd, check=True, capture_output=True, text=True, input=answers)

    assert combo_abs.exists()
    assert "4111111111111111|10/27|123" in combo_abs.read_text(encoding="utf-8")


def test_combo_uses_only_labeled_number_mm_yy_cvc(tmp_path: Path):
    html_dir = tmp_path / "html_labeled"
    html_dir.mkdir()
    (html_dir / "mixed.html").write_text(
        """
        <html><body>
          <div>some random 4111 1111 1111 1111 and 12/29 and 777 should be ignored</div>

          <div>number: 5264 3999 3325 4753</div>
          <div>mm/yy: 11/26</div>
          <div>cvc: 123</div>
        </body></html>
        """,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    combos = (out_dir / "cards_mm_yy_cvc.txt").read_text(encoding="utf-8").strip().splitlines()
    assert combos == ["5264399933254753|11/26|123"]


def test_deduplicates_same_combo_and_rows(tmp_path: Path):
    html_dir = tmp_path / "html_dups"
    html_dir.mkdir()
    duplicate_message = """
    <div>number: 5264 3999 3325 4753</div>
    <div>mm/yy: 11/26</div>
    <div>cvc: 123</div>
    """
    (html_dir / "a.html").write_text(f"<html><body>{duplicate_message}{duplicate_message}</body></html>", encoding="utf-8")

    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    combos = (out_dir / "cards_mm_yy_cvc.txt").read_text(encoding="utf-8").strip().splitlines()
    assert combos == ["5264399933254753|11/26|123"]

    import csv

    with (out_dir / "matches.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    mm_rows = [
        row for row in rows if row["file"] == str(html_dir / "a.html") and row["scope"] == "text" and row["pattern"] == "mm_yy" and row["value"] == "11/26"
    ]
    assert len(mm_rows) == 1


def test_combo_does_not_cross_combine_unrelated_cvc_values(tmp_path: Path):
    html_dir = tmp_path / "html_no_cross"
    html_dir.mkdir()
    (html_dir / "mixed.html").write_text(
        """
        <html><body>
          <div>number: 6666 6666 6666 6666 mm/yy: 11/11 cvc: 111</div>
          <div>number: 6666 6666 6666 6666 mm/yy: 11/11 cvc: 112</div>
          <div>cvc: 999</div>
          <div>mm/yy: 12/12</div>
        </body></html>
        """,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    combos = (out_dir / "cards_mm_yy_cvc.txt").read_text(encoding="utf-8").strip().splitlines()
    assert combos == [
        "6666666666666666|11/11|111",
        "6666666666666666|11/11|112",
    ]


def test_no_stdin_still_creates_default_combo_file(tmp_path: Path):
    html_dir = tmp_path / "html_noninteractive"
    html_dir.mkdir()
    (html_dir / "chat.html").write_text(
        "<html><body>number: 4111 1111 1111 1111 mm/yy: 10/27 cvc: 123</body></html>",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    script_path = Path(__file__).resolve().parents[1] / "html_data_parser.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--only-text",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, input="")

    combo_path = out_dir / "cards_mm_yy_cvc.txt"
    assert combo_path.exists()
    assert "4111111111111111|10/27|123" in combo_path.read_text(encoding="utf-8")


def test_include_raw_adds_raw_scope_matches(tmp_path: Path):
    html_dir = tmp_path / "html_raw"
    html_dir.mkdir()
    (html_dir / "a.html").write_text("<html><body>10/27</body></html>", encoding="utf-8")
    out_dir = tmp_path / "out"

    base_cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--no-prompt",
    ]
    subprocess.run(base_cmd, check=True, capture_output=True, text=True)
    csv_default = (out_dir / "matches.csv").read_text(encoding="utf-8")
    assert ",text," in csv_default
    assert ",raw," not in csv_default

    subprocess.run(base_cmd + ["--include-raw"], check=True, capture_output=True, text=True)
    csv_raw = (out_dir / "matches.csv").read_text(encoding="utf-8")
    assert ",raw," in csv_raw


def test_always_writes_combo_into_out_dir_even_with_custom_combo_path(tmp_path: Path):
    html_dir = tmp_path / "html_outdir_combo"
    html_dir.mkdir()
    (html_dir / "chat.html").write_text(
        "<html><body>number: 4111 1111 1111 1111 mm/yy: 10/27 cvc: 123</body></html>",
        encoding="utf-8",
    )

    out_dir = tmp_path / "parsed_output"
    custom_combo = tmp_path / "another" / "custom.txt"

    cmd = [
        sys.executable,
        "html_data_parser.py",
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(out_dir),
        "--combo-file",
        str(custom_combo),
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    expected = "4111111111111111|10/27|123"
    assert custom_combo.exists()
    assert expected in custom_combo.read_text(encoding="utf-8")

    out_dir_default_combo = out_dir / "cards_mm_yy_cvc.txt"
    assert out_dir_default_combo.exists()
    assert expected in out_dir_default_combo.read_text(encoding="utf-8")


def test_always_writes_combo_into_fixed_parsed_output_dir(tmp_path: Path):
    html_dir = tmp_path / "html_fixed_parsed"
    html_dir.mkdir()
    (html_dir / "chat.html").write_text(
        "<html><body>number: 4111 1111 1111 1111 mm/yy: 10/27 cvc: 123</body></html>",
        encoding="utf-8",
    )

    custom_out = tmp_path / "custom_out"
    script_path = Path(__file__).resolve().parents[1] / "html_data_parser.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--input-dir",
        str(html_dir),
        "--out-dir",
        str(custom_out),
        "--only-text",
        "--no-prompt",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=tmp_path)

    fixed_combo = tmp_path / "parsed_output" / "cards_mm_yy_cvc.txt"
    assert fixed_combo.exists()
    assert "4111111111111111|10/27|123" in fixed_combo.read_text(encoding="utf-8")
