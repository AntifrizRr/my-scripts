from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    ROOT
    / "google-apps-script"
    / "aff-partners-info"
    / "anonymized_table.xlsx"
)


def create_synthetic_workbook() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Synthetic Summary"

    worksheet.append(
        [
            "unique_key",
            "partner_name",
            "campaign_id",
            "status",
        ]
    )

    worksheet.append(
        [
            "alpha-001",
            "Example Partner",
            "CMP-100",
            "Approved",
        ]
    )

    worksheet.append(
        [
            "alpha-002",
            "Sample Partner",
            "CMP-101",
            "Pending",
        ]
    )

    worksheet.freeze_panes = "A2"
    worksheet.print_title_rows = "1:1"

    # Public-safe synthetic metadata.
    workbook.properties.creator = "Example Portfolio"
    workbook.properties.lastModifiedBy = "Example Portfolio"
    workbook.properties.title = "Synthetic Portfolio Workbook"
    workbook.properties.subject = "Portfolio Example"
    workbook.properties.description = (
        "Synthetic workbook for portfolio demonstration"
    )

    workbook.save(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    create_synthetic_workbook()