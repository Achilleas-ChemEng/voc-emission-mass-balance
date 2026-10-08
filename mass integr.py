import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import shutil
import re
import gc

# ==========================================
# 1. ΦΥΣΙΚΕΣ ΠΑΡΑΜΕΤΡΟΙ ΠΕΙΡΑΜΑΤΟΣ
# ==========================================
V = 0.2945        
Q = 4.18          
T_celsius = 25.0  
A_surface = 0.004

t_active_emission_min = 1.0  

file_path = r"C:\Users\temp\Desktop\additional_marker_tol_phen_form.xlsx"
sheet_name = 'markers timeseries'

output_excel_path = r"C:\Users\temp\Desktop\EMISSION RATES2\Mass_Balance_Integration_Results2.xlsx"
# ΝΕΟΣ ΦΑΚΕΛΟΣ: Μόνο για τα διαγράμματα οπτικού ελέγχου (fill)
fill_plots_folder = r"C:\Users\temp\Desktop\EMISSION RATES2\Integration_Fill_Plots2"

if os.path.exists(fill_plots_folder):
    shutil.rmtree(fill_plots_folder)
os.makedirs(fill_plots_folder, exist_ok=True)

placement_times = ['17:01:00', '17:26:00', '17:57:00', '18:29:00', '19:12:00', '19:31:00']
event_labels = ['MARKER 1', 'MARKER 2', 'MARKER 3', 'MARKER 4', 'MARKER WITHOUT CAP', 'MARKER WITH CAP']

Vm = 0.08206 * (T_celsius + 273.15) 

def extract_mz(col_name):
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str(col_name))
    if numbers:
        return float(numbers[0])
    return None

# ==========================================
# 2. ΕΙΣΑΓΩΓΗ & ΠΡΟΕΤΟΙΜΑΣΙΑ ΔΕΔΟΜΕΝΩΝ
# ==========================================
print("Φόρτωση δεδομένων από το Excel...")
df = pd.read_excel(file_path, sheet_name=sheet_name)
time_col = df.columns[0] 
df[time_col] = pd.to_datetime(df[time_col]) 
df['Time_String'] = df[time_col].dt.strftime('%H:%M:%S')

event_indices = []   
event_datetimes = [] 

for p_time in placement_times:
    idx_list = df.index[df['Time_String'] >= p_time].tolist()
    if not idx_list:
        raise ValueError(f"Σφάλμα: Η ώρα {p_time} δεν βρέθηκε στο αρχείο.")
    event_indices.append(idx_list[0]) 
    event_datetimes.append(df[time_col].iloc[idx_list[0]])

event_indices.append(len(df)) 

results_list = []
mz_columns = df.columns[1:-1] 
successful_mz_cols = set() 

# ΝΕΟ: Λεξικό για να αποθηκεύουμε τα όρια του ολοκληρώματος για τη ζωγραφική
integration_intervals = {}

# ==========================================
# 3. ΜΑΘΗΜΑΤΙΚΟ ΜΟΝΤΕΛΟ ΥΠΟΛΟΓΙΣΜΟΥ (AUC & SER)
# ==========================================
for i in range(len(placement_times)):
    event_name = event_labels[i]
    start_idx = event_indices[i] 
    end_idx = event_indices[i+1] 
    
    print(f"Ανάλυση γεγονότος: {event_name} ({placement_times[i]})...")
    
    df_event = df.iloc[start_idx:end_idx].copy()
    time_deltas = df_event[time_col] - df_event[time_col].iloc[0]
    t_data_hours_full = time_deltas.dt.total_seconds().values / 3600.0

    for col in mz_columns:
        mz_value = extract_mz(col)
        if mz_value is None: 
            continue
        
        MW = mz_value 

        bg_ppb = df_event[col].iloc[0]
        net_ppb = (df_event[col] - bg_ppb).clip(lower=0)
        
        peak_idx = net_ppb.argmax()     
        peak_val = net_ppb.iloc[peak_idx] 
        
        if peak_val <= 0:
            continue 
            
        threshold_almost_zero = 0.05 * peak_val
        end_idx_auc = len(net_ppb) - 1 
        
        for j in range(peak_idx, len(net_ppb)):
            if net_ppb.iloc[j] <= threshold_almost_zero:
                end_idx_auc = j
                break
                
        net_ppb_auc = net_ppb.iloc[:end_idx_auc + 1]
        t_hours_auc = t_data_hours_full[:end_idx_auc + 1]
        
        C_data_ugm3_auc = net_ppb_auc * (MW / Vm)
        
        AUC_val = np.trapz(C_data_ugm3_auc.values, t_hours_auc)
        C_end = C_data_ugm3_auc.values[-1]
        M_total_ug = (Q * AUC_val) + (V * C_end)
        t_integration_hours = t_hours_auc[-1] - t_hours_auc[0]
        
        t_active_emission_hours = t_active_emission_min / 60.0
        
        if M_total_ug > 0:
            SER_avg = M_total_ug / (A_surface * t_active_emission_hours)
        else:
            SER_avg = 0.0
            
        if SER_avg > 0:
            successful_mz_cols.add(col) 
            
            absolute_times = df_event[time_col].iloc[:end_idx_auc + 1]
            
            # --- ΑΠΟΘΗΚΕΥΣΗ ΟΡΙΩΝ ΓΙΑ ΤΟ ΓΡΑΦΗΜΑ (FILL) ---
            if col not in integration_intervals:
                integration_intervals[col] = []
            
            integration_intervals[col].append({
                'event_name': event_name,
                'abs_start_idx': start_idx,
                'abs_end_idx': start_idx + end_idx_auc,
                'bg_ppb': bg_ppb
            })
            
            results_list.append({
                'Event_Name': event_name,
                'Start_Time': absolute_times.iloc[0].strftime('%H:%M:%S'),
                'End_Time_Integration': absolute_times.iloc[-1].strftime('%H:%M:%S'),
                'm/z': mz_value,
                'Column_Name': col,
                'Background_Initial (ppb)': bg_ppb,
                'Peak_Concentration (ppb)': peak_val,
                'Total_Mass_Emitted (μg)': M_total_ug,
                'Integration_Duration (min)': t_integration_hours * 60,
                'Active_Emission_Time (min)': t_active_emission_min,
                'Average_SER (μg/m2*h)': SER_avg
            })

