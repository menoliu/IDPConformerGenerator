"""Test I/O lib."""
import pytest

from idpconfgen import Path
from idpconfgen.libs import libio


test_folder = Path(__file__).parents[0]


def test_concatenate_1():
    """Test concatenate entries."""
    user_input = [
        'IDDXCH',
        'somefile_that_does_not_exist.list',
        Path(test_folder, 'data', 'pdblist.list').str(),
        Path(test_folder, 'data', 'pdblist.list'),
        ]

    expected_output = [
        'IDDXCH',
        'somefile_that_does_not_exist.list',
        '123A\n',
        '123AB\n',
        '123ABC\n',
        '123A90\n',
        '# some comment line\n',
        '123A\n',
        '123AB\n',
        '123ABC\n',
        '123A90\n',
        '# some comment line\n',
        ]

    output = libio.concatenate_entries(user_input)

    assert expected_output == output


def test_concatenate_typerror_path():
    """Raise TypeError when Path is given."""
    with pytest.raises(TypeError):
        libio.concatenate_entries(Path('somepath'))


def test_concatenate_typerror_str():
    """Raise TypeError when string is given."""
    with pytest.raises(TypeError):
        libio.concatenate_entries('somestr')
