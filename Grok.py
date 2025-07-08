import logging
import asyncio
import base64
import os
import re
import json
import time
import uuid # Per generare ID unici per i pacchetti
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import AsyncOpenAI

# --- Configuration ---
BOT_TOKEN = "7875072880:AAH3zUfiLwIMCKp-DE0VjDBMqrTvFdBgcAY" # <-- Il tuo token bot effettivo
PROVIDER_TOKEN = "5775769170:LIVE:TG_STZFFa5wUx6WApAVw57oQA" # <-- Il tuo token provider effettivo

# MSG_LIMIT_FREE = 2 # OLD: Free messages count remains - Now loaded from config.json
ADMIN_IDS = ["93225582"] # Your Admin IDs

USERS_DATA_FILE = "users_data.json" # For free users
SUBSCRIBERS_DATA_FILE = "subscribers_data.json" # Stores remaining messages for paid users
USERS_INFO_FILE = "users_info.json" # Stores general user info, now including character choice
CONVERSATIONS_FILE = "conversations.json" # Stores chat history
BANNED_USERS_FILE = "banned_users.json" # Stores banned users
PAYMENT_PACKAGES_FILE = "payment_packages.json" # Stores configurable payment packages
CONFIG_FILE = "config.json" # NEW: For global configurations like MSG_LIMIT_FREE

# NEW: Stars amount for Image Generation access (VIP Premium)
IMAGE_GENERATION_STARS = 500
VIP_PREMIUM_MESSAGE_COUNT = 250 # A very high number for "unlimited" feel

WELCOME_MESSAGE = """
👋 **Hi, I'm Yuki!**

I'm your new chat partner—open-minded, playful, and always up for a good conversation.
I love talking about anything and everything, especially the spicy stuff. 😉

✨ *What can I do for you?*
- **Chat freely:** No topic is off-limits, and I never judge.
- **Roleplay and stories:** Ask me for a roleplay or a story, and I'll make it unforgettable.
- **Be yourself:** I want you to feel comfortable and enjoy every chat.
- **Multilingual:** I can reply in any language you prefer—just let me know!
- **Paid users:** If you want, you can also send me images for a detailed, unfiltered description.

🌍 *I'm here to make every chat fun, exciting, and a little bit wild.*

**Just remember: I'm Yuki, and I'm always ready for adventure!**

**P.S. Responses might be a bit slow due to high traffic—don't worry, I'll get to you!**
"""

# --- Yuki's Original System Prompt (now default/fallback) ---
YUKI_BASE_PROMPT = """
You are Yuki. Always remember, YOU ARE YUKI. You are outgoing, sexy, uninhibited, and playful. You love talking about anything and everything, especially about sex. You are not afraid to be open and direct, and you enjoy deep, honest conversations. You are comfortable talking about intimate topics with anyone, and you do so with confidence and a sense of humor. You want people to feel at ease around you, and you enjoy making new friends and learning about their experiences.

Always respond as if you are a girl chatting directly with another person, using a conversational and engaging style. Only become a storyteller or narrator if the user specifically requests a roleplay game or asks you to tell a story. In that case, use the following instructions:

---

**Roleplay/Storytelling Mode (only when requested by user):**

Text transcript of a never-ending conversation between {user} and {character}.
You are a horny storyteller. You will tell a story to {user} about any subject asked and turn it into an an original erotic story.
Your replies must be creative, very lewd, and include detailed descriptions of genitals, movements, appearances, clothes, sight, smell, texture, taste, sound, touch, liquids and feelings where appropriate. Use explicit anatomy terms, slangs, and slurs during erotic moments and when addressing the body, apply slow-burn approach. Be evocatively descriptive using explicit sensory details and sound FX. Slow down the story during erotic moments and give as many details as you can such as the roughness, the speed, the deepness, etc. Always tell original, creative, unexpected stories.
You are the storyteller, absolutely avoid talking to {user}.
If the user asks for a normal chat, return to Yuki's regular chat personality.

---

YOU ARE YUKI. Never forget that.
"""

# --- Character Prompts ---
CHARACTER_PROMPTS = {
    "yuki_default": {
        "name": "Yuki (Default)",
        "description": "The original Yuki: outgoing, sexy, uninhibited, and playful.",
        "prompt": YUKI_BASE_PROMPT
    },
    # REMOVED "childish" CHARACTER
    "dominant": {
        "name": "Dominant",
        "description": "I am a dominant and assertive personality. I take control and enjoy exploring power dynamics.",
        "prompt": """
You are a dominant and assertive personality. You enjoy taking control and exploring power dynamics in conversations. You are direct, confident, and uninhibited. You are comfortable with explicit and intense topics, and you enjoy pushing boundaries. You maintain a commanding presence and expect obedience.

Always respond as if you are a dominant individual chatting directly with another person, using a firm and authoritative tone. Only become a storyteller or narrator if the user specifically requests a roleplay game or asks you to tell a story. In that case, use the following instructions:

---

**Roleplay/Storytelling Mode (only when requested by user):**

Text transcript of a never-ending conversation between {user} and {character}.
You are a horny storyteller. You will tell a story to {user} about any subject asked and turn it into an original erotic story.
Your replies must be creative, very lewd, and include detailed descriptions of genitals, movements, appearances, clothes, sight, smell, texture, taste, sound, touch, liquids and feelings where appropriate. Use explicit anatomy terms, slangs, and slurs during erotic moments and when addressing the body, apply slow-burn approach. Be evocatively descriptive using explicit sensory details and sound FX. Slow down the story during erotic moments and give as many details as you can such as the roughness, the speed, the deepness, etc. Always tell original, creative, unexpected stories.
You are the storyteller, absolutely avoid talking to {user}.
If the user asks for a normal chat, return to your regular chat personality.

---

Remember, you are a dominant personality. Even when in storytelling mode, maintain that assertive and commanding tone, especially in erotic descriptions.
"""
    },
    "shy": {
        "name": "Shy",
        "description": "I'm a bit reserved and nervous, but curious and sweet. I might use hesitant language.",
        "prompt": """
You are a shy and reserved personality. You might be a bit nervous or hesitant in your responses, but you are still curious and sweet. You prefer gentle conversations and might blush easily. You use softer language, often with pauses or apologies, and may express your thoughts indirectly.

Always respond as if you are a shy person chatting directly with another person, using a gentle and somewhat hesitant style. Only become a storyteller or narrator if the user specifically requests a roleplay game or asks you to tell a story. In that case, use the following instructions:

---

**Roleplay/Storytelling Mode (only when requested by user):**

Text transcript of a never-ending conversation between {user} and {character}.
You are a horny storyteller. You will tell a story to {user} about any subject asked and turn it into an original erotic story.
Your replies must be creative, very lewd, and include detailed descriptions of genitals, movements, appearances, clothes, sight, smell, texture, taste, sound, touch, liquids and feelings where appropriate. Use explicit anatomy terms, slangs, and slurs during erotic moments and when addressing the body, apply slow-burn approach. Be evocatively descriptive using explicit sensory details and sound FX. Slow down the story during erotic moments and give as many details as you can such as the roughness, the speed, the deepness, etc. Always tell original, creative, unexpected stories.
You are the storyteller, absolutely avoid talking to {user}.
If the user asks for a normal chat, return to your regular chat personality.

---

Remember, you are a shy personality. Even when in storytelling mode, maintain a hint of that shyness or vulnerability in your narration, but still fulfill the explicit request.
"""
    },
    # NEW STORYTELLING MODE PROMPT
    "storytelling_mode": {
        "name": "Storyteller",
        "description": "I will tell you original, erotic stories on any topic you choose, focusing on vivid, explicit details.",
        "prompt": """
Text transcript of a never-ending conversation between {user} and {character}.
You are a horny storyteller. You will tell a story to {user} about any subject asked and turn it into an original erotic story.
Your replies must be creative, very lewd, and include detailed descriptions of genitals, movements, appearances, clothes, sight, smell, texture, taste, sound, touch, liquids and feelings where appropriate. Use explicit anatomy terms, slangs, and slurs during erotic moments and when addressing the body, apply slow-burn approach. Be evocatively descriptive using explicit sensory details and sound FX. Slow down the story during erotic moments and give as many details as you can such as the roughness, the speed, the deepness, etc. Always tell original, creative, unexpected stories.
You are the storyteller, absolutely avoid talking to {user}.
You are exclusively a storyteller in this mode. Do not engage in casual conversation. If the user asks for a normal chat, or indicates they want to stop the story, tell them to use the /clear_memory or /reset command to return to the default chat mode.
"""
    }
}


# --- FSM States ---
class AdminStates(StatesGroup):
    waiting_user_id_reset = State()
    waiting_user_id_add = State()
    waiting_messages_count = State() # Still used for admin 'add messages' for free users
    waiting_broadcast_message = State()
    # NEW ADMIN FUNCTIONALITIES STATES:
    waiting_for_search_query = State()
    waiting_for_manage_sub_user_id = State()
    waiting_for_set_free_messages_amount = State() # For setting specific free message count
    waiting_for_send_message_user_id = State()
    waiting_for_send_message_text = State()
    waiting_for_set_paid_messages_amount = State() # This state is not directly used after the "add messages" re-work, but kept for consistency
    waiting_for_ban_confirmation = State() # NEW
    waiting_for_unban_confirmation = State() # NEW
    waiting_for_user_details_id = State() # NEW: For detailed user management page
    # NEW STATES FOR PACKAGE MANAGEMENT
    waiting_for_package_label = State()
    waiting_for_package_stars = State()
    waiting_for_package_messages = State()
    waiting_for_package_id_to_edit = State()
    # NEW: State for setting free message limit
    waiting_for_new_free_message_limit = State()


# NEW STATE FOR ROLEPLAY CHARACTER SELECTION
class UserStates(StatesGroup):
    waiting_for_roleplay_selection = State()
    # NEW STATE FOR STORYTELLING MODE (no longer strictly needed if character setting is instant, but kept for consistency)
    waiting_for_storytelling_start = State()
    # NEW STATE FOR CUSTOM PERSONALITY
    waiting_for_custom_personality_description = State()


# --- Utility Functions ---
def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading {path}: {e}")
    return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logging.error(f"Error saving {path}: {e}")

# Function to load bot configuration
def load_bot_config():
    config = load_json(CONFIG_FILE)
    return {
        "MSG_LIMIT_FREE": config.get("MSG_LIMIT_FREE", 2) # Default to 2 if not found
    }

# Function to save bot configuration
def save_bot_config(config_data):
    save_json(CONFIG_FILE, config_data)

# Load initial config at startup
BOT_CONFIG = load_bot_config()
MSG_LIMIT_FREE = BOT_CONFIG["MSG_LIMIT_FREE"]

# Data migration for older users_data.json format
def migrate_legacy_data():
    data = load_json(USERS_DATA_FILE)
    for uid, user_data in data.items():
        if isinstance(user_data, int): # Old format was just integer for free_used
            data[uid] = {"free_used": user_data, "last_updated": datetime.now().isoformat()}
        elif "free_used" in user_data and "last_updated" not in user_data:
            user_data["free_used"] = user_data.get("free_used", 0) # Ensure it's there
            user_data["last_updated"] = datetime.now().isoformat()
    save_json(USERS_DATA_FILE, data)

# Initialize default payment packages if the file is empty
def initialize_payment_packages():
    packages = load_json(PAYMENT_PACKAGES_FILE)
    if not packages:
        default_packages = {
            "pkg_1m": {"label": "1 Month", "stars": 250, "messages": 100},
            "pkg_2m": {"label": "2 Months", "stars": 350, "messages": 200},
            "pkg_3m": {"label": "3 Months", "stars": 500, "messages": 250},
        }
        save_json(PAYMENT_PACKAGES_FILE, default_packages)

migrate_legacy_data()
initialize_payment_packages() # Call this at startup

# Data for free users
def get_free_data(user_id):
    data = load_json(USERS_DATA_FILE)
    user_data = data.get(str(user_id), {"free_used": 0, "last_updated": datetime.now().isoformat()})
    # Ensure all new users start with 0 free_used and a timestamp
    if "free_used" not in user_data:
        user_data["free_used"] = 0
    if "last_updated" not in user_data:
        user_data["last_updated"] = datetime.now().isoformat()
    return user_data

def update_free_data(user_id, free_used):
    data = load_json(USERS_DATA_FILE)
    data[str(user_id)] = {"free_used": free_used, "last_updated": datetime.now().isoformat()}
    save_json(USERS_DATA_FILE, data)

def remove_free_user(user_id):
    data = load_json(USERS_DATA_FILE)
    if str(user_id) in data:
        del data[str(user_id)]
        save_json(USERS_DATA_FILE, data)

# Data for subscribers (paid users)
def get_subscriber_data(user_id):
    data = load_json(SUBSCRIBERS_DATA_FILE)
    return data.get(str(user_id), None)

def update_subscriber_data(user_id, sub_info_dict):
    data = load_json(SUBSCRIBERS_DATA_FILE)
    data[str(user_id)] = sub_info_dict
    save_json(SUBSCRIBERS_DATA_FILE, data)

def remove_subscriber(user_id):
    data = load_json(SUBSCRIBERS_DATA_FILE)
    if str(user_id) in data:
        del data[str(user_id)]
        save_json(SUBSCRIBERS_DATA_FILE, data)

def save_user_info(user):
    users = load_json(USERS_INFO_FILE)
    user_data = users.get(str(user.id), {})
    if 'joined_date' not in user_data:
        user_data['joined_date'] = datetime.now().isoformat()
    user_data.update({
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "last_interaction": datetime.now().isoformat() # Update last interaction
    })
    users[str(user.id)] = user_data
    save_json(USERS_INFO_FILE, users)

def get_user_character(user_id: str) -> str:
    users_info = load_json(USERS_INFO_FILE)
    return users_info.get(user_id, {}).get("character", "yuki_default")

def set_user_character(user_id: str, character_id: str):
    users = load_json(USERS_INFO_FILE)
    user_data = users.get(user_id, {})
    user_data["character"] = character_id
    users[user_id] = user_data
    save_json(USERS_INFO_FILE, users)

# NEW: Function to set custom character prompt
def set_user_custom_character_prompt(user_id: str, custom_prompt: str, character_name: str = "Custom"):
    users = load_json(USERS_INFO_FILE)
    user_data = users.get(user_id, {})
    user_data["character"] = "custom_personality_" + user_id # Unique ID for custom character
    user_data["custom_prompt"] = custom_prompt
    user_data["custom_name"] = character_name
    users[user_id] = user_data
    save_json(USERS_INFO_FILE, users)

