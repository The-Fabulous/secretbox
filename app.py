import streamlit as st

import requests
import pandas as pd
import os
# Настройка вкладки браузера
st.set_page_config(
    page_title="SECRETBOX", 
    layout="wide"
)

# Глобальные стили: центрируем всё, включая таблицы и заголовки
st.markdown("""
    <style>
    /* Центрирование основного контейнера */
    .block-container {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    /* Центрирование заголовков и текста */
    h1, h2, h3, .stMarkdown {
        text-align: center !important;
    }
    /* Центрирование всех таблиц */
    table {
        margin-left: auto !important;
        margin-right: auto !important;
    }
    /* Центрирование кнопок */
    div.stButton {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

# Заголовок страницы
st.markdown("<h1 style='text-align: center;'>☕ SECRETBOX 📦</h1>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📋 Каталог", "📊 Аналитика"])
# ... остальной ваш код ...
with tab1:
    st.header("Просмотр меню")
    try:
        response = requests.get(f"{API_URL}/coffee-shops")
        # Добавим проверку ответа
        if response.status_code == 200:
            shops = response.json().get("shops", [])
            if shops:
                selected_shop = st.selectbox("Выберите кофейню:", shops)
                if selected_shop:
                    # Добавим вывод ошибки, если меню не грузится
                    menu_resp = requests.get(f"{API_URL}/menu/{selected_shop}")
                    if menu_resp.status_code == 200:
                        menu_data = menu_resp.json().get("menu", {})
                        df = pd.DataFrame(list(menu_data.items()), columns=["Напиток", "Цена"])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.error(f"Ошибка загрузки меню: {menu_resp.status_code}")
            else:
                st.warning("Список кофейнь пуст. Проверьте файлы в папке objects.")
        else:
            st.error(f"Сервер вернул ошибку: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Не удалось связаться с сервером: {e}")

with tab2:
    # Заголовок изменен по вашему требованию
    st.header("Сравнение цен")
    if st.button("Запустить полный анализ"):
        # ... остальной код для tab2 ...

        try:
            data = requests.get(f"{API_URL}/analytics/compare").json()
            shops = requests.get(f"{API_URL}/coffee-shops").json().get("shops", [])
            
            if data:
                df = pd.DataFrame(data)
                shop_cols = [c for c in df.columns if c not in ["Напиток", "Разброс"]]
                df['match_count'] = df[shop_cols].notna().sum(axis=1)
                
                # Таблица 1: Абсолютные (5 из 5)
                st.subheader("🟢 Абсолютные совпадения (во всех 5 кофейнях)")
                df_abs = df[df['match_count'] == 5].drop(columns=['match_count'])
                st.dataframe(df_abs, use_container_width=True)
                
                # Таблица 2: Частичные (от 2 до 4)
                st.subheader("🟡 Частичные совпадения (от 2 до 4 кофейнях)")
                df_part = df[(df['match_count'] >= 2) & (df['match_count'] <= 4)].drop(columns=['match_count'])
                st.dataframe(df_part, use_container_width=True)
            else:
                st.info("Данных для анализа недостаточно.")
        except Exception as e:
            st.error(f"Ошибка анализа: {e}")