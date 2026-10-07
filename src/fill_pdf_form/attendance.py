import csv
import re
import unicodedata
from datetime import date
from pathlib import Path

CERTIFIED_REPORT_COLUMNS = (
    "atividade_id",
    "slug",
    "atividade",
    "nome",
    "email",
    "check_in",
    "assinado",
    "motivo",
    "arquivo_certificado",
)
NON_CERTIFIED_REPORT_COLUMNS = CERTIFIED_REPORT_COLUMNS[:-2]


def _read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or ())
        missing = required_columns - columns
        if missing:
            raise ValueError(f"{path} is missing CSV columns: {', '.join(sorted(missing))}")
        return [
            {column: (value or "").strip() for column, value in row.items() if column}
            for row in reader
        ]


def _is_true(value: str) -> bool:
    return value.strip().casefold() == "true"


def _parse_hours(value: str) -> float:
    if ":" in value:
        hour, minute = value.split(":", maxsplit=1)
        return float(hour) + float(minute) / 60
    return float(value.replace(",", "."))


def _format_hours(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _person_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_") or "pessoa"


def _certificate_record(activity: dict[str, str], name: str) -> dict[str, str]:
    slug_date = activity["slug"][:8]
    try:
        certificate_date = date.fromisoformat(
            f"{slug_date[:4]}-{slug_date[4:6]}-{slug_date[6:8]}"
        )
        start = _parse_hours(activity["hora_inicio"])
        end = _parse_hours(activity["hora_termino"])
    except ValueError as error:
        raise ValueError(
            f"Invalid date or time in activity {activity['id']}: {error}"
        ) from error

    duration = end - start
    if duration <= 0:
        raise ValueError(f"Activity {activity['id']} must end after it starts")
    return {
        "atividade": activity["atividade"],
        "nome_sobrenome": name,
        "data": certificate_date.strftime("%d/%m/%Y"),
        "hora": _format_hours(start),
        "carga_horaria": _format_hours(duration),
    }


def load_attendance(
    activities_csv: Path, attendees_csv: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[tuple[dict[str, str], str]]]:
    activity_columns = {
        "id",
        "atividade",
        "dia",
        "hora_inicio",
        "hora_termino",
        "slug",
    }
    activities = _read_csv(activities_csv, activity_columns)
    attendees = _read_csv(
        attendees_csv,
        {"codigo", "nome", "email", "check_in", "assinado"},
    )
    if not activities:
        raise ValueError("The activities CSV must contain at least one activity")
    if not attendees:
        raise ValueError("The attendees CSV must contain at least one person")

    activities_by_id = {}
    for row_number, activity in enumerate(activities, start=2):
        activity_id = activity["id"]
        if not activity_id or not activity["slug"]:
            continue
        if activity_id in activities_by_id:
            raise ValueError(f"Duplicate activity id in {activities_csv}: {activity_id}")
        if "/" in activity["slug"] or "\\" in activity["slug"]:
            raise ValueError(f"Unsafe activity slug in row {row_number}: {activity['slug']}")
        activities_by_id[activity_id] = activity

    recipients = []
    non_recipients = []
    certificate_jobs = []
    for row_number, attendee in enumerate(attendees, start=2):
        activity_id = attendee["codigo"]
        activity = activities_by_id.get(activity_id)
        has_check_in = _is_true(attendee["check_in"])
        has_signed = _is_true(attendee["assinado"])
        eligible = has_check_in or has_signed
        report_record = {
            "atividade_id": activity_id,
            "slug": activity["slug"] if activity else "",
            "atividade": activity["atividade"] if activity else "",
            "nome": attendee["nome"],
            "email": attendee["email"],
            "check_in": attendee["check_in"],
            "assinado": attendee["assinado"],
        }

        if not eligible:
            non_recipients.append(report_record)
            continue
        if activity is None:
            raise ValueError(
                f"{attendees_csv}, row {row_number}: no activity found for codigo {activity_id!r}"
            )
        if not attendee["nome"]:
            raise ValueError(f"{attendees_csv}, row {row_number}: nome cannot be empty")
        required_activity_values = ("atividade", "hora_inicio", "hora_termino")
        missing_values = [
            column for column in required_activity_values if not activity[column]
        ]
        if missing_values:
            raise ValueError(
                f"Activity {activity_id} is missing: {', '.join(missing_values)}"
            )

        filename = f"{activity['slug']}-{_person_slug(attendee['nome'])}.pdf"
        reasons = [
            flag
            for flag, is_set in (("check_in", has_check_in), ("assinado", has_signed))
            if is_set
        ]
        recipients.append(
            {
                **report_record,
                "motivo": ";".join(reasons),
                "arquivo_certificado": filename,
            }
        )
        certificate_jobs.append(
            (_certificate_record(activity, attendee["nome"]), filename)
        )

    return recipients, non_recipients, certificate_jobs


def write_reports(
    output_dir: Path,
    recipients: list[dict[str, str]],
    non_recipients: list[dict[str, str]],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    recipients_path = output_dir / "certificados.csv"
    non_recipients_path = output_dir / "sem_certificado.csv"
    for path, records, columns in (
        (recipients_path, recipients, CERTIFIED_REPORT_COLUMNS),
        (non_recipients_path, non_recipients, NON_CERTIFIED_REPORT_COLUMNS),
    ):
        with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)
    return recipients_path, non_recipients_path