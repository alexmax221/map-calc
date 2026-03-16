import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os

CONFIG_FILE = "config.json"

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

# --- ИНИЦИАЛИЗАЦИЯ ---

st.set_page_config(page_title="Яндекс Карты: Прогноз 2025 (Мск)", layout="wide")
config = load_config()

# --- ИНТЕРФЕЙС ---

tab1, tab2 = st.tabs(["📊 Калькулятор прогноза", "⚙️ Настройки бенчмарков"])

with tab1:
    st.title("🚀 Калькулятор роста трафика на Яндекс Картах (Москва)")
    st.write("Инструмент экспертной оценки потенциала локации на основе отраслевых бенчмарков 2024-2025.")
    
    # --- БОКОВАЯ ПАНЕЛЬ ---
    st.sidebar.header("Вводные данные")
    selected_niche_name = st.sidebar.selectbox(
        "Ниша бизнеса:", 
        list(config["niches"].keys()),
        help="Выберите сферу деятельности клиента для подгрузки соответствующих бенчмарков."
    )
    wordstat_demand = st.sidebar.number_input(
        "Спрос в локации (чел/мес):", 
        min_value=0, 
        value=10000, 
        step=500,
        help=HELP_TEXTS["wordstat"]
    )
    current_rating = st.sidebar.slider(
        "Текущий рейтинг в Картах:", 
        1.0, 5.0, 4.0, 0.1,
        help=HELP_TEXTS["rating"]
    )
    
    n_data = config["niches"][selected_niche_name]
    default_conv_sale = n_data.get("conv_sale", 0.3) * 100

    sales_conv = st.sidebar.slider(
        "Конверсия из обращения в продажу (%):", 
        min_value=0.0, 
        max_value=60.0, 
        value=float(default_conv_sale), 
        step=0.1,
        key=f"conv_sale_{selected_niche_name}",
        help=HELP_TEXTS["conv_sale"]
    ) / 100

    # --- ЛОГИКА РАСЧЕТА ---
    rc = config["rating_coeffs"]

    # Коэффициент рейтинга
    r_coeff_before = rc["4.8"] if current_rating >= 4.8 else (
        rc["4.3"] if current_rating >= 4.3 else (
            rc["3.8"] if current_rating >= 3.8 else rc["default"]
        )
    )
    r_coeff_after = rc["4.8"] 

    def calculate_metrics(ctr, r_coeff):
        views = int(wordstat_demand * ctr)
        maps = int(views * n_data['conv_map'] * r_coeff)
        calls = int(views * n_data['conv_call'] * r_coeff)
        site = int(views * n_data['conv_site'] * r_coeff)
        total_leads = maps + calls + site
        sales = int(total_leads * sales_conv)
        revenue = int(sales * n_data['avg_check'])
        return [views, maps, calls, site, total_leads, revenue, sales]

    before = calculate_metrics(n_data['ctr_before'], r_coeff_before)
    after = calculate_metrics(n_data['ctr_after'], r_coeff_after)

    metrics_labels = ['Просмотры', 'Маршруты', 'Звонки', 'Сайт']

    # --- ВИЗУАЛИЗАЦИЯ (ГРАФИК) ---
    fig = go.Figure(data=[
        go.Bar(name='Текущее состояние', x=metrics_labels, y=before[:4], marker_color='#E0E0E0'),
        go.Bar(name='После продвижения (ТОП-3)', x=metrics_labels, y=after[:4], marker_color='#FFD700')
    ])
    fig.update_layout(barmode='group', title=f"Прогноз роста активности: {selected_niche_name}")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.plotly_chart(fig, use_container_width=True)
        
        # Блок бенчмарков
        st.subheader("📋 Отраслевые показатели (Бенчмарки)")
        bench_data = {
            "Параметр": [
                "Ожидаемый CTR в ТОП-3", 
                "Конв. в Маршрут", 
                "Конв. в Звонок", 
                "Конв. на Сайт", 
                "Средняя конв. в продажу",
                "Средний чек (Мск)"
            ],
            "Значение": [
                f"{round(n_data['ctr_after']*100, 1)}%",
                f"{round(n_data['conv_map']*100, 1)}%",
                f"{round(n_data['conv_call']*100, 1)}%",
                f"{round(n_data['conv_site']*100, 1)}%",
                f"{round(n_data.get('conv_sale', 0.3)*100, 1)}%",
                f"{n_data['avg_check']:,} руб."
            ],
            "Справка": [
                HELP_TEXTS["ctr"],
                HELP_TEXTS["conv_map"],
                HELP_TEXTS["conv_call"],
                HELP_TEXTS["conv_site"],
                HELP_TEXTS["conv_sale"],
                HELP_TEXTS["avg_check"]
            ]
        }
        st.table(pd.DataFrame(bench_data))
        st.caption("Данные основаны на агрегированной статистике по Москве за 2024 год (кейсы агентств и внутренние данные сервисов).")

    with col2:
        st.subheader("💰 Экономический эффект")
        st.metric("Прирост выручки (прогноз)", f"{after[5] - before[5]:,} ₽", f"x{round(after[5]/max(before[5],1), 1)}")
        
        comparison_df = pd.DataFrame({
            "Метрика": metrics_labels + ["Всего обращений", "Продажи"],
            "Было": before[:4] + [before[4], before[6]],
            "Станет": after[:4] + [after[4], after[6]],
            "Рост": [f"{round(a/max(b,1), 1)}x" for a, b in zip(after[:4] + [after[4], after[6]], before[:4] + [before[4], before[6]])]
        })
        st.table(comparison_df)
        
        with st.expander("Как считаются продажи?"):
            st.write(f"""
            1. **Обращения** = Звонки + Маршруты + Переходы на сайт.
            2. **Продажи** = Всего обращений * {round(sales_conv*100, 1)}% (выбранная конверсия).
            3. **Выручка** = Количество продаж * {n_data['avg_check']:,} руб. (средний чек).
            """)

    # --- ГОТОВЫЙ ТЕКСТ ДЛЯ КП ---
    st.subheader("📝 Текст для коммерческого предложения")
    summary_text = f"""
АНАЛИЗ ЛОКАЦИИ И ЭКОНОМИЧЕСКИЙ ПРОГНОЗ
Ниша: {selected_niche_name} (Москва)

---

1. ОЦЕНКА СПРОСА
Общий объем горячего спроса в локации (Wordstat): {wordstat_demand:,} чел/мес.

2. ПРОГНОЗ ПОКАЗАТЕЛЕЙ (Цель: ТОП-3 + Рейтинг 4.8+)
• Охват (просмотры карточки): {after[0]:,} (рост с {before[0]:,})
• Целевые обращения (звонки/маршруты/сайт): {after[4]:,} шт/мес.
• Прогнозное кол-во продаж: {after[6]:,} шт/мес.
• Кратность роста видимости: {round(after[0]/max(before[0],1),1)}x

3. ЭКОНОМИЧЕСКАЯ ЭФФЕКТИВНОСТЬ
• Средний чек в нише: {n_data['avg_check']:,} руб.
• Конверсия из обращения в продажу: {round(sales_conv*100, 1)}%
• Прогнозная выручка: {after[5]:,} руб/мес.
• Чистый прирост выручки от продвижения: {after[5] - before[5]:,} руб/мес.

---
*Данные основаны на средних бенчмарках Москвы за 2024 год и емкости рынка в указанной локации.
"""
    st.text_area("Скопируйте текст:", summary_text, height=350)

