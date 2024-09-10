import pytest

from pathlib import Path
from renode_ws_proxy.filesystem import FileSystemState


@pytest.fixture
def tmp_fs(tmp_path: Path):
    return FileSystemState(str(tmp_path))


def test_replace_analyzer(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.resc"
    test_data = b"""
foo
showAnalyzer bar
baz
    """
    test_full_path = tmp_path / test_file
    test_full_path.write_bytes(test_data)

    after_replacement = b"""
foo
emulation CreateServerSocketTerminal 29172 "term"; connector Connect bar term
baz
    """

    result = tmp_fs.replace_analyzer(test_file)

    assert result["success"]
    assert test_full_path.read_bytes() == after_replacement


def test_download_extract_zip(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / test_file

    example_zip = Path(__file__).parent / "example.zip"

    url = f"file://{example_zip}"

    assert not test_full_path.exists()

    result = tmp_fs.download_extract_zip(url)

    assert result["success"]
    assert result["path"] == str(tmp_path)
    assert test_full_path.exists()
    assert test_full_path.read_bytes() == test_data


def test_fetch_from_url(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / "testdir" / test_file
    test_full_path.parent.mkdir()
    test_full_path.write_bytes(test_data)

    test_actual_path = tmp_path / test_file

    url = f"file://{test_full_path}"
    result = tmp_fs.fetch_from_url(url)

    assert result["success"]
    assert result["path"] == str(test_actual_path)
    assert test_actual_path.read_bytes() == test_data


def test_list(tmp_path: Path, tmp_fs: FileSystemState):
    test_files = [
        "foo.txt",
        "bar.txt",
        "baz.txt",
    ]

    for file in test_files:
        p = tmp_path / file
        p.touch()

    result = tmp_fs.list("/")

    result_files = [next(f for f in result if f["name"] == file) for file in test_files]
    assert len(result_files) == len(test_files)
    assert all(f is not None for f in result_files)
    assert all(f["isfile"] and not f["islink"] for f in result_files)


def test_stat_file(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / test_file
    test_full_path.write_bytes(test_data)

    result = tmp_fs.stat(test_file)

    assert result["success"]
    assert result["size"] == len(test_data)
    assert result["isfile"]


def test_stat_dir(tmp_path: Path, tmp_fs: FileSystemState):
    test_dir = "foo"
    test_full_path = tmp_path / test_dir
    test_full_path.mkdir()

    result = tmp_fs.stat(test_dir)

    assert result["success"]
    assert not result["isfile"]


def test_download(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / test_file
    test_full_path.write_bytes(test_data)

    result = tmp_fs.download(test_file)

    assert result["success"]
    assert result["data"] == test_data


def test_upload(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "bar.txt"
    test_data = b"Bye"
    test_full_path = tmp_path / test_file

    assert not test_full_path.exists()

    result = tmp_fs.upload(test_file, test_data)

    assert result["success"]
    assert result["path"] == str(test_full_path)
    assert test_full_path.read_bytes() == test_data


def test_remove(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_full_path = tmp_path / test_file
    test_full_path.touch()

    assert test_full_path.exists()

    result = tmp_fs.remove(test_file)

    assert result["success"]
    assert result["path"] == str(test_full_path)
    assert not test_full_path.exists()


def test_move(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / test_file
    test_full_path.write_bytes(test_data)

    other_file = "bar.txt"
    other_full_path = tmp_path / other_file

    result = tmp_fs.move(test_file, other_file)

    assert result["success"]
    assert result["from"] == str(test_full_path)
    assert result["to"] == str(other_full_path)
    assert not test_full_path.exists()
    assert other_full_path.read_bytes() == test_data


def test_copy(tmp_path: Path, tmp_fs: FileSystemState):
    test_file = "foo.txt"
    test_data = b"Hello"
    test_full_path = tmp_path / test_file
    test_full_path.write_bytes(test_data)

    other_file = "bar.txt"
    other_full_path = tmp_path / other_file

    result = tmp_fs.copy(test_file, other_file)

    assert result["success"]
    assert result["from"] == str(test_full_path)
    assert result["to"] == str(other_full_path)
    assert test_full_path.exists()
    assert other_full_path.read_bytes() == test_data


def test_mkdir(tmp_path: Path, tmp_fs: FileSystemState):
    test_dir = "foo"
    test_full_path = tmp_path / test_dir

    assert not test_full_path.exists()

    result = tmp_fs.mkdir(test_dir)

    assert result["success"]
    assert test_full_path.exists()
    assert test_full_path.is_dir()
