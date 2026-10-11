# markitdown-mdzip

A [MarkItDown](https://github.com/microsoft/markitdown) plugin that converts **MDZip** (`.mdz`) archives to Markdown, and a `markitdown-mdz` command that goes the other way: Word, PowerPoint, HTML and more to `.mdz`, with the images kept.

An `.mdz` file is one or more Markdown documents and their images, packaged in a single ZIP file ([specification](https://github.com/mdzip-project/mdzip-spec)). Without this plugin, MarkItDown treats an `.mdz` as a plain ZIP and lists every file in it, `manifest.json` included. With it, you get the document itself.

## Install

```sh
pip install markitdown-mdzip
```

## Use

Plugins are off by default in MarkItDown, so turn them on:

```sh
markitdown --use-plugins guide.mdz
markitdown --list-plugins          # shows: mdzip
```

```python
from markitdown import MarkItDown

md = MarkItDown(enable_plugins=True)
result = md.convert("guide.mdz")
print(result.title)
print(result.markdown)
```

## What you get

- **A document-mode archive** (the usual kind) gives you its entry point: the main document, as the MDZip spec defines it.
- **A project-mode archive** gives you every document. The entry point comes first. Each document starts with a comment naming its path, so the boundaries survive:

  ```markdown
  <!-- mdz:document path="guide/setup.md" -->

  # Setup
  ```

  Support files at the archive root (`README`, `AGENTS`, `LICENSE`, `CHANGELOG`, `CONTRIBUTING`) describe the package rather than its content. They're left out unless one of them is the entry point.
- **The title** comes from the archive's manifest, or else from the first `#` heading.

### Options

Pass these to `convert()`:

| Option | Values | Default |
|---|---|---|
| `mdz_documents` | `"auto"`, `"entry"`, `"all"` | `"auto"`: `"all"` for project mode, otherwise `"entry"` |
| `keep_data_uris` | `True` / `False` | `False` |

By default, image links keep their paths inside the archive (`images/logo.png`), which don't resolve once the Markdown is outside it. `keep_data_uris=True` embeds those images as `data:` URIs, so the output stands alone. It's the same option MarkItDown's Word and PowerPoint converters use.

```python
md.convert("guide.mdz", keep_data_uris=True, mdz_documents="all")
```

### Errors

The plugin follows the spec. It won't guess an entry point: an archive with two candidate documents at its root and no manifest isn't converted by this plugin. The same goes for invalid archives, which includes unsafe paths, encrypted entries, and sizes over the limits. MarkItDown then falls back to its generic ZIP converter.

## The other direction: convert to `.mdz`

MarkItDown loses the images when it converts a Word or PowerPoint file to Markdown. The `markitdown-mdz` command keeps them: it writes an `.mdz` file holding the Markdown, with each image saved as its own file next to it.

```sh
pip install "markitdown-mdzip[docx,pptx]"     # MarkItDown's Word and PowerPoint support

markitdown-mdz "Launch Notes.docx"            # writes "Launch Notes.mdz"
markitdown-mdz deck.pptx -o slides.mdz
markitdown-mdz page.html --title "Trip Report"
```

```text
Launch Notes.mdz
├── manifest.json
├── Launch Notes.md          ← ![](images/image-001.png)
└── images/
    └── image-001.png
```

```python
from markitdown_mdzip import convert_to_mdz

result = convert_to_mdz("Launch Notes.docx")
result.save("Launch Notes.mdz")
print(result.entry_point, result.title, result.images)
```

How it works:
- MarkItDown runs with `keep_data_uris=True`, so each image arrives embedded in the Markdown.
- The tool decodes each embedded image into `images/image-001.png`, `image-002.jpg`, and so on, and points the Markdown at that file. An image used twice is stored once.
- **The document** is named after the source file (`Launch Notes.md`). The name falls back to `index.md` when it can't be used as an archive path, or when it would be mistaken for a support file such as `README.md`.
- **The title** is the one MarkItDown reports. If there isn't one, it's the document's first `#` heading, then the file name.

It works for any format MarkItDown reads. Images come through for any format whose MarkItDown converter embeds them, which includes Word (`.docx`), PowerPoint (`.pptx`), and HTML pages with embedded images. MarkItDown's PDF converter extracts text only, so a PDF gives an `.mdz` without images.

| Option | CLI | Python |
|---|---|---|
| Output path | `-o out.mdz` (default: source name + `.mdz`) | `result.save(path)` |
| Title | `--title` | `title=` |
| Entry document name | — | `entry_point=` |
| Image folder | — | `images_dir=` (default `images`) |
| MarkItDown plugins | `-p` / `--use-plugins` | pass your own `markitdown=MarkItDown(...)` |
| Overwrite | `-f` / `--force` | — |

## Development

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -e ../mdzip-core-python -e ".[docx,pptx,pdf]" python-docx
.venv/Scripts/python -m unittest
```

Reading `.mdz` files is done by [`mdzip-core`](https://github.com/mdzip-project/mdzip-core-python), the Python MDZip library. It has no dependencies of its own.

## License

Apache-2.0
