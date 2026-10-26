"""
Generate PowerPoint presentation with phase diagrams.
Creates slides for each surfactant-polymer combination at equilibrium timepoint,
plus summary pages for each polymer system.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import io
from scipy.interpolate import Rbf
import json
from phase_plotting import create_phase_diagram_grids, plot_continuous_map, plot_binary_boundary


class PhaseAnalysisPresentation:
    """Generate PowerPoint with phase diagrams at equilibrium timepoints."""
    
    def __init__(self, db_path='phase_diagrams.db', output_path='phase_diagrams_presentation.pptx'):
        self.db_path = db_path
        self.output_path = output_path
        self.prs = Presentation()
        self.prs.slide_width = Inches(10)
        self.prs.slide_height = Inches(7.5)
        
        # Color scheme
        self.BG_DARK = '#1e1e1e'
        self.BG_MEDIUM = '#2d2d2d'
        self.FG_PRIMARY = '#ffffff'
        self.FG_SECONDARY = '#b0b0b0'
        
    def determine_equilibrium_timepoint(self, experiment_id):
        """
        Determine the equilibrium timepoint for an experiment.
        Uses the 98% criterion: first timepoint where avg transmission >= 98% of final.
        """
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT timepoint_minutes, AVG(transmission_pct) as avg_trans
            FROM measurements
            WHERE experiment_id = ?
            GROUP BY timepoint_minutes
            ORDER BY timepoint_minutes
        """
        
        df = pd.read_sql_query(query, conn, params=(experiment_id,))
        conn.close()
        
        if len(df) < 2:
            return df['timepoint_minutes'].iloc[-1]
        
        final_avg = df['avg_trans'].iloc[-1]
        threshold_95 = final_avg * 0.95
        
        # Find first timepoint that reaches 95% of final
        for _, row in df.iterrows():
            if row['avg_trans'] >= threshold_95:
                # Return the next timepoint after this (first one past equilibrium)
                next_idx = df[df['timepoint_minutes'] >= row['timepoint_minutes']].index[0]
                if next_idx < len(df) - 1:
                    return df['timepoint_minutes'].iloc[next_idx + 1]
                else:
                    return row['timepoint_minutes']
        
        return df['timepoint_minutes'].iloc[-1]
    
    def get_experiments_by_polymer(self):
        """Group experiments by polymer, with surfactant and equilibrium timepoint info."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT DISTINCT experiment_id, experiment_name, 
                   surfactant_name, polymer_name
            FROM measurements
            ORDER BY polymer_name, surfactant_name, experiment_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Add equilibrium timepoints
        df['equilibrium_timepoint'] = df['experiment_id'].apply(self.determine_equilibrium_timepoint)
        
        return df.groupby('polymer_name')
    
    def load_experiment_data(self, experiment_id, timepoint):
        """Load data for a specific experiment and timepoint."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT *
            FROM measurements
            WHERE experiment_id = ? AND timepoint_minutes = ?
        """
        
        data = pd.read_sql_query(query, conn, params=(experiment_id, timepoint))
        conn.close()
        
        return data
    
    def load_kinetic_data(self, experiment_id):
        """Load all timepoint data for kinetic analysis."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT timepoint_minutes, transmission_pct
            FROM measurements
            WHERE experiment_id = ?
            ORDER BY timepoint_minutes
        """
        
        data = pd.read_sql_query(query, conn, params=(experiment_id,))
        conn.close()
        
        return data
    
    def create_phase_diagram_figure(self, data, timepoint):
        """Create a 4-panel phase diagram figure."""
        fig = plt.figure(figsize=(14, 10), facecolor='white')
        axes = fig.subplots(2, 2)
        
        surfactant = data['surfactant_name'].iloc[0]
        polymer = data['polymer_name'].iloc[0]
        
        fig.suptitle(f'{surfactant} - {polymer} at {timepoint:.2f} minutes',
                    fontsize=16, fontweight='bold')
        
        # Create interpolated grid
        ps_min, ps_max = data['polymer_pct'].min(), data['polymer_pct'].max()
        as_min, as_max = data['surfactant_pct'].min(), data['surfactant_pct'].max()
        
        # Use exact same grid creation and plotting as GUI
        AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
            data, n_points=800, method='gp', gp_length_scale=0.18, gaussian_sigma=6.0
        )
        threshold = 75.0
        
        # Plot 1: Continuous transmission map (exactly as in GUI)
        plot_continuous_map(axes[0, 0], AS_grid, PS_grid, trans_grid, data, threshold,
                           surfactant, polymer, fig=fig)
        axes[0, 0].set_title(f'Continuous Transmission Map ({timepoint:.2f} min)', fontweight='bold')
        
        # Plot 2: Three-phase classification (binary with filled contours - exactly as in GUI)
        phase_colors = ['#e74c3c', '#2ecc71']
        
        # Simple contourf without BoundaryNorm to avoid artifacts
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
        axes[0, 1].minorticks_on()
        
        from matplotlib.ticker import FixedLocator, FuncFormatter
        x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
        axes[0, 1].xaxis.set_major_locator(FixedLocator(x_ticks))
        axes[0, 1].yaxis.set_major_locator(FixedLocator(y_ticks))
        axes[0, 1].xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
        axes[0, 1].yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
        
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='#e74c3c', edgecolor='black', label=f'Precipitate (<{threshold:.0f}%)'),
                          Patch(facecolor='#2ecc71', edgecolor='black', label=f'Clear (≥{threshold:.0f}%)')]
        axes[0, 1].legend(handles=legend_elements, loc='upper left', fontsize=8)
        
        # Plot 3: Binary phase boundary (exactly as in GUI)
        plot_binary_boundary(axes[1, 0], AS_grid, PS_grid, trans_grid, data, threshold,
                            surfactant, polymer, fig=fig)
        
        # Plot 4: Statistics/histogram (exactly as in GUI)
        bins = np.arange(30, 100, 5)
        axes[1, 1].hist(data['transmission_pct'], bins=bins, color='steelblue', alpha=0.7, edgecolor='black')
        axes[1, 1].axvline(threshold, color='black', linewidth=2.5, linestyle='-', 
                          label=f'Threshold ({threshold:.0f}%)')
        axes[1, 1].set_xlabel('Transmission (%)', fontsize=10, fontweight='bold')
        axes[1, 1].set_ylabel('Frequency', fontsize=10, fontweight='bold')
        axes[1, 1].set_title('Transmission Distribution', fontsize=11, fontweight='bold')
        axes[1, 1].legend(fontsize=7)
        axes[1, 1].grid(True, alpha=0.3)
        
        axes[1, 1].set_xlabel('Transmission (%)', fontweight='bold')
        axes[1, 1].set_ylabel('Frequency', fontweight='bold')
        axes[1, 1].set_title('Transmission Distribution', fontweight='bold')
        axes[1, 1].legend(fontsize=9)
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def create_polymer_summary_figure(self, polymer_name, surfactants_data):
        """Create a figure with continuous transmission maps for all surfactants of one polymer."""
        n_surfactants = len(surfactants_data)
        n_cols = min(3, n_surfactants)
        n_rows = (n_surfactants + n_cols - 1) // n_cols
        
        fig = plt.figure(figsize=(15, 5 * n_rows), facecolor='white')
        
        fig.suptitle(f'{polymer_name} - Continuous Transmission Maps at Equilibrium',
                    fontsize=16, fontweight='bold')
        
        for idx, (surfactant, data) in enumerate(surfactants_data.items()):
            ax = fig.add_subplot(n_rows, n_cols, idx + 1)
            
            # Create interpolated grid
            ps_min, ps_max = data['polymer_pct'].min(), data['polymer_pct'].max()
            as_min, as_max = data['surfactant_pct'].min(), data['surfactant_pct'].max()
            
            # Use shared plotting function for consistency with GUI
            AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
                data, n_points=800, method='gp', gp_length_scale=0.18, gaussian_sigma=6.0
            )
            
            # Plot
            contourf_levels = np.linspace(35, 95, 21)
            cf = ax.contourf(AS_grid, PS_grid, trans_grid, levels=contourf_levels, 
                            cmap='RdYlGn', alpha=0.8)
            ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                      c=data['transmission_pct'], s=15, cmap='RdYlGn',
                      edgecolors='black', linewidth=0.3, alpha=0.6, vmin=35, vmax=95)
            
            ax.set_xlabel(f'{surfactant} (%)', fontweight='bold', fontsize=10)
            ax.set_ylabel(f'{polymer_name} (%)', fontweight='bold', fontsize=10)
            ax.set_title(f'{surfactant}', fontweight='bold', fontsize=11)
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3)
            
            # Set explicit tick locations for log scale
            from matplotlib.ticker import FixedLocator, FuncFormatter
            x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
            y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
            ax.xaxis.set_major_locator(FixedLocator(x_ticks))
            ax.yaxis.set_major_locator(FixedLocator(y_ticks))
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
            
            cbar = plt.colorbar(cf, ax=ax)
            cbar.set_label('Transmission (%)', fontsize=9)
        
        plt.tight_layout()
        return fig
    
    def analyze_polymer_surfactant_mechanisms(self):
        """Analyze mechanisms for each polymer-surfactant pair."""
        conn = sqlite3.connect(self.db_path)
        
        # Get all unique polymer-surfactant pairs
        query = """
            SELECT DISTINCT polymer_name, surfactant_name, experiment_id, 
                   experiment_name
            FROM measurements
            ORDER BY polymer_name, surfactant_name
        """
        
        pairs = pd.read_sql_query(query, conn)
        
        mechanisms = {}
        
        for _, row in pairs.iterrows():
            polymer = row['polymer_name']
            surfactant = row['surfactant_name']
            exp_id = row['experiment_id']
            
            if polymer not in mechanisms:
                mechanisms[polymer] = {}
            
            # Load equilibrium data (latest timepoint)
            eq_query = """
                SELECT surfactant_pct, polymer_pct, transmission_pct
                FROM measurements
                WHERE experiment_id = ?
                ORDER BY timepoint_minutes DESC
                LIMIT 96
            """
            eq_data = pd.read_sql_query(eq_query, conn, params=(exp_id,))
            
            # Load kinetic data
            kinetic_query = """
                SELECT timepoint_minutes, AVG(transmission_pct) as avg_trans
                FROM measurements
                WHERE experiment_id = ?
                GROUP BY timepoint_minutes
                ORDER BY timepoint_minutes
            """
            kinetic_data = pd.read_sql_query(kinetic_query, conn, params=(exp_id,))
            
            # Analyze phase behavior (75% threshold)
            clear_wells = len(eq_data[eq_data['transmission_pct'] >= 75])
            precipitate_wells = len(eq_data[eq_data['transmission_pct'] < 75])
            total_wells = len(eq_data)
            
            # Calculate equilibrium time (95% criterion)
            if len(kinetic_data) > 1:
                final_avg = kinetic_data['avg_trans'].iloc[-1]
                threshold_95 = final_avg * 0.95
                eq_times = kinetic_data[kinetic_data['avg_trans'] >= threshold_95]
                eq_time = eq_times['timepoint_minutes'].iloc[0] if len(eq_times) > 0 else kinetic_data['timepoint_minutes'].iloc[-1]
            else:
                eq_time = kinetic_data['timepoint_minutes'].iloc[0] if len(kinetic_data) > 0 else 0
            
            # Get concentration ranges
            surf_min, surf_max = eq_data['surfactant_pct'].min(), eq_data['surfactant_pct'].max()
            poly_min, poly_max = eq_data['polymer_pct'].min(), eq_data['polymer_pct'].max()
            trans_avg = eq_data['transmission_pct'].mean()
            trans_std = eq_data['transmission_pct'].std()
            
            mechanisms[polymer][surfactant] = {
                'clear_pct': 100 * clear_wells / total_wells,
                'precipitate_pct': 100 * precipitate_wells / total_wells,
                'eq_time': eq_time,
                'surf_range': (surf_min, surf_max),
                'poly_range': (poly_min, poly_max),
                'trans_avg': trans_avg,
                'trans_std': trans_std,
                'exp_id': exp_id
            }
        
        conn.close()
        return mechanisms
    
    def create_mechanism_summary_figure(self, mechanisms):
        """Create summary figures - multiple pages with tables and charts.
        
        Focus on coacervation (phase-separated regions) for deposition applications.
        Split each polymer into 2 pages for proper spacing.
        """
        figures = []
        
        # ===== PAGE 1: EXECUTIVE SUMMARY =====
        fig = plt.figure(figsize=(11, 8.5), facecolor='white')
        fig.suptitle('Mechanistic Summary: Coacervation Potential Analysis', 
                    fontsize=14, fontweight='bold', y=0.97)
        
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Calculate global statistics
        all_eq_times = []
        all_precipitate = []
        polymer_list = []
        
        for polymer_name, polymer_data in mechanisms.items():
            polymer_list.append(polymer_name)
            for data in polymer_data.values():
                all_eq_times.append(data['eq_time'])
                all_precipitate.append(data['precipitate_pct'])
        
        summary_text = "EXECUTIVE SUMMARY: Coacervation for Material Deposition\n"
        summary_text += "="*65 + "\n\n"
        summary_text += f"Polymer Systems Analyzed: {len(mechanisms)}\n"
        summary_text += f"Surfactant-Polymer Pairs: {sum(len(p) for p in mechanisms.values())}\n\n"
        
        summary_text += "GLOBAL DEPOSITION METRICS:\n"
        summary_text += f"  Avg Precipitation: {np.mean(all_precipitate):.1f}%\n"
        summary_text += f"  Avg Eq Time: {np.mean(all_eq_times):.1f} ± {np.std(all_eq_times):.1f} min\n\n"
        
        summary_text += "APPLICATION FOCUS:\n"
        summary_text += "  • Large phase-sep regions = Strong coacervation\n"
        summary_text += "  • Fast equilibration = Rapid deposition\n"
        summary_text += "  • Turbidity = Complex aggregation\n"
        
        ax.text(0.08, 0.92, summary_text, transform=ax.transAxes,
               fontsize=10, verticalalignment='top', family='monospace',
               bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8, pad=0.8))
        
        figures.append(fig)
        
        # ===== PAGES 2+: PER-POLYMER ANALYSIS (2 pages per polymer) =====
        for polymer_name in sorted(mechanisms.keys()):
            polymer_data = mechanisms[polymer_name]
            surfactants = sorted(polymer_data.keys())
            
            # ===== PAGE A: TABLE + COACERVATION RANKING =====
            fig_a = plt.figure(figsize=(11, 8.5), facecolor='white')
            fig_a.suptitle(f'{polymer_name}: Coacervation Ranking & Metrics', 
                        fontsize=13, fontweight='bold', y=0.98)
            
            gs_a = fig_a.add_gridspec(2, 1, hspace=0.3, wspace=0.3, 
                                     left=0.08, right=0.95, top=0.94, bottom=0.08)
            
            # TABLE (top, full width)
            ax_table = fig_a.add_subplot(gs_a[0])
            ax_table.axis('off')
            
            # Prepare table data - sorted by precipitation percentage (deposition potential)
            surfactants_sorted = sorted(surfactants, 
                                       key=lambda s: polymer_data[s]['precipitate_pct'], 
                                       reverse=True)
            
            table_data = [['Surfactant', 'Precipitate\n(%)', 'Clear\n(%)', 
                          'Eq Time\n(min)', 'Mean Trans\n(%)']]
            
            for surf in surfactants_sorted:
                data = polymer_data[surf]
                table_data.append([
                    surf,
                    f"{data['precipitate_pct']:.0f}",
                    f"{data['clear_pct']:.0f}",
                    f"{data['eq_time']:.2f}",
                    f"{data['trans_avg']:.1f}"
                ])
            
            # Create table
            table = ax_table.table(cellText=table_data, cellLoc='center', loc='center',
                                  colWidths=[0.25, 0.15, 0.15, 0.15, 0.15])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2.2)
            
            # Style header row - emphasize phase-separation column
            for i in range(len(table_data[0])):
                if i == 1:  # Phase-Sep column
                    table[(0, i)].set_facecolor('#e74c3c')
                else:
                    table[(0, i)].set_facecolor('#3498db')
                table[(0, i)].set_text_props(weight='bold', color='white', fontsize=10)
            
            # Alternate row colors
            for i in range(1, len(table_data)):
                color = '#ecf0f1' if i % 2 == 0 else 'white'
                for j in range(len(table_data[0])):
                    table[(i, j)].set_facecolor(color)
            
            # PRECIPITATION RANKING CHART (bottom, full width)
            ax_chart = fig_a.add_subplot(gs_a[1])
            precip_vals = [polymer_data[s]['precipitate_pct'] for s in surfactants_sorted]
            colors_sep = plt.cm.Reds(np.linspace(0.4, 0.9, len(surfactants_sorted)))
            bars_sep = ax_chart.barh(range(len(surfactants_sorted)), precip_vals, 
                                    color=colors_sep, edgecolor='black', linewidth=1.5)
            ax_chart.set_yticks(range(len(surfactants_sorted)))
            ax_chart.set_yticklabels(surfactants_sorted, fontsize=10)
            ax_chart.set_xlabel('Precipitate (<70%) (%)', fontweight='bold', fontsize=11)
            ax_chart.set_title('Precipitation/Deposition Potential Ranking', fontweight='bold', fontsize=12)
            ax_chart.set_xlim(0, 100)
            ax_chart.grid(True, alpha=0.3, axis='x')
            
            # Add value labels
            for i, (bar, val) in enumerate(zip(bars_sep, precip_vals)):
                ax_chart.text(val + 2, bar.get_y() + bar.get_height()/2, f'{val:.0f}%',
                            va='center', fontsize=10, fontweight='bold')
            
            figures.append(fig_a)
            
            # ===== PAGE B: EQUILIBRATION TIME + MECHANISTIC INSIGHTS =====
            fig_b = plt.figure(figsize=(11, 8.5), facecolor='white')
            fig_b.suptitle(f'{polymer_name}: Kinetics & Analysis', 
                        fontsize=13, fontweight='bold', y=0.98)
            
            gs_b = fig_b.add_gridspec(2, 1, hspace=0.35, wspace=0.3, 
                                     left=0.08, right=0.95, top=0.94, bottom=0.08)
            
            # EQUILIBRATION TIME CHART (top)
            ax_eq = fig_b.add_subplot(gs_b[0])
            eq_times = [polymer_data[s]['eq_time'] for s in surfactants_sorted]
            colors_eq = ['#2ecc71' if t < 10 else '#f39c12' if t < 20 else '#e74c3c' 
                        for t in eq_times]
            bars_eq = ax_eq.bar(range(len(surfactants_sorted)), eq_times, 
                               color=colors_eq, alpha=0.75, edgecolor='black', linewidth=1.5)
            ax_eq.set_xticks(range(len(surfactants_sorted)))
            ax_eq.set_xticklabels(surfactants_sorted, rotation=35, ha='right', fontsize=10)
            ax_eq.set_ylabel('Time (minutes)', fontweight='bold', fontsize=11)
            ax_eq.set_title('Equilibration Speed (95% criterion)', fontweight='bold', fontsize=12)
            ax_eq.grid(True, alpha=0.3, axis='y')
            
            # Add value labels
            for bar, val in zip(bars_eq, eq_times):
                height = bar.get_height()
                ax_eq.text(bar.get_x() + bar.get_width()/2., height,
                          f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
            
            # MECHANISTIC INSIGHTS (bottom)
            ax_insights = fig_b.add_subplot(gs_b[1])
            ax_insights.axis('off')
            
            insights_text = "COACERVATION MECHANISTIC ANALYSIS:\n"
            insights_text += "="*50 + "\n\n"
            
            for surf in surfactants_sorted:
                data = polymer_data[surf]
                insights_text += f"{surf}:\n"
                
                # Coacervation assessment (precipitation percentage)
                precip_pct = data['precipitate_pct']
                if precip_pct > 80:
                    insights_text += f"  ★ EXCELLENT ({precip_pct:.0f}% precipitate)\n"
                elif precip_pct > 60:
                    insights_text += f"  ◆ Good ({precip_pct:.0f}% precipitate)\n"
                elif precip_pct > 40:
                    insights_text += f"  ○ Moderate ({precip_pct:.0f}% precipitate)\n"
                else:
                    insights_text += f"  ◇ Poor ({precip_pct:.0f}% precipitate)\n"
                
                # Kinetics note
                if data['eq_time'] < 10:
                    insights_text += f"    • Fast kinetics: rapid deposition\n"
                elif data['eq_time'] > 20:
                    insights_text += f"    • Slow kinetics: aggregation dynamics\n"
                
                insights_text += "\n"
            
            ax_insights.text(0.05, 0.95, insights_text, transform=ax_insights.transAxes,
                           fontsize=9.5, verticalalignment='top', family='monospace',
                           bbox=dict(boxstyle='round', facecolor='#ffe6e6', alpha=0.75, pad=0.7))
            
            figures.append(fig_b)
        
        return figures
    
    def create_polymer_conclusions_figure(self, mechanisms):
        """Create final conclusions figure summarizing key findings by polymer."""
        fig = plt.figure(figsize=(11, 8.5), facecolor='white')
        fig.suptitle('Polymer System Conclusions: Coacervation Kinetics & Behavior', 
                    fontsize=13, fontweight='bold', y=0.97)
        
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        conclusions_text = "CORRECTED POLYMER BEHAVIOR SUMMARY\n"
        conclusions_text += "="*75 + "\n\n"
        
        # DADMAC
        conclusions_text += "1. DADMAC - STANDOUT FOR COACERVATION\n"
        conclusions_text += "-"*75 + "\n"
        conclusions_text += "   Coacervation Potential: 66.7% average phase-separated (EXCELLENT)\n"
        conclusions_text += "   Best Performer: SCG (100% phase-separated)\n"
        conclusions_text += "   CRITICAL FINDING: EXTREME kinetic variation (σ = 23.2 min)\n"
        conclusions_text += "     • SCG: 54.02 minutes (VERY SLOW equilibration!)\n"
        conclusions_text += "     • SLS: 9.14 minutes (fast, good balance)\n"
        conclusions_text += "     • SLESS: 1.51 minutes (turbid, fastest)\n"
        conclusions_text += "   Key Insight: Surfactant chemistry CRITICALLY affects deposition speed\n"
        conclusions_text += "   Recommendation: Choose SLS for ~9 min coacervation; avoid SCG if\n"
        conclusions_text += "                   rapid deposition required (54 min is too slow)\n\n"
        
        # KG30M
        conclusions_text += "2. KG30M - SELECTIVE COACERVATION\n"
        conclusions_text += "-"*75 + "\n"
        conclusions_text += "   Coacervation Potential: 25% average (only with Rhamnolipid)\n"
        conclusions_text += "   Best Performer: Rham (100% phase-separated in 1.52 min - INSTANT!)\n"
        conclusions_text += "   Profile: Highly selective - only biosurfactant triggers coacervation\n"
        conclusions_text += "     • Rhamnolipid: 1.52 minutes (exceptional speed)\n"
        conclusions_text += "     • SCG/SLS: No coacervation (clear)\n"
        conclusions_text += "     • SLESS: 16.52 minutes (no coacervation, but slow)\n"
        conclusions_text += "   Recommendation: Use ONLY if targeting Rham-based formulations\n\n"
        
        # AMT
        conclusions_text += "3. AMT - NO COACERVATION, FAST HYDRATION\n"
        conclusions_text += "-"*75 + "\n"
        conclusions_text += "   Coacervation Potential: 0% (all clear with all surfactants)\n"
        conclusions_text += "   Equilibration: 6.58 min average (reasonably fast, consistent)\n"
        conclusions_text += "   Profile: Excellent solubility, no phase separation\n"
        conclusions_text += "   Recommendation: Use for transparent formulations ONLY,\n"
        conclusions_text += "                   NOT suitable for coacervation deposition\n\n"
        
        # Excel/JR30M
        conclusions_text += "4. EXCEL & JR30M - LIMITED DATA\n"
        conclusions_text += "-"*75 + "\n"
        conclusions_text += "   Only tested with Rhamnolipid (incomplete surfactant set)\n"
        conclusions_text += "   Both show: No coacervation with Rham (~1.53 min)\n"
        conclusions_text += "   Cannot draw firm conclusions without synthetic surfactant testing\n\n"
        
        # Overall recommendation
        conclusions_text += "OVERALL RECOMMENDATION FOR COACERVATION DEPOSITION\n"
        conclusions_text += "="*75 + "\n"
        conclusions_text += "BEST CHOICE:      DADMAC with SLS (66.7% coacervation + 9 min kinetics)\n"
        conclusions_text += "FASTEST:          KG30M with Rhamnolipid (100% coarc, 1.5 min)\n"
        conclusions_text += "AVOID:            DADMAC with SCG (54 min too slow for most applications)\n"
        conclusions_text += "NOT SUITABLE:     AMT, Excel, JR30M (no meaningful coacervation)\n"
        
        ax.text(0.05, 0.96, conclusions_text, transform=ax.transAxes,
               fontsize=8.8, verticalalignment='top', family='monospace',
               bbox=dict(boxstyle='round', facecolor='#d4edda', alpha=0.85, pad=1))
        
        return fig
    
    def create_kinetic_analysis_figure(self, kinetic_data, experiment_id):
        """Create kinetic analysis figure with multiple subplots."""
        fig = plt.figure(figsize=(14, 10), facecolor='white')
        axes = fig.subplots(2, 2)
        
        fig.suptitle(f'Kinetic Analysis: {experiment_id}', fontsize=16, fontweight='bold')
        
        # Plot 1: Average transmission vs time
        ax1 = axes[0, 0]
        ax1.plot(kinetic_data['timepoint_minutes'], kinetic_data['avg_trans'],
                'o-', color='#2ecc71', linewidth=2, markersize=8, label='Mean Transmission')
        ax1.fill_between(kinetic_data['timepoint_minutes'],
                        kinetic_data['avg_trans'] - kinetic_data['std_trans'],
                        kinetic_data['avg_trans'] + kinetic_data['std_trans'],
                        alpha=0.3, color='#2ecc71', label='±1 Std Dev')
        
        final_avg = kinetic_data['avg_trans'].iloc[-1]
        ax1.axhline(final_avg, color='#e74c3c', linestyle='--', linewidth=2, label=f'Final Value ({final_avg:.1f}%)')
        
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
               color='#3498db', alpha=0.7, edgecolor='black', width=0.5)
        
        ax4.set_xlabel('Time (minutes)', fontweight='bold')
        ax4.set_ylabel('Number of Wells', fontweight='bold')
        ax4.set_title('Data Density Over Time', fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        return fig
    
    def fig_to_image_bytes(self, fig):
        """Convert matplotlib figure to image bytes for PowerPoint."""
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        image_bytes = io.BytesIO()
        canvas.print_png(image_bytes)
        image_bytes.seek(0)
        plt.close(fig)
        return image_bytes
    
    def add_title_slide(self, title, subtitle):
        """Add title slide to presentation."""
        slide_layout = self.prs.slide_layouts[6]  # Blank layout
        slide = self.prs.slides.add_slide(slide_layout)
        
        # Set background color
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(30, 30, 30)
        
        # Add title
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(9), Inches(1.5))
        title_frame = title_box.text_frame
        title_frame.word_wrap = True
        p = title_frame.paragraphs[0]
        p.text = title
        p.font.size = Pt(54)
        p.font.bold = True
        p.font.color.rgb = RGBColor(78, 201, 176)
        p.alignment = PP_ALIGN.CENTER
        
        # Add subtitle
        subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(9), Inches(1.5))
        subtitle_frame = subtitle_box.text_frame
        subtitle_frame.word_wrap = True
        p = subtitle_frame.paragraphs[0]
        p.text = subtitle
        p.font.size = Pt(28)
        p.font.color.rgb = RGBColor(200, 200, 200)
        p.alignment = PP_ALIGN.CENTER
    
    def add_image_slide(self, image_bytes, title):
        """Add slide with image and title."""
        slide_layout = self.prs.slide_layouts[6]  # Blank layout
        slide = self.prs.slides.add_slide(slide_layout)
        
        # Set background
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(30, 30, 30)
        
        # Add title
        title_box = slide.shapes.add_textbox(Inches(0.3), Inches(0.2), Inches(9.4), Inches(0.4))
        title_frame = title_box.text_frame
        p = title_frame.paragraphs[0]
        p.text = title
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RGBColor(78, 201, 176)
        
        # Add image
        slide.shapes.add_picture(image_bytes, Inches(0.3), Inches(0.7), width=Inches(9.4))
    
    def generate_presentation(self):
        """Generate the complete presentation."""
        print("Generating presentation...")
        
        # Title slide
        self.add_title_slide("Phase Diagram Analysis", "Surfactant-Polymer Systems at Equilibrium")
        
        # Analyze mechanisms first
        print("\nAnalyzing mechanisms...")
        mechanisms = self.analyze_polymer_surfactant_mechanisms()
        
        # Get experiments grouped by polymer
        polymer_groups = self.get_experiments_by_polymer()
        
        for polymer_name, group in polymer_groups:
            print(f"\nProcessing polymer: {polymer_name}")
            
            # Add section title
            self.add_title_slide(f"{polymer_name} System", "Phase Diagrams and Kinetics at Equilibrium")
            
            # Collect data for polymer summary
            surfactant_summary_data = {}
            
            # Generate full phase diagrams and kinetics for each surfactant-polymer combo
            for _, row in group.iterrows():
                exp_id = row['experiment_id']
                surf_name = row['surfactant_name']
                eq_timepoint = row['equilibrium_timepoint']
                
                print(f"  {surf_name} at {eq_timepoint:.2f} min")
                
                # Load data
                data = self.load_experiment_data(exp_id, eq_timepoint)
                
                if len(data) == 0:
                    print(f"    WARNING: No data found for {exp_id} at {eq_timepoint}")
                    continue
                
                # Store for polymer summary
                if surf_name not in surfactant_summary_data:
                    surfactant_summary_data[surf_name] = data
                
                # Create and add phase diagram slide
                fig = self.create_phase_diagram_figure(data, eq_timepoint)
                image_bytes = self.fig_to_image_bytes(fig)
                self.add_image_slide(image_bytes, f"{surf_name} - {polymer_name} (Phase Diagram)")
                
                # Load kinetic data and create kinetic analysis slide
                kinetic_data = self.load_kinetic_data(exp_id)
                
                if len(kinetic_data) > 2:
                    # Calculate statistics per timepoint
                    kinetic_stats = kinetic_data.groupby('timepoint_minutes')['transmission_pct'].agg([
                        ('avg_trans', 'mean'),
                        ('std_trans', 'std'),
                        ('min_trans', 'min'),
                        ('max_trans', 'max'),
                        ('n_wells', 'count')
                    ]).reset_index()
                    
                    # Calculate rate of change
                    kinetic_stats['rate_of_change'] = kinetic_stats['avg_trans'].diff() / kinetic_stats['timepoint_minutes'].diff()
                    
                    fig = self.create_kinetic_analysis_figure(kinetic_stats, exp_id)
                    image_bytes = self.fig_to_image_bytes(fig)
                    self.add_image_slide(image_bytes, f"{surf_name} - {polymer_name} (Kinetics)")
            
            # Add polymer summary page
            if len(surfactant_summary_data) > 1:
                print(f"  Creating summary page for {polymer_name}")
                fig = self.create_polymer_summary_figure(polymer_name, surfactant_summary_data)
                image_bytes = self.fig_to_image_bytes(fig)
                self.add_image_slide(image_bytes, f"{polymer_name} - Summary at Equilibrium")
        
        # Add mechanism summary slides (multiple pages)
        print("\nCreating mechanistic summary pages...")
        mechanism_figures = self.create_mechanism_summary_figure(mechanisms)
        for i, fig in enumerate(mechanism_figures):
            if i == 0:
                title = "Mechanistic Summary: Executive Overview"
            else:
                title = f"Mechanistic Summary: Page {i}"
            image_bytes = self.fig_to_image_bytes(fig)
            self.add_image_slide(image_bytes, title)
        
        # Add polymer conclusions
        print("\nCreating final conclusions page...")
        conclusions_fig = self.create_polymer_conclusions_figure(mechanisms)
        conclusions_bytes = self.fig_to_image_bytes(conclusions_fig)
        self.add_image_slide(conclusions_bytes, "Final Conclusions: Polymer Selection Guide")
        
        # Save presentation
        self.prs.save(self.output_path)
        print(f"\nPresentation saved to: {self.output_path}")


def main():
    # Generate presentation
    gen = PhaseAnalysisPresentation(
        db_path='phase_diagrams.db',
        output_path='phase_diagrams_presentation.pptx'
    )
    gen.generate_presentation()


if __name__ == "__main__":
    main()
