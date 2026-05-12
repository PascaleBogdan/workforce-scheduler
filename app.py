import streamlit as st
import pandas as pd
import datetime
import json
import os
import calendar
import storage
import scheduler
import importlib
importlib.reload(scheduler)
solve_schedule = scheduler.solve_schedule

import export_utils
importlib.reload(export_utils)
from export_utils import get_excel_download, get_csv_download, get_color_for_name

# Design and configuration
st.set_page_config(page_title="Workforce Scheduler", page_icon="📅", layout="wide")

if 'schedule_df' not in st.session_state:
    st.session_state['schedule_df'] = None

HISTORY_DIR = "istoric"
os.makedirs(HISTORY_DIR, exist_ok=True)


# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-family: 'Inter', sans-serif;
        color: #2c3e50;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #7f8c8d;
        font-size: 1.1em;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">📅 Scheduler</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Planificare automată a turelor cu balanțare echitabilă și constrângeri inteligente</p>', unsafe_allow_html=True)

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configurare Generală")
    
    loaded_people = storage.load_text("angajati.txt")
    if loaded_people is not None:
        default_people_str = loaded_people
    else:
        default_people_str = "Alex Lehadus\nSever Ali\nCalin Brojba\nElvir Bolat\nBogdan Pascale\nAndrei Badescu\nGeorgian Butoiu\nCosmin Mocanu\nOana Furtuna"
        
    people_input = st.text_area("Angajați (câte unul pe rând)", 
                                default_people_str,
                                height=200)
                                
    if people_input != default_people_str:
        storage.save_text("angajati.txt", people_input)
            
    # Deduplicate and clean
    people_raw = [p.strip() for p in people_input.split("\n") if p.strip()]
    people = list(dict.fromkeys(people_raw))
    
    col_luna, col_an = st.columns(2)
    with col_luna:
        if "luna_input" not in st.session_state:
            st.session_state["luna_input"] = datetime.date.today().month
        luna = int(st.number_input("Luna", min_value=1, max_value=12, key="luna_input"))
    with col_an:
        if "an_input" not in st.session_state:
            st.session_state["an_input"] = datetime.date.today().year
        an = int(st.number_input("Anul", min_value=2024, max_value=2030, key="an_input"))
        
    st.markdown("---")
    st.header("⚡ Performanță Algoritm")
    timp_gandire = st.slider("Timp de gândire (secunde)", min_value=10, max_value=600, value=30, step=10, help="Un timp mai mare permite PC-ului să testeze milioane de combinații în plus pentru un orar perfect. Recomandat: 30s-120s.")
    
    
    loaded_colors = storage.load_json("colors.json")
    custom_colors = loaded_colors if loaded_colors else {}
            
    with st.expander("🎨 Culori Angajați"):
        new_colors = {}
        for p in people:
            default_color = custom_colors.get(p, "#" + get_color_for_name(p, people))
            if not default_color.startswith("#"):
                default_color = "#" + default_color
            new_colors[p] = st.color_picker(p, value=default_color, key=f"color_{p}")
            
        if new_colors != custom_colors:
            storage.save_json("colors.json", new_colors)
            custom_colors = new_colors
            
    st.markdown("---")
    st.header("🗄️ Orare Definitive")
    
    history_files_sb = storage.list_history_files()
    if not history_files_sb:
        st.info("Niciun orar salvat.")
    else:
        for f in sorted(history_files_sb, reverse=True):
            parts = f.replace(".csv", "").split("_")
            if len(parts) == 3:
                y_str, m_str = parts[1], parts[2]
                
                col_name, col_load, col_del = st.columns([3, 1, 1])
                with col_name:
                    st.write(f"**{m_str} / {y_str}**")
                
                with col_load:
                    def load_hist(fname=f, m=m_str, y=y_str):
                        st.session_state['schedule_df'] = storage.load_history_df(fname)
                        st.session_state['luna_input'] = int(m)
                        st.session_state['an_input'] = int(y)
                        
                        json_name = fname.replace(".csv", ".json")
                        preset_data = storage.load_history_json(json_name)
                        if preset_data is not None:
                            try:
                                saved_prefs_load = preset_data.get("preferences", {})
                                saved_weekends_load = preset_data.get("weekends", {})
                                
                                _, num_zile_load = calendar.monthrange(int(y), int(m))
                                
                                saved_holidays_load = preset_data.get("holidays", {})
                                st.session_state["holiday_days"] = [d for d in saved_holidays_load.get("selected_days", []) if 1 <= d <= num_zile_load]
                                for key in list(st.session_state.keys()):
                                    if key.startswith("hol_"):
                                        del st.session_state[key]
                                for d_str, h_people in saved_holidays_load.get("assignments", {}).items():
                                    st.session_state[f"hol_{d_str}"] = [p for p in h_people if p in people]
                                    
                                for person in people:
                                    p_prefs = saved_prefs_load.get(person, {})
                                    st.session_state[f"off_{person}"] = [d for d in p_prefs.get("Liber", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"t1_{person}"] = [d for d in p_prefs.get("T1", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"t2_{person}"] = [d for d in p_prefs.get("T2", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"t3_{person}"] = [d for d in p_prefs.get("T3", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"pzu_{person}"] = [d for d in p_prefs.get("PZU", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"not1_{person}"] = [d for d in p_prefs.get("No_T1", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"not2_{person}"] = [d for d in p_prefs.get("No_T2", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"not3_{person}"] = [d for d in p_prefs.get("No_T3", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"nopzu_{person}"] = [d for d in p_prefs.get("No_PZU", []) if 1 <= d <= num_zile_load]
                                    st.session_state[f"allowed_{person}"] = p_prefs.get("Allowed_Shifts", ["T1", "T2", "T3", "PZU"])
                                    st.session_state[f"titular_{person}"] = p_prefs.get("Is_Titular", True)
                                
                                for i in range(10): 
                                    if f"wk_{i}" in st.session_state:
                                        del st.session_state[f"wk_{i}"]
                                
                                for i_str, wk_people in saved_weekends_load.items():
                                    try:
                                        i_int = int(i_str)
                                        st.session_state[f"wk_{i_int}"] = [p for p in wk_people if p in people]
                                    except:
                                        pass
                            except:
                                pass
                    st.button("📂", key=f"load_{f}", help="Încarcă Orarul Definitiv", on_click=load_hist)
                    
                with col_del:
                    def del_hist(fname=f):
                        storage.delete_history_files(fname)
                    st.button("🗑️", key=f"del_{f}", help="Șterge Orarul Definitiv", on_click=del_hist)

first_day_weekday, num_zile = calendar.monthrange(an, luna)

PRESETS_FILE = 'presets.json'
loaded_presets = storage.load_json('presets.json')
all_presets = loaded_presets if loaded_presets else {}

# Fallback/Migration for old preferences.json
if not all_presets and os.path.exists('preferences.json'):
    try:
        with open('preferences.json', "r", encoding="utf-8") as f:
            saved_data = json.load(f)
            if "preferences" in saved_data and "weekends" in saved_data:
                all_presets["Preset Vechi"] = saved_data
            else:
                all_presets["Preset Vechi"] = {"preferences": saved_data, "weekends": {}}
    except:
        pass

st.markdown("### 🗂️ Gestionare Preset-uri (Date de intrare)")
c_p1, c_p2, c_p3 = st.columns([2, 1, 1])

with c_p1:
    preset_names = list(all_presets.keys())
    selected_preset_name = st.selectbox("Alege un preset salvat:", ["-- Fără Preset --"] + preset_names)

with c_p2:
    st.markdown("<br>", unsafe_allow_html=True)
    
    def on_load_click(preset_name):
        if preset_name != "-- Fără Preset --":
            preset_data = all_presets[preset_name]
            saved_prefs_load = preset_data.get("preferences", {})
            saved_weekends_load = preset_data.get("weekends", {})
            
            load_luna = preset_data.get("luna", luna)
            load_an = preset_data.get("an", an)
            _, num_zile_load = calendar.monthrange(load_an, load_luna)
            
            saved_holidays_load = preset_data.get("holidays", {})
            st.session_state["holiday_days"] = [d for d in saved_holidays_load.get("selected_days", []) if 1 <= d <= num_zile_load]
            for key in list(st.session_state.keys()):
                if key.startswith("hol_"):
                    del st.session_state[key]
            for d_str, h_people in saved_holidays_load.get("assignments", {}).items():
                st.session_state[f"hol_{d_str}"] = [p for p in h_people if p in people]
                
            if "luna" in preset_data:
                st.session_state["luna_input"] = preset_data["luna"]
            if "an" in preset_data:
                st.session_state["an_input"] = preset_data["an"]
                
            for person in people:
                p_prefs = saved_prefs_load.get(person, {})
                st.session_state[f"off_{person}"] = [d for d in p_prefs.get("Liber", []) if 1 <= d <= num_zile_load]
                st.session_state[f"t1_{person}"] = [d for d in p_prefs.get("T1", []) if 1 <= d <= num_zile_load]
                st.session_state[f"t2_{person}"] = [d for d in p_prefs.get("T2", []) if 1 <= d <= num_zile_load]
                st.session_state[f"t3_{person}"] = [d for d in p_prefs.get("T3", []) if 1 <= d <= num_zile_load]
                st.session_state[f"pzu_{person}"] = [d for d in p_prefs.get("PZU", []) if 1 <= d <= num_zile_load]
                st.session_state[f"not1_{person}"] = [d for d in p_prefs.get("No_T1", []) if 1 <= d <= num_zile_load]
                st.session_state[f"not2_{person}"] = [d for d in p_prefs.get("No_T2", []) if 1 <= d <= num_zile_load]
                st.session_state[f"not3_{person}"] = [d for d in p_prefs.get("No_T3", []) if 1 <= d <= num_zile_load]
                st.session_state[f"nopzu_{person}"] = [d for d in p_prefs.get("No_PZU", []) if 1 <= d <= num_zile_load]
                st.session_state[f"allowed_{person}"] = p_prefs.get("Allowed_Shifts", ["T1", "T2", "T3", "PZU"])
                st.session_state[f"titular_{person}"] = p_prefs.get("Is_Titular", True)
            
            for i in range(10): 
                if f"wk_{i}" in st.session_state:
                    del st.session_state[f"wk_{i}"]
            
            for i_str, wk_people in saved_weekends_load.items():
                try:
                    i_int = int(i_str)
                    st.session_state[f"wk_{i_int}"] = [p for p in wk_people if p in people]
                except:
                    pass

    st.button("📂 Încarcă", use_container_width=True, on_click=on_load_click, args=(selected_preset_name,))

with c_p3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Șterge", use_container_width=True):
        if selected_preset_name != "-- Fără Preset --":
            del all_presets[selected_preset_name]
            storage.save_json(PRESETS_FILE, all_presets)
            st.rerun()

saved_prefs = {}
saved_weekends = {}
preset_data = {}
if selected_preset_name != "-- Fără Preset --":
    preset_data = all_presets.get(selected_preset_name, {})
    saved_prefs = preset_data.get("preferences", {})
    saved_weekends = preset_data.get("weekends", {})

with st.expander("🏕️ Repartizare Weekend-uri", expanded=False):
    st.info("Selectează persoanele care lucrează în fiecare weekend (între 3 și 6 persoane, în funcție de câte ture dublate ai nevoie).")
    
    first_day_is_sunday = (first_day_weekday == 6)
    prev_month_weekend_workers = []
    if first_day_is_sunday:
        prev_month = luna - 1 if luna > 1 else 12
        prev_year = an if luna > 1 else an - 1
        prev_file = os.path.join(HISTORY_DIR, f"orar_{prev_year}_{prev_month:02d}.csv")
        if os.path.exists(prev_file):
            try:
                df_prev = pd.read_csv(prev_file)
                if len(df_prev) >= 1:
                    last_day_row = df_prev.iloc[-1]
                    if last_day_row.get("Ziua", "") == "Sambata":
                        for col in ["Tura 1", "Tura 2", "Tura 3", "PZU"]:
                            if col in df_prev.columns:
                                w_sat = str(last_day_row.get(col, "-")).replace(" (!)", "")
                                if w_sat != "-" and w_sat in people:
                                    prev_month_weekend_workers.append(w_sat)
            except:
                pass
    
    weekends = []
    current_weekend = []
    for d in range(num_zile):
        current_weekday = (first_day_weekday + d) % 7
        if current_weekday in [5, 6]:
            current_weekend.append(d+1)
            if current_weekday == 6 or d == num_zile - 1:
                weekends.append(current_weekend)
                current_weekend = []
    
    weekend_assignments = {}
    cols_wk = st.columns(len(weekends) if len(weekends) <= 5 else 5)
    for i, wk_days in enumerate(weekends):
        col_idx = i % len(cols_wk)
        with cols_wk[col_idx]:
            if len(wk_days) == 2:
                label = f"Wkd {i+1} ({wk_days[0]:02d}-{wk_days[1]:02d}/{luna:02d})"
            else:
                label = f"Wkd {i+1} ({wk_days[0]:02d}/{luna:02d})"
            
            default_wk = saved_weekends.get(str(i), [])
            default_wk = [p for p in default_wk if p in people]
            
            if i == 0 and first_day_is_sunday and wk_days == [1] and prev_month_weekend_workers:
                st.info(f"**{label}**: Preluat din {prev_month:02d}/{prev_year}")
                st.write(", ".join(prev_month_weekend_workers))
                weekend_assignments[i] = prev_month_weekend_workers
            else:
                if f"wk_{i}" not in st.session_state:
                    st.session_state[f"wk_{i}"] = default_wk
                weekend_assignments[i] = st.multiselect(
                    label,
                    options=people,
                    key=f"wk_{i}"
                )

st.markdown("---")
with st.expander("🎉 Sărbători (Zile Speciale)", expanded=False):
    st.info("Alege zilele de sărbătoare și persoanele care au prioritate să lucreze în acele zile.")
    
    saved_holidays = preset_data.get("holidays", {})
    default_hol_days = saved_holidays.get("selected_days", [])
    default_hol_days = [d for d in default_hol_days if 1 <= d <= num_zile]
    
    if "holiday_days" not in st.session_state:
        st.session_state["holiday_days"] = default_hol_days
    holiday_days = st.multiselect(
        "Selectează Zilele de Sărbătoare",
        options=list(range(1, num_zile + 1)),
        key="holiday_days"
    )
    
    holiday_assignments = {}
    if holiday_days:
        cols_hol = st.columns(len(holiday_days) if len(holiday_days) <= 5 else 5)
        for i, hd in enumerate(sorted(holiday_days)):
            col_idx = i % len(cols_hol)
            with cols_hol[col_idx]:
                default_h_people = saved_holidays.get("assignments", {}).get(str(hd), [])
                default_h_people = [p for p in default_h_people if p in people]
                
                if f"hol_{hd}" not in st.session_state:
                    st.session_state[f"hol_{hd}"] = default_h_people
                holiday_assignments[str(hd)] = st.multiselect(
                    f"Prioritari {hd:02d}/{luna:02d}",
                    options=people,
                    key=f"hol_{hd}"
                )

st.markdown("---")
with st.expander("📊 Bază Istoric Ture (Date Manuale)", expanded=False):
    st.info("Aici poți adăuga turele din lunile precedente pe care algoritmul nu le cunoaște. Ele vor fi folosite pentru a echilibra turele în lunile viitoare. (Dacă ai deja orare salvate în istoric, acelea se adună automat, aici pui doar ce lipsește!)")
    
    ISTORIC_BAZA_FILE = "istoric_baza.csv"
    base_df = storage.load_df(ISTORIC_BAZA_FILE)
    if base_df is not None:
        existing_people = base_df["Angajat"].tolist()
        missing = [p for p in people if p not in existing_people]
        if missing:
            missing_df = pd.DataFrame([{"Angajat": p, "T1": 0, "T2": 0, "T3": 0, "PZU": 0, "T3_Weekend": 0, "T2_Vineri": 0} for p in missing])
            base_df = pd.concat([base_df, missing_df], ignore_index=True)
    else:
        base_df = pd.DataFrame([{"Angajat": p, "T1": 0, "T2": 0, "T3": 0, "PZU": 0, "T3_Weekend": 0, "T2_Vineri": 0} for p in people])
        
    edited_base_df = st.data_editor(base_df, num_rows="dynamic", use_container_width=True, hide_index=True)
    if st.button("💾 Salvează Istoricul Manual"):
        storage.save_df(ISTORIC_BAZA_FILE, edited_base_df)
        st.success("Istoricul manual a fost salvat!")

st.markdown("---")
preferences = {}
with st.expander("🛠️ Setare Ture Permise, Zile Libere și Preferințe pe Angajat", expanded=False):
    st.info("Setează cine este Titular (susține baza orarului, 1 persoană pe tură) și cine este Dublură (intră doar ca a doua persoană pe tură).")
    for i, person in enumerate(people):
        p_prefs = saved_prefs.get(person, {})
        st.markdown(f"#### {person}")
        c0, c1, c2, c3 = st.columns([1, 1, 1, 1])
        
        with c0:
            is_titular = st.checkbox(
                "👑 Este Titular", 
                value=p_prefs.get("Is_Titular", i < 9), 
                key=f"titular_{person}",
                help="Titularii formează baza orarului (1 pe tură). Dublurile vin doar ca a doua persoană pe tură."
            )
            
            st.markdown("✅ **Ture Permise**")
            allowed_shifts = st.multiselect(
                "Ture",
                options=["T1", "T2", "T3", "PZU"],
                default=p_prefs.get("Allowed_Shifts", ["T1", "T2", "T3", "PZU"]),
                key=f"allowed_{person}",
                help="Debifează turele pe care acest angajat NU are voie să lucreze niciodată."
            )
            
            if is_titular and len(allowed_shifts) < 4:
                st.warning("⚠️ Atenție! E recomandat ca titularii să aibă bifate toate cele 4 ture pentru a putea susține corect baza orarului!")
        
        with c1:
            st.markdown("✅ **Zile Libere**")
            off_days = st.multiselect(
                "❌ Complet Liber",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("Liber", []) if 1 <= d <= num_zile],
                key=f"off_{person}"
            )
            
        with c2:
            st.markdown("✅ **Zile Preferate (VREAU)**")
            t1_days = st.multiselect(
                "☀️ Zile cu T1",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("T1", []) if 1 <= d <= num_zile],
                key=f"t1_{person}"
            )
            t2_days = st.multiselect(
                "🌤️ Zile cu T2",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("T2", []) if 1 <= d <= num_zile],
                key=f"t2_{person}"
            )
            t3_days = st.multiselect(
                "🌙 Zile cu T3",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("T3", []) if 1 <= d <= num_zile],
                key=f"t3_{person}"
            )
            pzu_days = st.multiselect(
                "🏥 Zile cu PZU",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("PZU", []) if 1 <= d <= num_zile],
                key=f"pzu_{person}"
            )
            
        with c3:
            st.markdown("🚫 **Zile Nedorite (NU VREAU)**")
            not1_days = st.multiselect(
                "⛔ Zile FĂRĂ T1",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("No_T1", []) if 1 <= d <= num_zile],
                key=f"not1_{person}"
            )
            not2_days = st.multiselect(
                "⛔ Zile FĂRĂ T2",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("No_T2", []) if 1 <= d <= num_zile],
                key=f"not2_{person}"
            )
            not3_days = st.multiselect(
                "⛔ Zile FĂRĂ T3",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("No_T3", []) if 1 <= d <= num_zile],
                key=f"not3_{person}"
            )
            nopzu_days = st.multiselect(
                "⛔ Zile FĂRĂ PZU",
                options=list(range(1, num_zile + 1)),
                default=[d for d in p_prefs.get("No_PZU", []) if 1 <= d <= num_zile],
                key=f"nopzu_{person}"
            )
            
        preferences[person] = {
            "Liber": off_days,
            "T1": t1_days,
            "T2": t2_days,
            "T3": t3_days,
            "PZU": pzu_days,
            "No_T1": not1_days,
            "No_T2": not2_days,
            "No_T3": not3_days,
            "No_PZU": nopzu_days,
            "Allowed_Shifts": allowed_shifts,
            "Is_Titular": is_titular
        }
        st.markdown("---")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 💾 Salvare Preset Curent")
