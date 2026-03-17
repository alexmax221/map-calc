import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os

CONFIG_FILE = "config.json"
SAVED_CALCS_FILE = "saved_calculations.json"

# --- ТЕКСТЫ СПРАВОК ---
HELP_TEXTS = {
    "wordstat": "Общий объем поисковых запросов в месяц по данной нише в выбранной локации (город/район). Берется из Яндекс Wordstat.",
    "rating": "Рейтинг напрямую влияет на доверие и конверсию. При низком рейтинге (< 4.3) пользователи реже совершают звонки и строят маршруты.",
    "ctr": "CTR (Click-Through Rate) — процент пользователей, которые открыли вашу карточку после того, как увидели её в результатах поиска.",
    "conv_map": "Процент пользователей, которые нажали кнопку 'Построить маршрут' после открытия карточки.",
    "conv_call": "Процент пользователей, которые нажали на номер телефона в карточке (лиды на звонок).",
    "conv_site": "Процент пользователей, которые перешли на ваш сайт из карточки Карт.",
    "conv_sale": "Процент реальных покупок/визитов от общего количества обращений (звонки + маршруты + сайт).",
    "avg_check": "Средняя сумма одной покупки/услуги в данной нише для Москвы."
}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ---

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "niches": {
                "Стоматология (Мск)": {"ctr_before": 0.015, "ctr_after": 0.12, "conv_map": 0.12, "conv_call": 0.22, "conv_site": 0.12, "avg_check": 15000, "conv_sale": 0.28},
            },
            "rating_coeffs": {"4.8": 1.3, "4.3": 1.0, "3.8": 0.7, "default": 0.4}
        }
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def load_saved_calculations():
    if not os.path.exists(SAVED_CALCS_FILE):
        return {}
    with open(SAVED_CALCS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_calculation(name, data):
    saved = load_saved_calculations()
    saved[name] = data
    with open(SAVED_CALCS_FILE, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=4, ensure_ascii=False)

def delete_calculation(name):
    saved = load_saved_calculations()
    if name in saved:
        del saved[name]
        with open(SAVED_CALCS_FILE, "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=4, ensure_ascii=False)
        return True
    return False

# --- ИНИЦИАЛИЗАЦИЯ ---

st.set_page_config(page_title="Яндекс Карты: Прогноз 2025 (Мск)", layout="wide")
config = load_config()
NICHE_OPTIONS = ["--- Пользовательский ---"] + list(config["niches"].keys())

# Инициализация session_state
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    first_niche = list(config["niches"].keys())[0]
    n_data = config["niches"][first_niche]
    
    st.session_state.niche_selector = first_niche
    st.session_state.wordstat_demand = 10000
    st.session_state.current_rating = 4.0
    st.session_state.ctr_before_in = n_data['ctr_before'] * 100
    st.session_state.ctr_after_in = n_data['ctr_after'] * 100
    st.session_state.conv_map_in = n_data['conv_map'] * 100
    st.session_state.conv_call_in = n_data['conv_call'] * 100
    st.session_state.conv_site_in = n_data['conv_site'] * 100
    st.session_state.conv_sale_in = n_data.get('conv_sale', 0.3) * 100
    st.session_state.avg_check_in = n_data['avg_check']

# --- ИНТЕРФЕЙС ---

tab1, tab2, tab3 = st.tabs(["📊 Калькулятор прогноза", "⚙️ Настройки бенчмарков", "📂 Сохраненные расчеты"])

with tab1:
    st.title("🚀 Калькулятор роста трафика на Яндекс Картах (Москва)")
    st.write("Инструмент экспертной оценки потенциала локации на основе отраслевых бенчмарков 2024-2025.")
    
    # --- БОКОВАЯ ПАНЕЛЬ ---
    st.sidebar.header("Вводные данные")
    
    # --- ОБРАБОТЧИКИ ---
    def on_niche_change():
        n_name = st.session_state.niche_selector
        if n_name == "--- Пользовательский ---":
            return
            
        n_data = config["niches"][n_name]
        st.session_state.ctr_before_in = n_data['ctr_before'] * 100
        st.session_state.ctr_after_in = n_data['ctr_after'] * 100
        st.session_state.conv_map_in = n_data['conv_map'] * 100
        st.session_state.conv_call_in = n_data['conv_call'] * 100
        st.session_state.conv_site_in = n_data['conv_site'] * 100
        st.session_state.conv_sale_in = n_data.get('conv_sale', 0.3) * 100
        st.session_state.avg_check_in = n_data['avg_check']

    def on_load_calculation():
        load_name = st.session_state.load_selector
        if not load_name:
            return
        data = load_saved_calculations().get(load_name)
        if data:
            st.session_state.wordstat_demand = data['wordstat_demand']
            st.session_state.current_rating = data['current_rating']
            st.session_state.ctr_before_in = data['ctr_before']
            st.session_state.ctr_after_in = data['ctr_after']
            st.session_state.conv_map_in = data['conv_map']
            st.session_state.conv_call_in = data['conv_call']
            st.session_state.conv_site_in = data['conv_site']
            st.session_state.conv_sale_in = data['conv_sale']
            st.session_state.avg_check_in = data['avg_check']
            
            # Устанавливаем пресет
            saved_niche = data.get('niche', "--- Пользовательский ---")
            if saved_niche in NICHE_OPTIONS:
                st.session_state.niche_selector = saved_niche
            else:
                st.session_state.niche_selector = "--- Пользовательский ---"
                
            st.session_state.load_selector = ""
            st.sidebar.success(f"Расчет '{load_name}' загружен!")

    # Селектор ниши
    st.sidebar.selectbox(
        "Ниша бизнеса (пресет):", 
        NICHE_OPTIONS,
        key="niche_selector",
        on_change=on_niche_change
    )
    
    st.sidebar.number_input("Спрос в локации (чел/мес):", min_value=0, step=500, key="wordstat_demand")
    st.sidebar.slider("Текущий рейтинг в Картах:", 1.0, 5.0, 0.1, key="current_rating")
    
    st.sidebar.divider()
    st.sidebar.subheader("Настройка коэффициентов")
    
    c_col1, c_col2 = st.sidebar.columns(2)
    with c_col1:
        st.number_input("CTR до (%)", format="%.2f", key="ctr_before_in")
        st.number_input("CTR после (%)", format="%.2f", key="ctr_after_in")
        st.number_input("Конв. в маршрут (%)", format="%.2f", key="conv_map_in")
    with c_col2:
        st.number_input("Конв. в звонок (%)", format="%.2f", key="conv_call_in")
        st.number_input("Конв. на сайт (%)", format="%.2f", key="conv_site_in")
        st.number_input("Конв. в продажу (%)", format="%.2f", key="conv_sale_in")
    
    st.sidebar.number_input("Средний чек (руб)", step=500, key="avg_check_in")

    # --- ЗАГРУЗКА И СОХРАНЕНИЕ ---
    st.sidebar.divider()
    
    saved_calcs = load_saved_calculations()
    st.sidebar.selectbox(
        "Загрузить расчет:",
        [""] + list(saved_calcs.keys()),
        key="load_selector",
        on_change=on_load_calculation
    )

    save_name = st.sidebar.text_input("Название для сохранения:")
    if st.sidebar.button("💾 Сохранить текущий расчет"):
        if save_name:
            calc_data = {
                "niche": st.session_state.niche_selector,
                "wordstat_demand": st.session_state.wordstat_demand,
                "current_rating": st.session_state.current_rating,
                "ctr_before": st.session_state.ctr_before_in,
                "ctr_after": st.session_state.ctr_after_in,
                "conv_map": st.session_state.conv_map_in,
                "conv_call": st.session_state.conv_call_in,
                "conv_site": st.session_state.conv_site_in,
                "conv_sale": st.session_state.conv_sale_in,
                "avg_check": st.session_state.avg_check_in
            }
            save_calculation(save_name, calc_data)
            st.sidebar.success("✅ Сохранено!")
        else:
            st.sidebar.error("Введите название расчета!")

    # --- ЛОГИКА РАСЧЕТА ---
    rc = config["rating_coeffs"]
    r_coeff_before = rc.get("4.8") if st.session_state.current_rating >= 4.8 else (rc.get("4.3") if st.session_state.current_rating >= 4.3 else (rc.get("3.8") if st.session_state.current_rating >= 3.8 else rc.get("default")))
    r_coeff_after = rc.get("4.8")

    def calculate_metrics(ctr, r_coeff, conv_m, conv_c, conv_s, conv_sl, avg_c):
        views = int(st.session_state.wordstat_demand * (ctr / 100))
        maps = int(views * (conv_m / 100) * r_coeff)
        calls = int(views * (conv_c / 100) * r_coeff)
        site = int(views * (conv_s / 100) * r_coeff)
        total_leads = maps + calls + site
        sales = int(total_leads * (conv_sl / 100))
        revenue = int(sales * avg_c)
        return [views, maps, calls, site, total_leads, revenue, sales]

    before = calculate_metrics(st.session_state.ctr_before_in, r_coeff_before, st.session_state.conv_map_in, st.session_state.conv_call_in, st.session_state.conv_site_in, st.session_state.conv_sale_in, st.session_state.avg_check_in)
    after = calculate_metrics(st.session_state.ctr_after_in, r_coeff_after, st.session_state.conv_map_in, st.session_state.conv_call_in, st.session_state.conv_site_in, st.session_state.conv_sale_in, st.session_state.avg_check_in)

    metrics_labels = ['Просмотры', 'Маршруты', 'Звонки', 'Сайт']
    fig = go.Figure(data=[go.Bar(name='Текущее состояние', x=metrics_labels, y=before[:4], marker_color='#E0E0E0'), go.Bar(name='После продвижения (ТОП-3)', x=metrics_labels, y=after[:4], marker_color='#FFD700')])
    fig.update_layout(barmode='group', title=f"Прогноз роста активности: {st.session_state.niche_selector}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("📋 Используемые показатели")
        st.table(pd.DataFrame({
            "Параметр": ["CTR до / после", "Конв. в Маршрут", "Конв. в Звонок", "Конв. на Сайт", "Конв. в продажу", "Средний чек"],
            "Значение": [
                f"{st.session_state.ctr_before_in:.2f}% / {st.session_state.ctr_after_in:.2f}%",
                f"{st.session_state.conv_map_in:.2f}%", f"{st.session_state.conv_call_in:.2f}%",
                f"{st.session_state.conv_site_in:.2f}%", f"{st.session_state.conv_sale_in:.1f}%",
                f"{st.session_state.avg_check_in:,} руб."
            ],
            "Описание": [
                "Эффективность карточки в поиске (клики/показы).",
                "Процент построивших маршрут от открывших карточку.",
                "Процент нажавших на кнопку звонка.",
                "Процент перешедших на сайт.",
                "Конверсия из лида (звонок/маршрут/сайт) в сделку.",
                "Средняя стоимость услуги/товара."
            ]
        }))

    with col2:
        st.subheader("💰 Экономический эффект")
        st.metric("Прирост выручки (прогноз)", f"{after[5] - before[5]:,} ₽", f"x{round(after[5]/max(before[5],1), 1)}")
        st.table(pd.DataFrame({
            "Метрика": metrics_labels + ["Всего обращений", "Продажи"],
            "Было": before[:4] + [before[4], before[6]], "Станет": after[:4] + [after[4], after[6]],
            "Рост": [f"{round(a/max(b,1), 1)}x" for a, b in zip(after[:4] + [after[4], after[6]], before[:4] + [before[4], before[6]])]
        }))
        
        with st.expander("ℹ️ Как считаются показатели?"):
            st.write("""
            *   **Просмотры**: Спрос в локации × CTR.
            *   **Действия (Маршруты/Звонки/Сайт)**: Просмотры × Конверсия в действие × Коэф. рейтинга.
            *   **Всего обращений**: Сумма всех действий (Маршруты + Звонки + Сайт).
            *   **Продажи**: Всего обращений × Конверсия в продажу.
            *   **Выручка**: Продажи × Средний чек.
            """)

    st.subheader("📝 Текст для коммерческого предложения")
    st.text_area("Скопируйте текст:", f"""
АНАЛИЗ ЛОКАЦИИ И ЭКОНОМИЧЕСКИЙ ПРОГНОЗ
Ниша: {st.session_state.niche_selector} (Москва)
---
1. ОЦЕНКА СПРОСА
Общий объем горячего спроса в локации (Wordstat): {st.session_state.wordstat_demand:,} чел/мес.
2. ПРОГНОЗ ПОКАЗАТЕЛЕЙ (Цель: ТОП-3 + Рейтинг 4.8+)
• Охват (просмотры карточки): {after[0]:,} (рост с {before[0]:,})
• Целевые обращения (звонки/маршруты/сайт): {after[4]:,} шт/мес.
• Прогнозное кол-во продаж: {after[6]:,} шт/мес.
• Кратность роста видимости: {round(after[0]/max(before[0],1),1)}x
3. ЭКОНОМИЧЕСКАЯ ЭФФЕКТИВНОСТЬ
• Средний чек: {st.session_state.avg_check_in:,} руб.
• Конверсия из обращения в продажу: {st.session_state.conv_sale_in:.1f}%
• Прогнозная выручка: {after[5]:,} руб/мес.
• Чистый прирост выручки от продвижения: {after[5] - before[5]:,} руб/мес.
---
*Данные основаны на индивидуально настроенных коэффициентах и емкости рынка в указанной локации.
""", height=350)

# --- ВКЛАДКА НАСТРОЕК ---
with tab2:
    st.header("⚙️ Управление отраслевыми данными (Пресеты)")
    st.subheader("Редактирование параметров ниши")
    edit_name = st.selectbox("Выберите нишу для правки:", list(config["niches"].keys()), key="editor_niche_selector")
    if edit_name:
        n_edit = config["niches"][edit_name]
        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1:
            e_ctr_b = st.number_input("CTR до (%)", value=n_edit["ctr_before"]*100, format="%.2f", key=f"e1_{edit_name}") / 100
            e_ctr_a = st.number_input("CTR после (%)", value=n_edit["ctr_after"]*100, format="%.2f", key=f"e2_{edit_name}") / 100
        with ec2:
            e_conv_m = st.number_input("Конв. в маршрут (%)", value=n_edit["conv_map"]*100, format="%.2f", key=f"e3_{edit_name}") / 100
            e_conv_c = st.number_input("Конв. в звонок (%)", value=n_edit["conv_call"]*100, format="%.2f", key=f"e4_{edit_name}") / 100
        with ec3:
            e_conv_s = st.number_input("Конв. на сайт (%)", value=n_edit["conv_site"]*100, format="%.2f", key=f"e5_{edit_name}") / 100
            e_avg_check = st.number_input("Средний чек (руб)", value=n_edit["avg_check"], step=500, key=f"e6_{edit_name}")
        with ec4:
            e_conv_sale_preset = st.number_input("Конв. в продажу (%)", value=n_edit.get("conv_sale", 0.3)*100, format="%.1f", key=f"e7_{edit_name}") / 100
            st.write("") 
            if st.button("Сохранить изменения в пресет", key=f"save_preset_{edit_name}"):
                config["niches"][edit_name] = {"ctr_before": e_ctr_b, "ctr_after": e_ctr_a, "conv_map": e_conv_m, "conv_call": e_conv_c, "conv_site": e_conv_s, "avg_check": e_avg_check, "conv_sale": e_conv_sale_preset}
                save_config(config)
                st.success(f"Пресет '{edit_name}' обновлен!")
                st.rerun()

    st.divider()
    st.subheader("Добавить новую нишу (Пресет)")
    with st.expander("Открыть форму добавления"):
        with st.form("add_niche_form"):
            new_name = st.text_input("Название новой ниши")
            ac1, ac2 = st.columns(2)
            with ac1:
                n_ctr_b = st.number_input("CTR до (%)", value=1.0) / 100
                n_ctr_a = st.number_input("CTR после (%)", value=7.0) / 100
                n_conv_m = st.number_input("Конв. в маршрут (%)", value=5.0) / 100
                n_conv_c = st.number_input("Конв. в звонок (%)", value=15.0) / 100
            with ac2:
                n_conv_s = st.number_input("Конв. на сайт (%)", value=10.0) / 100
                n_avg_check = st.number_input("Средний чек (руб)", value=5000, step=500)
                n_conv_sale_new = st.number_input("Конв. в продажу (%)", value=30.0) / 100
            
            if st.form_submit_button("Создать нишу"):
                if new_name and new_name not in config["niches"]:
                    config["niches"][new_name] = {"ctr_before": n_ctr_b, "ctr_after": n_ctr_a, "conv_map": n_conv_m, "conv_call": n_conv_c, "conv_site": n_conv_s, "avg_check": n_avg_check, "conv_sale": n_conv_sale_new}
                    save_config(config)
                    st.success(f"Ниша '{new_name}' создана!")
                    st.rerun()

    st.divider()
    st.subheader("Настройка влияния рейтинга (коэффициенты)")
    rc_e = config["rating_coeffs"]
    rc_col1, rc_col2, rc_col3, rc_col4 = st.columns(4)
    with rc_col1: r48 = st.number_input("Рейтинг 4.8+", value=rc_e.get("4.8", 1.3), key="r48")
    with rc_col2: r43 = st.number_input("Рейтинг 4.3-4.7", value=rc_e.get("4.3", 1.0), key="r43")
    with rc_col3: r38 = st.number_input("Рейтинг 3.8-4.2", value=rc_e.get("3.8", 0.7), key="r38")
    with rc_col4: rdef = st.number_input("Рейтинг < 3.8", value=rc_e.get("default", 0.4), key="rdef")
    
    if st.button("Сохранить коэффициенты рейтинга"):
        config["rating_coeffs"] = {"4.8": r48, "4.3": r43, "3.8": r38, "default": rdef}
        save_config(config)
        st.success("Коэффициенты обновлены!")
        st.rerun()

# --- ВКЛАДКА СОХРАНЕННЫХ РАСЧЕТОВ ---
with tab3:
    st.header("📂 Управление сохраненными расчетами")
    st.info("Загрузка расчетов происходит в сайдбаре на вкладке 'Калькулятор прогноза'.")
    saved_calcs = load_saved_calculations()
    
    if not saved_calcs:
        st.info("У вас пока нет сохраненных расчетов.")
    else:
        for name, data in saved_calcs.items():
            with st.expander(f"📍 {name} (Ниша: {data.get('niche', 'N/A')})"):
                st.write(f"**Спрос:** {data.get('wordstat_demand', 'N/A')} | **Рейтинг:** {data.get('current_rating', 'N/A')}")
                st.write(f"**CTR:** {data.get('ctr_before', 'N/A')}% → {data.get('ctr_after', 'N/A')}%")
                st.write(f"**Средний чек:** {data.get('avg_check', 0):,} руб. | **Конв. в продажу:** {data.get('conv_sale', 'N/A')}%")
                
                if st.button("Удалить", key=f"del_{name}"):
                    delete_calculation(name)
                    st.warning(f"Расчет '{name}' удален.")
                    st.rerun()
