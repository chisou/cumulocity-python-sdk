# Copyright (c) 2026 Christoph Souris

import random
from datetime import datetime, timedelta, timezone

import logging
import time
from typing import List

import pytest

from pyc8y.base_util import is_sequence, ensure_sequence
from pyc8y.client import CumulocityClient
from pyc8y.model import Device, Measurement, Series, Value, Kelvin, Count
from pyc8y.model.measurement import AggregationType

from util.testing_util import create_random_name


def get_ids(ms: List[Measurement]) -> List[str]:
    """Isolate the ID from a list of measurements."""
    return [m.id for m in ms]


@pytest.fixture(scope="module", name="measurement_factory")
async def fix_measurement_factory(live_c8y: CumulocityClient, module_factory):
    """Provide a factory function to create measurements that are cleaned
    up after the session if needed."""

    created_devices = []

    async def factory_fun(n: int, device=None, type=None, series=None) -> List[Measurement]:
        type = type or create_random_name()
        series = series or type

        # 1) create device
        if not device:
            device = await module_factory(Device(c8y=live_c8y, type=f"{type}_device", name=type, test_marker={"name": type}))
            created_devices.append(device)
            logging.info(f"Created device #{device.id}")

        # 2) create measurements
        ms = []
        now = time.time()
        for i in range(0, n):
            measurement_time = datetime.fromtimestamp(now - i*60, timezone.utc)
            m = Measurement(c8y=live_c8y, type=type, source=device.id, time=measurement_time)
            # m[series] = {series: Value(random.randint(1000, 9999), '#')}
            m[series] = {"series": Value(random.randint(1000, 9999), "#")}
            m["marker"] = {"id": f"{device.id}_{type}_{series}_{i}"}
            await m.create()
            logging.info(f"Created measurement #{m.id}: {m.json}")
            ms.append(m)
        return ms

    yield factory_fun


async def test_select(live_c8y: CumulocityClient, measurement_factory):
    """Verify that selection works as expected."""
    # pylint: disable=too-many-statements)

    name = create_random_name()
    other_name = f"other_{name}"

    # create a couple of measurements (at a new device)
    created_ms = await measurement_factory(10, type=name, series=name)

    # create a couple of measurements with different source
    source_ms = await measurement_factory(10, type=name, series=name)

    # create a couple of measurements with different type name
    device_id = created_ms[0].source
    device = await live_c8y.device_inventory.get(created_ms[0].source)
    type_ms = await measurement_factory(10, device=device, type=other_name, series=name)

    # create a couple of measurements with different series name
    series_ms = await measurement_factory(10, device=device, type=name, series=other_name)

    # (1) all measurement collections can be selected separately

    # select by source
    same_source_ms = await live_c8y.measurements.get_all(source=device_id, limit=100)
    assert len({x.source for x in same_source_ms}) == 1
    assert len({x.type for x in same_source_ms}) == 2
    assert len({x.get_series()[0] for x in same_source_ms}) == 2
    assert len(same_source_ms) == len(created_ms) + len(type_ms) + len(series_ms)

    # select by type
    same_type_ms = await live_c8y.measurements.get_all(limit=None, type=name)
    assert len({x.source for x in same_type_ms}) == 2
    assert len({x.type for x in same_type_ms}) == 1
    assert len({x.get_series()[0] for x in same_type_ms}) == 2
    assert len(same_type_ms) == len(created_ms) + len(source_ms) + len(series_ms)

    # select by series
    same_series_ms = await live_c8y.measurements.get_all(limit=None, value_fragment_type=name)
    assert len({x.source for x in same_series_ms}) == 2
    assert len({x.type for x in same_series_ms}) == 2
    assert len({x.get_series()[0] for x in same_series_ms}) == 1
    assert len(same_series_ms) == len(created_ms) + len(source_ms) + len(type_ms)

    # skim latest
    skim_result = await live_c8y.measurements.skim_latest(source=device_id)
    # -> one of each type
    assert set(skim_result.keys()) == {name, other_name}
    # -> always return the latest of each
    assert skim_result[name].id == max(created_ms + series_ms, key=lambda m: m.time).id
    assert skim_result[other_name].id == max(type_ms, key=lambda m: m.time).id

    # (2) Testing deletion

    # Delete all with same source and type (fragment is not supported)
    # This would also include the ones having a different series name
    await live_c8y.measurements.delete_by(source=device_id, type=name)
    # wait for the deletion to be executed
    n = 10
    while True:
        if not await live_c8y.measurements.get_count(source=device_id, type=name):
            break
        n = n-1
        time.sleep(1 * (10-n))
    assert not await live_c8y.measurements.get_last(source=device_id, type=name)

    # -> there should still be similar measurements at a different device
    other_source_ms = await live_c8y.measurements.get_all(limit=None, type=name, value_fragment_type=name)
    assert len(other_source_ms) == len(source_ms)
    # -> there should still be differently typed measurements for the same source
    other_type_ms = await live_c8y.measurements.get_all(limit=None, source=device_id, type=other_name)
    assert len(other_type_ms) == len(type_ms)

    # Delete by type (don't care about the source)
    now = datetime.now(timezone.utc)
    now_truncated = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
    await live_c8y.measurements.delete_by(type=name, date_to=now_truncated)
    # wait for the deletion to be executed
    n = 10
    while True:
        if not await live_c8y.measurements.get_count(type=name):
            break
        n = n-1
        time.sleep(1 * (10-n))
    assert not await live_c8y.measurements.get_last(type=name)

    # -> we should still see some with the other type
    other_type_ms = await live_c8y.measurements.get_all(limit=None, type=other_name, before=now_truncated)
    assert len(other_type_ms) == len(type_ms)

    # Delete remaining measurements
    await live_c8y.measurements.delete_by(type=other_name, date_to=now_truncated)
    # wait for the deletion to be executed
    n = 10
    while True:
        if not await live_c8y.measurements.get_count(type=other_name):
            break
        n = n-1
        time.sleep(1 * (10-n))
    assert not await live_c8y.measurements.get_last(type=other_name)

    # -> no measurements should be left
    sources = [created_ms[0].source, source_ms[1].source]
    for source in sources:
        assert not await live_c8y.measurements.get_count(source=source)