c_save1, c_save2 = st.columns([2, 1])

with c_save1:
    default_name = selected_preset_name if selected_preset_name != "-- Fără Preset --" else ""
    new_preset_name = st.text_input("Nume pentru preset (ex: Orar August, Concedii Vara, etc.)", value=default_name)

with c_save2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvează Datele", use_container_width=True):
        if new_preset_name.strip():
            all_presets[new_preset_name.strip()] = {
                "luna": luna,
                "an": an,
                "preferences": preferences,
                "weekends": weekend_assignments,
                "holidays": {
                    "selected_days": holiday_days,
                    "assignments": holiday_assignments
                }
            }
            storage.save_json(PRESETS_FILE, all_presets)
            st.success(f"✅ Presetul '{new_preset_name.strip()}' a fost salvat cu succes!")
        else:
            st.error("Te rog introdu un nume valid pentru preset.")

st.markdown("---")

c_s1, c_gen, c_s2 = st.columns([1, 2, 1])
with c_gen:
    generate_clicked = st.button("🚀 Generează Orar", type="primary", use_container_width=True)

if generate_clicked or 'locked_shifts_run' in st.session_state:
    if len(people) < 4:
        st.error("Aplicația necesită cel puțin 4 persoane pentru a acoperi 4 ture zilnice.")
    else:
        # VALIDARE CONCEDII VS WEEKEND
        day_to_weekend = {}
        for i, wk_days in enumerate(weekends):
            for day in wk_days:
                day_to_weekend[day] = i

        for p, prefs in preferences.items():
            for off_day in prefs.get("Liber", []):
                w_idx = day_to_weekend.get(off_day)
                if w_idx is not None and p in weekend_assignments.get(w_idx, []):
                    st.warning(f"⚠️ **Atenție:** Ai selectat că {p} dorește zi liberă pe data de {off_day}, dar l-ai alocat și ca titular pentru Weekend-ul {w_idx + 1}! Ziua liberă va fi ignorată automat pentru a acoperi weekendul.")
                    
        invalid_weekends = []
        # Check previous month history
        prev_month = luna - 1 if luna > 1 else 12
        prev_year = an if luna > 1 else an - 1
        prev_fname = f"orar_{prev_year}_{prev_month:02d}.csv"
        
        prev_month_data = None
        df_prev = storage.load_history_df(prev_fname)
        if df_prev is not None:
            if not df_prev.empty:
                last_row = df_prev.iloc[-1]
                last_day_shifts = {}
                for col in ["Tura 1", "Tura 2", "Tura 3", "PZU"]:
                    if col in df_prev.columns:
                        worker = str(last_row.get(col, "-")).replace(" (!)", "")
                        if worker != "-":
                            shift_key = "PZU" if col == "PZU" else f"T{col.split()[-1]}"
                            last_day_shifts[worker] = shift_key
                            
                _, prev_num_zile = calendar.monthrange(prev_year, prev_month)
                last_day_weekday = calendar.weekday(prev_year, prev_month, prev_num_zile)
                
                last_weekend_workers = []
                if last_day_weekday == 6: # Sunday
                    if len(df_prev) >= 2:
                        sat_row = df_prev.iloc[-2]
                        sun_row = df_prev.iloc[-1]
                        workers_set = set()
                        for col in ["Tura 1", "Tura 2", "PZU"]:
                            if col in df_prev.columns:
                                w_sat = str(sat_row.get(col, "-")).replace(" (!)", "")
                                w_sun = str(sun_row.get(col, "-")).replace(" (!)", "")
                                if w_sat != "-": workers_set.add(w_sat)
                                if w_sun != "-": workers_set.add(w_sun)
                        last_weekend_workers = list(workers_set)
                        
                prev_month_data = {
                    "last_day_shifts": last_day_shifts,
                    "last_weekend_workers": last_weekend_workers
                }
                st.info(f"ℹ️ Am găsit orarul definitiv pentru {prev_month:02d}/{prev_year}. S-au aplicat automat regulile de odihnă (T2/T3/Weekend) pentru primele zile din luna curentă!")
        else:
            st.warning(f"⚠️ Nu a fost găsit un orar definitiv salvat pentru {prev_month:02d}/{prev_year}. Regulile de continuitate pentru primele zile din luna curentă NU vor fi aplicate.")

        # Validate weekends
        invalid_weekends = []
        for w_idx, persons in weekend_assignments.items():
            if len(persons) > 0 and not (3 <= len(persons) <= 6):
                invalid_weekends.append(str(w_idx + 1))
                
        if invalid_weekends:
            st.error(f"❌ Eroare: Ai selectat un număr invalid de persoane pentru Weekend-ul {', '.join(invalid_weekends)}. Trebuie să selectezi între 3 și 6 persoane care vor acoperi turele de weekend (sau lasă gol)!")
        else:
            with st.spinner(f"⏳ Se calculează cel mai echitabil orar... (poate dura până la {timp_gandire}s)"):
                past_shift_counts = {p: {"T1": 0, "T2": 0, "T3": 0, "PZU": 0, "T3_Weekend": 0, "T2_Vineri": 0} for p in people}
                
                # Load from base history
                ISTORIC_BAZA_FILE = "istoric_baza.csv"
                base_df = storage.load_df(ISTORIC_BAZA_FILE)
                if base_df is not None:
                    try:
                        for _, row in base_df.iterrows():
                            p = row.get("Angajat", "")
                            if p in past_shift_counts:
                                past_shift_counts[p]["T1"] += int(row.get("T1", 0))
                                past_shift_counts[p]["T2"] += int(row.get("T2", 0))
                                past_shift_counts[p]["T3"] += int(row.get("T3", 0))
                                past_shift_counts[p]["PZU"] += int(row.get("PZU", 0))
                                past_shift_counts[p]["T3_Weekend"] += int(row.get("T3_Weekend", 0))
                                past_shift_counts[p]["T2_Vineri"] += int(row.get("T2_Vineri", 0))
                    except:
                        pass
                
                # Load from all saved histories
                hist_files = storage.list_history_files()
                for hf in hist_files:
                    try:
                        h_df = storage.load_history_df(hf)
                        for _, row in h_df.iterrows():
                            ziua = str(row.get("Ziua", ""))
                            t1 = str(row.get("Tura 1", "")).replace(" (!)", "")
                            t2 = str(row.get("Tura 2", "")).replace(" (!)", "")
                            t3 = str(row.get("Tura 3", "")).replace(" (!)", "")
                            pzu = str(row.get("PZU", "")).replace(" (!)", "")
                            
                            if t1 in past_shift_counts: past_shift_counts[t1]["T1"] += 1
                            if t2 in past_shift_counts: 
                                past_shift_counts[t2]["T2"] += 1
                                if ziua == "Vineri": past_shift_counts[t2]["T2_Vineri"] += 1
                            if t3 in past_shift_counts: 
                                past_shift_counts[t3]["T3"] += 1
                                if ziua in ["Sambata", "Duminica"]: past_shift_counts[t3]["T3_Weekend"] += 1
                            if pzu in past_shift_counts: past_shift_counts[pzu]["PZU"] += 1
                    except:
                        pass

                try:
                    locked = st.session_state.get('locked_shifts_run')
                    hints = st.session_state.get('hints_run')
                    df, penalty, status, violation_details = solve_schedule(people, an, luna, preferences, weekend_assignments, prev_month_data, holiday_assignments, past_shift_counts, timp_gandire, locked, hints)
                    st.session_state['violation_details'] = violation_details
                    
                    if 'locked_shifts_run' in st.session_state: del st.session_state['locked_shifts_run']
                    if 'hints_run' in st.session_state: del st.session_state['hints_run']
                except ValueError as ve:
                    st.error(str(ve))
                except Exception as e:
                    import traceback
                    st.error(f"Eroare internă în algoritm:\n\n{traceback.format_exc()}")
                    df = None
                
                if df is not None:
                    st.session_state['schedule_df'] = df
                    st.session_state['schedule_penalty'] = penalty
                    st.success("✅ Orar generat cu succes! (Constraint Programming FEASIBLE/OPTIMAL)")
                else:
                    st.session_state['schedule_df'] = None
                    st.session_state['schedule_penalty'] = 0
                    st.session_state['violation_details'] = []
                    st.error("❌ Nu s-a putut găsi nicio soluție validă. Vă rugăm să relaxați cerințele.")
                    
