"""markitdown-mdz: convert a file to an .mdz archive with MarkItDown, keeping its images."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from typing import List, Optional

from markitdown import MarkItDown

from ._to_mdz import convert_to_mdz
from ._version import __version__

# MarkItDown's readers that need packages of their own (its extras), and the
# modules each imports, as of MarkItDown 0.1.9. Plain `pip install markitdown`
# leaves them out, and a file of that kind then fails to convert.
READERS = (
    ("docx", ("mammoth",)),
    ("pptx", ("pptx",)),
    ("xlsx", ("pandas", "openpyxl")),
    ("xls", ("pandas", "xlrd")),
    ("pdf", ("pdfminer", "pdfplumber")),
)


def missing_readers() -> List[str]:
    """The kinds of file (``docx``, ``pptx``, ...) MarkItDown can't read here for want of a package."""

    def present(module: str) -> bool:
        try:
            return importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            return False

    return [kind for kind, modules in READERS if not all(present(m) for m in modules)]


def version_text() -> str:
    """``--version``: this, MarkItDown's version, and the readers missing, if any.

    The last line is for programs that check the install (MDZip Studio does):
    ``Missing readers: docx, pptx`` names them by file extension.
    """
    try:
        from importlib.metadata import version

        markitdown = version("markitdown")
    except Exception:  # not installed as a distribution (a source checkout)
        markitdown = "unknown"
    lines = [f"markitdown-mdz {__version__}", f"MarkItDown {markitdown}"]
    missing = missing_readers()
    if missing:
        lines.append(f"Missing readers: {', '.join(missing)} (pip install \"markitdown-mdzip[all]\" adds them)")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="markitdown-mdz",
        description="Convert a file (Word, PowerPoint, HTML, PDF, ...) to an .mdz archive with MarkItDown. "
        "Images are kept as files in the archive.",
        # Keeps --version's lines as they are (argparse would join them).
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", help="file path or URL to convert")
    parser.add_argument("-o", "--output", help="output .mdz path (default: the source name with .mdz)")
    parser.add_argument("--title", help="archive title (default: the document's title or file name)")
    parser.add_argument("-p", "--use-plugins", action="store_true", help="enable MarkItDown's 3rd-party plugins")
    parser.add_argument("-f", "--force", action="store_true", help="overwrite the output file if it exists")
    parser.add_argument("--version", action="version", version=version_text())
    args = parser.parse_args(argv)

    output = args.output
    if not output:
        name = os.path.basename(args.source.split("?")[0].rstrip("/")) or "document"
        output = os.path.splitext(name)[0] + ".mdz"
    if os.path.abspath(output) == os.path.abspath(args.source):
        parser.error("the output would overwrite the source")
    if os.path.exists(output) and not args.force:
        parser.error(f"{output} already exists (use --force to overwrite)")

    try:
        result = convert_to_mdz(args.source, markitdown=MarkItDown(enable_plugins=args.use_plugins), title=args.title)
    except Exception as exc:  # MarkItDown raises several unrelated exception types
        print(f"markitdown-mdz: {exc}", file=sys.stderr)
        return 1
    result.save(output)
    images = len(result.images)
    print(f"Wrote {output}: {result.entry_point} + {images} image{'' if images == 1 else 's'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
