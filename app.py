import asyncio
import json
import os
import requests
import sqlite3
import calendar
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = os.getenv("TG_API_KEY", "")
OUTLINE_API_URL = os.getenv("OUTLINE_API_URL", "")
DB_NAME = "vpn.db"
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",")]
pending_invoices = {}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            vpn_key TEXT,
            ton_wallet TEXT,
            pending_comment TEXT,
            created_at TEXT,
            subscription_expires TEXT
        )
    """)
    conn.commit()
    conn.close()

def db_connect():
    return sqlite3.connect(DB_NAME)

def get_user(user_id: int):
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, vpn_key, ton_wallet, pending_comment, created_at, subscription_expires
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        return cursor.fetchone()

def add_user(user_id: int, username: str, vpn_key: str, ton_wallet: str = None, pending_comment: str = None):
    with db_connect() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO users (user_id, username, vpn_key, ton_wallet, pending_comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, vpn_key, ton_wallet, pending_comment, created_at))
        conn.commit()

def update_vpn_key(user_id: int, vpn_key: str):
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET vpn_key = ? WHERE user_id = ?", (vpn_key, user_id))
        conn.commit()

def update_subscription(user_id: int, expires: str):
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET subscription_expires = ? WHERE user_id = ?", (expires, user_id))
        conn.commit()

def get_all_users_with_subscription():
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, subscription_expires, vpn_key FROM users WHERE subscription_expires IS NOT NULL")
        return cursor.fetchall()

def get_total_users():
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

def get_active_subscriptions():
    now = datetime.utcnow().isoformat()
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_expires > ?", (now,))
        return cursor.fetchone()[0]

def get_all_users():
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, vpn_key, ton_wallet, pending_comment, created_at, subscription_expires
            FROM users
        """)
        return cursor.fetchall()

def add_months(sourcedate: datetime, months: int) -> datetime:
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = sourcedate.day
    try:
        return sourcedate.replace(year=year, month=month, day=day)
    except ValueError:
        last_day = calendar.monthrange(year, month)[1]
        return sourcedate.replace(year=year, month=month, day=last_day)

def create_vpn_key():
    url = f"{OUTLINE_API_URL}/access-keys"
    payload = {"name": "New Key"}
    try:
        response = requests.post(
            url, 
            json=payload, 
            headers={"Content-Type": "application/json"}, 
            verify=True,
            timeout=10
        )
        if response.status_code == 201:
            return response.json()
        else:
            print("Unexpected server response:", response.status_code, response.text)
            return None
    except Exception as e:
        print("Exception creating key:", e)
        return None

