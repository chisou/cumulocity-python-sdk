# Copyright (c) 2026 Christoph Souris

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar, Sequence, Self, Iterable, AsyncIterator, Any

from pyc8y.base_util import is_sequence
from pyc8y.rest import CumulocityRestClient
from pyc8y.model.model_base import (
    CumulocityObject,
    CumulocityResource,
    json_property,
    id_property,
    time_property,
    datetime_property,
    map_params,
)
from pyc8y.model.model_util import to_datetime
from pyc8y.types import MeasurementsMeta, AsValuesSpec


class Units(StrEnum):
    """Predefined, common units."""

    Grams = "g"
    Kilograms = "kg"
    Kelvin = "K"
    Celsius = "°C"
    Fahrenheit = "°F"
    Meters = "m"
    Centimeters = "cm"
    Millimeters = "mm"
    Liters = "l"
    CubicMeters = "m3"
    Count = "#"
    Percent = "%"


class AggregationType(StrEnum):
    """Series aggregation types."""

    DAILY = "DAILY"
    HOURLY = "HOURLY"
    MINUTELY = "MINUTELY"


class Value(dict):
    """Generic datapoint."""

    _unit: ClassVar[str] = ""

    def __init__(self, value: float, unit: str | None = None):
        super().__init__(value=value, unit=unit or self._unit)

    @property
    def value(self):
        return self["value"]

    @property
    def unit(self):
        return self["unit"]


class Grams(Value):
    """Weight datapoint (Grams)."""

    _unit = Units.Grams


class Kilograms(Value):
    """Weight datapoint (Kilograms)."""

    _unit = Units.Kilograms


class Kelvin(Value):
    """Temperature datapoint (Kelvin)."""

    _unit = Units.Kelvin


class Celsius(Value):
    """Temperature datapoint (Celsius)."""

    _unit = Units.Celsius


class Meters(Value):
    """Length datapoint (Meters)."""

    _unit = Units.Meters


class Centimeters(Value):
    """Length datapoint (Centimeters)."""

    _unit = Units.Centimeters


class Millimeters(Value):
    """Length datapoint (Millimeters)."""

    _unit = Units.Millimeters


class Liters(Value):
    """Volume datapoint (Liters)."""

    _unit = Units.Liters


class CubicMeters(Value):
    """Volume datapoint (Cubic Meters)."""

    _unit = Units.CubicMeters


class Count(Value):
    """Discrete number datapoint (number/count)."""

    _unit = Units.Count


class Percent(Value):
    """Percent value datapoint."""

    _unit = Units.Percent


def grams(value: int | float):
    """Build weight datapoint (Grams)."""
    return Grams(value)


def kilograms(value: int | float):
    """Build weight datapoint (Kilograms)."""
    return Kilograms(value)


def kelvin(value: int | float):
    """Build temperature datapoint (Kelvin)."""
    return Kelvin(value)


def celsius(value: int | float):
    """Build temperature datapoint (Celsius)."""
    return Celsius(value)


def meters(value: int | float):
    """Build length datapoint (Meters)."""
    return Meters(value)


def centimeters(value: int | float):
    """Build length datapoint (Centimeters)."""
    return Centimeters(value)


def millimeters(value: int | float):
    """Build length datapoint (Millimeters)."""
    return Millimeters(value)


def liters(value: int | float):
    """Build volume datapoint (Liters)."""
    return Liters(value)


def cubic_meters(value: int | float):
    """Build volume datapoint (Cubic Meters)."""
    return CubicMeters(value)


def count(value: int | float):
    """Build discrete number datapoint (number/count)."""
    return Count(value)


def percent(value: int | float):
    """Build percent value datapoint."""
    return Percent(value)


SeriesValue = tuple[str, int | float, str | None]


def is_series(series: Iterable[SeriesValue] | SeriesValue) -> bool:
    return isinstance(series, tuple) and len(series) in (2, 3) and isinstance(series[0], str)


