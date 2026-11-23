"""convert_to_mdz and the markitdown-mdz command."""

from __future__ import annotations

import base64
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import mdzip_core
from markitdown import StreamInfo

from markitdown_mdzip import convert_to_mdz
from markitdown_mdzip.__main__ import main

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
PNG2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
)


def uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


def html_with_images() -> bytes:
    return (
        "<html><head><title>Trip Report</title></head><body><h1>Trip Report</h1>"
        f'<p><img src="{uri(PNG)}" alt="map"></p>'
        f'<p><img src="{uri(PNG2)}" alt="photo"></p>'
        f'<p><img src="{uri(PNG)}" alt="map again"></p>'
        "</body></html>"
    ).encode()


def optional(module: str):
    try:
        __import__(module)
        return None
    except ImportError:
        return f"{module} not installed"


class HtmlTests(unittest.TestCase):
    def test_images_become_archive_files(self):
        result = convert_to_mdz(io.BytesIO(html_with_images()), stream_info=StreamInfo(extension=".html", filename="trip.html"))
        self.assertEqual(result.entry_point, "trip.md")
        self.assertEqual(result.title, "Trip Report")
        self.assertEqual(result.images, ["images/image-001.png", "images/image-002.png"])
        self.assertNotIn("data:", result.markdown)
        self.assertIn("![map](images/image-001.png)", result.markdown)
        self.assertIn("![photo](images/image-002.png)", result.markdown)
        self.assertIn("![map again](images/image-001.png)", result.markdown)  # stored once

        with mdzip_core.open(result.data) as archive:
            self.assertEqual(archive.entry_point, "trip.md")
            self.assertEqual(archive.title, "Trip Report")
            self.assertEqual(archive.read_bytes("images/image-001.png"), PNG)
            self.assertEqual(archive.read_bytes("images/image-002.png"), PNG2)
            self.assertEqual(archive.resolve_link("trip.md", "images/image-002.png").kind, "internal")
            self.assertEqual([d for d in archive.validate() if d.level == "error"], [])

    def test_from_a_path_and_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Trip Report.html")
            with open(path, "wb") as f:
                f.write(html_with_images())
            result = convert_to_mdz(path, title="Custom", images_dir="media/")
        self.assertEqual(result.entry_point, "Trip Report.md")
        self.assertEqual(result.title, "Custom")
        self.assertEqual(result.images[0], "media/image-001.png")

    def test_entry_names(self):
        page = b"<html><body><p>Hi</p></body></html>"
        for filename, expected in [("README.html", "index.md"), ("", "index.md"), ("notes.html", "notes.md")]:
            result = convert_to_mdz(io.BytesIO(page), stream_info=StreamInfo(extension=".html", filename=filename))
            self.assertEqual(result.entry_point, expected, filename)
        explicit = convert_to_mdz(io.BytesIO(page), stream_info=StreamInfo(extension=".html"), entry_point="doc.md")
        self.assertEqual(explicit.entry_point, "doc.md")


@unittest.skipIf(optional("docx") or optional("mammoth"), "python-docx and markitdown[docx] needed")
class DocxTests(unittest.TestCase):
    def test_word_images_are_kept(self):
        import docx

        document = docx.Document()
        document.add_heading("Quarterly Report", level=1)
        document.add_paragraph("Sales went up.")
        document.add_picture(io.BytesIO(PNG))
        buf = io.BytesIO()
        document.save(buf)
        buf.seek(0)

        result = convert_to_mdz(buf, stream_info=StreamInfo(extension=".docx", filename="report.docx"))
        self.assertEqual(result.entry_point, "report.md")
        self.assertIn("# Quarterly Report", result.markdown)
        self.assertEqual(result.title, "Quarterly Report")  # Word has no title; the heading is used
        self.assertEqual(result.images, ["images/image-001.png"])
        with mdzip_core.open(result.data) as archive:
            self.assertEqual(archive.read_bytes("images/image-001.png"), PNG)


