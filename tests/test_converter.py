"""MdzConverter, through MarkItDown with plugins enabled."""

from __future__ import annotations

import base64
import io
import os
import tempfile
import unittest
import zipfile

import mdzip_core
from markitdown import MarkItDown, StreamInfo

from markitdown_mdzip import MdzConverter

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def convert(data: bytes, extension: str = ".mdz", **kwargs):
    md = MarkItDown(enable_plugins=True)
    return md.convert_stream(io.BytesIO(data), stream_info=StreamInfo(extension=extension), **kwargs)


class DocumentModeTests(unittest.TestCase):
    def setUp(self):
        self.data = mdzip_core.create(
            {
                "index.md": "# Field Guide\n\nSee ![a bird](images/bird.png \"Bird\").\n",
                "notes.md": "# Notes\n\nNot the entry point.\n",
                "images/bird.png": PNG,
            },
            title="Field Guide",
        )

    def test_entry_point_only(self):
        result = convert(self.data)
        self.assertEqual(result.title, "Field Guide")
        self.assertIn("# Field Guide", result.markdown)
        self.assertNotIn("Not the entry point", result.markdown)
        self.assertIn("](images/bird.png", result.markdown)

    def test_all_documents_on_request(self):
        result = convert(self.data, mdz_documents="all")
        self.assertIn("Not the entry point", result.markdown)
        self.assertLess(result.markdown.index("# Field Guide"), result.markdown.index("# Notes"))
        self.assertIn('<!-- mdz:document path="notes.md" -->', result.markdown)

    def test_keep_data_uris_embeds_archive_images(self):
        result = convert(self.data, keep_data_uris=True)
        expected = "![a bird](data:image/png;base64," + base64.b64encode(PNG).decode() + ' "Bird")'
        self.assertIn(expected, result.markdown)

    def test_not_used_for_other_zips(self):
        result = convert(self.data, extension=".zip")
        self.assertIn("Content from the zip file", result.markdown)

    def test_mime_type_is_accepted(self):
        info = StreamInfo(mimetype="application/vnd.mdzip")
        self.assertTrue(MdzConverter().accepts(io.BytesIO(b""), info))

    def test_converts_from_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "guide.mdz")
            with open(path, "wb") as f:
                f.write(self.data)
            result = MarkItDown(enable_plugins=True).convert(path)
        self.assertIn("# Field Guide", result.markdown)

    def test_without_plugins_markitdown_dumps_every_file(self):
        # The behavior this plugin replaces: the generic ZIP converter, manifest and all.
        result = MarkItDown().convert_stream(io.BytesIO(self.data), stream_info=StreamInfo(extension=".mdz"))
        self.assertIn("## File: manifest.json", result.markdown)
        self.assertNotIn("## File: manifest.json", convert(self.data).markdown)


class ProjectModeTests(unittest.TestCase):
    def setUp(self):
        self.data = mdzip_core.create(
            {
                "index.md": "# Handbook\n\n[Setup](guide/setup.md)\n",
                "guide/setup.md": "# Setup\n\n![diagram](../images/d.png)\n",
                "README.md": "# About this package\n",
                "AGENTS.md": "# Agents\n",
                "images/d.png": PNG,
            },
            title="Handbook",
            mode="project",
            entry_point="index.md",
        )

    def test_all_documents_entry_first_support_files_skipped(self):
        markdown = convert(self.data).markdown
        self.assertTrue(markdown.startswith('<!-- mdz:document path="index.md" -->'))
        self.assertIn('<!-- mdz:document path="guide/setup.md" -->', markdown)
        self.assertNotIn("About this package", markdown)
        self.assertNotIn("# Agents", markdown)

    def test_entry_only_on_request(self):
        markdown = convert(self.data, mdz_documents="entry").markdown
        self.assertNotIn("# Setup", markdown)
        self.assertNotIn("mdz:document", markdown)

    def test_images_resolve_relative_to_their_document(self):
        markdown = convert(self.data, keep_data_uris=True).markdown
        self.assertIn("![diagram](data:image/png;base64,", markdown)


class EntryPointTests(unittest.TestCase):
    def raw(self, entries):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, text in entries.items():
                z.writestr(name, text)
        return buf.getvalue()

    def test_zipped_folder_with_support_files(self):
        data = self.raw({"recipes.md": "# Recipes\n", "README.md": "# About\n", "AGENTS.md": "# Agents\n"})
        result = convert(data)
        self.assertEqual(result.title, "Recipes")
        self.assertNotIn("About", result.markdown)

    def test_ambiguous_entry_point_is_not_guessed(self):
        data = self.raw({"a.md": "# A\n", "b.md": "# B\n"})
        with self.assertRaises(mdzip_core.MdzError) as caught:
            MdzConverter().convert(io.BytesIO(data), StreamInfo(extension=".mdz"))
        self.assertEqual(caught.exception.code, "ERR_ENTRYPOINT_UNRESOLVED")

    def test_unknown_option_value(self):
        data = self.raw({"index.md": "# I\n"})
        with self.assertRaises(ValueError):
            MdzConverter().convert(io.BytesIO(data), StreamInfo(extension=".mdz"), mdz_documents="some")


class PluginTests(unittest.TestCase):
    def test_entry_point_is_registered(self):
        from importlib.metadata import entry_points

        names = {ep.name: ep.value for ep in entry_points(group="markitdown.plugin")}
        self.assertEqual(names.get("mdzip"), "markitdown_mdzip")

    def test_interface_version(self):
        import markitdown_mdzip

        self.assertEqual(markitdown_mdzip.__plugin_interface_version__, 1)


if __name__ == "__main__":
    unittest.main()
