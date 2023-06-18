from typing import Optional

MODES = ["local", "remote"]


class IRCCapabilities:
    def __init__(self, mode: str = MODES[0], capabilities: dict = None):
        if mode not in MODES:
            raise ValueError(f"Invalid mode {mode}. Valid options: {MODES}")
        self.mode = mode
        self.capabilities = capabilities if capabilities is not None else {}
        self.extensions = [extension for extension in self.capabilities.keys()]

    def __contains__(self, item: list):
        if isinstance(item, list):
            return all(str(i).lstrip("-") in self.capabilities for i in item)
        else:
            raise TypeError(f"Unsupported comparison for {type(item)}")

    def to_list(self) -> list:
        capability_list = []
        for capability_key, capability_value in self.capabilities.items():
            capability_string = capability_key
            if "mechanisms" in capability_value and len(capability_value["mechanisms"]) > 0:
                methods = ",".join(capability_value["mechanisms"].keys())
                capability_string += "=" + methods
            capability_list.append(capability_string)
        return capability_list

    def filter_by_version(self, version: int) -> "IRCCapabilities":
        filtered_capabilities = self.capabilities.copy()
        for capability_key, capability_value in filtered_capabilities.items():
            required_version = capability_value.get("required_version", None)
            if required_version is None or required_version <= version:
                if "mechanisms" in capability_value.values():
                    for method_key, method_value in capability_value["mechanisms"]:
                        required_version = method_value.get("required_version", None)
                        if required_version is None or required_version <= version:
                            pass
                        else:
                            del filtered_capabilities[capability_key]["mechanisms"][method_key]
            else:
                del filtered_capabilities[capability_key]
        return IRCCapabilities(self.mode, filtered_capabilities)

    def get_mechanisms(self, extension: str) -> Optional[list]:
        try:
            mechanisms = list(self.capabilities[extension]["mechanisms"].keys())
            return mechanisms if mechanisms else None
        except IndexError:
            return None

    def validate_extensions(self, extensions: list):
        return extensions in self

    def validate_mechanism(self, extension: str, mechanism: str):
        return mechanism in self.get_mechanisms(extension)

    def update(self, cap: "IRCCapabilities"):
        self.update_capabilities(cap.capabilities)
        self.update_extensions(cap.extensions)

    def update_capabilities(self, capabilities: dict):
        self.capabilities.update(capabilities)

    def update_extensions(self, extensions: list):
        for extension in extensions:
            if extension.startswith("-"):
                self.extensions.remove(extension)
            elif extension not in self.extensions:
                self.extensions.append(extension)

    def serialize(self) -> str:
        capability_list = self.to_list()
        return " ".join(capability_list)
