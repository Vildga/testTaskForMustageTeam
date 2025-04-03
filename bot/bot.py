import asyncio
import os
import logging
import datetime
from io import BytesIO

import requests

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
    BufferedInputFile
)
from openpyxl.workbook import Workbook

# --------------------- LOGGING SETUP --------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# --------------------- ENV VARIABLES ---------------------- #
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class AddExpenseState(StatesGroup):
    """Стан FSM для покрокового додавання витрати."""
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_amount = State()


class ReportPeriodState(StatesGroup):
    """Стан FSM для отримання звіту (дата початку і кінця)."""
    waiting_for_start = State()
    waiting_for_end = State()


class DeleteExpenseState(StatesGroup):
    """Стан FSM для видалення статті (введення ID)."""
    waiting_for_id = State()


class EditExpenseState(StatesGroup):
    """Стан FSM для редагування статті """
    waiting_for_id = State()
    waiting_for_choice = State()
    waiting_for_new_title = State()
    waiting_for_new_amount = State()


class ReportPeriodChoice(StatesGroup):
    """Стан FSM для вибору періоду звіту"""
    choosing_mode = State()


# --------------------- KEYBOARD ------------------


def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Головне меню з чотирма кнопками.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Додати статтю витрат"),
                KeyboardButton(text="📊 Отримати звіт за період")
            ],
            [
                KeyboardButton(text="❌ Видалити статтю"),
                KeyboardButton(text="✏️ Редагувати статтю")
            ]],
        resize_keyboard=True
    )


def get_date_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавіатура з двома кнопками: "Сьогодні", "Вчора".
    Користувач все одно може ввести дату вручну (dd.mm.yyyy),
    не натискаючи жодної кнопки.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 сьогодні"), KeyboardButton(text="📆 вчора")]
        ],
        resize_keyboard=True
    )


def get_report_period_keyboard() -> ReplyKeyboardMarkup:
    """
    Повертає клавіатуру з чотирма кнопками:
    - Останній місяць
    - Останні 3 місяці
    - Увесь час
    - Ввести дати вручну
    """
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🗓️ Останній місяць"),
                KeyboardButton(text="📉 Останні 3 місяці")
            ],
            [
                KeyboardButton(text="🕓 Увесь час"),
                KeyboardButton(text="✍️ Ввести дати вручну")
            ],
            [
                KeyboardButton(text="🔙 Вихід")
            ]
        ],
        resize_keyboard=True
    )
    return kb


def get_edit_options_keyboard() -> ReplyKeyboardMarkup:
    """
    Повертає клавіатуру з трьома кнопками:
    - Редагувати назву
    - Редагувати суму
    - Вихід
    """
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Редагувати назву")],
            [KeyboardButton(text="📆 Редагувати суму")],
            [KeyboardButton(text="🔙 Вихід")]
        ],
        resize_keyboard=True
    )
    return kb


# --------------------- HANDLERS ------------------


