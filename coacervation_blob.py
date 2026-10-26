"""
Azure Blob storage + upload workflow for the coacervation platform.

Mirrors the data-storage pattern used by the sibling P&G Analytical apps
(`ap-ppt-blob-analysis` and `Ternary_Diagrams`):

  - An ``AzureBlobClient`` wrapper that reads credentials from a layered ``.env``
    search (cwd -> module dir), exposing list / download / upload / delete.
  - A single master ``CoacervationData.csv`` (well-level long table) that is
    **append-merged** on every upload so all experiments live in one queryable
    table (the "XY table" tier of the data strategy).
  - A per-sample ``CoacervationSamples.csv`` summary table (one row per trough:
    AUC, onset, fingerprint, chassis/polymer, batch id, deposition prediction).
  - A ``CoacervationManifest.json`` (one entry per experiment) that guards against
    duplicate uploads and powers the "list experiments" / "delete experiment" UI.

The module is intentionally decoupled from the Flask app: the app builds the two
DataFrames and calls :func:`merge_and_upload_experiment`.  Nothing here imports
``coacervation_app``.

Required environment variables (in a ``.env`` file next to this module or the
current working directory)::

    AZURE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;
    AZURE_BLOB_CONTAINER_NAME=coacervation-data
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

try:  # optional dependency - app still runs (storage disabled) if missing
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceExistsError
except Exception:  # pragma: no cover - import guard
    BlobServiceClient = None  # type: ignore
    ContainerClient = None  # type: ignore

    class ResourceExistsError(Exception):  # type: ignore
        pass

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore
        return False


# Blob object names (the three storage tiers, all in one container)
DATA_BLOB = "CoacervationData.csv"       # well-level long table (full curves)
SAMPLES_BLOB = "CoacervationSamples.csv"  # per-sample summary/metadata
MANIFEST_BLOB = "CoacervationManifest.json"  # one entry per experiment
PHASE_DATA_BLOB = "PhaseDiagramMeasurements.csv"
PHASE_MANIFEST_BLOB = "PhaseDiagramManifest.json"


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class AzureBlobClient:
    """Thin wrapper around a container client with layered ``.env`` loading.

    Adapted from ``ap-ppt-blob-analysis/azure_blob.py`` with upload/delete added.
    Reads ``AZURE_CONNECTION_STRING`` (or ``AZURE_STORAGE_CONNECTION_STRING``) and
    ``AZURE_BLOB_CONTAINER_NAME`` (or ``CONTAINER_NAME``).
    """

    def __init__(self) -> None:
        load_dotenv()
        module_dir = Path(__file__).resolve().parent
        cwd_dir = Path.cwd()
        for p in (cwd_dir, module_dir):
            env = p / ".env"
            if env.exists():
                # override=True so freshly-pasted .env values take effect live.
                load_dotenv(env, override=True)
        self.connection_string = (
            os.getenv("AZURE_CONNECTION_STRING")
            or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )
        # Container-level SAS URL (preferred when the account key is not shared).
        self.sas_url = os.getenv("BLOB_SAS_URL") or os.getenv("AZURE_BLOB_SAS_URL")
        self.container_name = (
            os.getenv("AZURE_BLOB_CONTAINER_NAME") or os.getenv("CONTAINER_NAME")
        )
        self.auth_mode = None
        self._cc = None
        self.blob_service_client = None
        # Prefer a container SAS URL: scoped, no account key, can't create the
        # container (it already exists) so we never call create_container for it.
        if self.sas_url and ContainerClient is not None:
            try:
                self._cc = ContainerClient.from_container_url(self.sas_url)
                self.auth_mode = "sas"
                if not self.container_name:
                    self.container_name = self._cc.container_name
            except Exception:
                self._cc = None
        if (self._cc is None and self.connection_string
                and BlobServiceClient is not None):
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                if self.container_name:
                    self._cc = self.blob_service_client.get_container_client(
                        self.container_name)
                    self.auth_mode = "connection_string"
            except Exception:
                self.blob_service_client = None
                self._cc = None

    # -- status ------------------------------------------------------------- #
    @property
    def package_installed(self) -> bool:
        return BlobServiceClient is not None

    @property
    def configured(self) -> bool:
        """True when the client can actually talk to Azure."""
        return self._cc is not None

    def status(self) -> dict[str, Any]:
        return {
            "package_installed": self.package_installed,
            "has_connection_string": bool(self.connection_string),
            "has_sas_url": bool(self.sas_url),
            "has_container_name": bool(self.container_name),
            "container_name": self.container_name or "",
            "auth_mode": self.auth_mode or "",
            "configured": self.configured,
        }

    # -- container ---------------------------------------------------------- #
    def _container(self):
        if not self.configured:
            raise RuntimeError(
                "Azure Blob not configured. Set BLOB_SAS_URL (or "
                "AZURE_CONNECTION_STRING) and AZURE_BLOB_CONTAINER_NAME in a "
                ".env file (see .env.example)."
            )
        # Only a connection-string (account-level) client may create the
        # container; a container SAS has no permission to and doesn't need to.
        if self.auth_mode == "connection_string":
            try:
                self._cc.create_container()
            except ResourceExistsError:
                pass
            except Exception:
                pass
        return self._cc

    # -- blobs -------------------------------------------------------------- #
    def list_blobs(self) -> list[str]:
        if not self.configured:
            return []
        try:
            return [b.name for b in self._cc.list_blobs()]
        except Exception:
            return []

    def download_blob(self, blob_name: str) -> bytes:
        cc = self._container()
        return cc.get_blob_client(blob_name).download_blob().readall()

    def upload_blob(self, blob_name: str, data: bytes, overwrite: bool = True) -> None:
        cc = self._container()
        cc.upload_blob(name=blob_name, data=data, overwrite=overwrite)

    def delete_blob(self, blob_name: str) -> None:
        cc = self._container()
        try:
            cc.get_blob_client(blob_name).delete_blob()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# CSV / manifest helpers
# --------------------------------------------------------------------------- #
def _download_csv(client: AzureBlobClient, blob_name: str) -> pd.DataFrame:
    try:
        raw = client.download_blob(blob_name)
        return pd.read_csv(BytesIO(raw), low_memory=False)
    except Exception:
        return pd.DataFrame()


def load_manifest(client: AzureBlobClient) -> list[dict]:
    """Return the experiment manifest (one dict per experiment)."""
    try:
        raw = client.download_blob(MANIFEST_BLOB)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return []


def save_manifest(client: AzureBlobClient, manifest: list[dict]) -> None:
    client.upload_blob(
        MANIFEST_BLOB, json.dumps(manifest, indent=2).encode("utf-8"), overwrite=True
    )


# --------------------------------------------------------------------------- #
# Upload / list / delete
# --------------------------------------------------------------------------- #
def merge_and_upload_experiment(
    experiment_id: str,
    well_df: pd.DataFrame,
    sample_df: pd.DataFrame,
    meta: dict | None = None,
    client: AzureBlobClient | None = None,
) -> dict[str, Any]:
    """Append-merge one experiment's data into the shared blob tables.

    Parameters
    ----------
    experiment_id:
        Unique id for this upload (e.g. worksheet id or plate stem). Duplicate
        ids are skipped (manifest-guarded), matching the sibling apps.
    well_df:
        Well-level long table (full curves) for this experiment.
    sample_df:
        Per-sample summary rows for this experiment.
    meta:
        Optional manifest metadata (purpose, submitter, source file, ...).

    Returns a dict with ``ok`` / ``skipped`` and the manifest entry.
    """
    client = client or AzureBlobClient()
    if not client.configured:
        raise RuntimeError(
            "Azure Blob not configured. Set AZURE_CONNECTION_STRING and "
            "AZURE_BLOB_CONTAINER_NAME in a .env file (see .env.example)."
        )
    experiment_id = str(experiment_id).strip()
    if not experiment_id:
        raise ValueError("experiment_id is required for upload.")

    manifest = load_manifest(client)
    existing_ids = {m.get("Experiment_ID") for m in manifest}
    if experiment_id in existing_ids:
        return {"ok": False, "skipped": True,
                "message": f"Experiment '{experiment_id}' already uploaded.",
                "experiment_id": experiment_id}

    upload_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = dict(meta or {})

    def _stamp(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.insert(0, "Experiment_ID", experiment_id)
        df["Upload_UTC"] = upload_utc
        return df

    new_wells = _stamp(well_df) if well_df is not None and not well_df.empty else pd.DataFrame()
    new_samples = _stamp(sample_df) if sample_df is not None and not sample_df.empty else pd.DataFrame()

    # Append-merge with existing tables (union of columns).
    old_wells = _download_csv(client, DATA_BLOB)
    old_samples = _download_csv(client, SAMPLES_BLOB)
    merged_wells = (
        pd.concat([old_wells, new_wells], ignore_index=True, sort=False)
        if not old_wells.empty else new_wells
    )
    merged_samples = (
        pd.concat([old_samples, new_samples], ignore_index=True, sort=False)
        if not old_samples.empty else new_samples
    )

    if not merged_wells.empty:
        client.upload_blob(DATA_BLOB, merged_wells.to_csv(index=False).encode("utf-8"))
    if not merged_samples.empty:
        client.upload_blob(SAMPLES_BLOB, merged_samples.to_csv(index=False).encode("utf-8"))

    entry = {
        "Experiment_ID": experiment_id,
        "Upload_UTC": upload_utc,
        "Well_Rows": int(len(new_wells)),
        "Sample_Rows": int(len(new_samples)),
        "Source_File": meta.get("source_file", ""),
        "Sheet": meta.get("sheet", ""),
        "Purpose": meta.get("purpose", ""),
        "Submitter": meta.get("submitter", ""),
        "Worksheet_ID": meta.get("worksheet_id", ""),
        "Samples": meta.get("samples", ""),
    }
    manifest.append(entry)
    save_manifest(client, manifest)
    return {"ok": True, "skipped": False, "entry": entry}


def list_experiments(client: AzureBlobClient | None = None) -> list[dict]:
    """Return manifest entries (newest first)."""
    client = client or AzureBlobClient()
    if not client.configured:
        return []
    manifest = load_manifest(client)
    manifest.sort(key=lambda m: str(m.get("Upload_UTC", "")), reverse=True)
    return manifest


def delete_experiment(
    experiment_id: str, client: AzureBlobClient | None = None
) -> dict[str, Any]:
    """Remove one experiment's rows from both CSV tables and the manifest."""
    client = client or AzureBlobClient()
    if not client.configured:
        raise RuntimeError("Azure Blob not configured.")
    experiment_id = str(experiment_id).strip()

    manifest = load_manifest(client)
    if experiment_id not in {m.get("Experiment_ID") for m in manifest}:
        return {"ok": False, "message": f"Experiment '{experiment_id}' not found."}

    wells = _download_csv(client, DATA_BLOB)
    samples = _download_csv(client, SAMPLES_BLOB)
    w_before = len(wells)
    s_before = len(samples)

    if not wells.empty and "Experiment_ID" in wells.columns:
        wells = wells[wells["Experiment_ID"].astype(str) != experiment_id]
        client.upload_blob(DATA_BLOB, wells.to_csv(index=False).encode("utf-8"))
    if not samples.empty and "Experiment_ID" in samples.columns:
        samples = samples[samples["Experiment_ID"].astype(str) != experiment_id]
        client.upload_blob(SAMPLES_BLOB, samples.to_csv(index=False).encode("utf-8"))

    manifest = [m for m in manifest if m.get("Experiment_ID") != experiment_id]
    save_manifest(client, manifest)
    return {
        "ok": True,
        "experiment_id": experiment_id,
        "well_rows_removed": int(w_before - len(wells)),
        "sample_rows_removed": int(s_before - len(samples)),
    }


