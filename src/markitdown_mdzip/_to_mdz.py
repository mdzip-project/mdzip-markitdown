"""Convert any file MarkItDown understands into an .mdz archive, keeping its images."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import os
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import unquote

import mdzip_core
from markitdown import MarkItDown, StreamInfo

from ._converter import _first_heading

# A base64 image data: URI, as MarkItDown writes them with keep_data_uris=True.
_DATA_URI = re.compile(r"data:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/]+={0,2})")

# A Markdown image, ![alt](target "title"); target may be <in angle brackets>.
_IMAGE_LINK = re.compile(r'(?P<start>!\[[^\]\n]*\]\()(?P<target><[^>\n]+>|[^)\s]+)(?P<end>(?:\s+"[^"\n]*")?\))')
# A link with a scheme (https:, data:), protocol-relative, a fragment, or from the root.
_EXTERNAL = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//|#|/)")

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
    source_bytes: Optional[bytes] = None
    if isinstance(source, (str, os.PathLike)):
        path = os.fspath(source)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                source_bytes = f.read()
        result = md.convert(source, stream_info=stream_info, **kwargs)
        name = os.path.basename(path.split("?")[0].rstrip("/"))
    else:
        # Read once, so the pictures inside it can be found afterwards.
        source_bytes = source.read()
        name = (stream_info.filename if stream_info else None) or getattr(source, "name", None) or ""
        name = os.path.basename(str(name))
        result = md.convert_stream(io.BytesIO(source_bytes), stream_info=stream_info, **kwargs)

    stem = os.path.splitext(name)[0]
    entry = entry_point or _entry_name(stem)
    images_dir = images_dir.strip("/")
    files: Dict[str, bytes] = {}
    by_hash: Dict[str, str] = {}
    markdown, cover = _package_images(result.markdown, source_bytes, images_dir, files, by_hash)
    markdown = _extract_images(markdown, images_dir, files, by_hash)
    doc_title = title or result.title or _first_heading(markdown) or stem or None

    contents: Dict[str, Union[str, bytes]] = {entry: markdown}
    contents.update(files)
    manifest = {"cover": cover} if cover else None
    data = mdzip_core.create(contents, title=doc_title, entry_point=entry, manifest=manifest)
    return MdzConversion(data=data, markdown=markdown, entry_point=entry, title=doc_title, images=list(files))


def _entry_name(stem: str) -> str:
    """``<stem>.md`` if that's a valid root-level archive path, else ``index.md``."""
    candidate = f"{stem.strip()}.md"
    if not stem.strip() or "/" in candidate:
        return "index.md"
    try:
        mdzip_core.validate_path(candidate)
    except mdzip_core.MdzError:
        return "index.md"
    if mdzip_core.is_support_file(candidate):
        # A support-file name (README.md, ...) would read as package documentation.
        return "index.md"
    return candidate


def _free_path(path: str, files: Dict[str, bytes]) -> str:
    """``path``, or ``stem-2.ext``, ``stem-3.ext``... whichever isn't taken."""
    taken = {p.lower() for p in files}
    if path.lower() not in taken:
        return path
    stem, extension = posixpath.splitext(path)
    n = 2
    while f"{stem}-{n}{extension}".lower() in taken:
        n += 1
    return f"{stem}-{n}{extension}"


_ROOTFILE = re.compile(r"""<(?:\w+:)?rootfile\b[^>]*\bfull-path\s*=\s*["']([^"']+)["']""")
_OPF_ITEM = re.compile(r"<(?:\w+:)?item\b[^>]*>")
_OPF_META_COVER = re.compile(r"<(?:\w+:)?meta\b[^>]*>")


def _attribute(tag: str, name: str) -> Optional[str]:
    match = re.search(rf"""\s{name}\s*=\s*["']([^"']*)["']""", tag)
    return match.group(1) if match else None


