import os
import csv
import io
import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv 

# Load environment variables from .env file
load_dotenv()

# Environment variables:
# SHEET_ID   = Google Sheet ID
# SHEET_NAME = Sheet/tab name (optional, default: Sheet1)

SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")

if not SHEET_ID:
    raise RuntimeError("SHEET_ID environment variable is required")

app = FastAPI()
templates = Jinja2Templates(directory="templates")


def fetch_sheet_rows(sheet_name: str):
    """
    Fetch the sheet as CSV and return rows as list of lists.
    Sheet must be public or 'published to web'.
    Columns (A–E):
    A: رقم الهوية
    B: رقم الجلوس
    C: اسم الطالبة
    D: رقم الدور
    E: رقم اللجنة
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )
    resp = requests.get(url)
    resp.raise_for_status()

    # Decode as UTF-8 and parse CSV
    text = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    return rows


def find_student_by_id(id_number: str, sheet_name: str):
    """
    Search for a student by رقم الهوية (column A) in the specified sheet.
    Returns dict or None if not found.
    """
    rows = fetch_sheet_rows(sheet_name)
    if not rows:
        return None

    # First row = header
    header = rows[0]
    data_rows = rows[1:]

    for row in data_rows:
        if not row:
            continue

        # Safely access up to 5 columns
        id_in_sheet = row[0].strip() if len(row) > 0 and row[0] else ""

        if id_in_sheet == id_number.strip():
            return {
                "idNumber": id_in_sheet,                    # رقم الهوية
                "seatNumber": row[1].strip() if len(row) > 1 else "",
                "studentName": row[2].strip() if len(row) > 2 else "",
                "roundNumber": row[3].strip() if len(row) > 3 else "",
                "committeeNumber": row[4].strip() if len(row) > 4 else "",
            }

    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Show the search form.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "error": ""}
    )


@app.post("/", response_class=HTMLResponse)
async def search(request: Request, idNumber: str = Form(...), className: str = Form(...)):
    """
    Handle form submit: student enters رقم الهوية and selects class.
    If found ➜ show result page, else show index with error.
    """
    # Map class selection to sheet name
    class_to_sheet = {
        "1": "1",  # الصف الأول
        "2": "2",  # الصف الثاني
        "3": "3",  # الصف الثالث
    }
    
    sheet_name = class_to_sheet.get(className, "1")  # Default to sheet "1"
    
    try:
        student = find_student_by_id(idNumber, sheet_name)
    except Exception as e:
        # If the sheet is unreachable or mis-configured
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "حدث خطأ في الاتصال بقاعدة البيانات. يرجى المحاولة لاحقًا.",
                "selectedClass": className,
                "enteredId": idNumber
            }
        )

    if student is None:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "لا يوجد طالبة بهذا رقم الهوية.",
                "selectedClass": className,
                "enteredId": idNumber
            }
        )

    # Student found → show result
    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "idNumber": student["idNumber"],
            "seatNumber": student["seatNumber"],
            "studentName": student["studentName"],
            "roundNumber": student["roundNumber"],
            "committeeNumber": student["committeeNumber"],
        },
    )
