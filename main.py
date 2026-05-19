import os
import time
import json
import base64
import threading
import requests
import pyrebase
from io import BytesIO
from kivy import *
import kivy
from kivymd import *
import kivymd

# --- Kivy & KivyMD Imports ---
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from plyer import filechooser

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
AI_NAME        = "Mwilima AI"
AI_PERSONA     = "You are Mwilima, a warm and supportive AI companion. Be concise, helpful, and friendly."
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE    = "https://openrouter.ai/api/v1/chat/completions"
VISION_MODEL = "openai/gpt-4o"
TEXT_MODEL   = "openai/gpt-3.5-turbo"

FIREBASE_CONFIG = {
    "apiKey":            "AIzaSyDapwQ97fbWO19oopUs9LOs5eUn6FCo1kM",
    "authDomain":        "mwilima.firebaseapp.com",
    "databaseURL":       "https://mwilima-default-rtdb.firebaseio.com",
    "projectId":         "mwilima",
    "storageBucket":     "mwilima.firebasestorage.app",
    "messagingSenderId": "363033516615",
    "appId":             "1:363033516615:web:7ed914f483fbe6029baf62",
    "measurementId":     "G-SV9QBW35LC"
}

# ─────────────────────────────────────────────
#  FIREBASE INIT & HELPERS
# ─────────────────────────────────────────────
firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
auth_svc = firebase.auth()
db       = firebase.database()