@dataclass
class SeriesSpec:
    """Series specifications."""

    unit: str
    type: str
    name: str

    @property
    def series(self):
        """Return the complete series name."""
        return f"{self.type}.{self.name}"


class Series(dict):
    """A wrapper for a series result.

    See also: `Measurements.get_series` function

    This class wraps the raw JSON result but can also be used to read result specs
    and collect result values conveniently.

    See also: https://cumulocity.com/api/core/#operation/getMeasurementSeriesResource
    """

    @property
    def truncated(self):
        """Whether the result was truncated
        (i.e. the query returned more than 5000 values)."""
        return self["truncated"]

    @property
    def specs(self) -> Sequence[SeriesSpec]:
        """Return specifications for all enclosed series."""
        return [SeriesSpec(type=i["type"], name=i["name"], unit=i["unit"]) for i in self["series"]]

    @property
    def values(self) -> dict[str, list[dict[str, float] | None]]:
        """Return series values.

        Returns:
            A dict of timestamp strings mapped to a list of dictionaries
            mapping value names (min, max, ...) to values (float) or None
            the series doesn't have values for this timestamp.
        """
        return self["values"]

    def collect(
        self,
        series: str | Sequence[str] | None = None,
        value: str | Sequence[str] | None = None,
        timestamps: bool | str | None = None,
    ) -> list | list[tuple]:
        """Collect series results.

        Args:
            series (str|Sequence[str]):  Which series' values to collect. If
                multiple series are collected each element in the result will
                be a tuple. If omitted, all available series are collected.
            value (str | Sequence[str]):  Which value(s) (min/max/avg/...) to
                collect. Multiple values can be specified. If omitted, all
                available values are collected.
            timestamps (bool|str):  Whether each element in the result list
                will be prepended with the corresponding timestamp. If True,
                the timestamp string will be included; Use 'datetime' or
                'epoch' to parse the timestamp string.

        Returns:
            A simple list or list of tuples (potentially nested) depending on the
            parameter combination.
        """

        # we want explicit else's to make the logic easier to understand
        # pylint: disable=no-else-return, too-many-return-statements, too-many-branches, line-too-long

        def indexes_by_name():
            """Mapping series names to indexes in value groups."""
            return {f"{s[1].type}.{s[1].name}": s[0] for s in enumerate(self.specs)}

        def parse_timestamp(t):
            """Parse timestamps."""
            if timestamps == "datetime":
                return to_datetime(t)
            if timestamps == "epoch":
                return to_datetime(t).timestamp()
            return t

        def value_keys():
            for vg in self["values"].values():
                if vg and vg[0] is not None:
                    return vg[0].keys()
            raise ValueError("Unable to collect data, data appears to be empty.")

        # use all series if no series provided
        if not series:
            series = [s.series for s in self.specs]

        # single series
        if isinstance(series, str):
            # which index to pull from values?
            i = indexes_by_name()[series]

            # single value
            if isinstance(value, str):
                if not timestamps:
                    # iterate over all values, select value group at specific
                    # index v[i] and extract specific value [value]. The value
                    # group may be undefined (None), hence filter for value v[i]
                    return [v[i].get(value, None) for v in self["values"].values() if (len(v) > i and v[i])]
                else:
                    # like above, but include timestamps
                    return [
                        (parse_timestamp(k), v[i].get(value, None))
                        for k, v in self["values"].items()
                        if (len(v) > i and v[i])
                    ]

            # multiple values
            else:
                keys = value if value is not None else value_keys()
                if not timestamps:
                    # iterate over all values, select value group at specific
                    # index v[i] and extract all (min, count, ...) values. The value
                    # group may be undefined (None), hence filter for value v[i]
                    return [
                        tuple(v[i].get(key, None) for key in keys)
                        for v in self["values"].values()
                        if (len(v) > i and v[i])
                    ]
                else:
                    # like above, but include timestamps
                    return [
                        (parse_timestamp(k), *(v[i].get(key, None) for key in keys))
                        for k, v in self["values"].items()
                        if (len(v) > i and v[i])
                    ]

        # multiple series
        if isinstance(series, Sequence):
            ii = [indexes_by_name()[s] for s in series]

            # single value
            if isinstance(value, str):
                if not timestamps:
                    # iterate over all values, collect specified value groups
                    # at their index v[i] and extract specific value [value].
                    # The value group may be undefined (None) which will result
                    # in a None value in the tuple as well.
                    return [
                        # collect values of all indexes (None of not defined)
                        tuple(v[i].get(value, None) if (len(v) > i and v[i]) else None for i in ii)
                        for v in self["values"].values()
                    ]
                else:
                    # like above, but prepend with timestamps
                    return [
                        (parse_timestamp(k), *(v[i].get(value, None) if (len(v) > i and v[i]) else None for i in ii))
                        for k, v in self["values"].items()
                    ]

            # multiple values
            else:
                keys = value if value is not None else value_keys()
                if not timestamps:
                    # iterate over all values, collect specified value groups
                    # at their index v[i] and extract specific keys (min, count, ...).
                    # The value group may be undefined (None) which will result
                    # in a None value in the tuple as well.
                    return [
                        # collect values of all indexes (None of not defined)
                        tuple(
                            (tuple(v[i].get(key, None) for key in keys)) if (len(v) > i and v[i]) else None for i in ii
                        )
                        for v in self["values"].values()
                    ]
                else:
                    # like above, but prepend with timestamps
                    return [
                        (
                            parse_timestamp(k),
                            *(
                                tuple(v[i].get(key, None) for key in keys) if (len(v) > i and v[i]) else None
                                for i in ii
                            ),
                        )
                        for k, v in self["values"].items()
                    ]

        raise ValueError("Invalid combination of arguments")

    @staticmethod
    def _encode_name(n: str) -> str:
        """Encode a series name for use as a column name."""
        return re.sub(r'[ \\.+-]', '_', n)

    def to_numpy(
        self,
        series: str | None = None,
        value: str | None = None,
    ):
        """Build a NumPy array from a single series and value.

        All available data points/timestamps are included in the result.
        Missing values are represented as NaN, preserving alignment with other
        series extracted from the same object.

        Args:
            series (str):  Series name (e.g. 'c8y_Temperature.T'); can be
                omitted if this object holds only one series.
            value (str):  Value key to extract (e.g. 'min' or 'max'); can be
                omitted if the series holds only one value.

        Returns:
            A 1-dimensional NumPy array.

        See also: `to_series` and `to_dataframe` to convert multiple series
            and/or values into a Pandas Series/DataFrame optionally using the
            timestamps as index.
        """
        try:
            import numpy as np
        except ImportError as e:
            raise ImportError("numpy is required. Install with: pip install pyc8y[pandas]") from e

        if not series:
            if len(self.specs) > 1:
                raise ValueError(f"Series name must be specified if the data holds multiple series. Found {', '.join(x.series for x in self.specs)}.")
            series = self.specs[0].series

        series_index = {s.series: i for i, s in enumerate(self.specs)}.get(series, None)
        if series_index is None:
            raise KeyError(f"No such series: {series}. Available series are {', '.join(x.series for x in self.specs)}.")

        value_keys = next(
            (
                row[series_index].keys()
                for row in self["values"].values()
                if series_index < len(row) and row[series_index] is not None
            ),
            None,
        )
        if not value_keys:
            return np.empty(0)
        if not value:
            if len(value_keys) > 1:
                raise ValueError(f"Value must be specified if the data holds multiple values. Found {', '.join(value_keys)}.")
            value = value_keys[0]
        else:
            if value not in value_keys:
                raise KeyError(
                    f"No such series value: {value}. Available values are {', '.join(value_keys)}.")

        rows = list(self['values'].values())
        n = len(rows)

        return np.fromiter(
            (row[series_index].get(value, float('nan')) if (series_index < len(row) and row[series_index] is not None) else float('nan')
             for row in rows),
            dtype=float, count=n,
        )

    def to_dataframe(
        self,
        series: str | Sequence[str] = None,
        value: str | Sequence[str] | None = None,
        timestamps: bool | str = None,
    ):
        """Build a Pandas DataFrame from this Series object.

        All timestamps are included as rows; missing values for a series at a
        given timestamp are represented as NaN.

        Args:
            series (str|list):  A series name or list of series names; defaults
                to all available series. Names are used as column names (special
                characters replaced with underscores).
            value (str|list):  Value key or list of value keys to extract
                (e.g. 'min', 'max', or ['min', 'max']); if omitted all
                available value keys are extracted. Column names are suffixed
                with the value key when multiple values are extracted.
            timestamps (bool|str):  Use timestamps as the DataFrame index; use
                True for raw strings, 'datetime' for parsed datetimes, or
                'epoch' for epoch floats.

        Returns:
            A Pandas DataFrame.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("pandas is required. Install with: pip install pyc8y[pandas]") from e

        # ensure sequences
        series = [series] if isinstance(series, str) else series
        value = [value] if isinstance(value, str) else value
        selected: list[tuple[int, str]] = []   # selected indexed and series names

        index_by_name = {s.series: i for i, s in enumerate(self.specs)}
        if series:
            unknown = [x for x in series if x not in index_by_name]
            if unknown:
                raise KeyError(f"No such series: {', '.join(unknown)}. Available series are: {', '.join(index_by_name)}.")
            selected = [(index_by_name[x], x) for x in series]
        else:
            # select all
            selected = [(v, k) for k, v in index_by_name]

        rows = list(self.values.values())
        ts_strings = list(self.values.keys())

        if isinstance(value, str):
            value_keys = [value]
        elif isinstance(value, list):
            value_keys = value
        else:
            value_keys = next(
                (list(vg.keys()) for row in rows for vg in row if vg is not None),
                [],
            )

        if isinstance(value, (str, list)):
            available_keys = next(
                (list(vg.keys()) for row in rows for vg in row if vg is not None),
                [],
            )
            unknown_keys = [k for k in value_keys if k not in available_keys]
            if unknown_keys:
                raise KeyError(f"No such value key(s): {', '.join(unknown_keys)}. Available values are: {', '.join(available_keys)}.")

        columns = {}
        for idx, name in selected:
            base = self._encode_name(name)
            for key in value_keys:
                col = base if len(value_keys) == 1 else f'{base}_{key}'
                columns[col] = [
                    row[idx].get(key, None) if (idx < len(row) and row[idx] is not None) else None
                    for row in rows
                ]

        if timestamps == 'datetime':
            index = pd.to_datetime(ts_strings)
        elif timestamps == 'epoch':
            from datetime import datetime
            index = [datetime.fromisoformat(t).timestamp() for t in ts_strings]
        elif timestamps:
            index = ts_strings
        else:
            index = None

        return pd.DataFrame(columns, index=index)

    def to_series(
        self,
        series: str = None,
        value: str = 'min',
        timestamps: bool | str = None,
    ):
        """Build a Pandas Series from a single Cumulocity series.

        All timestamps are included; missing values are represented as NaN.

        Args:
            series (str):  Series name; can be omitted if this object holds
                only one series.
            value (str):  Value key to extract; defaults to 'min'.
            timestamps (bool|str):  Use timestamps as the index; use True for
                raw strings, 'datetime' for parsed datetimes, or 'epoch' for
                epoch floats.

        Returns:
            A Pandas Series.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("pandas is required. Install with: pip install pyc8y[pandas]") from e

        if not series:
            all_series = [s.series for s in self.specs]
            if len(all_series) > 1:
                raise ValueError(f"Multiple series found ({', '.join(all_series)}); specify one.")
            series = all_series[0]

        idx = {s.series: i for i, s in enumerate(self.specs)}[series]

        ts_strings = []
        values = []
        for ts, row in self['values'].items():
            ts_strings.append(ts)
            vg = row[idx] if idx < len(row) else None
            values.append(vg.get(value, float('nan')) if vg is not None else float('nan'))

        if timestamps == 'datetime':
            index = pd.to_datetime(ts_strings)
        elif timestamps == 'epoch':
            from datetime import datetime
            index = [datetime.fromisoformat(t).timestamp() for t in ts_strings]
        elif timestamps:
            index = ts_strings
        else:
            index = None

        return pd.Series(values, index=index, name=self._encode_name(series))


