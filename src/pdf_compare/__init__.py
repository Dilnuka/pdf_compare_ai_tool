"""pdf_compare package

Contains baseline and pro comparison pipelines and shared utilities.
"""

from .baseline import compare_pdfs  # noqa: F401
from .pro import compare_pdfs_pro  # noqa: F401
from .visual import render_page_pair_png, merge_side_by_side  # noqa: F401

__all__ = [
	"compare_pdfs",
	"compare_pdfs_pro",
	"render_page_pair_png",
	"merge_side_by_side",
]
