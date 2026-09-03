import griffe

_ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum"}


class HideAttributes(griffe.Extension):
    def on_class(self, *, cls: griffe.Class, **kwargs) -> None:
        # Enum members are the whole point of documenting an enum - keep them.
        if any(str(base).rsplit(".", 1)[-1] in _ENUM_BASES for base in cls.bases):
            return
        # Copy keys because we will delete while iterating
        for name, member in list(cls.members.items()):
            labels = getattr(member, "labels", set()) or set()
            if labels.intersection({"property", "class-attribute", "instance-attribute"}):
                cls.del_member(name)