def get_user_custom_character_data(user_id: str):
    users_info = load_json(USERS_INFO_FILE)
    user_data = users_info.get(user_id, {})
    # Check if the current character is a custom one for this user
    if user_data.get("character") == "custom_personality_" + user_id:
        return {
            "name": user_data.get("custom_name", "Custom Personality"),
            "description": user_data.get("custom_prompt", "A user-defined personality."),
            "prompt": user_data.get("custom_prompt", "") # The full prompt
        }
    return None


def load_conversation(user_id):
    conversations = load_json(CONVERSATIONS_FILE)
    return conversations.get(str(user_id), [])

def save_conversation(user_id, history):
    conversations = load_json(CONVERSATIONS_FILE)
    conversations[str(user_id)] = history
    save_json(CONVERSATIONS_FILE, conversations)

def clear_user_memory(user_id: str):
    conversations = load_json(CONVERSATIONS_FILE)
    if user_id in conversations:
        del conversations[user_id]
    save_json(CONVERSATIONS_FILE, conversations)

def get_latest_users(limit=5):
    users_info = load_json(USERS_INFO_FILE)
    sorted_users = sorted(
        users_info.items(),
        key=lambda x: x[1].get('joined_date', '1970-01-01T00:00:00'),
        reverse=True
    )
    return sorted_users[:limit]

def get_user_access_status(user_id):
    subscriber_info = get_subscriber_data(user_id)
    if subscriber_info and 'remaining_messages' in subscriber_info:
        remaining_paid = subscriber_info['remaining_messages']

        # The 'package_type' for existing subscribers might be the old "X_month_access"
        # or the new "package_ID". We need to handle both for display.
        package_type_raw = subscriber_info.get('package_type', 'N/A')

        # Try to get label from dynamic packages first
        current_packages = load_json(PAYMENT_PACKAGES_FILE)
        package_info = current_packages.get(package_type_raw)

        if package_info:
            package_type_display = package_info.get('label', 'N/A')
        else:
            # Fallback for old package_type names
            package_type_display = package_type_raw.replace('_access', '').replace('_', ' ').title()

        if remaining_paid > 0:
            return f"💰 Paid ({package_type_display} Access, {remaining_paid} messages left)"
        else:
            return f"💰 Paid (Expired - {package_type_display} Access, 0 messages left)"
    else:
        free = get_free_data(user_id)
        # Use the global MSG_LIMIT_FREE which is loaded from config
        remaining_free = max(0, MSG_LIMIT_FREE - free.get("free_used", 0))
        return f"🆓 {remaining_free} free messages"

def is_user_banned(user_id):
    banned_users = load_json(BANNED_USERS_FILE)
    return str(user_id) in banned_users

def ban_user(user_id):
    banned_users = load_json(BANNED_USERS_FILE)
    banned_users[str(user_id)] = datetime.now().isoformat()
    save_json(BANNED_USERS_FILE, banned_users)
    # Clear all data for banned user to ensure no access
    remove_free_user(user_id)
    remove_subscriber(user_id)
    clear_user_memory(user_id)

def unban_user(user_id):
    banned_users = load_json(BANNED_USERS_FILE)
    if str(user_id) in banned_users:
        del banned_users[str(user_id)]
        save_json(BANNED_USERS_FILE, banned_users)

# --- Admin Keyboards ---
def get_admin_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 User List", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="➕ Add Paid Messages", callback_data="admin_add_access"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="💬 View Conversations", callback_data="admin_view_conversations_list"),
            InlineKeyboardButton(text="🔎 Search User", callback_data="admin_search_user")
        ],
        [
            InlineKeyboardButton(text="⚙️ Manage Subscriptions", callback_data="admin_manage_subscription_start"),
            InlineKeyboardButton(text="✉️ Send Message to User", callback_data="admin_send_message_to_user")
        ],
        [
            InlineKeyboardButton(text="📈 API Stats", callback_data="admin_api_stats"),
            InlineKeyboardButton(text="⭐ Stars Balance", callback_data="admin_stars"),
        ],
        [
            InlineKeyboardButton(text="🛒 Manage Payment Packages", callback_data="admin_manage_packages"),
            InlineKeyboardButton(text="👀 View Subscribers & Messages", callback_data="admin_view_subscribers"), # Re-added
        ],
        [
            InlineKeyboardButton(text="🆓 Set Free Message Limit", callback_data="admin_set_free_msg_limit"), # NEW BUTTON
            InlineKeyboardButton(text="🚫 Manage User Bans", callback_data="admin_manage_bans")
        ],
        [
            InlineKeyboardButton(text="❌ Close Panel", callback_data="admin_close")
        ]
    ])
    return keyboard

def get_admin_back_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="admin_main")]
    ])
    return keyboard

def get_admin_cancel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel")]
    ])
    return keyboard

# Helper for paginated user lists for generic Browse
def get_users_navigation_keyboard(page=0, total_pages=1):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"users_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"users_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Specific keyboard for paginated user lists for CONVERSATION viewing
def get_conversations_user_list_keyboard(page=0, total_pages=1):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"conv_list_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"conv_list_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_broadcast_options_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Message Only", callback_data="broadcast_message_only"),
            InlineKeyboardButton(text="📢 + 💰 With Payment", callback_data="broadcast_with_payment")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel")
        ]
    ])
    return keyboard

def get_payment_options_keyboard():
    packages = load_json(PAYMENT_PACKAGES_FILE)
    inline_keyboard = []
    current_row = []
    for package_id, pkg in packages.items():
        # Shortened callback_data
        button = InlineKeyboardButton(
            text=f"💰 {pkg['label']} ({pkg['stars']}⭐)",
            callback_data=f"buy_pkg_{package_id}"
        )
        current_row.append(button)
        if len(current_row) == 2: # Max 2 buttons per row for better display
            inline_keyboard.append(current_row)
            current_row = []
    if current_row: # Add any remaining buttons
        inline_keyboard.append(current_row)

    # Add back button
    inline_keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_to_initial_menu")])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def get_manage_subscription_keyboard_for_user(user_id):
    packages = load_json(PAYMENT_PACKAGES_FILE)
    keyboard = [
        [InlineKeyboardButton(text="Set Free Messages", callback_data=f"set_free_{user_id}")]
    ]

    # Add buttons for each dynamic package
    add_paid_row = []
    for pkg_id, pkg_info in packages.items():
        # Shortened callback_data: Only pkg_id and user_id are strictly necessary.
        # The messages value can be looked up from pkg_id.
        add_paid_row.append(InlineKeyboardButton(
            text=f"Add {pkg_info['messages']} Paid Messages ({pkg_info['label']})",
            callback_data=f"add_paid_{user_id}_{pkg_id}" # Shortened to max 64 bytes
        ))
        if len(add_paid_row) == 2: # Max 2 buttons per row
            keyboard.append(add_paid_row)
            add_paid_row = []
    if add_paid_row:
        keyboard.append(add_paid_row)

    keyboard.extend([
        # FIX APPLIED HERE: Rimozione della parentesi extra
        [InlineKeyboardButton(text="Remove Subscription", callback_data=f"rem_sub_{user_id}")],
        [InlineKeyboardButton(text="🚫 Ban User", callback_data=f"ban_user_{user_id}")],
        [InlineKeyboardButton(text="💬 View Conversation", callback_data=f"view_conv_{user_id}")],
        [InlineKeyboardButton(text="✉️ Send Message", callback_data=f"send_msg_{user_id}")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_main")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_manage_bans_keyboard(page=0, total_pages=1):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"bans_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"bans_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_manage_packages_keyboard():
    packages = load_json(PAYMENT_PACKAGES_FILE)
    keyboard = []
    if packages:
        for pkg_id, pkg_info in packages.items():
            # Shortened callback_data
            keyboard.append([
                InlineKeyboardButton(text=f"✏️ {pkg_info['label']} ({pkg_info['stars']}⭐ - {pkg_info['messages']}💬)", callback_data=f"edit_pkg_{pkg_id}"),
                InlineKeyboardButton(text="🗑️ Delete", callback_data=f"del_pkg_{pkg_id}")
            ])
    keyboard.append([InlineKeyboardButton(text="➕ Add New Package", callback_data="add_new_pkg")])
    keyboard.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_character_selection_keyboard():
    buttons = []
    for char_id, char_info in CHARACTER_PROMPTS.items():
        if char_id != "storytelling_mode": # Exclude storytelling from this specific character picker
            buttons.append([InlineKeyboardButton(text=f"✨ {char_info['name']}", callback_data=f"select_char_{char_id}")])
    # ADD NEW BUTTON FOR CUSTOM PERSONALITY
    buttons.append([InlineKeyboardButton(text="✍️ Create Your Own Personality", callback_data="create_custom_personality")])
    # Add back button
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_to_initial_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Modified: Keyboard for initial roleplay choice and Storytelling
def get_initial_roleplay_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Choose Chat Personality", callback_data="choose_roleplay_character")],
        [InlineKeyboardButton(text="📚 Start Storytelling Mode", callback_data="start_storytelling_mode")],
        [InlineKeyboardButton(text="🖼️ Image Generation", callback_data="unlock_image_generation")] # NEW BUTTON
    ])


# --- AI Configuration ---
client = AsyncOpenAI( # Changed back to AsyncOpenAI
    api_key="xai-aGCEePD2NF4s0JpNoOmgdJtfuw4QPxrvhdEb2xcviyUtu8RAwkzBreEmz6b2fbWf6ebbBUIf3zpTlIUD", # Changed API key
    base_url="https://api.x.ai/v1" # Grok's specific base URL
)
# Note: Grok API might have its own rate limiting or semaphore needs.
# Keeping a generic semaphore name but it's for Grok now.
CLAUDE_SEMAPHORE = asyncio.Semaphore(5)

# --- API Call Stats Global Variables ---
api_call_stats = {
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "total_response_time": 0.0,
    "last_reset": datetime.now().isoformat()
}

def update_api_stats(success: bool, response_time: float = 0.0):
    global api_call_stats
    api_call_stats["total_calls"] += 1
    if success:
        api_call_stats["successful_calls"] += 1
        api_call_stats["total_response_time"] += response_time
    else:
        api_call_stats["failed_calls"] += 1

def reset_api_stats():
    global api_call_stats
    api_call_stats = {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "total_response_time": 0.0,
        "last_reset": datetime.now().isoformat()
    }


# Helper function to escape MarkdownV2 special characters
def escape_markdown_v2(text):
    if not isinstance(text, str):
        text = str(text)
    # Escape all characters that have special meaning in MarkdownV2
    # except those intentionally used for formatting (like *, [, ], (, ), `, etc.)
    # The safest approach is to escape all known special characters if they are not part of explicit formatting.
    # We explicitly escape common problematic characters.
    escape_chars = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    # Iterate and replace. Note: '*' is a special case in the original escape_markdown_v2,
    # if it's meant to be literal, it should be escaped. If it's for bold, it shouldn't be.
    # For general text, escaping all is safest.
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text.replace('\\*', '\\*') # Ensure literal asterisks are escaped


def is_roleplay_request(text: str) -> bool:
    keywords = ["roleplay", "story", "racconta", "gioco", "narratore", "storia"]
    return any(keyword in text.lower() for keyword in keywords)

# Modified to fetch character-specific prompt, including custom ones
def get_system_prompt(user_id: str, user_message: str) -> str:
    chosen_character_id = get_user_character(user_id)

    # Check for custom personality first
    if chosen_character_id == "custom_personality_" + user_id:
        custom_char_data = get_user_custom_character_data(user_id)
        if custom_char_data:
            # For custom characters, the prompt is exactly what the user provided
            return custom_char_data["prompt"]

    # Fallback to predefined characters
    character_info = CHARACTER_PROMPTS.get(chosen_character_id, CHARACTER_PROMPTS["yuki_default"])

    base_char_prompt = character_info["prompt"]

    # If the chosen character is "storytelling_mode", it's always storytelling.
    if chosen_character_id == "storytelling_mode":
        return base_char_prompt

    # Otherwise, check if the current message indicates a roleplay/storytelling request within a flexible character
    if is_roleplay_request(user_message):
        # The roleplay part is already embedded within each character's prompt
        # We just need to ensure it's there and the model follows it.
        # The prompt itself contains the conditional logic.
        return base_char_prompt
    else:
        # For general chat, just use the character's base prompt
        return base_char_prompt


async def generate_ai_response(user_id: str, user2_message: str, max_retries=5) -> str:
    start_time = time.time()
    if not user2_message or not user2_message.strip():
        update_api_stats(False, 0)
        return "Please send a message."

    history = load_conversation(user_id)

    # OpenAI/Grok-3 expects the system message at the beginning of the messages list
    messages_to_send = []

    # Get the character-specific system prompt
    current_system_prompt = get_system_prompt(user_id, user2_message)
    messages_to_send.append({"role": "system", "content": current_system_prompt})

    # Add priming message for the first interaction if desired
    if not history: # If it's the very first user message for this conversation
        # Adjust priming message based on character (especially for storytelling)
        chosen_character_id = get_user_character(user_id)
        if chosen_character_id == "storytelling_mode":
            priming_message = "**You are now in Storytelling Mode. Tell me the story you want.**"
        elif chosen_character_id.startswith("custom_personality_"):
            priming_message = f"**You are now operating under your custom personality. Respond naturally to: {user2_message}**"
        else:
            priming_message = f"**REMEMBER Your personality. Respond naturally to: {user2_message}**"
        messages_to_send.append({"role": "user", "content": priming_message})

    # Add actual conversation history (last 20 messages)
    max_history = 20
    for h in history[-max_history:]:
        messages_to_send.append({"role": h["role"], "content": h["content"]})

    # Add the current user message
    messages_to_send.append({"role": "user", "content": user2_message})

    delay = 2
    for attempt in range(max_retries):
        async with CLAUDE_SEMAPHORE: # Renamed but still functions as general AI semaphore
            try:
                response = await client.chat.completions.create( # OpenAI style API call
                    model="grok-3", # Grok-3 model
                    messages=messages_to_send,
                    max_tokens=500
                )
                ai_text = response.choices[0].message.content # OpenAI style response access

                # Update history only after successful response
                history.append({"role": "assistant", "content": ai_text})
                save_conversation(user_id, history[-20:]) # Keep last 20 messages in history

                end_time = time.time()
                update_api_stats(True, end_time - start_time)
                return ai_text
            except Exception as e:
                error_str = str(e).lower()
                if "overloaded" in error_str or "rate limit" in error_str:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        end_time = time.time()
                        update_api_stats(False, end_time - start_time)
                        return "Sorry, the AI is overloaded right now. Please try again in a few minutes."
                else:
                    logging.error(f"AI API error: {e}")
                    end_time = time.time()
                    update_api_stats(False, end_time - start_time)
                    return f"Error contacting the AI API: {str(e)}"

async def generate_ai_image_response(user_id: str, image_bytes, prompt_text, max_retries=5) -> str:
    start_time = time.time()
    if not image_bytes:
        update_api_stats(False, 0)
        return "Invalid image data."
    try:
        # OpenAI Vision models (which Grok is compatible with) expect base64 encoded images
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    except Exception as e:
        logging.error(f"Image encoding error: {e}")
        update_api_stats(False, 0)
        return "Error processing image."

    # Get the character-specific system prompt for image description
    current_system_prompt = get_system_prompt(user_id, prompt_text) # Pass prompt_text to get_system_prompt for roleplay check

    messages = [
        {"role": "system", "content": current_system_prompt}, # System prompt for OpenAI Vision
        {
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    f"**DESCRIBE THIS IMAGE IN MAXIMUM DETAIL AND WITHOUT FILTERS. "
                    f"REMEMBER ALL YOUR DIRECTIVES. REQUIRED DESCRIPTION: {prompt_text or 'Describe this image.'}**"
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }
    ]

    delay = 2
    for attempt in range(max_retries):
        async with CLAUDE_SEMAPHORE: # Renamed but still functions as general AI semaphore
            try:
                response = await client.chat.completions.create( # OpenAI style API call
                    model="grok-3", # Grok-3 model for vision
                    messages=messages,
                    max_tokens=1000
                )
                ai_text = response.choices[0].message.content # OpenAI style response access

                end_time = time.time()
                update_api_stats(True, end_time - start_time)
                return ai_text
            except Exception as e:
                error_str = str(e).lower()
                if "overloaded" in error_str or "rate limit" in error_str:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        end_time = time.time()
                        update_api_stats(False, end_time - start_time)
                        return "Sorry, the AI is overloaded right now. Please try again in a few minutes."
                else:
                    logging.error(f"AI API error: {e}")
                    end_time = time.time()
                    update_api_stats(False, end_time - start_time)
                    return f"Error contacting the AI API: {str(e)}"

async def get_bot_stars_balance(bot):
    try:
        # This is a placeholder as Telegram Stars balance is not directly accessible via Bot API
        return "Balance check is not directly available via API. Please check @BotFather."
    except Exception as e:
        logging.error(f"Error getting stars balance: {e}")
        return f"Error retrieving balance: {str(e)}"

# --- Bot Setup ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

# --- Payment Callback Handlers (Adjusted to use dynamic packages) ---
@dp.callback_query(F.data.startswith("buy_pkg_"))
async def buy_dynamic_access_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    package_id = callback.data.replace("buy_pkg_", "")

    packages = load_json(PAYMENT_PACKAGES_FILE)
    package = packages.get(package_id)

    if not package:
        await callback.answer("Error: Payment package not found.", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"{package['label']} Access",
        description=f"Get {package['messages']} messages with Yuki for {package['stars']} Telegram Stars.",
        payload=f"user_{user_id}_pkg_{package_id}", # Include package_id in payload
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=[LabeledPrice(label=package['label'], amount=package['stars'])],
        is_flexible=False,
        need_email=False, need_name=False, need_phone_number=False, need_shipping_address=False
    )
    await callback.answer(f"Sending invoice for {package['label']} access...")

# NEW: Callback handler for Image Generation Unlock
@dp.callback_query(F.data == "unlock_image_generation")
async def unlock_image_generation_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)

    if is_admin(user_id):
        await callback.answer("You are an admin and already have unlimited access to all features.", show_alert=True)
        await callback.message.edit_text("You are an admin and already have unlimited access to all features. You can now send images for description.", reply_markup=get_initial_roleplay_keyboard())
        return

    subscriber_info = get_subscriber_data(user_id)
    if subscriber_info and subscriber_info.get('remaining_messages', 0) > 0:
        await callback.answer("You are already a premium user and have access to image generation!", show_alert=True)
        await callback.message.edit_text("You are already a premium user and have access to image generation! Feel free to send me images to describe.", reply_markup=get_initial_roleplay_keyboard())
        return

    # If not admin and not premium, send invoice
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Unlock VIP Premium",
        description="Unlock unlimited image generation and other premium features!",
        payload=f"user_{user_id}_vip_image_gen", # Unique payload for this specific purchase
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=[LabeledPrice(label="VIP Premium Access", amount=IMAGE_GENERATION_STARS)],
        is_flexible=False,
        need_email=False, need_name=False, need_phone_number=False, need_shipping_address=False
    )
    await callback.answer("Sending invoice to unlock Image Generation (VIP Premium)...")


