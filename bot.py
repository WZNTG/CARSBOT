import logging, random, sqlite3, time, asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8477161043:AAHQZtOjW_vua-NePpMbxghbxRvWYXxlGC8"
ADMIN_ID = 5394084759
CHANNEL_LINK = "https://t.me/your_channel"
CHANNEL_NAME = "@your_channel"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp  = Dispatcher()
conn   = sqlite3.connect("cars_bot.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,last_roll INTEGER DEFAULT 0,last_daily INTEGER DEFAULT 0,pts INTEGER DEFAULT 0,free_rolls INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS cars(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,description TEXT,rarity INTEGER,pts INTEGER,photo TEXT);
    CREATE TABLE IF NOT EXISTS collection(user_id INTEGER,car_id INTEGER);
    CREATE TABLE IF NOT EXISTS duplicates(user_id INTEGER,car_id INTEGER);
    CREATE TABLE IF NOT EXISTS promocodes(code TEXT PRIMARY KEY,type TEXT,value INTEGER,uses_left INTEGER);
    CREATE TABLE IF NOT EXISTS promo_used(code TEXT,user_id INTEGER,PRIMARY KEY(code,user_id));
    CREATE TABLE IF NOT EXISTS boosts(user_id INTEGER PRIMARY KEY,expires_at INTEGER);
    """)
    try: cursor.execute("ALTER TABLE users ADD COLUMN free_rolls INTEGER DEFAULT 0")
    except: pass
    conn.commit()
init_db()

ROLL_COOLDOWN=14400; DAILY_COOLDOWN=86400; BOOST_DURATION=3600; GARAGE_PAGE_SIZE=8
RARITY_NAME={1:"⚪ Common",2:"🔵 Rare",3:"🟣 Epic",4:"🟡 Legendary",5:"💎 Secret"}
RARITY_STARS={1:"★☆☆☆☆",2:"★★☆☆☆",3:"★★★☆☆",4:"★★★★☆",5:"★★★★★"}
DUPLICATE_PTS={1:1,2:2,3:4,4:10,5:25}
SLOT_SYMBOLS=["🍋","🍊","🍇","⭐","💎","7️⃣"]
UPGRADE_CHANCE={1:60,2:40,3:25,4:10}
MEDALS=["🥇","🥈","🥉"]
BREAKDOWN_MESSAGES=[
    ("🔧 Двигатель","Машина приехала с заклинившим двигателем — не заводится."),
    ("🛞 Колёса","Все четыре колеса сняты. Видимо, сняли ещё на складе."),
    ("💺 Салон","Машина приехала полностью разобранной — сиденья отсутствуют."),
    ("🔋 Аккумулятор","Аккумулятор мёртв, машина не подаёт признаков жизни."),
    ("🪟 Стёкла","Все стёкла разбиты при транспортировке."),
    ("🚪 Двери","Двери сорваны с петель — видимо, грузили кое-как."),
    ("⚙️ Коробка передач","Коробка передач рассыпалась прямо в пути."),
    ("🛢️ Масло","Масло вытекло полностью — двигатель сухой."),
    ("🔑 Ключи","Машина приехала без ключей и документов."),
    ("💥 Бампер","Передний и задний бамперы снесены — следы столкновения."),
    ("🎨 Кузов","Кузов в глубоких царапинах — похоже, везли волоком."),
    ("🔌 Проводка","Вся проводка вырвана — машина не реагирует ни на что."),
    ("🧯 Тормоза","Тормозная система неисправна — ехать невозможно."),
    ("📦 Комплектация","Приехала пустая коробка. Машины внутри не оказалось."),
    ("🌊 Затопление","Машина пришла мокрой насквозь — утопили при погрузке."),
    ("🔩 Крепления","Болты не затянули на заводе — кузов буквально разваливается."),
    ("🪫 Бак","Бак пробит, топливо вытекло ещё в дороге."),
    ("🏷️ Документы","VIN номер спилен — таможня завернула обратно."),
    ("🎭 Подмена","Пришла совсем другая машина. Где оригинал — неизвестно."),
    ("🐦 Птицы","Стая птиц свила гнёзда во всех воздуховодах и под капотом."),
]
forced_rolls={}; add_state={}

def ensure_user(uid,name):
    cursor.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)",(uid,name)); conn.commit()
def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE id=?",(uid,)); return cursor.fetchone()
def fmt_time(s):
    h,m=s//3600,(s%3600)//60; return f"{h}ч {m}м" if h else f"{m}м"
def get_rarity(boosted=False):
    r=random.randint(1,1000)
    if boosted:
        if r<=500: return 1
        elif r<=750: return 2
        elif r<=930: return 3
        elif r<=990: return 4
        else: return 5
    else:
        if r<=700: return 1
        elif r<=900: return 2
        elif r<=980: return 3
        elif r<=998: return 4
        else: return 5
def cap(name,desc,rarity,pts,label=None):
    if not label:
        if rarity==5: label="💎💎💎 SECRET DROP 💎💎💎"
        elif rarity==4: label="🔥 ЛЕГЕНДАРНАЯ МАШИНА!"
        elif rarity==3: label="✨ ЭПИЧЕСКАЯ МАШИНА!"
        else: label="🎉 Новая машина!"
    return (f"{label}\n\n🏎  <b>{name}</b>\n\n{RARITY_NAME[rarity]}  {RARITY_STARS[rarity]}\n"
            f"⭐  <b>{pts} pts</b>\n\n<i>{desc}</i>\n\n"
            f"📢 <a href='{CHANNEL_LINK}'>{CHANNEL_NAME}</a>")
def garage_kb(cars,page,total):
    btns=[[InlineKeyboardButton(text=f"{RARITY_NAME[r].split()[0]} {n}",callback_data=f"card:{cid}")] for cid,n,r in cars]
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text="◀️",callback_data=f"garage:{page-1}"))
    if page<total-1: nav.append(InlineKeyboardButton(text="▶️",callback_data=f"garage:{page+1}"))
    if nav: btns.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=btns)
def dups_kb(dups,page,total):
    btns=[]
    for cid,n,r in dups:
        icon=RARITY_NAME[r].split()[0]
        btns.append([InlineKeyboardButton(text=f"{icon} {n}",callback_data="noop"),
                     InlineKeyboardButton(text="⬆️",callback_data=f"upgrade:{cid}"),
                     InlineKeyboardButton(text="💰",callback_data=f"sell:{cid}")])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text="◀️",callback_data=f"dups:{page-1}"))
    if page<total-1: nav.append(InlineKeyboardButton(text="▶️",callback_data=f"dups:{page+1}"))
    if nav: btns.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=btns)

async def set_commands():
    await bot.set_my_commands([
        types.BotCommand(command="roll",description="🎰 Выбить машину"),
        types.BotCommand(command="garage",description="🏎 Твой гараж"),
        types.BotCommand(command="duplicates",description="♻️ Дубликаты"),
        types.BotCommand(command="profile",description="👤 Профиль"),
        types.BotCommand(command="collection",description="📖 Коллекция"),
        types.BotCommand(command="daily",description="🎁 Ежедневный бонус"),
        types.BotCommand(command="roulette",description="🎰 Казино"),
        types.BotCommand(command="promo",description="🎟 Промокод"),
        types.BotCommand(command="top",description="🏆 Топ Legendary"),
        types.BotCommand(command="top_pts",description="🏆 Топ по очкам"),
        types.BotCommand(command="top_cards",description="🏆 Топ по картам"),
        types.BotCommand(command="shop",description="🛒 Магазин"),
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    ensure_user(message.from_user.id,message.from_user.first_name)
    await message.answer(
        f"🏁 <b>Добро пожаловать, {message.from_user.first_name}!</b>\n\n"
        "Ты попал в гараж, где каждый ролл — это лотерея.\n"
        "Обычные тачки, редкие экземпляры, легендарные монстры — всё это ждёт тебя.\n\n"
        "⚠️ Но осторожно — иногда машины приходят <b>с сюрпризами</b>...\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🎰 /roll — крутить\n🏎 /garage — гараж\n♻️ /duplicates — дубликаты\n"
        "🎁 /daily — бонус\n👤 /profile — профиль\n\n"
        f"📢 <a href='{CHANNEL_LINK}'>{CHANNEL_NAME}</a>",
        parse_mode="HTML",disable_web_page_preview=True)

@dp.message(Command("roll"))
async def roll(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    user=get_user(uid); last=user[2]; now=int(time.time()); free=user[5] if len(user)>5 else 0
    if now-last<ROLL_COOLDOWN and free==0:
        await message.answer(f"⏳ <b>Перезарядка!</b>\n\nСледующий roll через <b>{fmt_time(ROLL_COOLDOWN-(now-last))}</b>\n\n📢 <a href='{CHANNEL_LINK}'>{CHANNEL_NAME}</a>",parse_mode="HTML",disable_web_page_preview=True); return
    frames=["🎰 <b>Крутим...</b>\n\n▪️▪️▪️","🎰 <b>Крутим...</b>\n\n⚪▪️▪️","🎰 <b>Крутим...</b>\n\n⚪🔵▪️","🎰 <b>Крутим...</b>\n\n⚪🔵🟣","🎰 <b>Крутим...</b>\n\n⚪🔵🟣🟡"]
    msg=await message.answer(frames[0],parse_mode="HTML")
    for f in frames[1:]:
        await asyncio.sleep(0.5); await msg.edit_text(f,parse_mode="HTML")
    car=None
    if uid in forced_rolls:
        fid=forced_rolls.pop(uid); cursor.execute("SELECT * FROM cars WHERE id=?",(fid,)); car=cursor.fetchone()
    if not car:
        cursor.execute("SELECT expires_at FROM boosts WHERE user_id=?",(uid,)); b=cursor.fetchone()
        rarity=get_rarity(bool(b and b[0]>now))
        cursor.execute("SELECT * FROM cars WHERE rarity=? ORDER BY RANDOM() LIMIT 1",(rarity,)); car=cursor.fetchone()
    if not car:
        cursor.execute("SELECT * FROM cars ORDER BY RANDOM() LIMIT 1"); car=cursor.fetchone()
    if not car:
        await msg.edit_text("🚫 В базе нет машин."); return
    cid,name,desc,rarity,pts,photo=car
    if free>0: cursor.execute("UPDATE users SET free_rolls=free_rolls-1 WHERE id=?",(uid,))
    else: cursor.execute("UPDATE users SET last_roll=? WHERE id=?",(now,uid))
    conn.commit()
    if random.randint(1,100)<=20:
        bt,bd=random.choice(BREAKDOWN_MESSAGES)
        c=cap(name,desc,rarity,pts)+f"\n\n━━━━━━━━━━━━━━━\n🚨 <b>Поломка: {bt}</b>\n{bd}\n\n<i>Машина не засчитана</i>"
        await msg.delete(); await message.answer_photo(photo,caption=c,parse_mode="HTML"); return
    cursor.execute("SELECT 1 FROM collection WHERE user_id=? AND car_id=?",(uid,cid)); have=cursor.fetchone()
    if have:
        bonus=DUPLICATE_PTS[rarity]
        cursor.execute("INSERT INTO duplicates VALUES(?,?)",(uid,cid))
        cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(bonus,uid)); conn.commit()
        await msg.delete(); await message.answer_photo(photo,caption=cap(name,desc,rarity,pts)+f"\n\n<i>+{bonus} pts</i>",parse_mode="HTML")
    else:
        cursor.execute("INSERT INTO collection VALUES(?,?)",(uid,cid))
        cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(pts,uid)); conn.commit()
        await msg.delete(); await message.answer_photo(photo,caption=cap(name,desc,rarity,pts),parse_mode="HTML")

@dp.message(Command("duplicates"))
async def duplicates(message: types.Message):
    ensure_user(message.from_user.id,message.from_user.first_name)
    await show_dups(message,message.from_user.id,0,False)

async def show_dups(target,uid,page=0,edit=False):
    cursor.execute("SELECT cars.id,cars.name,cars.rarity FROM duplicates JOIN cars ON cars.id=duplicates.car_id WHERE duplicates.user_id=? ORDER BY cars.rarity DESC,cars.name",(uid,))
    all_d=cursor.fetchall()
    if not all_d:
        text="♻️ <b>Дубликатов нет</b>\n\nПродолжай крутить — дубли копятся здесь."
        if edit: await target.message.edit_text(text,parse_mode="HTML")
        else: await target.answer(text,parse_mode="HTML"); return
    total=max(1,(len(all_d)+4)//5); page=max(0,min(page,total-1)); page_d=all_d[page*5:(page+1)*5]
    text=(f"♻️ <b>Дубликаты</b> ({len(all_d)} шт.)\n\n"
          "⬆️ Апгрейд — шанс повысить редкость:\nCommon→Rare: 60%  Rare→Epic: 40%\nEpic→Leg: 25%  Leg→Secret: 10%\n\n"
          "💰 Продать — получить очки\n\n<i>Выбери:</i>")
    if edit: await target.message.edit_text(text,reply_markup=dups_kb(page_d,page,total),parse_mode="HTML")
    else: await target.answer(text,reply_markup=dups_kb(page_d,page,total),parse_mode="HTML")

@dp.callback_query(F.data.startswith("dups:"))
async def dups_page(cb: types.CallbackQuery):
    await show_dups(cb,cb.from_user.id,int(cb.data.split(":")[1]),True); await cb.answer()

@dp.callback_query(F.data=="noop")
async def noop(cb: types.CallbackQuery): await cb.answer()

@dp.callback_query(F.data.startswith("sell:"))
async def sell_dup(cb: types.CallbackQuery):
    uid=cb.from_user.id; cid=int(cb.data.split(":")[1])
    cursor.execute("SELECT rowid FROM duplicates WHERE user_id=? AND car_id=? LIMIT 1",(uid,cid)); row=cursor.fetchone()
    if not row:
        await cb.answer("❌ Не найден",show_alert=True); return
    cursor.execute("SELECT rarity FROM cars WHERE id=?",(cid,)); rarity=cursor.fetchone()[0]
    price=DUPLICATE_PTS[rarity]
    cursor.execute("DELETE FROM duplicates WHERE rowid=?",(row[0],))
    cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(price,uid)); conn.commit()
    await cb.answer(f"💰 Продано за {price} pts!"); await show_dups(cb,uid,0,True)

@dp.callback_query(F.data.startswith("upgrade:"))
async def upgrade_dup(cb: types.CallbackQuery):
    uid=cb.from_user.id; cid=int(cb.data.split(":")[1])
    cursor.execute("SELECT rowid FROM duplicates WHERE user_id=? AND car_id=? LIMIT 1",(uid,cid)); row=cursor.fetchone()
    if not row:
        await cb.answer("❌ Не найден",show_alert=True); return
    cursor.execute("SELECT name,rarity FROM cars WHERE id=?",(cid,)); name,rarity=cursor.fetchone()
    if rarity==5:
        await cb.answer("💎 Secret — максимум!",show_alert=True); return
    cursor.execute("DELETE FROM duplicates WHERE rowid=?",(row[0],)); conn.commit()
    chance=UPGRADE_CHANCE.get(rarity,0)
    if random.randint(1,100)<=chance:
        new_r=rarity+1
        cursor.execute("SELECT * FROM cars WHERE rarity=? ORDER BY RANDOM() LIMIT 1",(new_r,)); nc=cursor.fetchone()
        if nc:
            ncid,ncname,ncdesc,ncrarity,ncpts,ncphoto=nc
            cursor.execute("SELECT 1 FROM collection WHERE user_id=? AND car_id=?",(uid,ncid))
            if cursor.fetchone():
                bonus=DUPLICATE_PTS[ncrarity]
                cursor.execute("INSERT INTO duplicates VALUES(?,?)",(uid,ncid))
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(bonus,uid)); conn.commit()
                await cb.answer(f"⬆️ Успех! {ncname} уже есть → +{bonus} pts",show_alert=True)
            else:
                cursor.execute("INSERT INTO collection VALUES(?,?)",(uid,ncid))
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(ncpts,uid)); conn.commit()
                lbl=f"⬆️ АПГРЕЙД!\n{RARITY_NAME[rarity]} → {RARITY_NAME[ncrarity]}"
                await cb.message.answer_photo(ncphoto,caption=cap(ncname,ncdesc,ncrarity,ncpts,label=lbl),parse_mode="HTML")
        else: await cb.answer("⬆️ Успех, но машин той редкости нет",show_alert=True)
    else: await cb.answer(f"💨 Не повезло ({chance}%). Дубликат сгорел.",show_alert=True)
    await show_dups(cb,uid,0,True)

@dp.message(Command("garage"))
async def garage(message: types.Message):
    ensure_user(message.from_user.id,message.from_user.first_name)
    await show_garage(message,message.from_user.id,0,False)

async def show_garage(target,uid,page=0,edit=False):
    cursor.execute("SELECT cars.id,cars.name,cars.rarity FROM collection JOIN cars ON cars.id=collection.car_id WHERE collection.user_id=? ORDER BY cars.rarity DESC,cars.name",(uid,))
    all_c=cursor.fetchall()
    if not all_c:
        text="🏎 <b>Гараж пуст</b>\n\nИспользуй /roll!"
        if edit: await target.message.edit_text(text,parse_mode="HTML")
        else: await target.answer(text,parse_mode="HTML"); return
    total=max(1,(len(all_c)+GARAGE_PAGE_SIZE-1)//GARAGE_PAGE_SIZE); page=max(0,min(page,total-1))
    pc=all_c[page*GARAGE_PAGE_SIZE:(page+1)*GARAGE_PAGE_SIZE]
    counts={r:0 for r in range(1,6)}
    for _,_,r in all_c: counts[r]+=1
    stats="  ".join(f"{RARITY_NAME[r].split()[0]}{counts[r]}" for r in range(5,0,-1) if counts[r])
    text=f"🏎 <b>Гараж</b> ({len(all_c)} машин)\n{stats}\n\n<i>Нажми на машину</i>"
    if edit: await target.message.edit_text(text,reply_markup=garage_kb(pc,page,total),parse_mode="HTML")
    else: await target.answer(text,reply_markup=garage_kb(pc,page,total),parse_mode="HTML")

@dp.callback_query(F.data.startswith("garage:"))
async def garage_page(cb: types.CallbackQuery):
    await show_garage(cb,cb.from_user.id,int(cb.data.split(":")[1]),True); await cb.answer()

@dp.callback_query(F.data.startswith("card:"))
async def view_card(cb: types.CallbackQuery):
    cid=int(cb.data.split(":")[1]); uid=cb.from_user.id
    cursor.execute("SELECT 1 FROM collection WHERE user_id=? AND car_id=?",(uid,cid))
    if not cursor.fetchone():
        await cb.answer("❌ Не в гараже",show_alert=True); return
    cursor.execute("SELECT * FROM cars WHERE id=?",(cid,)); car=cursor.fetchone()
    if not car:
        await cb.answer("❌ Не найдена",show_alert=True); return
    _,name,desc,rarity,pts,photo=car
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад",callback_data="garage:0")]])
    await cb.message.answer_photo(photo,caption=cap(name,desc,rarity,pts,label="🏎 Информация"),parse_mode="HTML",reply_markup=kb)
    await cb.answer()

@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    user=get_user(uid); pts=user[4]
    cursor.execute("SELECT COUNT(*) FROM collection WHERE user_id=?",(uid,)); total=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cars"); all_total=cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM duplicates WHERE user_id=?",(uid,)); dup_count=cursor.fetchone()[0]
    cursor.execute("SELECT cars.rarity,COUNT(*) FROM collection JOIN cars ON cars.id=collection.car_id WHERE collection.user_id=? GROUP BY cars.rarity ORDER BY cars.rarity DESC",(uid,))
    rc=cursor.fetchall()
    rt="  ".join(f"{RARITY_NAME[r].split()[0]}{c}" for r,c in rc) or "Нет машин"
    p=int(total/all_total*10) if all_total else 0; bar="█"*p+"░"*(10-p)
    text=(f"👤 <b>{message.from_user.first_name}</b>\n\n🚗 Машин: <b>{total}</b>/{all_total}\n[{bar}]\n\n{rt}\n♻️ Дубликатов: <b>{dup_count}</b>\n\n⭐ Очки: <b>{pts} pts</b>")
    photos=await bot.get_user_profile_photos(uid,limit=1)
    if photos.total_count>0: await message.answer_photo(photos.photos[0][-1].file_id,caption=text,parse_mode="HTML")
    else: await message.answer(text,parse_mode="HTML")

@dp.message(Command("collection"))
async def collection(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    cursor.execute("SELECT id,name,rarity FROM cars ORDER BY rarity DESC,name"); all_c=cursor.fetchall()
    cursor.execute("SELECT car_id FROM collection WHERE user_id=?",(uid,)); owned={x[0] for x in cursor.fetchall()}
    if not all_c:
        await message.answer("📖 Коллекция пуста"); return
    lines={r:[] for r in range(5,0,-1)}
    for cid,n,r in all_c: lines[r].append(f"  {'✅' if cid in owned else '❌'} {n}")
    text=f"📖 <b>Коллекция</b>  ({len(owned)}/{len(all_c)})\n"
    for r in range(5,0,-1):
        if lines[r]: text+=f"\n{RARITY_NAME[r]}\n"+"\n".join(lines[r])+"\n"
    await message.answer(text[:4000],parse_mode="HTML")

@dp.message(Command("daily"))
async def daily(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    user=get_user(uid); last=user[3]; now=int(time.time())
    if now-last<DAILY_COOLDOWN:
        await message.answer(f"⏳ Следующий бонус через <b>{fmt_time(DAILY_COOLDOWN-(now-last))}</b>",parse_mode="HTML"); return
    cursor.execute("UPDATE users SET pts=pts+5,last_daily=? WHERE id=?",(now,uid)); conn.commit()
    await message.answer("🎁 <b>Ежедневный бонус!</b>\n\n⭐ +5 pts",parse_mode="HTML")

@dp.message(Command("top"))
async def top(message: types.Message):
    cursor.execute("SELECT users.name,COUNT(*) FROM collection JOIN cars ON cars.id=collection.car_id JOIN users ON users.id=collection.user_id WHERE cars.rarity=4 GROUP BY users.id ORDER BY COUNT(*) DESC LIMIT 10")
    pl=cursor.fetchall()
    if not pl:
        await message.answer("🏆 Пока никто не выбил Legendary"); return
    text="🏆 <b>Топ по Legendary</b>\n\n"
    for i,(n,c) in enumerate(pl): text+=f"{MEDALS[i] if i<3 else f'{i+1}.'} {n} — <b>{c}</b> 🟡\n"
    await message.answer(text,parse_mode="HTML")

@dp.message(Command("top_pts"))
async def top_pts(message: types.Message):
    cursor.execute("SELECT name,pts FROM users ORDER BY pts DESC LIMIT 10"); pl=cursor.fetchall()
    text="🏆 <b>Топ по очкам</b>\n\n"
    for i,(n,p) in enumerate(pl): text+=f"{MEDALS[i] if i<3 else f'{i+1}.'} {n} — <b>{p} pts</b>\n"
    await message.answer(text,parse_mode="HTML")

@dp.message(Command("top_cards"))
async def top_cards(message: types.Message):
    cursor.execute("SELECT users.name,COUNT(*) FROM collection JOIN users ON users.id=collection.user_id GROUP BY users.id ORDER BY COUNT(*) DESC LIMIT 10")
    pl=cursor.fetchall()
    if not pl:
        await message.answer("🏆 Пока нет данных"); return
    text="🏆 <b>Топ по количеству карт</b>\n\n"
    for i,(n,c) in enumerate(pl): text+=f"{MEDALS[i] if i<3 else f'{i+1}.'} {n} — <b>{c}</b> 🚗\n"
    await message.answer(text,parse_mode="HTML")

@dp.message(Command("shop"))
async def shop(message: types.Message):
    await message.answer("🛒 <b>Магазин</b>\n\n🎰 <b>Казино рулетка</b> — 300 pts\nТри 7️⃣ — выигрываешь Legendary или Secret!\n\n👉 /roulette",parse_mode="HTML")

@dp.message(Command("roulette"))
async def roulette(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    user=get_user(uid); pts=user[4]
    if pts<300:
        await message.answer(f"❌ Нужно <b>300 pts</b>\nУ тебя: <b>{pts} pts</b>",parse_mode="HTML"); return
    cursor.execute("UPDATE users SET pts=pts-300 WHERE id=?",(uid,)); conn.commit()
    reels=[random.choice(SLOT_SYMBOLS) for _ in range(3)]
    msg=await message.answer("🎰 <b>Казино</b>\n\n❓ ❓ ❓",parse_mode="HTML")
    for i,r in enumerate(reels):
        await asyncio.sleep(0.8); shown=" ".join(reels[:i+1]+["❓"]*(2-i))
        await msg.edit_text(f"🎰 <b>Казино</b>\n\n{shown}",parse_mode="HTML")
    await asyncio.sleep(0.4)
    if reels[0]==reels[1]==reels[2]=="7️⃣":
        cursor.execute("SELECT * FROM cars WHERE rarity IN (4,5) ORDER BY RANDOM() LIMIT 1"); car=cursor.fetchone()
        if car:
            cid,name,desc,rarity,cpts,photo=car
            cursor.execute("SELECT 1 FROM collection WHERE user_id=? AND car_id=?",(uid,cid))
            if cursor.fetchone():
                bonus=DUPLICATE_PTS[rarity]
                cursor.execute("INSERT INTO duplicates VALUES(?,?)",(uid,cid))
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(bonus,uid)); conn.commit()
                await msg.edit_text(f"🎰 <b>7️⃣ 7️⃣ 7️⃣ ДЖЕКПОТ!</b>\n\n♻️ {name} → <b>+{bonus} pts</b>",parse_mode="HTML")
            else:
                cursor.execute("INSERT INTO collection VALUES(?,?)",(uid,cid))
                cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(cpts,uid)); conn.commit()
                await msg.delete(); await message.answer_photo(photo,caption="🎰 <b>7️⃣ 7️⃣ 7️⃣ ДЖЕКПОТ!</b>\n\n"+cap(name,desc,rarity,cpts),parse_mode="HTML")
        else: await msg.edit_text("🎰 ДЖЕКПОТ! Но машин нет 😢",parse_mode="HTML")
    else: await msg.edit_text(f"🎰 <b>Казино</b>\n\n{' '.join(reels)}\n\n❌ Нужно 7️⃣ 7️⃣ 7️⃣\n\n<i>/roulette</i>",parse_mode="HTML")

@dp.message(Command("promo"))
async def promo(message: types.Message):
    uid=message.from_user.id; ensure_user(uid,message.from_user.first_name)
    parts=message.text.split()
    if len(parts)<2:
        await message.answer("🎟 Используй: <code>/promo КОД</code>",parse_mode="HTML"); return
    code=parts[1].upper().strip()
    cursor.execute("SELECT * FROM promocodes WHERE code=?",(code,)); pd=cursor.fetchone()
    if not pd or pd[3]<=0:
        await message.answer("❌ Промокод не найден"); return
    cursor.execute("SELECT 1 FROM promo_used WHERE code=? AND user_id=?",(code,uid))
    if cursor.fetchone():
        await message.answer("❌ Уже использован"); return
    _,type_,value,_=pd
    cursor.execute("INSERT INTO promo_used VALUES(?,?)",(code,uid))
    cursor.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?",(code,)); conn.commit()
    if type_=="pts":
        cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(value,uid)); conn.commit()
        await message.answer(f"✅ <b>Активировано!</b>\n\n⭐ +{value} pts",parse_mode="HTML")
    elif type_=="free_roll":
        cursor.execute("UPDATE users SET free_rolls=free_rolls+? WHERE id=?",(value,uid)); conn.commit()
        await message.answer(f"✅ <b>Активировано!</b>\n\n🎰 +{value} бесплатных роллов",parse_mode="HTML")
    elif type_=="boost":
        now=int(time.time())
        cursor.execute("SELECT expires_at FROM boosts WHERE user_id=?",(uid,)); cb=cursor.fetchone()
        base=max(now,cb[0] if cb else 0)
        cursor.execute("INSERT OR REPLACE INTO boosts VALUES(?,?)",(uid,base+BOOST_DURATION*value)); conn.commit()
        await message.answer(f"✅ <b>Активировано!</b>\n\n🚀 Буст шансов на {value}ч!",parse_mode="HTML")

@dp.message(Command("give"))
async def give(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try:
        _,uid,cid=message.text.split(); uid,cid=int(uid),int(cid)
    except:
        await message.answer("Используй: /give &lt;user_id&gt; &lt;car_id&gt;",parse_mode="HTML"); return
    cursor.execute("SELECT name FROM cars WHERE id=?",(cid,)); car=cursor.fetchone()
    if not car:
        await message.answer("❌ Машина не найдена"); return
    forced_rolls[uid]=cid
    await message.answer(f"✅ Следующий ролл <code>{uid}</code> → <b>{car[0]}</b>",parse_mode="HTML")

@dp.message(Command("give_pts"))
async def give_pts(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try:
        _,uid,amount=message.text.split(); uid,amount=int(uid),int(amount)
    except:
        await message.answer("Используй: /give_pts &lt;user_id&gt; &lt;amount&gt;",parse_mode="HTML"); return
    ensure_user(uid,"unknown")
    cursor.execute("UPDATE users SET pts=pts+? WHERE id=?",(amount,uid)); conn.commit()
    await message.answer(f"✅ <b>{amount} pts</b> → <code>{uid}</code>",parse_mode="HTML")

@dp.message(Command("give_roll"))
async def give_roll(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try:
        parts=message.text.split(); uid=int(parts[1]); count=int(parts[2]) if len(parts)>2 else 1
    except:
        await message.answer("Используй: /give_roll &lt;user_id&gt; [кол-во]",parse_mode="HTML"); return
    ensure_user(uid,"unknown")
    cursor.execute("UPDATE users SET free_rolls=free_rolls+? WHERE id=?",(count,uid)); conn.commit()
    await message.answer(f"✅ <b>{count}</b> роллов → <code>{uid}</code>",parse_mode="HTML")

@dp.message(Command("cars_list"))
async def cars_list(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    cursor.execute("SELECT id,name,rarity,pts FROM cars ORDER BY rarity DESC"); cars=cursor.fetchall()
    if not cars:
        await message.answer("База пуста"); return
    text="📋 <b>Все машины:</b>\n\n"
    for cid,name,rarity,pts in cars: text+=f"<code>ID:{cid}</code>  {RARITY_NAME[rarity]}  {name}  ({pts} pts)\n"
    await message.answer(text[:4000],parse_mode="HTML")

@dp.message(Command("delete_car"))
async def delete_car(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try: cid=int(message.text.split()[1])
    except:
        await message.answer("Используй: /delete_car &lt;ID&gt;",parse_mode="HTML"); return
    cursor.execute("SELECT name FROM cars WHERE id=?",(cid,)); car=cursor.fetchone()
    if not car:
        await message.answer("❌ Не найдена"); return
    for q in ["DELETE FROM cars WHERE id=?","DELETE FROM collection WHERE car_id=?","DELETE FROM duplicates WHERE car_id=?"]:
        cursor.execute(q,(cid,))
    conn.commit()
    await message.answer(f"✅ <b>{car[0]}</b> удалена",parse_mode="HTML")

@dp.message(Command("create_promo"))
async def create_promo(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try:
        parts=message.text.split(); code=parts[1].upper(); type_=parts[2]; value=int(parts[3]); uses=int(parts[4])
    except:
        await message.answer("Используй:\n<code>/create_promo КОД ТИП ЗНАЧЕНИЕ АКТИВАЦИЙ</code>\n\nТипы: <code>pts</code> | <code>free_roll</code> | <code>boost</code>\nПример: <code>/create_promo SUPER pts 100 50</code>",parse_mode="HTML"); return
    if type_ not in ("pts","free_roll","boost"):
        await message.answer("❌ Тип: pts / free_roll / boost"); return
    cursor.execute("INSERT OR REPLACE INTO promocodes VALUES(?,?,?,?)",(code,type_,value,uses)); conn.commit()
    labels={"pts":f"⭐ {value} pts","free_roll":f"🎰 {value} роллов","boost":f"🚀 {value}ч"}
    await message.answer(f"✅ Промокод создан!\n\nКод: <code>{code}</code>\nНаграда: {labels[type_]}\nАктиваций: {uses}",parse_mode="HTML")

@dp.message(Command("promos_list"))
async def promos_list(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    cursor.execute("SELECT code,type,value,uses_left FROM promocodes"); promos=cursor.fetchall()
    if not promos:
        await message.answer("Промокодов нет"); return
    text="🎟 <b>Промокоды:</b>\n\n"
    for code,type_,value,uses_left in promos: text+=f"<code>{code}</code>  {type_}={value}  осталось: {uses_left}\n"
    await message.answer(text,parse_mode="HTML")

@dp.message(Command("delete_promo"))
async def delete_promo(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    try: code=message.text.split()[1].upper()
    except:
        await message.answer("Используй: /delete_promo КОД"); return
    cursor.execute("DELETE FROM promocodes WHERE code=?",(code,))
    cursor.execute("DELETE FROM promo_used WHERE code=?",(code,)); conn.commit()
    await message.answer(f"✅ Промокод <code>{code}</code> удалён",parse_mode="HTML")

@dp.message(Command("admin_reset"))
async def admin_reset(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    uid=message.from_user.id
    cursor.execute("DELETE FROM collection WHERE user_id=?",(uid,))
    cursor.execute("DELETE FROM duplicates WHERE user_id=?",(uid,))
    cursor.execute("UPDATE users SET last_roll=0,pts=0,free_rolls=0 WHERE id=?",(uid,)); conn.commit()
    await message.answer("🧹 Сброс выполнен")

@dp.message(Command("add"))
async def add(message: types.Message):
    if message.from_user.id!=ADMIN_ID: return
    add_state[message.from_user.id]={"step":"photo"}
    await message.answer("📸 <b>Шаг 1/5</b> — отправь фото машины",parse_mode="HTML")

@dp.message()
async def process_add(message: types.Message):
    uid=message.from_user.id
    if uid not in add_state: return
    state=add_state[uid]; step=state["step"]
    if step=="photo":
        if not message.photo:
            await message.answer("❌ Нужно фото!"); return
        state["photo"]=message.photo[-1].file_id; state["step"]="name"
        await message.answer("📝 <b>Шаг 2/5</b> — название",parse_mode="HTML")
    elif step=="name":
        state["name"]=message.text.strip(); state["step"]="desc"
        await message.answer("📝 <b>Шаг 3/5</b> — описание",parse_mode="HTML")
    elif step=="desc":
        state["desc"]=message.text.strip(); state["step"]="rarity"
        await message.answer("📝 <b>Шаг 4/5</b> — редкость:\n\n1=⚪Common  2=🔵Rare  3=🟣Epic  4=🟡Legendary  5=💎Secret",parse_mode="HTML")
    elif step=="rarity":
        try:
            r=int(message.text.strip())
            if r not in range(1,6): raise ValueError
        except:
            await message.answer("❌ Число от 1 до 5"); return
        state["rarity"]=r; state["step"]="pts"
        await message.answer("📝 <b>Шаг 5/5</b> — очки за машину",parse_mode="HTML")
    elif step=="pts":
        try: pts=int(message.text.strip())
        except:
            await message.answer("❌ Нужно число"); return
        cursor.execute("INSERT INTO cars(name,description,rarity,pts,photo) VALUES(?,?,?,?,?)",(state["name"],state["desc"],state["rarity"],pts,state["photo"]))
        conn.commit(); add_state.pop(uid)
        await message.answer(f"✅ <b>Машина добавлена!</b>\n\n🏎 {state['name']}\n{RARITY_NAME[state['rarity']]}  ⭐ {pts} pts",parse_mode="HTML")

async def main():
    await set_commands()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
