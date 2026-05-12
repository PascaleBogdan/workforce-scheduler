import re

with open('c:\\Users\\Bogdan\\.gemini\\antigravity\\scratch\\workforce_scheduler\\scheduler.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('penalties = []', 'penalties = []\n    tracked_violations = []\n    \n    def add_penalty(weight, var, desc=None):\n        penalties.append(weight * var)\n        if desc:\n            tracked_violations.append((var, weight, desc))\n'),
    ('penalties.append(1000000 * missing)', 'add_penalty(1000000, missing, f"Tură rămasă descoperită (GOL) pe data de {d+1}/{month}")'),
    ('penalties.append(20000 * viol_t1_prev)', 'add_penalty(20000, viol_t1_prev, f"{name}: Fără pauză după T1 la trecerea dintre luni")'),
    ('penalties.append(20000 * viol_pzu_prev)', 'add_penalty(20000, viol_pzu_prev, f"{name}: PZU consecutiv la trecerea dintre luni")'),
    ('penalties.append(500000 * viol_mon_prev)', 'add_penalty(500000, viol_mon_prev, f"{name}: A lucrat Luni după lucrul în ultimul weekend din luna trecută")'),
    ('penalties.append(20000 * viol_tue_prev)', 'add_penalty(20000, viol_tue_prev, f"{name}: A lucrat Marți după lucrul în ultimul weekend din luna trecută")'),
    ('penalties.append(20000 * viol_t2)', 'add_penalty(20000, viol_t2, f"{people[p]}: Fără zi liberă obligatorie după T2 (în data de {d+1}/{month})")'),
    ('penalties.append(30000 * viol_t3)', 'add_penalty(30000, viol_t3, f"{people[p]}: Fără cele 2 zile libere obligatorii după T3 (în data de {d+1}/{month})")'),
    ('penalties.append(20000 * viol_t1_cons)', 'add_penalty(20000, viol_t1_cons, f"{people[p]}: Ture T1 consecutive pe {d+1} și {d+2}")'),
    ('penalties.append(20000 * viol_pzu_cons)', 'add_penalty(20000, viol_pzu_cons, f"{people[p]}: Ture PZU consecutive pe {d+1} și {d+2}")'),
    ('penalties.append(100 * viol_max)', 'add_penalty(100, viol_max)'),
    ('penalties.append(100 * viol_min)', 'add_penalty(100, viol_min)'),
    ('penalties.append(50000 * viol_liber)', 'add_penalty(50000, viol_liber, f"{name}: Refuzare cerere zi Liberă pe {d+1}/{month}")'),
    ('penalties.append(10000 * viol_pref)', 'add_penalty(10000, viol_pref, f"{name}: Ignorare preferință {t_name} pe {d+1}/{month}")'),
    ('penalties.append(50000 * viol_nedorit)', 'add_penalty(50000, viol_nedorit, f"{name}: A primit tura nedorită ({t_name}) pe {d+1}/{month}")'),
    ('penalties.append(500000 * viol_mon)', 'add_penalty(500000, viol_mon, f"{name}: Muncă Luni ({d_mon+1}) după ce a muncit în weekend")'),
    ('penalties.append(20000 * viol_tue)', 'add_penalty(20000, viol_tue, f"{name}: Muncă Marți ({d_tue+1}) după ce a muncit în weekend")'),
    ('penalties.append(30000 * viol_sat_t2)', 'add_penalty(30000, viol_sat_t2, f"{people[p]}: T2 Sâmbăta ({d+1}) urmat de altceva în afară de PZU Duminica")'),
    ('penalties.append(10 * diff_shifts)', 'add_penalty(10, diff_shifts)'),
    ('penalties.append(50 * diff_t)', 'add_penalty(50, diff_t)'),
    ('penalties.append(100 * diff_t3_wk)', 'add_penalty(100, diff_t3_wk)'),
    ('penalties.append(100 * diff_t2_fri)', 'add_penalty(100, diff_t2_fri)'),
    ('penalties.append(50000 * viol_no_free_wk)', 'add_penalty(50000, viol_no_free_wk, f"{people[p]}: Nu a primit niciun weekend complet liber pe luna aceasta")'),
    ('objective_terms.append(violation * 10000)', 'objective_terms.append(violation * 10000)\n                        tracked_violations.append((violation, 10000, f"{name}: Nu a primit tură de Sărbătoare pe {d+1}/{month} deși a fost prioritar"))')
]

for old, new in replacements:
    content = content.replace(old, new)

return_block_old = '''        df = pd.DataFrame(rows)
        return df, solver.ObjectiveValue(), status
    else:
        return None, None, status'''

return_block_new = '''        df = pd.DataFrame(rows)
        
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
        return None, None, status, []'''

content = content.replace(return_block_old, return_block_new)

with open('c:\\Users\\Bogdan\\.gemini\\antigravity\\scratch\\workforce_scheduler\\scheduler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done patch')