class Measurement(CumulocityObject):
    _meta = MeasurementsMeta

    def __init__(
        self,
        c8y: CumulocityRestClient | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        time: str | datetime = None,
        series: SeriesValue | Iterable[SeriesValue] | None = None,
        **kwargs,
    ):
        """Create a new Measurement object.

        Args:
            c8y (CumulocityRestApi)  Cumulocity connection reference; needs
                to be set for direct manipulation (create, delete)
            type (str)  Measurement type
            source (str)  Device ID which this measurement is for
            time(str|datetime):  Datetime string or Python datetime object. A
                given datetime string needs to be in standard ISO format incl.
                timezone: YYYY-MM-DD'T'HH:MM:SS.SSSZ as it is returned by the
                Cumulocity REST API. A given datetime object needs to be
                timezone aware. For manual construction it is recommended to
                specify a datetime object as the formatting of a timestring
                is never checked for performance reasons.
            kwargs:  All additional named arguments are interpreted as
                custom fragments e.g. for data points.

        Returns:
            Measurement object
        """
        super().__init__(c8y, **kwargs)
        self.type = type
        self.source = source
        self.time = time
        if series and is_series(series):
            series = (series,)
        for s in series or ():
            if len(s) not in (2, 3):
                raise ValueError("Series spec must 2 or 3 elements (name, value, unit).")
            name0, sep, name1 = s[0].partition(".")
            value_json = {"value": s[1]}
            if len(s) > 2:
                value_json["unit"] = s[2]  # noqa (type inference issue)
            self._staged_json.setdefault(name0, {})[name1] = value_json

    type = json_property("type")
    source = id_property("source")
    text = json_property("text")
    time = time_property("time")
    datetime = datetime_property("time")

    def get_series(self) -> Sequence[str]:
        """Collect series names.

        Collect series names defined in this measurement. Any top level fragment having a nested element
        featuring a _value_ field is considered a series. Multiple such series could be defined.

        ```json
        {
            "c8y_Temperature": {
                "T": {
                    "unit": "C",
                    "value": 12.8
                }
            }
        }
        ```

        Returns:
            A list of series names (e.g. `c8y_Temperature.T`) defined in this measurement.
        """
        return [
            f"{name0}.{name1}"
            for name0, value0 in self._json.items()
            if isinstance(value0, dict)
            for name1, value1 in value0.items()
            if isinstance(value1, dict) and "value" in value1
        ]

    async def create(self) -> Self:
        """Store the Measurement within the database.

        Returns:  A fresh Measurement object representing what was
            created within the database (including the ID).
        """
        return await self._create()


