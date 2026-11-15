"""Offline unit coverage for the generated NASSIT contribution workpaper."""
import io
import zipfile
from xml.etree import ElementTree

from routers.compliance import _build_nassit_xlsx


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _cells(row):
    values = {}
    for cell in row.findall("x:c", NS):
        if cell.get("t") == "inlineStr":
            value = "".join(cell.find("x:is", NS).itertext())
        else:
            element = cell.find("x:v", NS)
            value = element.text if element is not None else ""
        values[cell.get("r")] = value
    return values


def test_nassit_workpaper_matches_published_fields_and_totals():
    run = {
        "period": "2026-11",
        "slips": [{
            "employee_id": "employee-1",
            "employee_nassit_member_name": "Mariama K. Sesay",
            "employee_nassit_no": "SS-001234",
            "basic": 1200.0,
            "nassit_employer": 120.0,
            "nassit_employee": 60.0,
        }],
    }
    company = {
        "name": "Salone Example Ltd",
        "address": "Freetown, Sierra Leone",
        "nassit_employer": "ER-001",
    }

    payload = _build_nassit_xlsx(run, [], company, "Bank transfer")
    with zipfile.ZipFile(io.BytesIO(payload)) as workbook:
        sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))

    rows = {
        row.get("r"): _cells(row)
        for row in sheet.findall(".//x:row", NS)
    }
    all_text = " ".join(
        text for row in rows.values() for text in row.values()
    )

    assert rows["1"]["A1"] == "Name of Employer"
    assert rows["2"]["A2"] == "ER Number"
    assert rows["4"]["A4"] == "Address of Employer"
    assert rows["5"]["A5"] == "Method of Payment"
    assert rows["5"]["B5"] == "Bank transfer"
    assert rows["7"]["B7"] == "Member Name (as on SS card)"
    assert rows["7"]["C7"] == "SS Number"
    assert rows["7"]["E7"] == "Employer 10% (Le)"
    assert rows["7"]["F7"] == "Employee 5% (Le)"
    assert rows["7"]["G7"] == "Total 15% (Le)"
    assert rows["8"]["B8"] == "Mariama K. Sesay"
    assert rows["8"]["C8"] == "SS-001234"
    assert rows["8"]["D8"] == "1200.00"
    assert rows["8"]["E8"] == "120.00"
    assert rows["8"]["F8"] == "60.00"
    assert rows["8"]["G8"] == "180.00"
    assert rows["10"]["A10"] == "TOTAL"
    assert rows["10"]["G10"] == "180.00"
    assert "Employee Staff Number" not in all_text
