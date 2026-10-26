"""
Flask Web Application for Phase Diagram Database System
Uses EXACT same core functions from existing validated code.
Only the interface layer is web-based.

This app includes:
1. Data Ingestion Tab - Upload and ingest experiments
2. Phase Analysis Tab - Visualize and analyze phase diagrams
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
from pathlib import Path
import sqlite3
from werkzeug.utils import secure_filename
import tempfile
import shutil
import traceback
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for web
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import io
import base64

# Import EXISTING validated functions - NO CHANGES to core logic
from schema import create_database
from ingest_experiment import (
    ingest_experiment, 
    query_experiment, 
    extract_surfactant_polymer_names, 
    extract_water_hardness_from_filename
)
from phase_plotting import create_phase_diagram_grids, GP_AVAILABLE

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Database path - check both locations
DB_PATH = '/app/data/phase_diagrams.db'
if not os.path.exists(DB_PATH):
    DB_PATH = 'phase_diagrams.db'  # Fallback for local development


def extract_names_with_debug(solutions_df):
    """
    Wrapper around extract_surfactant_polymer_names that adds debug logging.
    Does not modify the validated function.
    
    Args:
        solutions_df: DataFrame with 'Solution' and 'Description' columns
        
    Returns:
        tuple: (surfactant_name, cosurfactant_name, polymer_name)
    """
    print("\n=== DEBUG: Extracting names from Test Solutions ===")
    print(f"Solutions DataFrame shape: {solutions_df.shape}")
    print(f"Columns: {solutions_df.columns.tolist()}")
    
    # Show all rows for debugging
    for idx, row in solutions_df.iterrows():
        sol_id = str(row['Solution'])
        desc = str(row.get('Description', 'NO_DESC_COLUMN'))
        print(f"  Row {idx}: Solution='{sol_id}' (upper='{sol_id.upper()}'), Description='{desc}'")
    
    # Call the EXISTING validated function (no modifications)
    result = extract_surfactant_polymer_names(solutions_df)
    
    print(f"=== Extracted: Surfactant={result[0]}, CoSurfactant={result[1]}, Polymer={result[2]} ===\n")
    return result


def generate_experiment_names(surfactant_name, cosurfactant_name, polymer_name, water_hardness, 
                            solutions_df, volumes_df, excel_path):
    """
    Helper function to generate experiment ID and name.
    Handles both old experiment types (surfactant + polymer) and new types (with co-surfactants).
    For co-surfactant experiments, calculates the ratio from actual well compositions.
    
    Args:
        surfactant_name: Primary surfactant name or None
        cosurfactant_name: Co-surfactant name or None
        polymer_name: Polymer name or None
        water_hardness: Water hardness in gpg
        solutions_df: DataFrame with solution concentrations
        volumes_df: DataFrame with volumes dispensed in wells
        excel_path: Path to Excel file (for using existing functions)
        
    Returns:
        tuple: (experiment_id, experiment_name)
    """
    from datetime import datetime
    from ingest_experiment import normalize_column_names, normalize_solution_ids, read_compositions
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Calculate surfactant:cosurfactant ratio from actual well compositions
    surf_cosurf_ratio = None
    if surfactant_name and cosurfactant_name:
        try:
            # Use the EXISTING validated function to get compositions
            compositions = read_compositions(excel_path)
            
            print(f"DEBUG: Compositions dataframe columns: {compositions.columns.tolist()}")
            print(f"DEBUG: Surfactant column stats:")
            print(f"  surfactant_pct: min={compositions['surfactant_pct'].min():.4f}, max={compositions['surfactant_pct'].max():.4f}, median={compositions['surfactant_pct'].median():.4f}")
            print(f"DEBUG: Cosurfactant column stats:")
            print(f"  cosurfactant_pct: min={compositions['cosurfactant_pct'].min():.4f}, max={compositions['cosurfactant_pct'].max():.4f}, median={compositions['cosurfactant_pct'].median():.4f}")
            
            # Calculate the ratio from actual well compositions
            # Use median values to avoid outliers
            surf_pct_median = compositions['surfactant_pct'].median()
            cosurf_pct_median = compositions['cosurfactant_pct'].median()
            
            print(f"DEBUG: Well compositions - Median Surf={surf_pct_median:.4f}%, Median Cosurf={cosurf_pct_median:.4f}%")
            
            # Calculate ratio as percentages (e.g., 50/50, 75/25, 100/0)
            # Based on anionic (surf) to cationic (cosurf) ratio
            if surf_pct_median > 0 and cosurf_pct_median > 0:
                total = surf_pct_median + cosurf_pct_median
                surf_pct = round((surf_pct_median / total) * 100)
                cosurf_pct = round((cosurf_pct_median / total) * 100)
                surf_cosurf_ratio = f"{surf_pct}/{cosurf_pct}"
            elif surf_pct_median > 0:
                surf_cosurf_ratio = "100/0"
            elif cosurf_pct_median > 0:
                surf_cosurf_ratio = "0/100"
            else:
                # Both are zero - something is wrong
                surf_cosurf_ratio = "?/?"
                print(f"WARNING: Both surf and cosurf medians are 0!")
                
            print(f"DEBUG: Ratio from well compositions: {surf_cosurf_ratio} (Anionic/Cationic)")
        except Exception as e:
            print(f"Warning: Could not calculate surf:cosurf ratio from wells: {e}")
            import traceback
            traceback.print_exc()
    elif surfactant_name and not cosurfactant_name:
        # No co-surfactant detected - this is a surfactant-only experiment
        print(f"DEBUG: No co-surfactant detected, skipping ratio calculation")
        surf_cosurf_ratio = None
    
    # Build name components
    components = []
    id_components = []
    
    # Surfactant and co-surfactant (possibly with ratio)
    if surfactant_name and cosurfactant_name and surf_cosurf_ratio is not None:
        components.append(f"{surfactant_name}-{cosurfactant_name} {surf_cosurf_ratio}")
        id_components.append(surfactant_name.replace(' ', '_')[:10])
        id_components.append(cosurfactant_name.replace(' ', '_')[:10])
        # For ID, replace / with "to" (e.g., "66/34" becomes "66to34")
        id_components.append(surf_cosurf_ratio.replace('/', 'to').replace(':', 'to'))
    elif surfactant_name and cosurfactant_name:
        # No ratio available, just list both
        components.append(f"{surfactant_name}-{cosurfactant_name}")
        id_components.append(surfactant_name.replace(' ', '_')[:10])
        id_components.append(cosurfactant_name.replace(' ', '_')[:10])
    elif surfactant_name:
        components.append(surfactant_name)
        id_components.append(surfactant_name.replace(' ', '_')[:10])
        components.append(surfactant_name)
        id_components.append(surfactant_name.replace(' ', '_')[:10])
    
    # Polymer
    if polymer_name:
        components.append(polymer_name)
        id_components.append(polymer_name.replace(' ', '_')[:10])
    
    # If we have no components at all, use placeholder
    if not components:
        components = ['Unknown']
        id_components = ['UNK']
    
    # Build experiment_id: timestamp + components + hardness
    experiment_id = f"{timestamp}_{'_'.join(id_components)}_{int(water_hardness)}gpg"
    
    # Build experiment_name: descriptive with hardness
    experiment_name = f"{' - '.join(components)} ({water_hardness}gpg)"
    
    return experiment_id, experiment_name


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/create_database', methods=['POST'])
def api_create_database():
    """Create new database"""
    try:
        create_database(DB_PATH)
        return jsonify({
            'success': True,
            'message': f'Database created successfully at {DB_PATH}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/check_database', methods=['GET'])
def api_check_database():
    """Check if database exists and get stats"""
    if not os.path.exists(DB_PATH):
        return jsonify({
            'exists': False,
            'message': 'Database does not exist. Please create it first.',
            'db_path': DB_PATH
        })
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM measurements")
        row_count = cursor.fetchone()[0]
        
        # Get experiment count
        cursor.execute("SELECT COUNT(DISTINCT experiment_id) FROM measurements")
        exp_count = cursor.fetchone()[0]
        
        # Get list of experiments
        cursor.execute("""
            SELECT DISTINCT experiment_id, experiment_name, 
                   COUNT(*) as measurements,
                   MIN(date_created) as date_created,
                   MAX(water_hardness_gpg) as water_hardness
            FROM measurements 
            GROUP BY experiment_id, experiment_name
            ORDER BY date_created DESC
        """)
        experiments = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'exists': True,
            'db_path': DB_PATH,
            'row_count': row_count,
            'experiment_count': exp_count,
            'experiments': [
                {
                    'id': exp[0],
                    'name': exp[1],
                    'measurements': exp[2],
                    'date': exp[3],
                    'water_hardness': exp[4]
                }
                for exp in experiments
            ]
        })
    except Exception as e:
        return jsonify({
            'exists': True,
            'db_path': DB_PATH,
            'error': str(e)
        }), 500


@app.route('/api/extract_metadata', methods=['POST'])
def api_extract_metadata():
    """Extract surfactant/polymer names and water hardness from uploaded file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        file_type = request.form.get('file_type', 'excel')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        result = {'filename': filename}
        
        # Extract water hardness from filename (EXISTING validated function)
        water_hardness = extract_water_hardness_from_filename(filename)
        result['water_hardness'] = water_hardness
        
        # If Excel file, extract surfactant/polymer names (EXISTING validated function)
        if file_type == 'excel':
            try:
                solutions_df = pd.read_excel(filepath, sheet_name='Test Solutions')
                surf_name, poly_name = extract_surfactant_polymer_names(solutions_df)
                result['surfactant'] = surf_name
                result['polymer'] = poly_name
            except Exception as e:
                result['surfactant'] = None
                result['polymer'] = None
                result['extraction_error'] = str(e)
        
        # Clean up temp file
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/ingest_experiment', methods=['POST'])
def api_ingest_experiment():
    """Ingest experiment using EXISTING validated function"""
    try:
        # Get uploaded files first to extract metadata
        if 'excel_file' not in request.files or 'transmission_files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Both Excel file and transmission files are required'
            }), 400
        
        excel_file = request.files['excel_file']
        transmission_files = request.files.getlist('transmission_files')
        
        if excel_file.filename == '' or len(transmission_files) == 0:
            return jsonify({
                'success': False,
                'error': 'Please select all required files'
            }), 400
        
        # Create temporary directory for extraction
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Save Excel file temporarily to extract metadata
            excel_filename = secure_filename(excel_file.filename)
            excel_path = os.path.join(temp_dir, excel_filename)
            excel_file.save(excel_path)
            
            # Extract water hardness from Excel filename (EXISTING validated function)
            water_hardness = extract_water_hardness_from_filename(excel_filename)
            
            # If not found in Excel, try first transmission file
            if water_hardness == 7.0 and len(transmission_files) > 0:
                trans_filename = transmission_files[0].filename
                water_hardness = extract_water_hardness_from_filename(trans_filename)
            
            # Extract surfactant and polymer names from Excel (EXISTING validated function)
            try:
                solutions_df = pd.read_excel(excel_path, sheet_name='Test Solutions')
                # Function returns 3 values: surfactant, cosurfactant, polymer
                # Use debug wrapper to see what's being extracted
                surfactant_name, cosurfactant_name, polymer_name = extract_names_with_debug(solutions_df)
                
                # Also read volumes to calculate actual ratio in wells
                volumes_df = pd.read_excel(excel_path, sheet_name='Volumes')
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Could not extract surfactant/polymer names from Excel: {str(e)}'
                }), 400
            
            # AUTO-GENERATE experiment_id and experiment_name using helper function
            # Handles all experiment types: with/without co-surfactants, with/without names
            # Includes surfactant:cosurfactant ratio for co-surfactant experiments
            experiment_id, experiment_name = generate_experiment_names(
                surfactant_name, cosurfactant_name, polymer_name, water_hardness, 
                solutions_df, volumes_df, excel_path
            )
            
            # Log auto-generated values
            print(f"Auto-generated Experiment ID: {experiment_id}")
            print(f"Auto-generated Experiment Name: {experiment_name}")
            print(f"Auto-detected Water Hardness: {water_hardness} gpg")
            print(f"Detected: Surfactant={surfactant_name}, Co-surfactant={cosurfactant_name}, Polymer={polymer_name}")
            
            # Save transmission files in subfolder
            transmission_dir = os.path.join(temp_dir, 'transmission_data')
            os.makedirs(transmission_dir, exist_ok=True)
            
            for trans_file in transmission_files:
                if trans_file.filename:
                    trans_filename = secure_filename(trans_file.filename)
                    trans_path = os.path.join(transmission_dir, trans_filename)
                    trans_file.save(trans_path)
            
            # Call EXISTING validated ingest_experiment function
            # NO CHANGES to core logic - just passing parameters
            # Note: water_hardness is auto-detected inside ingest_experiment from filenames
            ingest_experiment(
                db_path=DB_PATH,
                experiment_id=experiment_id,
                experiment_name=experiment_name,
                excel_file=excel_path,
                transmission_folder=transmission_dir
            )
            
            return jsonify({
                'success': True,
                'message': f'Successfully ingested experiment: {experiment_name}',
                'experiment_id': experiment_id
            })
        
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/delete_experiment', methods=['POST'])
def api_delete_experiment():
    """Delete an experiment and all its measurements from the database"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        
        if not experiment_id:
            return jsonify({
                'success': False,
                'error': 'experiment_id is required'
            }), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if experiment exists and get count
        cursor.execute(
            "SELECT COUNT(*) FROM measurements WHERE experiment_id = ?",
            (experiment_id,)
        )
        count = cursor.fetchone()[0]
        
        if count == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Experiment {experiment_id} not found'
            }), 404
        
        # Delete all measurements for this experiment
        cursor.execute(
            "DELETE FROM measurements WHERE experiment_id = ?",
            (experiment_id,)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted experiment {experiment_id} ({count} measurements)'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/query_experiment', methods=['POST'])
def api_query_experiment():
    """Query experiment data using EXISTING validated function"""
    try:
        data = request.get_json()
        
        experiment_id = data.get('experiment_id')
        surfactant = data.get('surfactant')
        polymer = data.get('polymer')
        min_timepoint = data.get('min_timepoint')
        water_hardness = data.get('water_hardness')
        
        # Call EXISTING validated query_experiment function
        result_df = query_experiment(
            db_path=DB_PATH,
            experiment_id=experiment_id if experiment_id else None,
            surfactant=surfactant if surfactant else None,
            polymer=polymer if polymer else None,
            min_timepoint=float(min_timepoint) if min_timepoint else None,
            water_hardness=float(water_hardness) if water_hardness else None
        )
        
        if result_df.empty:
            return jsonify({
                'success': True,
                'row_count': 0,
                'message': 'No data found matching criteria'
            })
        
        # Save to temporary CSV for download
        temp_csv = os.path.join(tempfile.gettempdir(), f'query_result_{experiment_id or "all"}.csv')
        result_df.to_csv(temp_csv, index=False)
        
        return jsonify({
            'success': True,
            'row_count': len(result_df),
            'columns': list(result_df.columns),
            'preview': result_df.head(10).to_dict('records'),
            'download_url': '/api/download_csv'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/download_csv', methods=['GET'])
def api_download_csv():
    """Download last query result as CSV"""
    try:
        # This is a simplified version - in production you'd track per-user temp files
        csv_files = [f for f in os.listdir(tempfile.gettempdir()) if f.startswith('query_result_')]
        if not csv_files:
            return jsonify({'error': 'No query results available for download'}), 404
        
        # Get most recent
        latest_csv = max([os.path.join(tempfile.gettempdir(), f) for f in csv_files], 
                        key=os.path.getctime)
        
        return send_file(latest_csv, as_attachment=True, download_name='query_results.csv')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ANALYSIS ENDPOINTS - Using EXACT functions from analyze_gui.py
# ============================================================================

@app.route('/api/analysis/get_experiments', methods=['GET'])
def api_get_experiments():
    """Get list of experiments for analysis"""
    if not os.path.exists(DB_PATH):
        return jsonify({
            'success': False,
            'error': 'Database not found'
        }), 404
    
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT DISTINCT experiment_id, experiment_name, 
                   surfactant_name, polymer_name,
                   water_hardness_gpg,
                   COUNT(*) as records
            FROM measurements
            GROUP BY experiment_id, experiment_name, surfactant_name, polymer_name, water_hardness_gpg
            ORDER BY experiment_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        experiments = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'experiments': experiments
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analysis/get_timepoints', methods=['POST'])
def api_get_timepoints():
    """Get timepoints for a specific experiment"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        
        if not experiment_id:
            return jsonify({'success': False, 'error': 'experiment_id required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT DISTINCT timepoint_minutes, COUNT(*) as wells
            FROM measurements
            WHERE experiment_id = ?
            GROUP BY timepoint_minutes
            ORDER BY timepoint_minutes
        """
        
        df = pd.read_sql_query(query, conn, params=(experiment_id,))
        conn.close()
        
        timepoints = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'timepoints': timepoints
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analysis/generate_phase_diagram', methods=['POST'])
def api_generate_phase_diagram():
    """Generate phase diagram using EXACT functions from analyze_gui.py"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        timepoint = float(data.get('timepoint'))
        threshold = float(data.get('threshold', 75.0))
        
        # Load data from database (EXACT same query as analyze_gui.py)
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT *
            FROM measurements
            WHERE experiment_id = ? AND timepoint_minutes = ?
        """
        
        df = pd.read_sql_query(query, conn, params=(experiment_id, timepoint))
        conn.close()
        
        if len(df) == 0:
            return jsonify({
                'success': False,
                'error': 'No data found for selected timepoint'
            }), 404
        
        # Clean data: remove rows with NaN or Inf values
        # Note: Zero polymer is allowed (for surfactant-only experiments)
        df = df[
            (df['surfactant_pct'].notna()) & 
            (df['polymer_pct'].notna()) & 
            (df['transmission_pct'].notna()) &
            (np.isfinite(df['surfactant_pct'])) & 
            (np.isfinite(df['polymer_pct'])) & 
            (np.isfinite(df['transmission_pct']))
        ].copy()
        
        if len(df) == 0:
            return jsonify({
                'success': False,
                'error': 'No valid data after filtering'
            }), 404
        
        # For log-scale plotting, replace zero concentrations with small positive values
        MIN_CONC = 1e-4
        df.loc[df['surfactant_pct'] <= 0, 'surfactant_pct'] = MIN_CONC
        df.loc[df['polymer_pct'] <= 0, 'polymer_pct'] = MIN_CONC
        
        # Generate phase diagram using EXACT same function as GUI
        img_base64 = generate_phase_diagram_image(df, timepoint, threshold)
        
        return jsonify({
            'success': True,
            'image': img_base64
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/analysis/kinetic_analysis', methods=['POST'])
def api_kinetic_analysis():
    """Perform kinetic analysis using EXACT functions from analyze_gui.py"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        
        # Load all timepoints for this experiment (EXACT same query as GUI)
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT timepoint_minutes, transmission_pct, well, plate
            FROM measurements
            WHERE experiment_id = ?
            ORDER BY timepoint_minutes, plate, well
        """
        
        all_data = pd.read_sql_query(query, conn, params=(experiment_id,))
        conn.close()
        
        if len(all_data) < 2:
            return jsonify({
                'success': False,
                'error': 'Need at least 2 timepoints for kinetic analysis'
            }), 400
        
        # Calculate statistics per timepoint (EXACT same as GUI)
        kinetic_data = all_data.groupby('timepoint_minutes')['transmission_pct'].agg([
            ('avg_trans', 'mean'),
            ('std_trans', 'std'),
            ('min_trans', 'min'),
            ('max_trans', 'max'),
            ('n_wells', 'count')
        ]).reset_index()
        
        # Get well data for trajectories
        all_data['well_id'] = all_data['plate'].astype(str) + '-' + all_data['well']
        well_data = all_data[['well_id', 'timepoint_minutes', 'transmission_pct']].copy()
        
        # Generate kinetic analysis plot
        img_base64 = generate_kinetic_analysis_image(kinetic_data, well_data, experiment_id)
        
        return jsonify({
            'success': True,
            'image': img_base64
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/analysis/absorbance_plot', methods=['POST'])
def api_absorbance_plot():
    """Generate absorbance vs surfactant concentration plot with overlay capability"""
    try:
        data = request.get_json()
        curves = data.get('curves', [])
        
        if not curves:
            return jsonify({
                'success': False,
                'error': 'No curves specified'
            }), 400
        
        # Generate absorbance plot with all curves
        img_base64 = generate_absorbance_plot(curves)
        
        return jsonify({
            'success': True,
            'image': img_base64
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/analysis/absorbance_3d_plot', methods=['POST'])
def api_absorbance_3d_plot():
    """Generate 3D absorbance evolution plot over time"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        experiment_name = data.get('experiment_name', experiment_id)
        
        if not experiment_id:
            return jsonify({
                'success': False,
                'error': 'No experiment specified'
            }), 400
        
        # Generate 3D absorbance plot
        img_base64 = generate_absorbance_3d_plot(experiment_id, experiment_name)
        
        return jsonify({
            'success': True,
            'image': img_base64
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/analysis/transmission_plot', methods=['POST'])
def api_transmission_plot():
    """Generate traditional transmission vs surfactant concentration plot with 5 representative timepoints"""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        experiment_name = data.get('experiment_name', experiment_id)
        
        if not experiment_id:
            return jsonify({
                'success': False,
                'error': 'No experiment specified'
            }), 400
        
        # Generate transmission plot
        img_base64 = generate_transmission_plot(experiment_id, experiment_name)
        
        return jsonify({
            'success': True,
            'image': img_base64
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# EXPORT ENDPOINTS - Data export for modeling workflows
# ============================================================================

@app.route('/api/export/get_summary', methods=['GET'])
def api_export_summary():
    """Get summary of available data for export"""
    if not os.path.exists(DB_PATH):
        return jsonify({'success': False, 'error': 'Database not found'}), 404
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get overall stats
        stats_query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT experiment_id) as n_experiments,
                COUNT(DISTINCT surfactant_name) as n_surfactants,
                COUNT(DISTINCT polymer_name) as n_polymers,
                MIN(timepoint_minutes) as min_time,
                MAX(timepoint_minutes) as max_time
            FROM measurements
        """
        stats = pd.read_sql_query(stats_query, conn).iloc[0].to_dict()
        
        # Get list of experiments with record counts
        experiments_query = """
            SELECT 
                experiment_id, 
                experiment_name,
                surfactant_name, 
                polymer_name,
                water_hardness_gpg,
                COUNT(*) as records
            FROM measurements
            GROUP BY experiment_id, experiment_name, surfactant_name, polymer_name, water_hardness_gpg
            ORDER BY experiment_name
        """
        experiments = pd.read_sql_query(experiments_query, conn).to_dict(orient='records')
        
        # Get unique surfactants and polymers
        surfactants = pd.read_sql_query(
            "SELECT DISTINCT surfactant_name FROM measurements ORDER BY surfactant_name", conn
        )['surfactant_name'].tolist()
        
        polymers = pd.read_sql_query(
            "SELECT DISTINCT polymer_name FROM measurements ORDER BY polymer_name", conn
        )['polymer_name'].tolist()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'experiments': experiments,
            'surfactants': surfactants,
            'polymers': polymers
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export/download', methods=['POST'])
def api_export_download():
    """Export data in specified format with filters"""
    try:
        data = request.get_json()
        export_format = data.get('format', 'csv')
        experiment_ids = data.get('experiment_ids', [])  # Empty = all
        surfactants = data.get('surfactants', [])  # Filter by surfactant
        polymers = data.get('polymers', [])  # Filter by polymer
        min_timepoint = data.get('min_timepoint')
        max_timepoint = data.get('max_timepoint')
        include_derived = data.get('include_derived', True)  # Add absorbance, etc.
        
        conn = sqlite3.connect(DB_PATH)
        
        # Build query with filters
        query = "SELECT * FROM measurements WHERE 1=1"
        params = []
        
        if experiment_ids:
            placeholders = ','.join(['?' for _ in experiment_ids])
            query += f" AND experiment_id IN ({placeholders})"
            params.extend(experiment_ids)
        
        if surfactants:
            placeholders = ','.join(['?' for _ in surfactants])
            query += f" AND surfactant_name IN ({placeholders})"
            params.extend(surfactants)
        
        if polymers:
            placeholders = ','.join(['?' for _ in polymers])
            query += f" AND polymer_name IN ({placeholders})"
            params.extend(polymers)
        
        if min_timepoint is not None:
            query += " AND timepoint_minutes >= ?"
            params.append(float(min_timepoint))
        
        if max_timepoint is not None:
            query += " AND timepoint_minutes <= ?"
            params.append(float(max_timepoint))
        
        query += " ORDER BY experiment_id, timepoint_minutes, surfactant_pct, polymer_pct"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if len(df) == 0:
            return jsonify({'success': False, 'error': 'No data matches the filters'}), 404
        
        # Add derived columns for modeling
        if include_derived:
            # Absorbance: A = 2 - log10(T%)
            df['absorbance'] = df['transmission_pct'].apply(
                lambda t: 2 - np.log10(max(t, 0.01)) if pd.notna(t) and t > 0 else np.nan
            )
            # Log surfactant concentration
            df['log_surfactant_pct'] = df['surfactant_pct'].apply(
                lambda s: np.log10(s) if s > 0 else np.nan
            )
            # Surfactant to polymer ratio
            df['surf_poly_ratio'] = df.apply(
                lambda row: row['surfactant_pct'] / row['polymer_pct'] 
                if row['polymer_pct'] > 0 else np.nan, axis=1
            )
        
        # Generate file based on format
        temp_dir = tempfile.gettempdir()
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'csv':
            filename = f'phase_diagram_export_{timestamp}.csv'
            filepath = os.path.join(temp_dir, filename)
            df.to_csv(filepath, index=False)
            mimetype = 'text/csv'
            
        elif export_format == 'excel':
            filename = f'phase_diagram_export_{timestamp}.xlsx'
            filepath = os.path.join(temp_dir, filename)
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='All Data', index=False)
                
                # Add summary sheet
                summary_data = df.groupby(['experiment_name', 'surfactant_name', 'polymer_name', 'water_hardness_gpg']).agg({
                    'transmission_pct': ['count', 'mean', 'std', 'min', 'max'],
                    'timepoint_minutes': ['min', 'max', 'nunique']
                }).reset_index()
                summary_data.columns = ['_'.join(col).strip('_') for col in summary_data.columns]
                summary_data.to_excel(writer, sheet_name='Summary', index=False)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
        elif export_format == 'json':
            filename = f'phase_diagram_export_{timestamp}.json'
            filepath = os.path.join(temp_dir, filename)
            df.to_json(filepath, orient='records', indent=2)
            mimetype = 'application/json'
            
        elif export_format == 'parquet':
            filename = f'phase_diagram_export_{timestamp}.parquet'
            filepath = os.path.join(temp_dir, filename)
            df.to_parquet(filepath, index=False, engine='pyarrow')
            mimetype = 'application/octet-stream'
            
        elif export_format == 'feather':
            filename = f'phase_diagram_export_{timestamp}.feather'
            filepath = os.path.join(temp_dir, filename)
            df.to_feather(filepath)
            mimetype = 'application/octet-stream'
            
        else:
            return jsonify({'success': False, 'error': f'Unknown format: {export_format}'}), 400
        
        # Send file with proper headers
        response = send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/export/ml_ready', methods=['POST'])
def api_export_ml_ready():
    """
    Export data in ML-ready format with feature engineering.
    Creates separate feature matrix (X) and target (y) compatible with scikit-learn.
    """
    try:
        data = request.get_json()
        target_column = data.get('target', 'transmission_pct')  # What to predict
        experiment_ids = data.get('experiment_ids', [])
        time_filter = data.get('time_filter', 'equilibrium')  # 'equilibrium', 'all', or specific value
        
        conn = sqlite3.connect(DB_PATH)
        
        # Build query
        query = "SELECT * FROM measurements WHERE 1=1"
        params = []
        
        if experiment_ids:
            placeholders = ','.join(['?' for _ in experiment_ids])
            query += f" AND experiment_id IN ({placeholders})"
            params.extend(experiment_ids)
        
        if time_filter == 'equilibrium':
            # Get max timepoint per experiment
            query = f"""
                SELECT m.* FROM measurements m
                INNER JOIN (
                    SELECT experiment_id, MAX(timepoint_minutes) as max_time
                    FROM measurements
                    {'WHERE experiment_id IN (' + ','.join(['?' for _ in experiment_ids]) + ')' if experiment_ids else ''}
                    GROUP BY experiment_id
                ) t ON m.experiment_id = t.experiment_id AND m.timepoint_minutes = t.max_time
            """
            params = experiment_ids if experiment_ids else []
        elif time_filter != 'all':
            try:
                query += " AND timepoint_minutes = ?"
                params.append(float(time_filter))
            except ValueError:
                pass
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if len(df) == 0:
            return jsonify({'success': False, 'error': 'No data matches the filters'}), 404
        
        # Feature engineering for ML
        features = pd.DataFrame()
        
        # Numerical features
        features['surfactant_pct'] = df['surfactant_pct']
        features['polymer_pct'] = df['polymer_pct']
        features['log_surfactant'] = np.log10(df['surfactant_pct'].clip(lower=0.0001))
        features['log_polymer'] = np.log10(df['polymer_pct'].clip(lower=0.0001))
        features['surf_poly_ratio'] = df['surfactant_pct'] / df['polymer_pct'].clip(lower=0.0001)
        features['water_hardness_gpg'] = df['water_hardness_gpg'].fillna(0)
        features['timepoint_minutes'] = df['timepoint_minutes']
        
        # One-hot encode categorical variables
        surfactant_dummies = pd.get_dummies(df['surfactant_name'], prefix='surf')
        polymer_dummies = pd.get_dummies(df['polymer_name'], prefix='poly')
        features = pd.concat([features, surfactant_dummies, polymer_dummies], axis=1)
        
        # Target variable
        if target_column == 'transmission_pct':
            target = df['transmission_pct']
        elif target_column == 'absorbance':
            target = 2 - np.log10(df['transmission_pct'].clip(lower=0.01))
        elif target_column == 'phase_binary':
            # Binary classification: clear (>75%) vs turbid (<75%)
            target = (df['transmission_pct'] >= 75).astype(int)
        else:
            target = df[target_column]
        
        # Save to temp files
        temp_dir = tempfile.gettempdir()
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        
        # Create a zip with X and y
        import zipfile
        zip_filename = f'ml_export_{timestamp}.zip'
        zip_filepath = os.path.join(temp_dir, zip_filename)
        
        with zipfile.ZipFile(zip_filepath, 'w') as zf:
            # Features CSV
            features_csv = features.to_csv(index=False)
            zf.writestr('X_features.csv', features_csv)
            
            # Target CSV
            target_df = pd.DataFrame({'target': target, 'experiment_id': df['experiment_id']})
            target_csv = target_df.to_csv(index=False)
            zf.writestr('y_target.csv', target_csv)
            
            # Metadata JSON
            metadata = {
                'target_column': target_column,
                'n_samples': len(df),
                'n_features': len(features.columns),
                'feature_names': features.columns.tolist(),
                'time_filter': time_filter,
                'experiments_included': df['experiment_id'].unique().tolist(),
                'created': timestamp
            }
            import json
            zf.writestr('metadata.json', json.dumps(metadata, indent=2))
            
            # Example usage script
            usage_script = '''"""
Example usage of exported ML-ready data with scikit-learn
"""
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score

# Load data
X = pd.read_csv('X_features.csv')
y = pd.read_csv('y_target.csv')['target']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# For regression (predicting transmission_pct or absorbance)
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
print(f"R² Score: {r2_score(y_test, y_pred):.3f}")
print(f"RMSE: {mean_squared_error(y_test, y_pred, squared=False):.3f}")

# For classification (predicting phase_binary)
# model = RandomForestClassifier(n_estimators=100, random_state=42)
# model.fit(X_train, y_train)
# y_pred = model.predict(X_test)
# print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")

# Feature importance
importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)
print("\\nTop 10 Important Features:")
print(importance.head(10))
'''
            zf.writestr('example_usage.py', usage_script)
        
        return send_file(zip_filepath, as_attachment=True, download_name=zip_filename, 
                        mimetype='application/zip')
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# PLOTTING FUNCTIONS - Using EXACT logic from analyze_gui.py
# ============================================================================

def generate_phase_diagram_image(data, timepoint, threshold):
    """Generate phase diagram using EXACT same logic as analyze_gui.py create_alternative_phase_diagram"""
    
    # Dark theme colors (same as GUI)
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    
    fig = Figure(figsize=(14, 10))
    fig.patch.set_facecolor(BG_MEDIUM)
    
    axes = fig.subplots(2, 2)
    
    surfactant = data['surfactant_name'].iloc[0]
    polymer = data['polymer_name'].iloc[0]
    exp_name = data['experiment_name'].iloc[0]
    
    fig.suptitle(f'Phase Diagram: {exp_name}\n{surfactant}-{polymer} at {timepoint:.2f} minutes',
                 fontsize=14, fontweight='bold', color=FG_PRIMARY)
    
    # Create interpolated grid using EXACT same function and parameters as GUI
    AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
        data, n_points=800, method='gp', gp_length_scale=0.18, gaussian_sigma=6.0
    )
    
    contour_levels = [threshold]
    
    # Plot using EXACT same functions as GUI
    plot_continuous_map_web(axes[0, 0], AS_grid, PS_grid, trans_grid, data, contour_levels, surfactant, polymer, fig, BG_DARK, FG_PRIMARY, FG_SECONDARY)
    plot_three_phase_web(axes[0, 1], AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer, BG_DARK, BG_MEDIUM, FG_PRIMARY, FG_SECONDARY)
    plot_binary_boundary_web(axes[1, 0], AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer, BG_DARK, FG_PRIMARY, FG_SECONDARY, BG_MEDIUM)
    plot_statistics_web(axes[1, 1], data, threshold, BG_DARK, FG_PRIMARY, FG_SECONDARY, BG_MEDIUM)
    
    for ax in axes.flat:
        ax.set_facecolor(BG_DARK)
        ax.tick_params(colors=FG_PRIMARY)
        for spine in ax.spines.values():
            spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64


def plot_continuous_map_web(ax, AS_grid, PS_grid, trans_grid, data, levels, surf, poly, fig, BG_DARK, FG_PRIMARY, FG_SECONDARY):
    """EXACT same as analyze_gui.py plot_continuous_map"""
    from matplotlib.ticker import FixedLocator, FuncFormatter
    
    contourf_levels = np.linspace(0, 100, 21)
    contourf = ax.contourf(AS_grid, PS_grid, trans_grid, levels=contourf_levels, cmap='RdYlGn', alpha=0.8)
    
    contour_lines = ax.contour(AS_grid, PS_grid, trans_grid, levels=levels,
                   colors='black', linewidths=1.5, linestyles='-')
    ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%d%%')
    
    ax.scatter(data['surfactant_pct'], data['polymer_pct'],
               c=data['transmission_pct'], s=15, cmap='RdYlGn',
               edgecolors='black', linewidth=0.3, alpha=0.6, vmin=0, vmax=100)
    
    ax.set_xlabel(f'{surf} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel(f'{poly} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_title('Continuous Transmission Map', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.yaxis.set_major_locator(FixedLocator(y_ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    
    ax.grid(True, alpha=0.3, which='both', color=FG_SECONDARY)
    ax.minorticks_on()
    
    cbar = fig.colorbar(contourf, ax=ax)
    cbar.set_label('Transmission (%)', color=FG_PRIMARY)
    cbar.ax.yaxis.set_tick_params(color=FG_PRIMARY)
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=FG_PRIMARY)


def plot_three_phase_web(ax, AS_grid, PS_grid, trans_grid, data, threshold, surfactant, polymer, BG_DARK, BG_MEDIUM, FG_PRIMARY, FG_SECONDARY):
    """EXACT same as analyze_gui.py plot_three_phase"""
    from matplotlib.ticker import FixedLocator, FuncFormatter
    from matplotlib.patches import Patch
    
    phase_colors = ['#e74c3c', '#2ecc71']
    
    ax.contourf(AS_grid, PS_grid, trans_grid, levels=[35, threshold, 95],
               colors=phase_colors, alpha=0.7)

    ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
               colors='black', linewidths=2.5)

    data['phase'] = pd.cut(data['transmission_pct'], bins=[0, threshold, 100],
                           labels=['Precipitate', 'Clear'])

    ax.scatter(data['surfactant_pct'], data['polymer_pct'],
               c=[('#e74c3c' if p == 'Precipitate' else '#2ecc71') for p in data['phase']],
               s=20, edgecolors='black', linewidth=0.5, alpha=0.8)
    
    ax.set_xlabel(f'{surfactant} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel(f'{polymer} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_title('Three-Phase Classification', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.yaxis.set_major_locator(FixedLocator(y_ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    
    ax.grid(True, alpha=0.3, which='both', color=FG_SECONDARY)
    ax.minorticks_on()
    
    legend_elements = [Patch(facecolor='#e74c3c', edgecolor='black', label='Precipitate (<{:.0f}%)'.format(threshold)),
              Patch(facecolor='#2ecc71', edgecolor='black', label='Clear (≥{:.0f}%)'.format(threshold))]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8, 
         facecolor=BG_MEDIUM, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)


def plot_binary_boundary_web(ax, AS_grid, PS_grid, trans_grid, data, threshold, surf, poly, BG_DARK, FG_PRIMARY, FG_SECONDARY, BG_MEDIUM):
    """EXACT same as analyze_gui.py plot_binary_boundary"""
    from matplotlib.ticker import FixedLocator, FuncFormatter
    import matplotlib.patches as mpatches
    
    colors = ['#e74c3c' if t < threshold else '#2ecc71' for t in data['transmission_pct']]
    ax.scatter(data['surfactant_pct'], data['polymer_pct'],
              c=colors, s=50, edgecolors='black', linewidth=0.5, alpha=0.8)
    
    contour_thresh = ax.contour(AS_grid, PS_grid, trans_grid, levels=[threshold],
                                colors='black', linewidths=2.5, antialiased=True)
    ax.contourf(AS_grid, PS_grid, trans_grid, levels=[0, threshold, 100],
               colors=['#e74c3c', '#2ecc71'], alpha=0.15, antialiased=True)
    ax.clabel(contour_thresh, inline=True, fontsize=10, fmt=f'{threshold:.0f}%% Boundary')
    
    ax.set_xlabel(f'{surf} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel(f'{poly} Concentration (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'Binary Phase Boundary ({threshold:.0f}% Threshold)', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.yaxis.set_major_locator(FixedLocator(y_ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.3g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, p: f'{y:.3g}'))
    
    ax.grid(True, alpha=0.3, which='both', color=FG_SECONDARY)
    ax.minorticks_on()
    
    red_patch = mpatches.Patch(color='#e74c3c', label=f'2-Phase (<{threshold:.0f}%)')
    green_patch = mpatches.Patch(color='#2ecc71', label=f'1-Phase (≥{threshold:.0f}%)')
    ax.legend(handles=[red_patch, green_patch], loc='upper left', fontsize=8,
             facecolor=BG_MEDIUM, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)


def plot_statistics_web(ax, data, threshold, BG_DARK, FG_PRIMARY, FG_SECONDARY, BG_MEDIUM):
    """EXACT same as analyze_gui.py plot_statistics"""
    bins = np.arange(30, 100, 5)
    ax.hist(data['transmission_pct'], bins=bins, color='steelblue', alpha=0.7, edgecolor='black')
    
    ax.axvline(threshold, color='black', linewidth=2.5, linestyle='-', label=f'Threshold ({threshold:.0f}%)')
    
    ax.set_xlabel('Transmission (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Frequency', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax.set_title('Transmission Distribution', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax.legend(fontsize=7, facecolor=BG_MEDIUM, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax.grid(True, alpha=0.3, color=FG_SECONDARY)
    
    stats_text = f"Mean: {data['transmission_pct'].mean():.1f}%\n"
    stats_text += f"Std: {data['transmission_pct'].std():.1f}%\n"
    stats_text += f"Min: {data['transmission_pct'].min():.1f}%\n"
    stats_text += f"Max: {data['transmission_pct'].max():.1f}%"
    
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes,
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor=BG_DARK, alpha=0.8, edgecolor=FG_SECONDARY),
           color=FG_PRIMARY, family='monospace')


def generate_kinetic_analysis_image(kinetic_data, well_data, experiment_id):
    """Generate kinetic analysis using EXACT same logic as analyze_gui.py create_kinetic_analysis"""
    
    # Dark theme colors
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    
    fig = Figure(figsize=(14, 10))
    fig.patch.set_facecolor(BG_MEDIUM)
    
    axes = fig.subplots(2, 2)
    
    fig.suptitle(f'Kinetic Analysis: {experiment_id}\nEquilibrium Determination',
                 fontsize=14, fontweight='bold', color=FG_PRIMARY)
    
    # Calculate equilibrium metrics (EXACT same as GUI)
    final_avg = kinetic_data['avg_trans'].iloc[-1]
    initial_avg = kinetic_data['avg_trans'].iloc[0]
    threshold_98 = final_avg * 0.98
    
    eq_time_98 = None
    for _, row in kinetic_data.iterrows():
        if row['avg_trans'] >= threshold_98:
            eq_time_98 = row['timepoint_minutes']
            break
    
    kinetic_data['rate_of_change'] = kinetic_data['avg_trans'].diff() / kinetic_data['timepoint_minutes'].diff()
    
    # Plot 1: Mean transmission evolution (EXACT same as GUI)
    ax1 = axes[0, 0]
    ax1.plot(kinetic_data['timepoint_minutes'], kinetic_data['avg_trans'], 
            'o-', color='#2ecc71', linewidth=2, markersize=8, label='Mean Transmission')
    ax1.fill_between(kinetic_data['timepoint_minutes'],
                    kinetic_data['avg_trans'] - kinetic_data['std_trans'],
                    kinetic_data['avg_trans'] + kinetic_data['std_trans'],
                    alpha=0.3, color='#2ecc71', label='±1 Std Dev')
    
    ax1.axhline(final_avg, color='#e74c3c', linestyle='--', linewidth=2, label=f'Final Value ({final_avg:.1f}%)')
    ax1.axhline(threshold_98, color='#f39c12', linestyle=':', linewidth=2, label=f'98% of Final ({threshold_98:.1f}%)')
    
    if eq_time_98:
        ax1.axvline(eq_time_98, color='#f39c12', linestyle=':', linewidth=2, alpha=0.7)
        ax1.text(eq_time_98, ax1.get_ylim()[1]*0.95, f' t₉₈ = {eq_time_98:.1f} min',
                rotation=90, verticalalignment='top', color=FG_PRIMARY, fontweight='bold')
    
    ax1.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax1.set_ylabel('Transmission (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax1.set_title('Mean Transmission Evolution', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax1.legend(fontsize=8, facecolor=BG_MEDIUM, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax1.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax1.set_facecolor(BG_DARK)
    
    # Plot 2: Rate of change (EXACT same as GUI)
    ax2 = axes[0, 1]
    ax2.plot(kinetic_data['timepoint_minutes'].iloc[1:], kinetic_data['rate_of_change'].iloc[1:],
            'o-', color='#3498db', linewidth=2, markersize=8)
    ax2.axhline(0, color=FG_SECONDARY, linestyle='--', linewidth=1)
    
    ax2.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax2.set_ylabel('Rate of Change (%/min)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax2.set_title('Kinetic Rate Analysis', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax2.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax2.set_facecolor(BG_DARK)
    
    # Plot 3: Sample well trajectories (EXACT same as GUI)
    ax3 = axes[1, 0]
    sample_wells = well_data['well_id'].unique()[:10]
    colors = plt.cm.viridis(np.linspace(0, 1, len(sample_wells)))
    
    for well_id, color in zip(sample_wells, colors):
        well_subset = well_data[well_data['well_id'] == well_id]
        ax3.plot(well_subset['timepoint_minutes'], well_subset['transmission_pct'],
                'o-', alpha=0.6, linewidth=1.5, markersize=4, color=color, label=f'{well_id}')
    
    ax3.set_xlabel('Time (minutes)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax3.set_ylabel('Transmission (%)', fontsize=10, fontweight='bold', color=FG_PRIMARY)
    ax3.set_title('Individual Well Trajectories (Sample)', fontsize=11, fontweight='bold', color=FG_PRIMARY)
    ax3.legend(fontsize=7, ncol=2, facecolor=BG_MEDIUM, edgecolor=FG_SECONDARY, labelcolor=FG_PRIMARY)
    ax3.grid(True, alpha=0.3, color=FG_SECONDARY)
    ax3.set_facecolor(BG_DARK)
    
    # Plot 4: Summary statistics (EXACT same as GUI)
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    total_change = final_avg - initial_avg
    
    milestones = {'90%': 0.90, '95%': 0.95, '98%': 0.98, '99%': 0.99}
    milestone_times = {}
    for label, frac in milestones.items():
        threshold = initial_avg + (final_avg - initial_avg) * frac
        for _, row in kinetic_data.iterrows():
            if (total_change > 0 and row['avg_trans'] >= threshold) or \
               (total_change < 0 and row['avg_trans'] <= threshold):
                milestone_times[label] = row['timepoint_minutes']
                break
    
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
    
    summary_text += "RECOMMENDATION:\n"
    summary_text += "-"*50 + "\n"
    if eq_time_98:
        summary_text += f"✓ Use timepoints ≥ {eq_time_98:.1f} min for\n"
        summary_text += "  quasi-equilibrium phase diagrams\n"
    else:
        summary_text += "! System may not have reached equilibrium\n"
        summary_text += f"  Consider longer measurement times\n"
    
    ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
            fontsize=10, verticalalignment='top', family='monospace',
            color=FG_PRIMARY,
            bbox=dict(boxstyle='round', facecolor=BG_DARK, alpha=0.9, edgecolor=FG_SECONDARY, linewidth=2))
    
    for ax in axes.flat:
        if ax != ax4:
            ax.set_facecolor(BG_DARK)
            ax.tick_params(colors=FG_PRIMARY)
            for spine in ax.spines.values():
                spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64


def generate_absorbance_plot(curves):
    """
    Generate absorbance vs surfactant concentration plot.
    Converts transmission to absorbance, sums across all polymer concentrations
    for each surfactant level, and plots all requested curves.
    
    Args:
        curves: List of dicts with 'experiment_id', 'experiment_name', 'timepoint'
    
    Returns:
        Base64 encoded PNG image
    """
    # Dark theme colors
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    
    # Color palette for multiple curves
    COLORS = ['#4ec9b0', '#ce9178', '#569cd6', '#dcdcaa', '#c586c0', '#9cdcfe', '#4fc1ff']
    
    fig = Figure(figsize=(12, 7))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG_DARK)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Process each curve
    for idx, curve_info in enumerate(curves):
        experiment_id = curve_info['experiment_id']
        timepoint = curve_info['timepoint']
        exp_name = curve_info.get('experiment_name', experiment_id)
        
        # Query data for this curve
        query = """
            SELECT surfactant_pct, polymer_pct, transmission_pct
            FROM measurements
            WHERE experiment_id = ? AND timepoint_minutes = ?
        """
        df = pd.read_sql_query(query, conn, params=(experiment_id, timepoint))
        
        if len(df) == 0:
            continue
        
        # Data validation: filter out invalid transmission values
        # Remove NaN, zero, and negative transmission values
        df = df[df['transmission_pct'].notna()]
        df = df[df['transmission_pct'] > 0]
        
        if len(df) == 0:
            continue
        
        # Convert transmission to absorbance: A = 2 - log10(T%)
        # This assumes T% is the percent transmission (0-100)
        df['absorbance'] = 2 - np.log10(df['transmission_pct'])
        
        # Remove any inf or nan values that might result from the conversion
        df = df[np.isfinite(df['absorbance'])]
        
        if len(df) == 0:
            continue
        
        # Round surfactant_pct to 2 decimal places for proper grouping
        df['surfactant_pct_rounded'] = df['surfactant_pct'].round(2)
        
        # Compute normalized sum: mean * standard polymer levels (12)
        # This accounts for variable polymer coverage at different surfactant levels
        counts = df.groupby('surfactant_pct_rounded').size()
        absorbance_agg = df.groupby('surfactant_pct_rounded', as_index=False)['absorbance'].sum()
        STANDARD_POLYMER_LEVELS = 12
        absorbance_agg['absorbance'] = (absorbance_agg['absorbance'] / counts.loc[absorbance_agg['surfactant_pct_rounded']].values) * STANDARD_POLYMER_LEVELS
        absorbance_agg = absorbance_agg.sort_values('surfactant_pct_rounded')
        absorbance_agg = absorbance_agg.rename(columns={'surfactant_pct_rounded': 'surfactant_pct'})
        
        # Debug logging
        print(f"DEBUG: Experiment {exp_name} @ {timepoint}min")
        print(f"DEBUG: Original df shape: {df.shape}")
        print(f"DEBUG: Aggregated shape: {absorbance_agg.shape}")
        
        # Plot this curve
        color = COLORS[idx % len(COLORS)]
        label = f"{exp_name} @ {timepoint:.1f} min"
        ax.plot(absorbance_agg['surfactant_pct'], absorbance_agg['absorbance'],
                marker='o', linewidth=2, markersize=8, color=color, label=label, alpha=0.8)
    
    conn.close()
    
    # Styling
    ax.set_xlabel('Surfactant Concentration (%)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Total Absorbance (normalized)', fontsize=12, fontweight='bold', color=FG_PRIMARY)
    ax.set_title('Absorbance vs Surfactant Concentration', fontsize=14, fontweight='bold', color=FG_PRIMARY, pad=20)
    
    print("DEBUG: Setting x-axis to logarithmic scale")
    ax.set_xscale('log')
    print(f"DEBUG: X-axis scale is now: {ax.get_xscale()}")
    
    # Configure logarithmic x-axis ticks
    from matplotlib.ticker import LogLocator, FuncFormatter
    ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=15))
    ax.xaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1, numticks=100))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.2g}'))
    
    ax.grid(True, alpha=0.3, which='both', color=FG_SECONDARY, linestyle='--')
    ax.grid(True, alpha=0.15, which='minor', color=FG_SECONDARY, linestyle=':')
    ax.tick_params(colors=FG_PRIMARY, which='both')
    ax.tick_params(which='minor', labelsize=8)
    
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Legend
    if len(curves) > 0:
        legend = ax.legend(loc='best', facecolor=BG_DARK, edgecolor=FG_SECONDARY, 
                          framealpha=0.9, fontsize=10)
        plt.setp(legend.get_texts(), color=FG_PRIMARY)
    
    fig.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64


def generate_absorbance_3d_plot(experiment_id, experiment_name):
    """
    Generate heatmap showing absorbance evolution over time.
    X-axis: Surfactant concentration (log scale)
    Y-axis: Time
    Color: Total absorbance
    
    Args:
        experiment_id: The experiment ID
        experiment_name: Display name for the experiment
    
    Returns:
        Base64 encoded PNG image
    """
    # Dark theme colors
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    
    fig = Figure(figsize=(16, 10))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG_DARK)
    
    # Query all data for this experiment
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT surfactant_pct, polymer_pct, transmission_pct, timepoint_minutes
        FROM measurements
        WHERE experiment_id = ?
        ORDER BY timepoint_minutes, surfactant_pct
    """
    df = pd.read_sql_query(query, conn, params=(experiment_id,))
    conn.close()
    
    if len(df) == 0:
        raise ValueError(f"No data found for experiment {experiment_id}")
    
    # Data validation
    df = df[df['transmission_pct'].notna()]
    df = df[df['transmission_pct'] > 0]
    
    # Convert transmission to absorbance
    df['absorbance'] = 2 - np.log10(df['transmission_pct'])
    df = df[np.isfinite(df['absorbance'])]
    
    # Round surfactant concentration for proper grouping
    df['surfactant_pct_rounded'] = df['surfactant_pct'].round(6)
    
    # Group by timepoint and surfactant concentration, sum absorbances
    grouped = df.groupby(['timepoint_minutes', 'surfactant_pct_rounded'], as_index=False)['absorbance'].sum()
    
    # Pivot to create matrix for heatmap
    pivot_data = grouped.pivot(index='timepoint_minutes', columns='surfactant_pct_rounded', values='absorbance')
    
    print(f"DEBUG Heatmap: Pivot shape = {pivot_data.shape}")
    
    # Create heatmap
    im = ax.imshow(pivot_data.values, aspect='auto', cmap='viridis', interpolation='bilinear')
    
    # Set x-axis (surfactant concentrations) - use log scale positions
    surfactant_concs = pivot_data.columns.values
    n_concs = len(surfactant_concs)
    
    # Show subset of x-tick labels to avoid crowding
    tick_indices = np.linspace(0, n_concs - 1, min(10, n_concs), dtype=int)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([f'{surfactant_concs[i]:.2f}' for i in tick_indices], 
                       fontsize=12, color=FG_PRIMARY, rotation=45, ha='right')
    
    # Set y-axis (timepoints)
    timepoints = pivot_data.index.values
    n_times = len(timepoints)
    tick_indices_y = np.linspace(0, n_times - 1, min(15, n_times), dtype=int)
    ax.set_yticks(tick_indices_y)
    ax.set_yticklabels([f'{timepoints[i]:.1f}' for i in tick_indices_y], 
                       fontsize=12, color=FG_PRIMARY)
    
    # Labels and title
    ax.set_xlabel('Surfactant Concentration (%)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Time (minutes)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'Absorbance Evolution Over Time\n{experiment_name}\n(Color = Total Absorbance summed across all polymer levels)', 
                 fontsize=15, fontweight='bold', color=FG_PRIMARY, pad=20)
    
    # Colorbar
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label('Total Absorbance', color=FG_PRIMARY, fontsize=13, fontweight='bold')
    cbar.ax.tick_params(colors=FG_PRIMARY, labelsize=11)
    cbar.outline.set_edgecolor(FG_SECONDARY)
    
    # Grid for readability
    ax.set_xticks(np.arange(n_concs) - 0.5, minor=True)
    ax.set_yticks(np.arange(n_times) - 0.5, minor=True)
    ax.grid(which='minor', color=FG_SECONDARY, linestyle='-', linewidth=0.3, alpha=0.3)
    ax.tick_params(which='minor', size=0)
    
    # Style spines
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    fig.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=120)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64


def generate_transmission_plot(experiment_id, experiment_name):
    """
    Generate traditional transmission % vs surfactant concentration plot.
    Shows 5 representative timepoints on a single plot.
    This is the traditional view formulators use for phase diagram analysis.
    
    Args:
        experiment_id: Experiment identifier
        experiment_name: Display name for the experiment
    
    Returns:
        Base64 encoded PNG image
    """
    # Dark theme colors
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#2d2d2d'
    FG_PRIMARY = '#ffffff'
    FG_SECONDARY = '#b0b0b0'
    
    fig = Figure(figsize=(14, 8))
    fig.patch.set_facecolor(BG_MEDIUM)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG_DARK)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get all data for this experiment
    query = """
        SELECT surfactant_pct, timepoint_minutes, transmission_pct
        FROM measurements
        WHERE experiment_id = ?
        ORDER BY timepoint_minutes, surfactant_pct
    """
    df = pd.read_sql_query(query, conn, params=(experiment_id,))
    conn.close()
    
    if len(df) == 0:
        # Return empty plot with message
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                color=FG_PRIMARY, fontsize=16)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64
    
    # Filter invalid data
    df = df[df['transmission_pct'].notna()]
    df = df[df['transmission_pct'] >= 0]
    
    # Get unique timepoints up to 60 minutes
    timepoints = sorted([t for t in df['timepoint_minutes'].unique() if t <= 60])
    n_times = len(timepoints)
    
    # Use all timepoints up to 60 minutes
    selected_times = timepoints
    
    # Color gradient from light to dark (plasma colormap)
    colors = plt.cm.plasma(np.linspace(0.15, 0.85, len(selected_times)))
    
    # Round surfactant for grouping
    df['surfactant_pct_rounded'] = df['surfactant_pct'].round(4)
    
    # Plot each selected timepoint
    for i, t in enumerate(selected_times):
        df_t = df[df['timepoint_minutes'] == t]
        
        # Group by surfactant concentration and average transmission
        trans_curve = df_t.groupby('surfactant_pct_rounded', as_index=False)['transmission_pct'].mean()
        trans_curve = trans_curve.sort_values('surfactant_pct_rounded')
        
        if len(trans_curve) < 2:
            continue
        
        ax.plot(trans_curve['surfactant_pct_rounded'], trans_curve['transmission_pct'], 
                'o-', color=colors[i], linewidth=2, markersize=4, 
                label=f't = {t:.1f} min', alpha=0.85)
    
    # Styling
    ax.set_xscale('log')
    ax.set_xlabel('Surfactant Concentration (%)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_ylabel('Transmission (%)', fontsize=14, fontweight='bold', color=FG_PRIMARY)
    ax.set_title(f'Transmission vs Surfactant Concentration\n{experiment_name}\n(All Timepoints ≤60 min)', 
                 fontsize=14, fontweight='bold', color=FG_PRIMARY, pad=15)
    
    # Add phase region annotation line at 75% (clear/turbid transition)
    ax.axhline(y=75, color='#ff6b6b', linestyle='--', alpha=0.5, linewidth=1)
    
    # Add legend for phase interpretation
    xlim = ax.get_xlim()
    ax.text(xlim[0] * 1.2, 80, 'Clear (high T%)', color='#4fc1ff', fontsize=10, alpha=0.8)
    ax.text(xlim[0] * 1.2, 67, 'Turbid/Coacervate (low T%)', color='#ff6b6b', fontsize=10, alpha=0.8)
    
    # Configure x-axis ticks - show labels at 1, 2, 5 values per decade
    from matplotlib.ticker import LogLocator, FuncFormatter
    
    # Major ticks at 1, 2, 5 values per decade (e.g., 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0)
    ax.xaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0, 2.0, 5.0), numticks=50))
    ax.xaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(1, 10) * 0.1, numticks=100))
    
    # Custom formatter to show tick labels
    def custom_formatter(x, pos):
        if x >= 1:
            return f'{x:.0f}' if x == int(x) else f'{x:.1f}'
        elif x >= 0.1:
            return f'{x:.1f}'
        elif x >= 0.01:
            return f'{x:.2f}'
        else:
            return f'{x:.3f}'
    ax.xaxis.set_major_formatter(FuncFormatter(custom_formatter))
    
    # No labels on minor ticks
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda x, p: ''))
    
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, which='both', color=FG_SECONDARY, linestyle='--')
    ax.grid(True, alpha=0.15, which='minor', color=FG_SECONDARY, linestyle=':')
    ax.tick_params(colors=FG_PRIMARY, which='both', labelsize=11)
    
    for spine in ax.spines.values():
        spine.set_color(FG_SECONDARY)
    
    # Legend - use multiple columns for many timepoints
    n_cols = max(1, len(selected_times) // 8 + 1)
    legend = ax.legend(loc='upper right', facecolor=BG_DARK, edgecolor=FG_SECONDARY, 
                      framealpha=0.9, fontsize=9, title='Timepoint', title_fontsize=10,
                      ncol=n_cols)
    plt.setp(legend.get_texts(), color=FG_PRIMARY)
    legend.get_title().set_color(FG_PRIMARY)
    
    fig.tight_layout()
    
    # Convert to base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64


# ============================================================================
# DILUTION CURVE ENDPOINT
# ============================================================================

@app.route('/api/analysis/dilution_curves', methods=['POST'])
def api_dilution_curves():
    """Generate dilution (%T) curve analogues along fixed surfactant:polymer ratio rays."""
    try:
        data = request.get_json()
        experiment_id = data.get('experiment_id')
        timepoint = float(data.get('timepoint'))
        ratios = [float(r) for r in data.get('ratios', [8, 10, 12, 15])]

        if not experiment_id:
            return jsonify({'success': False, 'error': 'experiment_id required'}), 400

        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT surfactant_pct, polymer_pct, transmission_pct,
                   surfactant_name, polymer_name, experiment_name
            FROM measurements
            WHERE experiment_id = ? AND ABS(timepoint_minutes - ?) < 1.5
        """
        df = pd.read_sql_query(query, conn, params=(experiment_id, timepoint))
        conn.close()

        if len(df) == 0:
            return jsonify({'success': False, 'error': 'No data found for that timepoint'}), 404

        df = df[
            df['surfactant_pct'].notna() & df['polymer_pct'].notna() & df['transmission_pct'].notna() &
            np.isfinite(df['surfactant_pct']) & np.isfinite(df['polymer_pct']) & np.isfinite(df['transmission_pct']) &
            (df['surfactant_pct'] > 0) & (df['polymer_pct'] > 0)
        ].copy()

        if len(df) < 4:
            return jsonify({'success': False, 'error': 'Insufficient data points for interpolation'}), 400

        experiment_name = df['experiment_name'].iloc[0]
        surfactant_name = df['surfactant_name'].iloc[0] or 'Surfactant'
        polymer_name = df['polymer_name'].iloc[0] or 'Polymer'

        # Fit interpolator
        if GP_AVAILABLE:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF as GPKernel, WhiteKernel  # noqa: F811
            x_train = np.log10(np.vstack((df['surfactant_pct'].values, df['polymer_pct'].values)).T)
            y_train = df['transmission_pct'].values
            kernel = GPKernel(length_scale=0.18, length_scale_bounds='fixed') + WhiteKernel(
                noise_level=1.0, noise_level_bounds=(0.1, 10.0))
            gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=3, alpha=0.0, normalize_y=True)
            gp.fit(x_train, y_train)
            def predict(s_arr, p_arr):
                x = np.log10(np.vstack([s_arr, p_arr]).T)
                return gp.predict(x)
        else:
            from scipy.interpolate import griddata
            points = np.vstack((df['surfactant_pct'].values, df['polymer_pct'].values)).T
            values = df['transmission_pct'].values
            def predict(s_arr, p_arr):
                q = np.vstack([s_arr, p_arr]).T
                res = griddata(points, values, q, method='linear')
                if np.isnan(res).any():
                    near = griddata(points, values, q, method='nearest')
                    res = np.where(np.isnan(res), near, res)
                return res

        surf_min = df['surfactant_pct'].min()
        surf_max = df['surfactant_pct'].max()
        poly_min = df['polymer_pct'].min()
        poly_max = df['polymer_pct'].max()

        # Build figure
        BG_DARK = '#1e1e1e'
        BG_MEDIUM = '#2d2d2d'
        FG_PRIMARY = '#ffffff'
        FG_SECONDARY = '#b0b0b0'
        RATIO_COLORS = ['#4fc1ff', '#ff9f40', '#7bed9f', '#ff6b81']

        fig = Figure(figsize=(12, 7))
        fig.patch.set_facecolor(BG_MEDIUM)
        ax = fig.add_subplot(111)
        ax.set_facecolor(BG_DARK)

        any_plotted = False
        for color, ratio in zip(RATIO_COLORS, ratios):
            t_lo = max(surf_min, poly_min * ratio)
            t_hi = min(surf_max, poly_max * ratio)
            if t_lo >= t_hi:
                continue
            t_arr = np.logspace(np.log10(t_lo), np.log10(t_hi), 120)
            p_arr = t_arr / ratio
            trans = np.clip(predict(t_arr, p_arr), 0.0, 100.0)
            ax.plot(t_arr, trans, color=color, linewidth=2.2,
                    label=f'{ratio:.0f}:1  ({poly_min * ratio:.2f}\u2013{poly_max * ratio:.2f}% polymer)')
            any_plotted = True

        if not any_plotted:
            return jsonify({'success': False,
                            'error': 'None of the selected ratios fall within the measured concentration range'}), 400

        ax.set_xscale('log')
        ax.invert_xaxis()
        ax.set_ylim(0, 105)
        ax.set_xlabel(f'{surfactant_name} concentration (%)', fontsize=13, fontweight='bold', color=FG_PRIMARY)
        ax.set_ylabel('Transmission (%)', fontsize=13, fontweight='bold', color=FG_PRIMARY)
        ax.set_title(
            f'Dilution (\u0025T) Curve Analogues \u2014 {surfactant_name} / {polymer_name}\n'
            f'{experiment_name}  |  t \u2248 {timepoint:.1f} min  |  concentrated \u2190 dilute',
            fontsize=13, fontweight='bold', color=FG_PRIMARY, pad=12)
        ax.text(0.01, 0.97, 'concentrated', transform=ax.transAxes,
                color=FG_SECONDARY, fontsize=9, va='top')
        ax.text(0.99, 0.97, 'dilute', transform=ax.transAxes,
                color=FG_SECONDARY, fontsize=9, va='top', ha='right')
        ax.grid(True, alpha=0.25, which='both', color=FG_SECONDARY, linestyle='--')
        # set_xticks forces labels on an inverted log axis; formatters/locators
        # are silently overridden by matplotlib after invert_xaxis().
        _all_ticks = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        _x_ticks = [t for t in _all_ticks if surf_min * 0.8 <= t <= surf_max * 1.2]
        ax.set_xticks(_x_ticks)
        ax.set_xticklabels([f'{t:g}' for t in _x_ticks])
        ax.tick_params(colors=FG_PRIMARY, which='both', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(FG_SECONDARY)
        legend = ax.legend(title='Surf:Poly ratio', loc='lower right',
                           facecolor=BG_DARK, edgecolor=FG_SECONDARY, framealpha=0.9,
                           fontsize=9, title_fontsize=10)
        plt.setp(legend.get_texts(), color=FG_PRIMARY)
        legend.get_title().set_color(FG_PRIMARY)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor=BG_MEDIUM, dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return jsonify({'success': True, 'image': img_base64})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500


if __name__ == '__main__':
    # Run on all interfaces so it's accessible from host machine
    app.run(host='0.0.0.0', port=5003, debug=True)
