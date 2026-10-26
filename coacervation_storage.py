"""Persistent file storage for the single-worker BeautyFast deployment."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from threading import Event, Lock, Thread

SOURCE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("COACERVATION_DATA_DIR", SOURCE_DIR))
DATA_FOLDERS = ("raw_data", "lasentec_data", "microscopy_images")
PREFIX = "app-state/"


def state_files(root):
    files = list(root.glob("*.json")) + list(root.glob("*.db"))
    for folder in DATA_FOLDERS:
        directory = root / folder
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    return {path.relative_to(root).as_posix(): path for path in files}


def file_bytes(path):
    if path.suffix != ".db":
        return path.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        backup = Path(directory) / path.name
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(backup)) as target:
            source.backup(target)
        return backup.read_bytes()


def prepare_runtime():
    from dotenv import load_dotenv

    load_dotenv(SOURCE_DIR / ".env")
    if DATA_DIR == SOURCE_DIR:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("component_properties.csv", "polymer_properties.csv"):
        source = SOURCE_DIR / name
        if source.exists():
            shutil.copy2(source, DATA_DIR / name)
    if str(SOURCE_DIR) not in sys.path:
        sys.path.insert(0, str(SOURCE_DIR))
    os.chdir(DATA_DIR)


class FileStorage:
    def __init__(self, container, root=DATA_DIR):
        self.container = container
        self.root = root.resolve()
        self.known = {}
        self.etags = {}
        self.lock = Lock()
        self.lease = None
        self.stop = Event()
        self.renewal = None
        self.renewal_error = None

    def signatures(self):
        return {name: (path.stat().st_mtime_ns, path.stat().st_size)
                for name, path in state_files(self.root).items()}

    def restore(self):
        remote = set()
        for blob in self.container.list_blobs(name_starts_with=PREFIX):
            name = blob.name[len(PREFIX):]
            path = (self.root / name).resolve()
            if self.root not in path.parents:
                raise ValueError("Invalid persistent file path")
            remote.add(name)
            if self.etags.get(name) != blob.etag:
                path.parent.mkdir(parents=True, exist_ok=True)
                data = self.container.download_blob(blob.name).readall()
                path.write_bytes(data)
                self.etags[name] = blob.etag
        for name in set(self.known) - remote:
            (self.root / name).unlink(missing_ok=True)
            self.etags.pop(name, None)
        self.known = self.signatures()

    def flush(self):
        if self.renewal_error:
            raise RuntimeError("Persistent storage lock was lost") from self.renewal_error
        current = self.signatures()
        for name, signature in current.items():
            if self.known.get(name) != signature:
                result = self.container.upload_blob(
                    PREFIX + name, file_bytes(self.root / name), overwrite=True)
                self.etags[name] = result["etag"]
        for name in set(self.known) - set(current):
            self.container.delete_blob(PREFIX + name)
            self.etags.pop(name, None)
        self.known = current

    def renew(self):
        while not self.stop.wait(20):
            try:
                self.lease.renew()
            except Exception as error:
                self.renewal_error = error
                return

    def begin(self):
        from azure.core.exceptions import ResourceExistsError

        self.lock.acquire()
        try:
            blob = self.container.get_blob_client("app-state.lock")
            try:
                blob.upload_blob(b"", overwrite=False)
            except ResourceExistsError:
                pass
            self.lease = blob.acquire_lease(lease_duration=60)
            self.stop.clear()
            self.renewal_error = None
            self.renewal = Thread(target=self.renew, daemon=True)
            self.renewal.start()
            self.restore()
        except Exception:
            self.end()
            raise

    def end(self):
        self.stop.set()
        if self.renewal:
            self.renewal.join()
            self.renewal = None
        try:
            if self.lease:
                self.lease.release()
        finally:
            self.lease = None
            self.lock.release()


def storage_container():
    from azure.storage.blob import BlobServiceClient

    connection = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    name = os.environ.get("BEAUTYFAST_STORAGE_CONTAINER")
    if not connection or not name:
        return None
    return BlobServiceClient.from_connection_string(connection).get_container_client(name)


def install_storage(app):
    from flask import g, jsonify

    if DATA_DIR == SOURCE_DIR:
        return
    container = storage_container()
    storage = FileStorage(container) if container else None

    @app.before_request
    def restore_state():
        if storage is None:
            return jsonify(ok=False, error="Persistent storage is not configured yet."), 503
        try:
            storage.begin()
            g.storage_active = True
        except Exception:
            app.logger.exception("Could not restore persistent app data")
            return jsonify(ok=False, error="Persistent storage is temporarily unavailable."), 503

    @app.after_request
    def save_state(response):
        if getattr(g, "storage_active", False):
            try:
                storage.flush()
            except Exception:
                app.logger.exception("Could not persist app data")
                return app.make_response((jsonify(
                    ok=False, error="Changes could not be saved. Please retry."), 503))
        return response

    @app.teardown_request
    def release_storage(error):
        if getattr(g, "storage_active", False):
            g.storage_active = False
            storage.end()


def seed_storage():
    """Copy existing local data to a new container, never replacing cloud data."""
    from azure.core.exceptions import ResourceExistsError

    container = storage_container()
    if container is None:
        raise RuntimeError("Run bf storage create first")
    count = 0
    for name, path in state_files(SOURCE_DIR).items():
        try:
            container.upload_blob(PREFIX + name, file_bytes(path), overwrite=False)
            count += 1
        except ResourceExistsError:
            pass
    print(f"Migrated {count} local data files to private app storage.")