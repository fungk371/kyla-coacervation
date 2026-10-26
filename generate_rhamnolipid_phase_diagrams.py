"""
Generate phase diagrams and kinetics plots for Rhamnolipid experiments.
Creates plots matching the style of the existing phase_diagrams_presentation.pptx
but organized by polymer and water hardness level.
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter
from matplotlib.patches import Patch
from pathlib import Path
import os

# Import shared plotting functions
from phase_plotting import create_phase_diagram_grids, plot_continuous_map, plot_binary_boundary

# Dark theme colors (matching existing rhamnolipid presentation)
BG_DARK = '#1e1e1e'
BG_MEDIUM = '#2d2d2d'
FG_PRIMARY = '#ffffff'
FG_SECONDARY = '#b0b0b0'

# Output directory
OUTPUT_DIR = Path('analysis_output/rhamnolipid_phase_diagrams')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Database path
DB_PATH = 'data/phase_diagrams.db'

# Primary experiments to use (one per polymer/hardness combination)
PRIMARY_EXPERIMENTS = {
    ('AMT', 0): 'exp_20260217_rl_amt_0gpg',
    ('AMT', 7): '20260217_171955_Rhamnolipi_AMT_pH_7.0_7gpg',
    ('DADMAC', 0): '20260217_172032_Rhamnolipi_DADMAC_pH__0gpg',
    ('DADMAC', 7): '20260217_172101_Rhamnolipi_DADMAC_pH__7gpg',
    ('Excel', 0): '20260217_172307_Rhamnolipi_Excel_pH_7_0gpg',
    ('Excel', 7): '20260217_172153_Rhamnolipi_Excel_pH_7_7gpg',
    ('JR30M', 0): '20260218_151440_Rhamnolipi_JR30M_pH_7_0gpg',
    ('JR30M', 7): '20260218_151527_Rhamnolipi_JR30M_pH_7_7gpg',
    ('KG30M', 0): '20260218_151348_Rhamnolipi_KG30M_pH_7_0gpg',
    ('KG30M', 7): 'exp_20260112_rham_kg30',  # Only 7gpg available
}

# Polymer display colors
POLYMER_COLORS = {
    'AMT': '#ff6b6b',
    'DADMAC': '#4ecdc4',
    'Excel': '#45b7d1',
    'JR30M': '#fed766',
    'KG30M': '#9b59b6',
}


def get_equilibrium_timepoint(experiment_id):
    """Determine equilibrium timepoint using 95% of final value criterion."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT timepoint_minutes, transmission_pct
        FROM measurements
        WHERE experiment_id = ?
    """
    raw_df = pd.read_sql_query(query, conn, params=[experiment_id])
    conn.close()
    
    if len(raw_df) == 0:
        return 0
    
    # Bin timepoints to nearest 5 minutes
    raw_df['timepoint_binned'] = (raw_df['timepoint_minutes'] / 5).round() * 5
    df = raw_df.groupby('timepoint_binned').agg(
        avg_trans=('transmission_pct', 'mean')
    ).reset_index()
    df = df.sort_values('timepoint_binned')
    
    if len(df) < 2:
        return df['timepoint_binned'].iloc[-1] if len(df) > 0 else 0
    
    final_avg = df['avg_trans'].iloc[-1]
    threshold_95 = final_avg * 0.95
    
    for _, row in df.iterrows():
        if row['avg_trans'] >= threshold_95:
            return row['timepoint_binned']
    
    return df['timepoint_binned'].iloc[-1]


def load_experiment_data(experiment_id, timepoint=None):
    """Load data for a specific experiment, optionally at a specific binned timepoint."""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT *
        FROM measurements
        WHERE experiment_id = ?
    """
    data = pd.read_sql_query(query, conn, params=[experiment_id])
    conn.close()
    
    # Bin timepoints
    data['timepoint_binned'] = (data['timepoint_minutes'] / 5).round() * 5
    
    if timepoint is not None:
        # Filter to matching binned timepoint
        data = data[data['timepoint_binned'] == timepoint]
    
    return data


def load_kinetic_data(experiment_id):
    """Load aggregated kinetic data for an experiment, with timepoint binning."""
    conn = sqlite3.connect(DB_PATH)
    
    # First get raw data
    query = """
        SELECT timepoint_minutes, transmission_pct
        FROM measurements
        WHERE experiment_id = ?
    """
    raw_df = pd.read_sql_query(query, conn, params=[experiment_id])
    conn.close()
    
    # Bin timepoints to nearest 5 minutes to handle duplicate timepoint issue
    raw_df['timepoint_binned'] = (raw_df['timepoint_minutes'] / 5).round() * 5
    
    # Aggregate by binned timepoint
    df = raw_df.groupby('timepoint_binned').agg(
        avg_trans=('transmission_pct', 'mean'),
        min_trans=('transmission_pct', 'min'),
        max_trans=('transmission_pct', 'max'),
        std_trans=('transmission_pct', 'std'),
        n_wells=('transmission_pct', 'count')
    ).reset_index()
    df = df.rename(columns={'timepoint_binned': 'timepoint_minutes'})
    
    # Calculate rate of change
    df['rate_of_change'] = df['avg_trans'].diff() / df['timepoint_minutes'].diff()
    
    return df


