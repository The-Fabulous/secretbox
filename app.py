import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="SECRETBOX", layout="wide")

st.markdown(
    """
<style>
.block-container { display: flex; flex-direction: column; align-items: center; }
h1, h2, h3, .stMarkdown { text-align: center !important; }
table { margin-left: auto !important; margin-right: auto !important; }
div.stButton { text-align: center; }
</style>
""",
    unsafe_allow_html=True,
)

# Address of the backend. On Render this comes from the API_URL environment variable.
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")

# Free Render servers can take ~50 seconds to wake up, so wait long enough.
TIMEOUT = 90

if "token" not in st.session_state:
    st.session_state.token = None


def error_text(resp):
    """Pull the readable 'detail' message out of an error response."""
    try:
        return resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text


def api_get(path):
    """GET request that sends the login token, as the backend requires."""
    resp = requests.get(
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        timeout=TIMEOUT,
    )
    if resp.status_code == 401:
        # Token expired or invalid: forget it so the login form shows again.
        st.session_state.token = None
        st.warning("Сессия истекла. Обновите страницу и войдите снова.")
        st.stop()
    return resp


def show_login():
    st.header("Вход")
    login_tab, register_tab = st.tabs(["Войти", "Регистрация"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Имя пользователя")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти")
        if submitted:
            try:
                resp = requests.post(
                    f"{API_URL}/login",
                    json={"username": username, "password": password},
                    timeout=TIMEOUT,
                )
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["token"]
                    st.rerun()
                else:
                    st.error(error_text(resp))
            except requests.RequestException as e:
                st.error(f"Не удалось связаться с сервером: {e}")

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input("Новое имя пользователя")
            new_password = st.text_input("Новый пароль", type="password")
            registered = st.form_submit_button("Создать аккаунт")
        if registered:
            try:
                resp = requests.post(
                    f"{API_URL}/register",
                    json={"username": new_username, "password": new_password},
                    timeout=TIMEOUT,
                )
                if resp.status_code == 200:
                    st.success("Аккаунт создан. Теперь войдите на вкладке «Войти».")
                else:
                    st.error(error_text(resp))
            except requests.RequestException as e:
                st.error(f"Не удалось связаться с сервером: {e}")


st.markdown(
    "<h1 style='text-align: center;'>☕ SECRETBOX 📦</h1>", unsafe_allow_html=True
)

# Not logged in yet: show only the login form and stop here.
if not st.session_state.token:
    show_login()
    st.stop()

if st.button("Выйти"):
    st.session_state.token = None
    st.rerun()

tab1, tab2 = st.tabs(["📋 Каталог", "📊 Аналитика"])

with tab1:
    st.header("Просмотр меню")
    try:
        response = api_get("/coffee-shops")
        if response.status_code == 200:
            shops = response.json().get("shops", [])
            if shops:
                selected_shop = st.selectbox("Выберите кофейню:", shops)
                if selected_shop:
                    menu_resp = api_get(f"/menu/{selected_shop}")
                    if menu_resp.status_code == 200:
                        menu_data = menu_resp.json().get("menu", {})
                        df = pd.DataFrame(
                            list(menu_data.items()), columns=["Напиток", "Цена"]
                        )
                        st.dataframe(df)
                    else:
                        st.error(f"Ошибка загрузки меню: {menu_resp.status_code}")
            else:
                st.warning("Список кофейнь пуст. Проверьте файлы в папке objects.")
        else:
            st.error(f"Сервер вернул ошибку: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        st.error(f"Не удалось связаться с сервером: {e}")

with tab2:
    st.header("Сравнение цен")
    if st.button("Запустить полный анализ"):
        try:
            resp = api_get("/analytics/compare")
            if resp.status_code != 200:
                st.error(f"Ошибка анализа: {resp.status_code} - {resp.text}")
            else:
                data = resp.json()
                if data:
                    df = pd.DataFrame(data)
                    # Every column except these three is one coffee shop's price.
                    shop_cols = [
                        c for c in df.columns if c not in ["Напиток", "Объём", "Разброс"]
                    ]
                    total = len(shop_cols)
                    df["match_count"] = df[shop_cols].notna().sum(axis=1)

                    st.subheader(f"🟢 Абсолютные совпадения (во всех {total} кофейнях)")
                    df_abs = df[df["match_count"] == total].drop(columns=["match_count"])
                    st.dataframe(df_abs)

                    st.subheader(f"🟡 Частичные совпадения (от 2 до {total - 1} кофеен)")
                    df_part = df[
                        (df["match_count"] >= 2) & (df["match_count"] < total)
                    ].drop(columns=["match_count"])
                    st.dataframe(df_part)
                else:
                    st.info("Данных для анализа недостаточно.")
        except requests.RequestException as e:
            st.error(f"Ошибка анализа: {e}")