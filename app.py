import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
from subject_prompts import subject_prompts
from urllib.parse import urlencode

# 載入環境變數
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ---------- 登入／註冊區塊 ----------
def google_login_button():
    redirect_url = "https://mindmix-ai-o2wkozhzbtk38t5dghvfs7.streamlit.app/"  
    params = {
        "provider": "google",
        "redirect_to": redirect_url,
    }
    google_url = f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"
    st.markdown(f"""
    <a href="{google_url}">
        <button style="padding: 0.5em 1em; background-color: #4285F4; color: white; border: none; border-radius: 5px;">
            使用 Google 登入
        </button>
    </a>
    """, unsafe_allow_html=True)

def login():
    st.title("登入")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("密碼", type="password", key="login_password")
    if st.button("登入"):
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if user.user:
                st.session_state.user = user.user
                st.success("登入成功！")
                st.experimental_rerun()
            else:
                st.error("登入失敗，請確認帳號密碼。")
        except Exception as e:
            st.error(f"登入錯誤：{e}")

def signup():
    st.title("註冊")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("密碼", type="password", key="signup_password")
    password_confirm = st.text_input("確認密碼", type="password", key="signup_password_confirm")
    if st.button("註冊"):
        if password != password_confirm:
            st.error("密碼與確認密碼不符。")
            return
        try:
            user = supabase.auth.sign_up({"email": email, "password": password})
            if user.user:
                st.success("註冊成功，請查收驗證信。")
            else:
                st.error("註冊失敗，請稍後再試。")
        except Exception as e:
            st.error(f"註冊錯誤：{e}")

# ---------- 自動登入處理 ----------
def inject_token_rewriter():
    st.markdown("""
    <script>
    const hash = window.location.hash;
    if (hash && hash.includes("access_token")) {
        const query = hash.replace("#", "?");
        const cleanUrl = window.location.origin + window.location.pathname + query;
        window.location.replace(cleanUrl);
    }
    </script>
    """, unsafe_allow_html=True)

def parse_url_tokens():
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    if access_token and refresh_token:
        try:
            user = supabase.auth.set_session(access_token, refresh_token)
            if user.user:
                st.session_state.user = user.user
                st.experimental_rerun()
        except Exception as e:
            st.error(f"⚠️ 自動登入失敗：{e}")

# ---------- 主要功能 ----------
def ask_openrouter(prompt, language="繁體中文"):
    system_prompt = {
        "繁體中文": "你是一個親切、有幫助的中文學習助理，請用繁體中文回答使用者。",
        "English": "You are a helpful and friendly learning assistant. Please reply in English."
    }.get(language, "You are a helpful assistant.")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek/deepseek-chat:free",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"❌ 錯誤：{response.status_code}"

def get_today_question_count(user_id):
    today = datetime.utcnow().date().isoformat()
    result = admin_supabase.table("history").select("id", count="exact").eq("user_id", user_id).gte("created_at", today).execute()
    return result.count or 0

def save_record(table, data):
    try:
        admin_supabase.table(table).insert(data).execute()
    except Exception as e:
        st.error(f"❌ 儲存失敗：{e}")

def load_records(table, user_id):
    try:
        return supabase.table(table).select("*").eq("user_id", user_id).execute().data
    except Exception as e:
        st.error(f"❌ 載入失敗：{e}")
        return []

def main_app(user_id):
    st.title("📚 MindMix AI")
    tabs = st.tabs(["💡 主頁", "📜 提問歷史", "⭐ 收藏題目"])

    with tabs[0]:
        subject = st.selectbox("選擇科目", list(subject_prompts.keys()))
        task = st.selectbox("選擇題型", list(subject_prompts[subject].keys()))
        user_input = st.text_area("輸入題目內容或主題")
        language = st.radio("選擇回答語言", ["繁體中文", "English"], horizontal=True)

        if st.button("✏️ 送出"):
            if get_today_question_count(user_id) >= 8:
                st.warning("⚠️ 今天的提問次數已達上限（8次）。請明天再試！")
            else:
                prompt = subject_prompts[subject][task].format(input=user_input)
                reply = ask_openrouter(prompt, language)
                st.markdown("### ✅ 生成結果：")
                st.write(reply)
                save_record("history", {
                    "user_id": user_id,
                    "subject": subject,
                    "task": task,
                    "question": user_input,
                    "answer": reply,
                    "created_at": datetime.utcnow().isoformat()
                })
                if st.button("⭐ 收藏此題"):
                    save_record("favorites", {
                        "user_id": user_id,
                        "subject": subject,
                        "task": task,
                        "question": user_input,
                        "answer": reply,
                        "created_at": datetime.utcnow().isoformat()
                    })
                    st.success("已加入收藏！")

    with tabs[1]:
        st.header("📜 提問歷史")
        for i, item in enumerate(reversed(load_records("history", user_id))):
            with st.expander(f"{item['subject']} - {item['task']} - 第{i+1}題"):
                st.markdown(f"**問題：** {item['question']}")
                st.markdown(f"**答案：** {item['answer']}")

    with tabs[2]:
        st.header("⭐ 我的收藏")
        for i, item in enumerate(reversed(load_records("favorites", user_id))):
            with st.expander(f"{item['subject']} - {item['task']} - 收藏第{i+1}題"):
                st.markdown(f"**問題：** {item['question']}")
                st.markdown(f"**答案：** {item['answer']}")
                if st.button(f"❌ 取消收藏 {i+1}", key=f"unfav_{item['id']}"):
                    admin_supabase.table("favorites").delete().eq("id", item['id']).execute()
                    st.experimental_rerun()

# ---------- 主入口 ----------
def main():
    inject_token_rewriter()
    parse_url_tokens()

    if "user" not in st.session_state:
        st.title("🔐 請先登入")
        method = st.radio("選擇登入方式：", ["Email 登入", "Email 註冊", "Google 登入"])

        if method == "Email 登入":
            login()
        elif method == "Email 註冊":
            signup()
        elif method == "Google 登入":
            google_login_button()
    else:
        user = st.session_state.user
        st.sidebar.write(f"👋 歡迎 {user.email}")
        if st.sidebar.button("登出"):
            supabase.auth.sign_out()
            del st.session_state["user"]
            st.experimental_rerun()
        main_app(user.id)

if __name__ == "__main__":
    main()
