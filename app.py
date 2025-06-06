import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import requests
from datetime import datetime
from subject_prompts import subject_prompts  # 你自己的題目模板

# 載入環境變數
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# OpenRouter API 請求
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

# 取得今日提問次數
def get_today_question_count(user_id):
    today = datetime.utcnow().date().isoformat()
    result = admin_supabase.table("history").select("id", count="exact").eq("user_id", user_id).gte("created_at", today).execute()
    return result.count or 0

# 儲存紀錄或收藏
def save_record(table, data):
    try:
        admin_supabase.table(table).insert(data).execute()
    except Exception as e:
        st.error(f"❌ 儲存失敗：{e}")

# 載入使用者資料
def load_records(table, user_id):
    try:
        return supabase.table(table).select("*").eq("user_id", user_id).execute().data
    except Exception as e:
        st.error(f"❌ 載入失敗：{e}")
        return []

# 登入功能（Email + Password）
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

# 註冊功能
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

# Magic Link 登入功能（透過郵件發送登入連結）
def magic_link_login():
    st.title("Magic Link 登入")
    email = st.text_input("輸入你的 Email，系統會發送登入連結")
    if st.button("發送登入連結"):
        try:
            response = supabase.auth.sign_in_with_oauth({"email": email})
            # supabase-python 目前沒有直接支援 magic link 發送的專用方法，我們改用 REST API 或使用 signInWithOtp
            res = supabase.auth.api.sign_in_with_otp(email=email)
            if res.user:
                st.success("登入連結已發送到你的 Email，請查收。")
            else:
                st.error("發送失敗，請確認 Email 是否正確。")
        except Exception as e:
            st.error(f"發送失敗：{e}")

# 主功能頁面
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
        st.header("⭐ 我的收藏題目")
        for i, item in enumerate(reversed(load_records("favorites", user_id))):
            with st.expander(f"{item['subject']} - {item['task']} - 收藏第{i+1}題"):
                st.markdown(f"**問題：** {item['question']}")
                st.markdown(f"**答案：** {item['answer']}")
                if st.button(f"❌ 取消收藏 {i+1}", key=f"unfav_{item['id']}"):
                    admin_supabase.table("favorites").delete().eq("id", item['id']).execute()
                    st.experimental_rerun()

# 主入口
def main():
    if "user" not in st.session_state:
        menu = st.sidebar.selectbox("選擇", ["登入", "註冊", "Magic Link 登入"])
        if menu == "登入":
            login()
        elif menu == "註冊":
            signup()
        else:
            magic_link_login()
    else:
        user = st.session_state.user
        st.sidebar.write(f"歡迎，{user.email}")
        if st.sidebar.button("登出"):
            supabase.auth.sign_out()
            del st.session_state["user"]
            st.experimental_rerun()
        main_app(user.id)

if __name__ == "__main__":
    main()
