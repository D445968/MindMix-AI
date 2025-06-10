import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from subject_prompts import subject_prompts
from datetime import datetime
import requests

# ✅ Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
APP_URL = os.getenv("APP_URL") or ""
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def restore_session_from_url():
    qp = st.query_params
    a = qp.get("access_token")
    r = qp.get("refresh_token")

    if a and r and "user" not in st.session_state:
        try:
            supabase.auth.set_session(a, r)
            user = supabase.auth.get_user()
            if user and user.user:
                st.session_state["user"] = user.user
                st.session_state["access_token"] = a
                st.session_state["refresh_token"] = r
                st.experimental_set_query_params()  # Clear query params
                st.rerun()
        except Exception as e:
            st.warning(f"\u7121\u6cd5\u9084\u539f\u767b\u5165\uff1a{e}")

st.set_page_config(page_title="MindMix Redirect", layout="centered")

restore_session_from_url()

# JS redirect removed - now purely Python-based handling
if "user" not in st.session_state:
    st.write("⏳ Redirecting or login failed. Please try logging in again.")
    st.stop()

# After session restoration, move on to main
from app_main import main_app  # assumes your main app logic is in app_main.py

main_app(st.session_state.user)
