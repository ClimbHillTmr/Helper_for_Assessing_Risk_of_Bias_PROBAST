#!/usr/bin/env python3
"""Pre-submission readiness verifier and atomic author-metadata updater for JOSS.

Pure Python 3.10+ standard library only; writes zero bytecode files.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any

PLACEHOLDER_AUTHOR = "[AUTHOR_FULL_NAME]"
PLACEHOLDER_ORCID = "0000-0000-0000-0000"
PLACEHOLDER_AFFIL = "[AUTHOR_AFFILIATION]"
LEGACY_CONTRIBUTORS = "Medical Research Harness Contributors"
DEFAULT_GITHUB_REPO = "ClimbHillTmr/Helper_for_Assessing_Risk_of_Bias_PROBAST"

REQUIRED_HEADINGS = [
    "# Summary",
    "# Statement of Need",
    "# State of the Field",
    "# Software Design",
    "# AI Usage Disclosure",
    "# Acknowledgements",
    "# References",
]

REQUIRED_GOVERNANCE_FILES = [
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "CITATION.cff",
    "pyproject.toml",
    ".github/workflows/validate.yml",
]

BANNED_SUBSTRINGS = (
    "JAMIA_OPEN_EXPANSION",
    "外部人类专家",
    "human-expert",
)

DEV_VERSION_SUBSTRINGS = (
    "0.2.0.dev0",
    "0.2.0-dev",
)


def normalize_orcid(raw: str) -> str:
    val = raw.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/"):
        if val.startswith(prefix):
            val = val[len(prefix) :]
            break
    return val.upper()


def compute_orcid_check_digit(base15: str) -> str:
    total = 0
    for ch in base15:
        total = (total + int(ch)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    return "X" if result == 10 else str(result)


def validate_orcid(orcid: str) -> tuple[bool, str]:
    norm = normalize_orcid(orcid)
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", norm):
        return False, f"ORCID '{orcid}' does not match NNNN-NNNN-NNNN-NNNX format"
    if norm == PLACEHOLDER_ORCID:
        return False, f"ORCID is still placeholder '{PLACEHOLDER_ORCID}'"
    digits = norm.replace("-", "")
    expected = compute_orcid_check_digit(digits[:15])
    if digits[15] != expected:
        return (
            False,
            f"ORCID '{norm}' failed ISO 7064 Mod 11-2 checksum (expected trailing '{expected}')",
        )
    return True, norm


def _unquote(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        inner = val[1:-1]
        if val[0] == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    return val


def parse_joss_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse JOSS YAML frontmatter using pure Python stdlib."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing opening '---' YAML frontmatter delimiter on line 1")
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in ("---", "..."):
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("Missing closing '---' YAML frontmatter delimiter")

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])

    data: dict[str, Any] = {}
    current_key: str | None = None
    current_item: dict[str, Any] | None = None

    for lineno, raw_line in enumerate(fm_lines, start=2):
        stripped_comment = re.sub(r"\s+#.*$", "", raw_line).rstrip()
        if not stripped_comment.strip():
            continue
        indent = len(stripped_comment) - len(stripped_comment.lstrip(" "))
        content = stripped_comment.strip()

        if indent == 0:
            current_item = None
            if ":" not in content:
                raise ValueError(f"Invalid YAML line {lineno}: {raw_line!r}")
            key, rest = content.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if rest:
                data[key] = _unquote(rest)
                current_key = None
            else:
                data[key] = []
                current_key = key
        elif content.startswith("- "):
            if current_key is None or not isinstance(data.get(current_key), list):
                raise ValueError(f"Unexpected YAML list item on line {lineno}: {raw_line!r}")
            item_rest = content[2:].strip()
            if ":" in item_rest and not (
                item_rest[0] in ("'", '"') and item_rest[-1] == item_rest[0]
            ):
                k, v = item_rest.split(":", 1)
                current_item = {k.strip(): _unquote(v.strip())}
                data[current_key].append(current_item)
            else:
                current_item = None
                data[current_key].append(_unquote(item_rest))
        else:
            if current_item is None or ":" not in content:
                raise ValueError(f"Invalid nested YAML mapping on line {lineno}: {raw_line!r}")
            k, v = content.split(":", 1)
            current_item[k.strip()] = _unquote(v.strip())

    return data, body


def parse_bibtex_entries(bib_text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    cleaned_lines = [
        line for line in bib_text.splitlines() if not line.lstrip().startswith("%")
    ]
    cleaned = "\n".join(cleaned_lines)

    header_pat = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,")
    pos = 0
    while True:
        match = header_pat.search(cleaned, pos)
        if not match:
            break
        entry_type = match.group(1).lower()
        citekey = match.group(2).strip()
        if citekey in entries:
            raise ValueError(f"Duplicate BibTeX key '{citekey}' in paper.bib")
        brace_depth = 1
        idx = match.end()
        while idx < len(cleaned) and brace_depth > 0:
            if cleaned[idx] == "{":
                brace_depth += 1
            elif cleaned[idx] == "}":
                brace_depth -= 1
            idx += 1
        if brace_depth != 0:
            raise ValueError(f"Unbalanced braces in BibTeX entry '{citekey}'")
        body = cleaned[match.end() : idx - 1]
        fields: dict[str, str] = {"_type": entry_type}
        for fmatch in re.finditer(r"([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*", body):
            fname = fmatch.group(1).lower()
            vstart = fmatch.end()
            while vstart < len(body) and body[vstart].isspace():
                vstart += 1
            if vstart >= len(body):
                continue
            if body[vstart] == "{":
                d = 1
                j = vstart + 1
                while j < len(body) and d > 0:
                    if body[j] == "{":
                        d += 1
                    elif body[j] == "}":
                        d -= 1
                    j += 1
                fval = body[vstart + 1 : j - 1].strip()
            elif body[vstart] == '"':
                j = vstart + 1
                while j < len(body) and body[j] != '"':
                    if body[j] == "\\":
                        j += 1
                    j += 1
                fval = body[vstart + 1 : j].strip()
            else:
                j = vstart
                while j < len(body) and body[j] not in (",\n\r"):
                    j += 1
                fval = body[vstart:j].strip()
            fields[fname] = fval
        entries[citekey] = fields
        pos = idx
    return entries


def extract_markdown_citations(body_text: str) -> list[str]:
    # Remove fenced and inline code blocks before extracting citations
    scrubbed = re.sub(r"```.*?```", " ", body_text, flags=re.DOTALL)
    scrubbed = re.sub(r"`[^`]*`", " ", scrubbed)
    cited: list[str] = []
    for bracket in re.findall(r"\[([^\[\]]*@[^\[\]]+)\]", scrubbed):
        for key in re.findall(r"@([A-Za-z0-9_:-]+)", bracket):
            if key not in cited:
                cited.append(key)
    return cited


def read_png_dimensions(png_path: Path) -> tuple[int, int]:
    with png_path.open("rb") as fh:
        header = fh.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{png_path} does not have a valid 8-byte PNG signature")
    if header[12:16] != b"IHDR":
        raise ValueError(f"{png_path} is missing expected PNG IHDR chunk")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def atomic_write_text(target: Path, new_content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_content)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _escape_dq(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def apply_metadata_updates(
    repo_root: Path,
    author: str | None,
    orcid: str | None,
    affiliation: str | None,
    github_repo: str | None,
) -> list[str]:
    updates_log: list[str] = []
    norm_orcid: str | None = None

    if author is not None:
        author = author.strip()
        if not author or author == PLACEHOLDER_AUTHOR:
            raise ValueError("--set-author requires a real non-placeholder author name")
    if orcid is not None:
        ok, res = validate_orcid(orcid)
        if not ok:
            raise ValueError(res)
        norm_orcid = res
    if affiliation is not None:
        affiliation = affiliation.strip()
        if not affiliation or affiliation == PLACEHOLDER_AFFIL:
            raise ValueError("--set-affiliation requires a real non-placeholder affiliation")
    if github_repo is not None:
        github_repo = github_repo.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repo):
            raise ValueError(
                f"--set-github-repo '{github_repo}' must match OWNER/REPO format"
            )

    targets = [
        repo_root / "Paper" / "joss" / "paper.md",
        repo_root / "CITATION.cff",
        repo_root / "pyproject.toml",
    ]
    staged: dict[Path, str] = {}

    for path in targets:
        if not path.is_file():
            raise FileNotFoundError(f"Required metadata target missing: {path}")
        content = path.read_text(encoding="utf-8")
        orig = content

        if author is not None:
            esc = _escape_dq(author)
            if PLACEHOLDER_AUTHOR in content:
                content = content.replace(PLACEHOLDER_AUTHOR, esc)
            elif LEGACY_CONTRIBUTORS in content and path.name in (
                "CITATION.cff",
                "pyproject.toml",
            ):
                content = content.replace(LEGACY_CONTRIBUTORS, esc)

        if norm_orcid is not None:
            if PLACEHOLDER_ORCID in content:
                content = content.replace(PLACEHOLDER_ORCID, norm_orcid)
            elif path.name == "CITATION.cff" and "orcid:" not in content:
                content = re.sub(
                    r"(authors:\s*\n\s*-\s*[^\n]+\n)",
                    rf'\1    orcid: "https://orcid.org/{norm_orcid}"\n',
                    content,
                    count=1,
                )

        if affiliation is not None:
            esc_aff = _escape_dq(affiliation)
            if PLACEHOLDER_AFFIL in content:
                content = content.replace(PLACEHOLDER_AFFIL, esc_aff)
            elif path.name == "CITATION.cff" and "affiliation:" not in content:
                content = re.sub(
                    r"(authors:\s*\n\s*-\s*[^\n]+\n)",
                    rf'\1    affiliation: "{esc_aff}"\n',
                    content,
                    count=1,
                )

        if github_repo is not None:
            content = content.replace("[GITHUB_OWNER]/[GITHUB_REPO]", github_repo)
            content = content.replace(DEFAULT_GITHUB_REPO, github_repo)

        if content != orig:
            staged[path] = content
            updates_log.append(str(path.relative_to(repo_root)))

    for path, new_text in staged.items():
        atomic_write_text(path, new_text)

    return updates_log


def read_pyproject_version(pyproject_path: Path) -> str | None:
    raw = pyproject_path.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore[import-not-found]

        parsed = tomllib.loads(raw)
        proj = parsed.get("project", {})
        ver = proj.get("version")
        return str(ver) if ver is not None else None
    except ModuleNotFoundError:
        m = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']', raw)
        return m.group(1) if m else None


def read_cff_version(cff_path: Path) -> str | None:
    raw = cff_path.read_text(encoding="utf-8")
    m = re.search(r'(?m)^version:\s*["\']?([^"\'\n#]+)["\']?', raw)
    return m.group(1).strip() if m else None


def run_checks(
    repo_root: Path,
    allow_placeholders: bool,
    skip_packaging_version: bool,
) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []

    paper_path = repo_root / "Paper" / "joss" / "paper.md"
    bib_path = repo_root / "Paper" / "joss" / "paper.bib"

    if not paper_path.is_file():
        return passed, [f"[1/8] Missing JOSS manuscript: {paper_path}"]
    if not bib_path.is_file():
        return passed, [f"[5/8] Missing JOSS bibliography: {bib_path}"]

    paper_text = paper_path.read_text(encoding="utf-8")

    # Check 1: YAML frontmatter
    fm: dict[str, Any] = {}
    body_text = ""
    try:
        fm, body_text = parse_joss_frontmatter(paper_text)
        missing_keys = [
            k
            for k in ("title", "tags", "authors", "affiliations", "date", "bibliography")
            if k not in fm or not fm[k]
        ]
        if missing_keys:
            failed.append(f"[1/8] YAML frontmatter missing keys: {missing_keys}")
        else:
            affil_indices = {
                str(a.get("index", ""))
                for a in fm["affiliations"]
                if isinstance(a, dict) and a.get("name")
            }
            bad_authors = []
            for idx, auth in enumerate(fm["authors"], start=1):
                if not isinstance(auth, dict):
                    bad_authors.append(f"author #{idx} is not a mapping")
                    continue
                for req in ("name", "orcid", "affiliation"):
                    if not auth.get(req):
                        bad_authors.append(f"author #{idx} missing '{req}'")
                aff_ref = str(auth.get("affiliation", ""))
                for part in [p.strip() for p in aff_ref.split(",") if p.strip()]:
                    if part not in affil_indices:
                        bad_authors.append(
                            f"author #{idx} references undefined affiliation index '{part}'"
                        )
            if fm.get("bibliography") != "paper.bib":
                bad_authors.append(
                    f"bibliography must be 'paper.bib' (got {fm.get('bibliography')!r})"
                )
            if bad_authors:
                failed.append(f"[1/8] YAML frontmatter schema errors: {'; '.join(bad_authors)}")
            else:
                passed.append(
                    f"[1/8] YAML frontmatter valid ({len(fm['authors'])} author(s), "
                    f"{len(fm['tags'])} tags, bibliography={fm['bibliography']})"
                )
    except Exception as exc:
        failed.append(f"[1/8] YAML frontmatter parse error: {exc}")

    # Check 2: Word count within [250, 1000]
    total_words = len(paper_text.split())
    body_words = len(body_text.split()) if body_text else 0
    if 250 <= total_words <= 1000 and 250 <= body_words <= 1000:
        passed.append(
            f"[2/8] Word count within JOSS [250, 1000] bounds: "
            f"total={total_words} words, body={body_words} words"
        )
    else:
        failed.append(
            f"[2/8] Word count out of [250, 1000] bounds: "
            f"total={total_words} words, body={body_words} words"
        )

    # Check 3: Required JOSS headings
    h1_lines = [line.strip() for line in body_text.splitlines() if line.startswith("# ")]
    missing_h1 = [h for h in REQUIRED_HEADINGS if h not in h1_lines]
    if missing_h1:
        failed.append(f"[3/8] Missing required JOSS H1 headings: {missing_h1}")
    else:
        positions = [h1_lines.index(h) for h in REQUIRED_HEADINGS]
        if positions != sorted(positions):
            failed.append(f"[3/8] Required JOSS headings out of canonical order: {h1_lines}")
        else:
            passed.append(f"[3/8] All {len(REQUIRED_HEADINGS)} required JOSS headings present in order")

    # Check 4: Referenced figure exists, valid PNG, >= 1800 px wide
    img_refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body_text)
    expected_rel = "figures/fig1_harness_workflow.png"
    fig_path = repo_root / "Paper" / "joss" / expected_rel
    if expected_rel not in img_refs:
        failed.append(
            f"[4/8] Expected figure '{expected_rel}' not referenced in paper.md (found {img_refs})"
        )
    elif not fig_path.is_file():
        failed.append(f"[4/8] Referenced figure file missing: {fig_path}")
    else:
        try:
            width, height = read_png_dimensions(fig_path)
            if width < 1800:
                failed.append(
                    f"[4/8] Figure '{expected_rel}' width {width}px < required 1800px minimum"
                )
            else:
                passed.append(
                    f"[4/8] Figure '{expected_rel}' verified (valid PNG, {width}x{height} px)"
                )
        except Exception as exc:
            failed.append(f"[4/8] Figure validation failed: {exc}")

    # Check 5: BibTeX & citation integrity
    try:
        bib_entries = parse_bibtex_entries(bib_path.read_text(encoding="utf-8"))
        cited_keys = extract_markdown_citations(body_text)
        missing_in_bib = [k for k in cited_keys if k not in bib_entries]
        uncited_in_md = [k for k in bib_entries if k not in cited_keys]
        unpublished_no_id = [
            k
            for k, v in bib_entries.items()
            if v.get("_type") == "unpublished" and not (v.get("doi") or v.get("url"))
        ]
        bad_dois = []
        for k, v in bib_entries.items():
            doi = v.get("doi", "").strip()
            if not doi:
                bad_dois.append(f"{k} (missing doi)")
            elif not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
                bad_dois.append(f"{k} (invalid raw doi={doi!r}; omit https://doi.org/ prefix)")

        bib_errors = []
        if not bib_entries:
            bib_errors.append("paper.bib contains 0 entries")
        if missing_in_bib:
            bib_errors.append(f"cited keys missing from paper.bib: {missing_in_bib}")
        if uncited_in_md:
            bib_errors.append(f"uncited entries in paper.bib: {uncited_in_md}")
        if unpublished_no_id:
            bib_errors.append(f"@unpublished entries without DOI/URL: {unpublished_no_id}")
        if bad_dois:
            bib_errors.append(f"DOI errors: {bad_dois}")

        if bib_errors:
            failed.append(f"[5/8] Bibliography check failed: {'; '.join(bib_errors)}")
        else:
            passed.append(
                f"[5/8] Bibliography verified ({len(bib_entries)}/{len(bib_entries)} cited, "
                f"100% valid DOIs, 0 @unpublished)"
            )
    except Exception as exc:
        failed.append(f"[5/8] BibTeX parse error: {exc}")

    # Check 6: Required repository governance files
    missing_gov = []
    for rel in REQUIRED_GOVERNANCE_FILES:
        gp = repo_root / rel
        if not gp.is_file() or gp.stat().st_size == 0:
            missing_gov.append(rel)
    if missing_gov:
        failed.append(f"[6/8] Missing or empty governance files: {missing_gov}")
    else:
        passed.append(
            f"[6/8] All {len(REQUIRED_GOVERNANCE_FILES)} repository governance & CI files present"
        )

    # Check 7: Zero banned/stale strings & packaging version alignment
    stale_errors: list[str] = []
    jamia_memo = repo_root / "Paper" / "joss" / "JAMIA_OPEN_EXPANSION.md"
    if jamia_memo.exists():
        stale_errors.append("Paper/joss/JAMIA_OPEN_EXPANSION.md still exists on disk")

    scan_files: list[Path] = []
    for rel in (
        "Paper/README.md",
        "README.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
        "pyproject.toml",
    ):
        p = repo_root / rel
        if p.is_file():
            scan_files.append(p)
    joss_dir = repo_root / "Paper" / "joss"
    if joss_dir.is_dir():
        for child in sorted(joss_dir.iterdir()):
            if child.is_file() and child.suffix in (".md", ".bib", ".tex", ".yml", ".yaml"):
                scan_files.append(child)

    for sf in scan_files:
        txt = sf.read_text(encoding="utf-8")
        rel_sf = str(sf.relative_to(repo_root))
        for banned in BANNED_SUBSTRINGS:
            if banned in txt:
                stale_errors.append(f"banned string {banned!r} found in {rel_sf}")
        if not skip_packaging_version:
            for dev_tok in DEV_VERSION_SUBSTRINGS:
                if dev_tok in txt:
                    stale_errors.append(f"dev version string {dev_tok!r} found in {rel_sf}")

    if not skip_packaging_version:
        pyproj_path = repo_root / "pyproject.toml"
        cff_path = repo_root / "CITATION.cff"
        if pyproj_path.is_file():
            py_ver = read_pyproject_version(pyproj_path)
            if py_ver != "0.2.0":
                stale_errors.append(f"pyproject.toml version is {py_ver!r} (expected '0.2.0')")
        if cff_path.is_file():
            cff_ver = read_cff_version(cff_path)
            if cff_ver != "0.2.0":
                stale_errors.append(f"CITATION.cff version is {cff_ver!r} (expected '0.2.0')")

    if stale_errors:
        failed.append(f"[7/8] Stale/banned string or version errors: {'; '.join(stale_errors)}")
    else:
        suffix = (
            " (packaging version check skipped via --skip-packaging-version)"
            if skip_packaging_version
            else " (release version 0.2.0 verified)"
        )
        passed.append(f"[7/8] Zero banned/stale strings across JOSS & root docs{suffix}")

    # Check 8: Author placeholder & ISO 7064 Mod 11-2 ORCID checksum check
    placeholder_hits: list[str] = []
    orcid_errors: list[str] = []

    for tok in (
        PLACEHOLDER_AUTHOR,
        PLACEHOLDER_ORCID,
        PLACEHOLDER_AFFIL,
        "[Corresponding Author Name]",
        "[Author Institution and Department]",
    ):
        if tok in paper_text:
            placeholder_hits.append(f"Paper/joss/paper.md contains {tok!r}")

    if not skip_packaging_version:
        for rel in ("CITATION.cff", "pyproject.toml"):
            p = repo_root / rel
            if p.is_file():
                ptxt = p.read_text(encoding="utf-8")
                for tok in (
                    PLACEHOLDER_AUTHOR,
                    PLACEHOLDER_ORCID,
                    PLACEHOLDER_AFFIL,
                    LEGACY_CONTRIBUTORS,
                ):
                    if tok in ptxt:
                        placeholder_hits.append(f"{rel} contains {tok!r}")

    for idx, auth in enumerate(fm.get("authors", []), start=1):
        if not isinstance(auth, dict):
            continue
        raw_orcid = str(auth.get("orcid", "")).strip()
        if raw_orcid == PLACEHOLDER_ORCID and allow_placeholders:
            continue
        ok, msg = validate_orcid(raw_orcid)
        if not ok:
            orcid_errors.append(f"author #{idx}: {msg}")

    if orcid_errors:
        failed.append(
            "[8/8] Author/ORCID check failed: "
            + "; ".join(placeholder_hits + orcid_errors)
            + "\n        Fix with one command:\n"
            + '        python3 Paper/joss/check_joss_ready.py --set-author "Your Full Name" '
            + '--set-orcid "0000-0002-1825-0097" --set-affiliation "Department, University, Country"'
        )
    elif placeholder_hits and not allow_placeholders:
        failed.append(
            "[8/8] Author placeholders still present: "
            + "; ".join(placeholder_hits)
            + "\n        Fill real author metadata atomically with one command:\n"
            + '        python3 Paper/joss/check_joss_ready.py --set-author "Your Full Name" '
            + '--set-orcid "0000-0002-1825-0097" --set-affiliation "Department, University, Country"'
        )
    elif placeholder_hits and allow_placeholders:
        passed.append(
            "[8/8] Standardized author placeholders verified (--allow-placeholders enabled)"
        )
    else:
        passed.append(
            "[8/8] Real author metadata & ISO 7064 Mod 11-2 ORCID checksum verified"
        )

    return passed, failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify JOSS submission readiness for Medical Research Harness and optionally "
            "populate author/ORCID/affiliation metadata atomically across paper.md, CITATION.cff, "
            "and pyproject.toml."
        )
    )
    parser.add_argument(
        "--set-author",
        metavar="NAME",
        help="Atomically replace [AUTHOR_FULL_NAME] in Paper/joss/paper.md, CITATION.cff, and pyproject.toml",
    )
    parser.add_argument(
        "--set-orcid",
        metavar="ORCID",
        help="Validate ISO 7064 Mod 11-2 checksum and replace 0000-0000-0000-0000 across metadata files",
    )
    parser.add_argument(
        "--set-affiliation",
        metavar="AFFIL",
        help="Atomically replace [AUTHOR_AFFILIATION] across Paper/joss/paper.md, CITATION.cff, and pyproject.toml",
    )
    parser.add_argument(
        "--set-github-repo",
        metavar="OWNER/REPO",
        help="Optional: replace repository OWNER/REPO slug across Paper/joss/paper.md, CITATION.cff, and pyproject.toml",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow standardized author placeholders for CI or pre-submission structural verification",
    )
    parser.add_argument(
        "--skip-packaging-version",
        action="store_true",
        help="Skip strict 0.2.0 version check in pyproject.toml/CITATION.cff prior to packaging branch merge",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]

    if any(
        opt is not None
        for opt in (args.set_author, args.set_orcid, args.set_affiliation, args.set_github_repo)
    ):
        try:
            changed = apply_metadata_updates(
                repo_root=repo_root,
                author=args.set_author,
                orcid=args.set_orcid,
                affiliation=args.set_affiliation,
                github_repo=args.set_github_repo,
            )
            if changed:
                print("Updated metadata atomically in: " + ", ".join(changed))
            else:
                print("Metadata files already matched requested values (no file changes needed).")
        except Exception as exc:
            print(f"ERROR updating metadata: {exc}", file=sys.stderr)
            return 2

    passed, failed = run_checks(
        repo_root=repo_root,
        allow_placeholders=args.allow_placeholders,
        skip_packaging_version=args.skip_packaging_version,
    )

    print("=== JOSS Submission Readiness Audit ===")
    for item in passed:
        print(f"  PASS  {item}")
    for item in failed:
        print(f"  FAIL  {item}")

    if failed:
        print(f"\nRESULT: FAILED ({len(failed)} failed, {len(passed)} passed)")
        return 1

    print(f"\nRESULT: ALL {len(passed)} JOSS READINESS CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
