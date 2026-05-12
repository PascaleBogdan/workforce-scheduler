import pandas as pd
from ortools.sat.python import cp_model
import calendar

def solve_schedule(people, year, month, preferences, weekend_assignments, prev_month_data=None, holiday_assignments=None, past_shift_counts=None, timp_gandire=30.0, locked_shifts=None, hints=None):
    """
    people: list of names
    year: int
    month: int
    preferences: dict {person_name: {"off_days": [1, 2, ...], "pref_shift": "T1"}}
    weekend_assignments: dict {weekend_index: [list of names allowed to work]}
    prev_month_data: dict {"last_day_shifts": {"Name": "T3"}, "last_weekend_workers": ["Name1", "Name2"]}
    past_shift_counts: dict {"Name": {"T1": 5, "T2": 4, "T3": 3, "PZU": 2, "T3_Weekend": 1, "T2_Vineri": 0}}
    locked_shifts: dict {"day_index": {"shift_index": "Name"}}
    hints: dict {"day_index": {"shift_index": "Name"}}
    """
    model = cp_model.CpModel()
    
    # Calculate days in month and start day
    first_day_weekday, num_zile = calendar.monthrange(year, month)
    
    # T1, T2, T3, PZU
    ture = ["T1", "T2", "T3", "PZU"]
    num_ture = len(ture)
    num_people = len(people)
    
    titulari_idx = []
    dubluri_idx = []
    for p, name in enumerate(people):
        pref_dict = preferences.get(name, {})
        is_titular = pref_dict.get("Is_Titular", p < 9)
        if is_titular:
            titulari_idx.append(p)
        else:
            dubluri_idx.append(p)
            
    # 1. Variables
    # x[d, p, t] = 1 if person p works shift t on day d
    x = {}
    for d in range(num_zile):
        for p in range(num_people):
            for t in range(num_ture):
                x[(d, p, t)] = model.NewBoolVar(f"x_d{d}_p{p}_t{t}")
                
    penalties = []
    tracked_violations = []
    
    def add_penalty(weight, var, desc=None):
        penalties.append(weight * var)
        if desc:
            tracked_violations.append((var, weight, desc))
    
    # 2. Hard Constraints
    
    # A. Titular vs Dublură (PZU max 1, rest max 2)
    for d in range(num_zile):
        for t in range(num_ture):
            covered_titulari = sum(x[(d, p, t)] for p in titulari_idx)
            covered_dubluri = sum(x[(d, p, t)] for p in dubluri_idx)
            
            covered_total = covered_titulari + covered_dubluri
            
            if t == 3: # PZU
                # PZU are strict maxim 1 persoană (Titular sau Dublură)
                model.Add(covered_total <= 1)
                
                missing_pzu = model.NewBoolVar(f"missing_pzu_d{d}")
                model.Add(covered_total == 0).OnlyEnforceIf(missing_pzu)
                model.Add(covered_total == 1).OnlyEnforceIf(missing_pzu.Not())
                add_penalty(1000000, missing_pzu, f"Tură PZU descoperită (GOL) pe data de {d+1}/{month}")
                
            else: # T1, T2, T3
                # Maxim 1 titular per tură (titularii formează baza)
                model.Add(covered_titulari <= 1)
                
                # Maxim 1 dublură per tură
                model.Add(covered_dubluri <= 1)
                
                missing_any = model.NewBoolVar(f"missing_any_d{d}_t{t}")
                model.Add(covered_total == 0).OnlyEnforceIf(missing_any)
                model.Add(covered_total >= 1).OnlyEnforceIf(missing_any.Not())
                add_penalty(1000000, missing_any, f"Tură T{t+1} complet descoperită (GOL) pe {d+1}/{month}")
                
                missing_titular = model.NewBoolVar(f"missing_titular_d{d}_t{t}")
                model.Add(covered_titulari == 0).OnlyEnforceIf(missing_titular)
                model.Add(covered_titulari == 1).OnlyEnforceIf(missing_titular.Not())
                add_penalty(100000, missing_titular, f"Tură T{t+1} acoperită DOAR de Dublură (fără Titular) pe {d+1}/{month}")
            
    # B. A person works at most one shift per day
    for d in range(num_zile):
        for p in range(num_people):
            model.AddAtMostOne(x[(d, p, t)] for t in range(num_ture))
            
    # B.6 Locked Shifts (Manual Overrides)
    if locked_shifts:
        for d_str, shifts in locked_shifts.items():
            d = int(d_str)
            if 0 <= d < num_zile:
                for t_idx, person_name in shifts.items():
                    t = int(t_idx)
                    if person_name in people:
                        p = people.index(person_name)
                        model.Add(x[(d, p, t)] == 1)
                    elif person_name.upper() == "GOL" or person_name == "":
                        for p in range(num_people):
                            model.Add(x[(d, p, t)] == 0)
                    else:
                        names = [n.strip() for n in person_name.split(",")]
                        for n in names:
                            if n in people:
                                p = people.index(n)
                                model.Add(x[(d, p, t)] == 1)
                            else:
                                raise ValueError(f"Eroare la blocarea turelor: Numele '{n}' introdus pentru ziua {d+1} nu există în lista de angajați! Te rog verifică dacă l-ai scris corect.")
            
    # B.5 Cross-month boundary constraints
    if prev_month_data:
        last_day_shifts = prev_month_data.get("last_day_shifts", {})
        last_weekend_workers = prev_month_data.get("last_weekend_workers", [])
        
        for p, name in enumerate(people):
            shift = last_day_shifts.get(name)
            # Daca a facut T2 sau T3 in ultima zi din luna trecuta, primele zile sunt libere
            if shift == "T3":
                for t in range(num_ture):
                    model.Add(x[(0, p, t)] == 0)
                if 1 < num_zile:
                    for t in range(num_ture):
                        model.Add(x[(1, p, t)] == 0)
            elif shift == "T2":
                for t in range(num_ture):
                    model.Add(x[(0, p, t)] == 0)
            
            # Continuare penalizare pentru T1 sau PZU consecutiv la granita dintre luni
            if shift == "T1":
                viol_t1_prev = model.NewBoolVar(f"viol_t1_prev_p{p}")
                model.Add(x[(0, p, 0)] <= viol_t1_prev)
                add_penalty(20000, viol_t1_prev, f"{name}: Fără pauză după T1 la trecerea dintre luni")
            if shift == "PZU":
                viol_pzu_prev = model.NewBoolVar(f"viol_pzu_prev_p{p}")
                model.Add(x[(0, p, 3)] <= viol_pzu_prev)
                add_penalty(20000, viol_pzu_prev, f"{name}: PZU consecutiv la trecerea dintre luni")
                    
            # Daca a facut ultimul weekend si luna s-a terminat duminica, prima zi (Luni) si a doua (Marti) libere
            if name in last_weekend_workers:
                if 0 < num_zile:
                    viol_mon_prev = model.NewBoolVar(f"viol_mon_prev_p{p}")
                    model.Add(sum(x[(0, p, t)] for t in range(num_ture)) <= viol_mon_prev)
                    add_penalty(500000, viol_mon_prev, f"{name}: A lucrat Luni după lucrul în ultimul weekend din luna trecută")
                if 1 < num_zile:
                    viol_tue_prev = model.NewBoolVar(f"viol_tue_prev_p{p}")
                    model.Add(sum(x[(1, p, t)] for t in range(num_ture)) <= viol_tue_prev)
                    add_penalty(20000, viol_tue_prev, f"{name}: A lucrat Marți după lucrul în ultimul weekend din luna trecută")
            
    # 3. Soft Constraints
    
    # C. După T2 -> ziua următoare liber
    T2_idx = 1
    violations = {}
    for d in range(num_zile):
        for p in range(num_people):
            violations[(d, p)] = []
            
    for d in range(num_zile - 1):
        for p in range(num_people):
            viol_t2 = model.NewBoolVar(f"viol_t2_d{d}_p{p}")
            sum_next_day = sum(x[(d+1, p, t)] for t in range(num_ture))
            model.Add(x[(d, p, T2_idx)] + sum_next_day <= 1 + viol_t2)
            add_penalty(20000, viol_t2, f"{people[p]}: Fără zi liberă obligatorie după T2 (în data de {d+1}/{month})")
            violations[(d+1, p)].append(viol_t2)
            
    # D. După T3 -> 2 zile următoare libere
    T3_idx = 2
    for d in range(num_zile - 1):
        for p in range(num_people):
            viol_t3 = model.NewBoolVar(f"viol_t3_d{d}_p{p}")
            sum_next_days = sum(x[(d+1, p, t)] for t in range(num_ture))
            if d + 2 < num_zile:
                sum_next_days += sum(x[(d+2, p, t)] for t in range(num_ture))
                
            model.Add(2 * x[(d, p, T3_idx)] + sum_next_days <= 2 + 2 * viol_t3)
            add_penalty(30000, viol_t3, f"{people[p]}: Fără cele 2 zile libere obligatorii după T3 (în data de {d+1}/{month})")
            violations[(d+1, p)].append(viol_t3)
            if d + 2 < num_zile:
                violations[(d+2, p)].append(viol_t3)
                
            # Muncă obligatorie după liberele de la Tura 3
            if d + 3 < num_zile:
                d_work = d + 3
                # Verificăm dacă are "Liber" cerut pe ziua respectivă (d_work e 0-indexed, Liber e 1-indexed)
                is_liber_requested = (d_work + 1) in preferences.get(people[p], {}).get("Liber", [])
                
                # Verificăm dacă pică în weekend, iar persoana NU e pe lista de weekend
                is_weekend = ((first_day_weekday + d_work) % 7) in [5, 6]
                is_weekend_exempt = False
                if is_weekend:
                    wk_idx_local = 0
                    for day_iter in range(num_zile):
                        wd_iter = (first_day_weekday + day_iter) % 7
                        if wd_iter in [5, 6]:
                            if day_iter == d_work:
                                allowed_this_wk = weekend_assignments.get(wk_idx_local, [])
                                if allowed_this_wk and people[p] not in allowed_this_wk:
                                    is_weekend_exempt = True
                                break
                            if wd_iter == 6:
                                wk_idx_local += 1
                
                if not is_liber_requested and not is_weekend_exempt:
                    viol_work_after_t3 = model.NewBoolVar(f"viol_work_after_t3_d{d}_p{p}")
                    sum_work = sum(x[(d_work, p, t)] for t in range(num_ture))
                    # x == 1 si sum_work == 0 -> viol == 1
                    model.Add(x[(d, p, T3_idx)] - sum_work <= viol_work_after_t3)
                    add_penalty(20000, viol_work_after_t3, f"{people[p]}: Nu a fost pus la muncă după liberele de T3 (pe {d_work+1}/{month})")
            
    # D2. Evitare Ture Consecutive de același tip (T1, PZU)
    T1_idx = 0
    PZU_idx = 3
    for d in range(num_zile - 1):
        for p in range(num_people):
            # T1
            viol_t1_cons = model.NewBoolVar(f"viol_t1_cons_d{d}_p{p}")
            model.Add(x[(d, p, T1_idx)] + x[(d+1, p, T1_idx)] <= 1 + viol_t1_cons)
            add_penalty(20000, viol_t1_cons, f"{people[p]}: Ture T1 consecutive pe {d+1} și {d+2}")
            violations[(d+1, p)].append(viol_t1_cons)
            
            # PZU
            viol_pzu_cons = model.NewBoolVar(f"viol_pzu_cons_d{d}_p{p}")
            model.Add(x[(d, p, PZU_idx)] + x[(d+1, p, PZU_idx)] <= 1 + viol_pzu_cons)
            add_penalty(20000, viol_pzu_cons, f"{people[p]}: Ture PZU consecutive pe {d+1} și {d+2}")
            violations[(d+1, p)].append(viol_pzu_cons)
            
    # E. Balanțare Avansată: Minim 2 ture per tip, Maxim 5 ture per tip (Max 4 pentru T3)
    for p in range(num_people):
        for t_idx in range(num_ture):
            total_t = sum(x[(d, p, t_idx)] for d in range(num_zile))
            
            # Limita maximă (5 pentru T1, T2, PZU; 4 pentru T3)
            max_limit = 4 if t_idx == 2 else 5
            viol_max = model.NewIntVar(0, num_zile, f"viol_max_p{p}_t{t_idx}")
            model.Add(total_t <= max_limit + viol_max)
            add_penalty(100, viol_max)
            
            # Limita minimă (2 pentru toate turele)
            viol_min = model.NewIntVar(0, num_zile, f"viol_min_p{p}_t{t_idx}")
            model.Add(total_t >= 2 - viol_min)
            add_penalty(100, viol_min)
            
    # E2. Minim 2 ture, Maxim 5 ture per persoană PE SĂPTĂMÂNĂ (indiferent de tipul turei)
    weeks = []
    current_week = []
    for d in range(num_zile):
        current_week.append(d)
        if (first_day_weekday + d) % 7 == 6 or d == num_zile - 1:
            weeks.append(current_week)
            current_week = []
            
    for w_idx, w_days in enumerate(weeks):
        for p in range(num_people):
            shifts_in_week = sum(x[(d, p, t)] for d in w_days for t in range(num_ture))
            
            # Max 5
            viol_max_wk = model.NewIntVar(0, 7, f"viol_max_wk{w_idx}_p{p}")
            model.Add(shifts_in_week <= 5 + viol_max_wk)
            add_penalty(50000, viol_max_wk, f"{people[p]}: A depășit 5 ture în săptămâna {w_idx+1}")
            
            # Min 2 (adaptat la posibilitățile persoanei)
            possible_days = 0
            for d in w_days:
                if (d + 1) in preferences.get(people[p], {}).get("Liber", []):
                    continue
                # Verificăm dacă e weekend și dacă persoana e pe lista de weekend
                is_wkd = ((first_day_weekday + d) % 7) in [5, 6]
                if is_wkd:
                    wk_idx_local = 0
                    for day_iter in range(num_zile):
                        if day_iter == d: break
                        if ((first_day_weekday + day_iter) % 7) == 6:
                            wk_idx_local += 1
                    
                    allowed_this_wk = weekend_assignments.get(wk_idx_local, [])
                    if allowed_this_wk and people[p] not in allowed_this_wk:
                        continue
                possible_days += 1
                
            required_min = min(2, possible_days)
            if required_min > 0:
                viol_min_wk = model.NewIntVar(0, 7, f"viol_min_wk{w_idx}_p{p}")
                model.Add(shifts_in_week >= required_min - viol_min_wk)
                add_penalty(50000, viol_min_wk, f"{people[p]}: Nu a atins minimul de {required_min} ture în săptămâna {w_idx+1}")
        
    # F. Zile Libere și Preferințe (Soft Constraints Extreme)
    for p, name in enumerate(people):
        if name in preferences:
            pref_dict = preferences[name]
            
            # Zile Libere (Penalizare 100.000)
            for d_one_indexed in pref_dict.get("Liber", []):
                d = d_one_indexed - 1
                if 0 <= d < num_zile:
                    viol_liber = model.NewBoolVar(f"viol_liber_d{d}_p{p}")
                    # Suma turelor trebuie să fie 0, sau viol_liber e 1
                    model.Add(sum(x[(d, p, t)] for t in range(num_ture)) <= viol_liber)
                    add_penalty(100000, viol_liber, f"{name}: Refuzare cerere zi Liberă pe {d+1}/{month}")
                    
            # Preferințe de Tură (Penalizare 40.000)
            for t_name in ["T1", "T2", "T3", "PZU"]:
                if t_name in ture:
                    t_idx = ture.index(t_name)
                    for d_one_indexed in pref_dict.get(t_name, []):
                        d = d_one_indexed - 1
                        if 0 <= d < num_zile:
                            viol_pref = model.NewBoolVar(f"viol_pref_{t_name}_d{d}_p{p}")
                            # x[(d, p, t_idx)] trebuie să fie 1, sau viol_pref e 1
                            model.Add(x[(d, p, t_idx)] >= 1 - viol_pref)
                            add_penalty(40000, viol_pref, f"{name}: Ignorare preferință {t_name} pe {d+1}/{month}")
                            
            # Ture Nedorite specifice pe zile (Penalizare 100.000)
            for t_name in ["T1", "T2", "T3", "PZU"]:
                if t_name in ture:
                    t_idx = ture.index(t_name)
                    no_key = f"No_{t_name}"
                    for d_one_indexed in pref_dict.get(no_key, []):
                        d = d_one_indexed - 1
                        if 0 <= d < num_zile:
                            viol_nedorit = model.NewBoolVar(f"viol_nedorit_{t_name}_d{d}_p{p}")
                            model.Add(x[(d, p, t_idx)] <= viol_nedorit)
                            add_penalty(100000, viol_nedorit, f"{name}: A primit tura nedorită ({t_name}) pe {d+1}/{month}")
                            violations[(d, p)].append(viol_nedorit)
                            
            # F.2 Ture Permise (Matricea de permisiuni)
            allowed = pref_dict.get("Allowed_Shifts", ["T1", "T2", "T3", "PZU"])
            for t_idx, t_name in enumerate(ture):
                if t_name not in allowed:
                    for d in range(num_zile):
                        model.Add(x[(d, p, t_idx)] == 0)
                        
    # H. Preferences - Asignare exactă pe weekend-uri (Hard Constraint)
    day_to_weekend = {}
    weekend_idx = 0
    for d in range(num_zile):
        current_weekday = (first_day_weekday + d) % 7
        if current_weekday in [5, 6]:
            day_to_weekend[d] = weekend_idx
            if current_weekday == 6:
                weekend_idx += 1
                
    # Indices for shifts
    # ture = ["T1", "T2", "T3", "PZU"] -> 0, 1, 2, 3
    day_shifts = [0, 1, 3] # T1, T2, PZU
    night_shift = 2        # T3
    
    for d in range(num_zile):
        if d in day_to_weekend:
            w_idx = day_to_weekend[d]
            allowed_people = weekend_assignments.get(w_idx, [])
            if allowed_people: # Only apply constraint if user selected exactly 3 people
                for p, name in enumerate(people):
                    if name not in allowed_people:
                        # Ceilalți NU pot face turele de zi (T1, T2, PZU) în acest weekend
                        for t in day_shifts:
                            model.Add(x[(d, p, t)] == 0)
                    else:
                        # Titularii de weekend NU pot face tura de noapte (T3)
                        model.Add(x[(d, p, night_shift)] == 0)
                        
    # J. Rotatie de Weekend: O persoana nu poate face aceeasi tura de 2 ori in acelasi weekend
    for w_idx in set(day_to_weekend.values()):
        w_days = [d for d in day_to_weekend if day_to_weekend[d] == w_idx]
        if len(w_days) > 1: # Pentru weekend-uri intregi (Sambata si Duminica)
            for p in range(num_people):
                for t in range(num_ture):
                    model.Add(sum(x[(d, p, t)] for d in w_days) <= 1)
                    
    # K. Pauză după weekend
    for w_idx, allowed_people in weekend_assignments.items():
        if allowed_people:
            w_days = [d for d in day_to_weekend if day_to_weekend[d] == w_idx]
            if w_days:
                last_w_day = max(w_days)
                d_mon = last_w_day + 1
                d_tue = last_w_day + 2
                
                for p, name in enumerate(people):
                    if name in allowed_people:
                        # 1. Luni - strict interzis, cu o excepție (penalizare imensă 500000)
                        if d_mon < num_zile:
                            viol_mon = model.NewBoolVar(f"viol_mon_{w_idx}_p{p}")
                            model.Add(sum(x[(d_mon, p, t)] for t in range(num_ture)) <= viol_mon)
                            add_penalty(500000, viol_mon, f"{name}: Muncă Luni ({d_mon+1}) după ce a muncit în weekend")
                            violations[(d_mon, p)].append(viol_mon)
                            
                        # 2. Marti - de evitat, dar permis dacă e strict necesar (penalizare normală 20000)
                        if d_tue < num_zile:
                            viol_tue = model.NewBoolVar(f"viol_tue_{w_idx}_p{p}")
                            model.Add(sum(x[(d_tue, p, t)] for t in range(num_ture)) <= viol_tue)
                            add_penalty(20000, viol_tue, f"{name}: Muncă Marți ({d_tue+1}) după ce a muncit în weekend")
                            violations[(d_tue, p)].append(viol_tue)
                            
    # L. T2 Sâmbăta -> PZU Duminica
    for d in range(num_zile - 1):
        current_weekday = (first_day_weekday + d) % 7
        if current_weekday == 5: # Sâmbătă
            for p in range(num_people):
                viol_sat_t2 = model.NewBoolVar(f"viol_sat_t2_d{d}_p{p}")
                # Dacă e T2 sâmbăta, iar duminică lucrează o tura (alta decat PZU), e penalizat
                sum_non_pzu_sunday = x[(d+1, p, 0)] + x[(d+1, p, 1)] + x[(d+1, p, 2)]
                model.Add(x[(d, p, 1)] + sum_non_pzu_sunday <= 1 + viol_sat_t2)
                add_penalty(30000, viol_sat_t2, f"{people[p]}: T2 Sâmbăta ({d+1}) urmat de altceva în afară de PZU Duminica")
                violations[(d+1, p)].append(viol_sat_t2)
                            
    # I. Echilibrare Ture (Fairness Total) DOAR pentru Titulari
    total_shifts_per_person = []
    
    if titulari_idx:
        for p in titulari_idx:
            shifts_p = model.NewIntVar(0, num_zile, f"shifts_p{p}")
            model.Add(shifts_p == sum(x[(d, p, t)] for d in range(num_zile) for t in range(num_ture)))
            total_shifts_per_person.append(shifts_p)
        
    if total_shifts_per_person:
        min_shifts = model.NewIntVar(0, num_zile, "min_shifts")
        max_shifts = model.NewIntVar(0, num_zile, "max_shifts")
        model.AddMinEquality(min_shifts, total_shifts_per_person)
        model.AddMaxEquality(max_shifts, total_shifts_per_person)
        
        diff_shifts = model.NewIntVar(0, num_zile, "diff_shifts")
        model.Add(max_shifts == min_shifts + diff_shifts)
        add_penalty(10, diff_shifts)
    
    # I.2 Echilibrare specifică per TIP de tură (T1, T2, T3, PZU) cu Istoric - DOAR pentru Titulari
    for t_idx in range(num_ture):
        t_shifts_per_person = []
        t_name = ture[t_idx]
        if titulari_idx:
            for p in titulari_idx:
                name = people[p]
                past_count = 0
                if past_shift_counts and name in past_shift_counts:
                    past_count = past_shift_counts[name].get(t_name, 0)
                    
                t_p = model.NewIntVar(0, 1000, f"t{t_idx}_p{p}_total")
                current_month_shifts = sum(x[(d, p, t_idx)] for d in range(num_zile))
                model.Add(t_p == current_month_shifts + past_count)
                t_shifts_per_person.append(t_p)
            
        if t_shifts_per_person:
            min_t = model.NewIntVar(0, 1000, f"min_t{t_idx}")
            max_t = model.NewIntVar(0, 1000, f"max_t{t_idx}")
            model.AddMinEquality(min_t, t_shifts_per_person)
            model.AddMaxEquality(max_t, t_shifts_per_person)
            
            diff_t = model.NewIntVar(0, 1000, f"diff_t{t_idx}")
            model.Add(max_t == min_t + diff_t)
            
            # O penalizare medie-mare pentru a forța uniformitatea la nivelul tuturor turelor
            add_penalty(50, diff_t)
        
    # N. Rotația Turelor "Nașpa" (T3 Weekend, T2 Vineri) DOAR pentru Titulari
    # T3 Weekend
    t3_wk_per_person = []
    wk_days_all = [d for d in range(num_zile) if (first_day_weekday + d) % 7 in [5, 6]]
    if titulari_idx:
        for p in titulari_idx:
            name = people[p]
            past_t3_wk = 0
            if past_shift_counts and name in past_shift_counts:
                past_t3_wk = past_shift_counts[name].get("T3_Weekend", 0)
                
            t3_wk_p = model.NewIntVar(0, 1000, f"t3_wk_p{p}")
            curr_t3_wk = sum(x[(d, p, 2)] for d in wk_days_all)
            model.Add(t3_wk_p == curr_t3_wk + past_t3_wk)
            t3_wk_per_person.append(t3_wk_p)
        
    if t3_wk_per_person:
        min_t3_wk = model.NewIntVar(0, 1000, "min_t3_wk")
        max_t3_wk = model.NewIntVar(0, 1000, "max_t3_wk")
        model.AddMinEquality(min_t3_wk, t3_wk_per_person)
        model.AddMaxEquality(max_t3_wk, t3_wk_per_person)
        diff_t3_wk = model.NewIntVar(0, 1000, "diff_t3_wk")
        model.Add(max_t3_wk == min_t3_wk + diff_t3_wk)
        add_penalty(100, diff_t3_wk)
    
    # T2 Vineri
    t2_fri_per_person = []
    fri_days = [d for d in range(num_zile) if (first_day_weekday + d) % 7 == 4]
    if titulari_idx:
        for p in titulari_idx:
            name = people[p]
            past_t2_fri = 0
            if past_shift_counts and name in past_shift_counts:
                past_t2_fri = past_shift_counts[name].get("T2_Vineri", 0)
                
            t2_fri_p = model.NewIntVar(0, 1000, f"t2_fri_p{p}")
            curr_t2_fri = sum(x[(d, p, 1)] for d in fri_days)
            model.Add(t2_fri_p == curr_t2_fri + past_t2_fri)
            t2_fri_per_person.append(t2_fri_p)
        
    if t2_fri_per_person:
        min_t2_fri = model.NewIntVar(0, 1000, "min_t2_fri")
        max_t2_fri = model.NewIntVar(0, 1000, "max_t2_fri")
        model.AddMinEquality(min_t2_fri, t2_fri_per_person)
        model.AddMaxEquality(max_t2_fri, t2_fri_per_person)
        diff_t2_fri = model.NewIntVar(0, 1000, "diff_t2_fri")
        model.Add(max_t2_fri == min_t2_fri + diff_t2_fri)
        add_penalty(100, diff_t2_fri)
    
    # O. Macar un weekend complet liber per lună pentru fiecare angajat
    for p in range(num_people):
        weekend_worked_vars = []
        for w_idx in set(day_to_weekend.values()):
            w_days = [d for d in day_to_weekend if day_to_weekend[d] == w_idx]
            if len(w_days) == 2: # Doar weekendurile complete
                # True dacă a lucrat MĂCAR O tură în acest weekend
                worked_this_wk = model.NewBoolVar(f"worked_wk_{w_idx}_p{p}")
                sum_wk = sum(x[(d, p, t)] for d in w_days for t in range(num_ture))
                model.Add(sum_wk > 0).OnlyEnforceIf(worked_this_wk)
                model.Add(sum_wk == 0).OnlyEnforceIf(worked_this_wk.Not())
                weekend_worked_vars.append(worked_this_wk)
                
        if len(weekend_worked_vars) > 0:
            viol_no_free_wk = model.NewBoolVar(f"viol_no_free_wk_p{p}")
            # Daca suma weekendurilor muncite este egala cu totalul weekendurilor, luam amenda
            model.Add(sum(weekend_worked_vars) <= len(weekend_worked_vars) - 1 + viol_no_free_wk * len(weekend_worked_vars))
            add_penalty(50000, viol_no_free_wk, f"{people[p]}: Nu a primit niciun weekend complet liber pe luna aceasta")
    
    # M. Zile de Sărbătoare (Priorități)
    objective_terms = list(penalties)
    if holiday_assignments:
        for day_str, prioritized_people in holiday_assignments.items():
            d = int(day_str) - 1
            if 0 <= d < num_zile:
                for name in prioritized_people:
                    if name in people:
                        p = people.index(name)
                        works_on_holiday = sum(x[(d, p, t)] for t in range(num_ture))
                        violation = model.NewBoolVar(f"holiday_miss_{d}_{p}")
                        model.Add(works_on_holiday == 0).OnlyEnforceIf(violation)
                        model.Add(works_on_holiday == 1).OnlyEnforceIf(violation.Not())
                        objective_terms.append(violation * 40000)
                        tracked_violations.append((violation, 40000, f"{name}: Nu a primit tură de Sărbătoare pe {d+1}/{month} deși a fost prioritar"))
                        
    # 4.5 Warm Start Hints
    if hints:
        for d_str, shifts in hints.items():
            d = int(d_str)
            if 0 <= d < num_zile:
                for t_idx, person_name in shifts.items():
                    if person_name in people:
                        p = people.index(person_name)
                        model.AddHint(x[(d, p, int(t_idx))], 1)
    
    # 4. Objective
    model.Minimize(sum(objective_terms))
    
    # 5. Solve
    solver = cp_model.CpSolver()
    
    # Folosește mai multă putere de procesare (Multi-threading)
    import multiprocessing
    try:
        cores = multiprocessing.cpu_count()
    except:
        cores = 4
    solver.parameters.num_search_workers = cores
    
    # Timp maxim de gândire primit din interfață
    solver.parameters.max_time_in_seconds = float(timp_gandire)
    
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Build Result (Rows = Dates, Cols = Info + Shifts)
        zile_ro = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]
        luni_ro = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        rows = []
        for d in range(num_zile):
            current_date = f"{d+1:02d}/{month:02d}/{year}"
            current_weekday = (first_day_weekday + d) % 7
            ziua_nume = zile_ro[current_weekday]
            luna_nume = luni_ro[month-1]
            
            # Simplified week calculation
            import datetime
            dt = datetime.date(year, month, d+1)
            week_num = dt.isocalendar()[1]
            
            row = {
                "Luna": luna_nume,
                "Saptamana": week_num,
                "Ziua": ziua_nume,
                "Data": current_date,
                "Tura 1": "GOL",
                "Tura 2": "GOL",
                "Tura 3": "GOL",
                "PZU": "GOL"
            }
            
            for t_idx, t_name in enumerate(ture):
                # map T1 to Tura 1, T2 to Tura 2 etc
                col_name = "PZU" if t_name == "PZU" else f"Tura {t_name[1]}"
                assigned_names = []
                for p in range(num_people):
                    if solver.Value(x[(d, p, t_idx)]) == 1:
                        name_str = people[p]
                        
                        # Check if this assignment breaks a rest rule
                        is_forced = False
                        if (d, p) in violations:
                            for v_var in violations[(d, p)]:
                                if solver.Value(v_var) == 1:
                                    is_forced = True
                                    break
                                
                        if is_forced:
                            name_str += " (!)"
                            
                        assigned_names.append(name_str)
                
                if assigned_names:
                    row[col_name] = ", ".join(assigned_names)
                        
            rows.append(row)
            
        df = pd.DataFrame(rows)
        
        violation_details = []
        for var, weight, desc in tracked_violations:
            try:
                val = solver.Value(var)
                if val > 0 and weight >= 10000:
                    if val == 1:
                        violation_details.append(desc)
                    else:
                        violation_details.append(f"{desc} ({val} apariții)")
            except:
                pass
                
        return df, solver.ObjectiveValue(), status, violation_details
    else:
        return None, None, status, []
