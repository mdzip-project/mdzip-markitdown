# Changelog

## [0.1.1] - 2026-11-23

- `markitdown-mdz` keeps an EPUB's pictures. MarkItDown's EPUB converter leaves each `<img>` as a link to the file inside the EPUB, relative to its chapter (`../images/logo.png`), so the `.mdz` had broken image links and no pictures. They're now found in the EPUB and stored under `images/` with their own names, each once; a link to a file the EPUB doesn't have stays as it was.
- An EPUB's cover is kept. It's named only in the book's package file, not in any chapter, so MarkItDown leaves it out. It's now stored under `images/`, set as the archive's `cover`, and shown at the top of the document unless a chapter already shows it.
- `markitdown-mdz --version` also gives MarkItDown's version and, when MarkItDown was installed without some of its readers, names the kinds of file it can't read: `Missing readers: docx, pptx (pip install "markitdown-mdzip[all]" adds them)`. MDZip Studio's System Integration shows it.
- A picture whose name has a space or parenthesis is linked in `<angle brackets>`, so the link works.

## [0.1.0] - 2026-11-18

First release.

- MarkItDown plugin: `markitdown --use-plugins guide.mdz` converts an MDZip (`.mdz`) archive to Markdown. A document-mode archive gives its entry point; a project-mode archive gives every document, entry point first, each marked with its path (`mdz_documents=` chooses). `keep_data_uris=True` embeds the images. An archive that isn't valid, or has no clear entry point, is left to MarkItDown's own ZIP converter.
- `markitdown-mdz`, a command and a `convert_to_mdz()` function: anything MarkItDown reads (Word, PowerPoint, HTML, PDF and more) becomes an `.mdz`, with the pictures from Word and PowerPoint files packaged in it. PDFs come through as text only.
- Built on `mdzip-core` 0.1.0, the Python MDZip library. Tested with MarkItDown 0.1.9 on Python 3.10 and 3.14, on Linux, macOS and Windows.
