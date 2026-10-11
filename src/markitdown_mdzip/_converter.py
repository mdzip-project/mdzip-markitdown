"""The MarkItDown converter for .mdz archives."""

from __future__ import annotations

import base64
import mimetypes
import re
from typing import Any, BinaryIO, List, Optional

import mdzip
from markitdown import DocumentConverter, DocumentConverterResult, MarkItDown, StreamInfo

ACCEPTED_EXTENSIONS = [".mdz"]
ACCEPTED_MIME_TYPES = ["application/vnd.mdzip"]
"""The spec's proposed media type (MDZip spec Section 10)."""

DOCUMENTS_OPTIONS = ("auto", "entry", "all")

# An inline image: ![alt](dest) or ![alt](<dest> "title"). Reference-style images and
# raw <img> tags are left as written.
_IMAGE = re.compile(r'(!\[[^\]\n]*\]\()\s*(<[^>\n]*>|[^)\s]+)((?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'))?\s*\))')

# A leading "# Title" line, used when the manifest has no title.
_HEADING = re.compile(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", re.MULTILINE)


def register_converters(markitdown: MarkItDown, **kwargs: Any) -> None:
    """Called by MarkItDown when plugins are enabled."""
    # Priority 0 (PRIORITY_SPECIFIC_FILE_FORMAT) runs before MarkItDown's generic ZIP
    # converter, which would otherwise list the archive's files.
    markitdown.register_converter(MdzConverter(), priority=0.0)


class MdzConverter(DocumentConverter):
    """Converts an MDZip archive to Markdown.

    The output is the archive's entry point (MDZip spec Section 5.5). For a
    project-mode archive, the output also has every other Markdown document in it,
    each one introduced by an ``<!-- mdz:document path="..." -->`` comment. Support
    files (README, AGENTS, LICENSE, CHANGELOG and CONTRIBUTING at the root) are left
    out unless one of them is the entry point.

    Options, passed as ``convert()`` keyword arguments:

    - ``mdz_documents``: ``"auto"`` (default; ``"all"`` for project mode, otherwise
      ``"entry"``), ``"entry"``, or ``"all"``.
    - ``keep_data_uris``: embed images stored in the archive as ``data:`` URIs,
      instead of leaving their archive paths, which don't resolve once the Markdown
      is out of the archive. This is the same option MarkItDown's DOCX and PPTX
      converters use.
    """

    def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any) -> bool:
        extension = (stream_info.extension or "").lower()
        mimetype = (stream_info.mimetype or "").lower()
        return extension in ACCEPTED_EXTENSIONS or any(mimetype.startswith(m) for m in ACCEPTED_MIME_TYPES)

    def convert(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs: Any) -> DocumentConverterResult:
        documents = kwargs.get("mdz_documents", "auto")
        if documents not in DOCUMENTS_OPTIONS:
            raise ValueError(f"mdz_documents must be one of {', '.join(DOCUMENTS_OPTIONS)}, not {documents!r}")
        keep_data_uris = bool(kwargs.get("keep_data_uris", False))

        archive = mdzip.MdzArchive(file_stream.read(), path=stream_info.local_path)
        entry = archive.entry_point
        if documents == "auto":
            documents = "all" if archive.mode == "project" else "entry"

        paths = [entry]
        if documents == "all":
            paths += [p for p in archive.documents if p != entry and not mdzip.is_support_file(p)]

        parts: List[str] = []
        for path in paths:
            text = archive.read_text(path)
            if keep_data_uris:
                text = _embed_images(archive, path, text)
            if len(paths) > 1:
                text = f'<!-- mdz:document path="{_attr(path)}" -->\n\n{text.strip()}'
            parts.append(text.strip())

        markdown = "\n\n".join(parts) + "\n"
        return DocumentConverterResult(markdown=markdown, title=archive.title or _first_heading(markdown))


def _embed_images(archive: mdzip.MdzArchive, document: str, text: str) -> str:
    """Replace archive image paths in ``text`` with data: URIs."""

    def replace(match: "re.Match[str]") -> str:
        dest = match.group(2)
        bare = dest[1:-1] if dest.startswith("<") else dest
        target = archive.resolve_link(document, bare)
        if target.kind != "internal" or target.entry is None:
            return match.group(0)
        mimetype = mimetypes.guess_type(target.entry)[0]
        if not mimetype or not mimetype.startswith("image/"):
            return match.group(0)
        data = base64.b64encode(archive.read_bytes(target.entry)).decode("ascii")
        return f"{match.group(1)}data:{mimetype};base64,{data}{match.group(3)}"

    return _IMAGE.sub(replace, text)


def _first_heading(markdown: str) -> Optional[str]:
    match = _HEADING.search(markdown)
    return match.group(1) if match else None


def _attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("--", "&#45;&#45;")