@unittest.skipIf(optional("pptx"), "markitdown[pptx] needed")
class PptxTests(unittest.TestCase):
    def test_slide_images_are_kept(self):
        from pptx import Presentation
        from pptx.util import Inches

        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.title.text = "Roadmap"
        slide.shapes.add_picture(io.BytesIO(PNG), Inches(1), Inches(1))
        buf = io.BytesIO()
        deck.save(buf)
        buf.seek(0)

        result = convert_to_mdz(buf, stream_info=StreamInfo(extension=".pptx", filename="deck.pptx"))
        self.assertIn("Roadmap", result.markdown)
        self.assertEqual(result.images, ["images/image-001.png"])
        self.assertIn("](images/image-001.png)", result.markdown)


def epub(chapters: dict, files: dict, cover_items: str = "", cover_meta: str = "") -> bytes:
    """A minimal EPUB: chapters (name -> XHTML body) in OEBPS/text/, plus other files.

    cover_items and cover_meta go into the package file's manifest and metadata.
    """
    import zipfile

    items = cover_items + "".join(
        f'<item id="c{i}" href="text/{name}" media-type="application/xhtml+xml"/>' for i, name in enumerate(chapters)
    )
    spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles>'
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        z.writestr(
            "OEBPS/content.opf",
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<dc:title>Stories</dc:title>{cover_meta}</metadata><manifest>{items}</manifest><spine>{spine}</spine></package>",
        )
        for name, body in chapters.items():
            z.writestr(f"OEBPS/text/{name}", f'<html xmlns="http://www.w3.org/1999/xhtml"><body>{body}</body></html>')
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class EpubTests(unittest.TestCase):
    def test_pictures_inside_the_epub_are_packaged(self):
        # MarkItDown keeps each chapter's <img src> as written, relative to the
        # chapter inside the EPUB; markitdown-mdz finds and packages them.
        book = epub(
            {
                "one.xhtml": '<h1>One</h1><p><img src="../images/logo.png" alt="Logo"/></p>'
                '<p><img src="../images/map%20one.png" alt="Map"/></p>',
                "two.xhtml": '<h1>Two</h1><p><img src="../images/logo.png" alt="Logo again"/></p>'
                '<p><img src="../images/gone.png" alt="Missing"/></p>'
                '<p><img src="https://example.com/web.png" alt="Web"/></p>',
            },
            {"OEBPS/images/logo.png": PNG, "OEBPS/images/map one.png": PNG2},
        )
        result = convert_to_mdz(io.BytesIO(book), stream_info=StreamInfo(extension=".epub", filename="stories.epub"))
        self.assertEqual(result.images, ["images/logo.png", "images/map one.png"])
        self.assertIn("![Logo](images/logo.png)", result.markdown)
        self.assertIn("![Logo again](images/logo.png)", result.markdown)  # stored once
        self.assertIn("](<images/map one.png>)", result.markdown)  # a space: in angle brackets
        self.assertIn("../images/gone.png", result.markdown)  # not in the EPUB: left as it was
        self.assertIn("https://example.com/web.png", result.markdown)
        with mdzip_core.open(result.data) as archive:
            self.assertEqual(archive.read_bytes("images/logo.png"), PNG)
            self.assertEqual(archive.read_bytes("images/map one.png"), PNG2)

    def test_a_different_picture_with_the_same_name_gets_its_own(self):
        book = epub(
            {"one.xhtml": '<p><img src="../images/a/pic.png" alt="A"/></p><p><img src="../images/b/pic.png" alt="B"/></p>'},
            {"OEBPS/images/a/pic.png": PNG, "OEBPS/images/b/pic.png": PNG2},
        )
        result = convert_to_mdz(io.BytesIO(book), stream_info=StreamInfo(extension=".epub", filename="pics.epub"))
        self.assertEqual(result.images, ["images/pic.png", "images/pic-2.png"])

    def convert(self, book: bytes):
        return convert_to_mdz(io.BytesIO(book), stream_info=StreamInfo(extension=".epub", filename="book.epub"))

    def test_the_cover_picture_is_packaged_and_shown_first(self):
        # EPUB 3: the cover is an item marked cover-image, in no chapter.
        book = epub(
            {"one.xhtml": "<h1>One</h1><p>Text.</p>"},
            {"OEBPS/images/cover.png": PNG},
            cover_items='<item id="cv" href="images/cover.png" media-type="image/png" properties="cover-image"/>',
        )
        result = self.convert(book)
        self.assertEqual(result.images, ["images/cover.png"])
        self.assertTrue(result.markdown.startswith("![Cover](images/cover.png)\n\n"), result.markdown[:80])
        with mdzip_core.open(result.data) as archive:
            self.assertEqual(archive.read_bytes("images/cover.png"), PNG)
            self.assertEqual(archive.manifest.get("cover"), "images/cover.png")
            self.assertEqual([d for d in archive.validate() if d.level != "info"], [])

    def test_an_epub2_cover_and_one_a_chapter_already_shows(self):
        # EPUB 2 names the cover's id in <meta name="cover">; a chapter shows it, so it isn't added again.
        book = epub(
            {"cover.xhtml": '<p><img src="../images/front.png" alt="Front"/></p>'},
            {"OEBPS/images/front.png": PNG},
            cover_items='<item id="front" href="images/front.png" media-type="image/png"/>',
            cover_meta='<meta name="cover" content="front"/>',
        )
        result = self.convert(book)
        self.assertEqual(result.images, ["images/front.png"])
        self.assertNotIn("![Cover]", result.markdown)
        self.assertIn("![Front](images/front.png)", result.markdown)
        with mdzip_core.open(result.data) as archive:
            self.assertEqual(archive.manifest.get("cover"), "images/front.png")

    def test_no_cover(self):
        result = self.convert(epub({"one.xhtml": "<p>Text.</p>"}, {}))
        self.assertNotIn("![Cover]", result.markdown)
        with mdzip_core.open(result.data) as archive:
            self.assertIsNone(archive.manifest.get("cover"))


class CommandTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_writes_next_to_the_source_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "trip.html")
            with open(source, "wb") as f:
                f.write(html_with_images())
            output = os.path.join(tmp, "trip.mdz")

            code, out, _ = self.run_main(source, "-o", output)
            self.assertEqual(code, 0)
            self.assertIn("trip.md + 2 images", out)
            with mdzip_core.open(output) as archive:
                self.assertEqual(archive.entry_point, "trip.md")

            code, _, err = self.run_main(source, "-o", output)
            self.assertNotEqual(code, 0)
            self.assertIn("already exists", err)
            self.assertEqual(self.run_main(source, "-o", output, "--force")[0], 0)

    def test_version_names_missing_readers(self):
        from unittest import mock

        import markitdown_mdzip.__main__ as cli
        from markitdown_mdzip._version import __version__

        with mock.patch.object(cli, "missing_readers", return_value=["docx", "pptx"]):
            code, out, _ = self.run_main("--version")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"markitdown-mdz {__version__}")
        self.assertTrue(lines[1].startswith("MarkItDown "))
        self.assertTrue(lines[2].startswith("Missing readers: docx, pptx ("), lines[2])

        with mock.patch.object(cli, "missing_readers", return_value=[]):
            _, out, _ = self.run_main("--version")
        self.assertNotIn("Missing readers", out)

    def test_missing_readers_checks_the_modules(self):
        from unittest import mock

        import markitdown_mdzip.__main__ as cli

        present = {"mammoth", "pdfminer", "pdfplumber"}
        with mock.patch.object(cli.importlib.util, "find_spec", side_effect=lambda m: object() if m in present else None):
            self.assertEqual(cli.missing_readers(), ["pptx", "xlsx", "xls"])

    def test_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = self.run_main(os.path.join(tmp, "nope.docx"), "-o", os.path.join(tmp, "out.mdz"))
        self.assertEqual(code, 1)
        self.assertIn("markitdown-mdz:", err)


if __name__ == "__main__":
    unittest.main()
