# Changelog

## [0.1.0] - 2026-11-18

First release.

- MarkItDown plugin: `markitdown --use-plugins guide.mdz` converts an MDZip (`.mdz`) archive to Markdown. A document-mode archive gives its entry point; a project-mode archive gives every document, entry point first, each marked with its path (`mdz_documents=` chooses). `keep_data_uris=True` embeds the images. An archive that isn't valid, or has no clear entry point, is left to MarkItDown's own ZIP converter.
- `markitdown-mdz`, a command and a `convert_to_mdz()` function: anything MarkItDown reads (Word, PowerPoint, HTML, PDF and more) becomes an `.mdz`, with the pictures from Word and PowerPoint files packaged in it. PDFs come through as text only.
- Built on `mdzip-core` 0.1.0, the Python MDZip library. Tested with MarkItDown 0.1.9 on Python 3.10 and 3.14, on Linux, macOS and Windows.
