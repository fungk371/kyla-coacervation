"""
Comprehensive Rhamnolipid Analysis Report Generator
Analyzes the effect of water hardness on rhamnolipid-polymer interactions
for shampoo conditioning deposition applications.
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import os
from datetime import datetime

# Create output directory
OUTPUT_DIR = 'analysis_output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Dark theme colors
BG_DARK = '#1e1e1e'
BG_MEDIUM = '#2d2d2d'
FG_PRIMARY = '#ffffff'
FG_SECONDARY = '#b0b0b0'

# Polymer info
POLYMER_INFO = {
    'AMT': {'full_name': 'AMT (PQ-76)', 'charge': 'Medium-High', 'family': 'Synthetic VP/Imidazole', 'color': '#4ec9b0'},
    'AMT pH 7.0': {'full_name': 'AMT (PQ-76)', 'charge': 'Medium-High', 'family': 'Synthetic VP/Imidazole', 'color': '#4ec9b0'},
    'DADMAC': {'full_name': 'DADMAC (PQ-6)', 'charge': 'Very High', 'family': 'Synthetic DADMAC', 'color': '#ce9178'},
    'DADMAC pH 7': {'full_name': 'DADMAC (PQ-6)', 'charge': 'Very High', 'family': 'Synthetic DADMAC', 'color': '#ce9178'},
    'DADMAC pH 7.0': {'full_name': 'DADMAC (PQ-6)', 'charge': 'Very High', 'family': 'Synthetic DADMAC', 'color': '#ce9178'},
    'Excel': {'full_name': 'Excel Guar', 'charge': 'Low-Medium', 'family': 'Natural Cationic Guar', 'color': '#569cd6'},
    'Excel pH 7.0': {'full_name': 'Excel Guar', 'charge': 'Low-Medium', 'family': 'Natural Cationic Guar', 'color': '#569cd6'},
    'JR30M': {'full_name': 'JR-30M (PQ-10 High)', 'charge': 'High', 'family': 'Cellulosic PQ-10', 'color': '#dcdcaa'},
    'JR30M pH 7.0': {'full_name': 'JR-30M (PQ-10 High)', 'charge': 'High', 'family': 'Cellulosic PQ-10', 'color': '#dcdcaa'},
    'KG30M': {'full_name': 'KG-30M (PQ-10 Low)', 'charge': 'Low-Medium', 'family': 'Cellulosic PQ-10', 'color': '#c586c0'},
    'KG30M pH 7.0': {'full_name': 'KG-30M (PQ-10 Low)', 'charge': 'Low-Medium', 'family': 'Cellulosic PQ-10', 'color': '#c586c0'},
    'NoPoly': {'full_name': 'No Polymer (Baseline)', 'charge': 'N/A', 'family': 'Baseline', 'color': '#9cdcfe'},
}

def get_polymer_key(polymer_name):
    """Normalize polymer names for lookup."""
    if polymer_name is None:
        return 'NoPoly'
    for key in POLYMER_INFO:
        if key.lower() in polymer_name.lower():
            return key
    return polymer_name


def setup_log_xaxis_with_labels(ax, data_min=0.15, data_max=5.0):
    """
    Set up log scale x-axis with actual concentration labels (not log units).
    Ensures at least 5 tick labels showing real concentration values.
    """
    from matplotlib.ticker import FixedLocator, FixedFormatter
    
    ax.set_xscale('log')
    
    # Choose sensible tick positions for surfactant concentration range 0.1-5%
    # These are actual concentration values that will display as-is
    all_ticks = [0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
    
    # Filter to range and ensure at least 5 ticks
    ticks = [t for t in all_ticks if data_min * 0.8 <= t <= data_max * 1.2]
    if len(ticks) < 5:
        ticks = all_ticks  # Use all if filtering reduces too much
    
    # Format labels - show actual values (not in log form)
    labels = []
    for t in ticks:
        if t >= 1:
            labels.append(f'{t:.1f}%')
        else:
            labels.append(f'{t:.2f}%')
    
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_major_formatter(FixedFormatter(labels))
    ax.set_xlim(min(ticks) * 0.9, max(ticks) * 1.1)


# Primary experiments to use for each polymer/hardness combination
# Using most complete/representative experiment for each condition
PRIMARY_EXPERIMENTS = {
    # (polymer_key, hardness): experiment_id
    ('AMT', 0): 'exp_20260217_rl_amt_0gpg',
    ('AMT', 7): '20260217_171955_Rhamnolipi_AMT_pH_7.0_7gpg',
    ('DADMAC', 0): '20260217_172032_Rhamnolipi_DADMAC_pH__0gpg',
    ('DADMAC', 7): '20260217_172101_Rhamnolipi_DADMAC_pH__7gpg',
    ('Excel', 0): '20260217_172307_Rhamnolipi_Excel_pH_7_0gpg',
    ('Excel', 7): '20260217_172153_Rhamnolipi_Excel_pH_7_7gpg',
    ('JR30M', 0): '20260218_151440_Rhamnolipi_JR30M_pH_7_0gpg',
    ('JR30M', 7): '20260218_151527_Rhamnolipi_JR30M_pH_7_7gpg',
    ('KG30M', 0): '20260218_151348_Rhamnolipi_KG30M_pH_7_0gpg',
    ('KG30M', 7): 'exp_20260112_rham_kg30',
    ('NoPoly', 0): '20260217_172750_Rhamnolipi_NoPoly_0gpg',
    ('NoPoly', 7): '20260217_172820_Rhamnolipi_NoPoly_7gpg',
}

def load_rhamnolipid_data():
    """Load rhamnolipid experiment data, using only primary experiments."""
    con = sqlite3.connect('data/phase_diagrams.db')
    
    # Get list of primary experiment IDs
    primary_exp_ids = list(PRIMARY_EXPERIMENTS.values())
    placeholders = ','.join(['?' for _ in primary_exp_ids])
    
    query = f"""
    SELECT experiment_id, experiment_name, surfactant_name, polymer_name,
           water_hardness_gpg, surfactant_pct, polymer_pct, 
           timepoint_minutes, transmission_pct
    FROM measurements
    WHERE lower(surfactant_name) LIKE '%rham%'
      AND experiment_id IN ({placeholders})
    ORDER BY polymer_name, water_hardness_gpg, timepoint_minutes, surfactant_pct
    """
    
    df = pd.read_sql_query(query, con, params=primary_exp_ids)
    con.close()
    
    # Convert transmission to absorbance
    df = df[df['transmission_pct'].notna()]
    df = df[df['transmission_pct'] > 0]
    df['absorbance'] = 2 - np.log10(df['transmission_pct'])
    df = df[np.isfinite(df['absorbance'])]
    
    # Round surfactant for grouping - use 2 decimal places to group similar values
    # within a single experiment without over-merging
    df['surfactant_pct_rounded'] = df['surfactant_pct'].round(2)
    
    # Bin close timepoints together (fixes Excel 0gpg duplicate timepoint issue)
    # Round to nearest 5 minutes to merge timepoints that are < 1 min apart
    df['timepoint_binned'] = (df['timepoint_minutes'] / 5).round() * 5
    # Replace original with binned for consistency, but store original
    df['timepoint_minutes_original'] = df['timepoint_minutes']
    df['timepoint_minutes'] = df['timepoint_binned']
    
    return df

def filter_first_n_timepoints(df, n=5):
    """
    Filter dataframe to only include the first N timepoints.
    
    Args:
        df: DataFrame with timepoint_minutes column
        n: Number of timepoints to keep (default: 5)
    
    Returns:
        Filtered DataFrame
    """
    if 'timepoint_minutes' not in df.columns:
        return df
    
    timepoints = sorted(df['timepoint_minutes'].unique())
    first_n = timepoints[:n]
    return df[df['timepoint_minutes'].isin(first_n)]


def compute_absorbance_curve(df):
    """
    Compute normalized total absorbance vs surfactant concentration.
    Groups by surfactant concentration and computes mean absorbance, then scales
    to represent total across a standard number of polymer levels (12).
    """
    # Count records per surfactant level to normalize
    counts = df.groupby('surfactant_pct_rounded').size()
    sums = df.groupby('surfactant_pct_rounded', as_index=False)['absorbance'].sum()
    
    # Normalize by record count and scale to standard polymer coverage (12 levels = typical)
    STANDARD_POLYMER_LEVELS = 12
    sums['absorbance'] = (sums['absorbance'] / counts.loc[sums['surfactant_pct_rounded']].values) * STANDARD_POLYMER_LEVELS
    
    sums = sums.sort_values('surfactant_pct_rounded')
    return sums

def compute_metrics(df):
    """Compute key metrics for a dataset."""
    if len(df) == 0:
        return {}
    
    # Absorbance curve using sum over first 5 timepoints
    df_filtered = filter_first_n_timepoints(df, n=5)
    curve = compute_absorbance_curve(df_filtered)
    
    # Peak absorbance
    peak_abs = curve['absorbance'].max()
    peak_surf = curve.loc[curve['absorbance'].idxmax(), 'surfactant_pct_rounded']
    
    # Mean absorbance
    mean_abs = curve['absorbance'].mean()
    
    # Area under curve (proxy for total aggregation)
    # Use equal spacing (no x-values) so each concentration contributes equally
    # This makes AUC independent of absolute concentration values
    auc = np.trapz(curve['absorbance'])
    
    # Time evolution metrics (only meaningful if multiple timepoints present)
    timepoints = sorted(df['timepoint_minutes'].unique())
    if len(timepoints) > 1:
        early_time = timepoints[0]
        late_time = timepoints[-1]
        
        early_abs = df[df['timepoint_minutes'] == early_time]['absorbance'].mean()
        late_abs = df[df['timepoint_minutes'] == late_time]['absorbance'].mean()
        
        kinetic_ratio = late_abs / early_abs if early_abs > 0 else 1.0
    else:
        kinetic_ratio = 1.0
    
    return {
        'peak_absorbance': peak_abs,
        'peak_surfactant': peak_surf,
        'mean_absorbance': mean_abs,
        'auc': auc,
        'kinetic_ratio': kinetic_ratio,
        'n_timepoints': len(timepoints),
        'n_records': len(df)
    }

def plot_hardness_comparison(df, polymer_name, output_path):
    """Plot 0 vs 7 gpg comparison for a polymer."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.patch.set_facecolor(BG_MEDIUM)
    
    polymer_key = get_polymer_key(polymer_name)
    info = POLYMER_INFO.get(polymer_key, {'full_name': polymer_name, 'color': '#ffffff'})
    
    # Filter data by hardness
    df_0 = df[(df['water_hardness_gpg'] == 0)]
    df_7 = df[(df['water_hardness_gpg'] == 7)]
    
    # For consistent comparison, use only the first 5 timepoints from each dataset
    df_0 = filter_first_n_timepoints(df_0, n=5)
    df_7 = filter_first_n_timepoints(df_7, n=5)
    
    # Left plot: Absorbance curves
    ax1 = axes[0]
    ax1.set_facecolor(BG_DARK)
    
    if len(df_0) > 0:
        curve_0 = compute_absorbance_curve(df_0)
        ax1.plot(curve_0['surfactant_pct_rounded'], curve_0['absorbance'], 
                 'o-', color='#4fc1ff', linewidth=2, markersize=6, label='0 gpg (Soft Water)', alpha=0.9)
    
    if len(df_7) > 0:
        curve_7 = compute_absorbance_curve(df_7)
        ax1.plot(curve_7['surfactant_pct_rounded'], curve_7['absorbance'], 
                 's-', color='#ff6b6b', linewidth=2, markersize=6, label='7 gpg (Hard Water)', alpha=0.9)
    
    setup_log_xaxis_with_labels(ax1)
    ax1.set_xlabel('Surfactant Concentration', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax1.set_ylabel('Total Absorbance (normalized)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax1.set_title(f'{info["full_name"]}\nTotal Absorbance vs Surfactant (first 5 timepoints)', fontsize=13, fontweight='bold', color=FG_PRIMARY)
    ax1.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY, fontsize=10)
    ax1.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax1.tick_params(colors=FG_PRIMARY)
    for spine in ax1.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Right plot: Metrics comparison
    ax2 = axes[1]
    ax2.set_facecolor(BG_DARK)
    
    metrics_0 = compute_metrics(df_0) if len(df_0) > 0 else {}
    metrics_7 = compute_metrics(df_7) if len(df_7) > 0 else {}
    
    metric_names = ['Peak Abs', 'Mean Abs', 'AUC', 'Kinetic Ratio']
    x = np.arange(len(metric_names))
    width = 0.35
    
    vals_0 = [metrics_0.get('peak_absorbance', 0), metrics_0.get('mean_absorbance', 0), 
              metrics_0.get('auc', 0)/10, metrics_0.get('kinetic_ratio', 1)]  # AUC scaled
    vals_7 = [metrics_7.get('peak_absorbance', 0), metrics_7.get('mean_absorbance', 0), 
              metrics_7.get('auc', 0)/10, metrics_7.get('kinetic_ratio', 1)]
    
    bars1 = ax2.bar(x - width/2, vals_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    bars2 = ax2.bar(x + width/2, vals_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    
    ax2.set_ylabel('Value', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax2.set_title('Key Metrics Comparison', fontsize=13, fontweight='bold', color=FG_PRIMARY)
    ax2.set_xticks(x)
    ax2.set_xticklabels(metric_names, color=FG_PRIMARY, fontsize=10)
    ax2.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax2.tick_params(colors=FG_PRIMARY)
    for spine in ax2.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax2.annotate(f'{height:.2f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom',
                           color=FG_PRIMARY, fontsize=8)
    
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150)
    plt.close(fig)
    
    return metrics_0, metrics_7

def plot_polymer_comparison(all_data, hardness, output_path):
    """Compare all polymers at a given hardness level."""
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax.set_facecolor(BG_DARK)
    
    # Get unique polymers
    polymers = all_data['polymer_name'].unique()
    
    for polymer in polymers:
        if polymer is None:
            continue
        
        df_poly = all_data[(all_data['polymer_name'] == polymer) & 
                          (all_data['water_hardness_gpg'] == hardness)]
        
        if len(df_poly) == 0:
            continue
        
        # Use first 5 timepoints for consistent comparison
        df_poly = filter_first_n_timepoints(df_poly, n=5)
        
        polymer_key = get_polymer_key(polymer)
        info = POLYMER_INFO.get(polymer_key, {'full_name': polymer, 'color': '#ffffff'})
        
        curve = compute_absorbance_curve(df_poly)
        ax.plot(curve['surfactant_pct_rounded'], curve['absorbance'], 
                'o-', linewidth=2, markersize=5, label=info['full_name'], 
                color=info['color'], alpha=0.85)
    
    setup_log_xaxis_with_labels(ax)
    ax.set_xlabel('Surfactant Concentration', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Total Absorbance (normalized)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'Polymer Comparison at {hardness} gpg Water Hardness\nRhamnolipid System (first 5 timepoints)', 
                 fontsize=15, fontweight='bold', color=FG_PRIMARY, pad=15)
    ax.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY, fontsize=10, loc='best')
    ax.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax.tick_params(colors=FG_PRIMARY, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150)
    plt.close(fig)

def plot_heatmap(df, title, output_path):
    """Generate absorbance evolution heatmap."""
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax.set_facecolor(BG_DARK)
    
    # Group and pivot
    grouped = df.groupby(['timepoint_minutes', 'surfactant_pct_rounded'], as_index=False)['absorbance'].sum()
    
    try:
        pivot = grouped.pivot(index='timepoint_minutes', columns='surfactant_pct_rounded', values='absorbance')
    except:
        print(f"Could not create heatmap for {title}")
        plt.close(fig)
        return
    
    if pivot.shape[0] < 2 or pivot.shape[1] < 2:
        print(f"Insufficient data for heatmap: {title}")
        plt.close(fig)
        return
    
    im = ax.imshow(pivot.values, aspect='auto', cmap='viridis', interpolation='bilinear')
    
    # X-axis labels
    surfactants = pivot.columns.values
    n_x = min(10, len(surfactants))
    tick_x = np.linspace(0, len(surfactants)-1, n_x, dtype=int)
    ax.set_xticks(tick_x)
    ax.set_xticklabels([f'{surfactants[i]:.2f}' for i in tick_x], fontsize=10, color=FG_PRIMARY, rotation=45, ha='right')
    
    # Y-axis labels
    timepoints = pivot.index.values
    n_y = min(10, len(timepoints))
    tick_y = np.linspace(0, len(timepoints)-1, n_y, dtype=int)
    ax.set_yticks(tick_y)
    ax.set_yticklabels([f'{timepoints[i]:.1f}' for i in tick_y], fontsize=10, color=FG_PRIMARY)
    
    ax.set_xlabel('Surfactant Concentration (%)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Time (minutes)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(title, fontsize=13, fontweight='bold', color=FG_PRIMARY, pad=15)
    
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label('Total Absorbance', color=FG_PRIMARY, fontsize=11)
    cbar.ax.tick_params(colors=FG_PRIMARY)
    
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150)
    plt.close(fig)


def plot_kinetics(df, polymer_name, hardness, output_path):
    """Plot absorbance kinetics at key surfactant concentrations."""
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax.set_facecolor(BG_DARK)
    
    polymer_key = get_polymer_key(polymer_name)
    info = POLYMER_INFO.get(polymer_key, {'full_name': polymer_name, 'color': '#ffffff'})
    
    # Find peak and interesting surfactant concentrations
    curve = compute_absorbance_curve(df)
    if len(curve) == 0:
        plt.close(fig)
        return None
    
    peak_surf = curve.loc[curve['absorbance'].idxmax(), 'surfactant_pct_rounded']
    all_surfs = sorted(df['surfactant_pct_rounded'].unique())
    
    # Select ~5 representative concentrations spanning the range
    n_surfs = len(all_surfs)
    if n_surfs <= 5:
        selected_surfs = all_surfs
    else:
        indices = np.linspace(0, n_surfs - 1, 5, dtype=int)
        selected_surfs = [all_surfs[i] for i in indices]
        # Ensure peak is included
        if peak_surf not in selected_surfs:
            selected_surfs.append(peak_surf)
            selected_surfs = sorted(selected_surfs)
    
    # Color gradient
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(selected_surfs)))
    
    kinetics_data = []
    for i, surf in enumerate(selected_surfs):
        df_surf = df[df['surfactant_pct_rounded'] == surf]
        if len(df_surf) < 2:
            continue
        
        # Group by timepoint
        kinetic = df_surf.groupby('timepoint_minutes', as_index=False)['absorbance'].sum()
        kinetic = kinetic.sort_values('timepoint_minutes')
        
        marker = '*' if abs(surf - peak_surf) < 0.01 else 'o'
        markersize = 10 if marker == '*' else 6
        label = f'{surf:.2f}%' + (' (peak)' if marker == '*' else '')
        
        ax.plot(kinetic['timepoint_minutes'], kinetic['absorbance'], 
                f'{marker}-', color=colors[i], linewidth=2, markersize=markersize,
                label=label, alpha=0.9)
        
        # Store kinetics data
        if len(kinetic) > 1:
            t_half = None
            max_abs = kinetic['absorbance'].max()
            half_level = max_abs / 2
            for _, row in kinetic.iterrows():
                if row['absorbance'] >= half_level:
                    t_half = row['timepoint_minutes']
                    break
            kinetics_data.append({
                'surfactant': surf,
                'initial_abs': kinetic['absorbance'].iloc[0],
                'final_abs': kinetic['absorbance'].iloc[-1],
                'max_abs': max_abs,
                't_half': t_half,
                'stability': kinetic['absorbance'].iloc[-1] / kinetic['absorbance'].max() if kinetic['absorbance'].max() > 0 else 1
            })
    
    ax.set_xlabel('Time (minutes)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Absorbance', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'{info["full_name"]} - {int(hardness)} gpg\nCoacervation Kinetics at Various Surfactant Concentrations', 
                 fontsize=14, fontweight='bold', color=FG_PRIMARY, pad=15)
    ax.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY, 
              fontsize=10, title='Surfactant %', title_fontsize=11, loc='best')
    ax.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax.tick_params(colors=FG_PRIMARY, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150)
    plt.close(fig)
    
    return kinetics_data


