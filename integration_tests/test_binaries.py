# Copyright (c) 2026 Christoph Souris

import os
from tempfile import NamedTemporaryFile

import pytest

from pyc8y.client import CumulocityClient
from pyc8y.model.binary import Binary
from pyc8y.model.matcher import field

import coolname


def create_random_text() -> str:
    return " ".join([x for y in [coolname.generate(3) for _ in range(30)] for x in y])


@pytest.fixture(scope="session")
def file_factory(logger):
    """Provide a file factory which creates test files and deletes them
    after the session."""
    created_files = []

    def create_file() -> (str, str):
        data = create_random_text()
        file = NamedTemporaryFile(delete=False)
        file.write(bytes(data, "utf-8"))
        file.close()
        logger.info(f"Created temporary file: {file.name}")
        created_files.append(file.name)
        return file.name, data

    yield create_file

    for f in created_files:
        os.remove(f)
        logger.info(f"Removed temporary file: {f}")


async def test_CRUD(live_c8y: CumulocityClient, file_factory):
    """Verify that object based create, update, and delete works as expected."""

    file1_name, file1_data = file_factory()
    file2_name, file2_data = file_factory()
    binary = Binary(live_c8y, name="some_file.py", type="text/raw", file=file1_name, custom_attribute=False)

    await binary.create()
    try:
        assert binary.id
        assert binary.is_binary
        assert binary["c8y_IsBinary"] is not None
        assert binary["custom_attribute"] is False
        assert binary.content_type == binary.type
        assert binary.length == len(file1_data)

        assert file1_data == (await binary.read_file()).content.decode("utf-8")

        assert await live_c8y.binaries.get_count(type="text/raw") >= 1
        assert binary.id in await live_c8y.binaries.get_all(type="text/raw", limit=100, as_values="id")
        assert binary.id, len(file1_data) == (await live_c8y.binaries.get_all(
            type="text/raw", limit=100, as_values=["id", "length"], include=field("id", binary.id)))[0]

        binary.file = file2_name
        binary.content_type = "text/text"
        binary["custom_attribute"] = True
        await binary.update()
        new_data = (await binary.read_file()).content.decode("utf-8")
        assert new_data == file2_data

        await binary.delete()
        with pytest.raises(KeyError):
            await live_c8y.binaries.read_file(binary.id)

    except Exception:
        await binary.delete()
        raise


async def test_CRUD2(live_c8y: CumulocityClient, file_factory):
    """Verify that API based create, update, and delete works as expected."""

    file1_name, file1_data = file_factory()
    file2_name, file2_data = file_factory()

    created = await live_c8y.binaries.upload(file=file1_name, name="test.txt", type="text/raw")
    try:
        assert created.id
        assert created.is_binary
        assert created["c8y_IsBinary"] is not None
        assert created.content_type == created.type
        assert created.length == len(file1_data)

        content, filename = await live_c8y.binaries.read_file(created.id)
        assert content.decode("utf-8") == file1_data
        assert filename == "test.txt"

        await live_c8y.binaries.update(created.id, file=file2_name)

        content, _ = await live_c8y.binaries.read_file(created.id)
        assert content.decode("utf-8") == file2_data

    finally:
        await live_c8y.binaries.delete(created.id)
