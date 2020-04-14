"""
Handle structure representation components.
"""
import warnings

import numpy as np

from idpcalculator.libs.libpdb import PDBParams, is_pdb
from idpcalculator.libs.libcif import CIFParser, is_cif


class Structure:
    """
    Hold structural data from PDB files.

    Parameters
    ----------
    data : str
        Raw structural data from PDB formatted files.
    """
    def __init__(self, data, **kwargs):

        datastr = _get_datastr(data)
        self._structure_parser = _detect_structure_type(datastr)

        self._datastr = datastr
        self.data_array = None
        self.kwargs = kwargs
        self.clear_filters()
        assert isinstance(self.filters, list)

    def build(self):
        """
        Read structure raw data in :attr:`rawdata`.

        After `.build()`, filters and data can be accessed.
        """
        self.data_array = self._structure_parser(self._datastr, **self.kwargs)
        del self._datastr

    def clear_filters(self):
        self._filters = []

    @property
    def filters(self):
        return self._filters

    @property
    def filtered_atoms(self):
        """
        Filter data array by the selected filters.

        Returns
        -------
        list
            The data in PDB format after filtering.
        """
        filtered_data = self.data_array
        for f in self.filters:
            filtered_data = filter(f, filtered_data)
        return filtered_data

    @property
    def chain_set(self):
        """All chain IDs present in the raw dataset."""  # noqa: D401
        return set(self.data_array[:, PDBParams.acol.chainid])

    def pop_last_filter(self):
        self._filters.pop()

    def add_filter(self, function):
        """Adds a function as filter."""
        self.filters.append(function)

    def add_filter_record_name(self, record_name):
        """Add filter for record names."""
        self.filters.append(
            lambda x: x[PDBParams.acol.record].startswith(record_name)
            )

    def add_filter_chain(self, chain):
        """Add filters for chain."""
        self.filters.append(
            lambda x: x[PDBParams.acol.chainid].startswith(chain)
            )

    def write_PDB(self, filename):
        lines = structure_to_pdb(self.filtered_atoms)
        if lines:
            write_PDB(lines, filename)
        else:
            raise EXCPTS.EmptyFilterError from err


# this servers read_pdb_data_to_array mainly
# it is here for performance
_pdb_atom_line_headings = {
    'both': ('ATOM', 'HETATM'),
    'ATOM': 'ATOM',
    'HETATM': 'HETATM',
    }


def gen_empty_structure_data_array(number_of_atoms):
    """
    Generate an array data structure to contain structure data.

    Parameters
    ----------
    number_of_atoms : int
        The number of atoms in the structure.
        Determines the size of the axis 0 of the structure array.

    Returns
    -------
    np.ndarray of (N, :attr:`PDBParams.atom_slicers), dtype = '<U8'
        Where N is the ``number_of_atoms``.
    """
    # require
    assert isinstance(number_of_atoms, int), \
        f'`number_of_atoms` is not int, {type(number_of_atoms)} '
    assert number_of_atoms > 0, \
        f'or number is less than zero: {number_of_atoms}.'

    return np.empty(
        (number_of_atoms, len(PDBParams.atom_slicers)),
        dtype='<U8',
        )


def parse_pdb_to_array(datastr, which='both', **kwargs):
    """
    Transform PDB data into an array.

    Parameters
    ----------
    datastr : str
        String representing the PDB format v3 file.

    which : str
        Which lines to consider ['ATOM', 'HETATM', 'both'].
        Defaults to `'both'`, considers both 'ATOM' and 'HETATM'.

    Returns
    -------
    numpy.ndarray of (N, len(`PDBParams.atom_slicers`))
        Where N are the number of ATOM and/or HETATM lines,
        and axis=1 the number of fields in ATOM/HETATM lines according
        to the PDB format v3.
    """
    # require
    assert isinstance(datastr, str), \
        f'`datastr` is not str: {type(datastr)} instead'

    lines = datastr.split('\n')
    record_lines = _filter_record_lines(lines, which=which)
    data_array = gen_empty_structure_data_array(len(record_lines))
    _populate_structure_array_from_pdb(record_lines, data_array)
    return data_array


def _populate_structure_array_from_pdb(record_lines, data_array):
    for row, line in enumerate(record_lines):
        for column, slicer_item in enumerate(PDBParams.atom_slicers):
            data_array[row, column] = line[slicer_item]


def _filter_record_lines(lines, which='both'):
    """Filter lines to get record lines only."""
    coords_headings = _pdb_atom_line_headings
    try:
        # returns lines because needs len after
        return list(filter(
            lambda x: x.startswith(coords_headings[which]),
            lines,
            ))
    except KeyError as err:
        err2 = ValueError(f'`which` got an unexpected value \'{which}\'.')
        raise err2 from err


def parse_cif_to_array(datastr, **kwargs):
    """
    Parse mmCIF protein data to array.

    Array is as given by :func:`gen_empty_structure_data_array`.
    """
    cif = CIFParser(datastr)
    data_array = gen_empty_structure_data_array(cif.number_of_atoms)

    for ii in range(cif.number_of_atoms):
        data_array[ii, :] = cif.get_line_elements_for_PDB(ii)

    return data_array


# possible data inputs in __init__
# all should return a string
# used for control flow
_type2string = {
    type(Path()): lambda x: x.read_text(),
    bytes: lambda x: x.decode('utf_8'),
    str: lambda x: x,
    }

# order matters
_structure_parsers = [
    (is_cif, parse_cif_to_array),
    (is_pdb, parse_pdb_to_array),
    ]


def _get_datastr(data):
    data_type = type(data)
    try:
        datastr = _type2string[data_type](data)
    except KeyError as err:
        err2 = NotImplementedError('Struture data not of proper type')
        raise err2 from err
    assert isinstance(datastr, str)
    return datastr


def _detect_structure_type(datastr):
    for condition, parser in _structure_parsers:
        if condition(datastr):
            return parser


def write_PDB(lines, filename):
    if lines:
        with open(filename, 'w') as fh:
            fh.write('\n'.join(lines))
            fh.write('\n')
        log.info(S(f'saved: {filename}'))
    else:
        warnings.warn('Empty lines, nothing to write, ignoring.', UserWarning)


def structure_to_pdb(atoms):
    return [
        PDBParams.line_formatter.format(
            *[func(i) for i, func in zip(line, PDBParams.format_funcs)]
            )
        for line in atoms
