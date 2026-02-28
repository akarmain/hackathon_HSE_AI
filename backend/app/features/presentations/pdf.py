from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def build_pdf_from_images(image_paths: list[Path], output_path: Path) -> Path:
    if not image_paths:
        raise ValueError("No images to build PDF.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = None

    for image_path in image_paths:
        with Image.open(image_path) as image:
            width_px, height_px = image.size

        width_pt = width_px * 72.0 / 96.0
        height_pt = height_px * 72.0 / 96.0

        if pdf is None:
            pdf = canvas.Canvas(str(output_path), pagesize=(width_pt, height_pt))
        else:
            pdf.setPageSize((width_pt, height_pt))

        pdf.drawImage(
            ImageReader(str(image_path)),
            0,
            0,
            width=width_pt,
            height=height_pt,
            preserveAspectRatio=True,
            mask="auto",
        )
        pdf.showPage()

    if pdf is None:
        raise ValueError("No images were rendered into PDF.")
    pdf.save()
    return output_path