async def test_get_last(live_c8y: CumulocityClient, measurement_factory):
    """Verify that get_last returns the most recent matching measurement."""
    created_ms = await measurement_factory(5)
    device_id = created_ms[0].source
    type_name = created_ms[0].type

    last = await live_c8y.measurements.get_last(source=device_id, type=type_name)

    assert last is not None
    assert last.id == created_ms[0].id


async def test_single_page_select(live_c8y: CumulocityClient, measurement_factory):
    """Verify that selection works as expected."""
    # create a couple of measurements
    created_ms = await measurement_factory(50)
    created_ids = [m.id for m in created_ms]
    device_id = created_ms[0].source

    # select all measurements using different page sizes
    selected_ids = [m.id async for m in live_c8y.measurements.select(limit=None, source=device_id, page_size=10, page_number=2)]

    # -> all created measurements should be in the selection
    assert len(selected_ids) == 10
    assert all(i in set(created_ids) for i in selected_ids)


@pytest.fixture(scope="session", name="sample_series_device")
async def fix_sample_series_device(live_c8y: CumulocityClient, session_device: Device) -> Device:
    """Add measurement series to the sample device."""
    # create 12K measurements, 2 every minute
    start_time = datetime.fromisoformat("2020-01-01 00:00:00+00:00")
    ms_iter = [Measurement(type="c8y_TestMeasurement",
                           source=session_device.id,
                           time=start_time + (i * timedelta(seconds=30)),
                           c8y_Iteration={"c8y_Counter": Count(i)},
                           ) for i in range(0, 1000)]
    ms_temps = [Measurement(type="c8y_TestMeasurement",
                            source=session_device.id,
                            time=start_time + (i * timedelta(seconds=100)),
                            c8y_Temperature={"c8y_AverageTemperature": Kelvin(i * 0.2)},
                            ) for i in range(0, 1000)]
    await live_c8y.measurements.create(*ms_iter, workers=50)
    await live_c8y.measurements.create(*ms_temps, workers=50)

    session_device["c8y_SupportedSeries"] = [
        "c8y_Temperature.c8y_AverageTemperature",
        "c8y_Iteration.c8y_Counter"]
    return await session_device.update()


