#!/usr/bin/env python3
"""Build and check the 2026 Missing Semester GNU Info manual.

Run this script from any directory. Its default root is the containing
repository; --root selects another checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit

MANUAL = "missing-semester-2026"
BASE = "https://missing.csail.mit.edu"
COMMIT = "1d695c94ccafdce3f06d6b9dfe3e6f106097693a"
LECTURES = [
    ("course-shell", "Shell"),
    ("command-line-environment", "CLI"),
    ("development-environment", "Development"),
    ("debugging-profiling", "Debugging"),
    ("version-control", "Git"),
    ("shipping-code", "Shipping"),
    ("agentic-coding", "Agents"),
    ("beyond-code", "Beyond Code"),
    ("code-quality", "Quality"),
]


def run(args, data=None):
    result = subprocess.run(args, input=data, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed:\n{result.stderr}")
    if result.stderr.strip():
        raise RuntimeError(f"Unexpected {args[0]} warning:\n{result.stderr}")
    return result.stdout


def save(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tex(text):
    return text.replace("@", "@@").replace("{", "@{").replace("}", "@}")


def arg(text):
    return tex(text).replace(",", "@comma{}")


def plain(value):
    if isinstance(value, list):
        return "".join(plain(v) for v in value)
    if not isinstance(value, dict):
        return ""
    kind, content = value.get("t"), value.get("c")
    if kind == "Str":
        return content
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind == "CodeBlock":
        return "\n" + content[-1] + "\n"
    if kind in {"Code", "Math"}:
        return content[-1]
    if kind in {"Link", "Image"}:
        return plain(content[1])
    if kind == "Header":
        return plain(content[2]) + "\n"
    if kind in {"Para", "Plain"}:
        return plain(content) + "\n"
    if kind == "RawInline":
        return ""
    return plain(content)


def walk(value):
    if isinstance(value, dict):
        yield value
        yield from walk(value.get("c"))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def normalize(source):
    # Match Jekyll's visible content, including whitespace-control comment tags.
    body = source.split("---", 2)[2]
    body = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", body, flags=re.S)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)

    def pre(match):
        emphasis = "<strong>" in match[1]
        text = re.sub(r"</?(?:code|strong|b)(?:\s[^>]*)?>", "", match[1])
        rendered = "\n```text\n" + html.unescape(text).strip("\n") + "\n```\n"
        if emphasis:
            rendered += "\n> Info edition note: The new merge commit is the last `o` on the top row. The website shows that commit in bold.\n"
        return rendered

    return re.sub(r"<pre\b[^>]*>(.*?)</pre>", pre, body, flags=re.S)


@dataclass
class Node:
    name: str
    title: str
    depth: int
    slug: str = ""
    blocks: list = field(default_factory=list)
    parent: Node | None = None
    children: list = field(default_factory=list)
    intro: str = ""
    terms: list = field(default_factory=list)


class Builder:
    def __init__(self, root):
        self.root = root
        self.nodes = []
        self.lookup = {}
        self.asts = {}
        self.links = []
        self.facts = {}
        self.api = None

    def load(self):
        editorial = {}
        for path in sorted((self.root / "editorial").glob("lectures-*.json")):
            for item in json.loads(path.read_text()):
                editorial[item["slug"]] = item
        for number, (slug, short) in enumerate(LECTURES, 1):
            path = self.root / "sources/2026" / (slug + ".md")
            raw = path.read_text()
            title = re.search(r'^title: "(.*)"$', raw, re.M)[1]
            day = re.search(r"^date: (.*)$", raw, re.M)[1]
            video = re.search(r"^  id: (.*)$", raw, re.M)[1]
            ast = json.loads(run(["pandoc", "-f", "gfm+tex_math_dollars", "-t", "json"], normalize(raw)))
            self.api = ast["pandoc-api-version"]
            self.asts[slug] = ast
            guide = editorial[slug]
            top = Node(short, f"{number}. {title}", 1, slug)
            top.terms = guide["index_terms"]
            top.intro = f"Lecture date: {day}.\n\n@uref{{{BASE}/2026/{slug}/,Original notes}}. "
            top.intro += f"@uref{{https://www.youtube.com/watch?v={video},Lecture video}}.\n\n"
            top.intro += "@heading Study guide (added for this edition)\n\n" + tex(guide["overview"]) + "\n\n"
            top.intro += "@subheading Learning objectives\n@itemize @bullet\n"
            top.intro += "".join("@item\n" + tex(x) + "\n" for x in guide["objectives"]) + "@end itemize\n\n"
            top.intro += "@subheading Reading notes\n@itemize @bullet\n"
            top.intro += "".join("@item\n" + tex(x) + "\n" for x in guide["reading_notes"]) + "@end itemize\n\n"
            top.intro += "@heading Original lecture notes\n\n"
            self.nodes.append(top)
            self.lookup[(slug, "")] = top
            stack = [top]
            current = top
            for block in ast["blocks"]:
                if block["t"] == "Header":
                    level, attributes, inlines = block["c"]
                    heading = plain(inlines)
                    name = short + " - " + re.sub(r"[,:.()\x7f]", "", heading)
                    name = re.sub(r"\s+", " ", name).strip()
                    while any(n.name == name for n in self.nodes):
                        name += " - more"
                    while stack[-1].depth >= level + 1:
                        stack.pop()
                    current = Node(name, heading, level + 1, slug, parent=stack[-1])
                    stack[-1].children.append(current)
                    stack.append(current)
                    self.nodes.append(current)
                    self.lookup[(slug, attributes[0])] = current
                    current.terms.append(heading)
                else:
                    current.blocks.append(block)
            section_terms = {t.casefold() for n in self.nodes if n.slug == slug and n.depth > 1 for t in n.terms}
            top.terms = [t for t in top.terms if t.casefold() not in section_terms]
            self.facts[slug] = {
                "title": title, "node": short, "date": day,
                "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "code_blocks": [n["c"][1] for n in walk(ast["blocks"]) if n["t"] == "CodeBlock"],
                "visible_tokens": [token for n in walk(ast["blocks"])
                                   if n["t"] in {"Str", "Code", "CodeBlock", "Math"}
                                   for token in tokens(n["c"] if n["t"] == "Str" else n["c"][-1])],
            }

    def transform(self, value, slug):
        if isinstance(value, list):
            return [self.transform(x, slug) for x in value]
        if not isinstance(value, dict):
            return value
        kind, content = value.get("t"), value.get("c")
        if kind == "CodeBlock":
            return {"t": "RawBlock", "c": ["texinfo", "@example\n" + tex(content[1]) + "\n@end example\n\n"]}
        if kind == "Link":
            label = plain(content[1])
            url = content[2][0]
            target = urlsplit(urljoin(f"{BASE}/2026/{slug}/", url))
            destination = None
            if target.hostname == "missing.csail.mit.edu":
                match = re.fullmatch(r"/2026/([^/]+)/?", target.path)
                target_slug = match[1] if match else None
                if target_slug in dict(LECTURES):
                    key = (target_slug, unquote(target.fragment))
                    if key not in self.lookup:
                        raise RuntimeError(f"Unresolved internal link: {slug}: {url}")
                    destination = self.lookup[key].name
                elif target.path.rstrip("/") == "/2026":
                    destination = "Top"
            absolute = target.geturl()
            self.links.append({"lecture": slug, "label": label, "source": url,
                               "url": absolute, "node": destination})
            if destination:
                rendered = f"@ref{{{arg(destination)},,{arg(label)}}}"
            elif absolute.startswith("mailto:"):
                rendered = f"@email{{{arg(absolute[7:])},{arg(label)}}}"
            elif label == absolute:
                rendered = f"@uref{{{arg(absolute)}}}"
            else:
                rendered = f"@uref{{{arg(absolute)},{arg(label)}}}"
            return {"t": "RawInline", "c": ["texinfo", rendered]}
        if kind == "Image":
            label = plain(content[1]) or "Image"
            url = urljoin(f"{BASE}/2026/{slug}/", content[2][0])
            rendered = f"[Image: {arg(label)}; @uref{{{arg(url)},view image}}]"
            return {"t": "RawInline", "c": ["texinfo", rendered]}
        if kind in {"RawInline", "RawBlock"}:
            if content[0] == "html":
                raise RuntimeError(f"Unconverted HTML in {slug}: {content[1]}")
        return {k: self.transform(v, slug) for k, v in value.items()}

    def body(self, node):
        doc = {"pandoc-api-version": self.api, "meta": {}, "blocks": self.transform(node.blocks, node.slug)}
        rendered = run(["pandoc", "-f", "json", "-t", "texinfo", "--wrap=none"], json.dumps(doc))
        # The Texinfo writer always emits a synthetic Top even for a fragment.
        rendered = re.sub(r"\A@node Top\n@top Top\n\n?", "", rendered)
        rendered = re.sub(r"(?m)^@enumerate[ \t]+$", "@enumerate", rendered)
        # *Note has special meaning in Info; bold Note must not become a link.
        return rendered.replace("@strong{Note", "@b{Note")

    def menu(self, children):
        if not children:
            return ""
        return "@menu\n" + "".join(f"* {tex(n.name)}:: {tex(n.title)}\n" for n in children) + "@end menu\n\n"

    def build(self):
        self.load()
        tops = [n for n in self.nodes if n.depth == 1]
        helpnode = Node("How to Read", "How to read this manual", 1)
        credits = Node("Sources and License", "Sources and license", 1)
        index = Node("Concept Index", "Concept index", 1)
        roots = [helpnode] + tops + [credits, index]
        out = "\\input texinfo\n@documentencoding UTF-8\n@setfilename " + MANUAL + ".info\n"
        out += "@settitle Missing Semester 2026\n@paragraphindent 0\n@frenchspacing on\n"
        out += "@dircategory Education\n@direntry\n* Missing Semester 2026: (missing-semester-2026). Practical computing tools, nine MIT lectures.\n@end direntry\n"
        out += "\n@node Top\n@top The Missing Semester of Your CS Education (2026)\n\n"
        out += "Nine lectures from MIT IAP 2026, by Anish Athalye, Jon Gjengset, and Jose Javier Gonzalez.\n\n"
        out += "This edition preserves the full published lecture notes and exercises. Each lecture starts with an added study guide. Videos and image files are linked; they are not embedded.\n\n"
        out += self.menu(roots)
        ordered = [helpnode] + self.nodes + [credits, index]
        all_names = [n.name for n in ordered]
        for pos, node in enumerate(ordered):
            siblings = node.parent.children if node.parent else roots
            sibling_pos = siblings.index(node)
            next_name = siblings[sibling_pos + 1].name if sibling_pos + 1 < len(siblings) else ""
            prev_name = siblings[sibling_pos - 1].name if sibling_pos else (node.parent.name if node.parent else "Top")
            parent_name = node.parent.name if node.parent else "Top"
            out += f"@node {tex(node.name)}, {tex(next_name)}, {tex(prev_name)}, {tex(parent_name)}\n"
            command = {1: "unnumbered", 2: "unnumberedsec", 3: "unnumberedsubsec", 4: "unnumberedsubsubsec"}[node.depth]
            out += f"@{command} {tex(node.title)}\n"
            for term in node.terms:
                out += "@cindex " + tex(term) + "\n"
            out += "\n"
            if node == helpnode:
                out += READ_HELP
            elif node == credits:
                out += CREDITS.replace("COMMIT_ID", COMMIT)
            elif node == index:
                out += "Use @kbd{i} to search an index term.\n\n@printindex cp\n\n"
            else:
                out += node.intro + self.body(node) + "\n"
            out += self.menu(node.children)
        out += "@bye\n"
        save(self.root / "manual" / (MANUAL + ".texi"), out)
        run(["makeinfo", "--no-split", "--fill-column=79", "-o", str(self.root / "info" / (MANUAL + ".info")), str(self.root / "manual" / (MANUAL + ".texi"))])
        run(["install-info", "--info-dir=" + str(self.root / "info"), str(self.root / "info" / (MANUAL + ".info"))])
        save(self.root / "reports/link-map.json", json.dumps(self.links, indent=2, ensure_ascii=False) + "\n")
        node_tokens = {n.name: [token for leaf in walk(n.blocks)
                               if leaf["t"] in {"Str", "Code", "CodeBlock", "Math"}
                               for token in tokens(leaf["c"] if leaf["t"] == "Str" else leaf["c"][-1])]
                       for n in self.nodes}
        save(self.root / "reports/build-facts.json", json.dumps({"commit": COMMIT, "nodes": all_names, "node_tokens": node_tokens, "lectures": self.facts}, indent=2, ensure_ascii=False) + "\n")
        self.verify()

    def verify(self):
        facts = json.loads((self.root / "reports/build-facts.json").read_text())
        info = (self.root / "info" / (MANUAL + ".info")).read_text()
        # Work on the physical node records, not the tag table at the end.
        records = {}
        for record in info.split("\x1f\n"):
            match = re.match(r"File: .*?,  Node: ([^,\n]+)", record)
            if match:
                records[match[1]] = record
        missing = set(facts["nodes"]) - records.keys()
        if missing:
            raise RuntimeError(f"Missing nodes: {missing}")
        problems = []
        stats = []
        for name, expected in facts["node_tokens"].items():
            actual = iter(tokens(records[name]))
            if not all(any(item == wanted for item in actual) for wanted in expected):
                problems.append(f"{name}: source text order changed or text was lost")
        reachable = {"Top"}
        pending = ["Top"]
        while pending:
            name = pending.pop()
            menu = records[name].partition("* Menu:\n")[2]
            for child in re.findall(r"^\* (.+?)::", menu, re.M):
                if child not in records:
                    problems.append(f"{name}: menu target missing: {child}")
                elif child not in reachable:
                    reachable.add(child)
                    pending.append(child)
        if records.keys() - reachable:
            problems.append(f"Nodes absent from menus: {records.keys() - reachable}")
        for slug, short in LECTURES:
            lecture = "\n".join(v for k, v in records.items() if k == short or k.startswith(short + " - "))
            current = facts["lectures"][slug]
            source = (self.root / "sources/2026" / (slug + ".md")).read_bytes()
            if hashlib.sha256(source).hexdigest() != current["source_sha256"]:
                problems.append(f"{slug}: source hash changed; regenerate manual")
            expected = Counter(current["visible_tokens"])
            actual = Counter(tokens(lecture))
            missing_words = expected - actual
            if missing_words:
                problems.append(f"{slug}: lost text tokens: {dict(missing_words)}")
            for i, code in enumerate(current["code_blocks"], 1):
                if not code_present(code, lecture):
                    problems.append(f"{slug}: code block {i} lost text or indentation")
            # Confirm the native reader resolves every lecture entry.
            dumped = run(["info", "-d", str(self.root / "info"), MANUAL, short, "-o", "-"])
            if f"Node: {short}" not in dumped:
                problems.append(f"{slug}: native reader did not select lecture")
            stats.append(f"| {current['title']} | {len(current['code_blocks'])} | passed |")
        for name in facts["nodes"]:
            output = run(["info", "-f", str(self.root / "info" / (MANUAL + ".info")), "-n", name, "-o", "-"])
            if "Node: " + name not in output:
                problems.append(f"Info reader cannot open node {name}")
        if "Changes in this edition" not in records["Sources and License"] or "CC BY-NC-SA" not in records["Sources and License"]:
            problems.append("Attribution or modification notice is missing")
        if problems:
            raise RuntimeError("\n".join(problems))
        text = "# Validation\n\nAll offline checks passed.\n\n"
        text += f"- Nine lectures; {len(records)} nodes, including Top.\n"
        text += "- Every node opens with the GNU Info reader.\n- Every lecture opens through its top menu entry.\n"
        text += "- Every source text token is retained in its lecture.\n- Every code block retains its text and relative indentation.\n"
        text += "- Source text order is retained within every section.\n- Every node is reachable from Top through native menus.\n"
        text += "- Internal links resolve during conversion; makeinfo reports no warnings.\n"
        text += "- Original source file hashes match the build record.\n\n"
        text += "| Lecture | Code blocks | Offline checks |\n| --- | ---: | --- |\n" + "\n".join(stats) + "\n"
        save(self.root / "reports/validation.md", text)
        print(f"PASS: nine lectures, {len(records)} nodes, full text and code checks")


def tokens(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())


def code_present(code, lecture):
    source = code.expandtabs(8).splitlines()
    output = lecture.expandtabs(8).splitlines()
    if not source:
        return True
    for start, line in enumerate(output):
        if not line.endswith(source[0]):
            continue
        pad = len(line) - len(source[0])
        if line[:pad].strip():
            continue
        candidate = output[start:start + len(source)]
        if len(candidate) == len(source) and all(
            (not s.strip() and not o.strip()) or o == " " * pad + s
            for s, o in zip(source, candidate)
        ):
            return True
    return False


READ_HELP = """This is a native GNU Info manual. Start at Top, select a lecture, and use its section menu.

