import argparse
from pathlib import Path

from fill_pdf_form.attendance import load_attendance, write_reports
from fill_pdf_form.certificate_pdf import write_certificates

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def generate_certificates(
    template: Path,
    activities_csv: Path,
    attendees_csv: Path,
    output_dir: Path,
) -> list[Path]:
    recipients, non_recipients, certificate_jobs = load_attendance(
        activities_csv, attendees_csv
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_reports(output_dir, recipients, non_recipients)
    return write_certificates(template, output_dir, certificate_jobs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate event certificates from activity and attendance CSV files."
    )
    parser.add_argument("--template", type=Path, default=PROJECT_ROOT / "template.pdf")
    parser.add_argument(
        "--activities-csv", type=Path, default=PROJECT_ROOT / "inputs/atividades.csv"
    )
    parser.add_argument(
        "--attendees-csv", type=Path, default=PROJECT_ROOT / "inputs/checkins.csv"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "generated-certificates"
    )
    args = parser.parse_args()

    generated = generate_certificates(
        args.template,
        args.activities_csv,
        args.attendees_csv,
        args.output_dir,
    )
    certificate_count = sum(path.name != "certificates-all.pdf" for path in generated)
    print(f"Generated {certificate_count} certificates in {args.output_dir}")
    print(
        f"Recipient lists: {args.output_dir / 'certificados.csv'} "
        f"and {args.output_dir / 'sem_certificado.csv'}"
    )
    for path in generated:
        print(path)