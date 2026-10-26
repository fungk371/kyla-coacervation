"""
Alternative Phase Diagram Visualization
========================================

RECOMMENDED PARAMETERS based on data analysis:
----------------------------------------------
1. PHASE THRESHOLD: 75% transmission (50/50 split between phases)
   - Current threshold of 70% gives 204 vs 564 points (0.36 ratio - skewed)
   - Threshold of 75% gives 312 vs 456 points (0.68 ratio - more balanced)
   - This better represents the transition zone

2. CONTOUR LEVELS: Multi-level contours at [65, 70, 75, 80, 85]
   - Shows gradual transition rather than binary phase boundary
   - Captures 10%, 25%, 50%, 75%, 90% percentiles of data
   - More informative for understanding phase behavior

3. VISUALIZATION STYLE: 
   - Filled contour map with colorbar (continuous transmission scale)
   - Overlay distinct phase boundary contours
   - Add data points as overlay for validation
   - Include iso-transmission lines

4. AXIS FORMATTING:
   - Log-log scale (maintained from current version)
   - Extended tick labels for better readability
   - Equal aspect ratio for visual balance

5. ADDITIONAL FEATURES:
   - 3-phase classification: Clear (>80), Turbid (65-80), Phase-separated (<65)
   - Time-averaged phase diagram to show overall behavior
   - Difference maps showing temporal evolution
"""

import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.interpolate import Rbf
from scipy.ndimage import gaussian_filter
import matplotlib.patches as mpatches

# Connect to database and load data
conn = sqlite3.connect('phase_diagram.db')
solutions = pd.read_sql('SELECT * FROM solution_metadata', conn)

query = """
SELECT 
    wc.plate,
    wc.well,
    wc.row,
    wc.column,
    wc.SW1_uL,
    wc.PS1_uL,
    wc.PS2_uL,
    wc.AS1_uL,
    wc.AS2_uL,
    wc.total_volume_uL,
    tm.transmission,
    tm.timepoint_minutes,
    tm.experiment_name
FROM well_compositions wc
LEFT JOIN transmission_measurements tm 
    ON wc.plate = tm.plate AND wc.well = tm.well
ORDER BY tm.timepoint_minutes, wc.plate, wc.column, wc.row
"""

data = pd.read_sql(query, conn)
conn.close()

# Calculate actual concentrations
ps1_conc = solutions[solutions['solution_id'] == 'PS1']['concentration'].values[0]
ps2_conc = solutions[solutions['solution_id'] == 'PS2']['concentration'].values[0]
as1_conc = solutions[solutions['solution_id'] == 'AS1']['concentration'].values[0]
as2_conc = solutions[solutions['solution_id'] == 'AS2']['concentration'].values[0]

data['PS_total_pct'] = (data['PS1_uL'] * ps1_conc + data['PS2_uL'] * ps2_conc) / data['total_volume_uL']
data['AS_total_pct'] = (data['AS1_uL'] * as1_conc + data['AS2_uL'] * as2_conc) / data['total_volume_uL']

# Get unique timepoints
timepoints = sorted(data['timepoint_minutes'].dropna().unique())

print(f"\n{'='*60}")
print(f"ALTERNATIVE PHASE DIAGRAM GENERATION")
print(f"{'='*60}")
print(f"\nParameters:")
print(f"  - Phase threshold: 75% transmission")
print(f"  - Contour levels: [65, 70, 75, 80, 85]")
print(f"  - Classification: Clear (>80), Turbid (65-80), Phase-separated (<65)")
print(f"  - Interpolation: RBF with smooth=5 for finer detail")
print(f"  - Creating diagrams for {len(timepoints)} timepoints")
print(f"{'='*60}\n")

# Create output directory
output_dir = Path('phase_diagrams_alternative')
output_dir.mkdir(exist_ok=True)

# Define visualization parameters
PHASE_THRESHOLD = 75  # Recommended: 50/50 split
CONTOUR_LEVELS = [65, 70, 75, 80, 85]  # Multi-level contours
COLORMAP = 'RdYlGn'  # Red (low transmission) to Green (high transmission)

