"""markitdown-mdzip — a MarkItDown plugin that converts MDZip (.mdz) archives to Markdown.

Install it next to MarkItDown and enable plugins:

    markitdown --use-plugins guide.mdz

    from markitdown import MarkItDown
    md = MarkItDown(enable_plugins=True)
    print(md.convert("guide.mdz").markdown)

It also goes the other way, from anything MarkItDown reads to .mdz, keeping the images:

    markitdown-mdz report.docx          # writes report.mdz

    from markitdown_mdzip import convert_to_mdz
    convert_to_mdz("report.docx").save("report.mdz")
"""

from ._converter import MdzConverter, register_converters
from ._to_mdz import MdzConversion, convert_to_mdz
from ._version import __version__

__plugin_interface_version__ = 1
"""The MarkItDown plugin interface this plugin implements."""

__all__ = [
    "__version__",
    "__plugin_interface_version__",
    "MdzConverter",
    "register_converters",
    "convert_to_mdz",
    "MdzConversion",
]
