from datetime import datetime

from pyc8y.base import CumulocityRestApi
from pyc8y.model.base import CumulocityObject, json_property, id_property, time_property, datetime_property


class _MeaObject(CumulocityObject):
    def __init__(
            self,
            c8y: CumulocityRestApi,
            type: str = None,   # noqa (type)
            time: str | datetime = None,
            source: str = None,
            **kwargs
    ):
        super().__init__(c8y, **kwargs)
        self.type = type
        self.source = source
        self.time = time

    type = json_property("type")
    source = id_property("source")
    time = time_property("time")
    datetime = datetime_property("time")