def register_handlers(dp: Dispatcher):
    """
    Функція, де зібрані всі хендлери бота:
    1. /start
    2. Додати статтю витрат (із можливістю обрати "Сьогодні"/"Вчора")
    3. Отримати звіт за період (із можливістю обрати за "місяць" / "3 місяці" / "весь час" / "кастомний період")
    4. Видалити статтю
    5. Редагувати статтю
    """

    # =============== ХЕНДЛЕР /start ================= #
    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        """
        На команду /start виводимо вітальне повідомлення й показуємо головне меню.
        """
        await state.clear()
        await message.answer(
            "👋 Ласкаво просимо! Оберіть дію з меню нижче ⬇️",
            reply_markup=get_main_menu()
        )

    #  ---------------- ДОДАТИ СТАТТЮ ВИТРАТ (ADD EXPENSE) -----------------------

    # Користувач натискає "Додати статтю витрат"
    @dp.message(F.text == "➕ Додати статтю витрат")
    async def add_expense_start(message: Message, state: FSMContext):
        """
        Початок сценарію додавання витрати.
        """
        await message.answer("📝 Введіть назву витрати:")
        await state.set_state(AddExpenseState.waiting_for_title)

    # Користувач вводить назву
    @dp.message(StateFilter(AddExpenseState.waiting_for_title))
    async def get_expense_title(message: Message, state: FSMContext):
        await state.update_data(title=message.text)
        await message.answer(
            "📆 Оберіть дату кнопкою або введіть вручну у форматі dd.mm.yyyy",
            reply_markup=get_date_keyboard()
        )
        await state.set_state(AddExpenseState.waiting_for_date)

    # Користувач обирає "Сьогодні"/"Вчора" або вводить дату вручну
    @dp.message(StateFilter(AddExpenseState.waiting_for_date))
    async def get_expense_date(message: Message, state: FSMContext):
        text = message.text.strip().lower()
        today = datetime.date.today()
        if text == "📅 сьогодні":
            d = today
        elif text == "📆 вчора":
            d = today - datetime.timedelta(days=1)
        else:
            try:
                d = datetime.datetime.strptime(text, "%d.%m.%Y").date()
            except ValueError:
                await message.answer(
                    "❌ Невірний формат дати! Спробуйте ще раз у форматі dd.mm.yyyy або натисніть кнопку нижче. ⬇️")
                return

        await state.update_data(date=str(d))

        await message.answer(
            "💸 Введіть суму витрат у гривнях (UAH):",
            reply_markup=get_main_menu()
        )
        await state.set_state(AddExpenseState.waiting_for_amount)

    # Користувач вводить суму
    @dp.message(StateFilter(AddExpenseState.waiting_for_amount))
    async def get_expense_amount(message: Message, state: FSMContext):
        try:
            amount = float(message.text.replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Невірний формат суми. Спробуйте ще раз.")
            return

        data = await state.get_data()
        title = data["title"]
        date_ = data["date"]
        user_id = message.from_user.id

        expense_payload = {
            "user_id": user_id,
            "title": title,
            "date": date_,
            "amount_uah": amount
        }

        try:
            r = requests.post(f"{API_BASE_URL}/expenses/", json=expense_payload)
            if r.status_code in (200, 201):
                await message.answer(
                    "✅ Витрату успішно додано! ",
                    reply_markup=get_main_menu()
                )
            else:
                await message.answer(
                    "❌ Не вдалося додати витрату. Спробуйте ще раз або пізніше 😔",
                    reply_markup=get_main_menu()
                )
        except Exception as e:
            await message.answer(
                f"⚠️ Сталася помилка при зверненні до API: щось пішло не так.",
                reply_markup=get_main_menu()
            )

        await state.clear()

    #  -------------- ОТРИМАТИ ЗВІТ ЗА ПЕРІОД (REPORT PERIOD) ----------------------

    @dp.message(F.text == "📊 Отримати звіт за період")
    async def choose_report_mode(message: Message, state: FSMContext):
        await message.answer(
            "Виберіть період або натисніть «Ввести дати вручну»:",
            reply_markup=get_report_period_keyboard()
        )
        await state.set_state(ReportPeriodChoice.choosing_mode)

    @dp.message(StateFilter(ReportPeriodChoice.choosing_mode))
    async def process_report_choice(message: Message, state: FSMContext):
        choice = message.text.strip().lower()
        user_id = message.from_user.id

        today = datetime.date.today()
        start_dt = None
        end_dt = today

        if choice == "🗓️ останній місяць":
            start_dt = today - datetime.timedelta(days=30)
        elif choice == "📉 останні 3 місяці":
            start_dt = today - datetime.timedelta(days=90)
        elif choice == "🕓 увесь час":
            start_dt = datetime.date(2000, 1, 1)
        elif choice == "✍️ ввести дати вручну":
            await message.answer("Введіть дату початку періоду (dd.mm.yyyy):", reply_markup=None)
            await state.set_state(ReportPeriodState.waiting_for_start)
            return
        elif choice == "🔙 вихід":
            await message.answer("🔙 Повертаємось у головне меню. Оберіть наступну дію 👇", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer(
                "🔘 Оберіть один із варіантів кнопок нижче або введіть 'Ввести дати вручну' для більшої гнучкості.")
            return

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        report_url = f"{API_BASE_URL}/expenses/report/?user_id={user_id}&start_date={start_str}&end_date={end_str}"
        try:
            resp_report = requests.get(report_url)
            if resp_report.status_code == 200:
                file_bytes = resp_report.content
                doc = BufferedInputFile(
                    file=file_bytes,
                    filename="report.xlsx"
                )
                await message.answer_document(
                    document=doc,
                    caption=f"Ваш звіт за період: {choice.capitalize()}."
                )
                resp_list = requests.get(
                    f"{API_BASE_URL}/expenses/?user_id={user_id}&start_date={start_str}&end_date={end_str}"
                )
                if resp_list.status_code == 200:
                    expenses_json = resp_list.json()
                    total = sum(item["amount_uah"] for item in expenses_json)
                    await message.answer(f"💸 Загальна сума витрат: {total} UAH.")
                else:
                    await message.answer("❌ Помилка при отриманні загальної суми. Спробуйте ще раз.")
            else:
                await message.answer("⚠️ Не вдалося отримати звіт із сервера.")
        except Exception as e:
            await message.answer(f"❗ Сталася помилка при отриманні звіту")

        await message.answer("🔙 Повертаємось у головне меню...", reply_markup=get_main_menu())
        await state.clear()

    # Старий сценарій «Введення дат вручну»

    @dp.message(StateFilter(ReportPeriodState.waiting_for_start))
    async def process_report_start_date(message: Message, state: FSMContext):

        try:
            d_start = datetime.datetime.strptime(message.text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("❌ Невірний формат дати. Спробуйте ще раз (dd.mm.yyyy).")
            return

        await state.update_data(report_start_date=str(d_start))
        await message.answer("📅 Введіть дату кінця періоду (dd.mm.yyyy):")
        await state.set_state(ReportPeriodState.waiting_for_end)

    @dp.message(StateFilter(ReportPeriodState.waiting_for_end))
    async def process_report_end_date(message: Message, state: FSMContext):
        try:
            d_end = datetime.datetime.strptime(message.text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("❌ Невірний формат дати. Спробуйте ще раз (dd.mm.yyyy).")
            return

        data = await state.get_data()
        d_start = data["report_start_date"]
        user_id = message.from_user.id

        try:
            report_url = (
                f"{API_BASE_URL}/expenses/report/?user_id={user_id}"
                f"&start_date={d_start}&end_date={str(d_end)}"
            )
            resp_report = requests.get(report_url)
            if resp_report.status_code == 200:
                file_bytes = resp_report.content

                doc = BufferedInputFile(
                    file=file_bytes,
                    filename="report.xlsx"
                )

                await message.answer_document(
                    document=doc,
                    caption="📊 Ось ваш звіт за обраний період:"
                )

                resp_list = requests.get(
                    f"{API_BASE_URL}/expenses/?user_id={user_id}"
                    f"&start_date={d_start}&end_date={str(d_end)}"
                )
                if resp_list.status_code == 200:
                    expenses_json = resp_list.json()
                    total = sum(item["amount_uah"] for item in expenses_json)
                    await message.answer(f"💰 Загальна сума витрат за обраний період: {total} UAH.")
                else:
                    await message.answer("❌ Помилка при отриманні загальної суми. Спробуйте ще раз пізніше.")
            else:
                await message.answer("❗ Сталася помилка при отриманні звіту")
        except Exception as e:
            await message.answer(f"⚠️ Не вдалося отримати звіт із сервера.")

        await message.answer("🔙 Повертаємось у головне меню...", reply_markup=get_main_menu())
        await state.clear()

    #  ----------------- ВИДАЛИТИ СТАТТЮ ВИТРАТ (DELETE EXPENSE)----------------

    @dp.message(F.text == "❌ Видалити статтю")
    async def delete_expense_cmd(message: Message, state: FSMContext):
        user_id = message.from_user.id
        url = f"{API_BASE_URL}/expenses/?user_id={user_id}"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                expenses_list = r.json()
                if not expenses_list:
                    await message.answer(
                        "😞 У вас поки що немає витрат. Додайте нову витрату, натиснувши 'Додати статтю витрат'.")
                    return

                from openpyxl import Workbook
                from io import BytesIO
                wb = Workbook()
                ws = wb.active
                ws.title = "All Expenses"
                ws.append(["ID", "Title", "Date", "UAH", "USD"])
                for exp in expenses_list:
                    ws.append([
                        exp["id"],
                        exp["title"],
                        exp["date"],
                        exp["amount_uah"],
                        exp["amount_usd"]
                    ])
                bio = BytesIO()
                wb.save(bio)
                bio.seek(0)

                bio.seek(0)
                file_bytes = bio.read()

                xlsx_file = BufferedInputFile(
                    file=file_bytes,
                    filename="all_expenses.xlsx"
                )

                await message.answer_document(
                    document=xlsx_file,
                    caption="📊 Список усіх витрат із їх ID:"
                )
                await message.answer("🗑️ Введіть ID статті, яку потрібно видалити:")
                await state.set_state(DeleteExpenseState.waiting_for_id)
            else:
                await message.answer("❗ Не вдалося отримати список витрат.")
        except Exception as e:
            await message.answer(f"⚠️ Сталася помилка при зверненні до API: {e}")

    @dp.message(StateFilter(DeleteExpenseState.waiting_for_id))
    async def process_delete_expense_id(message: Message, state: FSMContext):
        try:
            exp_id = int(message.text)
        except ValueError:
            await message.answer("Введіть коректний ID (число).")
            return

        user_id = message.from_user.id
        delete_url = f"{API_BASE_URL}/expenses/{exp_id}?user_id={user_id}"
        try:
            r = requests.delete(delete_url)
            if r.status_code == 200:
                await message.answer("✅ Витрату видалено успішно!", reply_markup=get_main_menu())
            else:
                await message.answer("❗ Не вдалося видалити витрату.", reply_markup=get_main_menu())
        except Exception as e:
            await message.answer(f"❗ Помилка при видаленні: {e}", reply_markup=get_main_menu())

        await state.clear()

    # -------------- РЕДАГУВАТИ СТАТТЮ ВИТРАТ (EDIT EXPENSE) ----------------------

    @dp.message(F.text == "✏️ Редагувати статтю")
    async def edit_expense_cmd(message: Message, state: FSMContext):
        user_id = message.from_user.id
        url = f"{API_BASE_URL}/expenses/?user_id={user_id}"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                expenses_list = r.json()
                if not expenses_list:
                    await message.answer("У вас поки що немає витрат.")
                    return

                wb = Workbook()
                ws = wb.active
                ws.title = "All Expenses"
                ws.append(["ID", "Title", "Date", "UAH", "USD"])
                for exp in expenses_list:
                    ws.append([
                        exp["id"],
                        exp["title"],
                        exp["date"],
                        exp["amount_uah"],
                        exp["amount_usd"]
                    ])
                bio = BytesIO()
                wb.save(bio)
                bio.seek(0)

                file_bytes = bio.read()
                xlsx_file = BufferedInputFile(
                    file=file_bytes,
                    filename="all_expenses.xlsx"
                )

                await message.answer_document(
                    document=xlsx_file,
                    caption="Список усіх витрат із їх ID."
                )
                await message.answer("✏️ Введіть ID статті, яку потрібно редагувати:")
                await state.set_state(EditExpenseState.waiting_for_id)
            else:
                await message.answer("❗ Не вдалося отримати список витрат.")
        except Exception as e:
            await message.answer(f"❗ Сталася помилка: {e}")

    @dp.message(StateFilter(EditExpenseState.waiting_for_id))
    async def process_edit_expense_id(message: Message, state: FSMContext):
        try:
            exp_id = int(message.text)
        except ValueError:
            await message.answer("Введіть коректний ID (число).")
            return

        user_id = message.from_user.id
        url = f"{API_BASE_URL}/expenses/?user_id={user_id}"
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                expenses_list = resp.json()
                exp_found = None
                for e in expenses_list:
                    if e["id"] == exp_id:
                        exp_found = e
                        break
                if not exp_found:
                    await message.answer("❗ Не знайдено витрати з таким ID.")
                    await state.clear()
                    return

                await state.update_data(expense_id=exp_id)

                await message.answer(
                    f"Поточна інформація:\n"
                    f"Назва: {exp_found['title']}\n"
                    f"Дата: {exp_found['date']}\n"
                    f"Сума UAH: {exp_found['amount_uah']}\n\n"
                    "Оберіть, що хочете редагувати:",
                    reply_markup=get_edit_options_keyboard()
                )

                await state.set_state(EditExpenseState.waiting_for_choice)

            else:
                await message.answer("❗ Помилка при отриманні списку витрат.")
                await state.clear()
        except Exception as e:
            await message.answer(f"❗ Сталася помилка при зверненні до API: {e}")
            await state.clear()

    @dp.message(StateFilter(EditExpenseState.waiting_for_choice))
    async def process_edit_choice(message: Message, state: FSMContext):

        choice = message.text.lower()

        if choice == "📝 редагувати назву":
            await message.answer("📝 Введіть нову назву статті:", reply_markup=None)
            await state.set_state(EditExpenseState.waiting_for_new_title)
        elif choice == "📆 редагувати суму":
            await message.answer("💸 Введіть нову суму (UAH):", reply_markup=None)
            await state.set_state(EditExpenseState.waiting_for_new_amount)
        elif choice == "🔙 вихід":
            await message.answer("Повертаємось у головне меню:", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("📋 Виберіть один із пунктів меню або натисніть «Вихід».")

    @dp.message(StateFilter(EditExpenseState.waiting_for_new_title))
    async def edit_title(message: Message, state: FSMContext):
        new_title = message.text
        data = await state.get_data()
        exp_id = data["expense_id"]
        user_id = message.from_user.id

        update_payload = {"title": new_title}

        put_url = f"{API_BASE_URL}/expenses/{exp_id}?user_id={user_id}"
        try:
            r = requests.put(put_url, json=update_payload)
            if r.status_code == 200:
                await message.answer(
                    "✅ Назву оновлено успішно!",
                    reply_markup=get_main_menu()
                )
            else:
                await message.answer(
                    "❗ Не вдалося оновити назву!",
                    reply_markup=get_main_menu()
                )
        except Exception as e:
            await message.answer(
                f"❗ Сталася помилка при зверненні до API: {e}",
                reply_markup=get_main_menu()
            )

        await state.clear()

    @dp.message(StateFilter(EditExpenseState.waiting_for_new_amount))
    async def edit_amount(message: Message, state: FSMContext):
        text = message.text.replace(",", ".")
        try:
            new_amt = float(text)
        except ValueError:
            await message.answer("❗ Невірний формат суми. Спробуйте ще раз (цифри, з крапкою або комою).")
            return

        data = await state.get_data()
        exp_id = data["expense_id"]
        user_id = message.from_user.id

        update_payload = {"amount_uah": new_amt}

        put_url = f"{API_BASE_URL}/expenses/{exp_id}?user_id={user_id}"
        try:
            r = requests.put(put_url, json=update_payload)
            if r.status_code == 200:
                await message.answer(
                    "✅ Суму оновлено успішно!",
                    reply_markup=get_main_menu()
                )
            else:
                await message.answer(
                    "❗ Не вдалося оновити суму!",
                    reply_markup=get_main_menu()
                )
        except Exception as e:
            await message.answer(
                f"⚠️ Сталася помилка при зверненні до API: {e}",
                reply_markup=get_main_menu()
            )

        await state.clear()


#   ---------------- ГОЛОВНА ФУНКЦІЯ ЗАПУСКУ БОТА --------------------


async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    register_handlers(dp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