if st.session_state.get('schedule_df') is not None:
    df = st.session_state['schedule_df']
    penalty = st.session_state.get('schedule_penalty', 0)
    
    # 💯 Happiness Score
    if penalty == 0:
        score, msg, color = 10.0, "Perfect - Toate regulile și echilibrările sunt perfect respectate!", "green"
    elif penalty < 80000:
        score, msg, color = 9.5, "Excelent - Orar extrem de echilibrat (mici permutări invizibile).", "green"
    elif penalty < 250000:
        score, msg, color = 8.0, "Foarte Bun - Câteva compromisuri minore de odihnă.", "#d4b000"
    elif penalty < 600000:
        score, msg, color = 6.0, "Acceptabil - Compromisuri necesare (ex: s-a ignorat o cerință de zi liberă).", "orange"
    elif penalty < 1000000:
        score, msg, color = 4.0, "Slab - Orar supraîncărcat, reguli majore încălcate.", "red"
    else:
        score, msg, color = 2.0, "Critic - Orarul are GĂURI (Ture Neacoperite marcare cu GOL)!", "red"
        
    st.markdown("---")
    st.markdown(f"### 💯 Scorul de Fericire a Echipei: <span style='color:{color}'>{score}/10</span>", unsafe_allow_html=True)
    st.progress(score / 10.0)
    st.caption(f"_{msg}_")
    
    violation_details = st.session_state.get('violation_details', [])
    if penalty > 0 and violation_details:
        with st.expander("🔍 De ce nu am luat nota 10? Vezi compromisurile făcute de algoritm:", expanded=False):
            st.info("Aplicația a găsit un orar valid, dar pentru a acoperi toate turele, a fost obligată să ignore următoarele reguli (în funcție de gravitate):")
            for desc in violation_details:
                st.markdown(f"- {desc}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    c_s1, c_save_def, c_s2 = st.columns([1, 2, 1])
    with c_save_def:
        if st.button(f"🔒 Salvează ca Orar Definitiv pentru {luna:02d}/{an}", use_container_width=True):
            storage.save_history_df(f"orar_{an}_{luna:02d}.csv", df)
            
            storage.save_history_json(f"orar_{an}_{luna:02d}.json", {
                "preferences": preferences,
                "weekends": weekend_assignments,
                "holidays": {
                    "selected_days": holiday_days,
                    "assignments": holiday_assignments
                }
            })
                
            st.success(f"✅ Orarul a fost blocat și salvat în istoric! Se va ține cont de el pentru luna următoare.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Apply Pandas Styling to match Excel
    def colorize_shifts(val):
        clean_val = str(val).replace(" (!)", "")
        if clean_val == "GOL":
            return 'background-color: #ffcccc; color: red; font-weight: bold;'
        
        names = [n.strip() for n in clean_val.split(",")]
        if len(names) > 0 and names[0] in people:
            hex_color = get_color_for_name(names[0], people, custom_colors)
            return f'background-color: #{hex_color}; color: black;'
        return ''
        
    st.markdown("### 📅 Orar Detaliat pe Săptămâni")
    
    if "Saptamana" in df.columns:
        weeks = df["Saptamana"].unique()
        for w in weeks:
            st.markdown(f"<h4 style='text-align: center;'>Săptămâna {w}</h4>", unsafe_allow_html=True)
            week_df = df[df["Saptamana"] == w]
            styler = week_df.style.map(colorize_shifts, subset=["Tura 1", "Tura 2", "Tura 3", "PZU"])
            styler = styler.set_properties(**{'text-align': 'center'})
            st.dataframe(styler, use_container_width=True, hide_index=True)
    else:
        styler = df.style.map(colorize_shifts, subset=["Tura 1", "Tura 2", "Tura 3", "PZU"])
        styler = styler.set_properties(**{'text-align': 'center'})
        st.dataframe(styler, use_container_width=True, hide_index=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("✏️ Editează Manual Turele (Locking)"):
        st.info("💡 Din motive tehnice ale platformei, tabelul editabil nu poate fi colorat. Editează aici numele (sau scrie 'GOL'), apoi apasă pe Recalculează de mai jos. Noul orar generat va apărea frumos colorat mai sus!")
        
        with st.form("form_editor_orar"):
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True, key="tabel_editabil")
            
            submitted = st.form_submit_button("🔄 Recalculează Păstrând Modificările Manuale", type="secondary", use_container_width=True)
            if submitted:
                locked_shifts = {}
                hints = {}
                for idx in range(len(df)):
                    for col in ["Tura 1", "Tura 2", "Tura 3", "PZU"]:
                        original_val = str(df.iloc[idx][col]).replace(" (!)", "").strip()
                        new_val = str(edited_df.iloc[idx][col]).replace(" (!)", "").strip()
                        
                        d = idx
                        t_idx = ["Tura 1", "Tura 2", "Tura 3", "PZU"].index(col)
                        
                        if original_val != new_val:
                            if str(d) not in locked_shifts: locked_shifts[str(d)] = {}
                            locked_shifts[str(d)][str(t_idx)] = new_val
                        else:
                            if str(d) not in hints: hints[str(d)] = {}
                            hints[str(d)][str(t_idx)] = original_val
                            
                st.session_state['locked_shifts_run'] = locked_shifts
                st.session_state['hints_run'] = hints
                st.rerun()
    
    # Stats per person
    st.markdown("### 📊 Statistici Ture pe Persoană (Luna Curentă)")
    
    stats_data = []
    for person in people:
        p_stats = {"Angajat": person, "T1": 0, "T2": 0, "T3": 0, "PZU": 0, "Total": 0}
        for _, row in df.iterrows():
            # Remove the forced marker when calculating stats
            t1_val = str(row.get("Tura 1", "")).replace(" (!)", "")
            t2_val = str(row.get("Tura 2", "")).replace(" (!)", "")
            t3_val = str(row.get("Tura 3", "")).replace(" (!)", "")
            pzu_val = str(row.get("PZU", "")).replace(" (!)", "")
            
            if person in [x.strip() for x in t1_val.split(",")]: p_stats["T1"] += 1
            if person in [x.strip() for x in t2_val.split(",")]: p_stats["T2"] += 1
            if person in [x.strip() for x in t3_val.split(",")]: p_stats["T3"] += 1
            if person in [x.strip() for x in pzu_val.split(",")]: p_stats["PZU"] += 1
        p_stats["Total"] = p_stats["T1"] + p_stats["T2"] + p_stats["T3"] + p_stats["PZU"]
        stats_data.append(p_stats)
        
    stats_df = pd.DataFrame(stats_data).sort_values("Total", ascending=False)
    styler_stats = stats_df.style.set_properties(**{'text-align': 'center'})
    st.dataframe(styler_stats, use_container_width=True, hide_index=True)
    
    # Optional: Pastram un mic grafic doar pentru Total
    st.bar_chart(stats_df.set_index("Angajat")["Total"])
    
    st.markdown("---")
    st.markdown("### 📈 Analiză și Oboseală (Heatmap)")
    st.info("Această hartă îți arată vizual aglomerarea. **Alb** = Liber | **Albastru** = Tură de Zi | **Roșu** = Tură de Noapte (T3)")
    
    heatmap_data = []
    for d in range(num_zile):
        for p in people:
            val = 0 # Liber
            t1 = str(edited_df.iloc[d].get("Tura 1", "")).replace(" (!)", "")
            t2 = str(edited_df.iloc[d].get("Tura 2", "")).replace(" (!)", "")
            t3 = str(edited_df.iloc[d].get("Tura 3", "")).replace(" (!)", "")
            pzu = str(edited_df.iloc[d].get("PZU", "")).replace(" (!)", "")
            
            t1_list = [x.strip() for x in t1.split(",")]
            t2_list = [x.strip() for x in t2.split(",")]
            t3_list = [x.strip() for x in t3.split(",")]
            pzu_list = [x.strip() for x in pzu.split(",")]
            
            if p in t1_list or p in t2_list or p in pzu_list:
                val = 1
            elif p in t3_list:
                val = 2
                
            heatmap_data.append({"Ziua": d+1, "Angajat": p, "Status": val})
            
    import altair as alt
    hm_df = pd.DataFrame(heatmap_data)
    
    chart = alt.Chart(hm_df).mark_rect().encode(
        x=alt.X('Ziua:O', title='Ziua din lună', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Angajat:O', title='Angajat'),
        color=alt.Color('Status:Q', 
                        scale=alt.Scale(domain=[0, 1, 2], range=['#f0f2f6', '#3498db', '#e74c3c']),
                        legend=None),
        tooltip=['Angajat', 'Ziua', 'Status']
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)
    
    # Export buttons
    st.markdown("### 📥 Export")
    c_s1, c_dl1, c_dl2, c_s2 = st.columns([1, 2, 2, 1])
    
    with c_dl1:
        st.download_button(
            label="📄 Descarcă Excel (.xlsx)",
            data=get_excel_download(df, stats_df, custom_colors),
            file_name=f"orar_{luna}_{an}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with c_dl2:
        st.download_button(
            label="📄 Descarcă CSV",
            data=get_csv_download(df),
            file_name=f"orar_{luna}_{an}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("---")
    st.markdown("## 📅 Istoric și Export Multi-Lună")
    history_files = [f for f in os.listdir(HISTORY_DIR) if f.startswith("orar_") and f.endswith(".csv")]
    if not history_files:
        st.info("Nu există orare definitive salvate în istoric.")
    else:
        # Extract months
        available_months = sorted([f.replace("orar_", "").replace(".csv", "") for f in history_files], reverse=True)
        
        selected_months = st.multiselect("Selectează lunile pentru export cumulativ (Excel pe sheet-uri):", options=available_months)
        if selected_months:
            # We need to compute combined stats and prepare df dict
            df_dict = {}
            dfs_to_concat = []
            
            for m in selected_months:
                fpath = os.path.join(HISTORY_DIR, f"orar_{m}.csv")
                m_df = pd.read_csv(fpath)
                sheet_name = m.replace("_", "-")
                df_dict[sheet_name] = m_df
                dfs_to_concat.append(m_df)
                
            combined_df = pd.concat(dfs_to_concat, ignore_index=True)
            
            stats_data_multi = []
            for person in people:
                p_stats = {"Angajat": person, "T1": 0, "T2": 0, "T3": 0, "PZU": 0, "Total": 0}
                for _, row in combined_df.iterrows():
                    t1_val = str(row.get("Tura 1", "")).replace(" (!)", "")
                    t2_val = str(row.get("Tura 2", "")).replace(" (!)", "")
                    t3_val = str(row.get("Tura 3", "")).replace(" (!)", "")
                    pzu_val = str(row.get("PZU", "")).replace(" (!)", "")
                    
                    if person in [x.strip() for x in t1_val.split(",")]: p_stats["T1"] += 1
                    if person in [x.strip() for x in t2_val.split(",")]: p_stats["T2"] += 1
                    if person in [x.strip() for x in t3_val.split(",")]: p_stats["T3"] += 1
                    if person in [x.strip() for x in pzu_val.split(",")]: p_stats["PZU"] += 1
                p_stats["Total"] = p_stats["T1"] + p_stats["T2"] + p_stats["T3"] + p_stats["PZU"]
                stats_data_multi.append(p_stats)
                
            combined_stats_df = pd.DataFrame(stats_data_multi).sort_values("Total", ascending=False)
            
            st.dataframe(combined_stats_df, use_container_width=True, hide_index=True)
            
            from export_utils import get_multi_month_excel_download
            st.download_button(
                label="📥 Descarcă Excel Multi-Lună",
                data=get_multi_month_excel_download(df_dict, combined_stats_df, people, custom_colors),
                file_name=f"istoric_orar_cumulat.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

if __name__ == "__main__":
    import sys
    from streamlit.web import cli as stcli
    import streamlit.runtime
    
    if not streamlit.runtime.exists():
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())
