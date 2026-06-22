from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import _bootstrap  # noqa: F401


SPACE_GROUP_HEADER_RE = re.compile(r"International Tables for Crystallography .* Space group (\d+),")
ENTRY_RE = re.compile(r"\((\d+)\)\s*")
SETTING_RE = re.compile(r"^\s*(HEXAGONAL AXES|RHOMBOHEDRAL AXES|UNIQUE AXIS [ABC]|CELL CHOICE \d+)\s*$")
NO_RE = re.compile(r"^\s*No\.\s+(\d+)\b")
FRACTION_RE = re.compile(r"(?<=[\s(,;+−-])(\d{2})(?=[\s,;)])")
FRACTION_MAP = {
    "12": "1/2",
    "21": "1/2",
    "13": "1/3",
    "31": "1/3",
    "23": "2/3",
    "32": "2/3",
    "14": "1/4",
    "41": "1/4",
    "34": "3/4",
    "43": "3/4",
    "16": "1/6",
    "61": "1/6",
    "56": "5/6",
    "65": "5/6",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract ITC symmetry-operation notation blocks from Vol. A PDF.")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("docs/ITC vol.A.pdf"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("crystal_viewer/data/itc_operation_notations.json"),
    )
    parser.add_argument("--indent", type=int, default=None)
    args = parser.parse_args()

    text = pdftotext_layout(args.pdf)
    data = extract_operation_notations(text, source_pdf=str(args.pdf))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, indent=args.indent, separators=(",", ":") if args.indent is None else None)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    return 0


def pdftotext_layout(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def extract_operation_notations(text: str, *, source_pdf: str) -> dict:
    sections = space_group_sections(text)
    space_groups = {}
    for number, section in sections:
        descriptions = extract_descriptions(section)
        if descriptions:
            space_groups[str(number)] = {
                "number": number,
                "descriptions": descriptions,
            }
    return {
        "schema_version": 1,
        "source": "International Tables for Crystallography Vol. A PDF, Symmetry operations blocks",
        "source_pdf": source_pdf,
        "space_groups": space_groups,
    }


def space_group_sections(text: str) -> list[tuple[int, str]]:
    matches = list(SPACE_GROUP_HEADER_RE.finditer(text))
    sections: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((int(match.group(1)), text[start:end]))
    return sections


def extract_descriptions(section: str) -> list[dict]:
    lines = section.splitlines()
    descriptions = []
    pending_setting = ""
    current_number = None
    i = 0
    while i < len(lines):
        setting_match = SETTING_RE.match(lines[i])
        if setting_match is not None:
            pending_setting = normalize_space(setting_match.group(1).title())
        no_match = NO_RE.match(lines[i])
        if no_match is not None:
            current_number = int(no_match.group(1))
        if lines[i].strip() != "Symmetry operations":
            i += 1
            continue

        start = i + 1
        end = start
        while end < len(lines):
            stripped = lines[end].strip()
            if stripped.startswith("Copyright"):
                break
            if stripped.startswith("Generators selected"):
                break
            if stripped.startswith("Positions"):
                break
            if stripped.startswith("Maximal non-isomorphic subgroups"):
                break
            if SPACE_GROUP_HEADER_RE.search(lines[end]):
                break
            end += 1

        block_lines = lines[start:end]
        sets = parse_operation_block(block_lines)
        if sets:
            descriptions.append(
                {
                    "setting": pending_setting,
                    "number": current_number,
                    "sets": sets,
                    "operations": flatten_sets(sets),
                }
            )
        i = end + 1
    return descriptions


def parse_operation_block(lines: list[str]) -> list[dict]:
    sets = []
    current_set = {"label": "", "entries": []}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("(given on page") or stripped.startswith("(from page"):
            continue
        if stripped.startswith("For ") and " set" in stripped:
            if current_set["entries"]:
                sets.append(current_set)
            current_set = {"label": normalize_space(stripped), "entries": []}
            continue
        append_entries(current_set["entries"], line)
    if current_set["entries"]:
        sets.append(current_set)
    return sets


def append_entries(entries: list[dict], line: str) -> None:
    matches = list(ENTRY_RE.finditer(line))
    if not matches:
        return
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        notation = normalize_notation(line[start:end])
        if notation:
            entries.append({"operation_number": int(match.group(1)), "notation": notation})


def flatten_sets(sets: list[dict]) -> list[dict]:
    operations = []
    for operation_set in sets:
        for entry in operation_set["entries"]:
            operations.append(
                {
                    "linear_index": len(operations),
                    "set": operation_set["label"],
                    "operation_number": entry["operation_number"],
                    "notation": entry["notation"],
                }
            )
    return operations


def normalize_notation(text: str) -> str:
    text = normalize_space(text)
    text = text.replace("− ", "−")
    text = text.replace(" ̄", "̄")
    text = normalize_fractions(text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.strip()


def normalize_fractions(text: str) -> str:
    return FRACTION_RE.sub(lambda match: FRACTION_MAP.get(match.group(1), match.group(1)), text)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    raise SystemExit(main())
