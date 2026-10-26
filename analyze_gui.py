"""
GUI for Phase Diagram Analysis
Dark-themed interface for visualizing phase diagrams from the database.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
from scipy.interpolate import Rbf
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
from phase_plotting import create_phase_diagram_grids
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches


class PhaseAnalysisGUI:
    # Dark theme color palette
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    BG_LIGHT = '#3e3e3e'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    ACCENT_BLUE = '#0e639c'
    ACCENT_GREEN = '#4ec9b0'
    ACCENT_ORANGE = '#ce9178'
    ACCENT_RED = '#f48771'
    
    def __init__(self, root):
        self.root = root
        self.root.title("Phase Diagram Analysis Tool")
        self.root.state('zoomed')
        self.root.minsize(1200, 800)
        self.root.configure(bg=self.BG_DARK)
        
        # Variables
        self.db_path = tk.StringVar(value="phase_diagrams.db")
        self.selected_experiment = tk.StringVar()
        self.selected_timepoint = tk.StringVar()
        self.phase_threshold = tk.DoubleVar(value=75.0)
        self.experiments = []
        self.timepoints = []
        self.current_data = None
        
        # Hover context tracking for multiple plots
        self.hover_contexts = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Create the main UI components."""
        
        # Title
        title_frame = tk.Frame(self.root, bg=self.BG_DARK)
        title_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title = tk.Label(
            title_frame,
            text="Phase Diagram Analysis",
            font=('Segoe UI', 18, 'bold'),
            bg=self.BG_DARK,
            fg=self.ACCENT_GREEN
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            title_frame,
            text="Visualize and analyze surfactant-polymer phase diagrams",
            font=('Segoe UI', 10),
            bg=self.BG_DARK,
            fg=self.FG_SECONDARY
        )
        subtitle.pack(anchor=tk.W)
        
        # Main container
        main_container = tk.Frame(self.root, bg=self.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left panel (controls)
        left_panel = tk.Frame(main_container, bg=self.BG_DARK, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.create_control_panel(left_panel)
        
        # Right panel (visualization)
        right_panel = tk.Frame(main_container, bg=self.BG_MEDIUM)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_visualization_panel(right_panel)
        
    def create_control_panel(self, parent):
        """Create the control panel with experiment selection."""
        
        # Database section
        db_frame = tk.LabelFrame(
            parent,
            text="  Database  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT
        )
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        inner = tk.Frame(db_frame, bg=self.BG_MEDIUM)
        inner.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            inner,
            text="Database:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY
        ).pack(anchor=tk.W)
        
        db_entry = tk.Entry(
            inner,
            textvariable=self.db_path,
            font=('Segoe UI', 9),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT
        )
        db_entry.pack(fill=tk.X, pady=(5, 5))
        
        tk.Button(
            inner,
            text="Load Database",
            font=('Segoe UI', 10, 'bold'),
            bg=self.ACCENT_BLUE,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.load_database
        ).pack(fill=tk.X)
        
        # Experiment selection
        exp_frame = tk.LabelFrame(
            parent,
            text="  Experiment Selection  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT
        )
        exp_frame.pack(fill=tk.X, pady=(0, 10))
        
        exp_inner = tk.Frame(exp_frame, bg=self.BG_MEDIUM)
        exp_inner.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            exp_inner,
            text="Experiment:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY
        ).pack(anchor=tk.W)
        
        self.exp_listbox = tk.Listbox(
            exp_inner,
            font=('Segoe UI', 9),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            selectbackground=self.ACCENT_BLUE,
            relief=tk.FLAT,
            height=6
        )
        self.exp_listbox.pack(fill=tk.X, pady=(5, 10))
        self.exp_listbox.bind('<<ListboxSelect>>', self.on_experiment_select)
        
        tk.Label(
            exp_inner,
            text="Timepoint:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY
        ).pack(anchor=tk.W)
        
        self.time_listbox = tk.Listbox(
            exp_inner,
            font=('Segoe UI', 9),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            selectbackground=self.ACCENT_GREEN,
            relief=tk.FLAT,
            height=8
        )
        self.time_listbox.pack(fill=tk.X, pady=(5, 0))
        
        # Parameters section
        param_frame = tk.LabelFrame(
            parent,
            text="  Visualization Parameters  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT
        )
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        param_inner = tk.Frame(param_frame, bg=self.BG_MEDIUM)
        param_inner.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            param_inner,
            text="Phase Threshold (%):",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY
        ).pack(anchor=tk.W)
        
        threshold_frame = tk.Frame(param_inner, bg=self.BG_MEDIUM)
        threshold_frame.pack(fill=tk.X, pady=(5, 10))
        
        tk.Entry(
            threshold_frame,
            textvariable=self.phase_threshold,
            font=('Segoe UI', 9),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            width=10
        ).pack(side=tk.LEFT)
        
        tk.Label(
            threshold_frame,
            text="(Recommended: 75)",
            font=('Segoe UI', 8, 'italic'),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Action buttons
        tk.Button(
            param_inner,
            text="Generate Phase Diagram",
            font=('Segoe UI', 10, 'bold'),
            bg=self.ACCENT_GREEN,
            fg=self.BG_DARK,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.generate_phase_diagram
        ).pack(fill=tk.X, pady=(0, 5))
        
        tk.Button(
            param_inner,
            text="Kinetic Analysis",
            font=('Segoe UI', 10, 'bold'),
            bg=self.ACCENT_BLUE,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.kinetic_analysis
        ).pack(fill=tk.X, pady=(0, 5))
        
        tk.Button(
            param_inner,
            text="Save Figure",
            font=('Segoe UI', 9),
            bg=self.ACCENT_ORANGE,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.save_figure
        ).pack(fill=tk.X, pady=(0, 5))
        
        tk.Button(
            param_inner,
            text="Export Experiments",
            font=('Segoe UI', 9),
            bg=self.ACCENT_BLUE,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.export_experiments
        ).pack(fill=tk.X)
        
    def create_visualization_panel(self, parent):
        """Create the matplotlib visualization panel."""
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 10), facecolor=self.BG_MEDIUM)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add toolbar
        toolbar_frame = tk.Frame(parent, bg=self.BG_MEDIUM)
        toolbar_frame.pack(fill=tk.X)
        
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.config(background=self.BG_MEDIUM)
        toolbar._message_label.config(background=self.BG_MEDIUM, foreground=self.FG_PRIMARY)
        toolbar.update()
        
    def load_database(self):
        """Load experiments from the database."""
        db_path = self.db_path.get()
        
        if not Path(db_path).exists():
            messagebox.showerror("Error", f"Database not found:\n{db_path}")
            return
        
        try:
            conn = sqlite3.connect(db_path)
            
            # Get unique experiments
            query = """
                SELECT DISTINCT experiment_id, experiment_name, 
                       surfactant_name, polymer_name,
                       COUNT(*) as records
                FROM measurements
                GROUP BY experiment_id, experiment_name, surfactant_name, polymer_name
                ORDER BY experiment_id
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self.experiments = df.to_dict('records')
            
            # Update listbox
            self.exp_listbox.delete(0, tk.END)
            for exp in self.experiments:
                display_text = f"{exp['experiment_id']}: {exp['surfactant_name']}-{exp['polymer_name']} ({exp['records']} records)"
                self.exp_listbox.insert(tk.END, display_text)
            
            messagebox.showinfo("Success", f"Loaded {len(self.experiments)} experiment(s)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load database:\n{str(e)}")
    
    def on_hover(self, event):
        """Handle mouse hover over scatter points in all plots."""
        # Hide all annotations first
        for context in self.hover_contexts.values():
            context['annot'].set_visible(False)
        
        # Check which plot the cursor is over
        for ax, context in self.hover_contexts.items():
            if event.inaxes != ax:
                continue
            
            # Check if cursor is over any scatter point
            cont, ind = context['scatter'].contains(event)
            
            if cont:
                # Get the index of the nearest point
                point_idx = ind['ind'][0]
                row = context['data'].iloc[point_idx]
                
                # Create tooltip text
                tooltip_text = (
                    f"Plate: {int(row['plate'])}\n"
                    f"Well: {row['well']}\n"
                    f"{row['surfactant_name']}: {row['surfactant_pct']:.4f}%\n"
                    f"{row['polymer_name']}: {row['polymer_pct']:.4f}%\n"
                    f"Transmission: {row['transmission_pct']:.2f}%"
                )
                
                context['annot'].xy = (event.xdata, event.ydata)
                context['annot'].set_text(tooltip_text)
                context['annot'].set_visible(True)
                break
        
        self.canvas.draw_idle()
            
    def on_experiment_select(self, event):
        """Handle experiment selection."""
        selection = self.exp_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        exp = self.experiments[idx]
        self.selected_experiment.set(exp['experiment_id'])
        
        # Load timepoints for this experiment
        try:
            conn = sqlite3.connect(self.db_path.get())
            query = """
                SELECT DISTINCT timepoint_minutes, COUNT(*) as wells
                FROM measurements
                WHERE experiment_id = ?
                GROUP BY timepoint_minutes
                ORDER BY timepoint_minutes
            """
            
            df = pd.read_sql_query(query, conn, params=(exp['experiment_id'],))
            conn.close()
            
            self.timepoints = df['timepoint_minutes'].tolist()
            
            # Update timepoint listbox
            self.time_listbox.delete(0, tk.END)
            for tp in self.timepoints:
                wells = df[df['timepoint_minutes'] == tp]['wells'].values[0]
                self.time_listbox.insert(tk.END, f"{tp:.2f} min ({wells} wells)")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load timepoints:\n{str(e)}")
            
    def generate_phase_diagram(self):
        """Generate the phase diagram for selected experiment and timepoint."""
        if not self.selected_experiment.get():
            messagebox.showwarning("Warning", "Please select an experiment first")
            return
        
        selection = self.time_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a timepoint")
            return
        
        timepoint = self.timepoints[selection[0]]
        
        try:
            # Load data from database
            conn = sqlite3.connect(self.db_path.get())
            query = """
                SELECT *
                FROM measurements
                WHERE experiment_id = ? AND timepoint_minutes = ?
            """
            
            data = pd.read_sql_query(query, conn, params=(self.selected_experiment.get(), timepoint))
            conn.close()
            
            if len(data) == 0:
                messagebox.showerror("Error", "No data found for selected timepoint")
                return
            
            # Diagnostic: Check for duplicate compositions
            print(f"\nPhase Diagram Data Diagnostic:")
            print(f"  Total wells: {len(data)}")
            print(f"  Plate 1: {len(data[data['plate']==1])} wells")
            print(f"  Plate 2: {len(data[data['plate']==2])} wells")
            print(f"  Unique compositions: {data[['surfactant_pct', 'polymer_pct']].drop_duplicates().shape[0]}")
            
            # Check if any wells have identical compositions (shouldn't happen)
            duplicates = data.groupby(['surfactant_pct', 'polymer_pct']).size()
            duplicates = duplicates[duplicates > 1]
            if len(duplicates) > 0:
                print(f"  WARNING: {len(duplicates)} compositions have multiple wells:")
                for (surf, poly), count in list(duplicates.items())[:5]:
                    print(f"    {surf:.4f}% surf, {poly:.4f}% poly: {count} wells")
            
            self.current_data = data
            
            # Generate the phase diagram
            self.create_alternative_phase_diagram(data, timepoint)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate phase diagram:\n{str(e)}")
            import traceback
            traceback.print_exc()
            
    def create_alternative_phase_diagram(self, data, timepoint):
        """Create enhanced phase diagram with multiple visualization techniques."""
        
        self.fig.clear()
        
        # Clear hover contexts for fresh start
        self.hover_contexts = {}
        
        # Create 2x2 subplot layout
        axes = self.fig.subplots(2, 2)
        
        surfactant = data['surfactant_name'].iloc[0]
        polymer = data['polymer_name'].iloc[0]
        exp_name = data['experiment_name'].iloc[0]
        
        self.fig.suptitle(f'Phase Diagram: {exp_name}\n{surfactant}-{polymer} at {timepoint:.2f} minutes',
                         fontsize=14, fontweight='bold', color=self.FG_PRIMARY)
        self.fig.patch.set_facecolor(self.BG_MEDIUM)
        
        # Create interpolated grid
        ps_min, ps_max = data['polymer_pct'].min(), data['polymer_pct'].max()
        as_min, as_max = data['surfactant_pct'].min(), data['surfactant_pct'].max()
        
        # Use shared grid creation for consistency
        # Using Gaussian Process for probabilistic boundary detection with noise handling
        # gp_length_scale in log10 space: smaller = more wiggly, larger = smoother
        # gaussian_sigma removes small isolated "islands" from noisy data points
        AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
            data, n_points=800, method='gp', gp_length_scale=0.18, gaussian_sigma=6.0
        )
        
        threshold = self.phase_threshold.get()
        
        # Use a single contour level equal to the selected threshold
        contour_levels = [threshold]
        
        # Plot 1: Continuous transmission map
        self.plot_continuous_map(axes[0, 0], AS_grid, PS_grid, trans_grid, data, contour_levels, surfactant, polymer)
        
        # Plot 2: Three-phase classification
        self.plot_three_phase(axes[0, 1], AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer)
        
        # Plot 3: Binary phase boundary
        self.plot_binary_boundary(axes[1, 0], AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer)
        
        # Plot 4: Statistics
        self.plot_statistics(axes[1, 1], data, threshold)
        
        for ax in axes.flat:
            ax.set_facecolor(self.BG_DARK)
            ax.tick_params(colors=self.FG_PRIMARY)
            ax.spines['bottom'].set_color(self.FG_SECONDARY)
            ax.spines['top'].set_color(self.FG_SECONDARY)
            ax.spines['left'].set_color(self.FG_SECONDARY)
            ax.spines['right'].set_color(self.FG_SECONDARY)
        
        self.fig.tight_layout()
        
        # Connect hover event after all plots are created
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)
        
        self.canvas.draw()
        
    def plot_continuous_map(self, ax, AS_grid, PS_grid, trans_grid, data, levels, surf, poly):
        """Plot continuous transmission map with contour lines."""
        # Use explicit levels from 0-100 for consistent scaling across all plots
        contourf_levels = np.linspace(0, 100, 21)
        contourf = ax.contourf(AS_grid, PS_grid, trans_grid, levels=contourf_levels, cmap='RdYlGn', alpha=0.8)
        
        contour_lines = ax.contour(AS_grid, PS_grid, trans_grid, levels=levels,
                       colors='black', linewidths=1.5, linestyles='-')
        ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%d%%')
        
        scatter = ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                           c=data['transmission_pct'], s=15, cmap='RdYlGn',
                           edgecolors='black', linewidth=0.3, alpha=0.6, vmin=0, vmax=100)
        
        ax.set_xlabel(f'{surf} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_ylabel(f'{poly} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_title('Continuous Transmission Map', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Set explicit tick locations for better visibility
        from matplotlib.ticker import FixedLocator, FuncFormatter
        surf_range = data['surfactant_pct']
        poly_range = data['polymer_pct']
        
        # Create tick values spanning the data range
        x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
        
        ax.xaxis.set_major_locator(FixedLocator(x_ticks))
        ax.yaxis.set_major_locator(FixedLocator(y_ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
        
        ax.grid(True, alpha=0.3, which='both', color=self.FG_SECONDARY)
        ax.minorticks_on()
        
        cbar = self.fig.colorbar(contourf, ax=ax)
        cbar.set_label('Transmission (%)', color=self.FG_PRIMARY)
        cbar.ax.yaxis.set_tick_params(color=self.FG_PRIMARY)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.FG_PRIMARY)
        
        # Add hover annotation
        annot = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                           bbox=dict(boxstyle="round,pad=0.5", facecolor=self.BG_LIGHT, 
                                   edgecolor=self.FG_PRIMARY, linewidth=1.5),
                           arrowprops=dict(arrowstyle="->", color=self.FG_PRIMARY, lw=1),
                           color=self.FG_PRIMARY, fontsize=8, family='monospace')
        annot.set_visible(False)
        
        # Store hover context
        self.hover_contexts[ax] = {
            'scatter': scatter,
            'data': data.reset_index(drop=True),
            'annot': annot
        }
        
    def plot_three_phase(self, ax, AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer):
        """Plot three-phase classification with hover tooltips."""
        # Binary classification using single threshold
        phase_colors = ['#e74c3c', '#2ecc71']
        
        # Simple contourf without BoundaryNorm to avoid artifacts
        ax.contourf(AS_grid, PS_grid, trans_grid, levels=[35, threshold, 95],
                   colors=phase_colors, alpha=0.7)

        # Draw boundary at the threshold
        ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                   colors='black', linewidths=2.5)

        data['phase'] = pd.cut(data['transmission_pct'], bins=[0, threshold, 100],
                               labels=['Precipitate', 'Clear'])

        # Scatter with explicit binary colors for hover
        scatter = ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                             c=[('#e74c3c' if p == 'Precipitate' else '#2ecc71') for p in data['phase']],
                             s=20, edgecolors='black', linewidth=0.5, alpha=0.8)
        
        ax.set_xlabel(f'{surfactant} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_ylabel(f'{polymer} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_title('Three-Phase Classification', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Set explicit tick locations for better visibility
        from matplotlib.ticker import FixedLocator, FuncFormatter
        x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
        
        ax.xaxis.set_major_locator(FixedLocator(x_ticks))
        ax.yaxis.set_major_locator(FixedLocator(y_ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
        
        ax.grid(True, alpha=0.3, which='both', color=self.FG_SECONDARY)
        ax.minorticks_on()
        
        # Create binary legend
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='#e74c3c', edgecolor='black', label='Precipitate (<{:.0f}%)'.format(threshold)),
                  Patch(facecolor='#2ecc71', edgecolor='black', label='Clear (≥{:.0f}%)'.format(threshold))]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=8, 
             facecolor=self.BG_LIGHT, edgecolor=self.FG_SECONDARY, labelcolor=self.FG_PRIMARY)
        
        # Add hover annotation
        annot = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                           bbox=dict(boxstyle="round,pad=0.5", facecolor=self.BG_LIGHT, 
                                   edgecolor=self.FG_PRIMARY, linewidth=1.5),
                           arrowprops=dict(arrowstyle="->", color=self.FG_PRIMARY, lw=1),
                           color=self.FG_PRIMARY, fontsize=8, family='monospace')
        annot.set_visible(False)
        
        # Store hover context
        self.hover_contexts[ax] = {
            'scatter': scatter,
            'data': data.reset_index(drop=True),
            'annot': annot
        }
        
    def plot_binary_boundary(self, ax, AS_grid, PS_grid, trans_grid, data, threshold, surf, poly):
        """Plot binary phase boundary with hover tooltips."""
        colors = ['#e74c3c' if t < threshold else '#2ecc71' for t in data['transmission_pct']]
        scatter = ax.scatter(data['surfactant_pct'], data['polymer_pct'],
                  c=colors, s=50, edgecolors='black', linewidth=0.5, alpha=0.8)
        
        # Use smoother contour with anti-aliasing and filled contour for clarity
        contour_thresh = ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                                    colors='black', linewidths=2.5, antialiased=True)
        # Add filled contour bands for visual clarity
        ax.contourf(AS_grid, PS_grid, trans_grid, levels=[0, threshold, 100],
                   colors=['#e74c3c', '#2ecc71'], alpha=0.15, antialiased=True)
        ax.clabel(contour_thresh, inline=True, fontsize=10, fmt=f'{threshold:.0f}%% Boundary')
        
        ax.set_xlabel(f'{surf} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_ylabel(f'{poly} Concentration (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_title(f'Binary Phase Boundary ({threshold:.0f}% Threshold)', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Set explicit tick locations for better visibility
        from matplotlib.ticker import FixedLocator, FuncFormatter
        x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
        
        ax.xaxis.set_major_locator(FixedLocator(x_ticks))
        ax.yaxis.set_major_locator(FixedLocator(y_ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
        
        ax.grid(True, alpha=0.3, which='both', color=self.FG_SECONDARY)
        ax.minorticks_on()
        
        red_patch = mpatches.Patch(color='#e74c3c', label=f'2-Phase (<{threshold:.0f}%)')
        green_patch = mpatches.Patch(color='#2ecc71', label=f'1-Phase (≥{threshold:.0f}%)')
        ax.legend(handles=[red_patch, green_patch], loc='upper left', fontsize=8,
                 facecolor=self.BG_LIGHT, edgecolor=self.FG_SECONDARY, labelcolor=self.FG_PRIMARY)
        
        # Add hover annotation
        annot = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                           bbox=dict(boxstyle="round,pad=0.5", facecolor=self.BG_LIGHT, 
                                   edgecolor=self.FG_PRIMARY, linewidth=1.5),
                           arrowprops=dict(arrowstyle="->", color=self.FG_PRIMARY, lw=1),
                           color=self.FG_PRIMARY, fontsize=8, family='monospace')
        annot.set_visible(False)
        
        # Store hover context
        self.hover_contexts[ax] = {
            'scatter': scatter,
            'data': data.reset_index(drop=True),
            'annot': annot
        }
        
    def plot_statistics(self, ax, data, threshold):
        """Plot transmission distribution and statistics."""
        bins = np.arange(30, 100, 5)
        ax.hist(data['transmission_pct'], bins=bins, color='steelblue', alpha=0.7, edgecolor='black')
        
        # Single threshold line at the selected cutoff
        ax.axvline(threshold, color='black', linewidth=2.5, linestyle='-', label=f'Threshold ({threshold:.0f}%)')
        
        ax.set_xlabel('Transmission (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_ylabel('Frequency', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax.set_title('Transmission Distribution', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax.legend(fontsize=7, facecolor=self.BG_LIGHT, edgecolor=self.FG_SECONDARY, labelcolor=self.FG_PRIMARY)
        ax.grid(True, alpha=0.3, color=self.FG_SECONDARY)
        
        stats_text = f"Mean: {data['transmission_pct'].mean():.1f}%\n"
    def kinetic_analysis(self):
        """Perform kinetic analysis to determine equilibrium time."""
        if not self.selected_experiment.get():
            messagebox.showwarning("Warning", "Please select an experiment first")
            return
        
        # No timepoint selection needed - we analyze all timepoints
        
        try:
            # Load all timepoints for this experiment
            conn = sqlite3.connect(self.db_path.get())
            
            # Get all data for this experiment
            query = """
                SELECT timepoint_minutes, transmission_pct, well, plate
                FROM measurements
                WHERE experiment_id = ?
                ORDER BY timepoint_minutes, plate, well
            """
            
            all_data = pd.read_sql_query(query, conn, params=(self.selected_experiment.get(),))
            conn.close()
            
            if len(all_data) < 2:
                messagebox.showerror("Error", "Need at least 2 timepoints for kinetic analysis")
                return
            
            # Calculate statistics per timepoint using pandas
            kinetic_data = all_data.groupby('timepoint_minutes')['transmission_pct'].agg([
                ('avg_trans', 'mean'),
                ('std_trans', 'std'),
                ('min_trans', 'min'),
                ('max_trans', 'max'),
                ('n_wells', 'count')
            ]).reset_index()
            
            # Get well data for trajectories - create unique well IDs that include plate
            all_data['well_id'] = all_data['plate'].astype(str) + '-' + all_data['well']
            well_data = all_data[['well_id', 'timepoint_minutes', 'transmission_pct']].copy()
            
            # Create kinetic analysis figure
            self.create_kinetic_analysis(kinetic_data, well_data)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform kinetic analysis:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_kinetic_analysis(self, kinetic_data, well_data):
        """Create comprehensive kinetic analysis plots."""
        
        self.fig.clear()
        
        # Create 2x2 subplot layout
        axes = self.fig.subplots(2, 2)
        
        exp_id = self.selected_experiment.get()
        
        self.fig.suptitle(f'Kinetic Analysis: {exp_id}\nEquilibrium Determination',
                         fontsize=14, fontweight='bold', color=self.FG_PRIMARY)
        self.fig.patch.set_facecolor(self.BG_MEDIUM)
        
        # Calculate equilibrium metrics
        final_avg = kinetic_data['avg_trans'].iloc[-1]
        
        # Find when system reaches 98% of final value (equilibrium criterion)
        threshold_98 = final_avg * 0.98
        eq_time_98 = None
        for _, row in kinetic_data.iterrows():
            if row['avg_trans'] >= threshold_98:
                eq_time_98 = row['timepoint_minutes']
                break
        
        # Calculate rate of change between consecutive timepoints
        kinetic_data['rate_of_change'] = kinetic_data['avg_trans'].diff() / kinetic_data['timepoint_minutes'].diff()
        
        # Plot 1: Average transmission vs time
        ax1 = axes[0, 0]
        ax1.plot(kinetic_data['timepoint_minutes'], kinetic_data['avg_trans'], 
                'o-', color='#2ecc71', linewidth=2, markersize=8, label='Mean Transmission')
        ax1.fill_between(kinetic_data['timepoint_minutes'],
                        kinetic_data['avg_trans'] - kinetic_data['std_trans'],
                        kinetic_data['avg_trans'] + kinetic_data['std_trans'],
                        alpha=0.3, color='#2ecc71', label='±1 Std Dev')
        
        # Add equilibrium line
        ax1.axhline(final_avg, color='#e74c3c', linestyle='--', linewidth=2, label=f'Final Value ({final_avg:.1f}%)')
        ax1.axhline(threshold_98, color='#f39c12', linestyle=':', linewidth=2, label=f'98% of Final ({threshold_98:.1f}%)')
        
        if eq_time_98:
            ax1.axvline(eq_time_98, color='#f39c12', linestyle=':', linewidth=2, alpha=0.7)
            ax1.text(eq_time_98, ax1.get_ylim()[1]*0.95, f' t₉₈ = {eq_time_98:.1f} min',
                    rotation=90, verticalalignment='top', color=self.FG_PRIMARY, fontweight='bold')
        
        ax1.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax1.set_ylabel('Transmission (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax1.set_title('Mean Transmission Evolution', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax1.legend(fontsize=8, facecolor=self.BG_LIGHT, edgecolor=self.FG_SECONDARY, labelcolor=self.FG_PRIMARY)
        ax1.grid(True, alpha=0.3, color=self.FG_SECONDARY)
        ax1.set_facecolor(self.BG_DARK)
        
        # Plot 2: Rate of change
        ax2 = axes[0, 1]
        ax2.plot(kinetic_data['timepoint_minutes'].iloc[1:], kinetic_data['rate_of_change'].iloc[1:],
                'o-', color='#3498db', linewidth=2, markersize=8)
        ax2.axhline(0, color=self.FG_SECONDARY, linestyle='--', linewidth=1)
        
        ax2.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax2.set_ylabel('Rate of Change (%/min)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax2.set_title('Kinetic Rate Analysis', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax2.grid(True, alpha=0.3, color=self.FG_SECONDARY)
        ax2.set_facecolor(self.BG_DARK)
        
        # Add text annotation about equilibrium
        rate_threshold = 0.1  # Arbitrary small rate
        near_zero = kinetic_data[abs(kinetic_data['rate_of_change']) < rate_threshold]
        if len(near_zero) > 0:
            eq_time_rate = near_zero['timepoint_minutes'].iloc[0]
            ax2.axvline(eq_time_rate, color='#e74c3c', linestyle=':', linewidth=2, alpha=0.7)
            ax2.text(eq_time_rate, ax2.get_ylim()[1]*0.9, f' Rate ≈ 0 at {eq_time_rate:.1f} min',
                    rotation=90, verticalalignment='top', color=self.FG_PRIMARY, fontweight='bold')
        
        # Plot 3: Sample well trajectories
        ax3 = axes[1, 0]
        
        # Plot 10 random wells to show variability (using unique well_id that includes plate)
        sample_wells = well_data['well_id'].unique()[:10]
        colors = plt.cm.viridis(np.linspace(0, 1, len(sample_wells)))
        
        for well_id, color in zip(sample_wells, colors):
            well_subset = well_data[well_data['well_id'] == well_id]
            ax3.plot(well_subset['timepoint_minutes'], well_subset['transmission_pct'],
                    'o-', alpha=0.6, linewidth=1.5, markersize=4, color=color, label=f'{well_id}')
        
        ax3.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax3.set_ylabel('Transmission (%)', fontsize=10, fontweight='bold', color=self.FG_PRIMARY)
        ax3.set_title('Individual Well Trajectories (Sample)', fontsize=11, fontweight='bold', color=self.FG_PRIMARY)
        ax3.legend(fontsize=7, ncol=2, facecolor=self.BG_LIGHT, edgecolor=self.FG_SECONDARY, labelcolor=self.FG_PRIMARY)
        ax3.grid(True, alpha=0.3, color=self.FG_SECONDARY)
        ax3.set_facecolor(self.BG_DARK)
        
        # Plot 4: Equilibrium summary statistics
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        # Calculate additional statistics
        initial_avg = kinetic_data['avg_trans'].iloc[0]
        total_change = final_avg - initial_avg
        
        # Time to 90%, 95%, 98%, 99% equilibrium
        milestones = {'90%': 0.90, '95%': 0.95, '98%': 0.98, '99%': 0.99}
        milestone_times = {}
        for label, frac in milestones.items():
            threshold = initial_avg + (final_avg - initial_avg) * frac
            for _, row in kinetic_data.iterrows():
                if (total_change > 0 and row['avg_trans'] >= threshold) or \
                   (total_change < 0 and row['avg_trans'] <= threshold):
                    milestone_times[label] = row['timepoint_minutes']
                    break
        
        # Create summary text
        summary_text = "EQUILIBRIUM ANALYSIS SUMMARY\n"
        summary_text += "="*50 + "\n\n"
        summary_text += f"Initial Transmission:  {initial_avg:.2f}%\n"
        summary_text += f"Final Transmission:    {final_avg:.2f}%\n"
        summary_text += f"Total Change:          {total_change:.2f}%\n\n"
        
        summary_text += "Time to Reach Equilibrium:\n"
        summary_text += "-"*50 + "\n"
        for label, time in milestone_times.items():
            summary_text += f"  {label} equilibrium:  {time:.2f} minutes\n"
        
        summary_text += f"\nFinal Std Dev:         {kinetic_data['std_trans'].iloc[-1]:.2f}%\n"
        summary_text += f"CV at Final:           {(kinetic_data['std_trans'].iloc[-1]/final_avg*100):.2f}%\n\n"
        
        # Recommendation
        summary_text += "RECOMMENDATION:\n"
        summary_text += "-"*50 + "\n"
        if eq_time_98:
            summary_text += f"✓ Use timepoints ≥ {eq_time_98:.1f} min for\n"
            summary_text += "  quasi-equilibrium phase diagrams\n"
        else:
            summary_text += "! System may not have reached equilibrium\n"
            summary_text += f"  Consider longer measurement times\n"
        
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                fontsize=9, verticalalignment='top', horizontalalignment='left',
                family='monospace', color=self.FG_PRIMARY,
                bbox=dict(boxstyle='round', facecolor=self.BG_LIGHT, alpha=0.9, edgecolor=self.ACCENT_BLUE, linewidth=2))
        
        # Style all axes
        for ax in axes.flat[:3]:
            ax.tick_params(colors=self.FG_PRIMARY)
            ax.spines['bottom'].set_color(self.FG_SECONDARY)
            ax.spines['top'].set_color(self.FG_SECONDARY)
            ax.spines['left'].set_color(self.FG_SECONDARY)
            ax.spines['right'].set_color(self.FG_SECONDARY)
        
        self.fig.tight_layout()
        self.canvas.draw()
        
        self.current_data = kinetic_data  # Store for saving
    
    def save_figure(self):
        """Save the current figure to file."""
        if self.current_data is None:
            messagebox.showwarning("Warning", "No figure to save. Generate a phase diagram first.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if filename:
            self.fig.savefig(filename, dpi=300, bbox_inches='tight', facecolor=self.BG_MEDIUM)
            messagebox.showinfo("Success", f"Figure saved to:\n{filename}")
    
    def export_experiments(self):
        """Export selected experiments to CSV file."""
        
        # Create selection dialog
        export_window = tk.Toplevel(self.root)
        export_window.title("Export Experiments")
        export_window.geometry("500x400")
        export_window.configure(bg=self.BG_DARK)
        
        # Title
        tk.Label(
            export_window,
            text="Select Experiments to Export",
            font=('Segoe UI', 12, 'bold'),
            bg=self.BG_DARK,
            fg=self.FG_PRIMARY
        ).pack(pady=10)
        
        # Listbox with scrollbar
        list_frame = tk.Frame(export_window, bg=self.BG_DARK)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.BG_MEDIUM)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            font=('Segoe UI', 10),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY,
            selectbackground=self.ACCENT_BLUE,
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Load experiments
        try:
            conn = sqlite3.connect(self.db_path.get())
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT experiment_id, experiment_name FROM measurements ORDER BY experiment_id")
            experiments = cursor.fetchall()
            conn.close()
            
            for exp_id, exp_name in experiments:
                display_text = f"{exp_id}: {exp_name}" if exp_name else exp_id
                listbox.insert(tk.END, display_text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load experiments:\n{str(e)}")
            export_window.destroy()
            return
        
        # Button frame
        btn_frame = tk.Frame(export_window, bg=self.BG_DARK)
        btn_frame.pack(pady=10)
        
        def do_export():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select at least one experiment")
                return
            
            # Get selected experiment IDs
            selected_exp_ids = [experiments[i][0] for i in selection]
            
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Experiments"
            )
            
            if not filename:
                return
            
            try:
                # Load data for selected experiments
                conn = sqlite3.connect(self.db_path.get())
                
                placeholders = ','.join(['?' for _ in selected_exp_ids])
                query = f"""
                    SELECT experiment_id, experiment_name, date_created,
                           plate, well, row, column,
                           surfactant_name, polymer_name,
                           surfactant_pct, polymer_pct,
                           timepoint_minutes, transmission_pct,
                           total_volume_uL,
                           excel_filename, transmission_filename
                    FROM measurements
                    WHERE experiment_id IN ({placeholders})
                    ORDER BY experiment_id, plate, well, timepoint_minutes
                """
                
                data = pd.read_sql_query(query, conn, params=selected_exp_ids)
                conn.close()
                
                # Save to CSV
                data.to_csv(filename, index=False)
                
                messagebox.showinfo("Success", 
                    f"Exported {len(data)} records from {len(selected_exp_ids)} experiment(s) to:\n{filename}")
                export_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export:\n{str(e)}")
        
        tk.Button(
            btn_frame,
            text="Export",
            font=('Segoe UI', 10, 'bold'),
            bg=self.ACCENT_GREEN,
            fg=self.BG_DARK,
            relief=tk.FLAT,
            cursor="hand2",
            command=do_export,
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Cancel",
            font=('Segoe UI', 10),
            bg=self.ACCENT_RED,
            fg=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=export_window.destroy,
            width=15
        ).pack(side=tk.LEFT, padx=5)


def main():
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if filename:
            self.fig.savefig(filename, dpi=300, bbox_inches='tight', facecolor=self.BG_MEDIUM)
            messagebox.showinfo("Success", f"Figure saved to:\n{filename}")


def main():
    """Launch the analysis GUI."""
    root = tk.Tk()
    app = PhaseAnalysisGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
