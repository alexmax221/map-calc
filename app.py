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

def get_rating_coeff(rating, rating_coeffs):
    if rating >= 4.8:
        return rating_coeffs.get("4.8")
    if rating >= 4.3:
        return rating_coeffs.get("4.3")
    if rating >= 3.8:
        return rating_coeffs.get("3.8")
    return rating_coeffs.get("default")

def get_competition_coeff(competitor_count, competition_coeffs):
    if competitor_count <= 2:
        return competition_coeffs.get("2")
    if competitor_count <= 6:
        return competition_coeffs.get("6")
    if competitor_count <= 15:
        return competition_coeffs.get("15")
    if competitor_count <= 35:
        return competition_coeffs.get("35")
    if competitor_count <= 60:
        return competition_coeffs.get("60")
    return competition_coeffs.get("default")

def calculate_metrics(demand, ctr, rating_coeff, conv_map, conv_call, conv_site, conv_sale, avg_check, competition_coeff):
    views = int(demand * (ctr / 100))
    maps = int(views * (conv_map / 100) * rating_coeff)
    calls = int(views * (conv_call / 100) * rating_coeff)
    site = int(views * (conv_site / 100) * rating_coeff)
    total_leads = maps + calls + site
    sales = int(total_leads * (conv_sale / 100) * competition_coeff)
    revenue = int(sales * avg_check)
    return [views, maps, calls, site, total_leads, revenue, sales]

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

def get_calculation_type(data):
    return data.get("calc_type", "single")

def queue_chain_calculation_load(calc_name, data):
    st.session_state.pending_chain_load = {
        "name": calc_name,
        "data": data,
    }