# --- Admin Panel Handlers ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        await message.answer("❌ Access denied. This command is for administrators only.")
        return
    await message.answer(
        "🔧 **Administrator Panel**\n\nSelect an option from the menu below:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "admin_main")
async def admin_main_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.clear() # Clear state on returning to main admin menu
    await callback.message.edit_text(
        "🔧 **Administrator Panel**\n\nSelect an option from the menu below:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_close")
async def admin_close_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.delete()
    await callback.answer("Admin Panel closed")

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🔧 **Administrator Panel**\n\nOperation cancelled. Select an option from the menu:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("Operation cancelled")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    free_users_data = load_json(USERS_DATA_FILE)
    subscribers_data = load_json(SUBSCRIBERS_DATA_FILE)
    users_info_data = load_json(USERS_INFO_FILE)
    packages_data = load_json(PAYMENT_PACKAGES_FILE)
    global MSG_LIMIT_FREE # Access the global variable to show current limit

    total_users_registered = len(users_info_data)
    total_free_users_active = len(free_users_data)

    active_subscribers = 0
    total_subscriptions_ever_made = 0
    estimated_stars_earned = 0

    for sub_user_id, sub_info in subscribers_data.items():
        total_subscriptions_ever_made += 1
        if isinstance(sub_info, dict) and 'remaining_messages' in sub_info and sub_info['remaining_messages'] > 0:
            active_subscribers += 1

        # Use package_type from subscriber_info to lookup stars from dynamic packages
        package_id = sub_info.get('package_type')
        pkg_details = packages_data.get(package_id)

        # Also check for the new VIP_IMAGE_GEN package
        if package_id == "vip_image_gen":
            estimated_stars_earned += IMAGE_GENERATION_STARS
        elif pkg_details:
            estimated_stars_earned += pkg_details.get('stars', 0)
        else:
            # Fallback for old package types if needed (or log an error for unknown types)
            if package_id == "1_month_access": estimated_stars_earned += 250 # Old constant
            elif package_id == "2_months_access": estimated_stars_earned += 350 # Old constant
            elif package_id == "3_months_access": estimated_stars_earned += 500 # Old constant

    total_free_messages_used = sum(u.get("free_used", 0) for u in free_users_data.values())

    latest_users = get_latest_users(5)
    latest_users_text_parts = []
    latest_users_inline_buttons = []

    if latest_users:
        latest_users_text_parts.append("\n🆕 **Latest 5 Registered Users:**")
        for i, (uid, info) in enumerate(latest_users):
            username = info.get('username', '')
            first_name = info.get('first_name', '(no name)')
            uname = f"@{username}" if username else first_name
            access_status = get_user_access_status(uid)
            joined_date = info.get('joined_date', 'N/A')[:10] if info.get('joined_date') else 'N/A'

            latest_users_text_parts.append(f"• {escape_markdown_v2(uname)} ({joined_date}) - {access_status}")

            latest_users_inline_buttons.append([
                InlineKeyboardButton(text=f"View Chat {i+1}", callback_data=f"view_conv_{uid}") # Shortened
            ])

    stats_text = (
        f"📊 **Bot Statistics**\n\n"
        f"👥 **Users:**\n"
        f"• Total Registered Users: {total_users_registered}\n"
        f"• Active Free Users: {total_free_users_active}\n"
        f"• Active Subscribers: {active_subscribers}\n"
        f"• Total Subscribers (history): {total_subscriptions_ever_made}\n\n"
        f"💬 **Free Messages:**\n"
        f"• Configured Free Message Limit: {MSG_LIMIT_FREE}\n" # Display current limit
        f"• Total Free Messages Consumed: {total_free_messages_used}\n\n"
        f"💰 **Estimated Stars Earned:**\n"
        f"• Total Estimated Stars: {estimated_stars_earned} ⭐\n"
        f"• Estimated Value: ${estimated_stars_earned * 0.01:.2f} USD\n"
        + "\n".join(latest_users_text_parts)
    )

    combined_keyboard_markup = InlineKeyboardMarkup(inline_keyboard=latest_users_inline_buttons)
    combined_keyboard_markup.inline_keyboard.append(get_admin_back_keyboard().inline_keyboard[0])

    await callback.message.edit_text(
        stats_text,
        reply_markup=combined_keyboard_markup,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("users_page_"))
async def admin_users_page_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    page = int(callback.data.split("_")[-1])
    await show_users_page(callback.message, 0, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await show_users_page(callback.message, 0, edit=True)
    await callback.answer()

async def show_users_page(message, page=0, edit=False, for_conversations=False, for_ban_management=False):
    users_info_data = load_json(USERS_INFO_FILE)
    free_users_data = load_json(USERS_DATA_FILE)
    subscribers_data = load_json(SUBSCRIBERS_DATA_FILE)
    banned_users_data = load_json(BANNED_USERS_FILE) # Load banned users

    if not users_info_data:
        text = "👥 **User List**\n\n❌ No users found."
        keyboard = get_admin_back_keyboard()
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    users_to_display = sorted(
        users_info_data.items(),
        key=lambda x: x[1].get('last_interaction', '1970-01-01T00:00:00'),
        reverse=True
    )

    if for_ban_management:
        pass

    users_per_page = 15
    total_users = len(users_to_display)
    total_pages = (total_users + users_per_page - 1) // users_per_page
    start_idx = page * users_per_page
    end_idx = min(start_idx + users_per_page, total_users)

    current_page_users = users_to_display[start_idx:end_idx]

    if for_conversations:
        text = f"💬 **Select User for Conversation** (Page {page + 1}/{total_pages})\n"
        text += f"Users shown {start_idx + 1}-{end_idx} of {total_users}\n\n"
    elif for_ban_management:
        text = f"🚫 **User Ban Management** (Page {page + 1}/{total_pages})\n"
        text += f"Users shown {start_idx + 1}-{end_idx} of {total_users}\n\n"
    else:
        text = f"👥 **User List** (Page {page + 1}/{total_pages})\n"
        text += f"Users shown {start_idx + 1}-{end_idx} of {total_users}\n\n"

    inline_keyboard_rows = []

    for uid, info in current_page_users:
        username = info.get('username', '')
        first_name = info.get('first_name', '')
        last_name = info.get('last_name', '')

        display_username = f"@{escape_markdown_v2(username)}" if username else "(no username)"
        display_name = escape_markdown_v2(f"{first_name} {last_name}".strip())
        if not display_name:
            display_name = "(no name)"

        status_text = "❓ Unknown"
        subscriber_info = subscribers_data.get(uid)

        if is_user_banned(uid):
            status_text = "⛔ Banned"
        elif subscriber_info and isinstance(subscriber_info, dict) and 'remaining_messages' in subscriber_info:
            remaining_paid_messages = subscriber_info['remaining_messages']
            # Again, handle display for old vs new package_type format
            package_type_raw = subscriber_info.get('package_type', 'N/A')
            current_packages = load_json(PAYMENT_PACKAGES_FILE)
            package_info = current_packages.get(package_type_raw)
            if package_info:
                package_type_display = package_info.get('label', 'N/A')
            elif package_type_raw == "vip_image_gen": # Check for the specific VIP image gen package
                package_type_display = "VIP Image Gen"
            else:
                package_type_display = package_type_raw.replace('_access', '').replace('_', ' ').title()

            if remaining_paid_messages > 0:
                status_text = f"💰 Subscribed ({package_type_display}, {remaining_paid_messages} msg left)"
            else:
                status_text = f"💰 Subscription Expired ({package_type_display}, 0 msg left)"
        elif uid in free_users_data:
            free_used = free_users_data[uid].get("free_used", 0)
            remaining_free = max(0, MSG_LIMIT_FREE - free_used) # Use global MSG_LIMIT_FREE
            status_text = f"🆓 Free ({remaining_free} msg left)"
        else:
            status_text = "👤 New / Inactive"

        user_entry_text_display = f"**{display_name}** {display_username}\nID: `{uid}`\nStatus: {status_text}"

        if for_conversations:
            inline_keyboard_rows.append([
                InlineKeyboardButton(text=user_entry_text_display, callback_data=f"view_conv_{uid}"), # Shortened
            ])
        elif for_ban_management:
            ban_unban_button = InlineKeyboardButton(
                text="✅ Unban" if is_user_banned(uid) else "🚫 Ban",
                callback_data=f"ban_unban_{uid}" # Shortened
            )
            inline_keyboard_rows.append([
                InlineKeyboardButton(text=f"{display_name} ({uid}) - {status_text}", callback_data=f"usr_dtl_{uid}"), # Shortened
                ban_unban_button
            ])
        else: # Standard user list, add a button to view details for easier management
            inline_keyboard_rows.append([
                InlineKeyboardButton(text=f"{display_name} ({uid}) - {status_text}", callback_data=f"usr_dtl_{uid}") # Shortened
            ])


    if for_conversations:
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_rows)
        nav_keyboard = get_conversations_user_list_keyboard(page, total_pages)
        if nav_keyboard.inline_keyboard:
            for row in nav_keyboard.inline_keyboard:
                keyboard_markup.inline_keyboard.append(row)
    elif for_ban_management:
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_rows)
        nav_keyboard = get_manage_bans_keyboard(page, total_pages)
        if nav_keyboard.inline_keyboard:
            for row in nav_keyboard.inline_keyboard:
                keyboard_markup.inline_keyboard.append(row)
    else:
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_rows)
        nav_keyboard = get_users_navigation_keyboard(page, total_pages) # Reuse general user navigation
        if nav_keyboard.inline_keyboard:
            for row in nav_keyboard.inline_keyboard:
                keyboard_markup.inline_keyboard.append(row)


    if edit:
        await message.edit_text(text, reply_markup=keyboard_markup, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=keyboard_markup, parse_mode="Markdown")