def openrouter_chat(messages: list, model: str, max_tokens: int = 600) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://mwilima.app",
        "X-Title":       "Mwilima AI",
    }
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(OPENROUTER_BASE, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        print(f"API Error ({resp.status_code}): {resp.text}")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def encode_image_b64(path: str) -> tuple[str, str]:
    with open(path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("utf-8")
    ext = path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
    return b64, mime_map.get(ext, "image/jpeg")

# ─────────────────────────────────────────────
#  KIVY UI LAYOUT (KV Language)
# ─────────────────────────────────────────────
KV = '''
<ChatBubble>:
    orientation: "vertical"
    adaptive_height: True
    padding: dp(10)
    spacing: dp(5)

    MDBoxLayout:
        id: bubble_card
        adaptive_height: True
        radius: [dp(15), dp(15), dp(15), dp(15)]
        padding: dp(15)
        md_bg_color: root.bg_color

        MDLabel:
            id: msg_label
            text: root.text
            theme_text_color: "Custom"
            text_color: root.text_color
            markup: True
            adaptive_height: True
            font_name: "Roboto"

MDScreenManager:
    id: screen_manager

    # --- AUTH SCREEN ---
    MDScreen:
        name: "auth"
        md_bg_color: 0.05, 0.05, 0.07, 1  # BG_DARK

        MDBoxLayout:
            orientation: "vertical"
            spacing: dp(20)
            padding: dp(40)
            pos_hint: {"center_x": 0.5, "center_y": 0.5}
            adaptive_height: True

            MDLabel:
                text: "✦ MWILIMA"
                halign: "center"
                font_style: "H4"
                theme_text_color: "Custom"
                text_color: 167/255, 139/255, 250/255, 1  # ACCENT
                bold: True

            MDLabel:
                text: "Your intelligent companion"
                halign: "center"
                theme_text_color: "Custom"
                text_color: 100/255, 116/255, 139/255, 1  # MUTED

            MDTextField:
                id: email_input
                hint_text: "Email address"
                mode: "rectangle"
                text_color_normal: 1, 1, 1, 1

            MDTextField:
                id: pass_input
                hint_text: "Password"
                mode: "rectangle"
                password: True
                text_color_normal: 1, 1, 1, 1

            MDRaisedButton:
                id: login_btn
                text: "LOG IN"
                pos_hint: {"center_x": 0.5}
                size_hint_x: 1
                md_bg_color: 167/255, 139/255, 250/255, 1
                text_color: 0.05, 0.05, 0.07, 1
                on_release: app.start_auth("login")

            MDFlatButton:
                text: "Create new account →"
                pos_hint: {"center_x": 0.5}
                theme_text_color: "Custom"
                text_color: 100/255, 116/255, 139/255, 1
                on_release: app.start_auth("signup")

    # --- CHAT SCREEN ---
    MDScreen:
        name: "chat"
        MDNavigationLayout:
            MDScreenManager:
                MDScreen:
                    MDBoxLayout:
                        orientation: "vertical"
                        md_bg_color: 0.05, 0.05, 0.07, 1

                        # Top Bar
                        MDTopAppBar:
                            title: app.ai_status
                            left_action_items: [["menu", lambda x: nav_drawer.set_state("open")]]
                            right_action_items: [["trash-can", lambda x: app.clear_database()], ["refresh", lambda x: app.clear_local_ui()]]
                            md_bg_color: 0.09, 0.09, 0.12, 1 # BG_CARD
                            specific_text_color: 52/255, 211/255, 153/255, 1 if app.ai_status == "● Mwilima AI" else (1, 0, 0, 1)

                        # Chat Area
                        MDScrollView:
                            id: chat_scroll
                            MDBoxLayout:
                                id: chat_box
                                orientation: "vertical"
                                adaptive_height: True
                                padding: dp(10)
                                spacing: dp(10)

                        # Image Preview Strip
                        MDBoxLayout:
                            id: preview_strip
                            size_hint_y: None
                            height: dp(0)
                            md_bg_color: 0.09, 0.09, 0.12, 1
                            padding: dp(5)
                            opacity: 0

                            FitImage:
                                id: preview_img
                                size_hint_x: None
                                width: dp(50)
                                radius: [dp(5)]
                            MDLabel:
                                id: preview_name
                                text: ""
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                                padding_x: dp(10)
                            MDIconButton:
                                icon: "close"
                                theme_text_color: "Custom"
                                text_color: 1, 0, 0, 1
                                on_release: app.clear_image_selection()

                        # Input Bar
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(68)
                            md_bg_color: 0.09, 0.09, 0.12, 1
                            padding: dp(10)
                            spacing: dp(10)

                            MDIconButton:
                                icon: "camera"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                                on_release: app.select_image()

                            MDTextField:
                                id: msg_entry
                                hint_text: "Type a message..."
                                mode: "round"
                                fill_color_normal: 0.12, 0.16, 0.23, 1
                                text_color_normal: 1, 1, 1, 1
                                on_text_validate: app.start_chat()

                            MDFillRoundFlatButton:
                                text: "Send"
                                md_bg_color: 167/255, 139/255, 250/255, 1
                                text_color: 0, 0, 0, 1
                                on_release: app.start_chat()

            # Sidebar (Navigation Drawer)
            MDNavigationDrawer:
                id: nav_drawer
                md_bg_color: 0.07, 0.07, 0.1, 1

                MDBoxLayout:
                    orientation: "vertical"
                    padding: dp(10)
                    spacing: dp(10)

                    MDLabel:
                        text: "Saved Chats"
                        font_style: "H6"
                        theme_text_color: "Custom"
                        text_color: 167/255, 139/255, 250/255, 1
                        adaptive_height: True

                    MDRaisedButton:
                        text: "＋ New Conversation"
                        size_hint_x: 1
                        md_bg_color: 167/255, 139/255, 250/255, 1
                        text_color: 0,0,0,1
                        on_release: app.start_new_session()

                    MDScrollView:
                        MDList:
                            id: session_list
'''

# ─────────────────────────────────────────────
#  WIDGET CLASSES
# ─────────────────────────────────────────────
class ChatBubble(MDBoxLayout):
    text = kivy.properties.StringProperty()
    bg_color = kivy.properties.ColorProperty([0.12, 0.16, 0.23, 1])
    text_color = kivy.properties.ColorProperty([1, 1, 1, 1])

# ─────────────────────────────────────────────
#  MAIN APPLICATION CLASS
# ─────────────────────────────────────────────
class MwilimaApp(MDApp):
    ai_status = kivy.properties.StringProperty(f"● {AI_NAME}")

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        self.user_id = None
        self.current_session_id = None
        self.history = []
        self.selected_image_path = None
        self.is_thinking = False
        self.current_streaming_bubble = None
        self.dialog = None
        return Builder.load_string(KV)

    def show_toast(self, message):
        Clock.schedule_once(lambda dt: MDSnackbar(MDLabel(text=message, theme_text_color="Custom", text_color=(1,1,1,1))).open())

    # ── MEMORY & FIREBASE ──
    def _save_memory(self, memory_dict: dict):
        db.child("users").child(self.user_id).child("profile").set(memory_dict)

    def _get_memory(self) -> dict:
        data = db.child("users").child(self.user_id).child("profile").get().val()
        return data if data else {}

    def _get_dynamic_system_prompt(self) -> str:
        memory = self._get_memory()
        memory_str = json.dumps(memory, indent=2)
        return (f"{AI_PERSONA}\n\n"
                f"CURRENT USER PROFILE (Remember these facts):\n{memory_str}\n\n"
                "INSTRUCTION: If the user shares new personal information, update your knowledge by outputting JSON inside <memory> tags: "
                "<memory>{\"fact_name\": \"fact_value\"}</memory>.")

    # ── AUTHENTICATION ──
    def start_auth(self, mode):
        email = self.root.ids.email_input.text.strip()
        pwd = self.root.ids.pass_input.text.strip()
        if not email or not pwd:
            self.show_toast("Please enter email and password.")
            return
        self.root.ids.login_btn.text = "Connecting..."
        self.root.ids.login_btn.disabled = True
        threading.Thread(target=self._run_auth, args=(mode, email, pwd), daemon=True).start()

    def _run_auth(self, mode, email, pwd):
        try:
            if mode == "login":
                u = auth_svc.sign_in_with_email_and_password(email, pwd)
            else:
                u = auth_svc.create_user_with_email_and_password(email, pwd)
            self.user_id = u["localId"]
            Clock.schedule_once(self._finish_auth)
        except Exception as e:
            def reset(dt):
                self.show_toast("Authentication Failed. Check credentials.")
                self.root.ids.login_btn.text = "LOG IN"
                self.root.ids.login_btn.disabled = False
            Clock.schedule_once(reset)

    def _finish_auth(self, dt):
        self.root.current = "chat"
        self.start_new_session()
        threading.Thread(target=self._load_sidebar_sessions, daemon=True).start()

    # ── SESSION MANAGEMENT ──
    def start_new_session(self):
        self.current_session_id = f"chat_{int(time.time())}"
        self.history = []
        self.clear_local_ui()
        self.clear_image_selection()
        self.write_screen("System", "New conversation started. Say hello!", sender="sys")
        self.root.ids.nav_drawer.set_state("close")

    def _load_sidebar_sessions(self):
        try:
            data = db.child("users").child(self.user_id).child("sessions").get().val()
            def update_ui(dt):
                self.root.ids.session_list.clear_widgets()
                if not data: return
                for sid in sorted(data.keys(), reverse=True):
                    msgs = data[sid].get("messages")
                    title = "Empty thread"
                    if msgs:
                        first = list(msgs.values())[0]
                        title = (first.get("q") or "Image sent")[:26] + "..."
                    # Create button using explicit loop variable binding
                    btn = MDFlatButton(
                        text=f"💬 {title}",
                        theme_text_color="Custom", text_color=(1,1,1,1),
                        size_hint_x=1,
                        on_release=lambda x, s=sid: self._switch_session(s)
                    )
                    self.root.ids.session_list.add_widget(btn)
            Clock.schedule_once(update_ui)
        except Exception as e:
            pass

    def _switch_session(self, session_id):
        self.current_session_id = session_id
        self.history = []
        self.clear_local_ui()
        self.clear_image_selection()
        self.root.ids.nav_drawer.set_state("close")
        self.ai_status = "● Loading..."
        threading.Thread(target=self._load_session_messages, args=(session_id,), daemon=True).start()

    def _load_session_messages(self, session_id):
        try:
            nodes = db.child("users").child(self.user_id).child("sessions").child(session_id).child("messages").get().val()
            if nodes:
                def render_msgs(dt):
                    for node in nodes.values():
                        prefix = "📸 [Image] " if node.get("has_image") else ""
                        self.history.extend([
                            {"role": "user", "content": node["q"]},
                            {"role": "assistant", "content": node["a"]},
                        ])
                        self.write_screen("You", f"{prefix}{node['q']}", "user")
                        self.write_screen(AI_NAME, node["a"], "ai")
                    self.ai_status = f"● {AI_NAME}"
                Clock.schedule_once(render_msgs)
            else:
                Clock.schedule_once(lambda dt: setattr(self, 'ai_status', f"● {AI_NAME}"))
        except Exception:
            Clock.schedule_once(lambda dt: setattr(self, 'ai_status', "● Offline"))

    # ── UI HELPERS ──
    def write_screen(self, sender: str, text: str, sender_type: str):
        # Configure Colors based on sender
        bg = [0.12, 0.16, 0.23, 1] if sender_type == "user" else [0.09, 0.09, 0.12, 1]
        if sender_type == "sys":
            bg = [0.2, 0.1, 0.1, 1]
            text = f"[b]{sender}:[/b]\n{text}"
        else:
            color_hex = "38BDF8" if sender_type == "user" else "A78BFA"
            text = f"[color={color_hex}][b]{sender}[/b][/color]\n{text}"

        bubble = ChatBubble(text=text, bg_color=bg)

        # Align: User right, AI/Sys left
        if sender_type == "user":
            bubble.pos_hint = {"right": 1}
            bubble.size_hint_x = 0.85
        else:
            bubble.pos_hint = {"left": 1}
            bubble.size_hint_x = 0.95

        self.root.ids.chat_box.add_widget(bubble)
        self.scroll_to_bottom()

    def _stream_text(self, text: str):
        # Create empty AI bubble
        bubble = ChatBubble(text=f"[color=A78BFA][b]{AI_NAME}[/b][/color]\n", bg_color=[0.09, 0.09, 0.12, 1], size_hint_x=0.95, pos_hint={"left": 1})
        self.root.ids.chat_box.add_widget(bubble)
        self.current_streaming_bubble = bubble
        words = text.split(" ")

        def add_word(dt, i=0):
            if i < len(words):
                self.current_streaming_bubble.ids.msg_label.text += words[i] + " "
                self.scroll_to_bottom()
                Clock.schedule_once(lambda d: add_word(d, i + 1), 0.02) # Streaming speed
        Clock.schedule_once(add_word)

    def scroll_to_bottom(self):
        Clock.schedule_once(lambda dt: setattr(self.root.ids.chat_scroll, 'scroll_y', 0), 0.1)

    def clear_local_ui(self):
        self.root.ids.chat_box.clear_widgets()

    def clear_database(self):
        try:
            db.child("users").child(self.user_id).child("sessions").remove()
            self.start_new_session()
            threading.Thread(target=self._load_sidebar_sessions, daemon=True).start()
            self.show_toast("Cloud data wiped successfully.")
        except Exception:
            self.show_toast("Error connecting to cloud.")

    # ── IMAGE HANDLING (Plyer for Android Compatibility) ──
    def select_image(self):
        try:
            filechooser.open_file(on_selection=self._on_file_selection, filters=[("Images", "*.png", "*.jpg", "*.jpeg", "*.webp")])
        except Exception as e:
            self.show_toast(f"File picker not supported: {e}")

    def _on_file_selection(self, selection):
        if selection:
            self.selected_image_path = selection[0]
            Clock.schedule_once(self._update_image_preview)

    def _update_image_preview(self, dt):
        self.root.ids.preview_strip.height = dp(60)
        self.root.ids.preview_strip.opacity = 1
        self.root.ids.preview_img.source = self.selected_image_path
        self.root.ids.preview_name.text = self.selected_image_path.split("/")[-1][:20] + "..."

    def clear_image_selection(self):
        self.selected_image_path = None
        self.root.ids.preview_strip.height = dp(0)
        self.root.ids.preview_strip.opacity = 0
        self.root.ids.preview_img.source = ""

    # ── CHAT EXECUTION ──
    def start_chat(self):
        msg = self.root.ids.msg_entry.text.strip()
        img_path = self.selected_image_path
        if not msg and not img_path:
            return

        display = f"📸 [Image attached] {msg}" if img_path else msg
        self.write_screen("You", display, "user")
        self.root.ids.msg_entry.text = ""
        self.ai_status = f"● Thinking..."
        self.is_thinking = True
        threading.Thread(target=self._run_ai, args=(msg, img_path), daemon=True).start()
        self.clear_image_selection()

    def _run_ai(self, msg: str, img_path: str = None):
        try:
            if img_path:
                b64, mime = encode_image_b64(img_path)
                user_content = [{"type": "text", "text": msg}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]
                messages = [{"role": "system", "content": self._get_dynamic_system_prompt()}, *[{"role": t["role"], "content": t["content"]} for t in self.history], {"role": "user", "content": user_content}]
                reply = openrouter_chat(messages, model=VISION_MODEL, max_tokens=700)
            else:
                messages = [{"role": "system", "content": self._get_dynamic_system_prompt()}, *self.history, {"role": "user", "content": msg}]
                reply = openrouter_chat(messages, model=TEXT_MODEL, max_tokens=600)

            # Memory Parsing
            import re
            match = re.search(r"<memory>(.*?)</memory>", reply)
            if match:
                try:
                    new_facts = json.loads(match.group(1))
                    current_mem = self._get_memory()
                    current_mem.update(new_facts)
                    self._save_memory(current_mem)
                    reply = reply.replace(match.group(0), "").strip()
                except Exception as e:
                    print(f"Memory Parse Error: {e}")

            # Save to Firebase
            payload = {"q": msg or "(image only)", "a": reply, "timestamp": int(time.time()), "has_image": bool(img_path)}
            db.child("users").child(self.user_id).child("sessions").child(self.current_session_id).child("messages").push(payload)
            self.history.extend([{"role": "user", "content": msg}, {"role": "assistant", "content": reply}])
            Clock.schedule_once(lambda dt: self._stream_text(reply))
            threading.Thread(target=self._load_sidebar_sessions, daemon=True).start()

        except Exception as err:
            Clock.schedule_once(lambda dt: self.write_screen("System", f"AI Error: {err}", "sys"))
        finally:
            self.is_thinking = False
            Clock.schedule_once(lambda dt: setattr(self, 'ai_status', f"● {AI_NAME}"))

if __name__ == "__main__":
    MwilimaApp().run()