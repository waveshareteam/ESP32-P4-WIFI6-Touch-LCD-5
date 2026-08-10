#!/usr/bin/env python3
"""Repository-specific bilingual Markdown, link, and public-text checks.

This deliberately checks product-owned root pages, docs, and GitHub templates.
Markdown embedded in managed components and upstream examples is outside this
repository-specific policy and retains its upstream naming and content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
REFERENCE_LINK_RE = re.compile(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)")
HTML_LINK_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
EXPLICIT_ANCHOR_RE = re.compile(
    r"""<(?:a|[A-Za-z][A-Za-z0-9-]*)\b[^>]*(?:id|name)\s*=\s*["']([^"']+)["']""",
    re.I,
)
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF]"
)
QUICK_LINK_ICONS = ("🌐", "📚", "📦", "🚀", "🧩", "🔧")
CONFIG_PATH = Path("config/markdown-audit.json")
QUICK_LINKS = {
    "product": "🌐",
    "documentation": "📚",
    "firmware": "📦",
    "quick_start": "🚀",
    "esp_idf": "🧩",
    "arduino": "🔧",
}
REQUIRED_SINGLE_PRODUCT_COMPONENTS = frozenset(
    {
        "centered_header",
        "html_h1",
        "subtitle",
        "badges",
        "language_switch",
        "quick_links",
        "hero_image",
        "separator",
        "h2",
    }
)
REQUIRED_SINGLE_PRODUCT_QUICK_LINKS = frozenset(
    {"product", "documentation", "firmware", "esp_idf"}
)
REQUIRED_SINGLE_PRODUCT_BADGES = frozenset({"build", "license"})

PUBLIC_TEXT_PATTERNS = (
    (
        "LOCAL_ABSOLUTE_PATH",
        re.compile(r"(?i)(?:\b[A-Z]:[\\/]|\\\\[A-Za-z0-9_.-]+[\\/])"),
        "machine-specific absolute path",
    ),
    (
        "ACTUAL_SERIAL_PORT",
        re.compile(r"(?i)\bCOM\d+\b"),
        "actual serial-port identifier",
    ),
    (
        "MAC_ADDRESS",
        re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b"),
        "MAC address",
    ),
    (
        "CREDENTIAL_OR_TOKEN",
        re.compile(
            r"(?i)\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
            r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"
        ),
        "credential-shaped value",
    ),
    (
        "TOOL_OR_MODEL_PROVENANCE",
        re.compile(r"(?i)\b(?:Codex|ChatGPT|Claude|Cursor)\b"),
        "editing-tool or model provenance",
    ),
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class HomepagePair:
    english: str
    chinese: str
    profile: str
    required_components: frozenset[str]
    required_quick_links: tuple[str, ...]
    required_badges: tuple[str, ...]
    required_h2_icons: tuple[str, ...]


def relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def first_party_markdown(repo: Path) -> list[Path]:
    selected: set[Path] = set(repo.glob("*.md"))
    docs = repo / "docs"
    if docs.is_dir():
        selected.update(docs.rglob("*.md"))

    issue_templates = repo / ".github" / "ISSUE_TEMPLATE"
    if issue_templates.is_dir():
        selected.update(issue_templates.rglob("*.md"))

    pull_template_dir = repo / ".github" / "PULL_REQUEST_TEMPLATE"
    if pull_template_dir.is_dir():
        selected.update(pull_template_dir.rglob("*.md"))

    github_dir = repo / ".github"
    if github_dir.is_dir():
        selected.update(github_dir.glob("pull_request_template*.md"))

    # Example documentation is included only when the product repository owns
    # an explicit adjacent English/Simplified-Chinese pair. Unpaired upstream
    # example READMEs retain their original ownership and naming.
    for chinese in repo.glob("examples/esp-idf/*/README_ZH.md"):
        selected.add(chinese)
        english = chinese.with_name("README.md")
        if english.is_file():
            selected.add(english)

    return sorted(path for path in selected if path.is_file())


def is_chinese(path: Path) -> bool:
    return path.stem.endswith("_ZH")


def companion(path: Path) -> Path:
    if is_chinese(path):
        return path.with_name(path.stem[: -len("_ZH")] + path.suffix)
    return path.with_name(path.stem + "_ZH" + path.suffix)


def destination_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    # Markdown titles follow the destination after whitespace.
    return value.split(maxsplit=1)[0]


def link_targets(text: str) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    for regex in (MARKDOWN_LINK_RE, REFERENCE_LINK_RE, HTML_LINK_RE):
        for match in regex.finditer(text):
            targets.append((destination_value(match.group(1)), match.start(1)))
    return targets


def github_slug(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value).strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff -]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def markdown_anchors(text: str) -> set[str]:
    anchors = {unquote(value).lower() for value in EXPLICIT_ANCHOR_RE.findall(text)}
    seen: dict[str, int] = {}
    for _, title in HEADING_RE.findall(text):
        slug = github_slug(title)
        if not slug:
            continue
        duplicate = seen.get(slug, 0)
        anchors.add(slug if duplicate == 0 else f"{slug}-{duplicate}")
        seen[slug] = duplicate + 1
    return anchors


def local_target(
    repo: Path,
    source: Path,
    destination: str,
) -> tuple[Path | None, str]:
    if not destination:
        return None, ""
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc or destination.startswith("//"):
        return None, ""
    if parsed.path == "" and parsed.fragment:
        return source, unquote(parsed.fragment)
    if parsed.path.startswith("/"):
        return repo / unquote(parsed.path.lstrip("/")), unquote(parsed.fragment)
    return (source.parent / unquote(parsed.path)).resolve(), unquote(parsed.fragment)


def check_pairs(repo: Path, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    path_set = set(paths)
    for path in paths:
        other = companion(path)
        if other not in path_set:
            findings.append(
                Finding(
                    relative(repo, path),
                    1,
                    "BILINGUAL_COMPANION_MISSING",
                    f"missing product-owned companion {relative(repo, other)}",
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        if other.name not in text:
            findings.append(
                Finding(
                    relative(repo, path),
                    1,
                    "BILINGUAL_RECIPROCAL_LINK_MISSING",
                    f"language navigation must link to {other.name}",
                )
            )
    return findings


def check_links(repo: Path, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    path_set = set(paths)
    anchor_cache: dict[Path, set[str]] = {}

    for source in paths:
        text = source.read_text(encoding="utf-8")
        for destination, offset in link_targets(text):
            target, fragment = local_target(repo, source, destination)
            if target is None:
                continue
            try:
                target.relative_to(repo)
            except ValueError:
                findings.append(
                    Finding(
                        relative(repo, source),
                        line_number(text, offset),
                        "RELATIVE_LINK_ESCAPES_REPOSITORY",
                        "local link resolves outside the repository",
                    )
                )
                continue

            if not target.exists():
                findings.append(
                    Finding(
                        relative(repo, source),
                        line_number(text, offset),
                        "RELATIVE_LINK_TARGET_MISSING",
                        f"missing local target {target.relative_to(repo).as_posix()}",
                    )
                )
                continue

            if fragment and target.is_file() and target.suffix.lower() == ".md":
                if target not in anchor_cache:
                    anchor_cache[target] = markdown_anchors(
                        target.read_text(encoding="utf-8")
                    )
                if fragment.lower() not in anchor_cache[target]:
                    findings.append(
                        Finding(
                            relative(repo, source),
                            line_number(text, offset),
                            "RELATIVE_LINK_FRAGMENT_MISSING",
                            f"missing fragment #{fragment} in "
                            f"{target.relative_to(repo).as_posix()}",
                        )
                    )

            if source in path_set and target in path_set:
                own_companion = companion(source)
                if target == own_companion:
                    continue
                target_companion = companion(target)
                if target_companion.exists() and is_chinese(source) != is_chinese(target):
                    findings.append(
                        Finding(
                            relative(repo, source),
                            line_number(text, offset),
                            "WRONG_LANGUAGE_INTERNAL_LINK",
                            f"use same-language target "
                            f"{target_companion.relative_to(repo).as_posix()}",
                        )
                    )
    return findings


def check_public_text(repo: Path, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for code, regex, description in PUBLIC_TEXT_PATTERNS:
            for match in regex.finditer(text):
                findings.append(
                    Finding(
                        relative(repo, path),
                        line_number(text, match.start()),
                        code,
                        f"remove or replace {description} with a generic placeholder",
                    )
                )
    return findings


def h2_icons(text: str) -> list[str]:
    icons: list[str] = []
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        match = EMOJI_RE.match(title)
        icon = match.group(0) if match else ""
        if title.startswith(icon + "\ufe0f"):
            icon += "\ufe0f"
        icons.append(icon)
    return icons


def quick_icons(header: str) -> list[str]:
    icon_pattern = "|".join(re.escape(icon) for icon in QUICK_LINK_ICONS)
    return [match.group(0) for match in re.finditer(icon_pattern, header)]


def load_homepage_pairs(repo: Path) -> list[HomepagePair]:
    config_path = repo / CONFIG_PATH
    if not config_path.is_file():
        raise OSError(f"homepage policy config is missing: {CONFIG_PATH.as_posix()}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid homepage policy config: {error.msg}") from error
    if not isinstance(config, dict) or not isinstance(config.get("homepage_pairs"), list):
        raise ValueError("invalid homepage policy config: homepage_pairs must be a list")

    pairs: list[HomepagePair] = []
    for index, item in enumerate(config["homepage_pairs"], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] must be an object")
        fields = ("english", "chinese", "profile", "required_components", "required_quick_links", "required_badges", "required_h2_icons")
        if any(field not in item for field in fields):
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] is incomplete")
        english, chinese, profile = (item[field] for field in ("english", "chinese", "profile"))
        lists = tuple(item[field] for field in fields[3:])
        if (
            not all(isinstance(value, str) and value for value in (english, chinese, profile))
            or not all(isinstance(value, list) and all(isinstance(entry, str) for entry in value) for value in lists)
        ):
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] has invalid values")
        if profile != "single-product":
            raise ValueError(f"invalid homepage policy config: unsupported homepage profile {profile!r}")
        components = frozenset(lists[0])
        quick_links, badges, h2_icons = (tuple(values) for values in lists[1:])
        if not REQUIRED_SINGLE_PRODUCT_COMPONENTS <= components:
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] omits required components")
        if not REQUIRED_SINGLE_PRODUCT_QUICK_LINKS <= set(quick_links):
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] omits required quick links")
        if not REQUIRED_SINGLE_PRODUCT_BADGES <= set(badges) or not h2_icons:
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] omits required badge or H2 policy")
        if any(key not in QUICK_LINKS for key in quick_links) or any(key not in {"build", "license"} for key in badges):
            raise ValueError(f"invalid homepage policy config: homepage_pairs[{index}] has an unsupported key")
        pairs.append(HomepagePair(english, chinese, profile, components, quick_links, badges, h2_icons))
    if not pairs:
        raise ValueError("invalid homepage policy config: homepage_pairs must not be empty")
    return pairs


def header_for(text: str) -> str:
    header_end = text.find("</div>")
    return text[: header_end + len("</div>")] if header_end >= 0 else ""


def header_has_badge(header: str, key: str) -> bool:
    lowered = header.lower()
    if key == "build":
        return "actions/workflows" in lowered and "<img" in lowered
    return key in lowered and "<img" in lowered


def header_has_quick_link(header: str, key: str) -> bool:
    icon = QUICK_LINKS[key]
    return bool(re.search(rf'<a\s+href=["\'][^"\']+?["\'][^>]*>[^<]*{re.escape(icon)}', header))


def check_homepage(repo: Path, pairs: list[HomepagePair]) -> list[Finding]:
    findings: list[Finding] = []
    for pair in pairs:
        english_path = repo / pair.english
        chinese_path = repo / pair.chinese
        if not english_path.is_file() or not chinese_path.is_file():
            missing = english_path if not english_path.is_file() else chinese_path
            findings.append(Finding(relative(repo, missing), 1, "HOMEPAGE_PAIR_MISSING", "configured homepage file is missing"))
            continue

        english = english_path.read_text(encoding="utf-8")
        chinese = chinese_path.read_text(encoding="utf-8")
        for path, text, language_target in ((english_path, english, chinese_path.name), (chinese_path, chinese, english_path.name)):
            header = header_for(text)
            component_checks = {
                "centered_header": ('<div align="center">' in header, "centered header"),
                "html_h1": ("<h1>" in header and "</h1>" in header, "plain HTML level-one title"),
                "subtitle": ("<strong>" in header, "subtitle"),
                "badges": ("<img" in header, "badges"),
                "language_switch": (language_target in header, "reciprocal language switch"),
                "quick_links": (bool(quick_icons(header)), "quick links"),
                "hero_image": (any(line.lstrip().startswith("<img") for line in header.splitlines()), "hero image"),
                "separator": ("\n---\n" in text, "header/body separator"),
                "h2": (bool(h2_icons(text)), "primary sections"),
            }
            for component in pair.required_components:
                present, label = component_checks[component]
                if not present:
                    findings.append(Finding(relative(repo, path), 1, "HOMEPAGE_COMPONENT_MISSING", f"homepage is missing {label}"))
            for key in pair.required_quick_links:
                if not header_has_quick_link(header, key):
                    findings.append(Finding(relative(repo, path), 1, "HOMEPAGE_QUICK_LINK_MISSING", f"homepage is missing {key} quick link with URL"))
            for key in pair.required_badges:
                if not header_has_badge(header, key):
                    findings.append(Finding(relative(repo, path), 1, "HOMEPAGE_BADGE_MISSING", f"homepage is missing {key} badge"))
            h1 = re.search(r"<h1>(.*?)</h1>", header)
            if h1 and EMOJI_RE.search(h1.group(1)):
                findings.append(Finding(relative(repo, path), line_number(text, h1.start()), "HOMEPAGE_H1_EMOJI", "keep the product title free of emoji"))
            for match in re.finditer(r"(?m)^###\s+(.+)$", text):
                if EMOJI_RE.match(match.group(1).strip()):
                    findings.append(Finding(relative(repo, path), line_number(text, match.start()), "HOMEPAGE_H3_EMOJI", "tertiary headings must remain plain"))

        english_header = header_for(english)
        chinese_header = header_for(chinese)
        if quick_icons(english_header) != quick_icons(chinese_header):
            findings.append(Finding(pair.english, 1, "HOMEPAGE_QUICK_LINK_ASYMMETRY", "English and Chinese quick-link icon sequences differ"))
        english_h2 = h2_icons(english)
        chinese_h2 = h2_icons(chinese)
        if "" in english_h2 or "" in chinese_h2:
            findings.append(Finding(pair.english, 1, "HOMEPAGE_H2_ICON_MISSING", "every primary homepage section needs one semantic emoji"))
        if english_h2 != chinese_h2:
            findings.append(Finding(pair.english, 1, "HOMEPAGE_H2_ASYMMETRY", "English and Chinese primary-section emoji sequences differ"))
        if tuple(english_h2) != pair.required_h2_icons or tuple(chinese_h2) != pair.required_h2_icons:
            findings.append(Finding(pair.english, 1, "HOMEPAGE_H2_POLICY_MISMATCH", "homepage primary-section emoji sequence does not match configured policy"))
    return findings


def run(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    if not repo.is_dir():
        raise OSError(f"repository path is not a directory: {repo}")
    paths = first_party_markdown(repo)
    if not paths:
        raise OSError("no product-owned Markdown files were found")

    pairs = load_homepage_pairs(repo)
    findings = [
        *check_pairs(repo, paths),
        *check_links(repo, paths),
        *check_public_text(repo, paths),
        *check_homepage(repo, pairs),
    ]
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check this repository's product-owned Markdown policy."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        findings = run(args.root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"repository policy error: {error}", file=sys.stderr)
        return 2

    if findings:
        for finding in findings:
            print(
                f"{finding.path}:{finding.line}: "
                f"{finding.code}: {finding.message}"
            )
        print(f"{len(findings)} repository policy finding(s)", file=sys.stderr)
        return 1

    print("Repository policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