# --- ВКЛАДКА НАСТРОЕК ---
with tab2:
    st.header("⚙️ Управление отраслевыми данными")
    
    # Редактирование
    st.subheader("Редактирование параметров ниши")
    edit_name = st.selectbox("Выберите нишу для правки:", list(config["niches"].keys()))
    n_edit = config["niches"][edit_name]
    
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        e_ctr_b = st.number_input("CTR до (%)", value=n_edit["ctr_before"]*100, format="%.2f", help=HELP_TEXTS["ctr"]) / 100
        e_ctr_a = st.number_input("CTR после (%)", value=n_edit["ctr_after"]*100, format="%.2f") / 100
    with ec2:
        e_conv_m = st.number_input("Конв. в маршрут (%)", value=n_edit["conv_map"]*100, format="%.2f", help=HELP_TEXTS["conv_map"]) / 100
        e_conv_c = st.number_input("Конв. в звонок (%)", value=n_edit["conv_call"]*100, format="%.2f", help=HELP_TEXTS["conv_call"]) / 100
    with ec3:
        e_conv_s = st.number_input("Конв. на сайт (%)", value=n_edit["conv_site"]*100, format="%.2f", help=HELP_TEXTS["conv_site"]) / 100
        e_avg_check = st.number_input("Средний чек (руб)", value=n_edit["avg_check"], step=500, help=HELP_TEXTS["avg_check"])
    with ec4:
        e_conv_sale = st.number_input("Конв. в продажу (%)", value=n_edit.get("conv_sale", 0.3)*100, format="%.1f", help=HELP_TEXTS["conv_sale"]) / 100
        st.write("") 
        if st.button("Сохранить изменения"):
            config["niches"][edit_name] = {
                "ctr_before": e_ctr_b, "ctr_after": e_ctr_a,
                "conv_map": e_conv_m, "conv_call": e_conv_c,
                "conv_site": e_conv_s, "avg_check": e_avg_check,
                "conv_sale": e_conv_sale
            }
            save_config(config)
            st.success(f"Данные для '{edit_name}' обновлены!")
            st.rerun()

    st.divider()
    
    # Добавление
    st.subheader("Добавить новую нишу")
    with st.expander("Открыть форму добавления"):
        new_name = st.text_input("Название новой ниши")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1:
            n_ctr_b = st.number_input("CTR до (%)  ", value=1.0, key="n1") / 100
            n_ctr_a = st.number_input("CTR после (%)  ", value=7.0, key="n2") / 100
        with ac2:
            n_conv_m = st.number_input("Конв. в маршрут (%)  ", value=5.0, key="n3") / 100
            n_conv_c = st.number_input("Конв. в звонок (%)  ", value=15.0, key="n4") / 100
        with ac3:
            n_conv_s = st.number_input("Конв. на сайт (%)  ", value=10.0, key="n5") / 100
            n_avg_check = st.number_input("Средний чек (руб)  ", value=5000, step=500, key="n6")
        with ac4:
            n_conv_sale_new = st.number_input("Конв. в продажу (%)  ", value=30.0, key="n7") / 100
            
        if st.button("Создать нишу"):
            if new_name and new_name not in config["niches"]:
                config["niches"][new_name] = {
                    "ctr_before": n_ctr_b, "ctr_after": n_ctr_a,
                    "conv_map": n_conv_m, "conv_call": n_conv_c,
                    "conv_site": n_conv_s, "avg_check": n_avg_check,
                    "conv_sale": n_conv_sale_new
                }
                save_config(config)
                st.success(f"Ниша '{new_name}' создана!")
                st.rerun()

    st.divider()
    
    # Рейтинги
    st.subheader("Настройка влияния рейтинга (коэффициенты)")
    rc_e = config["rating_coeffs"]
    rc_col1, rc_col2, rc_col3, rc_col4 = st.columns(4)
    with rc_col1: r48 = st.number_input("Рейтинг 4.8+", value=rc_e["4.8"], help="Множитель конверсии при идеальном рейтинге.")
    with rc_col2: r43 = st.number_input("Рейтинг 4.3-4.7", value=rc_e["4.3"], help="Базовый коэффициент.")
    with rc_col3: r38 = st.number_input("Рейтинг 3.8-4.2", value=rc_e["3.8"], help="Штрафной коэффициент за средний рейтинг.")
    with rc_col4: rdef = st.number_input("Рейтинг < 3.8", value=rc_e["default"], help="Критический штраф за плохой рейтинг.")
    
    if st.button("Сохранить коэффициенты рейтинга"):
        config["rating_coeffs"] = {"4.8": r48, "4.3": r43, "3.8": r38, "default": rdef}
        save_config(config)
        st.success("Коэффициенты обновлены!")