def _epub_cover(z: zipfile.ZipFile, names: "set[str]") -> Optional[str]:
    """The path inside an EPUB of its cover picture, as its package file names it, or None.

    EPUB 3 marks the cover item ``properties="cover-image"``; EPUB 2 names its id in
    ``<meta name="cover" content="...">``.
    """
    if "META-INF/container.xml" not in names:
        return None
    try:
        container = z.read("META-INF/container.xml").decode("utf-8", "replace")
        rootfile = _ROOTFILE.search(container)
        if not rootfile or unquote(rootfile.group(1)) not in names:
            return None
        opf_path = unquote(rootfile.group(1))
        opf = z.read(opf_path).decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile):
        return None
    items = [tag for tag in _OPF_ITEM.findall(opf)]
    href = None
    for tag in items:
        if "cover-image" in (_attribute(tag, "properties") or "").split():
            href = _attribute(tag, "href")
            break
    if href is None:
        cover_id = None
        for tag in _OPF_META_COVER.findall(opf):
            if _attribute(tag, "name") == "cover":
                cover_id = _attribute(tag, "content")
                break
        for tag in items:
            if cover_id and _attribute(tag, "id") == cover_id:
                if (_attribute(tag, "media-type") or "").startswith("image/"):
                    href = _attribute(tag, "href")
                break
    if not href:
        return None
    path = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), unquote(href)))
    return path if path in names else None


def _package_images(
    markdown: str, source: Optional[bytes], images_dir: str, files: Dict[str, bytes], by_hash: Dict[str, str]
) -> "tuple[str, Optional[str]]":
    """Package pictures a ZIP-based source holds but MarkItDown left as links (EPUB).

    MarkItDown's EPUB converter turns each chapter's HTML into Markdown and keeps
    ``<img src>`` as written: a path relative to that chapter inside the EPUB
    (``../images/logo.png``), which means nothing in the .mdz. Each such link is
    looked up against the folders of the source's HTML files; a file found is stored
    under ``images_dir`` with its own name (stored once if repeated) and the link
    rewritten. Links that match nothing are left as they are.

    An EPUB's cover picture is usually named only in its package file, not in any
    chapter, so MarkItDown leaves it out. It's packaged too, shown at the top of the
    document unless a chapter already shows it, and returned for the manifest's
    ``cover``. Returns the Markdown and the cover's archive path (or None).
    """
    if not source or not zipfile.is_zipfile(io.BytesIO(source)):
        return markdown, None
    with zipfile.ZipFile(io.BytesIO(source)) as z:
        names = set(z.namelist())
        folders = sorted({posixpath.dirname(n) for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))})
        if not folders:
            return markdown, None
        found: Dict[str, Optional[str]] = {}
        shown = set()

        def store(name: str) -> str:
            data = z.read(name)
            digest = hashlib.sha256(data).hexdigest()
            archive_path = by_hash.get(digest)
            if archive_path is None:
                base = posixpath.basename(name)
                archive_path = _free_path(f"{images_dir}/{base}" if images_dir else base, files)
                by_hash[digest] = archive_path
                files[archive_path] = data
            return archive_path

        def lookup(target: str) -> Optional[str]:
            if target in found:
                return found[target]
            path = unquote(target.split("#")[0].split("?")[0])
            archive_path = None
            for folder in folders + [""]:
                candidate = posixpath.normpath(posixpath.join(folder, path))
                if not candidate.startswith("../") and candidate in names:
                    archive_path = store(candidate)
                    break
            found[target] = archive_path
            return archive_path

        def replace(match: "re.Match[str]") -> str:
            target = match.group("target")
            bare = target[1:-1] if target.startswith("<") else target
            if _EXTERNAL.match(bare):
                return match.group(0)
            archive_path = lookup(bare)
            if archive_path is None:
                return match.group(0)
            shown.add(archive_path)
            return match.group("start") + _link_target(archive_path) + match.group("end")

        markdown = _IMAGE_LINK.sub(replace, markdown)
        cover_name = _epub_cover(z, names)
        if cover_name is None:
            return markdown, None
        cover = store(cover_name)
        if cover not in shown:
            markdown = f"![Cover]({_link_target(cover)})\n\n" + markdown
        return markdown, cover


def _link_target(path: str) -> str:
    """``path`` as a Markdown link target: in <angle brackets> if it has spaces or parentheses."""
    return f"<{path}>" if re.search(r"[\s()]", path) else path


def _extract_images(markdown: str, images_dir: str, files: Dict[str, bytes], by_hash: Dict[str, str]) -> str:
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
            n = sum(1 for p in files if posixpath.basename(p).startswith("image-")) + 1
            path = _free_path(f"{images_dir}/image-{n:03d}{extension}" if images_dir else f"image-{n:03d}{extension}", files)
            by_hash[digest] = path
            files[path] = data
        return path

    return _DATA_URI.sub(replace, markdown)