# ==========================================
# 4. ΔΗΜΙΟΥΡΓΙΑ ΔΙΑΓΡΑΜΜΑΤΩΝ ΟΠΤΙΚΟΥ ΕΛΕΓΧΟΥ (FILL PLOTS)
# ==========================================
print("\nΔημιουργία Διαγραμμάτων Οπτικού Ελέγχου Ολοκληρώματος (AUC Visual Check)...")

plot_counter = 1

for col in mz_columns:
    if col not in successful_mz_cols:
        continue 
        
    fig, ax = plt.subplots(figsize=(14, 6)) 
    
    # Σχεδίαση της αρχικής (ακατέργαστης) χρονοσειράς
    ax.plot(df[time_col], df[col], color='#1f77b4', linewidth=1.5, label='Raw Concentration (ppb)')
    ax.margins(x=0)
    
    # Προσθήκη του κόκκινου Fill (γεμίσματος) για κάθε γεγονός που ολοκληρώθηκε
    added_fill_label = False
    added_bg_label = False
    
    for interval in integration_intervals[col]:
        start_i = interval['abs_start_idx']
        end_i = interval['abs_end_idx']
        bg_val = interval['bg_ppb']
        
        # Απομόνωση των δεδομένων ΜΟΝΟ για τη διάρκεια του ολοκληρώματος
        df_fill = df.iloc[start_i:end_i + 1]
        t_fill = df_fill[time_col]
        y_fill = df_fill[col]
        
        # Ζωγραφίζουμε μια μαύρη διακεκομμένη γραμμή για το Background
        label_bg = 'Calculated Background' if not added_bg_label else ""
        ax.plot(t_fill, [bg_val]*len(t_fill), color='black', linestyle='--', linewidth=1.2, label=label_bg)
        added_bg_label = True
        
        # Γεμίζουμε με κόκκινο χρώμα την περιοχή από το background μέχρι την καμπύλη
        label_fill = 'Integrated Area (AUC)' if not added_fill_label else ""
        ax.fill_between(t_fill, bg_val, y_fill, where=(y_fill >= bg_val), color='red', alpha=0.35, label=label_fill)
        added_fill_label = True
        
        # Προσθήκη ταμπέλας με το όνομα του Marker πάνω από την κορυφή
        peak_time = df_fill.loc[df_fill[col].idxmax(), time_col]
        peak_y = df_fill[col].max()
        ax.text(peak_time, peak_y * 1.02, interval['event_name'], 
                color='red', fontsize=9, fontweight='bold', ha='center', va='bottom')

    # Μορφοποίηση 
    max_y = df[col].max()
    ax.set_ylim(bottom=0, top=max_y * 1.20) 
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=30, ha='right', fontsize=10)
    
    ax.set_title(f'Visual AUC Inspection - {col}', fontsize=15, fontweight='bold', pad=15)
    ax.set_ylabel('Concentration (ppb)', fontsize=12, fontweight='bold')
    ax.legend(loc='upper right')
    
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    fig.tight_layout() 
    
    safe_col_name = re.sub(r'[^A-Za-z0-9_\-\. ]', '_', str(col))
    safe_name = f"{plot_counter:03d}_{safe_col_name}_AUC_Fill"
    
    fig.savefig(os.path.join(fill_plots_folder, f"{safe_name}.png"), dpi=150)
    plt.close(fig) 
    
    plot_counter += 1
    
gc.collect() 

# ==========================================
# 5. ΕΞΑΓΩΓΗ ΤΕΛΙΚΟΥ ΣΥΓΚΕΝΤΡΩΤΙΚΟΥ ΑΡΧΕΙΟΥ
# ==========================================
if results_list:
    results_df = pd.DataFrame(results_list)
    event_order = {name: i for i, name in enumerate(event_labels)}
    results_df['Event_Order'] = results_df['Event_Name'].map(event_order)
    results_df = results_df.sort_values(by=['Event_Order', 'm/z']).drop('Event_Order', axis=1) 
    
    try:
        results_df.to_excel(output_excel_path, index=False) 
    except Exception as e:
        print(f"\nΣφάλμα αποθήκευσης Excel (μήπως το έχεις ανοιχτό;): {e}")
        
    csv_path = output_excel_path.replace(".xlsx", ".csv")
    results_df.to_csv(csv_path, index=False, sep=';', encoding='utf-8-sig')
    
    print("\n" + "="*50)
    print("Η ΑΝΑΛΥΣΗ ΜΕ ΤΗΝ ΟΡΘΗ ΦΥΣΙΚΗ ΠΡΟΣΕΓΓΙΣΗ 1-ΛΕΠΤΟΥ ΟΛΟΚΛΗΡΩΘΗΚΕ ΕΠΙΤΥΧΩΣ!")
    print(f"\nΤο Excel αποθηκεύτηκε στο:\n{output_excel_path}")
    print("="*50)