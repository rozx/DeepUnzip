"""Fake archives and a fake 7-Zip engine shared by the work-pool and renderer tests.

Fake archives are JSON files. A container lists its files; a volume records its
set id, index, total and password. Like 7-Zip, the fake engine finds sibling
volumes by name in the primary's folder, so assembly isolation is exercised.
"""

import json
import os

from complex_unzip_tool_v2.modules import multipart_assembly as ma
from complex_unzip_tool_v2.modules import work_pool as wp

VOLUME_SIZE = 4096


def archive(files, password=None):
    return {"kind": "archive", "password": password, "files": files}


def volume(set_id, index, total, files=None, password=None, alone=None):
    data = {
        "kind": "volume",
        "set": set_id,
        "index": index,
        "total": total,
        "password": password,
        "files": files or {},
    }
    if alone:
        data["alone"] = alone
    return data


def write(path, value):
    path = str(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(value, str):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(value)
        return
    text = json.dumps(value, ensure_ascii=False)
    if value.get("kind") == "volume":
        text = text.ljust(VOLUME_SIZE)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class FakeEngine:
    def __init__(self, passwords=()):
        self.passwords = list(passwords)
        self.remembered = []
        self.probes = []

    @staticmethod
    def _load(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.loads(handle.read())
        except (OSError, ValueError):
            return None

    def classify(self, path):
        data = self._load(path)
        if not isinstance(data, dict):
            return "regular"
        return {"archive": "container", "volume": "container", "broken": "broken"}.get(
            data.get("kind"), "regular"
        )

    def _resolve(self, archive_path, password):
        data = self._load(archive_path)
        if not isinstance(data, dict):
            return wp.Outcome("unsupported"), None
        if data["kind"] == "broken":
            return wp.Outcome("failed"), None
        if data["kind"] == "volume":
            parsed = ma.parse_volume_name(archive_path)
            folder = os.path.dirname(archive_path)
            siblings = {}
            for name in os.listdir(folder):
                other = ma.parse_volume_name(name)
                if other and parsed and other.key == parsed.key:
                    siblings[other.index] = os.path.join(folder, name)
            if len(siblings) == 1 and data["total"] > 1:
                return wp.Outcome(data.get("alone", "missing_volume")), None
            for index in range(2, data["total"] + 1):
                if index not in siblings:
                    return wp.Outcome("missing_volume"), None
                other_data = self._load(siblings[index])
                if (
                    not isinstance(other_data, dict)
                    or other_data.get("set") != data["set"]
                    or other_data.get("index") != index
                ):
                    return wp.Outcome("failed", detail="CRC failed"), None
        tries = [password] if password is not None else ["", *self.passwords]
        for position, candidate in enumerate(tries):
            if (data.get("password") or "") == candidate:
                ref = "entered" if password is not None else position
                return wp.Outcome("ok", candidate, ref), data
        return wp.Outcome("password"), None

    def probe(self, archive_path, password=None):
        self.probes.append(archive_path)
        outcome, data = self._resolve(archive_path, password)
        if outcome.ok:
            used = data["total"] if data["kind"] == "volume" else 1
            return wp.Outcome(
                "ok", outcome.password, outcome.password_ref, volumes=used
            )
        return outcome

    def extract(self, archive_path, dest, password=None):
        outcome, data = self._resolve(archive_path, password)
        if outcome.ok:
            for name, value in data["files"].items():
                write(os.path.join(dest, name), value)
        return outcome

    def remember(self, password):
        self.remembered.append(password)
        self.passwords.append(password)


def uncloak_suffix(calls):
    def uncloak(path, is_source):
        calls.append((os.path.basename(path), is_source))
        if path.endswith("删掉"):
            new_path = path[: -len("删掉")]
            os.rename(path, new_path)
            return new_path
        return path

    return uncloak


class Remover:
    def __init__(self, fail_on=()):
        self.removed = []
        self.fail_on = set(fail_on)

    def __call__(self, path):
        if os.path.basename(path) in self.fail_on:
            return False
        self.removed.append(path)
        os.remove(path)
        return True

    def names(self):
        return sorted(os.path.basename(p) for p in self.removed)


def run_pool(root, engine=None, sources=None, **kwargs):
    root = str(root)
    if sources is None:
        sources = [
            os.path.join(folder, name)
            for folder, _dirs, names in os.walk(root)
            for name in names
        ]
    kwargs.setdefault("remove", Remover())
    kwargs.setdefault("run_id", "test")
    pool = wp.WorkPool(root, sources, engine or FakeEngine(), **kwargs)
    return pool.run(), kwargs["remove"]


def deleted(result):
    return sorted(os.path.basename(p) for p in result.deleted_sources)


def output_files(root):
    out = os.path.join(str(root), "unzipped")
    found = []
    for folder, _dirs, names in os.walk(out):
        for name in names:
            found.append(os.path.relpath(os.path.join(folder, name), out))
    return sorted(p.replace(os.sep, "/") for p in found)
