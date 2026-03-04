import configparser
from pathlib import Path
from typing import Any, Dict, List, Optional


class ClusterConfig:
    """Loads, resolves, and persists pyadm configuration and module contexts."""

    MODULE_KEYS = {
        "ELASTIC": "elastic",
        "LDAP": "ldap",
        "PVE": "pve",
    }

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = Path(config_file) if config_file else (Path.home() / ".config/pyadm/pyadm.conf")
        self.config = configparser.ConfigParser()
        self.reload()

    def reload(self) -> None:
        self.config = configparser.ConfigParser()
        self.config.read(self.config_file)

    def save(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as config_file:
            self.config.write(config_file)

    def _normalize_prefix(self, prefix: str) -> str:
        upper_prefix = prefix.upper()
        if upper_prefix in self.MODULE_KEYS:
            return upper_prefix
        lower_prefix = prefix.lower()
        for module_prefix, module_key in self.MODULE_KEYS.items():
            if lower_prefix == module_key:
                return module_prefix
        raise ValueError(f"Unsupported prefix/module '{prefix}'.")

    def _module_key(self, prefix: str) -> str:
        return self.MODULE_KEYS.get(self._normalize_prefix(prefix), prefix.lower())

    def _find_section_name(self, section_name: str) -> Optional[str]:
        target = section_name.lower()
        for section in self.config.sections():
            if section.lower() == target:
                return section
        return None

    def _infer_context_name(self, section: str, prefix: str) -> str:
        upper_section = section.upper()
        if upper_section == prefix:
            return "default"
        context_marker = f"{prefix}_CONTEXT_"
        if upper_section.startswith(context_marker):
            return section[len(context_marker):]
        legacy_marker = f"{prefix}_"
        if upper_section.startswith(legacy_marker):
            return section[len(legacy_marker):]
        return section

    def _find_context_entry(self, contexts: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
        target = name.lower()
        for entry in contexts:
            if entry["name"].lower() == target or entry["section"].lower() == target:
                return entry
        return None

    def get_section(self, section_name: str) -> Dict[str, str]:
        self.reload()
        section = self._find_section_name(section_name)
        if not section:
            raise RuntimeError(f"Section '{section_name}' not found in config.")
        return dict(self.config[section])

    def get_clusters(self, prefix: str = "ELASTIC", reload: bool = True) -> Dict[str, Dict[str, str]]:
        if reload:
            self.reload()
        normalized_prefix = self._normalize_prefix(prefix)
        clusters: Dict[str, Dict[str, str]] = {}
        for section in self.config.sections():
            if section.upper().startswith(normalized_prefix):
                clusters[section] = dict(self.config[section])
        return clusters

    def list_contexts(self, prefix: str = "ELASTIC", reload: bool = True) -> List[Dict[str, Any]]:
        if reload:
            self.reload()
        normalized_prefix = self._normalize_prefix(prefix)
        clusters = self.get_clusters(prefix=normalized_prefix, reload=False)
        context_map: Dict[str, Dict[str, Any]] = {}

        for section, cfg in clusters.items():
            configured_name = cfg.get("name", "")
            context_name = configured_name.strip() or self._infer_context_name(section, normalized_prefix)
            context_key = context_name.lower()
            existing = context_map.get(context_key)

            if existing and existing["section"] != section:
                raise RuntimeError(
                    f"Duplicate {normalized_prefix} context name '{context_name}' "
                    f"found in sections [{existing['section']}] and [{section}]."
                )

            context_map[context_key] = {
                "name": context_name,
                "section": section,
                "config": cfg,
            }

        return list(context_map.values())

    def get_active_context(self, prefix: str = "ELASTIC", reload: bool = True) -> Optional[str]:
        if reload:
            self.reload()
        module_key = self._module_key(prefix)
        if "CONTEXT" not in self.config:
            return None
        value = self.config["CONTEXT"].get(module_key)
        if not value:
            return None
        return value.strip() or None

    def set_active_context(self, prefix: str, name: str) -> str:
        self.reload()
        normalized_prefix = self._normalize_prefix(prefix)
        contexts = self.list_contexts(prefix=normalized_prefix, reload=False)
        if not contexts:
            raise RuntimeError(f"No {normalized_prefix} cluster/server defined in config.")

        selected = self._find_context_entry(contexts, name)
        if not selected:
            available = ", ".join(context["name"] for context in contexts)
            raise RuntimeError(
                f"Unknown {normalized_prefix} context '{name}'. Available contexts: {available}"
            )

        if "CONTEXT" not in self.config:
            self.config["CONTEXT"] = {}
        self.config["CONTEXT"][self._module_key(normalized_prefix)] = selected["name"]
        self.save()
        return selected["name"]

    def resolve_context(self, name: Optional[str] = None, prefix: str = "ELASTIC") -> Dict[str, Any]:
        self.reload()
        normalized_prefix = self._normalize_prefix(prefix)
        contexts = self.list_contexts(prefix=normalized_prefix, reload=False)

        if not contexts:
            raise RuntimeError(f"No {normalized_prefix} cluster/server defined in config.")

        if name:
            selected = self._find_context_entry(contexts, name)
            if selected:
                return selected

            available = ", ".join(context["name"] for context in contexts)
            raise RuntimeError(
                f"Unknown {normalized_prefix} context or section '{name}'. Available contexts: {available}"
            )

        active_name = self.get_active_context(prefix=normalized_prefix, reload=False)
        if active_name:
            selected = self._find_context_entry(contexts, active_name)
            if selected:
                return selected

        for context in contexts:
            if context["section"].upper() == normalized_prefix:
                return context

        return contexts[0]

    def get_cluster(self, name: Optional[str] = None, prefix: str = "ELASTIC") -> Dict[str, str]:
        return self.resolve_context(name=name, prefix=prefix)["config"]


cluster_config = ClusterConfig()
config = cluster_config.config