def create_phase_diagram_figure(data, polymer, hardness, equilibrium_timepoint):
    """Create a 4-panel phase diagram figure matching existing presentation style."""
    fig = plt.figure(figsize=(14, 10), facecolor='white')
    axes = fig.subplots(2, 2)
    
    hardness_str = f'{hardness} gpg' if hardness > 0 else 'Soft Water (0 gpg)'
    fig.suptitle(f'Rhamnolipid - {polymer}\n{hardness_str} at {equilibrium_timepoint:.1f} min (Equilibrium)',
                fontsize=16, fontweight='bold')
    
    # Create interpolated grid using GP method (same as existing presentation)
    try:
        AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
            data, n_points=800, method='gp', gp_length_scale=0.18, gaussian_sigma=6.0
        )
    except Exception as e:
        print(f"  Warning: GP method failed, using griddata: {e}")
        AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
            data, n_points=400, method='griddata', gaussian_sigma=3.0
        )
    
    threshold = 75.0
    surfactant = 'Rhamnolipid'
    
    # Plot 1: Continuous transmission map
    plot_continuous_map(axes[0, 0], AS_grid, PS_grid, trans_grid, data, threshold,
                       surfactant, polymer, fig=fig)
    axes[0, 0].set_title(f'Continuous Transmission Map', fontweight='bold')
    
    # Plot 2: Phase classification (binary with filled contours)
    phase_colors = ['#e74c3c', '#2ecc71']
    axes[0, 1].contourf(AS_grid, PS_grid, trans_grid, levels=[35, threshold, 95],
                       colors=phase_colors, alpha=0.7)
    axes[0, 1].contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                      colors='black', linewidths=2.5)
    
    data_copy = data.copy()
    data_copy['phase'] = pd.cut(data_copy['transmission_pct'], bins=[0, threshold, 100],
                                labels=['Precipitate', 'Clear'])
    axes[0, 1].scatter(data_copy['surfactant_pct'], data_copy['polymer_pct'],
                      c=[('#e74c3c' if p == 'Precipitate' else '#2ecc71') for p in data_copy['phase']],
                      s=20, edgecolors='black', linewidth=0.5, alpha=0.8)
    
    axes[0, 1].set_xlabel(f'{surfactant} Concentration (%)', fontsize=10, fontweight='bold')
    axes[0, 1].set_ylabel(f'{polymer} Concentration (%)', fontsize=10, fontweight='bold')
    axes[0, 1].set_title('Phase Classification', fontsize=11, fontweight='bold')
    axes[0, 1].set_xscale('log')
    axes[0, 1].set_yscale('log')
    axes[0, 1].grid(True, alpha=0.3, which='both')
    
    # Set tick locations for Rhamnolipid concentration range (0.15% - 5%)
    x_ticks = [0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    axes[0, 1].xaxis.set_major_locator(FixedLocator(x_ticks))
    axes[0, 1].yaxis.set_major_locator(FixedLocator(y_ticks))
    axes[0, 1].xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.2g}'))
    axes[0, 1].yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    
    legend_elements = [Patch(facecolor='#e74c3c', edgecolor='black', label=f'Precipitate (<{threshold:.0f}%)'),
                      Patch(facecolor='#2ecc71', edgecolor='black', label=f'Clear (≥{threshold:.0f}%)')]
    axes[0, 1].legend(handles=legend_elements, loc='upper left', fontsize=8)
    
    # Plot 3: Binary phase boundary
    plot_binary_boundary(axes[1, 0], AS_grid, PS_grid, trans_grid, data, threshold,
                        surfactant, polymer, fig=fig)
    # Update x-axis ticks for this plot too
    axes[1, 0].xaxis.set_major_locator(FixedLocator(x_ticks))
    axes[1, 0].xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.2g}'))
    
    # Plot 4: Transmission histogram
    bins = np.arange(30, 100, 5)
    axes[1, 1].hist(data['transmission_pct'], bins=bins, color='steelblue', alpha=0.7, edgecolor='black')
    axes[1, 1].axvline(threshold, color='black', linewidth=2.5, linestyle='-',
                      label=f'Threshold ({threshold:.0f}%)')
    axes[1, 1].set_xlabel('Transmission (%)', fontsize=10, fontweight='bold')
    axes[1, 1].set_ylabel('Frequency', fontsize=10, fontweight='bold')
    axes[1, 1].set_title('Transmission Distribution', fontsize=11, fontweight='bold')
    axes[1, 1].legend(fontsize=9)
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def create_kinetic_analysis_figure(kinetic_data, polymer, hardness):
    """Create kinetic analysis figure with 4 subplots."""
    fig = plt.figure(figsize=(14, 10), facecolor='white')
    axes = fig.subplots(2, 2)
    
    hardness_str = f'{hardness} gpg' if hardness > 0 else 'Soft Water (0 gpg)'
    fig.suptitle(f'Rhamnolipid - {polymer} Kinetics\n{hardness_str}',
                fontsize=16, fontweight='bold')
    
    # Plot 1: Average transmission vs time
    ax1 = axes[0, 0]
    ax1.plot(kinetic_data['timepoint_minutes'], kinetic_data['avg_trans'],
            'o-', color='#2ecc71', linewidth=2, markersize=8, label='Mean Transmission')
    ax1.fill_between(kinetic_data['timepoint_minutes'],
                    kinetic_data['avg_trans'] - kinetic_data['std_trans'],
                    kinetic_data['avg_trans'] + kinetic_data['std_trans'],
                    alpha=0.3, color='#2ecc71', label='±1 Std Dev')
    
    final_avg = kinetic_data['avg_trans'].iloc[-1]
    ax1.axhline(final_avg, color='#e74c3c', linestyle='--', linewidth=2,
               label=f'Final Value ({final_avg:.1f}%)')
    
    ax1.set_xlabel('Time (minutes)', fontweight='bold')
    ax1.set_ylabel('Transmission (%)', fontweight='bold')
    ax1.set_title('Mean Transmission Evolution', fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Rate of change
    ax2 = axes[0, 1]
    ax2.plot(kinetic_data['timepoint_minutes'].iloc[1:], kinetic_data['rate_of_change'].iloc[1:],
            'o-', color='#3498db', linewidth=2, markersize=8)
    ax2.axhline(0, color='gray', linestyle='--', linewidth=1)
    
    ax2.set_xlabel('Time (minutes)', fontweight='bold')
    ax2.set_ylabel('Rate of Change (%/min)', fontweight='bold')
    ax2.set_title('Kinetic Rate Analysis', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Min/Max range
    ax3 = axes[1, 0]
    ax3.fill_between(kinetic_data['timepoint_minutes'],
                    kinetic_data['min_trans'],
                    kinetic_data['max_trans'],
                    alpha=0.4, color='#9b59b6', label='Min-Max Range')
    ax3.plot(kinetic_data['timepoint_minutes'], kinetic_data['avg_trans'],
            'o-', color='#2ecc71', linewidth=2, markersize=6, label='Mean')
    
    ax3.set_xlabel('Time (minutes)', fontweight='bold')
    ax3.set_ylabel('Transmission (%)', fontweight='bold')
    ax3.set_title('Data Distribution Over Time', fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Number of wells sampled
    ax4 = axes[1, 1]
    ax4.bar(kinetic_data['timepoint_minutes'], kinetic_data['n_wells'],
           color='#3498db', alpha=0.7, edgecolor='black', width=5)
    
    ax4.set_xlabel('Time (minutes)', fontweight='bold')
    ax4.set_ylabel('Number of Wells', fontweight='bold')
    ax4.set_title('Data Density Over Time', fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    return fig


def create_hardness_comparison_figure(polymer):
    """Create side-by-side phase diagram comparison for 0 vs 7 gpg."""
    fig = plt.figure(figsize=(16, 7), facecolor='white')
    
    fig.suptitle(f'Rhamnolipid - {polymer}: Water Hardness Comparison',
                fontsize=16, fontweight='bold')
    
    axes = fig.subplots(1, 2)
    
    for idx, hardness in enumerate([0, 7]):
        ax = axes[idx]
        
        key = (polymer, hardness)
        if key not in PRIMARY_EXPERIMENTS:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', fontsize=14)
            ax.set_title(f'{hardness} gpg - No Data')
            continue
        
        exp_id = PRIMARY_EXPERIMENTS[key]
        eq_time = get_equilibrium_timepoint(exp_id)
        data = load_experiment_data(exp_id, eq_time)
        
        if len(data) == 0:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', fontsize=14)
            ax.set_title(f'{hardness} gpg - No Data')
            continue
        
        # Create interpolated grid
        try:
            AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
                data, n_points=400, method='griddata', gaussian_sigma=3.0
            )
        except Exception as e:
            print(f"  Warning: griddata failed for {polymer} {hardness}gpg: {e}")
            continue
        
        threshold = 75.0
        
        # Plot continuous map
        contourf_levels = np.linspace(35, 95, 21)
        cf = ax.contourf(AS_grid, PS_grid, trans_grid, levels=contourf_levels,
                        cmap='RdYlGn', alpha=0.8)
        ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                  colors='black', linewidths=2)
        ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                  c=data['transmission_pct'], s=15, cmap='RdYlGn',
                  edgecolors='black', linewidth=0.3, alpha=0.6, vmin=35, vmax=95)
        
        hardness_str = f'{hardness} gpg' if hardness > 0 else 'Soft Water'
        ax.set_title(f'{hardness_str}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Rhamnolipid (%)', fontweight='bold')
        ax.set_ylabel(f'{polymer} (%)', fontweight='bold')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3)
        
        # Set tick locations
        x_ticks = [0.15, 0.3, 0.5, 1.0, 2.0, 5.0]
        y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
        ax.xaxis.set_major_locator(FixedLocator(x_ticks))
        ax.yaxis.set_major_locator(FixedLocator(y_ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.2g}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
        
        plt.colorbar(cf, ax=ax, label='Transmission (%)')
    
    plt.tight_layout()
    return fig


def main():
    """Generate all phase diagram and kinetics plots for Rhamnolipid experiments."""
    print("=" * 70)
    print("GENERATING RHAMNOLIPID PHASE DIAGRAMS AND KINETICS PLOTS")
    print("=" * 70)
    
    polymers = ['AMT', 'DADMAC', 'Excel', 'JR30M', 'KG30M']
    hardness_levels = [0, 7]
    
    generated_files = []
    
    for polymer in polymers:
        print(f"\n{'='*50}")
        print(f"Processing {polymer}")
        print(f"{'='*50}")
        
        # Generate hardness comparison figure
        print(f"  Creating hardness comparison...")
        try:
            fig_compare = create_hardness_comparison_figure(polymer)
            compare_path = OUTPUT_DIR / f'{polymer}_hardness_comparison.png'
            fig_compare.savefig(compare_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig_compare)
            generated_files.append(compare_path)
            print(f"    Saved: {compare_path}")
        except Exception as e:
            print(f"    Error creating comparison: {e}")
        
        for hardness in hardness_levels:
            key = (polymer, hardness)
            if key not in PRIMARY_EXPERIMENTS:
                print(f"  Skipping {hardness}gpg - no data")
                continue
            
            exp_id = PRIMARY_EXPERIMENTS[key]
            hardness_str = f'{hardness}gpg'
            print(f"\n  {hardness_str}:")
            
            # Get equilibrium timepoint
            eq_time = get_equilibrium_timepoint(exp_id)
            print(f"    Equilibrium timepoint: {eq_time:.1f} min")
            
            # Load data at equilibrium
            data = load_experiment_data(exp_id, eq_time)
            print(f"    Data points at equilibrium: {len(data)}")
            
            if len(data) < 10:
                print(f"    WARNING: Insufficient data points, skipping")
                continue
            
            # Create phase diagram
            print(f"    Creating phase diagram...")
            try:
                fig_phase = create_phase_diagram_figure(data, polymer, hardness, eq_time)
                phase_path = OUTPUT_DIR / f'{polymer}_{hardness_str}_phase_diagram.png'
                fig_phase.savefig(phase_path, dpi=150, bbox_inches='tight', facecolor='white')
                plt.close(fig_phase)
                generated_files.append(phase_path)
                print(f"      Saved: {phase_path}")
            except Exception as e:
                print(f"      Error: {e}")
            
            # Create kinetics plot
            print(f"    Creating kinetics plot...")
            try:
                kinetic_data = load_kinetic_data(exp_id)
                fig_kinetic = create_kinetic_analysis_figure(kinetic_data, polymer, hardness)
                kinetic_path = OUTPUT_DIR / f'{polymer}_{hardness_str}_kinetics.png'
                fig_kinetic.savefig(kinetic_path, dpi=150, bbox_inches='tight', facecolor='white')
                plt.close(fig_kinetic)
                generated_files.append(kinetic_path)
                print(f"      Saved: {kinetic_path}")
            except Exception as e:
                print(f"      Error: {e}")
    
    print(f"\n{'='*70}")
    print(f"GENERATION COMPLETE")
    print(f"Total files generated: {len(generated_files)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*70}")
    
    return generated_files


if __name__ == '__main__':
    main()
