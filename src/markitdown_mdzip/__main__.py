"""markitdown-mdz: convert a file to an .mdz archive with MarkItDown, keeping its images."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from markitdown import MarkItDown

from ._to_mdz import convert_to_mdz
from ._version import __version__


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="markitdown-mdz",
        description="Convert a file (Word, PowerPoint, HTML, PDF, ...) to an .mdz archive with MarkItDown. "
        "Images are kept as files in the archive.",
    )
    parser.add_argument("source", help="file path or URL to convert")
    parser.add_argument("-o", "--output", help="output .mdz path (default: the source name with .mdz)")
    parser.add_argument("--title", help="archive title (default: the document's title or file name)")
    parser.add_argument("-p", "--use-plugins", action="store_true", help="enable MarkItDown's 3rd-party plugins")
    parser.add_argument("-f", "--force", action="store_true", help="overwrite the output file if it exists")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