def plot_transmission_curves(df, polymer_name, hardness, output_path):
    """Plot traditional transmission % vs surfactant concentration at various timepoints."""
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax.set_facecolor(BG_DARK)
    
    polymer_key = get_polymer_key(polymer_name)
    info = POLYMER_INFO.get(polymer_key, {'full_name': polymer_name, 'color': '#ffffff'})
    
    # Get timepoints
    timepoints = sorted(df['timepoint_minutes'].unique())
    n_times = len(timepoints)
    
    if n_times <= 6:
        selected_times = timepoints
    else:
        # Select early, middle, and late timepoints
        indices = np.linspace(0, n_times - 1, 6, dtype=int)
        selected_times = [timepoints[i] for i in indices]
    
    # Color gradient from light to dark
    colors = plt.cm.plasma(np.linspace(0.15, 0.85, len(selected_times)))
    
    for i, t in enumerate(selected_times):
        df_t = df[df['timepoint_minutes'] == t]
        
        # Group by surfactant concentration  
        trans_curve = df_t.groupby('surfactant_pct_rounded', as_index=False)['transmission_pct'].mean()
        trans_curve = trans_curve.sort_values('surfactant_pct_rounded')
        
        if len(trans_curve) < 2:
            continue
        
        ax.plot(trans_curve['surfactant_pct_rounded'], trans_curve['transmission_pct'], 
                'o-', color=colors[i], linewidth=2, markersize=5, 
                label=f't = {t:.0f} min', alpha=0.9)
    
    setup_log_xaxis_with_labels(ax)
    ax.set_xlabel('Surfactant Concentration', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Transmission (%)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'{info["full_name"]} - {int(hardness)} gpg\nTransmission vs Surfactant (Traditional Phase Diagram View)', 
                 fontsize=14, fontweight='bold', color=FG_PRIMARY, pad=15)
    
    # Add phase region annotations
    ax.axhline(y=50, color='#ff6b6b', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(ax.get_xlim()[0] * 1.5, 52, 'Clear', color='#4fc1ff', fontsize=10, alpha=0.7)
    ax.text(ax.get_xlim()[0] * 1.5, 45, 'Turbid/Coacervate', color='#ff6b6b', fontsize=10, alpha=0.7)
    
    ax.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY, 
              fontsize=10, title='Timepoint', title_fontsize=11, loc='best')
    ax.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax.tick_params(colors=FG_PRIMARY, labelsize=11)
    ax.set_ylim(0, 105)
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150)
    plt.close(fig)