@pytest.fixture(name="unaggregated_series_result", scope="session")
async def fix_unaggregated_series_result(live_c8y: CumulocityClient, sample_series_device: Device) -> Series:
    """Provide an unaggregated series result."""
    start_time = datetime.fromisoformat("2020-01-01 00:00:00+00:00")
    return await live_c8y.measurements.get_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        after=start_time, before="now"
    )


@pytest.fixture(name="aggregated_series_result", scope="session")
async def fix_aggregated_series_result(live_c8y: CumulocityClient, sample_series_device: Device) -> Series:
    """Provide an aggregated series result."""
    start_time = datetime.fromisoformat("2020-01-01 00:00:00+00:00")
    return await live_c8y.measurements.get_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        aggregation=AggregationType.HOURLY,
        after=start_time, before="now"
    )

@pytest.fixture(name="new_aggregated_series_result", scope="session")
async def fix_new_aggregated_series_result(live_c8y: CumulocityClient, sample_series_device: Device) -> Series:
    """Provide an aggregated series result."""
    start_time = datetime.fromisoformat("2020-01-01 00:00:00+00:00")
    return await live_c8y.measurements.get_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        aggregation_function=["min", "max"],
        aggregation_interval="1h",
        after=start_time, before="now"
    )

@pytest.mark.parametrize("name", ["aggregated", "unaggregated", "new_aggregated"])
@pytest.mark.asyncio(loop_scope="session")
async def test_collect_single_series(name, aggregated_series_result, unaggregated_series_result, new_aggregated_series_result):
    """Verify that collecting a single value (min or max) from a
    series works as expected."""
    series_result = {
        "aggregated": aggregated_series_result,
        "unaggregated": unaggregated_series_result,
        "new_aggregated": new_aggregated_series_result,
    }[name]
    for spec in series_result.specs:
        values = series_result.values_of(series=spec.series, value="min")
        # -> None values should be filtered out
        assert values
        assert all(v is not None for v in values)
        # -> Values should all have the same type
        # pylint: disable=unidiomatic-typecheck
        assert all(type(a) is type(b) for a, b in zip(values, values[1:]))
        # -> Values should be increasing continuously
        assert all(a<b for a,b in zip(values, values[1:]))


@pytest.mark.parametrize("name", ["aggregated", "unaggregated", "new_aggregated"])
@pytest.mark.asyncio(loop_scope="session")
async def test_collect_multiple_series(name, aggregated_series_result, unaggregated_series_result, new_aggregated_series_result):
    """Verify that collecting a single value (min or max) for multiple
    series works as expected."""
    series_result = {
        "aggregated": aggregated_series_result,
        "unaggregated": unaggregated_series_result,
        "new_aggregated": new_aggregated_series_result,
    }[name]
    series_names = [s.series for s in series_result.specs]
    values = series_result.collect(series=series_names, value="min")
    assert values
    # -> Each element should be an n-tuple (n as number of series)
    assert all(isinstance(v, tuple) for v in values)
    assert all(len(v) == len(series_names) for v in values)
    # -> Each value within the n-tuple belongs to one series
    #    There will be None values (when a series does not define a value
    #    at that timestamp). All actual values will have the same type.
    assert any(any(e is None for e in v) for v in values)
    for i in range(0, len(series_names)):
        actual_values = [v[i] for v in values if v[i] is not None]
        assert all(isinstance(v, type(actual_values[0])) for v in actual_values)