def revoke_vpn_key(vpn_key_data: dict):
    key_id = vpn_key_data.get("id")
    if not key_id:
        return False
    url = f"{OUTLINE_API_URL}/access-keys/{key_id}"
    try:
        response = requests.delete(url, verify=True, timeout=10)
        if response.status_code == 204:
            return True
        else:
            print("Failed to delete Outline key:", response.status_code, response.text)
            return False
    except Exception as e:
        print("Exception revoking Outline key:", e)
        return False

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Get VPN", callback_data="menu_get_vpn")
    builder.button(text="ℹ️ Information", callback_data="menu_info")
    builder.button(text="⚙ Settings", callback_data="menu_settings")
    builder.button(text="💳 Payment", callback_data="menu_payments")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    text = (
        "👋 Hi! Welcome to the Outline VPN Purchase Bot!\n\n"
        "This bot allows you to purchase VPN access via subscription using Telegram Stars.\n\n"
        "Choose an option below:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(lambda c: c.data == "menu_get_vpn")
async def menu_get_vpn(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user:
        await callback.answer("❌ Please purchase VPN access first.", show_alert=True)
        return
        
    if not user[6]:
        await callback.answer("❌ Please purchase VPN access first.", show_alert=True)
        return
        
    try:
        expires = datetime.fromisoformat(user[6])
    except Exception:
        expires = None
        
    if not expires or expires <= datetime.utcnow():
        if user[2]:
            try:
                vpn_data = json.loads(user[2])
                if vpn_data:
                    revoke_vpn_key(vpn_data)
                    update_vpn_key(user_id, None)
            except json.JSONDecodeError:
                pass
                
        update_subscription(user_id, None)
        await callback.answer("Your subscription has expired. Please purchase a new subscription.", show_alert=True)
        return
        
    vpn_key_data = None
    if user[2]:
        try:
            vpn_key_data = json.loads(user[2])
        except json.JSONDecodeError:
            pass
            
    if not vpn_key_data:
        vpn_key_data = create_vpn_key()
        if vpn_key_data:
            update_vpn_key(user_id, json.dumps(vpn_key_data))
        else:
            await callback.answer()
            await bot.send_message(user_id, "❌ Failed to create VPN access. Please try again later.")
            return
            
    text = (
        f"🔑 Your VPN access:\n<pre>{vpn_key_data.get('accessUrl')}</pre>\n\n"
        f"Subscription valid until {expires.strftime('%Y-%m-%d %H:%M:%S')} UTC."
    )
    await callback.answer()
    await bot.send_message(user_id, text, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "menu_info")
async def menu_info(callback: types.CallbackQuery):
    text = (
        "📖 Instructions for using the Outline VPN Purchase Bot:\n\n"
        "<b>Purchase VPN access:</b>\n"
        "1. Press the '💳 Payment' button to choose a subscription duration and complete payment using Telegram Stars.\n"
        "2. After successful payment, your subscription will activate and you can access the VPN.\n"
        "   Note: A valid subscription is required to access the VPN."
    )
    await callback.answer()
    await bot.send_message(callback.from_user.id, text, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "menu_settings")
async def menu_settings(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[6]:
        try:
            expiry = datetime.fromisoformat(user[6])
            if expiry > datetime.utcnow():
                subscription_info = f"Subscription active until {expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC."
            else:
                subscription_info = f"Subscription expired on {expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC."
        except Exception:
            subscription_info = "Unable to determine subscription validity."
    else:
        subscription_info = "No subscription active. Please purchase a subscription to get VPN access."
    await callback.answer()
    await bot.send_message(callback.from_user.id, f"⚙ Bot Settings:\n\n{subscription_info}")

@dp.callback_query(lambda c: c.data == "menu_payments")
async def menu_payments(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[6]:
        try:
            expires = datetime.fromisoformat(user[6])
            if expires and expires > datetime.utcnow():
                await callback.answer("You already have an active subscription. To extend, choose a duration.", show_alert=True)
        except Exception:
            pass
            
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 month - 150 ⭐", callback_data="pay_sub_1")],
        [InlineKeyboardButton(text="3 months - 405 ⭐", callback_data="pay_sub_3")],
        [InlineKeyboardButton(text="6 months - 765 ⭐", callback_data="pay_sub_6")],
        [InlineKeyboardButton(text="12 months - 1440 ⭐", callback_data="pay_sub_12")],
        [InlineKeyboardButton(text="Cancel", callback_data="subscription_selection_cancel")]
    ])
    await callback.answer()
    await bot.send_message(callback.from_user.id, "💳 Choose subscription duration for VPN access:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "subscription_selection_cancel")
async def subscription_selection_cancel(callback: types.CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("pay_sub_"))
async def process_subscription_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_invoices:
        await callback.answer("You already have a pending invoice. Please complete or cancel it before creating a new one.", show_alert=True)
        return
        
    try:
        duration = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Invalid subscription period.", show_alert=True)
        return
        
    price_mapping = {
        1: 150,
        3: 405,
        6: 765,
        12: 1440
    }
    
    price_xtr = price_mapping.get(duration)
    if price_xtr is None:
        await callback.answer("Unknown subscription period.", show_alert=True)
        return
        
    payload = f"subscription_{duration}_{price_xtr}"
    prices = [LabeledPrice(label=f"{duration} month subscription", amount=price_xtr)]
    
    kb = InlineKeyboardBuilder()
    kb.button(text=f"Pay {price_xtr} ⭐", pay=True)
    kb.button(text="Cancel", callback_data="subscription_cancel")
    kb.adjust(1)
    
    await callback.answer()
    try:
        invoice_message = await bot.send_invoice(
            chat_id=user_id,
            title="VPN Subscription Purchase",
            description=f"{duration} month(s) of VPN access subscription.",
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=prices,
            start_parameter="vpn_subscription",
            reply_markup=kb.as_markup()
        )
        pending_invoices[user_id] = invoice_message.message_id
    except Exception as e:
        await callback.message.answer(f"Error creating invoice: {e}")

@dp.callback_query(lambda c: c.data == "subscription_cancel")
async def subscription_cancel_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_invoices:
        message_id = pending_invoices.pop(user_id)
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass
        await callback.answer("Invoice canceled.")
    else:
        await callback.answer("No pending invoice to cancel.", show_alert=True)

@dp.pre_checkout_query()
async def pre_checkout_query_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    try:
        parts = payload.split("_")
        if parts[0] != "subscription":
            return
        duration = int(parts[1])
    except Exception:
        await message.answer("Error processing payment data.")
        return
        
    user_id = message.from_user.id
    user = get_user(user_id)
    now = datetime.utcnow()
    
    if not user:
        username = message.from_user.username or str(user_id)
        add_user(user_id, username, None)
        
    if user and user[6]:
        try:
            current_expiry = datetime.fromisoformat(user[6])
            if current_expiry > now:
                new_expiry = add_months(current_expiry, duration)
            else:
                new_expiry = add_months(now, duration)
        except Exception:
            new_expiry = add_months(now, duration)
    else:
        new_expiry = add_months(now, duration)
        
    update_subscription(user_id, new_expiry.isoformat())
    
    if user_id in pending_invoices:
        pending_invoices.pop(user_id)
        
    await message.answer(f"Payment successful! Subscription extended until {new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC.")

async def subscription_reminder():
    while True:
        await asyncio.sleep(24 * 3600)
        users = get_all_users_with_subscription()
        now = datetime.utcnow()
        for user_id, sub_expires, vpn_key in users:
            try:
                expires = datetime.fromisoformat(sub_expires)
            except Exception:
                continue
                
            if expires <= now:
                if vpn_key:
                    try:
                        vpn_data = json.loads(vpn_key)
                        if vpn_data:
                            revoke_vpn_key(vpn_data)
                            update_vpn_key(user_id, None)
                    except json.JSONDecodeError:
                        pass
                        
                update_subscription(user_id, None)
                try:
                    await bot.send_message(user_id, "Your subscription has expired. Please purchase a new subscription to continue accessing the VPN.")
                except Exception:
                    pass
            elif (expires - now).days <= 5:
                try:
                    await bot.send_message(user_id, f"Reminder: Your subscription expires in {(expires - now).days} days. Renew to keep VPN access.")
                except Exception:
                    pass

@dp.message(Command("admin"))
async def admin_panel_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Access Denied")
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="General Stats", callback_data="admin_stats")],
        [InlineKeyboardButton(text="User List", callback_data="admin_users")],
        [InlineKeyboardButton(text="Close", callback_data="admin_close")]
    ])
    await message.answer("Admin Panel:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access Denied", show_alert=True)
        return
        
    total_users = get_total_users()
    active_subs = get_active_subscriptions()
    
    text = (
        f"📊 General Statistics:\n"
        f"Users: {total_users}\n"
        f"Active Subscriptions: {active_subs}\n"
        f"Data Usage: not implemented"
    )
    await callback.answer()
    await bot.send_message(callback.from_user.id, text)

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access Denied", show_alert=True)
        return
        
    users = get_all_users()
    if not users:
        text = "No users found."
    else:
        lines = []
        for user in users:
            user_id, username, vpn_key, ton_wallet, pending_comment, created_at, subscription_expires = user
            sub = subscription_expires if subscription_expires else "None"
            active = ""
            
            if subscription_expires:
                try:
                    expires = datetime.fromisoformat(subscription_expires)
                    if expires > datetime.utcnow():
                        active = "✅"
                    else:
                        active = "❌"
                except Exception:
                    pass
                    
            line = f"ID: {user_id}, Name: {username}, Subscription: {sub} {active}"
            lines.append(line)
            
        text = "\n".join(lines)
        
    await callback.answer()
    
    max_message_length = 4096
    if len(text) <= max_message_length:
        await bot.send_message(callback.from_user.id, text)
    else:
        chunks = [text[i:i+max_message_length] for i in range(0, len(text), max_message_length)]
        for chunk in chunks:
            await bot.send_message(callback.from_user.id, chunk)

@dp.callback_query(lambda c: c.data == "admin_close")
async def admin_close_handler(callback: types.CallbackQuery):
    await callback.answer("Admin panel closed.")
    try:
        await bot.delete_message(callback.from_user.id, callback.message.message_id)
    except Exception:
        pass

async def main():
    init_db()
    asyncio.create_task(subscription_reminder())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())