from pathlib import Path

import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDERS = {
    "nome_sobrenome": "{{nome, sobrenome}}",
    "atividade": "{{atividade}}",
}
BODY_SIZE = 18.0
MAX_LINE_WIDTH = 660.0


def _find_line(lines: list[list[dict]], marker: str) -> list[dict]:
    for spans in lines:
        if any(marker in span["text"] for span in spans):
            return spans
    raise ValueError(f"Template placeholder not found: {marker}")


def _get_lines(page: pymupdf.Page) -> list[list[dict]]:
    return [
        line["spans"]
        for block in page.get_text("dict")["blocks"]
        if "lines" in block
        for line in block["lines"]
    ]


def _font_size(
    runs: list[tuple[str, str]], fonts: dict, max_width: float, base_size: float
) -> float:
    text_width = sum(
        fonts[style].text_length(text, fontsize=base_size)
        for text, style in runs
    )
    if text_width <= max_width or text_width == 0:
        return base_size
    return max(12.0, base_size * max_width / text_width)


def _draw_centered(
    page: pymupdf.Page,
    runs: list[tuple[str, str]],
    baseline: float,
    center_x: float,
    fonts: dict,
    font_files: dict,
    colors: dict,
    max_width: float,
    base_size: float = BODY_SIZE,
) -> None:
    size = _font_size(runs, fonts, max_width, base_size)
    total_width = sum(
        fonts[style].text_length(text, fontsize=size)
        for text, style in runs
    )
    x = center_x - total_width / 2
    for text, style in runs:
        if text:
            page.insert_text(
                (x, baseline),
                text,
                fontname=f"Rajdhani-{style.title()}",
                fontfile=str(font_files[style]),
                fontsize=size,
                color=colors[style],
                overlay=True,
            )
            x += fonts[style].text_length(text, fontsize=size)


def _color_from_int(color: int) -> tuple[float, float, float]:
    return (
        ((color >> 16) & 255) / 255,
        ((color >> 8) & 255) / 255,
        (color & 255) / 255,
    )


def _certificate_document(
    template: Path,
    record: dict[str, str],
    font_files: dict[str, Path],
    fonts: dict,
) -> pymupdf.Document:
    document = pymupdf.open(template)
    page = document[0]
    lines = _get_lines(page)
    redactions = []
    insertions = []

    regular_style = next(
        span
        for spans in lines
        for span in spans
        if span["font"].endswith("Rajdhani-Regular")
    )
    fonts_by_style = {"regular": fonts["regular"], "bold": fonts["bold"]}
    files_by_style = {"regular": font_files["regular"], "bold": font_files["bold"]}
    text_color = _color_from_int(regular_style["color"])
    colors_by_style = {"regular": text_color, "bold": text_color}

    for field, marker in PLACEHOLDERS.items():
        value = record[field].strip()
        if not value:
            raise ValueError(f"Certificate field {field!r} cannot be empty")
        spans = _find_line(lines, marker)
        span = next(span for span in spans if marker in span["text"])
        redactions.append(pymupdf.Rect(span["bbox"]))
        insertions.append(
            (
                [(value, "regular" if field == "nome_sobrenome" else "bold")],
                span["origin"][1],
                page.rect.width / 2,
                22.0 if field == "nome_sobrenome" else 20.0,
            )
        )

    date_value = record["data"].strip()
    raw_time = record["hora"].strip()
    time_value = raw_time[:-1].strip() if raw_time.lower().endswith("h") else raw_time
    hours_value = record["carga_horaria"].strip()
    if not date_value or not time_value or not hours_value:
        raise ValueError("Date, time, and workload fields cannot be empty")
    try:
        hora_s = "hora." if float(hours_value.replace(",", ".")) == 1 else "horas."
    except ValueError:
        hora_s = "horas."

    date_line = _find_line(lines, "dd/mm/yyyy")
    date_rect = pymupdf.Rect(date_line[0]["bbox"])
    for span in date_line[1:]:
        date_rect |= pymupdf.Rect(span["bbox"])
    redactions.append(date_rect)
    insertions.append(
        (
            [
                ("no dia ", "regular"),
                (date_value, "regular"),
                (" às ", "regular"),
                (time_value, "regular"),
                ("h,", "regular"),
            ],
            date_line[0]["origin"][1],
            page.rect.width / 2,
            BODY_SIZE,
        )
    )

    hours_line = _find_line(lines, "hs")
    hours_rect = pymupdf.Rect(hours_line[0]["bbox"])
    for span in hours_line[1:]:
        hours_rect |= pymupdf.Rect(span["bbox"])
    redactions.append(hours_rect)
    insertions.append(
        (
            [
                ("contabilizando a carga horária de ", "regular"),
                (hours_value, "regular"),
                (f" {hora_s}", "regular"),
            ],
            hours_line[0]["origin"][1],
            page.rect.width / 2,
            BODY_SIZE,
        )
    )

    for rectangle in redactions:
        page.add_redact_annot(rectangle, fill=None, cross_out=False)
    page.apply_redactions(images=0, graphics=0)

    for runs, baseline, center_x, base_size in insertions:
        _draw_centered(
            page,
            runs,
            baseline,
            center_x,
            fonts_by_style,
            files_by_style,
            colors_by_style,
            MAX_LINE_WIDTH,
            base_size,
        )
    return document


def write_certificates(
    template: Path,
    output_dir: Path,
    certificate_jobs: list[tuple[dict[str, str], str]],
) -> list[Path]:
    font_files = {
        "regular": PROJECT_ROOT / "fonts/rajdhani/Rajdhani-Regular.ttf",
        "bold": PROJECT_ROOT / "fonts/rajdhani/Rajdhani-Bold.ttf",
    }
    fonts = {
        style: pymupdf.Font(fontfile=str(font_file))
        for style, font_file in font_files.items()
    }
    combined = pymupdf.open()
    generated = []
    output_paths = set()

    try:
        for record, filename in certificate_jobs:
            output_path = output_dir / filename
            if output_path in output_paths:
                raise ValueError(f"Duplicate certificate filename: {output_path.name}")
            certificate = _certificate_document(template, record, font_files, fonts)
            try:
                certificate.save(output_path, garbage=4, deflate=True)
                combined.insert_pdf(certificate)
            finally:
                certificate.close()
            output_paths.add(output_path)
            generated.append(output_path)

        if generated:
            combined_path = output_dir / "certificates-all.pdf"
            combined.save(combined_path, garbage=4, deflate=True)
            generated.append(combined_path)
    finally:
        combined.close()

    return generated