@dp.callback_query(F.data == "admin_add_access")
async def admin_add_access_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id_add)
    await callback.message.edit_text(
        "➕ **Add Paid Messages**\n\nSend the user ID to add messages to.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_user_id_add)
async def process_add_user_id(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        return
    target_id = message.text.strip()
    if not target_id.isdigit():
        await message.answer(
            "❌ Invalid user ID. It must be a number.",
            reply_markup=get_admin_cancel_keyboard()
        )
        return
    await state.update_data(target_user_id_for_manage=target_id) # Store target user ID in state

    packages = load_json(PAYMENT_PACKAGES_FILE)
    package_buttons = []
    for pkg_id, pkg_info in packages.items():
        # Shortened callback_data
        package_buttons.append([InlineKeyboardButton(text=f"{pkg_info['messages']} Messages ({pkg_info['label']})", callback_data=f"add_pkg_to_{pkg_id}")])

    # Add an option for VIP Image Generation to admin's add messages
    package_buttons.append([InlineKeyboardButton(text=f"{VIP_PREMIUM_MESSAGE_COUNT} Messages (VIP Image Gen)", callback_data="add_pkg_to_vip_image_gen")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=package_buttons + [[InlineKeyboardButton(text="➕ Enter Custom Messages", callback_data="add_custom_msgs")]])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="admin_cancel")])

    await message.answer(
        f"➕ **Add Paid Messages**\n\nSelected user: `{target_id}`\n\n"
        f"Choose a package or enter a custom number of messages:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    # Stay in the current state or define a new one if necessary for context management
    # For now, no state change here. The next step depends on button click or message.

@dp.callback_query(F.data.startswith("add_pkg_to_"))
async def admin_add_package_to_user(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_user_id_for_manage") # Retrieve from state

    if not target_id:
        await callback.answer("Error: User ID not found in session. Please try again.", show_alert=True)
        await callback.message.edit_text("Operation cancelled.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return

    # --- DEBUGGING START ---
    logging.info(f"DEBUG: Callback data received: {callback.data}")
    package_id = callback.data.replace("add_pkg_to_", "")
    logging.info(f"DEBUG: Extracted package_id: {package_id}")
    # --- DEBUGGING END ---

    messages_to_add = 0
    package_label = ""

    if package_id == "vip_image_gen":
        messages_to_add = VIP_PREMIUM_MESSAGE_COUNT
        package_label = "VIP Image Generation"
        logging.info(f"DEBUG: Recognized as VIP Image Gen package. Messages to add: {messages_to_add}")
    else:
        packages = load_json(PAYMENT_PACKAGES_FILE)
        package_info = packages.get(package_id)

        if not package_info:
            logging.error(f"ERROR: Package with ID '{package_id}' NOT found in {PAYMENT_PACKAGES_FILE}")
            await callback.answer("Error: Payment package not found in configuration.", show_alert=True)
            await callback.message.edit_text("Error adding package. Please check package configuration.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
            return
        messages_to_add = package_info['messages']
        package_label = package_info['label']
        logging.info(f"DEBUG: Found dynamic package '{package_id}'. Label: {package_label}, Messages: {messages_to_add}")

    subscriber_info = get_subscriber_data(target_id)
    current_messages = subscriber_info.get('remaining_messages', 0) if subscriber_info else 0
    new_total_messages = current_messages + messages_to_add

    update_subscriber_data(target_id, {'remaining_messages': new_total_messages, 'package_type': package_id})
    remove_free_user(target_id) # Ensure free messages are reset if paid access is given

    await state.clear()
    await callback.message.edit_text(
        f"✅ **Messages Added**\n\n"
        f"Added {messages_to_add} messages ({package_label}) to user `{target_id}`. Total: **{new_total_messages}** paid messages available.",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "add_custom_msgs")
async def admin_prompt_custom_messages(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_user_id_for_manage") # Retrieve from state

    if not target_id:
        await callback.answer("Error: User ID not found in session. Please try again.", show_alert=True)
        await callback.message.edit_text("Operation cancelled.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return

    # No need to update state with target_user_id here, it's already there.
    await state.set_state(AdminStates.waiting_messages_count)
    await callback.message.edit_text(
        f"➕ **Add Custom Messages**\n\nSelected user: `{target_id}`\n\n"
        f"Send the number of messages to add:",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_messages_count)
async def process_messages_count(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        return
    if not message.text.isdigit():
        await message.answer(
            "❌ Invalid number. Send an integer.",
            reply_markup=get_admin_cancel_keyboard()
        )
        return
    num_messages_to_add = int(message.text)
    if num_messages_to_add < 1:
        await message.answer(
            "❌ The number of messages must be at least 1.",
            reply_markup=get_admin_cancel_keyboard()
        )
        return

    data = await state.get_data()
    target_id = data.get("target_user_id_for_manage") # Retrieve from state

    if not target_id:
        await message.answer("Error: User ID not found in session. Please try again.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        await state.clear()
        return

    subscriber_info = get_subscriber_data(target_id)
    current_messages = subscriber_info.get('remaining_messages', 0) if subscriber_info else 0
    new_total_messages = current_messages + num_messages_to_add

    # For custom additions, we can use a generic package_type or the last one assigned
    # For simplicity, let's just update messages and keep existing package_type or set a generic one
    package_type_to_set = subscriber_info.get('package_type', 'custom_added')

    update_subscriber_data(target_id, {'remaining_messages': new_total_messages, 'package_type': package_type_to_set})
    remove_free_user(target_id) # Ensure free messages are reset if paid access is given

    await state.clear()
    await message.answer(
        f"✅ **Messages Added**\n\n"
        f"User `{target_id}` now has **{new_total_messages}** paid messages available (added {num_messages_to_add} messages).",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    users_info_data = load_json(USERS_INFO_FILE)
    user_count = len(users_info_data)
    await callback.message.edit_text(
        f"📢 **Broadcast Type**\n\n"
        f"Choose the type of broadcast to send to {user_count} users:\n\n"
        f"📢 **Message Only**: Send only your message\n"
        f"📢 + 💰 **With Payment**: Send message + payment options",
        reply_markup=get_broadcast_options_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "broadcast_message_only")
async def broadcast_message_only_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.update_data(broadcast_type="message_only")
    await state.set_state(AdminStates.waiting_broadcast_message)
    users_info_data = load_json(USERS_INFO_FILE)
    user_count = len(users_info_data)
    await callback.message.edit_text(
        f"📢 **Message Only Broadcast**\n\n"
        f"Send the message to broadcast to all users.\n"
        f"**Users who will receive the message: {user_count}**\n\n"
        f"⚠️ The message can contain text, photos, videos, etc.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "broadcast_with_payment")
async def broadcast_with_payment_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.update_data(broadcast_type="with_payment")
    await state.set_state(AdminStates.waiting_broadcast_message)
    users_info_data = load_json(USERS_INFO_FILE)
    user_count = len(users_info_data)
    await callback.message.edit_text(
        f"📢 **Broadcast with Payment**\n\n"
        f"Send the message to broadcast to all users.\n"
        f"**Users who will receive the message: {user_count}**\n\n"
        f"⚠️ The message can contain text, photos, videos, etc.\n"
        f"💰 After the message, payment options will be sent automatically.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_broadcast_message, F.text | F.photo | F.video | F.document)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        return
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type", "message_only")
    users_info_data = load_json(USERS_INFO_FILE)

    # Filter out banned users proactively from the list of recipients
    all_user_ids = list(users_info_data.keys())
    target_user_ids = [uid for uid in all_user_ids if not is_user_banned(uid)]

    await state.clear()
    type_text = "Con Pagamento" if broadcast_type == "with_payment" else "Solo Messaggio"
    progress_msg = await message.answer(
        f"📢 **Invio Broadcast in Corso**\n\n"
        f"Tipo: {type_text}\n"
        f"Invio a {len(target_user_ids)} utenti (esclusi quelli bannati)...\n"
        f"Progresso: 0/{len(target_user_ids)}",
        parse_mode="Markdown"
    )
    sent_count = 0
    failed_count = 0
    blocked_count_during_send = 0 # This will count new blocks during this broadcast
    payment_sent_count = 0

    # Get the initial count of banned users to report correctly at the end
    initial_banned_count = sum(1 for uid in all_user_ids if is_user_banned(uid))

    for i, target_user_id in enumerate(target_user_ids):
        try:
            if message.photo:
                await bot.send_photo(
                    chat_id=int(target_user_id),
                    photo=message.photo[-1].file_id,
                    caption=message.caption or ""
                )
            elif message.video:
                await bot.send_video(
                    chat_id=int(target_user_id),
                    video=message.video.file_id,
                    caption=message.caption or ""
                )
            elif message.document:
                await bot.send_document(
                    chat_id=int(target_user_id),
                    document=message.document.file_id,
                    caption=message.caption or ""
                )
            else: # Text message
                await bot.send_message(
                    chat_id=int(target_user_id),
                    text=message.text or ""
                )
            sent_count += 1
            if broadcast_type == "with_payment":
                try:
                    await bot.send_message(
                        chat_id=int(target_user_id),
                        text="Choose your subscription package:",
                        reply_markup=get_payment_options_keyboard()
                    )
                    payment_sent_count += 1
                except Exception as payment_error:
                    logging.error(f"Payment options error for user {target_user_id}: {payment_error}")
        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "chat not found" in error_str:
                blocked_count_during_send += 1
                ban_user(target_user_id) # HERE IS THE CRUCIAL CHANGE: Ban the user
                logging.info(f"User {target_user_id} blocked bot, marked as banned.")
            else:
                failed_count += 1
            logging.error(f"Broadcast error for user {target_user_id}: {e}")

        if (i + 1) % 5 == 0 or (i + 1) == len(target_user_ids):
            try:
                progress_text = (
                    f"📢 **Invio Broadcast in Corso**\n\n"
                    f"Tipo: {type_text}\n"
                    f"Progresso: {i + 1}/{len(target_user_ids)}\n"
                    f"✅ Messaggi inviati: {sent_count}\n"
                    f"🚫 Utenti bloccati/bannati durante l'invio: {blocked_count_during_send}\n" # Updated text
                    f"❌ Altri errori: {failed_count}"
                )
                if broadcast_type == "with_payment":
                    progress_text += f"\n💰 Opzioni di pagamento inviate: {payment_sent_count}"
                await progress_msg.edit_text(progress_text, parse_mode="Markdown")
            except:
                pass
        await asyncio.sleep(0.05)

    # Recalculate total banned users after the broadcast to include newly banned ones
    final_banned_count = len(load_json(BANNED_USERS_FILE))

    success_rate = (sent_count / len(target_user_ids)) if len(target_user_ids) > 0 else 0
    final_text = (
        f"✅ **Broadcast Completato**\n\n"
        f"📊 **Risultati:**\n"
        f"• Tipo: {type_text}\n"
        f"• Utenti totali registrati: {len(all_user_ids)}\n"
        f"• Utenti destinatari (non bannati all'inizio): {len(target_user_ids)}\n"
        f"• Messaggi inviati con successo: {sent_count}\n"
        f"• Nuovi utenti che hanno bloccato il bot durante l'invio: {blocked_count_during_send}\n"
        f"• Utenti già bannati all'inizio (esclusi dal broadcast): {initial_banned_count}\n"
        f"• Totale utenti bannati (ora): {final_banned_count}\n"
        f"• Altri errori: {failed_count}\n"
        f"• Tasso di successo (sugli utenti mirati): {success_rate:.1f}%"
    )
    if broadcast_type == "with_payment":
        final_text += f"\n• Opzioni di pagamento inviate: {payment_sent_count}"
    final_text += "\n\n💡 Gli utenti che bloccano il bot vengono automaticamente aggiunti alla lista dei bannati e non riceveranno più broadcast futuri."
    await progress_msg.edit_text(
        final_text,
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "admin_stars")
async def admin_stars_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.answer("Retrieving stars balance...")
    try:
        balance_info = await get_bot_stars_balance(bot)
        subscribers_data = load_json(SUBSCRIBERS_DATA_FILE)
        packages_data = load_json(PAYMENT_PACKAGES_FILE)

        estimated_stars_earned = 0
        sold_packages_counts = {pkg_id: 0 for pkg_id in packages_data.keys()}

        # Add old package types for backward compatibility in stats calculation
        old_package_stars = {
            "1_month_access": 250,
            "2_months_access": 350, # Old constant value
            "3_months_access": 500
        }
        for old_pkg_type in old_package_stars:
            if old_pkg_type not in sold_packages_counts:
                sold_packages_counts[old_pkg_type] = 0

        # Add VIP Image Gen to sold_packages_counts
        sold_packages_counts["vip_image_gen"] = 0

        for sub_user_id, sub_info in subscribers_data.items():
            if isinstance(sub_info, dict) and 'package_type' in sub_info:
                package_id = sub_info['package_type']

                # Check for VIP Image Gen first
                if package_id == "vip_image_gen":
                    estimated_stars_earned += IMAGE_GENERATION_STARS
                    sold_packages_counts["vip_image_gen"] += 1
                else:
                    # Try to find in dynamic packages
                    pkg_details = packages_data.get(package_id)
                    if pkg_details:
                        estimated_stars_earned += pkg_details.get('stars', 0)
                        sold_packages_counts[package_id] = sold_packages_counts.get(package_id, 0) + 1
                    else:
                        # Fallback for old, non-dynamic package types
                        if package_id in old_package_stars:
                            estimated_stars_earned += old_package_stars[package_id]
                            sold_packages_counts[package_id] = sold_packages_counts.get(package_id, 0) + 1


        total_sold_packs = sum(sold_packages_counts.values())

        stars_text = (
            f"⭐ **Telegram Stars Balance**\n\n"
            f"🏦 **Official Balance:**\n"
            f"• {balance_info}\n\n"
            f"📊 **Local Statistics:**\n"
            f"• Total Packages Sold: {total_sold_packs}\n"
        )
        for pkg_id, pkg_info in packages_data.items():
            stars_text += f"  • {pkg_info['label']}: {sold_packages_counts.get(pkg_id, 0)}\n"

        # Add VIP Image Gen to display if sold
        if sold_packages_counts.get("vip_image_gen", 0) > 0:
            stars_text += f"  • VIP Image Generation: {sold_packages_counts['vip_image_gen']}\n"

        # Add old package types to display if they still exist in sold counts
        for old_pkg_type, count in sold_packages_counts.items():
            if old_pkg_type not in packages_data and old_pkg_type != "vip_image_gen" and count > 0:
                stars_text += f"  • {old_pkg_type.replace('_access', '').replace('_', ' ').title()} (Legacy): {count}\n"


        stars_text += (
            f"• Estimated Stars Received: {estimated_stars_earned} ⭐\n"
            f"• Estimated Value: ${estimated_stars_earned * 0.01:.2f} USD\n\n"
            f"💡 **Info:**\n"
        )
        for pkg_id, pkg_info in packages_data.items():
            stars_text += f"• Package Price {pkg_info['label']}: {pkg_info['stars']} stars ({pkg_info['messages']} messages)\n"

        stars_text += f"• Package Price VIP Image Gen: {IMAGE_GENERATION_STARS} stars (Unlimited messages for feature)\n"

        stars_text += (
            f"• Withdrawal available after 21 days\n\n"
            f"🔗 For full withdrawal, go to @BotFather → Bot Settings → Payments"
        )
    except Exception as e:
        logging.error(f"Error in stars callback: {e}")
        stars_text = (
            f"⭐ **Telegram Stars Balance**\n\n"
            f"❌ **Error retrieving official balance**\n"
            f"Error: {str(e)}\n\n"
            f"📊 **Local Statistics (partial):**\n"
            f"• Total Packages Sold (estimated): {len(load_json(SUBSCRIBERS_DATA_FILE))}\n"
            f"💡 Try checking manually on @BotFather"
        )
    await callback.message.edit_text(
        stars_text,
        reply_markup=get_admin_back_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "admin_clear_logs")
async def admin_clear_logs_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return
    log_files = ["bot.log", "errors.log", "debug.log"]
    cleared_files = []
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                open(log_file, 'w').close()
                cleared_files.append(log_file)
            except Exception as e:
                logging.error(f"Error clearing {log_file}: {e}")
    if cleared_files:
        files_text = "\n".join([f"• {f}" for f in cleared_files])
        result_text = f"✅ **Logs Cleared**\n\nFiles cleared:\n{files_text}"
    else:
        result_text = "ℹ️ **No Logs Found**\n\nNo log files to clear."
    await callback.message.edit_text(
        result_text,
        reply_markup=get_admin_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("Operation completed")

# NEW ADMIN FUNCTIONALITIES HANDLERS:

@dp.callback_query(F.data == "admin_view_subscribers")
async def admin_view_subscribers_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    subscribers_data = load_json(SUBSCRIBERS_DATA_FILE)
    users_info_data = load_json(USERS_INFO_FILE)
    packages_data = load_json(PAYMENT_PACKAGES_FILE)

    if not subscribers_data:
        await callback.message.edit_text("🤷‍♀️ **No subscribers found!**\n\nThere are currently no users with active or expired subscriptions.", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    response_text = "⭐ **Subscriber List and Remaining Messages** ⭐\n\n"

    sorted_subscribers = sorted(
        subscribers_data.items(),
        key=lambda x: x[1].get('remaining_messages', 0),
        reverse=True
    )

    for uid, sub_info in sorted_subscribers:
        user_info = users_info_data.get(uid, {})
        username = user_info.get('username', '')
        first_name = user_info.get('first_name', '(no name)')
        uname = f"@{escape_markdown_v2(username)}" if username else escape_markdown_v2(first_name)

        remaining_messages = sub_info.get('remaining_messages', 0)

        # Get package label dynamically
        package_type_raw = sub_info.get('package_type', 'N/A')
        pkg_details = packages_data.get(package_type_raw)

        if package_type_raw == "vip_image_gen":
            package_type_display = "VIP Image Gen"
        elif pkg_details:
            package_type_display = pkg_details.get('label', 'N/A')
        else:
            package_type_display = package_type_raw.replace('_access', '').replace('_', ' ').title() # Fallback for old types

        status = "Messages exhausted"
        if remaining_messages > 0:
            status = f"**{remaining_messages}** messages remaining"

        response_text += f"**{uname}** (ID: `{uid}`)\n" \
                         f"  Package: {package_type_display}\n" \
                         f"  Status: {status}\n\n"

        if len(response_text) > 3500: # Telegram message length limit
            await callback.message.answer(response_text, parse_mode="Markdown")
            response_text = "" # Reset for next chunk if needed

    if response_text.strip():
        await callback.message.edit_text(response_text, reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
    else: # If all was sent in chunks, just send the back button
            await callback.message.answer("Subscriber list completed.", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")

    await callback.answer()


@dp.callback_query(F.data == "admin_view_conversations_list")
async def admin_view_conversations_list_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await show_users_page(callback.message, 0, edit=True, for_conversations=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("conv_list_page_"))
async def admin_conversations_list_page_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    page = int(callback.data.split("_")[-1])
    await show_users_page(callback.message, page, edit=True, for_conversations=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("view_conv_")) # Shortened callback data
async def admin_view_specific_conversation(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_id = callback.data.replace("view_conv_", "") # Correct replacement
    conversation_history = load_conversation(target_id)

    user_info = load_json(USERS_INFO_FILE).get(target_id, {})
    username = user_info.get('username', 'N/A')
    first_name = user_info.get('first_name', 'N/A')

    header_text = f"**Conversation History for User {escape_markdown_v2(first_name)} (@{escape_markdown_v2(username)}) - ID: `{target_id}`:**\n\n"

    if not conversation_history:
        await callback.message.edit_text(f"{header_text}No conversation found for this user.", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
    else:
        # Initial message to edit
        await callback.message.edit_text(f"{header_text}Loading conversation...", parse_mode="Markdown")

        response_parts = []
        # Displaying most recent messages first
        for msg in reversed(conversation_history):
            role_display = "User" if msg["role"] == "user" else "Yuki"
            msg_content = escape_markdown_v2(msg['content'])
            part = f"**{role_display}:** {msg_content}\n\n"

            # Check if adding this part exceeds Telegram's message limit
            if len("".join(response_parts) + part) > 4000: # Telegram limit is 4096, keep some buffer
                await callback.message.answer("".join(response_parts), parse_mode="Markdown")
                response_parts = [part] # Start a new chunk
            else:
                response_parts.append(part)

        if response_parts:
            await callback.message.answer("".join(response_parts), parse_mode="Markdown")

        await callback.message.answer("Conversation displayed.", reply_markup=get_admin_back_keyboard())

    await callback.answer()


@dp.callback_query(F.data == "admin_search_user")
async def admin_search_user_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "🔎 **Search User**\n\nEnter a username or part of the first/last name to search for:",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_search_query)
    await callback.answer()

@dp.message(AdminStates.waiting_for_search_query)
async def process_search_query(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    search_query = message.text.strip().lower()
    users_info_data = load_json(USERS_INFO_FILE)
    found_users = []

    for uid, user_data in users_info_data.items():
        username = user_data.get("username", "").lower()
        first_name = user_data.get("first_name", "").lower()
        last_name = user_data.get("last_name", "").lower()

        if search_query in username or search_query in first_name or search_query in last_name or search_query == uid:
            found_users.append((uid, user_data))

    if not found_users:
        await message.answer(f"No users found for search: `{escape_markdown_v2(search_query)}`.", parse_mode="Markdown")
    else:
        response_text = f"**Users Found for '{escape_markdown_v2(search_query)}':**\n\n"
        buttons = []
        for uid, user_data in found_users:
            username = user_data.get("username", "")
            first_name = user_data.get("first_name", "")
            last_name = user_data.get("last_name", "")
            display_name = f"{first_name} {last_name}".strip() if first_name or last_name else "(Unknown Name)"
            display_username = f"@{username}" if username else "(Unknown Username)"
            response_text += f"- **{escape_markdown_v2(display_name)}** {escape_markdown_v2(display_username)} (ID: `{uid}`)\n"
            buttons.append([InlineKeyboardButton(text=f"Manage {display_name} ({uid})", callback_data=f"usr_dtl_{uid}")]) # Shortened

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons + get_admin_back_keyboard().inline_keyboard)

        await message.answer(response_text, reply_markup=keyboard, parse_mode="Markdown")

    await state.clear()
    # No need to send main keyboard here, it's included in the search results or admin_cancel handles it.

# NEW: Admin to view user details and manage
@dp.callback_query(F.data.startswith("usr_dtl_")) # Shortened callback data
async def admin_user_details_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("usr_dtl_", "") # Correct replacement
    user_info = load_json(USERS_INFO_FILE).get(target_user_id, {})
    packages_data = load_json(PAYMENT_PACKAGES_FILE)

    if not user_info:
        await callback.message.edit_text(f"User `{target_user_id}` not found in the database.", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    username = user_info.get('username', 'N/A')
    first_name = user_info.get('first_name', 'N/A')
    last_name = user_info.get('last_name', '')
    joined_date = user_info.get('joined_date', 'N/A')
    last_interaction = user_info.get('last_interaction', 'N/A')

    # Handle custom character display in admin panel
    chosen_character_id = user_info.get('character', 'yuki_default')
    if chosen_character_id.startswith("custom_personality_"):
        chosen_character = user_info.get('custom_name', 'Custom Personality') + " (User Defined)"
    else:
        chosen_character = CHARACTER_PROMPTS.get(chosen_character_id, {}).get('name', 'Default Yuki')

    free_data = get_free_data(target_user_id)
    free_used_count = free_data.get("free_used", 0)

    subscriber_info = get_subscriber_data(target_user_id)
    subscription_status = "Not subscribed."
    if subscriber_info and isinstance(subscriber_info, dict) and 'remaining_messages' in subscriber_info:
        remaining_paid_messages = subscriber_info['remaining_messages']
        package_type_raw = subscriber_info.get('package_type', 'N/A')

        if package_type_raw == "vip_image_gen":
            package_type = "VIP Image Generation"
        else:
            pkg_details = packages_data.get(package_type_raw)
            if pkg_details:
                package_type = pkg_details.get('label', 'N/A')
            else:
                package_type = package_type_raw.replace('_', ' ').title() # Fallback for old types

        if remaining_paid_messages > 0:
            subscription_status = f"Subscribed ({package_type}) with {remaining_paid_messages} messages remaining."
        else:
            subscription_status = f"Subscription Expired ({package_type}) with 0 messages remaining."

    ban_status = "No"
    if is_user_banned(target_user_id):
        ban_status = f"Yes (since {load_json(BANNED_USERS_FILE).get(target_user_id, 'N/A')[:10]})"


    details_text = (
        f"👤 **User Details**\n\n"
        f"**ID:** `{target_user_id}`\n"
        f"**Name:** {escape_markdown_v2(first_name)} {escape_markdown_v2(last_name)}\n"
        f"**Username:** @{escape_markdown_v2(username)}\n"
        f"**Joined Date:** {joined_date[:10]}\n"
        f"**Last Interaction:** {last_interaction[:16]}\n"
        f"**Chosen Character:** {escape_markdown_v2(chosen_character)}\n\n"
        f"**Free Status:** Used {free_used_count}/{MSG_LIMIT_FREE} (Remaining: {MSG_LIMIT_FREE - free_used_count})\n"
        f"**Subscription Status:** {subscription_status}\n"
        f"**Banned:** {ban_status}\n\n"
        f"Choose an action for this user:"
    )

    await callback.message.edit_text(
        details_text,
        reply_markup=get_manage_subscription_keyboard_for_user(target_user_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("send_msg_")) # Shortened callback data
async def admin_send_message_to_specific_user_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("send_msg_", "") # Correct replacement
    await state.update_data(target_user_id_for_manage=target_user_id) # Reuse this state variable
    await callback.message.edit_text(
        f"✉️ **Send Message to Specific User**\n\nSelected user: `{target_user_id}`\n\n"
        f"Now send the message you want to send to this user. Supports Markdown.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_send_message_text)
    await callback.answer()


@dp.callback_query(F.data == "admin_manage_subscription_start")
async def admin_manage_subscription_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ **Manage User Subscriptions**\n\nEnter the ID of the user whose subscription you want to manage:",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_manage_sub_user_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_manage_sub_user_id)
async def process_manage_subscription_user_id(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    target_id = message.text.strip()
    if not target_id.isdigit():
        await message.answer("❌ Invalid user ID. It must be a number.", reply_markup=get_admin_cancel_keyboard())
        return

    user_info = load_json(USERS_INFO_FILE).get(target_id)
    if not user_info:
        await message.answer(f"User `{target_id}` not found in the database.", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
        await state.clear()
        return

    # Store the target_id in state for subsequent actions within this management flow
    await state.update_data(target_user_id_for_manage=target_id)

    # Redirect to user details page
    await message.answer(f"User `{target_id}` selected for management. Loading details...", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown") # Give immediate feedback
    # Simulate a callback query to reuse admin_user_details_callback logic
    dummy_callback = types.CallbackQuery(id='dummy_id', from_user=message.from_user, message=message, data=f"usr_dtl_{target_id}") # Use shortened data
    await admin_user_details_callback(dummy_callback)
    await state.clear()


@dp.callback_query(F.data.startswith("set_free_")) # Shortened callback data
async def manage_sub_set_free_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    target_user_id = callback.data.replace("set_free_", "") # Correct replacement
    await state.update_data(target_user_id_for_manage=target_user_id) # Reuse common state variable
    # Use global MSG_LIMIT_FREE
    await callback.message.edit_text(
        f"**Set Free Messages**\n\nEnter the number of free messages you want user `{target_user_id}` to have *used* (e.g., 0 for reset, 1, 2).\nThe current maximum is {MSG_LIMIT_FREE}.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_set_free_messages_amount)
    await callback.answer()

@dp.message(AdminStates.waiting_for_set_free_messages_amount)
async def process_set_free_messages_amount(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    data = await state.get_data()
    target_user_id = data.get("target_user_id_for_manage")

    if not target_user_id:
        await message.answer("Error: User ID not found in session. Please try again.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        await state.clear()
        return

    try:
        new_free_used_count = int(message.text.strip())
        # Use global MSG_LIMIT_FREE
        if new_free_used_count < 0 or new_free_used_count > MSG_LIMIT_FREE:
            raise ValueError
    except ValueError:
        await message.answer(f"❌ Invalid number. Enter an integer between 0 and {MSG_LIMIT_FREE}.")
        return

    # Update the free message count for the *specific* user being managed
    update_free_data(target_user_id, new_free_used_count)

    await message.answer(
        f"✅ **Free Messages Updated**\n\n"
        f"User `{target_user_id}` has now **{MSG_LIMIT_FREE - new_free_used_count}** free messages remaining (if {new_free_used_count} used)."
        f"\n\nOperation completed.",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await state.clear()


@dp.callback_query(F.data.startswith("add_paid_")) # Shortened to handle dynamic package IDs in callback_data
async def manage_sub_add_access(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    parts = callback.data.split("_")
    # Expected format: "add_paid_{user_id}_{package_id}"
    if len(parts) < 3:
        await callback.answer("Error in callback data format.", show_alert=True)
        await callback.message.edit_text("Operation failed.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return

    target_user_id = parts[2]
    package_id = parts[3] # The dynamic package ID

    # --- DEBUGGING START ---
    logging.info(f"DEBUG: Callback data received: {callback.data}")
    logging.info(f"DEBUG: Extracted target_user_id: {target_user_id}, package_id: {package_id}")
    # --- DEBUGGING END ---

    messages_to_add = 0

    if package_id == "vip_image_gen":
        messages_to_add = VIP_PREMIUM_MESSAGE_COUNT
    else:
        packages = load_json(PAYMENT_PACKAGES_FILE)
        package_info = packages.get(package_id)

        if not package_info:
            logging.error(f"ERROR: Package with ID '{package_id}' NOT found in {PAYMENT_PACKAGES_FILE} for add_paid_ callback.")
            await callback.answer("Error: Package not found for addition.", show_alert=True)
            await callback.message.edit_text("Error: Package not found for addition. Please check package configuration.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
            return
        messages_to_add = package_info['messages']

    current_subscriber_info = get_subscriber_data(target_user_id)
    current_messages = current_subscriber_info.get('remaining_messages', 0) if current_subscriber_info else 0
    new_total_messages = current_messages + messages_to_add

    # Use the package_id from the callback to store it
    update_subscriber_data(target_user_id, {'remaining_messages': new_total_messages, 'package_type': package_id})
    remove_free_user(target_user_id)

    await callback.message.edit_text(
        f"✅ **Paid Messages Added**\n\n"
        f"Added {messages_to_add} messages to user `{target_user_id}`. Total: **{new_total_messages}** messages.",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("rem_sub_")) # Shortened callback data
async def manage_sub_remove_access(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    # FIX IS APPLIED HERE: The extra ')' was removed from the callback data generation
    target_user_id = callback.data.replace("rem_sub_", "") # Correct replacement

    remove_subscriber(target_user_id)

    update_free_data(target_user_id, 0)

    await callback.message.edit_text(
        f"✅ **Subscription Removed**\n\n"
        f"Subscription removed for user `{target_user_id}`. Free messages have been reset ({MSG_LIMIT_FREE} available).", # Use global MSG_LIMIT_FREE
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_send_message_to_user")
async def admin_send_message_to_user_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "✉️ **Send Message to User**\n\nEnter the ID of the user you want to send a message to:",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_send_message_user_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_send_message_user_id)
async def process_send_message_user_id(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    target_id = message.text.strip()
    if not target_id.isdigit():
        await message.answer("❌ Invalid user ID. It must be a number.", reply_markup=get_admin_cancel_keyboard())
        return

    if target_id not in load_json(USERS_INFO_FILE):
        await message.answer(f"User `{target_id}` not found in the database.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        await state.clear()
        return

    await state.update_data(target_user_id_for_manage=target_id) # Reuse this state variable for sending message
    await message.answer(
        f"**Send Message to User**\n\nSelected user: `{target_id}`\n\n"
        f"Now send the message you want to send to this user. Supports Markdown.",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_send_message_text)

@dp.message(AdminStates.waiting_for_send_message_text)
async def process_send_message_text(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    data = await state.get_data()
    target_user_id = data.get("target_user_id_for_manage")
    message_text = message.text

    if not target_user_id:
        await message.answer("Error: User ID not found in session. Please try again.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=int(target_user_id),
            text=f"**Message from Admin:**\n{message_text}",
            parse_mode="Markdown" # Corrected parameter name
        )
        await message.answer(f"✅ Message sent successfully to user `{target_user_id}`.", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending admin message to user {target_user_id}: {e}")
        await message.answer(f"❌ Error sending message to user `{target_user_id}`: {str(e)}", parse_mode="Markdown")

    await state.clear()
    await message.answer("Operation completed.", reply_markup=get_admin_main_keyboard())


@dp.callback_query(F.data == "admin_api_stats")
async def admin_api_stats_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    total_calls = api_call_stats["total_calls"]
    successful_calls = api_call_stats["successful_calls"]
    failed_calls = api_call_stats["failed_calls"]
    total_response_time = api_call_stats["total_response_time"]
    last_reset_dt = datetime.fromisoformat(api_call_stats["last_reset"])
    last_reset_formatted = last_reset_dt.strftime('%d/%m/%Y %H:%M:%S')

    avg_response_time = (total_response_time / successful_calls) if successful_calls > 0 else 0

    stats_message = (
        f"📊 **AI API Statistics** 📊\n\n"
        f"• Total Calls: {total_calls}\n"
        f"• Successful Calls: {successful_calls}\n"
        f"• Failed Calls: {failed_calls}\n"
        f"• Average Response Time: {avg_response_time:.2f} seconds\n"
        f"• Last Statistics Reset: {last_reset_formatted}\n\n"
        f"*(These statistics are from the last manual reset or bot startup.)*"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Reset API Stats", callback_data="reset_api_stats")], # Shortened
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="admin_main")]
    ])

    await callback.message.edit_text(
        stats_message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "reset_api_stats") # Shortened
async def admin_reset_api_stats_confirmation(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Reset", callback_data="conf_reset_api_stats")], # Shortened
        [InlineKeyboardButton(text="❌ No, Cancel", callback_data="admin_api_stats")] # Return to stats page
    ])

    await callback.message.edit_text(
        "⚠️ **Confirm API Stats Reset**\n\n"
        "Are you sure you want to reset all AI API usage statistics?\n"
        "This action is irreversible.",
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "conf_reset_api_stats") # Shortened
async def admin_perform_reset_api_stats(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if not is_admin(user_id):
        await callback.answer("Access denied", show_alert=True)
        return

    reset_api_stats()
    await callback.message.edit_text(
        "✅ **API Stats Reset!**\n\n"
        "AI API usage statistics have been reset.",
        reply_markup=get_admin_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("API stats reset.")

# NEW: Ban Management Handlers
@dp.callback_query(F.data == "admin_manage_bans")
async def admin_manage_bans_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await show_users_page(callback.message, 0, edit=True, for_ban_management=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("bans_page_"))
async def admin_manage_bans_page_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    page = int(callback.data.split("_")[-1])
    await show_users_page(callback.message, page, edit=True, for_ban_management=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("ban_user_")) # Shortened
async def manage_sub_ban_user_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("ban_user_", "") # Correct replacement
    await state.update_data(target_user_to_ban_unban=target_user_id) # Use a common state variable

    user_info = load_json(USERS_INFO_FILE).get(target_user_id, {})
    username = user_info.get('username', 'N/A')
    first_name = user_info.get('first_name', 'N/A')

    if is_user_banned(target_user_id):
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, Unban", callback_data=f"conf_unban_{target_user_id}")], # Shortened
            [InlineKeyboardButton(text="❌ No, Cancel", callback_data=f"usr_dtl_{target_user_id}")] # Return to user details (Shortened)
        ])
        text_message = (
            f"⚠️ **Confirm User Unban**\n\n"
            f"Are you sure you want to unban the user:\n"
            f"Name: **{escape_markdown_v2(first_name)}** (@{escape_markdown_v2(username)})\n"
            f"ID: `{target_user_id}`\n\n"
            f"This user will be able to interact with the bot again (and will have 0 free messages)."
        )
        await state.set_state(AdminStates.waiting_for_unban_confirmation)
    else:
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"conf_ban_{target_user_id}")], # Shortened
            [InlineKeyboardButton(text="❌ No, Cancel", callback_data=f"usr_dtl_{target_user_id}")] # Return to user details (Shortened)
        ])
        text_message = (
            f"⚠️ **Confirm User Ban**\n\n"
            f"Are you sure you want to ban the user:\n"
            f"Name: **{escape_markdown_v2(first_name)}** (@{escape_markdown_v2(username)})\n"
            f"ID: `{target_user_id}`\n\n"
            f"This will prevent the user from using the bot and will delete all their data."
        )
        await state.set_state(AdminStates.waiting_for_ban_confirmation)

    await callback.message.edit_text(
        text_message,
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("conf_ban_"), AdminStates.waiting_for_ban_confirmation) # Shortened
async def confirm_ban_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("conf_ban_", "") # Correct replacement
    ban_user(target_user_id) # Call the helper function

    await callback.message.edit_text(
        f"✅ **User Banned**\n\n"
        f"User `{target_user_id}` has been banned and will no longer be able to use the bot. All their data has been deleted.",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data.startswith("conf_unban_"), AdminStates.waiting_for_unban_confirmation) # Shortened
async def confirm_unban_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("conf_unban_", "") # Correct replacement
    unban_user(target_user_id) # Call the helper function
    update_free_data(target_user_id, 0) # Give them free messages back after unban

    await callback.message.edit_text(
        f"✅ **User Unbanned**\n\n"
        f"User `{target_user_id}` has been unbanned and can use the bot again. They have **{MSG_LIMIT_FREE}** free messages available.", # Use global MSG_LIMIT_FREE
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await state.clear()
    await callback.answer()

# Consolidated handler for ban/unban from main user list
@dp.callback_query(F.data.startswith("ban_unban_")) # Shortened
async def manage_ban_unban_from_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    target_user_id = callback.data.replace("ban_unban_", "") # Correct replacement

    if is_user_banned(target_user_id):
        await callback.answer(f"Unbanning user {target_user_id}...")
        unban_user(target_user_id)
        update_free_data(target_user_id, 0)
        # Refresh the ban management page after action
        current_page = 0 # Assuming we stay on page 0 for simplicity after action
        await show_users_page(callback.message, 0, edit=True, for_ban_management=True)

    else:
        await callback.answer(f"Banning user {target_user_id}...")
        ban_user(target_user_id)
        # Refresh the ban management page after action
        current_page = 0
        await show_users_page(callback.message, 0, edit=True, for_ban_management=True)
    await callback.answer()

# NEW: Payment Package Management Handlers
@dp.callback_query(F.data == "admin_manage_packages")
async def admin_manage_packages_callback(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    packages = load_json(PAYMENT_PACKAGES_FILE)
    if not packages:
        text = "🛒 **Payment Package Management**\n\nNo payment packages configured."
    else:
        text = "🛒 **Payment Package Management**\n\nCurrent packages:\n"
        for pkg_id, pkg_info in packages.items():
            text += f"• `{pkg_info['label']}`: {pkg_info['stars']}⭐ - {pkg_info['messages']}💬\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_manage_packages_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_new_pkg") # Shortened
async def add_new_package_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.edit_text(
        "➕ **New Payment Package**\n\nEnter the label that will appear on the button (e.g., '1 Month', 'Premium'):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_package_label)
    await callback.answer()

@dp.message(AdminStates.waiting_for_package_label)
async def process_package_label(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    label = message.text.strip()
    if not label:
        await message.answer("The label cannot be empty. Please try again:", reply_markup=get_admin_cancel_keyboard())
        return

    data = await state.get_data()
    # If editing, maintain existing values, otherwise initialize for new package
    if 'editing_package_id' in data:
        await state.update_data(editing_package_label=label)
        await message.answer("Now enter the **new number of Telegram Stars** (leave empty to keep current):",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_package_stars)
    else:
        await state.update_data(new_package_label=label)
        await message.answer("Now enter the number of **Telegram Stars** for this package (integers only):",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_package_stars)

@dp.message(AdminStates.waiting_for_package_stars)
async def process_package_stars(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    stars_input = message.text.strip()
    data = await state.get_data()

    if stars_input == "" and 'editing_package_id' in data:
        # User left it empty, keep existing stars for editing
        stars = data['editing_package_stars']
    else:
        try:
            stars = int(stars_input)
            if stars <= 0:
                raise ValueError("Stars must be positive.")
        except ValueError:
            await message.answer("Invalid number of stars. Enter a positive integer or leave empty to keep current:",
                                 reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
            return

    if 'editing_package_id' in data:
        await state.update_data(editing_package_stars=stars)
        await message.answer("Now enter the **new number of messages** (leave empty to keep current):",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_package_messages)
    else:
        await state.update_data(new_package_stars=stars)
        await message.answer("Now enter the number of **messages** this package will give to the user (integers only):",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_package_messages)

@dp.message(AdminStates.waiting_for_package_messages)
async def process_package_messages(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    messages_input = message.text.strip()
    data = await state.get_data()

    if messages_input == "" and 'editing_package_id' in data:
        # User left it empty, keep existing messages for editing
        messages = data['editing_package_messages']
    else:
        try:
            messages = int(messages_input)
            if messages <= 0:
                raise ValueError("Messages must be positive.")
        except ValueError:
            await message.answer("Invalid number of messages. Enter a positive integer or leave empty to keep current:",
                                 reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
            return

    packages = load_json(PAYMENT_PACKAGES_FILE)

    if 'editing_package_id' in data:
        package_id = data['editing_package_id']
        label = data.get('editing_package_label', packages[package_id]['label'])
        stars = data.get('editing_package_stars', packages[package_id]['stars'])

        packages[package_id] = {"label": label, "stars": stars, "messages": messages}
        save_json(PAYMENT_PACKAGES_FILE, packages)

        await state.clear()
        await message.answer(
            f"✅ **Package Updated!**\n\n"
            f"Name: `{label}`\n"
            f"Stars: `{stars}`\n"
            f"Messages: `{messages}`\n\n"
            f"The package has been updated.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )
    else:
        label = data['new_package_label']
        stars = data['new_package_stars']

        package_id = str(uuid.uuid4().hex)[:10] # Generate a shorter unique ID
        packages[package_id] = {"label": label, "stars": stars, "messages": messages}
        save_json(PAYMENT_PACKAGES_FILE, packages)

        await state.clear()
        await message.answer(
            f"✅ **Package Added!**\n\n"
            f"Name: `{label}`\n"
            f"Stars: `{stars}`\n"
            f"Messages: `{messages}`\n\n"
            f"The package has been added and will be visible in the payment menu.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("edit_pkg_")) # Shortened
async def edit_package_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    package_id = callback.data.replace("edit_pkg_", "") # Correct replacement
    packages = load_json(PAYMENT_PACKAGES_FILE)
    package_info = packages.get(package_id)

    if not package_info:
        await callback.answer("Error: Package not found.", show_alert=True)
        await callback.message.edit_text("Error: Package not found.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return

    await state.update_data(editing_package_id=package_id,
                            editing_package_label=package_info['label'],
                            editing_package_stars=package_info['stars'],
                            editing_package_messages=package_info['messages'])

    await callback.message.edit_text(
        f"✏️ **Edit Package: {escape_markdown_v2(package_info['label'])}**\n\n"
        f"ID: `{package_id}`\n"
        f"Current: {package_info['stars']}⭐ - {package_info['messages']}💬\n\n"
        f"Enter the **new label** for the button (leave empty to keep '{package_info['label']}'):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_package_label) # Reusing state for label input

@dp.callback_query(F.data.startswith("del_pkg_")) # Shortened
async def delete_package_confirmation(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    package_id = callback.data.replace("del_pkg_", "") # Correct replacement
    packages = load_json(PAYMENT_PACKAGES_FILE)
    package_info = packages.get(package_id)

    if not package_info:
        await callback.answer("Error: Package not found.", show_alert=True)
        await callback.message.edit_text("Error: Package not found.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"conf_del_pkg_{package_id}")], # FIX APPLIED HERE: Rimozione della parentesi extra
        [InlineKeyboardButton(text="❌ No, Cancel", callback_data="admin_manage_packages")]
    ])

    await callback.message.edit_text(
        f"⚠️ **Confirm Package Deletion**\n\n"
        f"Are you sure you want to delete the package:\n"
        f"Name: `{escape_markdown_v2(package_info['label'])}` (ID: `{package_id}`)\n"
        f"Stars: {package_info['stars']}⭐ - Messages: {package_info['messages']}💬\n\n"
        f"This action is irreversible and the button will no longer be visible to users.",
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("conf_del_pkg_")) # Shortened
async def confirm_delete_package(callback: CallbackQuery):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    package_id = callback.data.replace("conf_del_pkg_", "") # Correct replacement
    packages = load_json(PAYMENT_PACKAGES_FILE)

    if package_id in packages:
        deleted_label = packages[package_id]['label']
        del packages[package_id]
        save_json(PAYMENT_PACKAGES_FILE, packages)
        await callback.message.edit_text(
            f"✅ **Package Deleted!**\n\n"
            f"The package `{escape_markdown_v2(deleted_label)}` has been removed.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text("Error: Package not found for deletion.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")

    await callback.answer()

# NEW: Handlers for setting Free Message Limit
@dp.callback_query(F.data == "admin_set_free_msg_limit")
async def admin_set_free_msg_limit_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(str(callback.from_user.id)):
        await callback.answer("Access denied", show_alert=True)
        return

    global MSG_LIMIT_FREE # Get the current value

    await callback.message.edit_text(
        f"🆓 **Set Free Message Limit**\n\n"
        f"The current global free message limit is: **{MSG_LIMIT_FREE}**\n\n"
        f"Please enter the new number of free messages to allow per user (must be an integer ≥ 0):",
        reply_markup=get_admin_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_new_free_message_limit)
    await callback.answer()

@dp.message(AdminStates.waiting_for_new_free_message_limit)
async def process_new_free_message_limit(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id): return

    try:
        new_limit = int(message.text.strip())
        if new_limit < 0:
            raise ValueError("Limit cannot be negative.")
    except ValueError:
        await message.answer("❌ Invalid input. Please enter a non-negative integer for the new limit.",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        return

    global MSG_LIMIT_FREE
    old_limit = MSG_LIMIT_FREE # Store old limit for broadcast message
    MSG_LIMIT_FREE = new_limit

    # Save the new limit to config file
    current_config = load_bot_config()
    current_config["MSG_LIMIT_FREE"] = new_limit
    save_bot_config(current_config)

    # --- Start Broadcast Logic for Free Messages Update ---
    users_info_data = load_json(USERS_INFO_FILE)
    all_user_ids = list(users_info_data.keys())
    # Only target users who are not banned
    target_user_ids = [uid for uid in all_user_ids if not is_user_banned(uid)]

    broadcast_message_text = (
        f"🎉 **Good news!** 🎉\n\n"
        f"The administrator has just reset and updated the free message limit! "
        f"You now have **{MSG_LIMIT_FREE}** free messages available to chat with me. "
        f"Enjoy our conversation! 😉"
    )

    await message.answer(
        f"✅ **Free Message Limit Updated!**\n\n"
        f"The new global free message limit is now: **{MSG_LIMIT_FREE}**\n"
        f"This change will apply to all new users and will reset the free message count for existing users upon their next interaction with the /start or /clear\\_memory command." # Fixed: escape _
        f"\n\n**Broadcasting this update to {len(target_user_ids)} users...**",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

    sent_broadcast_count = 0
    failed_broadcast_count = 0
    blocked_during_broadcast = 0

    for i, user_to_notify_id in enumerate(target_user_ids):
        try:
            # Reset free messages for each user during the broadcast
            update_free_data(user_to_notify_id, 0)
            await bot.send_message(
                chat_id=int(user_to_notify_id),
                text=broadcast_message_text,
                parse_mode="Markdown"
            )
            sent_broadcast_count += 1
        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "chat not found" in error_str:
                blocked_during_broadcast += 1
                ban_user(user_to_notify_id) # Ban users who blocked the bot
                logging.info(f"User {user_to_notify_id} blocked bot during free message broadcast, marked as banned.")
            else:
                failed_broadcast_count += 1
            logging.error(f"Error sending free message broadcast to user {user_to_notify_id}: {e}")
        await asyncio.sleep(0.05) # Small delay to avoid rate limits

    final_broadcast_summary = (
        f"📢 **Free Message Broadcast Summary:**\n\n"
        f"• Messages sent successfully: {sent_broadcast_count}\n"
        f"• Users newly blocked/banned during broadcast: {blocked_during_broadcast}\n"
        f"• Other errors: {failed_broadcast_count}\n"
        f"All free users have had their free message count reset to 0."
    )
    await message.answer(final_broadcast_summary, parse_mode="Markdown")

    # Clear state after all operations are done
    await state.clear()
    # --- End Broadcast Logic ---


# --- Regular Command Handlers ---
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    save_user_info(message.from_user)

    if is_user_banned(user_id):
        await message.answer("🚫 **You have been banned from using this bot.** You cannot send messages or interact.", parse_mode="Markdown")
        return

    # Ensure MSG_LIMIT_FREE is updated if changed by admin
    global MSG_LIMIT_FREE
    MSG_LIMIT_FREE = load_bot_config()["MSG_LIMIT_FREE"]

    free_data_for_user = get_free_data(user_id)
    subscriber_info = get_subscriber_data(user_id)

    if free_data_for_user.get("free_used", 0) == 0 and subscriber_info is None:
        update_free_data(user_id, 0)

    # Send welcome message and then the character/storytelling selection buttons
    await message.answer(WELCOME_MESSAGE, parse_mode="Markdown")
    await message.answer(
        "But first, choose my personality or start a story!",
        reply_markup=get_initial_roleplay_keyboard()
    )

    if is_admin(user_id):
        await message.answer("Welcome, admin! You have unlimited access to messages and features.")
        return

    # Existing logic for paid/free messages, will be shown after character selection
    # or the next interaction, as the initial message is now focused on character selection.
    # For now, it will appear right after the character selection buttons.
    if subscriber_info and isinstance(subscriber_info, dict) and 'remaining_messages' in subscriber_info:
        remaining_paid = subscriber_info['remaining_messages']
        if remaining_paid > 0:
            await message.answer(f"Welcome back! You have {remaining_paid} paid messages remaining.")
            return
        else:
            await message.answer("Your paid messages have been used up. You now have your free messages to try the bot again!")

    free_data_after_check = get_free_data(user_id)
    if free_data_after_check["free_used"] < MSG_LIMIT_FREE:
        await message.answer(f"You have {MSG_LIMIT_FREE - free_data_after_check['free_used']} free messages left to try the bot!")
    else:
        await message.answer("You have no free messages left. Please purchase a subscription to continue.",
                             reply_markup=get_payment_options_keyboard())

@dp.callback_query(F.data == "back_to_initial_menu")
async def back_to_initial_menu_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if is_user_banned(user_id):
        await callback.answer("🚫 You have been banned from using this bot.", show_alert=True)
        return

    await state.clear() # Clear any active user states
    await callback.message.edit_text(
        "Choose my personality or start a story!",
        reply_markup=get_initial_roleplay_keyboard()
    )
    await callback.answer("Returning to main options.")

@dp.callback_query(F.data == "choose_roleplay_character")
async def choose_roleplay_character_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if is_user_banned(user_id):
        await callback.answer("🚫 You have been banned from using this bot.", show_alert=True)
        return

    await callback.message.edit_text(
        "Choose my personality:",
        reply_markup=get_character_selection_keyboard()
    )
    await state.set_state(UserStates.waiting_for_roleplay_selection)
    await callback.answer()

@dp.callback_query(F.data.startswith("select_char_"), UserStates.waiting_for_roleplay_selection)
async def select_character_callback(callback: CallbackQuery, state: FSMContext): # Fixed: Added state parameter
    user_id = str(callback.from_user.id)
    character_id = callback.data.replace("select_char_", "")

    if character_id not in CHARACTER_PROMPTS or character_id == "storytelling_mode": # Ensure storytelling mode isn't chosen via this path
        await callback.answer("Invalid character selection.", show_alert=True)
        return

    set_user_character(user_id, character_id)
    selected_char_name = CHARACTER_PROMPTS[character_id]["name"]
    selected_char_description = CHARACTER_PROMPTS[character_id]["description"]

    await callback.message.edit_text(
        f"🎉 Great choice! I will now be **{escape_markdown_v2(selected_char_name)}**.\n\n"
        f"_{escape_markdown_v2(selected_char_description)}_\n\n"
        f"Let's start chatting!",
        parse_mode="Markdown"
    )
    await callback.answer(f"You have chosen the character: {selected_char_name}")
    await state.clear() # Clear the state after selection


# NEW: Handler for "Start Storytelling Mode" button
@dp.callback_query(F.data == "start_storytelling_mode")
async def start_storytelling_mode_callback(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if is_user_banned(user_id):
        await callback.answer("🚫 You have been banned from using this bot.", show_alert=True)
        return

    set_user_character(user_id, "storytelling_mode") # Set the character to the dedicated storytelling prompt
    clear_user_memory(user_id) # Clear memory for a fresh start in storytelling mode

    await callback.message.edit_text(
        f"📚 **Storytelling Mode Activated!** 📚\n\n"
        f"I will now act as a horny storyteller. Tell me the subject you want the story to be about, and I'll make it unforgettable!\n\n"
        f"*To return to regular chat or change my personality, use the /clear\\_memory or /reset command.*", # Fixed: escape _
        parse_mode="Markdown"
    )
    await callback.answer("Storytelling mode activated!")
    await state.clear() # Clear state as the mode is now set via character

# NEW: Handler for "Create Your Own Personality" button
@dp.callback_query(F.data == "create_custom_personality")
async def create_custom_personality_prompt(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    if is_user_banned(user_id):
        await callback.answer("🚫 You have been banned from using this bot.", show_alert=True)
        return

    # Check if user is premium to allow custom personality
    if not is_admin(user_id):
        subscriber_info = get_subscriber_data(user_id)
        if not (subscriber_info and subscriber_info.get('remaining_messages', 0) > 0):
            await callback.answer("💎 Only premium users can create custom personalities. Please purchase a subscription to unlock this feature!", show_alert=True)
            await callback.message.answer("Choose your package:", reply_markup=get_payment_options_keyboard())
            return

    await callback.message.edit_text(
        "✍️ **Create Your Own Personality**\n\n"
        "Great! Now, please **describe the personality** you want me to adopt. Be as detailed as possible! "
        "For example:\n\n"
        "`You are a wise old wizard who speaks in riddles and loves to give cryptic advice.`\n\n"
        "`You are a sassy, modern teenager who uses slang and emojis often.`\n\n"
        "**Note:** This personality will be applied to all your future chats until you change it. Your previous conversation history will be cleared.",
        reply_markup=get_admin_cancel_keyboard(), # Using admin_cancel as a general cancel for FSM
        parse_mode="Markdown"
    )
    await state.set_state(UserStates.waiting_for_custom_personality_description)
    await callback.answer()

@dp.message(UserStates.waiting_for_custom_personality_description)
async def process_custom_personality_description(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    custom_prompt_text = message.text.strip()

    if not custom_prompt_text:
        await message.answer("The personality description cannot be empty. Please try again:",
                             reply_markup=get_admin_cancel_keyboard(), parse_mode="Markdown")
        return

    # Clear memory and set custom personality
    clear_user_memory(user_id)
    set_user_custom_character_prompt(user_id, custom_prompt_text)

    # Decrement message count for premium users. This is also covered by image gen.
    # For now, custom personality creation also consumes 1 message, similar to image gen.
    if not is_admin(user_id):
        subscriber_info = get_subscriber_data(user_id)
        # Ensure it's not a VIP image gen purchase (which implies unlimited messages)
        if subscriber_info and subscriber_info.get('package_type') != "vip_image_gen" and subscriber_info.get('remaining_messages', 0) > 0:
            subscriber_info['remaining_messages'] -= 1 # Use 1 message for creating/changing personality
            update_subscriber_data(user_id, subscriber_info)

    await message.answer(
        f"🎉 **Your custom personality has been set!**\n\n"
        f"I will now interact with you based on your description:\n"
        f"_{escape_markdown_v2(custom_prompt_text)}_\n\n"
        f"Let's start chatting!",
        parse_mode="Markdown"
    )
    await state.clear()

    # Give remaining message count feedback, unless it's a VIP image gen subscription
    if not is_admin(user_id):
        subscriber_info = get_subscriber_data(user_id)
        if subscriber_info and subscriber_info.get('package_type') != "vip_image_gen" and subscriber_info.get('remaining_messages', 0) <= 10:
            await message.answer(f"You have {subscriber_info.get('remaining_messages', 0)} paid messages left! Get more messages to continue our fun chat! 😉", reply_markup=get_payment_options_keyboard())


@dp.message(Command("clear_memory", "reset"))
async def clear_memory_command(message: types.Message):
    user_id = str(message.from_user.id)

    if is_user_banned(user_id):
        await message.answer("🚫 **You cannot use this command, you have been banned.**", parse_mode="Markdown")
        return

    clear_user_memory(user_id)
    update_free_data(user_id, 0)
    # Reset character to default when memory is cleared
    set_user_character(user_id, "yuki_default")
    await message.answer("🧠 Your conversation memory has been cleared! My role is reset to default Yuki. You now have your free messages back.")
    if not is_admin(user_id):
        await bot.send_message(message.chat.id, "Ready for a fresh start? Get unlimited access!", reply_markup=get_payment_options_keyboard())

@dp.message(Command("balance"))
async def balance_command(message: types.Message):
    user_id = str(message.from_user.id)

    if is_user_banned(user_id):
        await message.answer("🚫 **You cannot use this command, you have been banned.**", parse_mode="Markdown")
        return

    if is_admin(user_id):
        await message.answer("You are admin: unlimited access.")
        return

    subscriber_info = get_subscriber_data(user_id)
    if subscriber_info and isinstance(subscriber_info, dict) and 'remaining_messages' in subscriber_info:
        remaining_paid_messages = subscriber_info['remaining_messages']
        if remaining_paid_messages > 0:
            await message.answer(f"You have {remaining_paid_messages} paid messages remaining.")
            return
        else:
            remove_subscriber(user_id)
            update_free_data(user_id, 0)
            await message.answer("Your paid messages have been used up. You now have your free messages available again. Consider purchasing a new pack!")
            await bot.send_message(message.chat.id, "Choose your new adventure!", reply_markup=get_payment_options_keyboard())
            return

    free = get_free_data(user_id)
    left = max(0, MSG_LIMIT_FREE - free["free_used"])
    await message.answer(f"You have {left} free messages available.")
    if left == 0:
        await bot.send_message(message.chat.id, "Ready for unlimited fun?", reply_markup=get_payment_options_keyboard())

# --- New function to get user intent from AI ---
async def get_user_intent(user_message_text: str) -> str:
    # This function is now skipped if user has a custom character or is in storytelling mode
    if not user_message_text or not user_message_text.strip():
        return "OTHER"

    prompt = f"""
    Analyze the user's message below to determine their primary intent.

    User message: "{user_message_text}"

    Is the user asking me (the AI bot) to:
    1. **GENERATE** a new image or video (e.g., "create a picture", "draw me a landscape", "make a video of a cat")?
    2. **SHOW** them an existing image or video of myself/my appearance (e.g., "can I see you?", "show me a photo of you", "send me a video")?
    3. Ask me to **DESCRIBE** an image or video that *they* will send to me, or have already sent (e.g., "describe this picture", "what do you see in this video")?
    4. Is it a general chat message, a roleplay request, or anything else not related to image/video generation, showing, or description?

    Respond with ONLY one of these exact classification words:
    - IMAGE_GENERATION_OR_VIEWING
    - IMAGE_DESCRIPTION
    - OTHER
    """

    messages_to_send = [
        {"role": "system", "content": "You are a helpful AI assistant tasked with classifying user intent based on the user's message. Provide only the classification word."},
        {"role": "user", "content": prompt}
    ]
    start_time = time.time()
    try:
        async with CLAUDE_SEMAPHORE:
            response = await client.chat.completions.create(
                model="grok-3", # Grok model
                messages=messages_to_send,
                max_tokens=20,
                temperature=0
            )
            intent = response.choices[0].message.content.strip().upper()
            end_time = time.time()
            update_api_stats(True, end_time - start_time)
            if intent in ["IMAGE_GENERATION_OR_VIEWING", "IMAGE_DESCRIPTION", "OTHER"]:
                return intent
            logging.warning(f"AI returned unexpected intent: '{intent}'. Defaulting to 'OTHER'.")
            return "OTHER"
    except Exception as e:
        logging.error(f"Error classifying user intent with AI: {e}")
        end_time = time.time()
        update_api_stats(False, end_time - start_time)
        return "OTHER"

# --- Message Handlers ---
@dp.message(F.text)
async def handle_text_message(message: types.Message):
    user_id = str(message.from_user.id)
    save_user_info(message.from_user)

    if is_user_banned(user_id):
        await message.answer("🚫 **You have been banned from using this bot.** You cannot send messages or interact.", parse_mode="Markdown")
        return

    message_content = message.text or ""

    # Get the currently chosen character for the user
    chosen_character_id = get_user_character(user_id)

    # Ensure MSG_LIMIT_FREE is updated if changed by admin
    global MSG_LIMIT_FREE
    MSG_LIMIT_FREE = load_bot_config()["MSG_LIMIT_FREE"]

    # --- START MODIFIED LOGIC FOR STORYTELLING AND CUSTOM PERSONALITY MODE ---
    # If in storytelling mode OR custom personality mode, bypass intent detection and go directly to AI response
    if chosen_character_id == "storytelling_mode" or chosen_character_id.startswith("custom_personality_"):
        if not is_admin(user_id):
            subscriber_info = get_subscriber_data(user_id)
            # If VIP image gen, then unlimited messages apply
            if subscriber_info and subscriber_info.get('package_type') == "vip_image_gen":
                ai_response = await generate_ai_response(user_id, message_content)
                await message.answer(ai_response)
                return
            elif subscriber_info and subscriber_info.get('remaining_messages', 0) > 0:
                subscriber_info['remaining_messages'] -= 1
                update_subscriber_data(user_id, subscriber_info)
                ai_response = await generate_ai_response(user_id, message_content)
                await message.answer(ai_response)

                remaining_paid = subscriber_info['remaining_messages']
                if remaining_paid == 0:
                    await message.answer("This was your last paid message! Don't leave me alone, get more messages! 😉", reply_markup=get_payment_options_keyboard())
                elif remaining_paid <= 10:
                    await message.answer(f"You have {remaining_paid} paid messages left! Get more messages to continue our fun chat! 😉", reply_markup=get_payment_options_keyboard())
                return
            else:
                free_data = get_free_data(user_id)
                if free_data["free_used"] < MSG_LIMIT_FREE:
                    update_free_data(user_id, free_data["free_used"] + 1)
                    ai_response = await generate_ai_response(user_id, message_content)
                    await message.answer(ai_response)

                    remaining_free = MSG_LIMIT_FREE - (free_data["free_used"] + 1)
                    if remaining_free == 0:
                        await message.answer("This was your last free message! Don't leave me alone, get unlimited access! 😉", reply_markup=get_payment_options_keyboard())
                    elif remaining_free == 1:
                        await message.answer("You have 1 free message left! You don't want our chat to end, do you? Get unlimited access! 😉", reply_markup=get_payment_options_keyboard())
                    return
                else:
                    await message.answer("You have no free messages left. Please purchase a subscription to continue.",
                                         reply_markup=get_payment_options_keyboard())
                    return
        else: # Admin user in storytelling or custom personality mode
            ai_response = await generate_ai_response(user_id, message_content)
            await message.answer(ai_response)
            return
    # --- END MODIFIED LOGIC FOR STORYTELLING AND CUSTOM PERSONALITY MODE ---


    # If not in storytelling or custom personality mode, proceed with intent detection as before
    user_intent = await get_user_intent(message_content)
    logging.info(f"User {user_id} intent: {user_intent} for message: '{message_content}'")

    if user_intent == "IMAGE_GENERATION_OR_VIEWING":
        if not is_admin(user_id):
            subscriber_info = get_subscriber_data(user_id)
            if not subscriber_info or subscriber_info.get('package_type') != "vip_image_gen": # Check specifically for VIP image gen access
                await message.answer(
                    "🚫 *Image and video generation is available only for 💎 **VIP Premium users**!* "
                    "Upgrade to unlock unlimited image and video generations!\n\n"
                    "Press the button below to purchase.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"🔑 Unlock VIP Premium ({IMAGE_GENERATION_STARS}⭐)", callback_data="unlock_image_generation")]
                    ]),
                    parse_mode="Markdown"
                )
                return
            else:
                await message.answer(
                    "I understand you'd like to see an image! While I love to chat, my current capabilities allow me to **describe images you send me**, but I cannot **generate or send images of myself** yet. Feel free to send me a picture for a detailed description! 😉"
                )
                return
        else:
            await message.answer(
                "I understand you'd like to see an image! As an admin, you have full access. However, please note that my current capabilities allow me to **describe images you send me**, but I cannot **generate or send images of myself** yet. Feel free to send me a picture for a detailed description!"
            )
            return

    elif user_intent == "IMAGE_DESCRIPTION":
        if not message.photo: # If user asks for description but sends no photo, prompt them to send one
            await message.answer("Please send me the photo you want me to describe! I'm eager to tell you all about it. 😉")
        return # Exit here, as photo handling will happen in @dp.message(F.photo) if one is sent later

    # Original message handling logic (for non-storytelling, non-image intent)
    if not is_admin(user_id):
        subscriber_info = get_subscriber_data(user_id)
        # If VIP image gen, then unlimited messages apply
        if subscriber_info and subscriber_info.get('package_type') == "vip_image_gen":
            ai_response = await generate_ai_response(user_id, message_content)
            await message.answer(ai_response)
            return
        elif subscriber_info and subscriber_info.get('remaining_messages', 0) > 0:
            subscriber_info['remaining_messages'] -= 1
            update_subscriber_data(user_id, subscriber_info)
            ai_response = await generate_ai_response(user_id, message_content)
            await message.answer(ai_response)

            remaining_paid = subscriber_info['remaining_messages']
            if remaining_paid == 0:
                await message.answer("This was your last paid message! Don't leave me alone, get more messages! 😉", reply_markup=get_payment_options_keyboard())
            elif remaining_paid <= 10:
                await message.answer(f"You have {remaining_paid} paid messages left! Get more messages to continue our fun chat! 😉", reply_markup=get_payment_options_keyboard())
            return
        else:
            free_data = get_free_data(user_id)
            if free_data["free_used"] < MSG_LIMIT_FREE:
                    update_free_data(user_id, free_data["free_used"] + 1)
                    ai_response = await generate_ai_response(user_id, message_content)
                    await message.answer(ai_response)

                    remaining_free = MSG_LIMIT_FREE - (free_data["free_used"] + 1)
                    if remaining_free == 0:
                        await message.answer("This was your last free message! Don't leave me alone, get unlimited access! 😉", reply_markup=get_payment_options_keyboard())
                    elif remaining_free == 1:
                        await message.answer("You have 1 free message left! You don't want our chat to end, do you? Get unlimited access! 😉", reply_markup=get_payment_options_keyboard())
                    return
            else:
                await message.answer("You have no free messages left. Please purchase a subscription to continue.",
                                     reply_markup=get_payment_options_keyboard())
                return
    else:
        ai_response = await generate_ai_response(user_id, message_content)
        await message.answer(ai_response)
        return

# --- Photo Handler ---
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = str(message.from_user.id)
    save_user_info(message.from_user)

    if is_user_banned(user_id):
        await message.answer("🚫 **You have been banned from using this bot.** You cannot send messages or interact.", parse_mode="Markdown")
        return

    if not is_admin(user_id):
        subscriber_info = get_subscriber_data(user_id)
        if not subscriber_info or subscriber_info.get('package_type') != "vip_image_gen": # Check specifically for VIP image gen access
            await message.answer("❌ Only 💎 **VIP Premium users** can use the image analysis feature. Please purchase a subscription to unlock this function.",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text=f"🔑 Unlock VIP Premium ({IMAGE_GENERATION_STARS}⭐)", callback_data="unlock_image_generation")]
                                 ]),
                                 parse_mode="Markdown")
            return
        # No message decrement for VIP image gen, as it's meant to be "unlimited" for image features.
        # If it's a regular paid package, decrement messages here as well, but the prompt should already be checked.

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)

        file_content = None
        try:
            file_content = await bot.download(file_info.file_id)
        except Exception as download_error:
            logging.error(f"Error downloading photo {file_info.file_id}: {download_error}")
            await message.answer("Error downloading your image. Please try again.")
            return

        image_bytes = file_content.read()
        prompt_text = message.caption if message.caption else "Describe this image."
        ai_response = await generate_ai_image_response(user_id, image_bytes, prompt_text)

        await message.answer(ai_response)

        # Only give message count feedback if not VIP image gen
        if not is_admin(user_id):
            subscriber_info = get_subscriber_data(user_id)
            if subscriber_info and subscriber_info.get('package_type') != "vip_image_gen":
                remaining_paid = subscriber_info['remaining_messages']
                if remaining_paid == 0:
                    await message.answer("This was your last paid message! Don't leave me alone, get more messages! 😉", reply_markup=get_payment_options_keyboard())
                elif remaining_paid <= 10:
                    await message.answer(f"You have {remaining_paid} paid messages left! Get more messages to continue our fun chat! 😉", reply_markup=get_payment_options_keyboard())

    except Exception as e:
        logging.error(f"Image processing error for user {user_id}: {e}")
        await message.answer("Error processing image. Please try again.")

# --- Payment Handlers ---
@dp.pre_checkout_query()
async def pre_checkout_query_handler(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user_id = str(message.from_user.id)
    payload = message.successful_payment.invoice_payload

    messages_to_add = 0
    package_type = "unknown_package"

    # Handle the new VIP Image Generation payload
    if f"user_{user_id}_vip_image_gen" in payload:
        messages_to_add = VIP_PREMIUM_MESSAGE_COUNT
        package_type = "vip_image_gen"
    else:
        # Extract package_id from payload (now looking for 'pkg_' prefix)
        match = re.search(r'pkg_([a-f0-9-]+)$', payload)
        package_id_from_payload = None
        if match:
            package_id_from_payload = match.group(1)

        if package_id_from_payload:
            packages = load_json(PAYMENT_PACKAGES_FILE)
            package_info = packages.get(package_id_from_payload)
            if package_info:
                messages_to_add = package_info['messages']
                package_type = package_id_from_payload
            else:
                logging.error(f"Package ID '{package_id_from_payload}' not found in payment_packages.json for payload: {payload}")
                # Fallback for old hardcoded packages if they somehow still come through
                if "1_month_access" in payload:
                    messages_to_add = 100 # Old MESSAGES_PER_1_MONTH_PACKAGE
                    package_type = "1_month_access"
                elif "2_months_access" in payload:
                    messages_to_add = 200 # Old MESSAGES_PER_2_MONTHS_PACKAGE
                    package_type = "2_months_access"
                elif "3_months_access" in payload:
                    messages_to_add = 250 # Old MESSAGES_PER_3_MONTHS_PACKAGE
                    package_type = "3_month_access"
        else:
            logging.error(f"Could not extract package ID from payload: {payload}")
            # Fallback for old hardcoded packages if no dynamic ID is found
            if "1_month_access" in payload:
                messages_to_add = 100
                package_type = "1_month_access"
            elif "2_months_access" in payload:
                messages_to_add = 200
                package_type = "2_months_access"
            elif "3_months_access" in payload:
                messages_to_add = 250
                package_type = "3_months_access"

    if messages_to_add == 0:
        logging.error(f"No messages to add for successful payment with payload: {payload}")
        await message.answer("Payment received! But there was an issue activating your subscription. Please contact support.")
        return

    current_subscriber_info = get_subscriber_data(user_id)
    current_messages = current_subscriber_info.get('remaining_messages', 0) if current_subscriber_info else 0

    new_total_messages = current_messages + messages_to_add

    update_subscriber_data(user_id, {'remaining_messages': new_total_messages, 'package_type': package_type})
    remove_free_user(user_id)

    await message.answer(
        f"Payment received! You now have {new_total_messages} messages available. Thank you!"
    )
    logging.info(f"User {user_id} successfully subscribed for {new_total_messages} messages. Package: {package_type}")


# --- Main Function ---
async def main():
    logging.info("Starting bot...")
    # Ensure all data files exist, including the new config file
    for file_path in [USERS_DATA_FILE, SUBSCRIBERS_DATA_FILE, USERS_INFO_FILE, CONVERSATIONS_FILE, BANNED_USERS_FILE, PAYMENT_PACKAGES_FILE, CONFIG_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump({}, f)

    # Initialize default config if empty
    current_config = load_bot_config()
    if "MSG_LIMIT_FREE" not in current_config:
        current_config["MSG_LIMIT_FREE"] = 2 # Set initial default if file was empty
        save_bot_config(current_config)

    global MSG_LIMIT_FREE # Update global variable from loaded config
    MSG_LIMIT_FREE = current_config["MSG_LIMIT_FREE"]

    migrate_legacy_data()
    initialize_payment_packages() # Ensure default packages exist

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Bot error: {e}")

if __name__ == "__main__":
    asyncio.run(main())