def download_tables(
    client: AzureBlobClient | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (well_df, sample_df) for all uploaded experiments."""
    client = client or AzureBlobClient()
    return _download_csv(client, DATA_BLOB), _download_csv(client, SAMPLES_BLOB)


def merge_and_upload_phase_experiment(
    experiment_id: str,
    measurements: pd.DataFrame,
    meta: dict | None = None,
    client: AzureBlobClient | None = None,
) -> dict[str, Any]:
    """Append one phase-diagram experiment to its independent blob table."""
    client = client or AzureBlobClient()
    if not client.configured:
        raise RuntimeError("Azure Blob not configured.")
    experiment_id = str(experiment_id).strip()
    if not experiment_id:
        raise ValueError("experiment_id is required for upload.")

    try:
        manifest = json.loads(client.download_blob(PHASE_MANIFEST_BLOB).decode("utf-8"))
    except Exception:
        manifest = []
    if experiment_id in {str(row.get("Experiment_ID", "")) for row in manifest}:
        return {"ok": False, "skipped": True,
                "message": f"Phase experiment '{experiment_id}' already uploaded.",
                "experiment_id": experiment_id}

    upload_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_rows = measurements.copy()
    if "experiment_id" not in new_rows.columns:
        new_rows.insert(0, "experiment_id", experiment_id)
    new_rows["Upload_UTC"] = upload_utc
    old_rows = _download_csv(client, PHASE_DATA_BLOB)
    merged = pd.concat([old_rows, new_rows], ignore_index=True, sort=False)
    client.upload_blob(PHASE_DATA_BLOB, merged.to_csv(index=False).encode("utf-8"))

    meta = dict(meta or {})
    entry = {
        "Experiment_ID": experiment_id,
        "Experiment_Name": meta.get("experiment_name", ""),
        "Surfactant": meta.get("surfactant", ""),
        "Polymer": meta.get("polymer", ""),
        "Measurement_Rows": int(len(new_rows)),
        "Upload_UTC": upload_utc,
    }
    manifest.append(entry)
    client.upload_blob(PHASE_MANIFEST_BLOB,
                       json.dumps(manifest, indent=2).encode("utf-8"))
    return {"ok": True, "skipped": False, "entry": entry}


def list_phase_experiments(client: AzureBlobClient | None = None) -> list[dict]:
    client = client or AzureBlobClient()
    if not client.configured:
        return []
    try:
        manifest = json.loads(client.download_blob(PHASE_MANIFEST_BLOB).decode("utf-8"))
    except Exception:
        return []
    return sorted(manifest, key=lambda row: str(row.get("Upload_UTC", "")), reverse=True)


def delete_phase_experiment(
    experiment_id: str, client: AzureBlobClient | None = None
) -> dict[str, Any]:
    client = client or AzureBlobClient()
    if not client.configured:
        raise RuntimeError("Azure Blob not configured.")
    experiment_id = str(experiment_id).strip()
    try:
        manifest = json.loads(client.download_blob(PHASE_MANIFEST_BLOB).decode("utf-8"))
    except Exception:
        manifest = []
    if experiment_id not in {str(row.get("Experiment_ID", "")) for row in manifest}:
        return {"ok": False, "message": f"Phase experiment '{experiment_id}' not found."}

    rows = _download_csv(client, PHASE_DATA_BLOB)
    before = len(rows)
    if not rows.empty and "experiment_id" in rows.columns:
        rows = rows[rows["experiment_id"].astype(str) != experiment_id]
    if rows.empty:
        client.delete_blob(PHASE_DATA_BLOB)
    else:
        client.upload_blob(PHASE_DATA_BLOB, rows.to_csv(index=False).encode("utf-8"))
    manifest = [row for row in manifest
                if str(row.get("Experiment_ID", "")) != experiment_id]
    client.upload_blob(PHASE_MANIFEST_BLOB,
                       json.dumps(manifest, indent=2).encode("utf-8"))
    return {"ok": True, "experiment_id": experiment_id,
            "measurement_rows_removed": int(before - len(rows))}


def download_phase_measurements(
    client: AzureBlobClient | None = None,
) -> pd.DataFrame:
    client = client or AzureBlobClient()
    return _download_csv(client, PHASE_DATA_BLOB)