class Measurements(CumulocityResource[Measurement]):
    _meta = MeasurementsMeta
    _object_type = Measurement

    async def get(self, id: str) -> Measurement:
        """Get a Measurement by ID."""
        return await self._get(id)

    async def get_all(
        self,
        expression: str = None,
        *,
        type: str | None = None,
        source: str | None = None,
        value_fragment_type: str | None = None,
        value_fragment_series: str | None = None,
        series: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        reverse: bool | None = None,
        limit: int = None,
        page_size: int = 1000,
        page_number: int = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> list[Measurement | Any | tuple[Any]]:
        """Query the database for measurements and return the results
        as list.

        This function is a greedy version of the select function. All
        available results are read immediately and returned as list.

        Returns:
            List of matching Measurement objects or values/value
                tuples if the `as_values` parameter is defined.
        """
        return [
            x
            async for x in self.select(
                expression=expression,
                type=type,
                source=source,
                value_fragment_type=value_fragment_type,
                value_fragment_series=value_fragment_series,
                series=series,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                reverse=reverse,
                limit=limit,
                page_size=page_size,
                page_number=page_number,
                as_values=as_values,
                workers=workers,
                **kwargs,
            )
        ]

    async def get_count(
        self,
        expression: str = None,
        *,
        type: str | None = None,
        source: str | None = None,
        value_fragment_type: str | None = None,
        value_fragment_series: str | None = None,
        series: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ) -> int:
        """Calculate the number of potential results of a database query.

        This function uses the same parameters as the `select` function.

        Returns:
            Number of potential results
        """
        series_type, series_value = self._collate_series_params(
            series=series,
            value_fragment_type=value_fragment_type,
            value_fragment_series=value_fragment_series,
        )
        params = map_params(
            type=type,
            source=source,
            valueFragmentType=series_type,
            valueFragmentSeries=series_value,
            before=before,
            after=after,
            date_from=date_from,
            date_to=date_to,
            min_age=min_age,
            max_age=max_age,
            page_size=1,
            **kwargs,
        )
        return await self._get_count(expression=expression, params=params)

    async def get_last(
        self,
        expression: str = None,
        *,
        type: str = None,
        source: str = None,
        value_fragment_type: str = None,
        value_fragment_series: str = None,
        series: str = None,
        date_to: str | datetime = None,
        before: str | datetime = None,
        min_age: timedelta = None,
        as_values: AsValuesSpec | None = None,
        **kwargs,
    ) -> Measurement | None:
        """Query the database and return the last matching measurement.

        This function is a special variant of the select function. Only
        the last matching result is returned.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            value_fragment_type (str):  The series' value fragment name
                (e.g. c8y_Environment)
            value_fragment_series (str):  The series' name (within the
                value fragment, e.g. Temperature)
            series (str):  Full name of a present series within a value
                fragment e.g. "c8y_Environment.Temperature"
            before (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time before this date are
                returned.
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Timedelta object. Only measurements of
                at least this age are returned.
            as_values: (*str|tuple):  Don't parse object, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.
        Returns:
            Last matching Measurement object or values/value tuples if the
                `as_values` parameter is defined.
        """
        series_type, series_value = self._collate_series_params(
            series=series,
            value_fragment_type=value_fragment_type,
            value_fragment_series=value_fragment_series,
        )
        # we need at least one date parameter
        after = None
        if all(x is None for x in [date_to, before, min_age]):
            after = "1970-01-01"

        params = map_params(
            type=type,
            source=source,
            valueFragmentType=series_type,
            valueFragmentSeries=series_value,
            before=before,
            after=after,
            date_to=date_to,
            min_age=min_age,
            page_size=1,
            **kwargs,
        )
        return await self._get_last(expression=expression, params=params, as_values=as_values)

    def select(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        value_fragment_type: str | None = None,
        value_fragment_series: str | None = None,
        series: str | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        reverse: bool | None = None,
        limit: int | None = None,
        page_size: int | None = 1000,
        page_number: int | None = None,
        as_values: AsValuesSpec | None = None,
        workers: int | None = None,
        **kwargs,
    ) -> AsyncIterator[Measurement | Any | tuple[Any]]:
        """Query the database for measurements and iterate over the results.

        This function is implemented in a lazy fashion - results will only be
        fetched from the database as long there is a consumer for them.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification.  Filters can be
        combined (within reason).

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            value_fragment_type (str):  The series' value fragment name
                (e.g. c8y_Environment)
            value_fragment_series (str):  The series' name (within the
                value fragment, e.g. Temperature)
            series (str):  Full name of a present series within a value
                fragment e.g. "c8y_Environment.Temperature"
            before (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time before this date are
                returned.
            after (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time after this date are
                returned.
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Timedelta object. Only measurements of
                at least this age are returned.
            max_age (timedelta):  Timedelta object. Only measurements with
                at most this age are returned.
            reverse (bool):  Invert the order of results, starting with the
                most recent one.
            limit (int):  Limit the number of results to this number.
            page_size (int):  Define the number of measurements which are
                read (and parsed in one chunk). This is a performance
                related setting.
            page_number (int): Pull a specific page; this effectively disables
                automatic follow-up page retrieval.
            as_values: (*str|tuple):  Don't parse objects, but directly extract
                the values at certain JSON paths as tuples; If the path is not
                defined in a result, None is used; Specify a tuple to define
                a proper default value for each path.

        Returns:
            Async iterator for matching Measurement objects or values/value
                tuples if the `as_values` parameter is defined.
        """
        params = ()
        if not expression:
            series_type, series_value = self._collate_series_params(
                series=series,
                value_fragment_type=value_fragment_type,
                value_fragment_series=value_fragment_series,
            )
            params = map_params(
                type=type,
                source=source,
                valueFragmentType=series_type,
                valueFragmentSeries=series_value,
                before=before,
                after=after,
                date_from=date_from,
                date_to=date_to,
                min_age=min_age,
                max_age=max_age,
                reverse=reverse,
                page_size=page_size,
                **kwargs,
            )
        return super()._iterate(
            expression=expression,
            params=params,
            page_number=page_number,
            limit=limit,
            as_values=as_values,
            workers=workers,
        )

    async def get_series(
        self,
        expression: str = None,
        *,
        source: str = None,
        aggregation: str = None,
        aggregation_function: str | Sequence[str] = None,
        aggregation_interval: str = None,
        series: str | Sequence[str] = None,
        before: str | datetime = None,
        after: str | datetime = None,
        min_age: timedelta = None,
        max_age: timedelta = None,
        reverse: bool = None,
        **kwargs,
    ) -> Series:
        """Query the database for a list of series and their values.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            source (str):  Database ID of a source device
            aggregation (str):  Aggregation type
            aggregation_function (str):  Aggregation function, e.g. "min",
                "max", "avg", "sum", "count". Needs aggregation_interval.
            aggregation_interval (str):  Aggregation interval for the
                aggregation function.
            series (str|Sequence[str]):  Series' to query
            before (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time before this date are
                included.
            after (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time after this date are
                included.
            min_age (timedelta):  Timedelta object. Only measurements of
                at least this age are included.
            max_age (timedelta):  Timedelta object. Only measurements with
                at most this age are included.
            reverse (bool):  Invert the order of results, starting with the
                most recent one.

        Returns:
            A Series object which wraps the raw JSON result but can also be
            used to conveniently collect the series' values.

        See also: https://cumulocity.com/api/core/#operation/getMeasurementSeriesResource
        """
        resource_path = f"{self.resource_path}/series"
        if expression:
            response_json = await self.c8y.get(f"{resource_path}?{expression}")
        else:
            params = map_params(
                source=source,
                aggregationType=aggregation,  # this is a non-mapped parameter
                aggregationInterval=aggregation_interval,  # this is a non-mapped parameter
                aggregation_function=aggregation_function,  # this needs special list handling
                series=series,
                before=before,
                after=after,
                min_age=min_age,
                max_age=max_age,
                reverse=reverse,
                **kwargs,
            )
            response_json = await self.c8y.get(resource_path, params=params, accept="application/json")
        return Series(response_json)

    async def collect_series(
        self,
        expression: str | None = None,
        *,
        source: str | None = None,
        aggregation: str | None = None,
        series: str | Sequence[str] | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        reverse: bool | None = None,
        value: str | None = None,
        timestamps: bool | str | None = None,
        **kwargs,
    ):
        """Query the database for series values.

        This function is functionally the same as using the `get_series` function
        with an immediate `collect` on the result.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            source (str):  Database ID of a source device
            aggregation (str):  Aggregation type
            series (str|Sequence[str]):  Series' to query and collect; If
                multiple series are collected each element in the result will
                be a tuple. If omitted, all available series are collected.
            before (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time before this date are
                included.
            after (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time after this date are
                included.
            min_age (timedelta):  Timedelta object. Only measurements of
                at least this age are included.
            max_age (timedelta):  Timedelta object. Only measurements with
                at most this age are included.
            reverse (bool):  Invert the order of results, starting with the
                most recent one.
            value (str):  Which value (min/max) to collect. If omitted, both
                values will be collected, grouped as 2-tuples.
            timestamps (bool|str):  Whether each element in the result list will
                be prepended with the corresponding timestamp. If True, the
                timestamp string will be included; Use 'datetime' or 'epoch' to
                parse the timestamp string.

        Returns:
            A simple list or list of tuples (potentially nested) depending on the
            parameter combination.

        See also: https://cumulocity.com/api/core/#operation/getMeasurementSeriesResource
        """
        result = await self.get_series(
            expression=expression,
            source=source,
            aggregation=aggregation,
            series=series,
            before=before,
            after=after,
            min_age=min_age,
            max_age=max_age,
            reverse=reverse,
            **kwargs,
        )
        return result.collect(series=series, value=value, timestamps=timestamps)

    async def create(self, *objects: Measurement, workers: int | None = None) -> None:
        await self._create(*objects, workers=workers)

    async def delete(self, *objects: str | Measurement, workers: int | None = None) -> None:
        await self._delete(*objects, workers=workers)

    async def delete_by(
        self,
        expression: str | None = None,
        *,
        type: str | None = None,
        source: str | None = None,
        value_fragment_type: str | None = None,  # todo: this is not supported at the moment
        value_fragment_series: str | None = None,  # todo: this is not supported at the moment
        series: str | None = None,  # todo: this is not supported at the moment
        fragment: str | None = None,
        date_from: str | datetime | None = None,
        date_to: str | datetime | None = None,
        before: str | datetime | None = None,
        after: str | datetime | None = None,
        min_age: str | timedelta | None = None,
        max_age: str | timedelta | None = None,
        **kwargs,
    ):
        """Query the database and delete matching measurements.

        All parameters are considered to be filters, limiting the result set
        to objects which meet the filters specification.  Filters can be
        combined (within reason).

        Note: In Cumulocity, measurements are deleted asynchronously by design.

        Args:
            expression (str):  Arbitrary filter expression which will be
                passed to Cumulocity without change; all other filters
                are ignored if this is provided
            type (str):  Alarm type
            source (str):  Database ID of a source device
            value_fragment_type (str):  The series' value fragment name
                (e.g. c8y_Environment)
            value_fragment_series (str):  The series' name (within the
                value fragment, e.g. Temperature)
            series (str):  Full name of a present series within a value
                fragment e.g. "c8y_Environment.Temperature"
            fragment (str):  Name of a present custom/standard fragment
            before (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time before this date are
                returned.
            after (datetime|str):  Datetime object or ISO date/time string.
                Only measurements assigned to a time after this date are
                returned.
            date_from (str|datetime): Same as `after`
            date_to (str|datetime): Same as `before`
            min_age (timedelta):  Timedelta object. Only measurements of
                at least this age are returned.
            max_age (timedelta):  Timedelta object. Only measurements with
                at most this age are returned.
        """
        if expression:
            await self.c8y.delete(f"{self.resource_path}/?{expression}")
        else:
            series_type, series_value = self._collate_series_params(
                series=series,
                value_fragment_type=value_fragment_type,
                value_fragment_series=value_fragment_series,
            )
            params = map_params(
                type=type,
                source=source,
                fragmentType=fragment,
                valueFragmentType=series_type,
                valueFragmentSeries=series_value,
                date_from=date_from,
                date_to=date_to,
                before=before,
                after=after,
                min_age=min_age,
                max_age=max_age,
                **kwargs,
            )
            await self.c8y.delete(self.resource_path, params=params)

    @staticmethod
    def _collate_series_params(
        series: str | None = None,
        value_fragment_type: str | None = None,
        value_fragment_series: str | None = None,
    ) -> (str, str):
        if series and (value_fragment_type or value_fragment_series):
            raise ValueError(
                "Series parameter must not be combined with 'value_fragment_type' or 'value_fragment_series'."
            )
        if series:
            parts = series.split(".")
            if len(parts) != 2:
                raise ValueError("Series spec must have exactly two parts.")
            return parts[0], parts[1]
        return value_fragment_type, value_fragment_series
