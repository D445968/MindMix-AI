import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from subject_prompts import subject_prompts
from datetime import datetime
import requests

# ✅ Fix Supabase Google OAuth redirect (#access_token → ?access_token)
st.markdown("""
<script>
    if (window.location.hash.includes("access_token")) {
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const newUrl = new URL(window.location.href.split('#')[0]);
        for (const [key, value] of hashParams.entries()) {
            newUrl.searchParams.set(key, value);
        }
        // Force reload so Streamlit picks up new query params
        newUrl.searchParams.set("reload", "true");
        window.location.replace(newUrl.toString());
    }
</script>
""", unsafe_allow_html=True)

# ✅ Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
APP_URL = os.getenv("APP_URL") or ""
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ✅ Try to restore session from URL tokens
def restore_session_from_url():
    qp = st.query_params
    if "reload" in qp:
        st.query_params.clear()
        st.rerun()
        return

    a = qp.get("access_token", [None])[0]
    r = qp.get("refresh_token", [None])[0]

    if a and r and "user" not in st.session_state:
        try:
            supabase.auth.set_session(a, r)
            user = supabase.auth.get_user()
            if user and user.user:
                st.session_state["user"] = user.user
                st.session_state["access_token"] = a
                st.session_state["refresh_token"] = r
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.warning(f"無法還原登入：{e}")

def email_login():
    st.subheader("📧 Email 登入")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("密碼", type="password", key="login_pw")
    if st.button("登入"):
        if not email or not password:
            st.warning("請輸入 Email 和密碼")
            return
        try:
            auth = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if auth.user and auth.session:
                st.session_state["user"] = auth.user
                st.session_state["access_token"] = auth.session.access_token
                st.session_state["refresh_token"] = auth.session.refresh_token
                st.rerun()
        except Exception as e:
            st.error(f"登入失敗：{e}")

def email_signup():
    st.subheader("🆕 Email 註冊")
    email = st.text_input("Email", key="signup_email")
    pw = st.text_input("密碼", type="password", key="signup_pw")
    confirm = st.text_input("再次輸入密碼", type="password", key="signup_confirm")
    if st.button("註冊"):
        if not email or not pw or not confirm:
            st.warning("請完整輸入所有欄位")
            return
        if pw != confirm:
            st.warning("密碼不一致")
            return
        try:
            res = supabase.auth.sign_up({"email": email, "password": pw})
            if res.user:
                st.success("註冊成功，請登入")
        except Exception as e:
            st.error(f"註冊失敗：{e}")

def google_login_button():
    if not APP_URL:
        st.error("APP_URL 尚未設定")
        return
    login_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={APP_URL}"
    st.markdown(f"""
        <a href="{login_url}">
            <button style="padding:10px;background:#4285F4;color:white;border:none;border-radius:5px;font-weight:bold;width:100%;">
                使用 Google 登入
            </button>
        </a>
    """, unsafe_allow_html=True)

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

def ask_openrouter(prompt, lang):
    system_prompt = {
        "繁體中文": "你是一位親切、有幫助的中文學習助理，請使用繁體中文回答。",
        "English": "You are a helpful assistant. Please reply only in English."
    }[lang]
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "deepseek/deepseek-chat:free",
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        }
    )
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    return f"❌ 請求失敗（{resp.status_code}）"

def get_today_question_count(uid):
    today = datetime.utcnow().date().isoformat()
    res = admin_supabase.table("history").select("id", count="exact").eq("user_id", uid).gte("created_at", today).execute()
    return res.count or 0

def save_record(uid, subject, task, q, a):
    admin_supabase.table("history").insert({
        "user_id": uid, "subject": subject, "task": task, "question": q, "answer": a,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

def load_records(uid):
    return supabase.table("history").select("*").eq("user_id", uid).order("created_at", desc=True).execute().data

def main_app(user):
    st.sidebar.selectbox("🌐 介面語言", ["繁體中文", "English"], key="ui_lang")
    t = {
        "繁體中文": {
            "title": "📚 MindMix AI",
            "submit": "✏️ 提交",
            "subject": "選擇科目",
            "task": "選擇任務",
            "question": "輸入你的問題",
            "answer": "### ✅ AI 回答：",
            "history": "📜 歷史紀錄",
            "limit": "⚠️ 今日提問已達 80 次上限"
        },
        "English": {
            "title": "📚 MindMix AI",
            "submit": "✏️ Submit",
            "subject": "Choose Subject",
            "task": "Choose Task",
            "question": "Enter Your Question",
            "answer": "### ✅ AI Response:",
            "history": "📜 History",
            "limit": "⚠️ You reached today's limit of 80 questions."
        }
    }[st.session_state.ui_lang]

    st.title(t["title"])
    tabs = st.tabs(["🧠 QA", t["history"]])
    with tabs[0]:
        subject = st.selectbox(t["subject"], list(subject_prompts.keys()))
        task = st.selectbox(t["task"], list(subject_prompts[subject].keys()))
        q = st.text_area(t["question"])
        st.selectbox("選擇 AI 回答語言" if st.session_state.ui_lang == "繁體中文" else "Select AI Response Language", ["繁體中文", "English"], key="ai_lang")

        if st.button(t["submit"]):
            if get_today_question_count(user.id) >= 80:
                st.warning(t["limit"])
            else:
                prompt = subject_prompts[subject][task].format(input=q)
                answer = ask_openrouter(prompt, st.session_state.ai_lang)
                st.markdown(t["answer"])
                st.write(answer)
                save_record(user.id, subject, task, q, answer)

    with tabs[1]:
        st.header(t["history"])
        records = load_records(user.id) or []
        for item in records:
            with st.expander(f"{item['subject']} - {item['task']} - {item['created_at'][:10]}"):
                st.markdown(f"**問題：** {item['question']}")
                st.markdown(f"**回答：** {item['answer']}")

def main():
    
    restore_session_from_url()
    if "user" not in st.session_state:
        if "ui_lang" not in st.session_state:
            st.session_state.ui_lang = "繁體中文"

        st.title("🔐 登入或註冊" if st.session_state.ui_lang == "繁體中文" else "🔐 Login or Sign Up")
        mode = st.radio("", ["登入", "註冊", "Google 登入"] if st.session_state.ui_lang == "繁體中文" else ["Login", "Sign Up", "Google Login"])
        if mode in ["登入", "Login"]:
            email_login()
        elif mode in ["註冊", "Sign Up"]:
            email_signup()
        else:
            google_login_button()
        return


    st.sidebar.success(f"👤 {st.session_state.user.email}")
    if st.sidebar.button("登出" if st.session_state.ui_lang == "繁體中文" else "Logout"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        for k in ["user", "access_token", "refresh_token"]:
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()

    main_app(st.session_state.user)

if __name__ == "__main__":
    main()
