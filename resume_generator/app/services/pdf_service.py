from playwright.async_api import async_playwright
from typing import Optional
import io


class PDFGenerator:
    """
    Generate PDF from HTML using Playwright.

    Brandon's requirement: One-page PDF with exact dimensions.
    Uses Playwright's PDF generation with precise page settings.
    """

    async def generate_pdf(
        self,
        html_content: str,
        page_width: str = "8.5in",
        page_height: str = "11in"
    ) -> bytes:
        """
        Generate PDF from HTML content.

        Args:
            html_content: Rendered HTML string
            page_width: Page width (default: 8.5in for US Letter)
            page_height: Page height (default: 11in for US Letter)

        Returns:
            PDF bytes
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Set content
            await page.set_content(html_content, wait_until="networkidle")

            # Generate PDF with exact dimensions
            pdf_bytes = await page.pdf(
                format=None,  # Use custom dimensions
                width=page_width,
                height=page_height,
                print_background=True,  # CRITICAL: Print background colors/images
                margin={
                    "top": "0",
                    "bottom": "0",
                    "left": "0",
                    "right": "0"
                },
                prefer_css_page_size=False  # Use our dimensions, not CSS
            )

            await browser.close()
            return pdf_bytes

    async def validate_one_page(self, html_content: str) -> tuple[bool, Optional[int]]:
        """
        Check if content fits on one page.

        Returns:
            (fits_on_one_page, estimated_height_px)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Set viewport to match PDF dimensions (8.5in x 11in @ 96dpi)
            await page.set_viewport_size({"width": 816, "height": 1056})
            await page.set_content(html_content, wait_until="networkidle")

            # Get content height
            content_height = await page.evaluate(
                "() => document.documentElement.scrollHeight"
            )

            await browser.close()

            # One page = 1056px (11in @ 96dpi)
            fits = content_height <= 1056
            return fits, content_height
