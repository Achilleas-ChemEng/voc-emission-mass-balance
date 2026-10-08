# voc-emission-mass-balance
Automated mass balance and numerical AUC integration tool for real-time indoor VOC emission rate analysis.
####
## Features
* **Mass Balance Calculation:** Computes total emitted mass  and  Emission Rates.
* **Automated AUC Integration:** Uses trapezoidal numerical integration (`np.trapz`) with automatic 5% peak baseline cutoff.
* **Inspection Plots:** Auto-generates clean visual verification plots (shaded AUC).
* **Multi-Format Export:** Exports results to both Excel (`.xlsx`) and `.csv`.
