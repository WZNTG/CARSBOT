
import logging
import random
import sqlite3
import time
import asyncio

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8477161043:AAHHnvxnop0lBnSdNg22amSlqo7sQRCoTY0"
ADMIN_ID = 5394084759

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("cars_bot.db")
cursor = conn.cursor()

# ═══════════════════════════════════════
#                DATABASE
# ═══════════════════════════════════════

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    name TEXT,
    last_roll INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    pts INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cars(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    rarity INTEGER,
    pts INTEGER,
    photo TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS collection(
    user_id INTEGER,
    car_id INTEGER
)
""")

conn.commit()

# ═══════════════════════════════════════
#               CONSTANTS
# ═══════════════════════════════════════

ROLL_COOLDOWN = 14400
DAILY_COOLDOWN = 86400

RARITY_NAME = {
    1: "⚪ Common",
    2: "🔵 Rare",
    3: "🟣 Epic",
    4: "🟡 Legendary",
    5: "💎 Secret"
}

RARITY_STARS = {
    1: "★☆☆☆☆",
    2: "★★☆☆☆",
    3: "★★★☆☆",
    4: "★★★★☆",
    5: "★★★★★"
}

DUPLICATE_PTS = {1: 1, 2: 2, 3: 4, 4: 10, 5: 25}

SLOT_SYMBOLS = ["🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]

GARAGE_PAGE_SIZE = 8

# ═══════════════════════════════════════
#               HELPERS
# ═══════════════════════════════════════

def ensure_user(user_id, name):
    cursor.execute(
        "INSERT OR IGNORE INTO users(id, name) VALUES(?, ?)",
        (user_id, name)
    )
    conn.commit()

def get_random_rarity():
    roll = random.randint(1, 1000)
    if roll <= 700:   return 1
    elif roll <= 900: return 2
    elif roll <= 980: return 3
    elif roll <= 998: return 4
    else:             return 5

def format_time_left(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"

def build_car_caption(name, desc, rarity, pts, is_new=True):
    if rarity == 5:
        label = "💎💎💎 SECRET DROP 💎💎💎"
    elif rarity == 4:
        label = "🔥 ЛЕГЕНДАРНАЯ МАШИНА!"
    elif rarity == 3 and is_new:
        label = "✨ ЭПИЧЕСКАЯ МАШИНА!"
    elif is_new:
        label = "🎉 Новая машина!"
    else:
        label = "🏎 Информация о машине"

    return (
        f"{label}\n\n"
        f"🏎  <b>{name}</b>\n\n"
        f"{RARITY_NAME[rarity]}  {RARITY_STARS[rarity]}\n"
        f"⭐  <b>{pts} pts</b>\n\n"
        f"<i>{desc}</i>"
    )

# ═══════════════════════════════════════
#               COMMANDS
# ═══════════════════════════════════════

async def set_commands():
    commands = [
        types.BotCommand(command="roll",       description="🎰 Выбить машину"),
        types.BotCommand(command="garage",     description="🏎 Твой гараж"),
        types.BotCommand(command="profile",    description="👤 Профиль"),
        types.BotCommand(command="collection", description="📖 Коллекция"),
        types.BotCommand(command="daily",      description="🎁 Ежедневный бонус"),
        types.BotCommand(command="roulette",   description="🎰 Казино"),
        types.BotCommand(command="top",        description="🏆 Топ Legendary"),
        types.BotCommand(command="top_pts",    description="🏆 Топ по очкам"),
        types.BotCommand(command="shop",       description="🛒 Магазин"),
    ]
    await bot.set_my_commands(commands)

# ═══════════════════════════════════════
#                START
# ═══════════════════════════════════════

@dp.message(Command("start"))
async def start(message: types.Message):
    ensure_user(message.from_user.id, message.from_user.first_name)
    await message.answer(
        "🚗 <b>Добро пожаловать в Car Collection!</b>\n\n"
        "Выбивай машины, собирай коллекцию, соревнуйся с другими!\n\n"
        "🎰 /roll — выбить машину (раз в 4 часа)\n"
        "🏎 /garage — твой гараж\n"
        "🎁 /daily — ежедневный бонус\n"
        "👤 /profile — твой профиль",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════
#                ROLL
# ═══════════════════════════════════════

@dp.message(Command("roll"))
async def roll(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)

    cursor.execute("SELECT last_roll FROM users WHERE id=?", (user_id,))
    last = cursor.fetchone()[0]
    now = int(time.time())

    if now - last < ROLL_COOLDOWN:
        left = ROLL_COOLDOWN - (now - last)
        await message.answer(
            f"⏳ <b>Перезарядка!</b>\n\n"
            f"Следующий roll через <b>{format_time_left(left)}</b>",
            parse_mode="HTML"
        )
        return

    frames = [
        "🎰 <b>Крутим барабаны...</b>\n\n▪️▪️▪️",
        "🎰 <b>Крутим барабаны...</b>\n\n⚪▪️▪️",
        "🎰 <b>Крутим барабаны...</b>\n\n⚪🔵▪️",
        "🎰 <b>Крутим барабаны...</b>\n\n⚪🔵🟣",
        "🎰 <b>Крутим барабаны...</b>\n\n⚪🔵🟣🟡",
    ]
    msg = await message.answer(frames[0], parse_mode="HTML")
    for frame in frames[1:]:
        await asyncio.sleep(0.5)
        await msg.edit_text(frame, parse_mode="HTML")

    rarity = get_random_rarity()

    cursor.execute(
        "SELECT * FROM cars WHERE rarity=? ORDER BY RANDOM() LIMIT 1",
        (rarity,)
    )
    car = cursor.fetchone()

    if not car:
        cursor.execute("SELECT * FROM cars ORDER BY RANDOM() LIMIT 1")
        car = cursor.fetchone()

    if not car:
        await msg.edit_text("🚫 В базе нет машин. Обратитесь к администратору.")
        return

    car_id, name, desc, rarity, pts, photo = car

    cursor.execute(
        "SELECT * FROM collection WHERE user_id=? AND car_id=?",
        (user_id, car_id)
    )
    have = cursor.fetchone()

    cursor.execute("UPDATE users SET last_roll=? WHERE id=?", (now, user_id))
    conn.commit()

    if have:
        bonus = DUPLICATE_PTS[rarity]
        cursor.execute("UPDATE users SET pts=pts+? WHERE id=?", (bonus, user_id))
        conn.commit()
        await msg.edit_text(
            f"♻️ <b>Дубликат!</b>\n\n"
            f"🏎 <b>{name}</b>  {RARITY_NAME[rarity]}\n\n"
            f"Уже есть в гараже → <b>+{bonus} pts</b>",
            parse_mode="HTML"
        )
    else:
        cursor.execute("INSERT INTO collection VALUES(?,?)", (user_id, car_id))
        cursor.execute("UPDATE users SET pts=pts+? WHERE id=?", (pts, user_id))
        conn.commit()
        caption = build_car_caption(name, desc, rarity, pts, is_new=True)
        await msg.delete()
        await message.answer_photo(photo, caption=caption, parse_mode="HTML")

# ═══════════════════════════════════════
#               GARAGE
# ═══════════════════════════════════════

def build_garage_keyboard(cars, page, total_pages):
    buttons = []
    for car_id, name, rarity in cars:
        icon = RARITY_NAME[rarity].split()[0]
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {name}",
                callback_data=f"card:{car_id}"
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"garage:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"garage:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("garage"))
async def garage(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)
    await show_garage(message, user_id, page=0, edit=False)

async def show_garage(target, user_id, page=0, edit=False):
    cursor.execute("""
        SELECT cars.id, cars.name, cars.rarity
        FROM collection
        JOIN cars ON cars.id = collection.car_id
        WHERE collection.user_id=?
        ORDER BY cars.rarity DESC, cars.name
    """, (user_id,))
    all_cars = cursor.fetchall()

    if not all_cars:
        text = "🏎 <b>Гараж пуст</b>\n\nИспользуй /roll чтобы выбить первую машину!"
        if edit:
            await target.message.edit_text(text, parse_mode="HTML")
        else:
            await target.answer(text, parse_mode="HTML")
        return

    total_pages = max(1, (len(all_cars) + GARAGE_PAGE_SIZE - 1) // GARAGE_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    page_cars = all_cars[page * GARAGE_PAGE_SIZE:(page + 1) * GARAGE_PAGE_SIZE]

    counts = {r: 0 for r in range(1, 6)}
    for _, _, r in all_cars:
        counts[r] += 1

    stats = "  ".join(
        f"{RARITY_NAME[r].split()[0]}{counts[r]}"
        for r in range(5, 0, -1) if counts[r] > 0
    )

    text = (
        f"🏎 <b>Гараж</b> ({len(all_cars)} машин)\n"
        f"{stats}\n\n"
        f"<i>Нажми на машину чтобы посмотреть</i>"
    )

    kb = build_garage_keyboard(page_cars, page, total_pages)

    if edit:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("garage:"))
async def garage_page(callback: types.CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_garage(callback, callback.from_user.id, page=page, edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("card:"))
async def view_card(callback: types.CallbackQuery):
    car_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    cursor.execute(
        "SELECT * FROM collection WHERE user_id=? AND car_id=?",
        (user_id, car_id)
    )
    if not cursor.fetchone():
        await callback.answer("❌ Эта машина не в твоём гараже!", show_alert=True)
        return

    cursor.execute("SELECT * FROM cars WHERE id=?", (car_id,))
    car = cursor.fetchone()
    if not car:
        await callback.answer("❌ Машина не найдена", show_alert=True)
        return

    _, name, desc, rarity, pts, photo = car
    caption = build_car_caption(name, desc, rarity, pts, is_new=False)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад в гараж", callback_data="garage:0")
    ]])

    await callback.message.answer_photo(
        photo,
        caption=caption,
        parse_mode="HTML",
        reply_markup=back_kb
    )
    await callback.answer()

# ═══════════════════════════════════════
#               PROFILE
# ═══════════════════════════════════════

@dp.message(Command("profile"))
async def profile(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)

    cursor.execute("SELECT pts FROM users WHERE id=?", (user_id,))
    pts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM collection WHERE user_id=?", (user_id,))
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cars")
    all_total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT cars.rarity, COUNT(*) as cnt
        FROM collection
        JOIN cars ON cars.id = collection.car_id
        WHERE collection.user_id=?
        GROUP BY cars.rarity
        ORDER BY cars.rarity DESC
    """, (user_id,))
    rarity_counts = cursor.fetchall()

    rarity_text = "  ".join(
        f"{RARITY_NAME[r].split()[0]}{cnt}"
        for r, cnt in rarity_counts
    ) or "Нет машин"

    progress = int((total / all_total * 10)) if all_total > 0 else 0
    bar = "█" * progress + "░" * (10 - progress)

    text = (
        f"👤 <b>{message.from_user.first_name}</b>\n\n"
        f"🚗 Машин: <b>{total}</b> / {all_total}\n"
        f"[{bar}]\n\n"
        f"{rarity_text}\n\n"
        f"⭐ Очки: <b>{pts} pts</b>"
    )

    photos = await bot.get_user_profile_photos(user_id, limit=1)
    if photos.total_count > 0:
        photo = photos.photos[0][-1].file_id
        await message.answer_photo(photo, caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

# ═══════════════════════════════════════
#             COLLECTION
# ═══════════════════════════════════════

@dp.message(Command("collection"))
async def collection(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)

    cursor.execute("SELECT id, name, rarity FROM cars ORDER BY rarity DESC, name")
    all_cars = cursor.fetchall()

    cursor.execute("SELECT car_id FROM collection WHERE user_id=?", (user_id,))
    owned = {x[0] for x in cursor.fetchall()}

    if not all_cars:
        await message.answer("📖 Коллекция пока пуста")
        return

    lines = {r: [] for r in range(5, 0, -1)}
    for car_id, name, rarity in all_cars:
        icon = "✅" if car_id in owned else "❌"
        lines[rarity].append(f"  {icon} {name}")

    text = f"📖 <b>Коллекция</b>  ({len(owned)}/{len(all_cars)})\n"
    for r in range(5, 0, -1):
        if lines[r]:
            text += f"\n{RARITY_NAME[r]}\n" + "\n".join(lines[r]) + "\n"

    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await message.answer(text, parse_mode="HTML")

# ═══════════════════════════════════════
#               DAILY
# ═══════════════════════════════════════

@dp.message(Command("daily"))
async def daily(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)

    cursor.execute("SELECT last_daily FROM users WHERE id=?", (user_id,))
    last = cursor.fetchone()[0]
    now = int(time.time())

    if now - last < DAILY_COOLDOWN:
        left = DAILY_COOLDOWN - (now - last)
        await message.answer(
            f"⏳ Уже получено!\n\nСледующий бонус через <b>{format_time_left(left)}</b>",
            parse_mode="HTML"
        )
        return

    cursor.execute("UPDATE users SET pts=pts+5, last_daily=? WHERE id=?", (now, user_id))
    conn.commit()
    await message.answer("🎁 <b>Ежедневный бонус получен!</b>\n\n⭐ +5 pts", parse_mode="HTML")

# ═══════════════════════════════════════
#             TOP LEGENDARY
# ═══════════════════════════════════════

@dp.message(Command("top"))
async def top(message: types.Message):
    cursor.execute("""
        SELECT users.name, COUNT(*) as cnt
        FROM collection
        JOIN cars ON cars.id = collection.car_id
        JOIN users ON users.id = collection.user_id
        WHERE cars.rarity = 4
        GROUP BY users.id
        ORDER BY cnt DESC
        LIMIT 10
    """)
    players = cursor.fetchall()

    if not players:
        await message.answer("🏆 Пока никто не выбил Legendary")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ по Legendary</b>\n\n"
    for i, (name, count) in enumerate(players):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {name} — <b>{count}</b> 🟡\n"

    await message.answer(text, parse_mode="HTML")

# ═══════════════════════════════════════
#              TOP PTS
# ═══════════════════════════════════════

@dp.message(Command("top_pts"))
async def top_pts(message: types.Message):
    cursor.execute("SELECT name, pts FROM users ORDER BY pts DESC LIMIT 10")
    players = cursor.fetchall()

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ по очкам</b>\n\n"
    for i, (name, pts) in enumerate(players):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {name} — <b>{pts} pts</b>\n"

    await message.answer(text, parse_mode="HTML")

# ═══════════════════════════════════════
#               SHOP
# ═══════════════════════════════════════

@dp.message(Command("shop"))
async def shop(message: types.Message):
    await message.answer(
        "🛒 <b>Магазин</b>\n\n"
        "🎰 <b>Казино рулетка</b> — 300 pts\n"
        "Три 7️⃣ — выигрываешь Legendary или Secret!\n\n"
        "👉 /roulette",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════
#              ROULETTE
# ═══════════════════════════════════════

@dp.message(Command("roulette"))
async def roulette(message: types.Message):
    user_id = message.from_user.id
    ensure_user(user_id, message.from_user.first_name)

    cursor.execute("SELECT pts FROM users WHERE id=?", (user_id,))
    pts = cursor.fetchone()[0]

    if pts < 300:
        await message.answer(
            f"❌ Недостаточно очков!\n\nНужно: <b>300 pts</b>\nУ тебя: <b>{pts} pts</b>",
            parse_mode="HTML"
        )
        return

    cursor.execute("UPDATE users SET pts=pts-300 WHERE id=?", (user_id,))
    conn.commit()

    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]

    msg = await message.answer("🎰 <b>Казино</b>\n\n❓ ❓ ❓", parse_mode="HTML")
    await asyncio.sleep(0.8)
    await msg.edit_text(f"🎰 <b>Казино</b>\n\n{reels[0]} ❓ ❓", parse_mode="HTML")
    await asyncio.sleep(0.8)
    await msg.edit_text(f"🎰 <b>Казино</b>\n\n{reels[0]} {reels[1]} ❓", parse_mode="HTML")
    await asyncio.sleep(0.8)
    await msg.edit_text(f"🎰 <b>Казино</b>\n\n{reels[0]} {reels[1]} {reels[2]}", parse_mode="HTML")
    await asyncio.sleep(0.4)

    if reels[0] == reels[1] == reels[2] == "7️⃣":
        prize_rarity = random.choice([4, 5])
        cursor.execute(
            "SELECT * FROM cars WHERE rarity=? ORDER BY RANDOM() LIMIT 1",
            (prize_rarity,)
        )
        car = cursor.fetchone()

        if car:
            car_id, name, desc, rarity, car_pts, photo = car
            cursor.execute(
                "SELECT * FROM collection WHERE user_id=? AND car_id=?",
                (user_id, car_id)
            )
            have = cursor.fetchone()

            if have:
                bonus = DUPLICATE_PTS[rarity]
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?", (bonus, user_id))
                conn.commit()
                await msg.edit_text(
                    f"🎰 <b>7️⃣ 7️⃣ 7️⃣ ДЖЕКПОТ!</b>\n\n♻️ {name} уже есть → <b>+{bonus} pts</b>",
                    parse_mode="HTML"
                )
            else:
                cursor.execute("INSERT INTO collection VALUES(?,?)", (user_id, car_id))
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?", (car_pts, user_id))
                conn.commit()
                await msg.delete()
                caption = "🎰 <b>7️⃣ 7️⃣ 7️⃣ ДЖЕКПОТ!</b>\n\n" + build_car_caption(name, desc, rarity, car_pts)
                await message.answer_photo(photo, caption=caption, parse_mode="HTML")
        else:
            await msg.edit_text("🎰 <b>7️⃣ 7️⃣ 7️⃣ ДЖЕКПОТ!</b>\n\nНо машин нет в базе 😢", parse_mode="HTML")
    else:
        await msg.edit_text(
            f"🎰 <b>Казино</b>\n\n{reels[0]} {reels[1]} {reels[2]}\n\n"
            f"❌ Не повезло! Нужно 7️⃣ 7️⃣ 7️⃣\n\n<i>Попробуй снова — /roulette</i>",
            parse_mode="HTML"
        )

# ═══════════════════════════════════════
#            ADMIN: ADD CAR
# ═══════════════════════════════════════

admin_state = {}

@dp.message(Command("add"))
async def add(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    admin_state[message.from_user.id] = "photo"
    await message.answer("📸 <b>Добавление машины</b>\n\nОтправь фото машины", parse_mode="HTML")

@dp.message(Command("delete_car"))
async def delete_car(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        car_id = int(message.text.split()[1])
    except:
        await message.answer("Используй: /delete_car &lt;ID&gt;", parse_mode="HTML")
        return

    cursor.execute("SELECT name FROM cars WHERE id=?", (car_id,))
    car = cursor.fetchone()
    if not car:
        await message.answer("❌ Машина не найдена")
        return

    cursor.execute("DELETE FROM cars WHERE id=?", (car_id,))
    cursor.execute("DELETE FROM collection WHERE car_id=?", (car_id,))
    conn.commit()
    await message.answer(f"✅ Машина <b>{car[0]}</b> удалена", parse_mode="HTML")

@dp.message(Command("admin_reset"))
async def admin_reset(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("DELETE FROM collection WHERE user_id=?", (message.from_user.id,))
    cursor.execute("UPDATE users SET last_roll=0, pts=0 WHERE id=?", (message.from_user.id,))
    conn.commit()
    await message.answer("🧹 Сброс выполнен")

@dp.message(Command("cars_list"))
async def cars_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT id, name, rarity, pts FROM cars ORDER BY rarity DESC")
    cars = cursor.fetchall()
    if not cars:
        await message.answer("База пуста")
        return
    text = "📋 <b>Все машины в базе:</b>\n\n"
    for car_id, name, rarity, pts in cars:
        text += f"<code>ID:{car_id}</code>  {RARITY_NAME[rarity]}  {name}  ({pts} pts)\n"
    await message.answer(text, parse_mode="HTML")

@dp.message()
async def process_add(message: types.Message):
    if message.from_user.id not in admin_state:
        return

    state = admin_state[message.from_user.id]

    if state == "photo":
        if not message.photo:
            await message.answer("Нужно фото!")
            return
        photo = message.photo[-1].file_id
        admin_state[message.from_user.id] = {"photo": photo}
        await message.answer(
            "Теперь отправь данные в формате:\n\n"
            "<code>Название | Описание | Редкость (1-5) | Очки</code>\n\n"
            "1=Common  2=Rare  3=Epic  4=Legendary  5=Secret",
            parse_mode="HTML"
        )
    else:
        data = message.text.split("|")
        if len(data) != 4:
            await message.answer("❌ Неверный формат. Нужно 4 части разделённые |")
            return
        try:
            name = data[0].strip()
            desc = data[1].strip()
            rarity = int(data[2].strip())
            pts = int(data[3].strip())
        except:
            await message.answer("❌ Ошибка. Проверь редкость и очки (числа)")
            return

        if rarity not in range(1, 6):
            await message.answer("❌ Редкость: от 1 до 5")
            return

        photo = admin_state[message.from_user.id]["photo"]
        cursor.execute(
            "INSERT INTO cars(name, description, rarity, pts, photo) VALUES(?,?,?,?,?)",
            (name, desc, rarity, pts, photo)
        )
        conn.commit()
        admin_state.pop(message.from_user.id)

        await message.answer(
            f"✅ <b>Машина добавлена!</b>\n\n🏎 {name}\n{RARITY_NAME[rarity]}  ⭐ {pts} pts",
            parse_mode="HTML"
        )

# ═══════════════════════════════════════
#               MAIN
# ═══════════════════════════════════════

async def main():
    await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