def plot_stability_comparison(all_data, output_path):
    """Plot stability comparison across all systems."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor(BG_MEDIUM)
    
    stability_data = []
    
    for polymer in all_data['polymer_normalized'].unique():
        df_poly = all_data[all_data['polymer_normalized'] == polymer]
        info = POLYMER_INFO.get(polymer, {'full_name': polymer, 'color': '#ffffff'})
        
        for hardness in [0, 7]:
            df_h = df_poly[df_poly['water_hardness_gpg'] == hardness]
            if len(df_h) == 0:
                continue
            
            # Get peak surfactant region
            curve = compute_absorbance_curve(df_h)
            if len(curve) == 0:
                continue
            peak_surf = curve.loc[curve['absorbance'].idxmax(), 'surfactant_pct_rounded']
            
            # Find data near peak
            df_peak = df_h[abs(df_h['surfactant_pct_rounded'] - peak_surf) < 0.1]
            if len(df_peak) < 2:
                continue
            
            kinetic = df_peak.groupby('timepoint_minutes', as_index=False)['absorbance'].sum()
            kinetic = kinetic.sort_values('timepoint_minutes')
            
            if len(kinetic) > 1:
                initial = kinetic['absorbance'].iloc[0]
                final = kinetic['absorbance'].iloc[-1]
                max_abs = kinetic['absorbance'].max()
                
                # Time to 90% of max
                t_90 = None
                level_90 = max_abs * 0.9
                for _, row in kinetic.iterrows():
                    if row['absorbance'] >= level_90:
                        t_90 = row['timepoint_minutes']
                        break
                
                stability_data.append({
                    'polymer': polymer,
                    'full_name': info['full_name'],
                    'hardness': hardness,
                    'color': info['color'],
                    'initial_abs': initial,
                    'final_abs': final,
                    'max_abs': max_abs,
                    't_90': t_90 if t_90 else kinetic['timepoint_minutes'].max(),
                    'stability_ratio': final / max_abs if max_abs > 0 else 1.0
                })
    
    # Left plot: Time to 90% coacervation
    ax1 = axes[0]
    ax1.set_facecolor(BG_DARK)
    
    df_stab = pd.DataFrame(stability_data)
    
    polymers_unique = df_stab['polymer'].unique()
    x = np.arange(len(polymers_unique))
    width = 0.35
    
    t90_0 = []
    t90_7 = []
    colors_list = []
    
    for poly in polymers_unique:
        row_0 = df_stab[(df_stab['polymer'] == poly) & (df_stab['hardness'] == 0)]
        row_7 = df_stab[(df_stab['polymer'] == poly) & (df_stab['hardness'] == 7)]
        t90_0.append(row_0['t_90'].values[0] if len(row_0) > 0 else 0)
        t90_7.append(row_7['t_90'].values[0] if len(row_7) > 0 else 0)
        colors_list.append(df_stab[df_stab['polymer'] == poly]['color'].values[0])
    
    ax1.bar(x - width/2, t90_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    ax1.bar(x + width/2, t90_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    ax1.set_ylabel('Time to 90% Max (min)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax1.set_title('Coacervation Formation Rate\n(Lower = Faster Formation)', fontsize=13, fontweight='bold', color=FG_PRIMARY)
    ax1.set_xticks(x)
    ax1.set_xticklabels(polymers_unique, rotation=45, ha='right', fontsize=10, color=FG_PRIMARY)
    ax1.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax1.tick_params(colors=FG_PRIMARY)
    for spine in ax1.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Right plot: Stability ratio (final/max)
    ax2 = axes[1]
    ax2.set_facecolor(BG_DARK)
    
    stab_0 = []
    stab_7 = []
    
    for poly in polymers_unique:
        row_0 = df_stab[(df_stab['polymer'] == poly) & (df_stab['hardness'] == 0)]
        row_7 = df_stab[(df_stab['polymer'] == poly) & (df_stab['hardness'] == 7)]
        stab_0.append(row_0['stability_ratio'].values[0] * 100 if len(row_0) > 0 else 0)
        stab_7.append(row_7['stability_ratio'].values[0] * 100 if len(row_7) > 0 else 0)
    
    ax2.bar(x - width/2, stab_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    ax2.bar(x + width/2, stab_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    ax2.axhline(y=100, color=FG_SECONDARY, linestyle='--', alpha=0.5)
    ax2.set_ylabel('Stability (% of Max Retained)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax2.set_title('Coacervate Stability\n(100% = No Dissolution at End)', fontsize=13, fontweight='bold', color=FG_PRIMARY)
    ax2.set_xticks(x)
    ax2.set_xticklabels(polymers_unique, rotation=45, ha='right', fontsize=10, color=FG_PRIMARY)
    ax2.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax2.tick_params(colors=FG_PRIMARY)
    ax2.set_ylim(0, 130)
    for spine in ax2.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.suptitle('Kinetics Summary - Formation Rate & Stability', fontsize=15, fontweight='bold', color=FG_PRIMARY, y=1.02)
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150, bbox_inches='tight')
    plt.close(fig)


def generate_summary_plot(metrics_summary, output_path):
    """Generate summary comparison of all polymers."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG_MEDIUM)
    
    polymers = list(metrics_summary.keys())
    
    # Hardness sensitivity (difference in peak absorbance)
    ax1 = axes[0, 0]
    ax1.set_facecolor(BG_DARK)
    
    hardness_sens = []
    colors = []
    for poly in polymers:
        m = metrics_summary[poly]
        peak_0 = m.get('0gpg', {}).get('peak_absorbance', 0)
        peak_7 = m.get('7gpg', {}).get('peak_absorbance', 0)
        # Use signed value to show direction of change
        sens = (peak_7 - peak_0) / max(peak_0, 0.001) * 100
        hardness_sens.append(sens)
        info = POLYMER_INFO.get(get_polymer_key(poly), {'color': '#ffffff'})
        colors.append(info['color'])
    
    bars = ax1.barh(polymers, hardness_sens, color=colors, alpha=0.8)
    ax1.axvline(x=0, color=FG_SECONDARY, linestyle='-', alpha=0.5)  # Zero reference line
    ax1.set_xlabel('Peak Absorbance Change (%)', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax1.set_title('Water Hardness Effect\n(% change in peak absorbance 0→7 gpg)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax1.tick_params(colors=FG_PRIMARY)
    for spine in ax1.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Peak absorbance comparison
    ax2 = axes[0, 1]
    ax2.set_facecolor(BG_DARK)
    
    x = np.arange(len(polymers))
    width = 0.35
    peaks_0 = [metrics_summary[p].get('0gpg', {}).get('peak_absorbance', 0) for p in polymers]
    peaks_7 = [metrics_summary[p].get('7gpg', {}).get('peak_absorbance', 0) for p in polymers]
    
    ax2.bar(x - width/2, peaks_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    ax2.bar(x + width/2, peaks_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    ax2.set_ylabel('Peak Absorbance', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax2.set_title('Peak Absorbance by Polymer', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax2.set_xticks(x)
    ax2.set_xticklabels(polymers, rotation=45, ha='right', fontsize=9, color=FG_PRIMARY)
    ax2.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax2.tick_params(colors=FG_PRIMARY)
    for spine in ax2.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Kinetic ratio
    ax3 = axes[1, 0]
    ax3.set_facecolor(BG_DARK)
    
    kinetic_0 = [metrics_summary[p].get('0gpg', {}).get('kinetic_ratio', 1) for p in polymers]
    kinetic_7 = [metrics_summary[p].get('7gpg', {}).get('kinetic_ratio', 1) for p in polymers]
    
    ax3.bar(x - width/2, kinetic_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    ax3.bar(x + width/2, kinetic_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    ax3.axhline(y=1.0, color=FG_SECONDARY, linestyle='--', alpha=0.5)
    ax3.set_ylabel('Kinetic Ratio (late/early)', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax3.set_title('Kinetic Evolution\n(>1 = increasing turbidity over time)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax3.set_xticks(x)
    ax3.set_xticklabels(polymers, rotation=45, ha='right', fontsize=9, color=FG_PRIMARY)
    ax3.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax3.tick_params(colors=FG_PRIMARY)
    for spine in ax3.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # AUC (total aggregation)
    ax4 = axes[1, 1]
    ax4.set_facecolor(BG_DARK)
    
    auc_0 = [metrics_summary[p].get('0gpg', {}).get('auc', 0) for p in polymers]
    auc_7 = [metrics_summary[p].get('7gpg', {}).get('auc', 0) for p in polymers]
    
    ax4.bar(x - width/2, auc_0, width, label='0 gpg', color='#4fc1ff', alpha=0.8)
    ax4.bar(x + width/2, auc_7, width, label='7 gpg', color='#ff6b6b', alpha=0.8)
    ax4.set_ylabel('Area Under Curve (AUC)', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax4.set_title('Total Aggregation (AUC)\n(Higher = more phase separation)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax4.set_xticks(x)
    ax4.set_xticklabels(polymers, rotation=45, ha='right', fontsize=9, color=FG_PRIMARY)
    ax4.legend(facecolor=BG_DARK, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax4.tick_params(colors=FG_PRIMARY)
    for spine in ax4.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.suptitle('Rhamnolipid-Polymer Interaction Summary\nWater Hardness Effect Analysis', 
                 fontsize=16, fontweight='bold', color=FG_PRIMARY, y=1.02)
    fig.tight_layout()
    fig.savefig(output_path, facecolor=BG_MEDIUM, dpi=150, bbox_inches='tight')
    plt.close(fig)

def main():
    print("=" * 60)
    print("RHAMNOLIPID COMPREHENSIVE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    print("Loading data...")
    df = load_rhamnolipid_data()
    print(f"  Total records: {len(df)}")
    
    # Get unique polymer/hardness combinations
    combos = df.groupby(['polymer_name', 'water_hardness_gpg']).size().reset_index(name='count')
    print(f"  Unique polymer/hardness combinations: {len(combos)}")
    print()
    
    # Normalize polymer names for grouping
    df['polymer_normalized'] = df['polymer_name'].apply(lambda x: get_polymer_key(x) if x else 'NoPoly')
    
    # Store metrics
    metrics_summary = {}
    
    # Generate comparisons for each polymer
    print("Generating polymer analyses...")
    
    unique_polymers = df['polymer_normalized'].unique()
    
    for polymer in unique_polymers:
        print(f"  Processing: {polymer}")
        
        df_polymer = df[df['polymer_normalized'] == polymer]
        
        # Check what hardness levels we have
        hardness_levels = df_polymer['water_hardness_gpg'].unique()
        
        metrics_summary[polymer] = {}
        
        # Generate hardness comparison if we have both
        if 0 in hardness_levels or 7 in hardness_levels:
            output_file = os.path.join(OUTPUT_DIR, f'hardness_comparison_{polymer}.png')
            df_0 = df_polymer[df_polymer['water_hardness_gpg'] == 0]
            df_7 = df_polymer[df_polymer['water_hardness_gpg'] == 7]
            
            metrics_0, metrics_7 = plot_hardness_comparison(df_polymer, polymer, output_file)
            metrics_summary[polymer]['0gpg'] = metrics_0
            metrics_summary[polymer]['7gpg'] = metrics_7
            print(f"    - Saved hardness comparison: {output_file}")
        
        # Generate heatmaps for each hardness level
        for hardness in hardness_levels:
            df_h = df_polymer[df_polymer['water_hardness_gpg'] == hardness]
            if len(df_h) > 0:
                info = POLYMER_INFO.get(polymer, {'full_name': polymer})
                title = f"{info['full_name']} - {int(hardness)} gpg\nAbsorbance Evolution"
                output_file = os.path.join(OUTPUT_DIR, f'heatmap_{polymer}_{int(hardness)}gpg.png')
                plot_heatmap(df_h, title, output_file)
                print(f"    - Saved heatmap: {output_file}")
                
                # Generate kinetics plot
                kinetics_file = os.path.join(OUTPUT_DIR, f'kinetics_{polymer}_{int(hardness)}gpg.png')
                plot_kinetics(df_h, polymer, hardness, kinetics_file)
                print(f"    - Saved kinetics: {kinetics_file}")
                
                # Generate traditional transmission curves
                trans_file = os.path.join(OUTPUT_DIR, f'transmission_{polymer}_{int(hardness)}gpg.png')
                plot_transmission_curves(df_h, polymer, hardness, trans_file)
                print(f"    - Saved transmission curves: {trans_file}")
    
    # Generate cross-polymer comparison at each hardness level
    print("\nGenerating cross-polymer comparisons...")
    
    for hardness in [0, 7]:
        df_h = df[df['water_hardness_gpg'] == hardness]
        if len(df_h) > 0:
            output_file = os.path.join(OUTPUT_DIR, f'polymer_comparison_{int(hardness)}gpg.png')
            plot_polymer_comparison(df, hardness, output_file)
            print(f"  Saved: {output_file}")
    
    # Generate kinetics summary plot
    print("\nGenerating kinetics summary...")
    stability_file = os.path.join(OUTPUT_DIR, 'kinetics_summary.png')
    plot_stability_comparison(df, stability_file)
    print(f"  Saved: {stability_file}")
    
    # Generate summary plot
    print("\nGenerating summary visualization...")
    output_file = os.path.join(OUTPUT_DIR, 'summary_metrics.png')
    generate_summary_plot(metrics_summary, output_file)
    print(f"  Saved: {output_file}")
    
    # Print metrics summary
    print("\n" + "=" * 60)
    print("METRICS SUMMARY")
    print("=" * 60)
    
    for polymer, data in metrics_summary.items():
        info = POLYMER_INFO.get(polymer, {'full_name': polymer, 'charge': 'Unknown'})
        print(f"\n{info['full_name']} (Charge: {info.get('charge', 'Unknown')})")
        print("-" * 40)
        
        for gpg, metrics in data.items():
            if metrics:
                print(f"  {gpg}:")
                print(f"    Peak Abs: {metrics.get('peak_absorbance', 0):.2f} @ {metrics.get('peak_surfactant', 0):.3f}%")
                print(f"    Mean Abs: {metrics.get('mean_absorbance', 0):.2f}")
                print(f"    AUC: {metrics.get('auc', 0):.2f}")
                print(f"    Kinetic Ratio: {metrics.get('kinetic_ratio', 1):.2f}")
    
    # Save metrics to CSV
    metrics_rows = []
    for polymer, data in metrics_summary.items():
        for gpg, metrics in data.items():
            if metrics:
                row = {
                    'polymer': polymer,
                    'hardness': gpg,
                    **metrics
                }
                metrics_rows.append(row)
    
    if metrics_rows:
        metrics_df = pd.DataFrame(metrics_rows)
        metrics_file = os.path.join(OUTPUT_DIR, 'metrics_summary.csv')
        metrics_df.to_csv(metrics_file, index=False)
        print(f"\nMetrics saved to: {metrics_file}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print(f"Output files saved to: {OUTPUT_DIR}/")
    print("=" * 60)
    
    return metrics_summary

if __name__ == "__main__":
    main()
