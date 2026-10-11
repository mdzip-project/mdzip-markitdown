"""Convert any file MarkItDown understands into an .mdz archive, keeping its images."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Union

import mdzip
from markitdown import MarkItDown, StreamInfo

from ._converter import _first_heading

# A base64 image data: URI, as MarkItDown writes them with keep_data_uris=True.
_DATA_URI = re.compile(r"data:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/]+={0,2})")

_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/x-emf": ".emf",
    "image/x-wmf": ".wmf",
    "image/avif": ".avif",
}

Source = Union[str, "os.PathLike[str]", BinaryIO]


@dataclass
class MdzConversion:
    """The result of :func:`convert_to_mdz`."""

    data: bytes
    """The .mdz archive bytes."""
    markdown: str
    """The entry document's Markdown, with image links pointing into the archive."""
    entry_point: str
    title: Optional[str]
    images: List[str] = field(default_factory=list)
    """Archive paths of the images that were extracted, in order of first appearance."""

    def save(self, path: Union[str, "os.PathLike[str]"]) -> None:
        with open(path, "wb") as f:
            f.write(self.data)


def convert_to_mdz(
    source: Source,
    *,
    markitdown: Optional[MarkItDown] = None,
    stream_info: Optional[StreamInfo] = None,
    title: Optional[str] = None,
    entry_point: Optional[str] = None,
    images_dir: str = "images",
    **kwargs: Any,
) -> MdzConversion:
    """Convert ``source`` (a path, URL or binary stream) with MarkItDown and package the result.

    MarkItDown is asked to keep images as ``data:`` URIs (``keep_data_uris=True``);
    each one is written to ``images_dir`` in the archive, named in order of first
    appearance (``image-001.png``, ...), with duplicates stored once, and the link is
    rewritten to point at it. Formats whose MarkItDown converter emits no image data
    (PDF, for example) give an archive with the text only.

    ``entry_point`` defaults to the source's file name with ``.md`` (``report.docx`` ->
    ``report.md``), or ``index.md`` if there's no usable name. ``title`` defaults to the
    title MarkItDown found, then the first ``#`` heading, then the file name. Other
    keyword arguments go to ``MarkItDown.convert``.
    """
    md = markitdown or MarkItDown()
    kwargs.setdefault("keep_data_uris", True)
    if isinstance(source, (str, os.PathLike)):
        result = md.convert(source, stream_info=stream_info, **kwargs)
        name = os.path.basename(os.fspath(source).split("?")[0].rstrip("/"))
    else:
        result = md.convert_stream(source, stream_info=stream_info, **kwargs)
        name = (stream_info.filename if stream_info else None) or getattr(source, "name", None) or ""
        name = os.path.basename(str(name))

    stem = os.path.splitext(name)[0]
    entry = entry_point or _entry_name(stem)
    images_dir = images_dir.strip("/")
    markdown, files = _extract_images(result.markdown, images_dir)
    doc_title = title or result.title or _first_heading(markdown) or stem or None

    contents: Dict[str, Union[str, bytes]] = {entry: markdown}
    contents.update(files)
    data = mdzip.create(contents, title=doc_title, entry_point=entry)
    return MdzConversion(data=data, markdown=markdown, entry_point=entry, title=doc_title, images=list(files))


def _entry_name(stem: str) -> str:
    """``<stem>.md`` if that's a valid root-level archive path, else ``index.md``."""
    candidate = f"{stem.strip()}.md"
    if not stem.strip() or "/" in candidate:
        return "index.md"
    try:
        mdzip.validate_path(candidate)
    except mdzip.MdzError:
        return "index.md"
    if mdzip.is_support_file(candidate):
        # A support-file name (README.md, ...) would read as package documentation.
        return "index.md"
    return candidate


def _extract_images(markdown: str, images_dir: str):
    files: Dict[str, bytes] = {}
    by_hash: Dict[str, str] = {}

    def replace(match: "re.Match[str]") -> str:
        mimetype = match.group(1).lower()
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError):
            return match.group(0)
        digest = hashlib.sha256(data).hexdigest()
        path = by_hash.get(digest)
        if path is None:
            extension = _EXTENSIONS.get(mimetype, ".bin")
            path = f"{images_dir}/image-{len(by_hash) + 1:03d}{extension}" if images_dir else f"image-{len(by_hash) + 1:03d}{extension}"
            by_hash[digest] = path
            files[path] = data
        return path

    return _DATA_URI.sub(replace, markdown), files
