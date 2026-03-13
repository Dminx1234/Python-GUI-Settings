# core.py — Config, Environment model, and environment discovery
import json, os, re, shutil, subprocess, platform
from pathlib import Path

# ── Persistent paths ──────────────────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".pyenv_manager"
CONFIG_FILE = CONFIG_DIR / "config.json"
ACTIVE_FILE = CONFIG_DIR / "active_env.sh"
LAUNCH_TMP  = CONFIG_DIR / "launch_env.sh"

SHELL_HOOK = (
    '\n# ── PyEnv Manager auto-activation ──\n'
    f'[ -f "{ACTIVE_FILE}" ] && source "{ACTIVE_FILE}"\n'
)


# ─────────────────────────────────────────────────────────────────────────────
#  Config  (persists aliases + active env)
# ─────────────────────────────────────────────────────────────────────────────
class Config:
    def __init__(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        self._d = {"aliases": {}, "active": None}
        if CONFIG_FILE.exists():
            try:
                self._d.update(json.loads(CONFIG_FILE.read_text()))
            except Exception:
                pass

    def save(self):
        CONFIG_FILE.write_text(json.dumps(self._d, indent=2))

    @property
    def active(self): return self._d.get("active")

    @active.setter
    def active(self, v):
        self._d["active"] = v
        self.save()

    def set_alias(self, key, name):
        self._d["aliases"][key] = name
        self.save()

    def get_alias(self, key):
        return self._d["aliases"].get(key)

    def clear_alias(self, key):
        self._d["aliases"].pop(key, None)
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
#  Environment model
# ─────────────────────────────────────────────────────────────────────────────
class Environment:
    def __init__(self, info: dict, config: Config):
        self.path   = info["path"]   # Path object
        self.type   = info["type"]   # conda | venv | pyenv | system
        self.config = config
        self._version  = None
        self._packages = None        # None = not loaded yet

    # ── Identity ──────────────────────────────────────────────────────────────
    @property
    def key(self):
        if self.type == "system":
            return f"sys:{self.path}"
        return str(self.path)

    @property
    def display_name(self):
        alias = self.config.get_alias(self.key)
        if alias:
            return alias
        if self.type == "system":
            return f"System  ({self.path.name})"
        return self.path.name

    # ── Binaries ──────────────────────────────────────────────────────────────
    @property
    def python_bin(self):
        if self.type == "system":
            return str(self.path)
        return str(self.path / "bin" / "python")

    @property
    def pip_bin(self):
        if self.type == "system":
            parent = Path(self.python_bin).parent
            for nm in ("pip3", "pip"):
                c = parent / nm
                if c.exists():
                    return str(c)
            return shutil.which("pip3") or shutil.which("pip") or "pip3"
        for nm in ("pip", "pip3"):
            p = self.path / "bin" / nm
            if p.exists():
                return str(p)
        return str(self.path / "bin" / "pip")

    @property
    def activate_cmd(self):
        if self.type == "conda":
            return f'conda activate "{self.path}"'
        elif self.type == "system":
            return f'export PATH="{Path(self.python_bin).parent}:$PATH"'
        else:
            return f'source "{self.path / "bin" / "activate"}"'

    # ── Lazy data ─────────────────────────────────────────────────────────────
    def get_version(self):
        if self._version:
            return self._version
        try:
            r = subprocess.run([self.python_bin, "--version"],
                               capture_output=True, text=True, timeout=6)
            self._version = (r.stdout + r.stderr).strip()
        except Exception:
            self._version = "Unknown"
        return self._version

    def get_packages(self):
        if self._packages is not None:
            return self._packages
        try:
            r = subprocess.run(
                [self.pip_bin, "list", "--format=columns"],
                capture_output=True, text=True, timeout=30
            )
            lines = r.stdout.strip().split("\n")
            self._packages = [
                {"name": p[0], "version": p[1]}
                for line in lines[2:]
                if len(p := line.split()) >= 2
            ]
        except Exception:
            self._packages = []
        return self._packages

    def export_requirements(self, path: Path):
        r = subprocess.run([self.pip_bin, "freeze"],
                           capture_output=True, text=True, timeout=30)
        path.write_text(r.stdout)

    # ── Active env management ─────────────────────────────────────────────────
    def is_active(self):
        return self.config.active == self.key

    def set_active(self):
        self.config.active = self.key
        self._write_hook()

    def _write_hook(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        if self.type == "conda":
            content = f'conda activate "{self.path}" 2>/dev/null\n'
        elif self.type == "system":
            content = f'export PATH="{Path(self.python_bin).parent}:$PATH" 2>/dev/null\n'
        else:
            content = f'source "{self.path / "bin" / "activate"}" 2>/dev/null\n'
        ACTIVE_FILE.write_text(content)

    # ── Rename ────────────────────────────────────────────────────────────────
    def rename(self, new_name: str):
        self.config.set_alias(self.key, new_name.strip())

    def reset_name(self):
        self.config.clear_alias(self.key)

    # ── Delete ────────────────────────────────────────────────────────────────
    def delete(self):
        """Remove env from disk and config. Raises RuntimeError on failure."""
        if self.type == "system":
            raise RuntimeError("System Python cannot be deleted from here.")

        if self.type == "conda":
            r = subprocess.run(
                ["conda", "env", "remove", "--prefix", str(self.path), "-y"],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr or "conda remove failed")
        else:
            if not self.path.exists():
                raise RuntimeError(f"Path not found: {self.path}")
            import shutil as _sh
            _sh.rmtree(str(self.path))

        # Clean up config
        if self.config.active == self.key:
            self.config.active = None
            if ACTIVE_FILE.exists():
                ACTIVE_FILE.write_text("# No active environment\n")
        self.config.clear_alias(self.key)


# ─────────────────────────────────────────────────────────────────────────────
#  Environment discovery
# ─────────────────────────────────────────────────────────────────────────────
class EnvDiscovery:

    @staticmethod
    def find_all():
        envs, seen = [], set()

        # ── conda ─────────────────────────────────────────────────────────────
        if shutil.which("conda"):
            try:
                r = subprocess.run(["conda", "env", "list", "--json"],
                                   capture_output=True, text=True, timeout=12)
                for p in json.loads(r.stdout).get("envs", []):
                    path = Path(p)
                    key  = str(path)
                    if key not in seen and (path / "bin" / "python").exists():
                        seen.add(key)
                        envs.append({"path": path, "type": "conda"})
            except Exception:
                pass

        # ── pyenv virtualenvs ─────────────────────────────────────────────────
        pyenv_versions = Path.home() / ".pyenv" / "versions"
        if pyenv_versions.exists():
            for p in sorted(pyenv_versions.iterdir()):
                if p.is_dir() and (p / "bin" / "python").exists():
                    key = str(p)
                    if key not in seen:
                        seen.add(key)
                        envs.append({"path": p, "type": "pyenv"})

        # ── common venv dirs ──────────────────────────────────────────────────
        venv_roots = [
            Path.home() / ".virtualenvs",
            Path.home() / "envs",
            Path.home() / "venvs",
            Path.home() / ".venvs",
            Path.home() / "Envs",
        ]
        for root in venv_roots:
            if root.is_dir():
                for p in sorted(root.iterdir()):
                    if p.is_dir() and EnvDiscovery._is_venv(p):
                        key = str(p)
                        if key not in seen:
                            seen.add(key)
                            envs.append({"path": p, "type": "venv"})

        # ── system pythons ────────────────────────────────────────────────────
        for py in EnvDiscovery._system_pythons():
            key = f"sys:{py}"
            if key not in seen:
                seen.add(key)
                envs.append({"path": Path(py), "type": "system"})

        return envs

    @staticmethod
    def _is_venv(path: Path) -> bool:
        return (
            (path / "bin" / "python").exists() and
            (path / "bin" / "activate").exists() and
            (path / "pyvenv.cfg").exists()
        )

    @staticmethod
    def _system_pythons():
        """Find system Pythons — checks PATH, macOS framework, and common install dirs."""
        found, real_seen = [], set()

        def _try(p):
            if not p:
                return
            try:
                real = os.path.realpath(p)
                if real in real_seen:
                    return
                real_seen.add(real)
                found.append(p)
            except Exception:
                if p not in found:
                    found.append(p)

        # PATH-based
        for name in ["python3", "python",
                     "python3.13", "python3.12", "python3.11",
                     "python3.10", "python3.9",  "python3.8"]:
            _try(shutil.which(name))

        # macOS — python.org installs Framework
        if platform.system() == "Darwin":
            base = Path("/Library/Frameworks/Python.framework/Versions")
            if base.exists():
                for v in sorted(base.iterdir(), reverse=True):
                    _try(str(v / "bin" / "python3"))
            # Homebrew
            for brew_base in [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]:
                for name in ["python3", "python3.13", "python3.12", "python3.11",
                             "python3.10", "python3.9", "python3.8"]:
                    p = brew_base / name
                    if p.exists():
                        _try(str(p))

        # Linux common locations
        if platform.system() == "Linux":
            for v in ["3.13", "3.12", "3.11", "3.10", "3.9", "3.8"]:
                for prefix in ["/usr/bin", "/usr/local/bin"]:
                    p = Path(prefix) / f"python{v}"
                    if p.exists():
                        _try(str(p))

        return found[:8]

    # ── Utility: all Python binaries for dropdowns ────────────────────────────
    @staticmethod
    def find_python_binaries() -> dict:
        """Returns {real_path: display_label} for all usable Pythons."""
        result, seen = {}, set()

        def _probe(path_str):
            if not path_str or not os.path.isfile(path_str):
                return
            real = os.path.realpath(path_str)
            if real in seen:
                return
            seen.add(real)
            try:
                r = subprocess.run([path_str, "--version"],
                                   capture_output=True, text=True, timeout=4)
                ver = (r.stdout + r.stderr).strip()
                result[real] = f"{ver}  ·  {path_str}"
            except Exception:
                pass

        for py in EnvDiscovery._system_pythons():
            _probe(py)

        pyenv_vers = Path.home() / ".pyenv" / "versions"
        if pyenv_vers.exists():
            for d in sorted(pyenv_vers.iterdir()):
                _probe(str(d / "bin" / "python"))

        return result
