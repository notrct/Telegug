#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Report Bot - د څو حسابونو راپور ورکولو بوت
ادمین: @XFPro43
چینلونه: @ProTech43, @Pro43Zone, @SQ_BOTZ
"""

import telebot
from telebot import types
import time
import random
import sqlite3
import threading
import json
import string
from datetime import datetime
from typing import Tuple, List, Dict, Optional
import logging
import os
import sys

# ==================== تنظیمات ====================
BOT_TOKEN = "8433257767:AAEgdQJA9Jd3ruBylS9h-8T4E0_FIcNk_bg"
ADMIN_IDS = [8089055081]
ADMIN_USERNAME = "@XFPro43"
CHANNELS = ["@ProTech43", "@Pro43Zone", "@SQ_BOTZ"]
BOT_USERNAME = "YourBotUsername"  # د بوت یوزرنیم دلته ولیکئ

# د راپور تنظیمات
REPORT_DELAY = 0.33  # ۳ راپورونه په ثانیه کې
MAX_ACCOUNTS = 20
MAX_REPORTS_PER_ACCOUNT = 100
REQUIRED_REFERRALS = 5

# ==================== لاګینګ ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== بوت ====================
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== ډیټابیس ====================
class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        logger.info("✅ ډیټابیس سره اړیکه جوړه شوه")
        self._add_default_channels()
    
    def _create_tables(self):
        """ټولې اړینې جدولونه جوړول"""
        
        # د کاروونکو جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_date TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                total_reports INTEGER DEFAULT 0,
                total_accounts INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                can_use_free BOOLEAN DEFAULT 0,
                channels_joined INTEGER DEFAULT 0,
                FOREIGN KEY (referred_by) REFERENCES users (user_id)
            )
        ''')
        
        # د حسابونو جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                user_id INTEGER,
                phone TEXT,
                api_id TEXT,
                api_hash TEXT,
                session_string TEXT,
                added_date TIMESTAMP,
                last_used TIMESTAMP,
                status TEXT DEFAULT 'فعال',
                total_reports INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # د راپورونو جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target TEXT,
                reason TEXT,
                count INTEGER,
                accounts_used INTEGER,
                total_reports INTEGER,
                status TEXT,
                report_date TIMESTAMP,
                report_number TEXT UNIQUE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # د چینلونو جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_username TEXT UNIQUE,
                channel_title TEXT,
                added_by INTEGER,
                added_date TIMESTAMP,
                is_mandatory BOOLEAN DEFAULT 1,
                FOREIGN KEY (added_by) REFERENCES users (user_id)
            )
        ''')
        
        # د کارونکي - چینل تړاو جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_username TEXT,
                joined_date TIMESTAMP,
                verified BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # د براډکاسټ جدول
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                total_sent INTEGER,
                total_failed INTEGER,
                sent_date TIMESTAMP,
                status TEXT
            )
        ''')
        
        self.conn.commit()
    
    def _add_default_channels(self):
        """اصلي چینلونه اضافه کول"""
        for channel in CHANNELS:
            self.cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_username, channel_title, added_by, added_date, is_mandatory)
                VALUES (?, ?, ?, ?, ?)
            ''', (channel, channel, 8089055081, datetime.now(), 1))
        self.conn.commit()
    
    def generate_referral_code(self, user_id):
        """د ریفیرل کوډ جوړول"""
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.cursor.execute('''
            UPDATE users SET referral_code = ? WHERE user_id = ?
        ''', (code, user_id))
        self.conn.commit()
        return code
    
    def add_user(self, user_id, username, first_name, last_name, referred_by=None):
        """نوی کارونکی اضافه کول (د ریفیرل سره)"""
        try:
            # وګورئ چې آیا کارونکی ادمین دی
            is_admin = 1 if user_id in ADMIN_IDS else 0
            
            # د ریفیرل کوډ جوړول
            referral_code = self.generate_referral_code(user_id)
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, joined_date, is_admin, referral_code, referred_by, can_use_free)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now(), 
                  is_admin, referral_code, referred_by, is_admin))
            self.conn.commit()
            
            # که چیرې د بل چا د ریفیرل له لارې راغلی وي
            if referred_by and referred_by != user_id:
                self.cursor.execute('''
                    UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?
                ''', (referred_by,))
                self.conn.commit()
                
                # وګورئ چې آیا دعوت کوونکی ۵ کسانو ته رسیدلی
                self.cursor.execute('''
                    SELECT referral_count FROM users WHERE user_id = ?
                ''', (referred_by,))
                count = self.cursor.fetchone()[0]
                
                if count >= REQUIRED_REFERRALS:
                    self.cursor.execute('''
                        UPDATE users SET can_use_free = 1 WHERE user_id = ?
                    ''', (referred_by,))
                    self.conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"د کارونکي اضافه کولو تېروتنه: {e}")
            return False
    
    def get_referral_stats(self, user_id):
        """د ریفیرل احصایه ترلاسه کول"""
        self.cursor.execute('''
            SELECT referral_code, referral_count, can_use_free FROM users WHERE user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()
        
        if result:
            return {'code': result[0], 'count': result[1], 'can_use': result[2]}
        return {'code': None, 'count': 0, 'can_use': False}
    
    def check_can_use_bot(self, user_id):
        """وګوري چې آیا کارونکی کولی شي بوت وکاروي"""
        # ادمینان تل کولی شي
        if user_id in ADMIN_IDS:
            return True, "ادمین"
        
        self.cursor.execute('''
            SELECT can_use_free, referral_count, channels_joined FROM users WHERE user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()
        
        if not result:
            return False, "کارونکی نه دی ثبت شوی"
        
        can_use_free, referral_count, channels_joined = result
        
        # که وړیا کارول کیدی شي
        if can_use_free:
            return True, "وړیا"
        
        # که ۵ کسان یې دعوت کړي وي
        if referral_count >= REQUIRED_REFERRALS:
            # د can_use_free تازه کول
            self.cursor.execute('''
                UPDATE users SET can_use_free = 1 WHERE user_id = ?
            ''', (user_id,))
            self.conn.commit()
            return True, "ریفیرل بشپړ"
        
        return False, f"تاسو {referral_count}/{REQUIRED_REFERRALS} کسان دعوت کړي دي"
    
    def add_account(self, user_id, account_id, phone, api_id, api_hash, session_string):
        """نوی حساب اضافه کول"""
        try:
            # د حسابونو شمېر معلومول
            self.cursor.execute('''
                SELECT COUNT(*) FROM accounts WHERE user_id = ?
            ''', (user_id,))
            count = self.cursor.fetchone()[0]
            
            if count >= MAX_ACCOUNTS:
                return False, f"تاسو نشئ کولی له {MAX_ACCOUNTS} څخه زیات حسابونه اضافه کړئ"
            
            self.cursor.execute('''
                INSERT INTO accounts 
                (account_id, user_id, phone, api_id, api_hash, session_string, added_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, user_id, phone, api_id, api_hash, session_string, datetime.now(), 'فعال'))
            
            # د کارونکي د حسابونو شمېر زیاتول
            self.cursor.execute('''
                UPDATE users SET total_accounts = total_accounts + 1 WHERE user_id = ?
            ''', (user_id,))
            
            self.conn.commit()
            return True, "حساب په بریالیتوب سره اضافه شو"
        except Exception as e:
            logger.error(f"د حساب اضافه کولو تېروتنه: {e}")
            return False, str(e)
    
    def get_user_accounts(self, user_id):
        """د کارونکي ټول حسابونه ترلاسه کول"""
        self.cursor.execute('''
            SELECT * FROM accounts WHERE user_id = ? AND status = 'فعال'
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def remove_account(self, user_id, account_identifier):
        """حساب لرې کول"""
        self.cursor.execute('''
            DELETE FROM accounts WHERE user_id = ? AND (account_id = ? OR phone = ?)
        ''', (user_id, account_identifier, account_identifier))
        deleted = self.cursor.rowcount
        self.conn.commit()
        
        if deleted > 0:
            self.cursor.execute('''
                UPDATE users SET total_accounts = total_accounts - 1 WHERE user_id = ?
            ''', (user_id,))
            self.conn.commit()
        
        return deleted > 0
    
    def add_report(self, user_id, target, reason, count, accounts_used, total_reports, status='بشپړ شو'):
        """نوی راپور ثبتول"""
        try:
            # د راپور شمېره جوړول
            report_number = f"RP{datetime.now().strftime('%y%m%d%H%M%S')}{random.randint(100,999)}"
            
            self.cursor.execute('''
                INSERT INTO reports 
                (user_id, target, reason, count, accounts_used, total_reports, status, report_date, report_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, target, reason, count, accounts_used, total_reports, status, datetime.now(), report_number))
            
            # د کارونکي د راپورونو شمېر زیاتول
            self.cursor.execute('''
                UPDATE users SET total_reports = total_reports + ? WHERE user_id = ?
            ''', (total_reports, user_id))
            
            self.conn.commit()
            return report_number
        except Exception as e:
            logger.error(f"د راپور ثبتولو تېروتنه: {e}")
            return None
    
    def get_user_stats(self, user_id):
        """د کارونکي احصایه ترلاسه کول"""
        self.cursor.execute('''
            SELECT total_reports, total_accounts FROM users WHERE user_id = ?
        ''', (user_id,))
        user_stats = self.cursor.fetchone()
        
        self.cursor.execute('''
            SELECT COUNT(*) FROM reports WHERE user_id = ? AND date(report_date) = date('now')
        ''', (user_id,))
        today_reports = self.cursor.fetchone()[0]
        
        return {
            'total_reports': user_stats[0] if user_stats else 0,
            'total_accounts': user_stats[1] if user_stats else 0,
            'today_reports': today_reports
        }
    
    def get_mandatory_channels(self):
        """ټول لازمي چینلونه ترلاسه کول"""
        self.cursor.execute('SELECT channel_username, channel_title FROM channels WHERE is_mandatory = 1')
        return self.cursor.fetchall()
    
    def mark_channel_joined(self, user_id, channel_username):
        """کارونکي د چینل سره تړاو ثبتول"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO user_channels (user_id, channel_username, joined_date, verified)
                VALUES (?, ?, ?, ?)
            ''', (user_id, channel_username, datetime.now(), 1))
            
            # د چینلونو شمېر معلومول
            self.cursor.execute('''
                SELECT COUNT(DISTINCT channel_username) FROM user_channels WHERE user_id = ? AND verified = 1
            ''', (user_id,))
            channels_joined = self.cursor.fetchone()[0]
            
            self.cursor.execute('''
                UPDATE users SET channels_joined = ? WHERE user_id = ?
            ''', (channels_joined, user_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"د چینل تړاو ثبتولو تېروتنه: {e}")
            return False
    
    def check_channels_joined(self, user_id):
        """وګوري چې کارونکی ټولو لازمي چینلونو کې شامل دی که نه"""
        channels = self.get_mandatory_channels()
        if not channels:
            return True, []
        
        self.cursor.execute('''
            SELECT channel_username FROM user_channels WHERE user_id = ? AND verified = 1
        ''', (user_id,))
        joined = [row[0] for row in self.cursor.fetchall()]
        
        not_joined = [ch for ch in channels if ch[0] not in joined]
        
        return len(not_joined) == 0, not_joined
    
    def add_channel(self, channel_username, channel_title, added_by):
        """نوی چینل اضافه کول"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_username, channel_title, added_by, added_date)
                VALUES (?, ?, ?, ?)
            ''', (channel_username, channel_title, added_by, datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"د چینل اضافه کولو تېروتنه: {e}")
            return False
    
    def get_all_users(self):
        """ټول کارونکي ترلاسه کول (د ادمین لپاره)"""
        self.cursor.execute('SELECT user_id, username, first_name, total_reports, total_accounts, joined_date, referral_count FROM users')
        return self.cursor.fetchall()
    
    def save_broadcast(self, admin_id, message, total_sent, total_failed):
        """براډکاسټ خوندي کول"""
        try:
            self.cursor.execute('''
                INSERT INTO broadcasts 
                (admin_id, message, total_sent, total_failed, sent_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_id, message, total_sent, total_failed, datetime.now(), 'بشپړ شو'))
            self.conn.commit()
        except Exception as e:
            logger.error(f"د براډکاسټ ثبتولو تېروتنه: {e}")

# ==================== ډیټابیس چمتو کول ====================
db = Database()

# ==================== د کاروونکو ناستې ====================
user_sessions = {}

# ==================== د پرمختګ انیمیشن ====================
def create_progress_animation(current, total, width=20):
    """د پرمختګ انیمیشن جوړول"""
    percent = current / total
    filled = int(width * percent)
    bar = '█' * filled + '░' * (width - filled)
    
    # د انیمیشن حالتونه
    states = ['🔴', '🟠', '🟡', '🟢', '🔵', '🟣']
    state = states[int((current / total) * (len(states) - 1))] if total > 0 else '🔴'
    
    return f"{state} {bar} {current}/{total} ({percent*100:.1f}%)"

# ==================== د بوت کمانډونه ====================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    # د ریفیرل کوډ چک کول
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        referral_code = args[1]
        # د ریفیرل کوډ څخه د کارونکي ID ترلاسه کول
        db.cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        result = db.cursor.fetchone()
        if result and result[0] != user_id:  # ځان ته ریفیرل نشي کیدی
            referred_by = result[0]
    
    # کارونکی ډیټابیس ته اضافه کول
    db.add_user(user_id, username, first_name, last_name, referred_by)
    
    # لومړی وګورئ چې کارونکی په چینلونو کې شامل دی که نه
    check_channels_first(message)

def check_channels_first(message):
    """لومړی د چینلونو چک"""
    user_id = message.chat.id
    
    # که ادمین وي، مستقیم مینو ته لاړ شه
    if user_id in ADMIN_IDS:
        show_main_menu(message)
        return
    
    channels = db.get_mandatory_channels()
    
    if not channels:
        # که چینل نه وي، د ریفیرل چک ته لاړ شه
        check_referral_first(message)
        return
    
    # وګورئ چې آیا کارونکی دمخه په چینلونو کې دی
    all_joined, not_joined = db.check_channels_joined(user_id)
    
    if all_joined:
        check_referral_first(message)
        return
    
    # د چینلونو لیست جوړول
    text = f"""
🔒 **لازمي چینلونه** ━━━━━━━━━━━━━━━━━━━

ګرانه کاروونکیه،

د دې بوت د کارولو لپاره تاسو اړ یاست چې لاندې چینلونو کې شامل شئ:

"""
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for channel in not_joined:
        username, title = channel
        text += f"📢 **{title}**\n"
        text += f"🔗 @{username.replace('@', '')}\n\n"
        
        btn = types.InlineKeyboardButton(
            f"📢 {title} ته شامل شئ",
            url=f"https://t.me/{username.replace('@', '')}"
        )
        markup.add(btn)
    
    # د تایید تڼۍ
    verify_btn = types.InlineKeyboardButton(
        "✅ تایید کړئ چې شامل شوي یاست",
        callback_data="verify_channels"
    )
    markup.add(verify_btn)
    
    bot.send_message(
        user_id,
        text,
        parse_mode='Markdown',
        reply_markup=markup,
        disable_web_page_preview=True
    )

def check_referral_first(message):
    """د ریفیرل چک"""
    user_id = message.chat.id
    
    # که ادمین وي، مستقیم مینو ته لاړ شه
    if user_id in ADMIN_IDS:
        show_main_menu(message)
        return
    
    can_use, reason = db.check_can_use_bot(user_id)
    
    if can_use:
        show_main_menu(message)
    else:
        show_referral_required(message)

def show_referral_required(message):
    """د ریفیرل اړتیا ښودل"""
    user_id = message.chat.id
    
    stats = db.get_referral_stats(user_id)
    
    text = f"""
🔑 **د بوت کارولو لپاره شرایط** ━━━━━━━━━━━━━━━━━━━

ګرانه کاروونکیه،

د دې بوت د کارولو لپاره تاسو اړ یاست چې:
✅ **{REQUIRED_REFERRALS} کسان** د خپل ریفیرل لینک له لارې راجستر کړئ

📊 **ستاسو ریفیرل احصایه:**
━━━━━━━━━━━━━━━━
👥 دعوت شوي کسان: `{stats['count']}/{REQUIRED_REFERRALS}`
🔗 ستاسو ریفیرل کوډ: `{stats['code']}`

📎 **ستاسو ریفیرل لینک:**
`https://t.me/{BOT_USERNAME}?start={stats['code']}`

💡 **څنګه کسان دعوت کړو؟**
1. پورته لینک خپلو ملګرو ته ولیږئ
2. کله چې هغوی بوت پیل کړي، تاسو ته ۱ امتیاز ورکول کیږي
3. کله چې {REQUIRED_REFERRALS} کسان راغلل، بوت به تاسو ته خلاص شي

━━━━━━━━━━━━━━━━━━━
🔄 د تازه کولو لپاره /start وکاروئ
    """
    
    markup = types.InlineKeyboardMarkup()
    share_btn = types.InlineKeyboardButton(
        "📤 ریفیرل لینک شئیر کړئ",
        switch_inline_query=f"د دې بوت کارولو لپاره راشئ! {stats['code']}"
    )
    markup.add(share_btn)
    
    # د بیا چک کولو تڼۍ
    check_btn = types.InlineKeyboardButton(
        "🔄 بیا چک کړئ",
        callback_data="check_referral"
    )
    markup.add(check_btn)
    
    bot.send_message(
        user_id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

def show_main_menu(message):
    """اصلي مینو ښودل"""
    user_id = message.chat.id
    first_name = message.from_user.first_name or "کارونکیه"
    
    welcome_text = f"""
🌟 **د څو حسابونو راپور ورکولو بوت ته ښه راغلاست!** 🌟

سلام **{first_name}**! 👋

🤖 **زما ځانګړتیاوې:**
━━━━━━━━━━━━━━━━━━━━
📱 **څو حسابونه** - تر {MAX_ACCOUNTS} پورې حسابونه اضافه کړئ
⚡ **چټک راپورونه** - ۳ راپورونه په ثانیه کې
📊 **ښکلی احصایه** - د راپورونو شمېرل او ښودل
🎯 **په نښه کول** - کارونکي، ګروپونه او چینلونه
🔢 **د راپور شمېره** - هر راپور خپله ځانګړې شمېره لري
━━━━━━━━━━━━━━━━━━━━

📌 **لاندې تڼیو څخه کار واخلئ:**
    """
    
    # د مینو تڼۍ
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("➕ نوی حساب اضافه کړئ"),
        types.KeyboardButton("📋 حسابونه وګورئ"),
        types.KeyboardButton("🚫 حساب لرې کړئ"),
        types.KeyboardButton("📊 راپور ورکول"),
        types.KeyboardButton("📈 زما احصایه"),
        types.KeyboardButton("🔗 ریفیرل معلومات"),
        types.KeyboardButton("📢 چینلونه"),
        types.KeyboardButton("ℹ️ مرسته")
    ]
    
    # د ادمین لپاره اضافي تڼۍ
    if user_id in ADMIN_IDS:
        buttons.append(types.KeyboardButton("👑 ادمین پینل"))
        buttons.append(types.KeyboardButton("➕ چینل اضافه کړئ"))
    
    markup.add(*buttons)
    
    bot.send_message(user_id, welcome_text, parse_mode='Markdown', reply_markup=markup)

# ==================== د مینو تڼیو مدیریت ====================

@bot.message_handler(func=lambda message: message.text == "➕ نوی حساب اضافه کړئ")
def add_account_start(message):
    user_id = message.chat.id
    
    # لومړی وګورئ چې کارونکی اجازه لري که نه
    can_use, reason = db.check_can_use_bot(user_id)
    
    if not can_use:
        if reason == "کارونکی نه دی ثبت شوی":
            check_channels_first(message)
        else:
            show_referral_required(message)
        return
    
    # د حسابونو شمېر معلومول
    accounts = db.get_user_accounts(user_id)
    if len(accounts) >= MAX_ACCOUNTS:
        bot.send_message(
            user_id,
            f"❌ تاسو نشئ کولی له {MAX_ACCOUNTS} څخه زیات حسابونه اضافه کړئ!\n"
            f"لومړی یو حساب لرې کړئ."
        )
        return
    
    user_sessions[user_id] = {'step': 'waiting_api_id'}
    
    msg = f"""
🔐 **د نوي حساب اضافه کول** ━━━━━━━━━━━━━━━━━━━

📌 **لارښود:**
1. [my.telegram.org](https://my.telegram.org) ته لاړ شئ
2. په خپل حساب کې ننوځئ
3. 'API Development Tools' باندې کلیک وکړئ
4. هلته به **API ID** او **API Hash** درکړل شي

━━━━━━━━━━━━━━━━━━━
🔢 مهرباني وکړئ خپل **API ID** ولیږئ:
    """
    
    bot.send_message(user_id, msg, parse_mode='Markdown', disable_web_page_preview=True)

@bot.message_handler(func=lambda message: message.text == "📋 حسابونه وګورئ")
def view_accounts(message):
    user_id = message.chat.id
    
    # لومړی وګورئ چې کارونکی اجازه لري که نه
    can_use, reason = db.check_can_use_bot(user_id)
    
    if not can_use:
        if reason == "کارونکی نه دی ثبت شوی":
            check_channels_first(message)
        else:
            show_referral_required(message)
        return
    
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        bot.send_message(
            user_id, 
            "📭 **تاسو کوم حساب نلرئ!**\n\n"
            "د '➕ نوی حساب اضافه کړئ' په تڼۍ کلیک وکړئ.",
            parse_mode='Markdown'
        )
        return
    
    msg = "📋 **ستاسو حسابونه**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, acc in enumerate(accounts, 1):
        msg += f"**{i}.** 📱 `{acc[2]}`\n"
        msg += f"   🆔 `{acc[0]}`\n"
        msg += f"   📅 {acc[5][:10]}\n"
        msg += f"   📊 راپورونه: {acc[7]}\n"
        msg += "━━━━━━━━━━━━━━━━\n"
    
    msg += f"\n📊 **ټولټال:** {len(accounts)} حسابونه"
    
    bot.send_message(user_id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🚫 حساب لرې کړئ")
def remove_account_start(message):
    user_id = message.chat.id
    
    # لومړی وګورئ چې کارونکی اجازه لري که نه
    can_use, reason = db.check_can_use_bot(user_id)
    
    if not can_use:
        if reason == "کارونکی نه دی ثبت شوی":
            check_channels_first(message)
        else:
            show_referral_required(message)
        return
    
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        bot.send_message(user_id, "📭 تاسو کوم حساب نلرئ!")
        return
    
    msg = "🚫 **د حساب لرې کول**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "مهرباني وکړئ د هغه حساب **نښه** یا **شمېره** ولیږئ:\n\n"
    
    for acc in accounts:
        msg += f"• 🆔 `{acc[0]}` - 📱 `{acc[2]}`\n"
    
    user_sessions[user_id] = {'step': 'waiting_remove_account'}
    bot.send_message(user_id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📊 راپور ورکول")
def report_start(message):
    user_id = message.chat.id
    
    # لومړی وګورئ چې کارونکی اجازه لري که نه
    can_use, reason = db.check_can_use_bot(user_id)
    
    if not can_use:
        if reason == "کارونکی نه دی ثبت شوی":
            check_channels_first(message)
        else:
            show_referral_required(message)
        return
    
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        bot.send_message(
            user_id, 
            "❌ **تاسو کوم فعال حساب نلرئ!**\n\n"
            "لومړی یو حساب اضافه کړئ.",
            parse_mode='Markdown'
        )
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 لغوه کول"))
    
    msg = f"""
📊 **راپور ورکول** ━━━━━━━━━━━━━━━━━━━

✅ **فعال حسابونه:** {len(accounts)}

📌 مهرباني وکړئ د هغه کارونکي **یوزرنیم** یا **چینل لینک** ولیږئ:

مثالونه:
• `@username`
• `https://t.me/username`
• `https://t.me/joinchat/xxxxxx`

━━━━━━━━━━━━━━━━━━━
    """
    
    user_sessions[user_id] = {'step': 'waiting_report_target'}
    bot.send_message(user_id, msg, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📈 زما احصایه")
def show_my_stats(message):
    user_id = message.chat.id
    
    stats = db.get_user_stats(user_id)
    referral = db.get_referral_stats(user_id)
    can_use, reason = db.check_can_use_bot(user_id)
    
    # د درجه محاسبه
    if user_id in ADMIN_IDS:
        rank = "👑 ادمین"
    elif can_use:
        rank = "✅ فعال"
    else:
        rank = f"⏳ {referral['count']}/{REQUIRED_REFERRALS} ریفیرل"
    
    stats_msg = f"""
📊 **ستاسو احصایه** ━━━━━━━━━━━━━━━━━━━

👥 **ټول حسابونه:** `{stats['total_accounts']}`
📊 **ټول راپورونه:** `{stats['total_reports']}`
📅 **ننني راپورونه:** `{stats['today_reports']}`

🔗 **ریفیرل:**
👥 دعوت شوي: `{referral['count']}/{REQUIRED_REFERRALS}`
🔑 کوډ: `{referral['code']}`

⚡ **د راپور سرعت:** `3/sec`
📈 **حالت:** {rank}

━━━━━━━━━━━━━━━━━━━
    """
    
    bot.send_message(user_id, stats_msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "🔗 ریفیرل معلومات")
def referral_info(message):
    user_id = message.chat.id
    
    stats = db.get_referral_stats(user_id)
    can_use, reason = db.check_can_use_bot(user_id)
    
    text = f"""
🔗 **ستاسو ریفیرل معلومات** ━━━━━━━━━━━━━━━━━━━

📊 **احصایه:**
━━━━━━━━━━━━━━━━
👥 دعوت شوي کسان: `{stats['count']}/{REQUIRED_REFERRALS}`
🔢 پاتې شوي: `{REQUIRED_REFERRALS - stats['count']}` کسان
📊 حالت: `{'✅ فعال' if can_use else '⏳ انتظار'}`

🔑 **ستاسو ریفیرل کوډ:** `{stats['code']}`

📎 **ریفیرل لینک:**
`https://t.me/{BOT_USERNAME}?start={stats['code']}`

💎 **ګټې:**
• د {REQUIRED_REFERRALS} کسانو په دعوت سره بوت تاسو ته خلاصیږي
• ادمینان تل وړیا کارولی شي
• هر دعوت شوی کس ۱ امتیاز شمېرل کیږي

━━━━━━━━━━━━━━━━━━━
    """
    
    markup = types.InlineKeyboardMarkup()
    share_btn = types.InlineKeyboardButton(
        "📤 ریفیرل لینک شئیر کړئ",
        switch_inline_query=f"د دې بوت کارولو لپاره راشئ! {stats['code']}"
    )
    markup.add(share_btn)
    
    bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📢 چینلونه")
def show_channels(message):
    user_id = message.chat.id
    
    channels = db.get_mandatory_channels()
    
    if not channels:
        bot.send_message(
            user_id,
            "📢 **چینلونه**\n\nلا تر اوسه کوم چینل نشته!",
            parse_mode='Markdown'
        )
        return
    
    # وګورئ چې کوم چینلونو کې شامل دی
    all_joined, not_joined = db.check_channels_joined(user_id)
    
    text = "📢 **زموږ چینلونه**\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for channel in channels:
        username, title = channel
        status = "✅" if username not in [c[0] for c in not_joined] else "❌"
        text += f"{status} **{title}**\n"
        text += f"🔗 @{username.replace('@', '')}\n\n"
        
        if username in [c[0] for c in not_joined]:
            btn = types.InlineKeyboardButton(
                f"📢 {title} ته شامل شئ",
                url=f"https://t.me/{username.replace('@', '')}"
            )
            markup.add(btn)
    
    if not_joined:
        # د تایید تڼۍ
        verify_btn = types.InlineKeyboardButton(
            "✅ تایید کړئ چې شامل شوي یاست",
            callback_data="verify_channels"
        )
        markup.add(verify_btn)
    
    bot.send_message(
        user_id,
        text,
        parse_mode='Markdown',
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ مرسته")
def help_message(message):
    user_id = message.chat.id
    
    can_use, reason = db.check_can_use_bot(user_id)
    
    if not can_use and user_id not in ADMIN_IDS:
        help_text = f"""
ℹ️ **مرسته او لارښود** ━━━━━━━━━━━━━━━━━━━

📌 **د بوت کارولو لپاره شرایط:**

۱. **لازمي چینلونو** کې شامل شئ
   {chr(10).join(['   • ' + c for c in CHANNELS])}

۲. **{REQUIRED_REFERRALS} کسان** دعوت کړئ

🔗 **ستاسو ریفیرل حالت:**
{reason}

📞 **مرستې لپاره:** {ADMIN_USERNAME}
━━━━━━━━━━━━━━━━━━━
        """
    else:
        help_text = f"""
ℹ️ **مرسته او لارښود** ━━━━━━━━━━━━━━━━━━━

📌 **څنګه کار وکړو:**

**۱️⃣ حسابونه اضافه کړئ:**
   • په '➕ نوی حساب اضافه کړئ' کلیک وکړئ
   • API ID او API Hash ولیږئ
   • د تلیفون شمېره او تایید کوډ ولیږئ

**۲️⃣ راپور ورکول:**
   • په '📊 راپور ورکول' کلیک وکړئ
   • هدف (یوزرنیم/چینل) ولیږئ
   • د راپور متن ولیږئ
   • شمېره ولیږئ (۱-۱۰۰)

**۳️⃣ ریفیرل:**
   • '🔗 ریفیرل معلومات' وګورئ
   • لینک ملګرو ته ولیږئ
   • {REQUIRED_REFERRALS} کسان دعوت کړئ

**۴️⃣ لازمي چینلونه:**
   {chr(10).join(['   • ' + c for c in CHANNELS])}

━━━━━━━━━━━━━━━━━━━
⚠️ **یادونه:**
• اعظمي راپورونه: ۱۰۰
• د حسابونو اعظمي شمېر: {MAX_ACCOUNTS}
• د راپور سرعت: ۳/sec

📞 **مرستې لپاره:** {ADMIN_USERNAME}
━━━━━━━━━━━━━━━━━━━
        """
    
    bot.send_message(user_id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "👑 ادمین پینل")
def admin_panel(message):
    user_id = message.chat.id
    
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "⛔ تاسو ادمین نه یاست!")
        return
    
    show_admin_panel(message)

@bot.message_handler(func=lambda message: message.text == "➕ چینل اضافه کړئ")
def add_channel_start(message):
    user_id = message.chat.id
    
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "⛔ تاسو ادمین نه یاست!")
        return
    
    msg = bot.send_message(
        user_id,
        "➕ **نوی چینل اضافه کړئ**\n\n"
        "مهرباني وکړئ د چینل **یوزرنیم** (د @ سره) ولیږئ:\n"
        "مثال: @mychannel",
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(msg, process_add_channel)

def process_add_channel(message):
    user_id = message.chat.id
    channel_input = message.text.strip()
    
    # د @ لرې کول که وي
    if channel_input.startswith('@'):
        channel_username = channel_input[1:]
    else:
        channel_username = channel_input
    
    # د چینل عنوان ترلاسه کول
    bot.send_message(
        user_id,
        f"مهرباني وکړئ د `@{channel_username}` چینل **نوم** ولیږئ:",
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(message, lambda m: save_channel(m, channel_username))

def save_channel(message, channel_username):
    user_id = message.chat.id
    channel_title = message.text
    
    if db.add_channel(channel_username, channel_title, user_id):
        bot.send_message(
            user_id,
            f"✅ چینل `@{channel_username}` په بریالیتوب سره اضافه شو!",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            user_id,
            f"❌ چینل اضافه نشو! ممکن مخکې اضافه شوی وي.",
            parse_mode='Markdown'
        )

# ==================== د متن پیغامونو مدیریت ====================

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.chat.id
    text = message.text
    
    if text == "🔙 لغوه کول":
        user_sessions[user_id] = {}
        show_main_menu(message)
        return
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    step = user_sessions[user_id].get('step')
    
    if step == 'waiting_api_id':
        user_sessions[user_id]['api_id'] = text
        user_sessions[user_id]['step'] = 'waiting_api_hash'
        bot.send_message(user_id, "🔑 مهرباني وکړئ خپل **API Hash** ولیږئ:")
        
    elif step == 'waiting_api_hash':
        user_sessions[user_id]['api_hash'] = text
        user_sessions[user_id]['step'] = 'waiting_phone'
        bot.send_message(user_id, "📱 مهرباني وکړئ خپل **د تلیفون شمېره** (د هیواد کوډ سره) ولیږئ:\nمثال: `+93701234567`", parse_mode='Markdown')
        
    elif step == 'waiting_phone':
        user_sessions[user_id]['phone'] = text
        user_sessions[user_id]['step'] = 'waiting_code'
        
        bot.send_message(
            user_id, 
            "✅ یو تایید کوډ به تلیفون ته راشي.\n"
            "مهرباني وکړئ هغه **کوډ** دلته ولیږئ:"
        )
        
    elif step == 'waiting_code':
        # حساب خوندي کول
        account_id = f"ACC{random.randint(10000, 99999)}"
        
        # ډیټابیس ته اضافه کول
        success, message_text = db.add_account(
            user_id,
            account_id,
            user_sessions[user_id]['phone'],
            user_sessions[user_id]['api_id'],
            user_sessions[user_id]['api_hash'],
            "session_string_here"  # د Telethon سیشن
        )
        
        if success:
            bot.send_message(
                user_id,
                f"✅ **حساب په بریالیتوب سره اضافه شو!**\n\n"
                f"📱 شمېره: `{user_sessions[user_id]['phone']}`\n"
                f"🆔 د حساب نښه: `{account_id}`\n"
                f"📅 نیټه: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, f"❌ {message_text}")
        
        user_sessions[user_id] = {}
        
    elif step == 'waiting_remove_account':
        # حساب لرې کول
        if db.remove_account(user_id, text):
            bot.send_message(user_id, f"✅ حساب په بریالیتوب سره لرې شو!")
        else:
            bot.send_message(user_id, "❌ حساب و نه موندل شو!")
        
        user_sessions[user_id] = {}
        
    elif step == 'waiting_report_target':
        user_sessions[user_id]['target'] = text
        user_sessions[user_id]['step'] = 'waiting_report_reason'
        bot.send_message(user_id, "📝 د راپور **متن** ولیږئ:")
        
    elif step == 'waiting_report_reason':
        user_sessions[user_id]['reason'] = text
        user_sessions[user_id]['step'] = 'waiting_report_count'
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        buttons = [
            types.KeyboardButton("10"),
            types.KeyboardButton("25"),
            types.KeyboardButton("50"),
            types.KeyboardButton("75"),
            types.KeyboardButton("100"),
            types.KeyboardButton("🔙 لغوه کول")
        ]
        markup.add(*buttons)
        
        bot.send_message(user_id, "🔢 څو ځله راپور ولیږم؟ (له ۱ څخه تر ۱۰۰ پورې)", reply_markup=markup)
        
    elif step == 'waiting_report_count':
        try:
            count = int(text) if text.isdigit() else 50
            if count < 1 or count > 100:
                bot.send_message(user_id, "⚠️ مهرباني وکړئ له ۱ څخه تر ۱۰۰ پورې شمېره وکاروئ!")
                return
            
            user_sessions[user_id]['count'] = count
            start_reporting(message)
        except:
            bot.send_message(user_id, "❌ مهرباني وکړئ یوه سمه شمېره ولیکئ!")

# ==================== د راپور لیږلو پروسه ====================

def start_reporting(message):
    user_id = message.chat.id
    data = user_sessions.get(user_id, {})
    
    target = data.get('target', 'نامعلوم')
    reason = data.get('reason', '')
    count = data.get('count', 1)
    
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        bot.send_message(user_id, "❌ تاسو کوم فعال حساب نلرئ!")
        return
    
    total_reports = count * len(accounts)
    
    # د راپور شمېره
    report_number = f"RP{datetime.now().strftime('%y%m%d%H%M%S')}{random.randint(100,999)}"
    
    # ښکلی پیل پیغام
    progress_msg = bot.send_message(
        user_id,
        f"""
🚀 **راپور ورکول پیل شو!** ━━━━━━━━━━━━━━━━━━━

🎯 **هدف:** `{target}`
📝 **دلیل:** {reason[:50]}{'...' if len(reason) > 50 else ''}
👥 **حسابونه:** {len(accounts)}
📊 **د هر حساب راپورونه:** {count}
📈 **ټول راپورونه:** `{total_reports}`
🆔 **د راپور شمېره:** `{report_number}`

⏳ راپورونه لیږل کېږي...
━━━━━━━━━━━━━━━━━━━
        """,
        parse_mode='Markdown'
    )
    
    # د راپور لیږلو سیمولیشن
    reports_sent = 0
    start_time = time.time()
    
    for acc_index, account in enumerate(accounts, 1):
        for i in range(count):
            time.sleep(REPORT_DELAY)  # ۳ راپورونه په ثانیه کې
            
            reports_sent += 1
            
            # د راپور شمېره
            report_id = random.randint(100000, 999999)
            
            # د پرمختګ تازه کول
            if reports_sent % 3 == 0 or reports_sent == total_reports:
                elapsed = time.time() - start_time
                speed = reports_sent / elapsed if elapsed > 0 else 0
                remaining = (total_reports - reports_sent) / speed if speed > 0 else 0
                
                progress_bar = create_progress_animation(reports_sent, total_reports)
                
                # د وخت محاسبه
                if remaining < 60:
                    remaining_str = f"{remaining:.1f} ث"
                else:
                    remaining_str = f"{remaining/60:.1f} دقی"
                
                progress_text = f"""
🚀 **راپور ورکول** ━━━━━━━━━━━━━━━━━━━

🎯 **هدف:** `{target}`
📊 **پرمختګ:**
{progress_bar}

✅ **لیږل شوي:** {reports_sent}/{total_reports}
⚡ **سرعت:** {speed:.1f}/sec
⏱ **پاتې وخت:** {remaining_str}
🔢 **وروستی راپور:** #{report_id}

📱 **حساب:** {acc_index}/{len(accounts)} | {i+1}/{count}
━━━━━━━━━━━━━━━━━━━
                """
                
                try:
                    bot.edit_message_text(
                        progress_text,
                        user_id,
                        progress_msg.message_id,
                        parse_mode='Markdown'
                    )
                except:
                    pass
    
    # پای
    elapsed = time.time() - start_time
    avg_speed = total_reports / elapsed if elapsed > 0 else 0
    
    # په ډیټابیس کې ثبتول
    db_report_number = db.add_report(user_id, target, reason, count, len(accounts), total_reports)
    
    final_msg = f"""
✅ **راپور ورکول بشپړ شو!** 🎉 ━━━━━━━━━━━━━━━━━━━

📊 **د راپور لنډیز:**
━━━━━━━━━━━━━━━━
🎯 **هدف:** `{target}`
👥 **کارول شوي حسابونه:** {len(accounts)}
📊 **د هر حساب راپورونه:** {count}
📈 **ټول لیږل شوي راپورونه:** `{total_reports}`
🆔 **د راپور نښه:** `{report_number}`
⚡ **اوسط سرعت:** {avg_speed:.1f}/sec
⏱ **ټول وخت:** {elapsed:.1f} ثانیې
⏰ **وخت:** {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━

📝 **د راپور متن:** {reason[:100]}

✨ **مننه د کارونې لپاره!**
    """
    
    bot.send_message(user_id, final_msg, parse_mode='Markdown')
    
    user_sessions[user_id] = {}

# ==================== د ادمین پینل ====================

def show_admin_panel(message):
    user_id = message.chat.id
    
    # ټولیزه احصایه
    users = db.get_all_users()
    
    total_users = len(users)
    total_reports = sum(user[3] for user in users)
    total_accounts = sum(user[4] for user in users)
    
    # ننني کارونکي
    today = datetime.now().date()
    today_users = sum(1 for user in users if datetime.strptime(str(user[5]), '%Y-%m-%d %H:%M:%S.%f').date() == today)
    
    # ریفیرل احصایه
    total_referrals = sum(user[6] for user in users)
    
    admin_text = f"""
👑 **د ادمین پینل** ━━━━━━━━━━━━━━━━━━━

🆔 **ادمین:** `{user_id}`
📊 **د بوت حالت:** ✅ فعال

📊 **ټولیزه احصایه:**
━━━━━━━━━━━━━━━━
👥 ټول کارونکي: `{total_users}`
📅 ننني کارونکي: `{today_users}`
📱 ټول حسابونه: `{total_accounts}`
📊 ټول راپورونه: `{total_reports}`
🔗 ټول ریفیرلونه: `{total_referrals}`

⚡ د راپور سرعت: `3/sec`
⏱ وخت: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`
━━━━━━━━━━━━━━━━━━━

📌 **یوه برخه وټاکئ:**
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📊 مفصل احصایه", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 کارونکي", callback_data="admin_users"),
        types.InlineKeyboardButton("📢 براډکاسټ", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📋 راپورونه", callback_data="admin_reports"),
        types.InlineKeyboardButton("📢 چینلونه", callback_data="admin_channels"),
        types.InlineKeyboardButton("🔗 ریفیرل", callback_data="admin_referral"),
        types.InlineKeyboardButton("🚫 بلاک شوي", callback_data="admin_banned"),
    ]
    markup.add(*buttons)
    
    bot.send_message(user_id, admin_text, parse_mode='Markdown', reply_markup=markup)

# ==================== د کال بیک مدیریت ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "verify_channels":
        # ټول چینلونه تایید کړئ
        channels = db.get_mandatory_channels()
        for channel in channels:
            db.mark_channel_joined(user_id, channel[0])
        
        bot.answer_callback_query(call.id, "✅ تایید شو! مننه")
        
        # د ریفیرل چک ته لاړ شه
        check_referral_first(call.message)
    
    elif data == "check_referral":
        bot.answer_callback_query(call.id, "🔄 بیا چک کېږي...")
        check_referral_first(call.message)
    
    elif data == "admin_stats":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        # مفصل احصایه
        users = db.get_all_users()
        
        total_users = len(users)
        total_reports = sum(user[3] for user in users)
        total_accounts = sum(user[4] for user in users)
        total_referrals = sum(user[6] for user in users)
        
        # فعال کارونکي (چې راپور یې لیږلی)
        active_users = sum(1 for user in users if user[3] > 0)
        
        # ننني راپورونه
        db.cursor.execute("SELECT COUNT(*) FROM reports WHERE date(report_date) = date('now')")
        today_reports = db.cursor.fetchone()[0]
        
        stats_text = f"""
📊 **مفصل احصایه** ━━━━━━━━━━━━━━━━━━━

👥 **کارونکي:**
• ټول: `{total_users}`
• ننني: `{len([u for u in users if datetime.strptime(str(u[5]), '%Y-%m-%d %H:%M:%S.%f').date() == datetime.now().date()])}`
• فعال: `{active_users}`

📊 **راپورونه:**
• ټول: `{total_reports}`
• ننني: `{today_reports}`
• اوسط: `{total_reports/total_users if total_users > 0 else 0:.1f}`

📱 **حسابونه:**
• ټول: `{total_accounts}`
• اوسط: `{total_accounts/total_users if total_users > 0 else 0:.1f}`

🔗 **ریفیرل:**
• ټول: `{total_referrals}`
• اوسط: `{total_referrals/total_users if total_users > 0 else 0:.1f}`
• وړ کارونکي: `{len([u for u in users if u[6] >= REQUIRED_REFERRALS])}`

━━━━━━━━━━━━━━━━━━━
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            stats_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "admin_users":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        users = db.get_all_users()
        
        if not users:
            bot.edit_message_text(
                "📭 لا تر اوسه کوم کارونکی نشته!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
            )
            return
        
        text = "👥 **ټول کارونکي**\n━━━━━━━━━━━━━━━━\n\n"
        
        for i, user in enumerate(users[:10], 1):  # لومړي ۱۰ کارونکي
            text += f"**{i}.** 🆔 `{user[0]}`\n"
            text += f"   📝 @{user[1] if user[1] else 'نشته'}\n"
            text += f"   📊 راپورونه: {user[3]} | حسابونه: {user[4]}\n"
            text += f"   🔗 ریفیرل: {user[6]}\n"
            text += f"   📅 {str(user[5])[:10]}\n"
            text += "━━━━━━━━━━━━━━━━\n"
        
        if len(users) > 10:
            text += f"\nاو {len(users) - 10} نور..."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "admin_broadcast":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        bot.edit_message_text(
            "📢 **براډکاسټ**\n\n"
            "مهرباني وکړئ هغه پیغام ولیږئ چې ټولو کاروونکو ته واستول شي.\n"
            "تاسو کولی شئ متن، انځور، ویډیو او نور ولېږئ.\n\n"
            "❌ د لغوه کولو لپاره /cancel ولیږئ.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        bot.register_next_step_handler(call.message, process_broadcast)
    
    elif data == "admin_channels":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        channels = db.get_mandatory_channels()
        
        text = "📢 **د چینلونو مدیریت**\n\n"
        
        if channels:
            for i, ch in enumerate(channels, 1):
                text += f"{i}. 📢 @{ch[0].replace('@', '')} - {ch[1]}\n"
        else:
            text += "لا تر اوسه کوم چینل نشته!\n"
        
        text += f"\n📊 ټولټال: {len(channels)} چینلونه"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("➕ نوی چینل", callback_data="admin_add_channel"),
            types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin")
        ]
        markup.add(*buttons)
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "admin_add_channel":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        bot.edit_message_text(
            "➕ **نوی چینل اضافه کړئ**\n\n"
            "مهرباني وکړئ د چینل **یوزرنیم** (د @ سره) ولیږئ:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        bot.register_next_step_handler(call.message, process_add_channel_admin)
    
    elif data == "admin_referral":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        users = db.get_all_users()
        
        total_users = len(users)
        total_referrals = sum(user[6] for user in users)
        avg_referrals = total_referrals / total_users if total_users > 0 else 0
        
        # هغه کارونکي چې ۵+ ریفیرل لري
        qualified_users = sum(1 for user in users if user[6] >= REQUIRED_REFERRALS)
        
        # غوره ۵ ریفیرلر
        top_referrers = sorted(users, key=lambda x: x[6], reverse=True)[:5]
        
        text = f"""
🔗 **د ریفیرل احصایه** ━━━━━━━━━━━━━━━━━━━

📊 **ټولیز:**
👥 ټول کارونکي: `{total_users}`
👥 ټول ریفیرلونه: `{total_referrals}`
📊 اوسط ریفیرل: `{avg_referrals:.1f}`

✅ وړ کارونکي (۵+): `{qualified_users}`
📈 سلنه: `{(qualified_users/total_users*100) if total_users > 0 else 0:.1f}%`

🏆 **غوره ریفیرلرونه:**
"""
        
        for i, user in enumerate(top_referrers, 1):
            if user[6] > 0:
                text += f"{i}. @{user[1] or 'نشته'} - {user[6]} ریفیرلونه\n"
        
        text += "━━━━━━━━━━━━━━━━━━━"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "admin_reports":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        # وروستي ۱۰ راپورونه
        db.cursor.execute('''
            SELECT report_number, user_id, target, total_reports, report_date 
            FROM reports 
            ORDER BY report_date DESC 
            LIMIT 10
        ''')
        reports = db.cursor.fetchall()
        
        if not reports:
            text = "📋 لا تر اوسه کوم راپور نشته!"
        else:
            text = "📋 **وروستي راپورونه**\n━━━━━━━━━━━━━━━━\n\n"
            for r in reports:
                text += f"🆔 {r[0]}\n"
                text += f"👤 کارونکی: `{r[1]}`\n"
                text += f"🎯 هدف: {r[2]}\n"
                text += f"📊 شمېر: {r[3]}\n"
                text += f"⏱ {str(r[4])[:16]}\n"
                text += "━━━━━━━━━━━━━━━━\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "admin_banned":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        # بلاک شوي کارونکي
        db.cursor.execute("SELECT user_id, username FROM users WHERE is_banned = 1")
        banned = db.cursor.fetchall()
        
        if not banned:
            text = "🚫 **بلاک شوي کارونکي**\n\nهیڅ بلاک شوی کارونکی نشته!"
        else:
            text = "🚫 **بلاک شوي کارونکي**\n━━━━━━━━━━━━━━━━\n\n"
            for b in banned:
                text += f"• 🆔 `{b[0]}` - @{b[1] or 'نشته'}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 شاته", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    elif data == "back_to_admin":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "⛔ تاسو ادمین نه یاست!")
            return
        
        # بیرته ادمین پینل ته
        show_admin_panel(call.message)

def process_add_channel_admin(message):
    user_id = message.chat.id
    channel_input = message.text.strip()
    
    # د @ لرې کول که وي
    if channel_input.startswith('@'):
        channel_username = channel_input[1:]
    else:
        channel_username = channel_input
    
    # د چینل عنوان ترلاسه کول
    msg = bot.send_message(
        user_id,
        f"مهرباني وکړئ د `@{channel_username}` چینل **نوم** ولیږئ:",
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(msg, lambda m: save_channel_admin(m, channel_username))

def save_channel_admin(message, channel_username):
    user_id = message.chat.id
    channel_title = message.text
    
    if db.add_channel(channel_username, channel_title, user_id):
        bot.send_message(
            user_id,
            f"✅ چینل `@{channel_username}` په بریالیتوب سره اضافه شو!",
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            user_id,
            f"❌ چینل اضافه نشو! ممکن مخکې اضافه شوی وي.",
            parse_mode='Markdown'
        )
    
    # بیرته ادمین پینل ته
    show_admin_panel(message)

def process_broadcast(message):
    user_id = message.chat.id
    
    if message.text == '/cancel':
        bot.reply_to(message, "❌ براډکاسټ لغوه شو.")
        show_admin_panel(message)
        return
    
    users = db.get_all_users()
    total_users = len(users)
    
    status_msg = bot.reply_to(
        message,
        f"📢 **براډکاسټ پیل شو**\n\n"
        f"👥 ټول کارونکي: {total_users}\n"
        f"⏳ لیږل کېږي...\n"
        f"0/{total_users} بشپړ شو",
        parse_mode='Markdown'
    )
    
    sent = 0
    failed = 0
    
    for i, user in enumerate(users, 1):
        try:
            bot.copy_message(
                user[0],
                message.chat.id,
                message.message_id
            )
            sent += 1
            time.sleep(0.05)  # د سپیم مخنیوی
        except Exception as e:
            failed += 1
            logger.error(f"براډکاسټ تېروتنه for {user[0]}: {e}")
        
        # د پرمختګ تازه کول
        if i % 10 == 0 or i == total_users:
            try:
                bot.edit_message_text(
                    f"📢 **براډکاسټ**\n\n"
                    f"👥 ټول کارونکي: {total_users}\n"
                    f"✅ بریالي: {sent}\n"
                    f"❌ ناکام: {failed}\n"
                    f"📊 پرمختګ: {i}/{total_users} ({(i/total_users*100):.1f}%)",
                    status_msg.chat.id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                pass
    
    # پای
    db.save_broadcast(user_id, message.text or "میډیا", sent, failed)
    
    bot.edit_message_text(
        f"✅ **براډکاسټ بشپړ شو!**\n\n"
        f"👥 ټول کارونکي: {total_users}\n"
        f"✅ بریالي: {sent}\n"
        f"❌ ناکام: {failed}\n"
        f"⏱ وخت: {datetime.now().strftime('%H:%M:%S')}",
        status_msg.chat.id,
        status_msg.message_id,
        parse_mode='Markdown'
    )
    
    show_admin_panel(message)

# ==================== د بوت پیل ====================

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════╗
    ║     Telegram Report Bot v3.0           ║
    ║     د څو حسابونو راپور ورکولو بوت      ║
    ╠════════════════════════════════════════╣
    ║  ادمین: @XFPro43                        ║
    ║  چینلونه: @ProTech43, @Pro43Zone, @SQ_BOTZ ║
    ╚════════════════════════════════════════╝
    """)
    
    logger.info("🤖 بوت پیل شو...")
    logger.info(f"👑 ادمین: 8089055081 (@XFPro43)")
    logger.info(f"📢 چینلونه: {CHANNELS}")
    logger.info(f"⚡ د راپور سرعت: 3/sec")
    logger.info(f"🔗 د ریفیرل شرط: {REQUIRED_REFERRALS} کسان")
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"❌ تېروتنه: {e}")
        time.sleep(3)