async def test_get_and_collect_series(live_c8y, sample_series_device):
    """Verify that get & collect works as expected."""
    series = await live_c8y.measurements.get_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        aggregation=AggregationType.HOURLY,
        after="1970-01-01",
        before="now"
    )

    # multiple series
    collected = series.collect(sample_series_device["c8y_SupportedSeries"])
    directly_collected = await live_c8y.measurements.collect_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        aggregation=AggregationType.HOURLY,
        after="1970-01-01",
        before="now"
    )
    assert collected == directly_collected

    # single series
    for series_name in sample_series_device["c8y_SupportedSeries"]:
        collected = series.collect(series_name)
        directly_collected = await live_c8y.measurements.collect_series(
            source=sample_series_device.id,
            series=series_name,
            aggregation=AggregationType.HOURLY,
            after="1970-01-01",
            before="now"
        )
        # we have to filter None rows because pulling a single series would do the same
        assert [x for x in collected if x[0] is not None] == directly_collected


@pytest.mark.parametrize("aggregation_function", [
    "min",
    ["max", "avg"],
    ("avg", "sum", "count"),
], ids=["min", "max-avg", "max-sum-count"])
async def test_new_aggregation_single(live_c8y: CumulocityClient, sample_series_device: Device, aggregation_function):
    """Verify that the new aggregation functions work as expected."""
    for series_name in sample_series_device["c8y_SupportedSeries"]:
        series = await live_c8y.measurements.get_series(
            source=sample_series_device.id,
            series=series_name,
            aggregation_function=aggregation_function,
            aggregation_interval="1h",
            after="1970-01-01",
            before="now"
        )

        # collect all functions
        collected = series.collect(value=aggregation_function)
        # -> each element is a tuple (of all queried series)
        num_values = len(ensure_sequence(aggregation_function))
        assert isinstance(collected[0], tuple)
        assert all(len(x) == num_values for x in collected)
        # -> each tuple holds the values of all aggregation function
        assert isinstance(collected[0][0], float)
        assert all(isinstance(x[y], float) for y in range(num_values) for x in collected)
        # collect individual function results
        aggregation_function = [aggregation_function] if isinstance(aggregation_function, str) else aggregation_function
        for fun in aggregation_function:
            collected = series.values_of(series=series_name, value=fun)
            # -> the values are held directly
            assert isinstance(collected[0], float)


@pytest.mark.parametrize("aggregation_function", [
    "min",
    ["max", "avg"],
    ("avg", "sum", "count"),
],ids=["min", "max-avg", "max-sum-count"])
async def test_new_aggregation_multi(live_c8y: CumulocityClient, sample_series_device: Device, aggregation_function):
    """Verify that the new aggregation functions work as expected."""
    series = await live_c8y.measurements.get_series(
        source=sample_series_device.id,
        series=sample_series_device["c8y_SupportedSeries"],
        aggregation_function=aggregation_function,
        aggregation_interval="1h",
        after="1970-01-01",
        before="now"
    )

    # collect all functions
    collected = series.collect(value=aggregation_function, timestamps="datetime")
    # -> each element is a tuple (of all queried series times aggregation functions plus 1 for the timestamp)
    num_values = len(series.specs) * len(ensure_sequence(aggregation_function)) + 1
    assert isinstance(collected[0], tuple)
    assert all(len(x) == num_values for x in collected)
    # -> each "row" holds the values of all aggregation function
    assert isinstance(collected[0][0], datetime)  # timestamp
    assert isinstance(collected[0][1], float)  # aggregated value
    assert all(isinstance(x[y], float | None) for y in range(1, num_values) for x in collected)

    # collect individual function results
    aggregation_function = [aggregation_function] if isinstance(aggregation_function, str) else aggregation_function
    for series_name in sample_series_device["c8y_SupportedSeries"]:
        for fun in aggregation_function:
            collected = series.values_of(series=series_name, value=fun)
            # -> the values are held directly
            assert isinstance(collected[0], float)

    # collect multiple individual function results
    if is_sequence(aggregation_function) and len(aggregation_function) > 2:
        subsets = [
            [aggregation_function[0], aggregation_function[1]],
            [aggregation_function[1], aggregation_function[2]],
            [aggregation_function[0], aggregation_function[2]],
        ]

        for series_name in sample_series_device["c8y_SupportedSeries"]:
            for subset in subsets:
                collected = series.collect(series=series_name, value=subset)
                # -> each row contains 2 values
                assert isinstance(collected[0], tuple)
                assert len(collected[0]) == 2

