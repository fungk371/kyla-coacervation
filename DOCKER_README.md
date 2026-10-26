# Phase Diagram Database - Docker Web Application

This is the **containerized web version** of the Phase Diagram Database System. It uses the **exact same validated data extraction, processing, and analysis code** as the desktop GUI versions, with only the interface changed to a web-based application.

## What's Different?

- **Interface**: Web browser with tabbed navigation instead of Tkinter GUI
- **Platform**: Runs in Docker container for easy deployment
- **Core Logic**: **100% IDENTICAL** - all data extraction, parsing, database, and analysis functions are unchanged

## Features

### 📊 Data Ingestion Tab
- Upload and ingest experiments
- Auto-generation of experiment IDs and names
- Auto-detection of water hardness from filenames
- Metadata extraction preview before ingestion

### 🔬 Phase Analysis Tab
- Generate 4-panel phase diagrams (same as analyze_gui.py)
- Continuous transmission maps
- Three-phase classification
- Binary phase boundaries
- Kinetic analysis with equilibrium determination
- Interactive experiment and timepoint selection
- Adjustable phase thresholds

### 🔍 Data Query Tab
- Filter and export data by experiment, surfactant, polymer, timepoint, water hardness
- CSV download of query results

## Prerequisites

- Docker Desktop for Windows
- Docker Compose (included with Docker Desktop)

## Quick Start

### 1. Build and Start the Container

Open PowerShell in this directory and run:

```powershell
docker-compose up --build
```

First time build will take a few minutes to install dependencies.

### 2. Access the Web Interface

Open your browser and go to:

```
http://localhost:5003
```

### 3. Use the Application

The web interface provides streamlined data ingestion:

1. **Automatic Database Setup** - Existing database is pre-loaded in the container
2. **Auto-Generated Metadata** - No manual entry needed:
   - **Experiment ID**: Generated from timestamp + surfactant + polymer + water hardness
   - **Experiment Name**: Generated from surfactant-polymer combination
   - **Water Hardness**: Auto-detected from filenames (e.g., "7gpg" or "0gpg")
3. **Simple File Upload** - Just select Excel design file and transmission data files
4. **Query Data** - Filter and export data as CSV

**Upload Process:**
1. Select your Excel design file
2. The system automatically detects surfactant, polymer, and water hardness
3. Select your transmission data files
4. Click "Ingest Experiment" - ID and name are generated automatically

### 4. Stop the Container

Press `Ctrl+C` in the terminal, or run:

```powershell
docker-compose down
```

## Data Persistence

The existing `phase_diagrams.db` is copied into the container at build time and mounted to the `./data` directory on your host machine. This means:

- **Pre-loaded Data**: Your existing database with all experiments is immediately available
- **Persistent Storage**: New experiments are saved to `./data/phase_diagrams.db` on your host machine
- **Data Safety**: Your data persists even if you stop/restart the container
- **Easy Backup**: Simply backup the `./data` folder
- **Direct Access**: You can access `phase_diagrams.db` directly from your host machine for analysis

**Important**: The container uses `/app/data/phase_diagrams.db` internally, which is mapped to `./data/phase_diagrams.db` on your host.

## Development Mode

To run with live code reload (for development):

1. Edit `docker-compose.yml` and uncomment these lines:
   ```yaml
   volumes:
     - .:/app
   command: flask run --host=0.0.0.0 --port=5000 --reload
   ```

2. Restart the container:
   ```powershell
   docker-compose down
   docker-compose up
   ```

Now code changes will automatically reload the app.

## Architecture

### Files That Are IDENTICAL (Core Logic)
- `ingest_experiment.py` - All data extraction and parsing functions
- `schema.py` - Database schema and creation
- `phase_plotting.py` - Plotting functions (if used)

### Files That Are NEW (Web Interface Only)
- `app.py` - Flask web application (wraps existing functions)
- `templates/index.html` - Web UI
- `static/style.css` - Dark theme styling
- `Dockerfile` - Container definition
- `docker-compose.yml` - Easy deployment configuration

### How It Works

```
Browser → Flask (app.py) → EXISTING functions (ingest_experiment.py, schema.py)
```

The Flask app simply:
1. Receives file uploads via HTTP
2. Saves them temporarily
3. Calls the **exact same** `ingest_experiment()` function
4. Returns results to the browser

**NO changes** were made to:
- Excel parsing logic
- Transmission file parsing
- Water hardness extraction
- Well ID assignment
- Concentration calculations
- Database insertion

## Troubleshooting

### Port Already in Use

If port 5003 is already in use, edit `docker-compose.yml`:

```yaml
ports:
  - "5004:5003"  # Change 5004 to any available port
```

### Container Won't Start

Check logs:
```powershell
docker-compose logs
```

### Database Permission Issues

Ensure the `./data` directory exists and is writable:
```powershell
mkdir data
```

### Rebuild After Code Changes

If you modify any Python files:
```powershell
docker-compose down
docker-compose up --build
```

## Production Deployment

The container uses **Gunicorn** as the production WSGI server with:
- 2 worker processes
- 300 second timeout (for large file uploads)
- Automatic worker restart on failure

For production on a server, consider:
- Using HTTPS (add nginx reverse proxy)
- Increasing worker count based on CPU cores
- Setting up regular database backups
- Adding authentication (currently open access)

## Validation

All core functions are **unchanged and validated**. The web interface has been enhanced to:
- **Auto-generate experiment IDs** from timestamp, surfactant, polymer, and water hardness
- **Auto-generate experiment names** from surfactant-polymer combinations
- **Auto-detect water hardness** from filenames using the validated extraction function
- Correctly extract surfactant and polymer names from Excel files
- Parse Excel files identically to the GUI version
- Handle transmission files with UTF-16 encoding
- Assign well IDs in column-wise order
- Calculate concentrations accurately

All auto-generation features use the **same validated extraction functions** (`extract_water_hardness_from_filename`, `extract_surfactant_polymer_names`, etc.)

## Support

If you encounter any issues with the **core data processing**, they should be identical to the desktop GUI version since they use the same code.

If you encounter issues with the **web interface** (file uploads, display, etc.), check:
1. Browser console for JavaScript errors
2. Docker logs for Python errors
3. File size limits (100MB max by default)