def create_alternative_phase_diagram(tp_data, timepoint, output_dir):
    """Create an enhanced phase diagram with multiple visualization techniques"""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'Enhanced Phase Diagram at {timepoint:.2f} minutes\n{tp_data["experiment_name"].iloc[0]}', 
                 fontsize=16, fontweight='bold')
    
    # Create interpolated grid
    ps_grid = np.logspace(np.log10(tp_data['PS_total_pct'].min()), 
                          np.log10(tp_data['PS_total_pct'].max()), 400)
    as_grid = np.logspace(np.log10(tp_data['AS_total_pct'].min()), 
                          np.log10(tp_data['AS_total_pct'].max()), 400)
    AS_grid, PS_grid = np.meshgrid(as_grid, ps_grid)
    
    # RBF interpolation with finer smoothing
    rbf = Rbf(tp_data['AS_total_pct'], tp_data['PS_total_pct'], tp_data['transmission'], 
              function='multiquadric', smooth=5)
    trans_grid = rbf(AS_grid, PS_grid)
    trans_grid = np.clip(trans_grid, 35, 95)
    
    # ====== SUBPLOT 1: Continuous Transmission Map with Contour Lines ======
    ax1 = axes[0, 0]
    
    # Filled contour with continuous color scale
    contourf = ax1.contourf(AS_grid, PS_grid, trans_grid, levels=20, cmap=COLORMAP, alpha=0.8)
    
    # Add contour lines at key transmission values
    contour_lines = ax1.contour(AS_grid, PS_grid, trans_grid, levels=CONTOUR_LEVELS, 
                                colors='black', linewidths=[1, 1.5, 2.5, 1.5, 1], 
                                linestyles=['--', '--', '-', '--', '--'])
    ax1.clabel(contour_lines, inline=True, fontsize=9, fmt='%d%%')
    
    # Overlay data points
    scatter1 = ax1.scatter(tp_data['AS_total_pct'], tp_data['PS_total_pct'], 
                          c=tp_data['transmission'], s=15, cmap=COLORMAP, 
                          edgecolors='black', linewidth=0.3, alpha=0.6, vmin=35, vmax=95)
    
    ax1.set_xlabel('Rhamnolipid Concentration (%)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Excel Concentration (%)', fontsize=11, fontweight='bold')
    ax1.set_title('Continuous Transmission Map', fontsize=12, fontweight='bold')
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax1.set_xticklabels(['0.1', '0.2', '0.5', '1', '2', '5', '10'])
    ax1.set_xlim([tp_data['AS_total_pct'].min() * 0.9, tp_data['AS_total_pct'].max() * 1.1])
    ax1.set_ylim([tp_data['PS_total_pct'].min() * 0.9, tp_data['PS_total_pct'].max() * 1.1])
    ax1.grid(True, alpha=0.3, which='both')
    
    cbar1 = plt.colorbar(contourf, ax=ax1, label='Transmission (%)')
    
    # ====== SUBPLOT 2: Three-Phase Classification ======
    ax2 = axes[0, 1]
    
    # Create three-phase regions
    from matplotlib.colors import ListedColormap, BoundaryNorm
    phase_colors = ['#c0392b', '#f39c12', '#27ae60']  # Red, Orange, Green
    phase_cmap = ListedColormap(phase_colors)
    phase_bounds = [0, 65, 80, 100]
    phase_norm = BoundaryNorm(phase_bounds, phase_cmap.N)
    
    ax2.contourf(AS_grid, PS_grid, trans_grid, levels=phase_bounds, 
                cmap=phase_cmap, norm=phase_norm, alpha=0.7)
    
    # Add boundaries
    ax2.contour(AS_grid, PS_grid, trans_grid, levels=[65, 80], 
               colors='black', linewidths=2.5)
    
    # Overlay data points colored by phase
    tp_data['phase'] = pd.cut(tp_data['transmission'], bins=[0, 65, 80, 100], 
                              labels=['Phase-separated', 'Turbid', 'Clear'])
    
    for phase, color in zip(['Phase-separated', 'Turbid', 'Clear'], phase_colors):
        phase_data = tp_data[tp_data['phase'] == phase]
        ax2.scatter(phase_data['AS_total_pct'], phase_data['PS_total_pct'], 
                   c=color, s=20, edgecolors='black', linewidth=0.5, label=phase)
    
    ax2.set_xlabel('Rhamnolipid Concentration (%)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Excel Concentration (%)', fontsize=11, fontweight='bold')
    ax2.set_title('Three-Phase Classification', fontsize=12, fontweight='bold')
    ax2.set_xscale('log')
    ax2.set_yscale('log')
    ax2.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax2.set_xticklabels(['0.1', '0.2', '0.5', '1', '2', '5', '10'])
    ax2.set_xlim([tp_data['AS_total_pct'].min() * 0.9, tp_data['AS_total_pct'].max() * 1.1])
    ax2.set_ylim([tp_data['PS_total_pct'].min() * 0.9, tp_data['PS_total_pct'].max() * 1.1])
    ax2.grid(True, alpha=0.3, which='both')
    ax2.legend(loc='upper left', fontsize=9)
    
    # ====== SUBPLOT 3: Data Points with 75% Threshold ======
    ax3 = axes[1, 0]
    
    # Binary classification at 75%
    colors = ['#e74c3c' if t < 75 else '#2ecc71' for t in tp_data['transmission']]
    ax3.scatter(tp_data['AS_total_pct'], tp_data['PS_total_pct'], 
               c=colors, s=50, edgecolors='black', linewidth=0.5, alpha=0.8)
    
    # Add 75% boundary
    contour_75 = ax3.contour(AS_grid, PS_grid, trans_grid, levels=[75], 
                            colors='black', linewidths=3)
    ax3.clabel(contour_75, inline=True, fontsize=10, fmt='75%% Boundary')
    
    ax3.set_xlabel('Rhamnolipid Concentration (%)', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Excel Concentration (%)', fontsize=11, fontweight='bold')
    ax3.set_title('Binary Phase Boundary (75% Threshold)', fontsize=12, fontweight='bold')
    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax3.set_xticklabels(['0.1', '0.2', '0.5', '1', '2', '5', '10'])
    ax3.set_xlim([tp_data['AS_total_pct'].min() * 0.9, tp_data['AS_total_pct'].max() * 1.1])
    ax3.set_ylim([tp_data['PS_total_pct'].min() * 0.9, tp_data['PS_total_pct'].max() * 1.1])
    ax3.grid(True, alpha=0.3, which='both')
    
    # Add legend
    red_patch = mpatches.Patch(color='#e74c3c', label='2-Phase (<75%)')
    green_patch = mpatches.Patch(color='#2ecc71', label='1-Phase (≥75%)')
    ax3.legend(handles=[red_patch, green_patch], loc='upper left', fontsize=9)
    
    # ====== SUBPLOT 4: Statistics and Distribution ======
    ax4 = axes[1, 1]
    
    # Histogram with phase classifications
    bins = np.arange(30, 100, 5)
    ax4.hist(tp_data['transmission'], bins=bins, color='steelblue', alpha=0.7, edgecolor='black')
    
    # Add vertical lines for phase boundaries
    ax4.axvline(65, color='#c0392b', linewidth=2, linestyle='--', label='Phase-separated/Turbid (65%)')
    ax4.axvline(75, color='black', linewidth=2.5, linestyle='-', label='Recommended boundary (75%)')
    ax4.axvline(80, color='#27ae60', linewidth=2, linestyle='--', label='Turbid/Clear (80%)')
    
    ax4.set_xlabel('Transmission (%)', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax4.set_title('Transmission Distribution', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)
    
    # Add statistics text box
    stats_text = f"Mean: {tp_data['transmission'].mean():.1f}%\n"
    stats_text += f"Std: {tp_data['transmission'].std():.1f}%\n"
    stats_text += f"Range: {tp_data['transmission'].min():.1f} - {tp_data['transmission'].max():.1f}%\n\n"
    stats_text += f"Phase-separated (<65%): {(tp_data['transmission'] < 65).sum()} wells\n"
    stats_text += f"Turbid (65-80%): {((tp_data['transmission'] >= 65) & (tp_data['transmission'] < 80)).sum()} wells\n"
    stats_text += f"Clear (≥80%): {(tp_data['transmission'] >= 80).sum()} wells"
    
    ax4.text(0.98, 0.97, stats_text, transform=ax4.transAxes, 
            fontsize=9, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    # Save figure
    filename = f'alternative_phase_diagram_{timepoint:.2f}min.png'
    plt.savefig(output_dir / filename, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {output_dir / filename}")

# Generate diagrams for each timepoint
for tp in timepoints:
    tp_data = data[data['timepoint_minutes'] == tp].copy()
    create_alternative_phase_diagram(tp_data, tp, output_dir)

# Create time evolution comparison
print("\nCreating time evolution comparison...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Phase Boundary Evolution (75% Threshold)', fontsize=16, fontweight='bold')

for idx, tp in enumerate(timepoints):
    ax = axes[idx // 2, idx % 2]
    tp_data = data[data['timepoint_minutes'] == tp].copy()
    
    # Create interpolated grid
    ps_grid = np.logspace(np.log10(tp_data['PS_total_pct'].min()), 
                          np.log10(tp_data['PS_total_pct'].max()), 300)
    as_grid = np.logspace(np.log10(tp_data['AS_total_pct'].min()), 
                          np.log10(tp_data['AS_total_pct'].max()), 300)
    AS_grid, PS_grid = np.meshgrid(as_grid, ps_grid)
    
    rbf = Rbf(tp_data['AS_total_pct'], tp_data['PS_total_pct'], tp_data['transmission'], 
              function='multiquadric', smooth=5)
    trans_grid = rbf(AS_grid, PS_grid)
    trans_grid = np.clip(trans_grid, 35, 95)
    
    # Three-phase contour
    from matplotlib.colors import ListedColormap, BoundaryNorm
    colors = ['#c0392b', '#f39c12', '#27ae60']
    cmap = ListedColormap(colors)
    bounds = [0, 65, 80, 100]
    norm = BoundaryNorm(bounds, cmap.N)
    
    ax.contourf(AS_grid, PS_grid, trans_grid, levels=bounds, cmap=cmap, norm=norm, alpha=0.6)
    contour_lines = ax.contour(AS_grid, PS_grid, trans_grid, levels=[65, 75, 80], 
                                colors='black', linewidths=[2, 3, 2], 
                                linestyles=['--', '-', '--'])
    ax.clabel(contour_lines, inline=True, fontsize=9, fmt='%d%%')
    
    ax.set_xlabel('Rhamnolipid Concentration (%)', fontsize=10)
    ax.set_ylabel('Excel Concentration (%)', fontsize=10)
    ax.set_title(f'T = {tp:.2f} min (Mean: {tp_data["transmission"].mean():.1f}%)', fontsize=11)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax.set_xticklabels(['0.1', '0.2', '0.5', '1', '2', '5', '10'])
    ax.set_xlim([tp_data['AS_total_pct'].min() * 0.9, tp_data['AS_total_pct'].max() * 1.1])
    ax.set_ylim([tp_data['PS_total_pct'].min() * 0.9, tp_data['PS_total_pct'].max() * 1.1])
    ax.grid(True, alpha=0.3, which='both')

plt.tight_layout()
plt.savefig(output_dir / 'time_evolution_alternative.png', dpi=300, bbox_inches='tight')
plt.close()

print(f"  Saved: {output_dir / 'time_evolution_alternative.png'}")

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"Generated alternative phase diagrams with:")
print(f"  ✓ Multi-level contours (65, 70, 75, 80, 85%)")
print(f"  ✓ Three-phase classification system")
print(f"  ✓ Recommended 75% threshold for phase boundary")
print(f"  ✓ Continuous transmission maps")
print(f"  ✓ Enhanced statistical visualizations")
print(f"\nAll diagrams saved to: {output_dir}")
print(f"{'='*60}\n")