def load_chain_calculation_into_state(calc_name, data):
    points = data.get("points", [])
    normalized_points = [
        {
            "Адрес": point.get("address", ""),
            "Спрос": int(point.get("demand", 0)),
            "Конкуренты": int(point.get("competitors", 0)),
            "Рейтинг": float(point.get("rating", 4.0)),
        }
        for point in points
    ]

    for key in list(st.session_state.keys()):
        if key.startswith("chain_address_") or key.startswith("chain_demand_") or key.startswith("chain_competitors_") or key.startswith("chain_rating_"):
            del st.session_state[key]

    st.session_state.chain_points = normalized_points or [{"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0}]
    st.session_state.chain_save_name = calc_name
    saved_niche = data.get("niche")
    if saved_niche in config["niches"]:
        st.session_state.chain_niche_selector = saved_niche

    for idx, point in enumerate(st.session_state.chain_points):
        st.session_state[f"chain_address_{idx}"] = point["Адрес"]
        st.session_state[f"chain_demand_{idx}"] = point["Спрос"]
        st.session_state[f"chain_competitors_{idx}"] = point["Конкуренты"]
        st.session_state[f"chain_rating_{idx}"] = point["Рейтинг"]

def apply_pending_chain_load():
    pending = st.session_state.pop("pending_chain_load", None)
    if pending:
        load_chain_calculation_into_state(pending["name"], pending["data"])

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
    st.session_state.competitor_count = 5
    st.session_state.ctr_before_in = n_data['ctr_before'] * 100
    st.session_state.ctr_after_in = n_data['ctr_after'] * 100
    st.session_state.conv_map_in = n_data['conv_map'] * 100
    st.session_state.conv_call_in = n_data['conv_call'] * 100
    st.session_state.conv_site_in = n_data['conv_site'] * 100
    st.session_state.conv_sale_in = n_data.get('conv_sale', 0.3) * 100
    st.session_state.avg_check_in = n_data['avg_check']

if 'chain_points' not in st.session_state:
    st.session_state.chain_points = [
        {"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0},
        {"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0},
        {"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0},
    ]

# --- ИНТЕРФЕЙС ---

tab1, tab2, tab3, tab4 = st.tabs(["📊 Калькулятор прогноза", "🏪 Сетка точек", "⚙️ Настройки бенчмарков", "📂 Сохраненные расчеты"])

with tab1:
    st.title("🚀 Калькулятор роста трафика на Яндекс Картах")
    st.write("Инструмент экспертной оценки потенциала локации на основе отраслевых бенчмарков.")
    
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
        if data and get_calculation_type(data) == "single":
            st.session_state.wordstat_demand = data['wordstat_demand']
            st.session_state.current_rating = data['current_rating']
            st.session_state.competitor_count = data.get('competitor_count', 5)
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
    st.sidebar.number_input("Текущий рейтинг в Картах:", min_value=1.0, max_value=5.0, step=0.1, format="%.1f", key="current_rating")
    
    st.sidebar.number_input("Конкурентов в радиусе 1 км:", min_value=0, step=1, key="competitor_count")
    
    # Расчет коэффициента для вывода в sidebar
    cc_sidebar = config.get("competition_coeffs", {"2": 1.1, "6": 1.0, "15": 0.85, "35": 0.7, "60": 0.55, "default": 0.4})
    c_count_sb = st.session_state.competitor_count
    current_k = cc_sidebar.get("2") if c_count_sb <= 2 else (cc_sidebar.get("6") if c_count_sb <= 6 else (cc_sidebar.get("15") if c_count_sb <= 15 else (cc_sidebar.get("35") if c_count_sb <= 35 else (cc_sidebar.get("60") if c_count_sb <= 60 else cc_sidebar.get("default")))))
    
    st.sidebar.caption(f"📊 Множитель влияния: **x{current_k}**")
    if current_k < 1.0:
        st.sidebar.warning(f"Высокая конкуренция снижает продажи на {int((1-current_k)*100)}%")
    elif current_k > 1.0:
        st.sidebar.success(f"Низкая конкуренция дает бонус +{int((current_k-1)*100)}%")

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
    single_saved_calc_names = [name for name, data in saved_calcs.items() if get_calculation_type(data) == "single"]
    st.sidebar.selectbox(
        "Загрузить расчет:",
        [""] + single_saved_calc_names,
        key="load_selector",
        on_change=on_load_calculation
    )

    save_name = st.sidebar.text_input("Название для сохранения:")
    if st.sidebar.button("💾 Сохранить текущий расчет"):
        if save_name:
            calc_data = {
                "calc_type": "single",
                "niche": st.session_state.niche_selector,
                "wordstat_demand": st.session_state.wordstat_demand,
                "current_rating": st.session_state.current_rating,
                "competitor_count": st.session_state.competitor_count,
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
    r_coeff_before = get_rating_coeff(st.session_state.current_rating, rc)
    r_coeff_after = rc.get("4.8")

    # Коэффициент конкуренции из конфига
    cc = config.get("competition_coeffs", {"2": 1.1, "6": 1.0, "15": 0.85, "35": 0.7, "60": 0.55, "default": 0.4})
    c_count = st.session_state.competitor_count
    comp_coeff = get_competition_coeff(c_count, cc)

    before = calculate_metrics(st.session_state.wordstat_demand, st.session_state.ctr_before_in, r_coeff_before, st.session_state.conv_map_in, st.session_state.conv_call_in, st.session_state.conv_site_in, st.session_state.conv_sale_in, st.session_state.avg_check_in, comp_coeff)
    after = calculate_metrics(st.session_state.wordstat_demand, st.session_state.ctr_after_in, r_coeff_after, st.session_state.conv_map_in, st.session_state.conv_call_in, st.session_state.conv_site_in, st.session_state.conv_sale_in, st.session_state.avg_check_in, comp_coeff)

    metrics_labels = ['Просмотры', 'Маршруты', 'Звонки', 'Сайт']
    fig = go.Figure(data=[go.Bar(name='Текущее состояние', x=metrics_labels, y=before[:4], marker_color='#E0E0E0'), go.Bar(name='После продвижения (ТОП-3)', x=metrics_labels, y=after[:4], marker_color='#FFD700')])
    fig.update_layout(barmode='group', title=f"Прогноз роста активности: {st.session_state.niche_selector}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("📋 Используемые показатели")
        st.table(pd.DataFrame({
            "Параметр": ["Конкуренция (1км)", "CTR до / после", "Конв. в Маршрут", "Конв. в Звонок", "Конв. на Сайт", "Конв. в продажу", "Средний чек"],
            "Значение": [
                f"{st.session_state.competitor_count} объект. (x{comp_coeff})",
                f"{st.session_state.ctr_before_in:.2f}% / {st.session_state.ctr_after_in:.2f}%",
                f"{st.session_state.conv_map_in:.2f}%", f"{st.session_state.conv_call_in:.2f}%",
                f"{st.session_state.conv_site_in:.2f}%", f"{st.session_state.conv_sale_in:.1f}%",
                f"{st.session_state.avg_check_in:,} руб."
            ],
            "Описание": [
                "Плотность конкуренции снижает долю рынка одного игрока.",
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
1. ОЦЕНКА СПРОСА И КОНКУРЕНЦИИ
Общий объем горячего спроса в локации (Wordstat): {st.session_state.wordstat_demand:,} чел/мес.
Плотность конкуренции: {st.session_state.competitor_count} объектов в радиусе 1 км.
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

# --- ВКЛАДКА СЕТКИ ТОЧЕК ---
with tab2:
    apply_pending_chain_load()
    st.title("🏪 Расчет прироста трафика для сетки точек")
    st.write("Выберите нишу и заполните данные по каждой точке. Для всей сетки автоматически применяются бенчмарки выбранной отрасли.")

    chain_niche = st.selectbox(
        "Ниша для всей сетки:",
        list(config["niches"].keys()),
        key="chain_niche_selector"
    )
    chain_preset = config["niches"][chain_niche]

    st.caption(
        f"Пресет ниши: CTR {chain_preset['ctr_before']*100:.1f}% → {chain_preset['ctr_after']*100:.1f}%, "
        f"маршрут {chain_preset['conv_map']*100:.1f}%, звонок {chain_preset['conv_call']*100:.1f}%, "
        f"сайт {chain_preset['conv_site']*100:.1f}%, продажа {chain_preset['conv_sale']*100:.1f}%, "
        f"средний чек {chain_preset['avg_check']:,} ₽."
    )

    toolbar_col1, toolbar_col2 = st.columns([1, 5])
    with toolbar_col1:
        if st.button("➕ Добавить точку", key="add_chain_point"):
            st.session_state.chain_points.append({"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0})
            st.rerun()
    with toolbar_col2:
        st.caption("Изменения в полях сохраняются при переходе к следующему полю. Для рейтинга доступны дробные значения, например `4.4`.")

    st.subheader("📍 Параметры точек")
    header_cols = st.columns([3, 1.2, 1.2, 1.2, 0.8])
    header_cols[0].markdown("**Адрес**")
    header_cols[1].markdown("**Спрос**")
    header_cols[2].markdown("**Конкуренты**")
    header_cols[3].markdown("**Рейтинг**")
    header_cols[4].markdown("**Действие**")

    updated_chain_points = []
    remove_index = None
    if not st.session_state.chain_points:
        st.session_state.chain_points = [{"Адрес": "", "Спрос": 10000, "Конкуренты": 5, "Рейтинг": 4.0}]

    for idx, point in enumerate(st.session_state.chain_points):
        row_cols = st.columns([3, 1.2, 1.2, 1.2, 0.8])
        address_key = f"chain_address_{idx}"
        demand_key = f"chain_demand_{idx}"
        competitors_key = f"chain_competitors_{idx}"
        rating_key = f"chain_rating_{idx}"

        if address_key not in st.session_state:
            st.session_state[address_key] = point.get("Адрес", "")
        if demand_key not in st.session_state:
            st.session_state[demand_key] = int(point.get("Спрос", 10000))
        if competitors_key not in st.session_state:
            st.session_state[competitors_key] = int(point.get("Конкуренты", 5))
        if rating_key not in st.session_state:
            st.session_state[rating_key] = float(point.get("Рейтинг", 4.0))

        with row_cols[0]:
            address = st.text_input(
                f"Адрес {idx + 1}",
                key=address_key,
                label_visibility="collapsed",
                placeholder="Например, ул. Ленина, 10"
            )
        with row_cols[1]:
            demand = st.number_input(
                f"Спрос {idx + 1}",
                min_value=0,
                step=500,
                key=demand_key,
                label_visibility="collapsed"
            )
        with row_cols[2]:
            competitors = st.number_input(
                f"Конкуренты {idx + 1}",
                min_value=0,
                step=1,
                key=competitors_key,
                label_visibility="collapsed"
            )
        with row_cols[3]:
            rating = st.number_input(
                f"Рейтинг {idx + 1}",
                min_value=1.0,
                max_value=5.0,
                step=0.1,
                format="%.1f",
                key=rating_key,
                label_visibility="collapsed"
            )
        with row_cols[4]:
            if st.button("✕", key=f"remove_chain_point_{idx}", help="Удалить точку"):
                remove_index = idx

        updated_chain_points.append({
            "Адрес": address,
            "Спрос": int(demand),
            "Конкуренты": int(competitors),
            "Рейтинг": float(rating),
        })

    st.session_state.chain_points = updated_chain_points
    if remove_index is not None:
        st.session_state.chain_points.pop(remove_index)
        st.rerun()

    cc = config.get("competition_coeffs", {"2": 1.1, "6": 1.0, "15": 0.85, "35": 0.7, "60": 0.55, "default": 0.4})
    rc = config["rating_coeffs"]
    saved_calcs = load_saved_calculations()
    chain_saved_calc_names = [name for name, data in saved_calcs.items() if get_calculation_type(data) == "chain"]
    chain_results = []

    for row in st.session_state.chain_points:
        address = str(row.get("Адрес", "")).strip()
        demand = int(row.get("Спрос", 0) or 0)
        competitors = int(row.get("Конкуренты", 0) or 0)
        rating = float(row.get("Рейтинг", 0) or 0)

        if not address or demand <= 0:
            continue

        rating_before = get_rating_coeff(rating, rc)
        rating_after = rc.get("4.8")
        competition_coeff = get_competition_coeff(competitors, cc)

        before_point = calculate_metrics(
            demand,
            chain_preset["ctr_before"] * 100,
            rating_before,
            chain_preset["conv_map"] * 100,
            chain_preset["conv_call"] * 100,
            chain_preset["conv_site"] * 100,
            chain_preset["conv_sale"] * 100,
            chain_preset["avg_check"],
            competition_coeff
        )
        after_point = calculate_metrics(
            demand,
            chain_preset["ctr_after"] * 100,
            rating_after,
            chain_preset["conv_map"] * 100,
            chain_preset["conv_call"] * 100,
            chain_preset["conv_site"] * 100,
            chain_preset["conv_sale"] * 100,
            chain_preset["avg_check"],
            competition_coeff
        )

        chain_results.append({
            "Адрес": address or "Без названия",
            "Спрос": demand,
            "Конкуренты": competitors,
            "Рейтинг": round(rating, 1),
            "Просмотры сейчас": before_point[0],
            "Просмотры после": after_point[0],
            "Прирост просмотров": after_point[0] - before_point[0],
            "Обращения сейчас": before_point[4],
            "Обращения после": after_point[4],
            "Прирост обращений": after_point[4] - before_point[4],
            "Продажи сейчас": before_point[6],
            "Продажи после": after_point[6],
            "Прирост продаж": after_point[6] - before_point[6],
            "Выручка сейчас, ₽": before_point[5],
            "Выручка после, ₽": after_point[5],
            "Прирост выручки, ₽": after_point[5] - before_point[5],
        })

    if chain_results:
        chain_results_df = pd.DataFrame(chain_results)
        total_views_gain = int(chain_results_df["Прирост просмотров"].sum())
        total_leads_gain = int(chain_results_df["Прирост обращений"].sum())
        total_revenue_gain = int(chain_results_df["Прирост выручки, ₽"].sum())
        top_point = chain_results_df.sort_values("Прирост выручки, ₽", ascending=False).iloc[0]

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric("Суммарный прирост просмотров", f"{total_views_gain:,}")
        with metric_col2:
            st.metric("Суммарный прирост обращений", f"{total_leads_gain:,}")
        with metric_col3:
            st.metric("Суммарный прирост выручки", f"{total_revenue_gain:,} ₽")

        st.subheader("📋 Итог по точкам")
        st.dataframe(chain_results_df, use_container_width=True, hide_index=True)

        summary_export_df = chain_results_df[["Адрес", "Спрос", "Прирост выручки, ₽"]].copy()
        summary_totals_df = pd.DataFrame([{
            "Адрес": "Итого",
            "Спрос": int(summary_export_df["Спрос"].sum()),
            "Прирост выручки, ₽": int(summary_export_df["Прирост выручки, ₽"].sum()),
        }])
        summary_export_df = pd.concat([summary_export_df, summary_totals_df], ignore_index=True)

        def highlight_total_row(row):
            if row.name == len(summary_export_df) - 1:
                return ["font-weight: bold"] * len(row)
            return [""] * len(row)

        st.subheader("📦 Таблица для выгрузки")
        st.dataframe(
            summary_export_df.style.apply(highlight_total_row, axis=1),
            use_container_width=True,
            hide_index=True
        )
        st.download_button(
            "Скачать CSV",
            data=summary_export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="chain_traffic_growth_summary.csv",
            mime="text/csv"
        )

        st.info(
            f"Точка с максимальным потенциалом: {top_point['Адрес']} "
            f"({int(top_point['Прирост выручки, ₽']):,} ₽ прироста выручки)."
        )
    else:
        st.info("Добавьте хотя бы одну точку с адресом и параметрами, чтобы увидеть расчет по сетке.")

    st.divider()
    st.subheader("💾 Сохранение и загрузка сеточного расчета")

    chain_load_col, chain_save_col = st.columns(2)
    with chain_load_col:
        selected_chain_calc = st.selectbox(
            "Загрузить сохраненный сеточный расчет:",
            [""] + chain_saved_calc_names,
            key="chain_load_selector"
        )
        if st.button("Загрузить в Сетку точек", key="load_chain_calc_btn"):
            if selected_chain_calc:
                queue_chain_calculation_load(selected_chain_calc, saved_calcs[selected_chain_calc])
                st.rerun()
            else:
                st.error("Выберите сохраненный сеточный расчет для загрузки.")

    with chain_save_col:
        chain_save_name = st.text_input("Название для сохранения сеточного расчета:", key="chain_save_name")
        if st.button("💾 Сохранить расчет по сетке", key="save_chain_calc"):
            valid_chain_points = [
                {
                    "address": row["Адрес"],
                    "demand": int(row["Спрос"]),
                    "competitors": int(row["Конкуренты"]),
                    "rating": float(row["Рейтинг"]),
                }
                for row in st.session_state.chain_points
                if str(row.get("Адрес", "")).strip() and int(row.get("Спрос", 0) or 0) > 0
            ]
            if not valid_chain_points:
                st.error("Добавьте хотя бы одну точку с адресом и спросом, чтобы сохранить сеточный расчет.")
            elif chain_save_name.strip():
                save_calculation(chain_save_name.strip(), {
                    "calc_type": "chain",
                    "niche": chain_niche,
                    "points": valid_chain_points,
                    "summary": {
                        "total_views_gain": int(sum(item["Прирост просмотров"] for item in chain_results)),
                        "total_leads_gain": int(sum(item["Прирост обращений"] for item in chain_results)),
                        "total_revenue_gain": int(sum(item["Прирост выручки, ₽"] for item in chain_results)),
                    }
                })
                st.success("✅ Сеточный расчет сохранен со всеми вводными данными!")
            else:
                st.error("Введите название для сохранения сеточного расчета.")

# --- ВКЛАДКА НАСТРОЕК ---
with tab3:
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
with tab4:
    st.header("📂 Управление сохраненными расчетами")
    st.info("Одиночные расчеты загружаются в сайдбаре на вкладке 'Калькулятор прогноза'. Сеточные расчеты хранятся здесь как отдельные сохранения.")
    saved_calcs = load_saved_calculations()
    
    if not saved_calcs:
        st.info("У вас пока нет сохраненных расчетов.")
    else:
        for name, data in saved_calcs.items():
            calc_type = get_calculation_type(data)
            type_label = "Сетка точек" if calc_type == "chain" else "Одиночный расчет"

            with st.expander(f"📍 {name} ({type_label}, ниша: {data.get('niche', 'N/A')})"):
                if calc_type == "chain":
                    points = data.get("points", [])
                    summary = data.get("summary", {})
                    st.write(f"**Точек в расчете:** {len(points)}")
                    st.write(
                        f"**Суммарный прирост просмотров:** {summary.get('total_views_gain', 0):,} | "
                        f"**Суммарный прирост обращений:** {summary.get('total_leads_gain', 0):,} | "
                        f"**Суммарный прирост выручки:** {summary.get('total_revenue_gain', 0):,} ₽"
                    )
                    if points:
                        chain_saved_df = pd.DataFrame([
                            {
                                "Адрес": point.get("address", ""),
                                "Спрос": point.get("demand", 0),
                                "Конкуренты": point.get("competitors", 0),
                                "Рейтинг": point.get("rating", 0),
                            }
                            for point in points
                        ])
                        st.dataframe(chain_saved_df, use_container_width=True, hide_index=True)
                    if st.button("Загрузить в Сетку точек", key=f"load_chain_{name}"):
                        queue_chain_calculation_load(name, data)
                        st.rerun()
                else:
                    st.write(f"**Спрос:** {data.get('wordstat_demand', 'N/A')} | **Рейтинг:** {data.get('current_rating', 'N/A')}")
                    st.write(f"**CTR:** {data.get('ctr_before', 'N/A')}% → {data.get('ctr_after', 'N/A')}%")
                    st.write(f"**Средний чек:** {data.get('avg_check', 0):,} руб. | **Конв. в продажу:** {data.get('conv_sale', 'N/A')}%")

                if st.button("Удалить", key=f"del_{name}"):
                    delete_calculation(name)
                    st.warning(f"Расчет '{name}' удален.")
                    st.rerun()
