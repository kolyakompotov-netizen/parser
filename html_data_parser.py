#!/usr/bin/env python3
"""Parser for extracting date-like and custom patterns from HTML files."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable

DEFAULT_PATTERNS: dict[str, str] = {
    "mm_yy": r"\b(0[1-9]|1[0-2])\/\d{2}\b",
    "mm_yyyy": r"\b(0[1-9]|1[0-2])\/\d{4}\b",
    "dd_mm_yy": r"\b(0[1-9]|[12]\d|3[01])[.\/-](0[1-9]|1[0-2])[.\/-]\d{2}\b",
    "dd_mm_yyyy": r"\b(0[1-9]|[12]\d|3[01])[.\/-](0[1-9]|1[0-2])[.\/-]\d{4}\b",
}

SCRIPT_STYLE_RE = re.compile(r"<(script|style)(.|\n)*?</\1>", flags=re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--(.|\n)*?-->")
TAG_RE = re.compile(r"<[^>]+>")

LABEL_TRANSLATION = str.maketrans({
    "ɴ": "n",
    "ᴜ": "u",
    "ᴍ": "m",
    "ʙ": "b",
    "ᴇ": "e",
    "ʀ": "r",
    "ʏ": "y",
    "ᴄ": "c",
    "ᴠ": "v",
})

NUMBER_LABEL_RE = re.compile(r"(?:^|\b)number\s*:\s*([0-9][0-9 \-]{14,25}[0-9])", flags=re.IGNORECASE)
MM_YY_LABEL_RE = re.compile(r"(?:^|\b)mm/yy\s*:\s*((?:0[1-9]|1[0-2])/[0-9]{2})", flags=re.IGNORECASE)
CVC_LABEL_RE = re.compile(r"(?:^|\b)cvc\s*:\s*([0-9]{3,4})", flags=re.IGNORECASE)
LABEL_TOKEN_RE = re.compile(
    r"(?P<label>number|mm/yy|cvc)\s*:\s*(?P<value>(?:[0-9][0-9 \-]{14,25}[0-9])|(?:0[1-9]|1[0-2])/[0-9]{2}|[0-9]{3,4})",
    flags=re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ищет mm/yy и другие шаблоны в HTML файлах и сохраняет результаты."
    )
    parser.add_argument("input_dir", nargs="?", default=None, type=Path, help="Папка с HTML файлами")
    parser.add_argument("--input-dir", dest="input_dir_opt", type=Path, help="Папка с HTML файлами (явный параметр)")
    parser.add_argument("--glob", default="*.htm*", help="Маска файлов (по умолчанию: *.htm*)")
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        metavar="NAME=REGEX",
        help="Добавить кастомный шаблон, например card=\\b\\d{16}\\b",
    )
    parser.add_argument("--only-text", action="store_true", help="Совместимость: искать только в видимом тексте (теперь режим по умолчанию)")
    parser.add_argument("--include-raw", action="store_true", help="Искать и в raw HTML, и в text (может давать больше совпадений)")
    parser.add_argument("--by-message", action="store_true", help="Разбивать текст на отдельные сообщения и проверять их по очереди")
    parser.add_argument("--out-dir", type=Path, default=Path("./parsed_output"), help="Папка для результатов")
    parser.add_argument("--combo-file", default=None, help="Имя TXT файла для формата xxxxxxxxxxxxxxxx|xx/xx|xxx")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Отключить вопросы в консоли и использовать только переданные аргументы",
    )
    return parser.parse_args()


def prompt_text(question: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{question}{suffix}: ").strip()
    except EOFError:
        return default or ""
    if value:
        return value
    return default or ""


def resolve_input_dir(args: argparse.Namespace) -> Path:
    if args.input_dir_opt is not None:
        return args.input_dir_opt
    if args.input_dir is not None:
        return args.input_dir
    if args.no_prompt:
        return Path(".")

    while True:
        raw = prompt_text("Укажи путь к папке с HTML файлами", ".")
        candidate = Path(raw)
        if candidate.exists() and candidate.is_dir():
            return candidate
        print(f"Папка не найдена: {candidate}. Попробуй снова.")


def resolve_combo_path(args: argparse.Namespace) -> Path:
    if args.combo_file:
        combo_name = args.combo_file
    elif args.no_prompt:
        combo_name = "cards_mm_yy_cvc.txt"
    else:
        combo_name = prompt_text(
            "Как назвать TXT файл вывода (формат xxxxxxxxxxxxxxxx|xx/xx|xxx)",
            "cards_mm_yy_cvc.txt",
        )

    combo_path = Path(combo_name)
    if combo_path.is_absolute() or combo_path.parent != Path("."):
        combo_path.parent.mkdir(parents=True, exist_ok=True)
        return combo_path

    args.out_dir.mkdir(parents=True, exist_ok=True)
    return args.out_dir / combo_name


def default_combo_in_out_dir(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "cards_mm_yy_cvc.txt"


def fixed_parsed_output_combo_path() -> Path:
    parsed_output_dir = Path("parsed_output")
    parsed_output_dir.mkdir(parents=True, exist_ok=True)
    return parsed_output_dir / "cards_mm_yy_cvc.txt"


def parse_custom_patterns(items: Iterable[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Неверный формат --pattern: '{item}'. Ожидается NAME=REGEX")
        name, regex = item.split("=", 1)
        name = name.strip()
        regex = regex.strip()
        if not name or not regex:
            raise ValueError(f"Неверный формат --pattern: '{item}'. NAME и REGEX обязательны")
        parsed[name] = regex
    return parsed


def read_html(path: Path) -> str:
    encodings = ("utf-8", "cp1251", "latin-1")
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def html_to_text(html: str) -> str:
    no_script = SCRIPT_STYLE_RE.sub(" ", html)
    no_comments = COMMENT_RE.sub(" ", no_script)
    no_tags = TAG_RE.sub(" ", no_comments)
    return re.sub(r"\s+", " ", no_tags).strip()


def split_messages(html: str) -> list[str]:
    chunks = [x for x in re.split(r"\n\s*\n+", html) if x.strip()]
    messages: list[str] = []
    for chunk in chunks:
        text = html_to_text(chunk)
        if text:
            messages.append(text)
    return messages


def find_matches(content: str, patterns: dict[str, str]) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for name, regex in patterns.items():
        for match in re.finditer(regex, content):
            matches.append((name, match.group(0)))
    return matches


def collect_html_files(root: Path, glob_mask: str) -> list[Path]:
    return sorted([p for p in root.rglob(glob_mask) if p.is_file()])


def normalize_card(card: str) -> str:
    return re.sub(r"\D", "", card)


def normalize_label_text(content: str) -> str:
    return content.translate(LABEL_TRANSLATION)


def build_combo_lines(content: str) -> list[str]:
    normalized = normalize_label_text(content)
    tokens = list(LABEL_TOKEN_RE.finditer(normalized))

    combos: list[str] = []
    current: dict[str, str] = {}

    for match in tokens:
        label = match.group("label").lower()
        value = match.group("value").strip()

        if label == "number":
            card = normalize_card(value)
            if len(card) != 16:
                current = {}
                continue
            current = {"number": card}
            continue

        if label == "mm/yy":
            if "number" not in current:
                continue
            current["mm/yy"] = value
            continue

        if label == "cvc":
            if "number" not in current or "mm/yy" not in current:
                continue
            if len(value) not in (3, 4):
                continue
            current["cvc"] = value
            combos.append(f"{current['number']}|{current['mm/yy']}|{current['cvc']}")
            current = {}

    return combos




def deduplicate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        key = (row["file"], row["scope"], row["message_id"], row["pattern"], row["value"])
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def deduplicate_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result

def main() -> int:
    args = parse_args()
    input_dir = resolve_input_dir(args)
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Папка не найдена: {input_dir}")

    patterns = dict(DEFAULT_PATTERNS)
    patterns.update(parse_custom_patterns(args.pattern))

    files = collect_html_files(input_dir, args.glob)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.out_dir / "matches.csv"
    unique_path = args.out_dir / "unique_values.txt"
    combo_path = resolve_combo_path(args)

    rows: list[dict[str, str]] = []
    unique_values: set[str] = set()
    combo_lines: list[str] = []

    for file_path in files:
        html = read_html(file_path)

        if args.by_message:
            for idx, message in enumerate(split_messages(html), start=1):
                block_matches = find_matches(message, patterns)
                for pattern_name, value in block_matches:
                    rows.append(
                        {
                            "file": str(file_path),
                            "scope": "message",
                            "message_id": str(idx),
                            "pattern": pattern_name,
                            "value": value,
                        }
                    )
                    unique_values.add(value)
                combo_lines.extend(build_combo_lines(message))
            continue

        scopes = [("raw", html), ("text", html_to_text(html))] if args.include_raw else [("text", html_to_text(html))]

        for scope_name, scope_content in scopes:
            block_matches = find_matches(scope_content, patterns)
            for pattern_name, value in block_matches:
                rows.append(
                    {
                        "file": str(file_path),
                        "scope": scope_name,
                        "message_id": "",
                        "pattern": pattern_name,
                        "value": value,
                    }
                )
                unique_values.add(value)
            combo_lines.extend(build_combo_lines(scope_content))

    rows = deduplicate_rows(rows)
    combo_lines = deduplicate_lines(combo_lines)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["file", "scope", "message_id", "pattern", "value"]
        )
        writer.writeheader()
        writer.writerows(rows)

    unique_path.write_text("\n".join(sorted(unique_values)), encoding="utf-8")
    combo_path.parent.mkdir(parents=True, exist_ok=True)
    combo_content = "\n".join(combo_lines)
    combo_path.write_text(combo_content, encoding="utf-8")

    # Всегда дублируем стандартный output-файл в out_dir
    out_dir_combo_path = default_combo_in_out_dir(args.out_dir)
    out_dir_combo_path.write_text(combo_content, encoding="utf-8")

    # И дополнительно всегда пишем в фиксированную папку ./parsed_output
    parsed_output_combo_path = fixed_parsed_output_combo_path()
    parsed_output_combo_path.write_text(combo_content, encoding="utf-8")

    print(f"Папка: {input_dir}")
    print(f"Файлов проверено: {len(files)}")
    print(f"Совпадений найдено: {len(rows)}")
    print(f"CSV: {csv_path}")
    print(f"Unique: {unique_path}")
    print(f"Combos: {combo_path}")
    print(f"Combos (out-dir default): {out_dir_combo_path}")
    print(f"Combos (fixed parsed_output): {parsed_output_combo_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