@table @kbd
@item Tab
Move to the next menu entry or cross-reference.
@item Return
Follow the selected menu entry or cross-reference.
@item m
Choose a menu entry by name, for example @code{Git} at Top.
@item n / p / u
Go to the next sibling, previous sibling, or parent node.
@item Space / Backspace
Read forward or backward through the manual, across section boundaries.
@item l
Return to the last visited node.
@item t
Return to Top.
@item g
Go to a named node, for example @code{Quality - Regular expressions}.
@item s / i
Search the manual text or concept index.
@item q
Quit Info.
@end table

@heading Links

Lecture and section references are native Info links. They work offline. Web references keep their labels and complete URLs. Emacs Info and many terminal emulators can open these URLs in a browser. The stand-alone GNU Info reader does not provide native web browsing; copy a URL to your browser if your terminal does not open it.

@heading Code and diagrams

Code blocks use literal, fixed-width text. Indentation, backslashes, prompts, and long lines are preserved in the file. GNU Info wraps long lines on screen and marks a continuation with a backslash. Use @kbd{C-x w} to toggle display wrapping, or widen your terminal. A line that begins with a shell or interpreter prompt is a transcript; omit the prompt when you enter the command. Illustrations have text labels and links. The Git history diagrams are retained as text.

@heading Scope

