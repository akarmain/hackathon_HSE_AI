from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from playwright.sync_api import sync_playwright
except Exception:  # noqa: BLE001
    sync_playwright = None


class SlideRenderer:
    def __init__(self, width: int = 1280, height: int = 720, scale: int = 2) -> None:
        self._width = width
        self._height = height
        self._scale = scale

    def render(
        self,
        output_path: Path,
        html: str,
        *,
        fallback_title: str,
        fallback_text: str,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._render_playwright(html=html, output_path=output_path)
        except Exception:  # noqa: BLE001
            self._render_fallback(
                output_path=output_path,
                title=fallback_title,
                text=fallback_text,
            )

    def _render_playwright(self, html: str, output_path: Path) -> None:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not available.")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": self._width, "height": self._height},
                device_scale_factor=self._scale,
            )
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()

    def _render_fallback(self, output_path: Path, title: str, text: str) -> None:
        canvas = Image.new("RGB", (self._width, self._height), color=(14, 17, 35))
        draw = ImageDraw.Draw(canvas)
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

        draw.rectangle((0, 0, self._width, 110), fill=(34, 47, 102))
        draw.text((42, 42), title[:140], font=title_font, fill=(255, 255, 255))
        draw.text((42, 160), text[:900], font=body_font, fill=(238, 240, 255))

        canvas.save(output_path, format="PNG")
