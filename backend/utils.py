import requests
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from typing import List
from .models import Expense


def get_usd_rate() -> float:
    """
    Отримує поточний курс USD/UAH з офіційного API НБУ.
    """
    url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&json"
    try:
        response = requests.get(url)
        data = response.json()
        return float(data[0]["rate"])
    except Exception:
        return 38.0


def generate_expenses_excel(expenses: List[Expense]) -> bytes:
    """
    Генерує .xlsx-файл у вигляді байтів, щоб повернути користувачеві.
    """
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "Expenses"

    # Заголовки
    headers = ["ID", "Назва", "Дата", "Сума (UAH)", "Сума (USD)"]
    ws.append(headers)

    for exp in expenses:
        ws.append([
            exp.id,
            exp.title,
            exp.date.strftime("%d.%m.%Y"),
            exp.amount_uah,
            exp.amount_usd,
        ])

    # Зберігаємо в пам'ять
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    return output.getvalue()