The notes and exercises are complete for the pinned source snapshot. Source comments hidden on the website are omitted. The added guides identify known caveats without rewriting the original lesson or solving the exercises. Video content is linked and has not been transcribed. Some live demonstrations exist only in the recordings.\n\n"""

CREDITS = """@heading Attribution

The Missing Semester of Your CS Education, MIT IAP 2026, by Anish Athalye, Jon Gjengset, and Jose Javier Gonzalez, with contributions from the Missing Semester community.

@uref{https://missing.csail.mit.edu/2026/,Course website}.
@uref{https://github.com/missing-semester/missing-semester/tree/COMMIT_ID/_2026,Exact source revision}.

@heading License

The lecture notes, exercises, and this adaptation are licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).

@uref{https://creativecommons.org/licenses/by-nc-sa/4.0/,License summary}.
@uref{https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode,Full license terms}.

Give attribution, indicate changes, use the material for noncommercial purposes, and distribute adaptations under the same license. This summary does not replace the license terms.

@heading Changes in this edition

Converted Markdown to GNU Texinfo and Info; added section navigation, an index, original study guides, and technical reading notes; converted course links to offline references; replaced image embeds with labeled URLs; preserved code and text diagrams; removed website-only metadata and hidden comments. The course instructors do not endorse this edition.\n\n"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify", "selftest"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    builder = Builder(args.root.resolve())
    if args.action == "build":
        builder.build()
    elif args.action == "verify":
        builder.verify()
    else:
        selftest(args.root.resolve())


def selftest(root):
    """Prove that the checker rejects representative damaged artifacts."""
    with tempfile.TemporaryDirectory(prefix="missing-semester-check-") as temporary:
        target = Path(temporary) / "manual"
        shutil.copytree(root, target, ignore=shutil.ignore_patterns(".git"))
        info = target / "info" / (MANUAL + ".info")
        original = info.read_text()
        source = target / "sources/2026/course-shell.md"
        source_original = source.read_text()
        mutations = {
            "missing source text": original.replace("This class is co-taught", "This class was taught", 1),
            "code indentation": original.replace("     missing:~$ date", "      missing:~$ date", 1),
            "missing node": original.replace("Node: Shell,", "Node: Removed,", 1),
            "missing modification notice": original.replace("Changes in this edition", "Removed notice", 1),
        }
        for label, damaged in mutations.items():
            if damaged == original:
                raise RuntimeError(f"Selftest fixture did not mutate: {label}")
            info.write_text(damaged)
            try:
                Builder(target).verify()
            except RuntimeError:
                print("PASS: checker rejected " + label)
            else:
                raise RuntimeError("Checker accepted " + label)
            info.write_text(original)
        source.write_text(source_original + "\nChanged source.\n")
        try:
            Builder(target).verify()
        except RuntimeError:
            print("PASS: checker rejected a changed source hash")
        else:
            raise RuntimeError("Checker accepted changed source")


if __name__ == "__main__":
    main()
