"""
GUI for Phase Diagram Database System
Dark-themed interface for ingesting experiments with progress tracking and validation.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd
import re
from schema import create_database
from ingest_experiment import ingest_experiment, query_experiment, extract_surfactant_polymer_names, extract_water_hardness_from_filename


class DarkThemedGUI:
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
        self.root.title("Phase Diagram Database - Data Ingestion Tool")
        
        # Start maximized to ensure all content is visible
        self.root.state('zoomed')
        
        # Set minimum size to prevent content from being cut off
        self.root.minsize(900, 750)
        self.root.configure(bg=self.BG_DARK)
        
        # Variables
        self.db_path = tk.StringVar(value="phase_diagrams.db")
        self.excel_path = tk.StringVar()
        self.transmission_folder = tk.StringVar()
        self.experiment_id = tk.StringVar()
        self.experiment_name = tk.StringVar()
        self.water_hardness = tk.StringVar(value="7.0")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Create the main UI components."""
        
        # Title
        title_frame = tk.Frame(self.root, bg=self.BG_DARK)
        title_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title = tk.Label(
            title_frame,
            text="Phase Diagram Database",
            font=('Segoe UI', 18, 'bold'),
            bg=self.BG_DARK,
            fg=self.ACCENT_GREEN
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            title_frame,
            text="Ingest surfactant-polymer phase diagram experiments",
            font=('Segoe UI', 10),
            bg=self.BG_DARK,
            fg=self.FG_SECONDARY
        )
        subtitle.pack(anchor=tk.W)
        
        # Main container with padding
        main_container = tk.Frame(self.root, bg=self.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Input section
        self.create_input_section(main_container)
        
        # Progress section
        self.create_progress_section(main_container)
        
        # Results section
        self.create_results_section(main_container)
        
        # Buttons
        self.create_button_section(main_container)
        
    def create_input_section(self, parent):
        """Create input fields section."""
        frame = tk.LabelFrame(
            parent,
            text="  Experiment Configuration  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT,
            borderwidth=2
        )
        frame.pack(fill=tk.X, pady=(0, 10))
        
        inner = tk.Frame(frame, bg=self.BG_MEDIUM)
        inner.pack(fill=tk.X, padx=15, pady=15)
        
        # Database path
        self.create_field_row(
            inner, 0,
            "Database File:",
            self.db_path,
            browse_type="save_db"
        )
        
        # Excel file
        self.create_field_row(
            inner, 1,
            "Excel File:",
            self.excel_path,
            browse_type="file"
        )
        
        # Transmission folder
        self.create_field_row(
            inner, 2,
            "Transmission Folder:",
            self.transmission_folder,
            browse_type="folder"
        )
        
        # Spacer
        tk.Label(
            inner,
            text="",
            bg=self.BG_MEDIUM,
            height=1
        ).grid(row=3, column=0, columnspan=3)
        
        # Experiment ID (auto-generated, read-only)
        id_label = tk.Label(
            inner,
            text="Experiment ID:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY,
            anchor=tk.W,
            width=18
        )
        id_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        
        self.id_display = tk.Label(
            inner,
            textvariable=self.experiment_id,
            font=('Segoe UI', 9),
            bg=self.BG_DARK,
            fg=self.ACCENT_ORANGE,
            anchor=tk.W,
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        self.id_display.grid(row=4, column=1, sticky=tk.EW, pady=5, padx=(5, 5))
        
        tk.Label(
            inner,
            text="(auto-generated)",
            font=('Segoe UI', 8, 'italic'),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY
        ).grid(row=4, column=2, padx=(5, 0), pady=5)
        
        # Experiment Name (auto-generated, read-only)
        name_label = tk.Label(
            inner,
            text="Experiment Name:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY,
            anchor=tk.W,
            width=18
        )
        name_label.grid(row=5, column=0, sticky=tk.W, pady=5)
        
        self.name_display = tk.Label(
            inner,
            textvariable=self.experiment_name,
            font=('Segoe UI', 9),
            bg=self.BG_DARK,
            fg=self.ACCENT_ORANGE,
            anchor=tk.W,
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        self.name_display.grid(row=5, column=1, sticky=tk.EW, pady=5, padx=(5, 5))
        
        tk.Label(
            inner,
            text="(auto-generated)",
            font=('Segoe UI', 8, 'italic'),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY
        ).grid(row=5, column=2, padx=(5, 0), pady=5)
        
        # Water Hardness (auto-detected from filename)
        hardness_label = tk.Label(
            inner,
            text="Water Hardness:",
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY,
            anchor=tk.W,
            width=18
        )
        hardness_label.grid(row=6, column=0, sticky=tk.W, pady=5)
        
        self.hardness_display = tk.Label(
            inner,
            textvariable=self.water_hardness,
            font=('Segoe UI', 9),
            bg=self.BG_DARK,
            fg=self.ACCENT_GREEN,
            anchor=tk.W,
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        self.hardness_display.grid(row=6, column=1, sticky=tk.EW, pady=5, padx=(5, 5))
        
        tk.Label(
            inner,
            text="gpg (from filename)",
            font=('Segoe UI', 8, 'italic'),
            bg=self.BG_MEDIUM,
            fg=self.FG_SECONDARY
        ).grid(row=6, column=2, padx=(5, 0), pady=5)
        
    def create_field_row(self, parent, row, label_text, variable, browse_type=None, placeholder=None):
        """Create a labeled input field with optional browse button."""
        label = tk.Label(
            parent,
            text=label_text,
            font=('Segoe UI', 9),
            bg=self.BG_MEDIUM,
            fg=self.FG_PRIMARY,
            anchor=tk.W,
            width=18
        )
        label.grid(row=row, column=0, sticky=tk.W, pady=5)
        
        entry = tk.Entry(
            parent,
            textvariable=variable,
            font=('Segoe UI', 9),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            insertbackground=self.FG_PRIMARY,
            relief=tk.FLAT,
            borderwidth=0
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=(5, 5))
        
        if placeholder and not variable.get():
            entry.insert(0, placeholder)
            entry.config(fg=self.FG_SECONDARY)
            
            def on_focus_in(event):
                if entry.get() == placeholder:
                    entry.delete(0, tk.END)
                    entry.config(fg=self.FG_PRIMARY)
            
            def on_focus_out(event):
                if not entry.get():
                    entry.insert(0, placeholder)
                    entry.config(fg=self.FG_SECONDARY)
            
            entry.bind('<FocusIn>', on_focus_in)
            entry.bind('<FocusOut>', on_focus_out)
        
        if browse_type:
            browse_btn = tk.Button(
                parent,
                text="Browse...",
                font=('Segoe UI', 9),
                bg=self.ACCENT_BLUE,
                fg=self.FG_PRIMARY,
                activebackground=self.ACCENT_GREEN,
                activeforeground=self.FG_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda: self.browse(browse_type, variable)
            )
            browse_btn.grid(row=row, column=2, padx=(5, 0), pady=5)
        
        parent.columnconfigure(1, weight=1)
        
    def browse(self, browse_type, variable):
        """Handle browse button clicks."""
        if browse_type == "file":
            filename = filedialog.askopenfilename(
                title="Select Excel File",
                filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            )
            if filename:
                variable.set(filename)
                # Auto-generate experiment ID and name when file is selected
                self.auto_generate_experiment_info()
        elif browse_type == "folder":
            folder = filedialog.askdirectory(
                title="Select Transmission Data Folder"
            )
            if folder:
                variable.set(folder)
                # Update water hardness from folder name
                water_hardness = float(extract_water_hardness_from_filename(folder))
                # If not found in folder, check excel filename
                if water_hardness == 7.0 and self.excel_path.get():
                    water_hardness = float(extract_water_hardness_from_filename(self.excel_path.get()))
                self.water_hardness.set(f"{water_hardness}")
        elif browse_type == "save_db":
            filename = filedialog.asksaveasfilename(
                title="Database File",
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
            )
            if filename:
                variable.set(filename)
    
    def auto_generate_experiment_info(self):
        """Auto-generate experiment ID and name based on Excel file contents."""
        excel_path = self.excel_path.get()
        
        if not excel_path or not Path(excel_path).exists():
            self.log_progress("No Excel file selected")
            return
        
        try:
            self.log_progress(f"Reading Excel file: {Path(excel_path).name}")
            
            # Read the Test Solutions sheet to extract surfactant/polymer info
            solutions = pd.read_excel(excel_path, sheet_name='Test Solutions')
            self.log_progress(f"Found {len(solutions)} solutions in Test Solutions sheet")
            
            # Debug: show what we found
            for _, row in solutions.iterrows():
                sol_id = row['Solution']
                desc = row['Description']
                self.log_progress(f"  {sol_id}: {desc}")
            
            surfactant_name, polymer_name = extract_surfactant_polymer_names(solutions)
            self.log_progress(f"Extracted - Surfactant: {surfactant_name}, Polymer: {polymer_name}")
            
            # Handle None or NaN values
            if surfactant_name is None or (isinstance(surfactant_name, float) and pd.isna(surfactant_name)):
                surfactant_name = "Unknown_Surfactant"
                self.log_progress("Warning: Could not identify surfactant")
            if polymer_name is None or (isinstance(polymer_name, float) and pd.isna(polymer_name)):
                polymer_name = "Unknown_Polymer"
                self.log_progress("Warning: Could not identify polymer")
            
            # Get current date
            date_str = datetime.now().strftime("%Y%m%d")
            
            # Extract water hardness from filename (need this before generating ID)
            water_hardness = float(extract_water_hardness_from_filename(excel_path))
            # Also check transmission folder if selected
            if water_hardness == 7.0 and self.transmission_folder.get():
                water_hardness = float(extract_water_hardness_from_filename(self.transmission_folder.get()))
            self.water_hardness.set(f"{water_hardness}")
            
            # Create short codes for surfactant and polymer
            surf_code = self.create_short_code(surfactant_name)
            poly_code = self.create_short_code(polymer_name)
            
            # Generate experiment ID: exp_YYYYMMDD_surf_poly_Xgpg
            hardness_code = f"{int(water_hardness)}gpg"
            exp_id = f"exp_{date_str}_{surf_code}_{poly_code}_{hardness_code}"
            
            # Check if ID already exists and add replicate suffix if needed
            if Path(self.db_path.get()).exists():
                exp_id = self.get_unique_experiment_id(exp_id)
            
            self.experiment_id.set(exp_id)
            
            # Generate experiment name: "Surfactant-Polymer X gpg (YYYY-MM-DD)"
            # Add replicate info if present in ID
            if "_rep" in exp_id:
                rep_num = exp_id.split("_rep")[1]
                exp_name = f"{surfactant_name}-{polymer_name} {hardness_code} Rep{rep_num} ({datetime.now().strftime('%Y-%m-%d')})"
            else:
                exp_name = f"{surfactant_name}-{polymer_name} {hardness_code} ({datetime.now().strftime('%Y-%m-%d')})"
            self.experiment_name.set(exp_name)
            
            self.log_progress(f"✓ Generated experiment ID: {exp_id}")
            self.log_progress(f"✓ Water Hardness: {water_hardness} gpg")
            
        except Exception as e:
            # If we can't read the file, use generic naming
            import traceback
            self.log_progress(f"ERROR reading Excel: {str(e)}", tag="error")
            self.log_progress(traceback.format_exc(), tag="error")
            
            # Still try to extract water hardness
            water_hardness = float(extract_water_hardness_from_filename(excel_path))
            if water_hardness == 7.0 and self.transmission_folder.get():
                water_hardness = float(extract_water_hardness_from_filename(self.transmission_folder.get()))
            self.water_hardness.set(f"{water_hardness}")
            
            date_str = datetime.now().strftime("%Y%m%d")
            hardness_code = f"{int(water_hardness)}gpg"
            exp_id = f"exp_{date_str}_unknown_{hardness_code}"
            
            if Path(self.db_path.get()).exists():
                exp_id = self.get_unique_experiment_id(exp_id)
            
            self.experiment_id.set(exp_id)
            
            # Generate name with replicate info if present
            if "_rep" in exp_id:
                rep_num = exp_id.split("_rep")[1]
                self.experiment_name.set(f"Experiment {hardness_code} Rep{rep_num} {datetime.now().strftime('%Y-%m-%d')}")
            else:
                self.experiment_name.set(f"Experiment {hardness_code} {datetime.now().strftime('%Y-%m-%d')}")
            self.log_progress(f"Using fallback ID: {exp_id}")
    
    def create_short_code(self, name):
        """Create a short code from a chemical name."""
        if not name:
            return "unk"
        
        name_lower = name.lower()
        
        # Common abbreviations
        abbrev_map = {
            'rhamnolipid': 'rl',
            'excel': 'excel',
            'polyethylene glycol': 'peg',
            'polyvinyl alcohol': 'pva',
            'sodium dodecyl sulfate': 'sds',
            'cetyltrimethylammonium bromide': 'ctab',
        }
        
        # Check for known abbreviations
        for full_name, abbrev in abbrev_map.items():
            if full_name in name_lower:
                return abbrev
        
        # Otherwise, use first word or first 4 letters
        words = re.findall(r'\w+', name)
        if words:
            return words[0][:4].lower()
        
        return "unk"
    
    def get_unique_experiment_id(self, base_id):
        """Ensure experiment ID is unique by adding replicate suffix if needed."""
        conn = sqlite3.connect(self.db_path.get())
        cursor = conn.cursor()
        
        # Check if base_id exists
        cursor.execute(
            "SELECT COUNT(*) FROM measurements WHERE experiment_id = ?",
            (base_id,)
        )
        
        if cursor.fetchone()[0] == 0:
            conn.close()
            return base_id
        
        # This is a replicate - add _rep1, _rep2, _rep3, etc.
        rep_num = 1
        while rep_num <= 99:  # Support up to 99 replicates
            new_id = f"{base_id}_rep{rep_num}"
            cursor.execute(
                "SELECT COUNT(*) FROM measurements WHERE experiment_id = ?",
                (new_id,)
            )
            if cursor.fetchone()[0] == 0:
                conn.close()
                self.log_progress(f"⚠ Replicate detected: Using ID {new_id}")
                return new_id
            rep_num += 1
        
        # If all replicate numbers used, add timestamp
        conn.close()
        return f"{base_id}_rep{datetime.now().strftime('%H%M%S')}"
    
    def create_progress_section(self, parent):
        """Create progress display section."""
        frame = tk.LabelFrame(
            parent,
            text="  Progress  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT,
            borderwidth=2
        )
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        inner = tk.Frame(frame, bg=self.BG_MEDIUM)
        inner.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Progress text area
        self.progress_text = scrolledtext.ScrolledText(
            inner,
            font=('Consolas', 9),
            bg=self.BG_DARK,
            fg=self.ACCENT_GREEN,
            insertbackground=self.FG_PRIMARY,
            relief=tk.FLAT,
            height=8,
            wrap=tk.WORD
        )
        self.progress_text.pack(fill=tk.BOTH, expand=True)
        self.progress_text.config(state=tk.DISABLED)
        
    def create_results_section(self, parent):
        """Create results display section."""
        frame = tk.LabelFrame(
            parent,
            text="  Results & Validation  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.BG_MEDIUM,
            fg=self.ACCENT_BLUE,
            relief=tk.FLAT,
            borderwidth=2
        )
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        inner = tk.Frame(frame, bg=self.BG_MEDIUM)
        inner.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Results text area
        self.results_text = scrolledtext.ScrolledText(
            inner,
            font=('Consolas', 9),
            bg=self.BG_DARK,
            fg=self.FG_PRIMARY,
            insertbackground=self.FG_PRIMARY,
            relief=tk.FLAT,
            height=10,
            wrap=tk.NONE
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        self.results_text.config(state=tk.DISABLED)
        
    def create_button_section(self, parent):
        """Create button panel."""
        frame = tk.Frame(parent, bg=self.BG_DARK)
        frame.pack(fill=tk.X)
        
        # Ingest button
        self.ingest_btn = tk.Button(
            frame,
            text="Ingest Experiment",
            font=('Segoe UI', 11, 'bold'),
            bg=self.ACCENT_GREEN,
            fg=self.BG_DARK,
            activebackground=self.ACCENT_BLUE,
            activeforeground=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.ingest_data,
            padx=30,
            pady=10
        )
        self.ingest_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # View database button
        view_btn = tk.Button(
            frame,
            text="View Database Stats",
            font=('Segoe UI', 10),
            bg=self.ACCENT_BLUE,
            fg=self.FG_PRIMARY,
            activebackground=self.ACCENT_GREEN,
            activeforeground=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.view_database,
            padx=20,
            pady=10
        )
        view_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Delete experiment button
        delete_btn = tk.Button(
            frame,
            text="Delete Experiment",
            font=('Segoe UI', 10),
            bg=self.ACCENT_RED,
            fg=self.FG_PRIMARY,
            activebackground=self.ACCENT_ORANGE,
            activeforeground=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.delete_experiment,
            padx=20,
            pady=10
        )
        delete_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Clear button
        clear_btn = tk.Button(
            frame,
            text="Clear",
            font=('Segoe UI', 10),
            bg=self.BG_LIGHT,
            fg=self.FG_PRIMARY,
            activebackground=self.ACCENT_ORANGE,
            activeforeground=self.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.clear_outputs,
            padx=20,
            pady=10
        )
        clear_btn.pack(side=tk.RIGHT)
        
    def log_progress(self, message, tag=None):
        """Add message to progress window."""
        self.progress_text.config(state=tk.NORMAL)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        
        self.progress_text.insert(tk.END, formatted)
        
        if tag == "error":
            # Color the last line red
            last_line_start = self.progress_text.index("end-2c linestart")
            last_line_end = self.progress_text.index("end-1c")
            self.progress_text.tag_add("error", last_line_start, last_line_end)
            self.progress_text.tag_config("error", foreground=self.ACCENT_RED)
        
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
        
    def log_results(self, message):
        """Add message to results window."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, message)
        self.results_text.see(tk.END)
        self.results_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
        
    def clear_outputs(self):
        """Clear progress and results windows."""
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.delete(1.0, tk.END)
        self.progress_text.config(state=tk.DISABLED)
        
        self.results_text.config(state=tk.NORMAL)
    def validate_inputs(self):
        """Validate all required inputs."""
        errors = []
        
        if not self.db_path.get():
            errors.append("Database file path is required")
        
        if not self.experiment_id.get():
            errors.append("Experiment ID is required (should be auto-generated)")
        
        if not self.experiment_name.get():
            errors.append("Experiment Name is required (should be auto-generated)")
        
        if not self.excel_path.get():
            errors.append("Excel file is required")
        elif not Path(self.excel_path.get()).exists():
            errors.append("Excel file does not exist")
        
        if not self.transmission_folder.get():
            errors.append("Transmission folder is required")
        elif not Path(self.transmission_folder.get()).exists():
            errors.append("Transmission folder does not exist")
        
        return errors
        
    def ingest_data(self):
        """Main ingestion workflow."""
        # Clear previous results
        self.clear_outputs()
        
        # Validate inputs
        errors = self.validate_inputs()
        if errors:
            for error in errors:
                self.log_progress(f"ERROR: {error}", tag="error")
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
        
        # Disable button during processing
        self.ingest_btn.config(state=tk.DISABLED, text="Processing...")
        
        try:
            db_path = self.db_path.get()
            experiment_id = self.experiment_id.get()
            experiment_name = self.experiment_name.get()
            excel_file = self.excel_path.get()
            transmission_folder = self.transmission_folder.get()
            
            # Step 1: Create/verify database
            self.log_progress("Checking database...")
            if not Path(db_path).exists():
                self.log_progress(f"Creating new database: {db_path}")
                create_database(db_path)
            else:
                self.log_progress(f"Using existing database: {db_path}")
            
            # Step 2: Check if experiment already exists
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM measurements WHERE experiment_id = ?",
                (experiment_id,)
            )
            existing_count = cursor.fetchone()[0]
            conn.close()
            
            if existing_count > 0:
                response = messagebox.askyesno(
                    "Experiment Exists",
                    f"Experiment '{experiment_id}' already has {existing_count} records.\n\n"
                    "Replace existing data with new ingestion?\n\n"
                    "Yes = Delete old data and reload\n"
                    "No = Cancel operation"
                )
                if not response:
                    self.log_progress("Operation cancelled by user")
                    return
                
                # Delete old data
                self.log_progress(f"Deleting existing {existing_count} records for experiment '{experiment_id}'...")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM measurements WHERE experiment_id = ?",
                    (experiment_id,)
                )
                conn.commit()
                conn.close()
                self.log_progress(f"✓ Deleted {existing_count} old records")
            
            # Step 3: Ingest experiment
            self.log_progress(f"Starting ingestion: {experiment_name}")
            self.log_progress(f"Experiment ID: {experiment_id}")
            
            # Capture ingestion output
            import sys
            from io import StringIO
            
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            try:
                dataset = ingest_experiment(
                    db_path=db_path,
                    experiment_id=experiment_id,
                    experiment_name=experiment_name,
                    excel_file=excel_file,
                    transmission_folder=transmission_folder
                )
            finally:
                sys.stdout = old_stdout
                output = captured_output.getvalue()
            
            # Log the output
            for line in output.split('\n'):
                if line.strip():
                    self.log_progress(line.strip())
            
            # Step 4: Display summary and validation
            self.log_progress("Generating summary...")
            self.display_summary(db_path, experiment_id, dataset)
            
            self.log_progress("✓ INGESTION COMPLETE")
            messagebox.showinfo(
                "Success",
                f"Successfully ingested {len(dataset)} measurements for experiment '{experiment_name}'"
            )
            
        except Exception as e:
            self.log_progress(f"ERROR: {str(e)}", tag="error")
            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
            
        finally:
            # Re-enable button
            self.ingest_btn.config(state=tk.NORMAL, text="Ingest Experiment")
    
    def display_summary(self, db_path, experiment_id, dataset):
        """Display detailed summary of ingested data."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        # Header
        self.results_text.insert(tk.END, "="*80 + "\n")
        self.results_text.insert(tk.END, "INGESTION SUMMARY & VALIDATION\n")
        self.results_text.insert(tk.END, "="*80 + "\n\n")
        
        # Experiment info
        self.results_text.insert(tk.END, f"Experiment ID: {experiment_id}\n")
        self.results_text.insert(tk.END, f"Total Records: {len(dataset):,}\n\n")
        
        # Chemical system
        surfactant = dataset['surfactant_name'].iloc[0]
        polymer = dataset['polymer_name'].iloc[0]
        water_hardness = float(dataset['water_hardness_gpg'].iloc[0]) if 'water_hardness_gpg' in dataset.columns else 7.0
        self.results_text.insert(tk.END, f"Chemical System:\n")
        self.results_text.insert(tk.END, f"  Surfactant: {surfactant}\n")
        self.results_text.insert(tk.END, f"  Polymer: {polymer}\n")
        self.results_text.insert(tk.END, f"  Water Hardness: {water_hardness} gpg\n\n")
        
        # Concentration ranges
        self.results_text.insert(tk.END, f"Concentration Ranges:\n")
        self.results_text.insert(tk.END, f"  {surfactant}: {float(dataset['surfactant_pct'].min()):.4f} - {float(dataset['surfactant_pct'].max()):.4f} wt%\n")
        self.results_text.insert(tk.END, f"  {polymer}: {float(dataset['polymer_pct'].min()):.4f} - {float(dataset['polymer_pct'].max()):.4f} wt%\n\n")
        
        # Transmission range
        self.results_text.insert(tk.END, f"Transmission Range: {float(dataset['transmission_pct'].min()):.2f} - {float(dataset['transmission_pct'].max()):.2f}%\n\n")
        
        # Timepoints
        timepoints = sorted(dataset['timepoint_minutes'].unique())
        self.results_text.insert(tk.END, f"Timepoints ({len(timepoints)}): ")
        self.results_text.insert(tk.END, ", ".join([f"{t:.2f}" for t in timepoints]) + " minutes\n\n")
        
        # Plate/well info
        unique_wells = dataset[['plate', 'well']].drop_duplicates()
        self.results_text.insert(tk.END, f"Unique Wells: {len(unique_wells)} ({unique_wells['plate'].value_counts().to_dict()})\n\n")
        
        # Sample data validation
        self.results_text.insert(tk.END, "-"*80 + "\n")
        self.results_text.insert(tk.END, "SAMPLE DATA (First 5 Records):\n")
        self.results_text.insert(tk.END, "-"*80 + "\n\n")
        
        # Select columns to display
        display_cols = [
            'plate', 'well', 'timepoint_minutes',
            'surfactant_pct', 'polymer_pct', 'transmission_pct'
        ]
        
        sample_data = dataset[display_cols].head(5)
        
        # Format as table
        col_widths = {col: max(len(col), 12) for col in display_cols}
        
        # Header
        header = " | ".join([col.ljust(col_widths[col]) for col in display_cols])
        self.results_text.insert(tk.END, header + "\n")
        self.results_text.insert(tk.END, "-" * len(header) + "\n")
        
        # Rows
        for _, row in sample_data.iterrows():
            row_str = " | ".join([
                str(row[col])[:col_widths[col]].ljust(col_widths[col]) 
                for col in display_cols
            ])
            self.results_text.insert(tk.END, row_str + "\n")
        
        self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
        
        # Data quality checks
        self.results_text.insert(tk.END, "DATA QUALITY CHECKS:\n")
        self.results_text.insert(tk.END, "="*80 + "\n\n")
        
        # Check 1: Valid transmission values
        try:
            trans_numeric = pd.to_numeric(dataset['transmission_pct'], errors='coerce')
            invalid_trans = dataset[(trans_numeric < 0) | (trans_numeric > 100)]
            if len(invalid_trans) == 0:
                self.results_text.insert(tk.END, "✓ All transmission values are valid (0-100%)\n")
            else:
                self.results_text.insert(tk.END, f"✗ Found {len(invalid_trans)} invalid transmission values\n")
        except Exception as e:
            self.results_text.insert(tk.END, f"! Could not validate transmission values: {e}\n")
        
        # Check 2: Valid concentrations
        try:
            surf_numeric = pd.to_numeric(dataset['surfactant_pct'], errors='coerce')
            poly_numeric = pd.to_numeric(dataset['polymer_pct'], errors='coerce')
            invalid_conc = dataset[(surf_numeric < 0) | (poly_numeric < 0)]
            if len(invalid_conc) == 0:
                self.results_text.insert(tk.END, "✓ All concentration values are valid (>= 0)\n")
            else:
                self.results_text.insert(tk.END, f"✗ Found {len(invalid_conc)} invalid concentrations\n")
        except Exception as e:
            self.results_text.insert(tk.END, f"! Could not validate concentrations: {e}\n")
        
        # Check 3: No null values in critical columns
        null_check_cols = ['well', 'timepoint_minutes', 'transmission_pct', 'surfactant_pct', 'polymer_pct']
        null_counts = dataset[null_check_cols].isnull().sum()
        if null_counts.sum() == 0:
            self.results_text.insert(tk.END, "✓ No missing values in critical columns\n")
        else:
            self.results_text.insert(tk.END, "✗ Missing values detected:\n")
            for col, count in null_counts[null_counts > 0].items():
                self.results_text.insert(tk.END, f"  {col}: {count}\n")
        
        # Check 4: Consistent measurements per well
        measurements_per_well = dataset.groupby(['plate', 'well']).size()
        if measurements_per_well.nunique() == 1:
            self.results_text.insert(tk.END, f"✓ Consistent measurements per well ({measurements_per_well.iloc[0]} timepoints each)\n")
        else:
            self.results_text.insert(tk.END, f"! Variable measurements per well (range: {measurements_per_well.min()}-{measurements_per_well.max()})\n")
        
        self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
        
        self.results_text.config(state=tk.DISABLED)
        
    def view_database(self):
        """Display overall database statistics."""
        db_path = self.db_path.get()
        
        if not Path(db_path).exists():
            messagebox.showwarning("Database Not Found", f"Database file does not exist:\n{db_path}")
            return
        
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        try:
            conn = sqlite3.connect(db_path)
            
            # Total records
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM measurements")
            total_records = cursor.fetchone()[0]
            
            self.results_text.insert(tk.END, "="*80 + "\n")
            self.results_text.insert(tk.END, "DATABASE STATISTICS\n")
            self.results_text.insert(tk.END, "="*80 + "\n\n")
            self.results_text.insert(tk.END, f"Database: {db_path}\n")
            self.results_text.insert(tk.END, f"Total Records: {total_records:,}\n\n")
            
            if total_records > 0:
                # Experiments with water hardness
                # Check if water_hardness_gpg column exists
                cursor.execute("PRAGMA table_info(measurements)")
                columns = [col[1] for col in cursor.fetchall()]
                has_hardness = 'water_hardness_gpg' in columns
                
                if has_hardness:
                    df = pd.read_sql_query(
                        "SELECT experiment_id, experiment_name, "
                        "MAX(water_hardness_gpg) as water_hardness, COUNT(*) as records "
                        "FROM measurements GROUP BY experiment_id, experiment_name",
                        conn
                    )
                else:
                    df = pd.read_sql_query(
                        "SELECT experiment_id, experiment_name, COUNT(*) as records "
                        "FROM measurements GROUP BY experiment_id, experiment_name",
                        conn
                    )
                
                self.results_text.insert(tk.END, f"Experiments ({len(df)}):\n")
                self.results_text.insert(tk.END, "-"*80 + "\n")
                for _, row in df.iterrows():
                    hardness_str = f" [{float(row['water_hardness'])} gpg]" if has_hardness and 'water_hardness' in row else ""
                    self.results_text.insert(tk.END, f"  {row['experiment_id']}{hardness_str}: {row['experiment_name']} ({row['records']:,} records)\n")
                
                self.results_text.insert(tk.END, "\n")
                
                # Chemical systems
                systems = pd.read_sql_query(
                    "SELECT DISTINCT surfactant_name, polymer_name, COUNT(*) as records "
                    "FROM measurements GROUP BY surfactant_name, polymer_name",
                    conn
                )
                
                self.results_text.insert(tk.END, f"Chemical Systems ({len(systems)}):\n")
                self.results_text.insert(tk.END, "-"*80 + "\n")
                for _, row in systems.iterrows():
                    self.results_text.insert(tk.END, f"  {row['surfactant_name']} + {row['polymer_name']} ({row['records']:,} records)\n")
            
            self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
            
            conn.close()
            
        except Exception as e:
            self.results_text.insert(tk.END, f"Error reading database: {str(e)}\n")
        
        self.results_text.config(state=tk.DISABLED)
    
    def delete_experiment(self):
        """Delete an experiment from the database."""
        db_path = self.db_path.get()
        
        if not Path(db_path).exists():
            messagebox.showwarning("Database Not Found", f"Database file does not exist:\n{db_path}")
            return
        
        # Get list of experiments
        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(
                "SELECT experiment_id, experiment_name, COUNT(*) as records "
                "FROM measurements GROUP BY experiment_id, experiment_name",
                conn
            )
            conn.close()
            
            if len(df) == 0:
                messagebox.showinfo("No Data", "Database is empty.")
                return
            
            # Create selection dialog
            delete_window = tk.Toplevel(self.root)
            delete_window.title("Delete Experiment")
            delete_window.geometry("600x400")
            delete_window.configure(bg=self.BG_DARK)
            
            tk.Label(
                delete_window,
                text="Select Experiment(s) to Delete",
                font=('Segoe UI', 14, 'bold'),
                bg=self.BG_DARK,
                fg=self.ACCENT_RED
            ).pack(pady=10)
            
            tk.Label(
                delete_window,
                text="⚠️ WARNING: This action cannot be undone!",
                font=('Segoe UI', 10),
                bg=self.BG_DARK,
                fg=self.ACCENT_ORANGE
            ).pack(pady=5)
            
            # Listbox frame
            list_frame = tk.Frame(delete_window, bg=self.BG_MEDIUM)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Scrollbar
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Listbox with checkboxes (using Listbox with MULTIPLE selection)
            listbox = tk.Listbox(
                list_frame,
                font=('Consolas', 9),
                bg=self.BG_LIGHT,
                fg=self.FG_PRIMARY,
                selectmode=tk.MULTIPLE,
                selectbackground=self.ACCENT_RED,
                yscrollcommand=scrollbar.set,
                relief=tk.FLAT
            )
            listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Populate listbox
            for _, row in df.iterrows():
                text = f"{row['experiment_id']}: {row['experiment_name']} ({row['records']:,} records)"
                listbox.insert(tk.END, text)
            
            # Button frame
            btn_frame = tk.Frame(delete_window, bg=self.BG_DARK)
            btn_frame.pack(fill=tk.X, padx=20, pady=10)
            
            def do_delete():
                selected = listbox.curselection()
                if not selected:
                    messagebox.showwarning("No Selection", "Please select at least one experiment to delete.")
                    return
                
                exp_ids = [df.iloc[i]['experiment_id'] for i in selected]
                exp_names = [df.iloc[i]['experiment_id'] for i in selected]
                
                confirm = messagebox.askyesno(
                    "Confirm Deletion",
                    f"Delete {len(exp_ids)} experiment(s)?\n\n" + "\n".join(exp_names) + "\n\nThis cannot be undone!"
                )
                
                if not confirm:
                    return
                
                # Delete experiments
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                total_deleted = 0
                
                for exp_id in exp_ids:
                    cursor.execute("DELETE FROM measurements WHERE experiment_id = ?", (exp_id,))
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    self.log_progress(f"Deleted experiment '{exp_id}': {deleted} records")
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Deleted {total_deleted} records from {len(exp_ids)} experiment(s)")
                delete_window.destroy()
                
                # Refresh database view
                self.view_database()
            
            tk.Button(
                btn_frame,
                text="Delete Selected",
                font=('Segoe UI', 11, 'bold'),
                bg=self.ACCENT_RED,
                fg=self.FG_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                command=do_delete,
                padx=30,
                pady=10
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            tk.Button(
                btn_frame,
                text="Cancel",
                font=('Segoe UI', 10),
                bg=self.BG_LIGHT,
                fg=self.FG_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                command=delete_window.destroy,
                padx=20,
                pady=10
            ).pack(side=tk.LEFT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load experiments:\n{str(e)}")


def main():
    """Launch the GUI application."""
    root = tk.Tk()
    app = DarkThemedGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
