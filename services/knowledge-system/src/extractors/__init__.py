"""
Extractors package for PLOS Knowledge System - CPU-Optimized.
Contains optimized extraction modules for various content types.
"""

from .image_extractor import ImageExtractor
from .pdf_extractor import PDFExtractor
from .web_scraper import WebScraper

__all__ = [
    "PDFExtractor",
    "WebScraper",
    "ImageExtractor",
]
