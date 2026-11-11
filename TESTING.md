# Test script: markitdown-mdzip

This walks you through trying markitdown-mdzip by hand. It takes about 30
minutes. You'll type commands into a terminal, but you don't need to write
code.

The package does two jobs:

- **Reading:** a plugin for Microsoft's
  [MarkItDown](https://github.com/microsoft/markitdown) that turns an MDZip
  (`.mdz`) file into plain Markdown.
- **Writing:** a `markitdown-mdz` command that turns a Word, PowerPoint or
  HTML file into an `.mdz` file, with its images kept. Plain MarkItDown drops
  the images.

Work through the tests in order. Tick each box when you see what the
**Expected** line describes. When you see something else, write down what
happened (see [Reporting problems](#reporting-problems)).

## Setup

You need Python 3.10 or newer. To check your version, run `python --version`
(on macOS or Linux, use `python3`).

1. Make an empty folder to work in, and open a terminal there.
2. Create a virtual environment so nothing touches your system Python:

   ```sh
   python -m venv .venv
   ```

3. Activate it:

   | System | Command |
   |---|---|
   | Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
   | Windows (Command Prompt) | `.venv\Scripts\activate.bat` |
   | macOS / Linux | `source .venv/bin/activate` |

4. Install the package from GitHub (it isn't on PyPI yet):

   ```sh
   pip install "markitdown-mdzip[docx,pptx] @ git+https://github.com/mdzip-project/mdzip-markitdown"
   ```

5. Download the two sample files into your folder:

   - [demo-single.mdz](https://mdzip.org/assets/demo-single.mdz): one document and one image
   - [demo-project.mdz](https://mdzip.org/assets/demo-project.mdz): several documents (index, format, tools)

6. Find a Word file (`.docx`) and a PowerPoint file (`.pptx`) that **contain
   pictures**, and copy them into your folder. Any of your own will do. The
   tests below call them `report.docx` and `slides.pptx`; use your own file
   names instead.

## Part 1: Reading `.mdz` files

### 1.1 The plugin is installed

```sh
markitdown --list-plugins
```

- [ ] **Expected:** `mdzip` appears in the list.

### 1.2 Without the plugin (for comparison)

```sh
markitdown demo-single.mdz
```

- [ ] **Expected:** a list of the files inside the archive, including
  `manifest.json` and `images/specimen.png`. This is what MarkItDown does
  with any ZIP file. The plugin is off here, so this is the "before" picture.

### 1.3 A single-document file

```sh
markitdown --use-plugins demo-single.mdz
```

- [ ] **Expected:** the text of the document itself, as readable Markdown.
- [ ] **Expected:** no list of archive files and no `manifest.json` content.
- [ ] **Expected:** the image appears as a link like
  `![...](images/specimen.png)`.

### 1.4 A multi-document file

```sh
markitdown --use-plugins demo-project.mdz
```

- [ ] **Expected:** all three documents, one after another, with the main
  one (`index.md`) first.
- [ ] **Expected:** each document starts with a line like
  `<!-- mdz:document path="format.md" -->` showing where it came from.

### 1.5 Save the output to a file

```sh
markitdown --use-plugins demo-project.mdz -o project.md
```

- [ ] **Expected:** a new `project.md` file. Open it in any text editor; it
  should match what you saw in 1.4.

### 1.6 Images that work outside the archive

The image links in 1.3 point inside the `.mdz`, so they break once the text
is outside it. This option embeds the images in the text instead. Run it as
one line:

```sh
python -c "from markitdown import MarkItDown; r = MarkItDown(enable_plugins=True).convert('demo-single.mdz', keep_data_uris=True); open('single.md', 'w', encoding='utf-8').write(r.markdown)"
```

- [ ] **Expected:** a new `single.md` file. The image link now starts with
  `data:image/png;base64,` followed by a long run of characters.
- [ ] **Optional:** open `single.md` in a Markdown viewer (VS Code's
  preview, for example). The picture shows.

### 1.7 Title

```sh
python -c "from markitdown import MarkItDown; print(MarkItDown(enable_plugins=True).convert('demo-single.mdz').title)"
```

- [ ] **Expected:** `Single-Document Sample`

## Part 2: Making `.mdz` files

### 2.1 Word to `.mdz`

```sh
markitdown-mdz report.docx
```

- [ ] **Expected:** a message like `Wrote report.mdz: report.md + 3 images`,
  where the number matches the pictures in your document.
- [ ] **Expected:** a new `report.mdz` file in your folder.

### 2.2 Look inside it

Make a copy of `report.mdz`, rename the copy to `report.zip`, and open it
like any ZIP file.

- [ ] **Expected:** `manifest.json`, `report.md`, and an `images` folder
  holding `image-001.png` (or `.jpg`) and so on.
- [ ] **Expected:** the pictures in `images` are the ones from your Word
  file.

### 2.3 Read it back

```sh
markitdown --use-plugins report.mdz
```

- [ ] **Expected:** your document's text, with image links like
  `![...](images/image-001.png)`.

### 2.4 Open it in an MDZip viewer

Open `report.mdz` in the [online editor](https://mdzip.org/editor.html), or
in MDZip Studio or VS Code if you have them.

- [ ] **Expected:** the document displays with its pictures in place.

### 2.5 PowerPoint, with a chosen name and title

```sh
markitdown-mdz slides.pptx -o deck.mdz --title "My Test Deck"
```

- [ ] **Expected:** `Wrote deck.mdz: ...` and a new `deck.mdz` file.
- [ ] **Expected:** opened in a viewer as in 2.4, the slide text and pictures
  appear, and the title shows as "My Test Deck".

### 2.6 It won't overwrite by accident

Run the command from 2.1 again:

```sh
markitdown-mdz report.docx
```

- [ ] **Expected:** an error saying `report.mdz already exists (use --force
  to overwrite)`. The existing file is unchanged.

```sh
markitdown-mdz report.docx --force
```

- [ ] **Expected:** it succeeds and replaces `report.mdz`.

### 2.7 A web page

```sh
markitdown-mdz https://en.wikipedia.org/wiki/Markdown -o wiki.mdz
```

- [ ] **Expected:** `Wrote wiki.mdz: ...` Open it in a viewer: the article
  text is there. Pictures linked from other sites stay as web links, not
  files in `images`, which is expected.

### 2.8 A file it can't read

```sh
markitdown-mdz does-not-exist.docx
```

- [ ] **Expected:** a short error message starting with `markitdown-mdz:`,
  not a long crash report.

## Part 3: Your own files (optional)

Try any other files you have: a long Word document, a deck with many
pictures, an HTML page saved from a browser, a PDF. PDFs come through as
text only, with no pictures, which is expected.

- [ ] **Expected:** every conversion finishes, and the result opens in a
  viewer with its pictures.

## Reporting problems

For each failed check, note:

- the test number (for example, 2.5)
- the exact command you ran
- what you expected and what you saw, with any error text copied in full
- your operating system and Python version (`python --version`)
- the file you used, if you can share it

Post your results in
[Test reports](https://github.com/orgs/mdzip-project/discussions/categories/test-reports)
(a free GitHub account is needed). A report where everything passed is useful
too.
