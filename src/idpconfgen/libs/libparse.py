"""Contain different parsing strategies for different files."""
import sys

import numpy as np

from idpconfgen import Path
from idpconfgen.core import definitions as DEFS
from idpconfgen.core import exceptions as EXCPTS
from idpconfgen.libs import libcheck, libpdb


class DSSPParser:
    """
    Provides an interface for `DSSP files`_.

    .. _DSSP files: https://github.com/cmbi/xssp

    If neither `fin` nor `data` parameters are given, initiates
    an data empty parser.

    Parameters
    ----------
    fin : str or Path object, optional
        The path to the dssp text file to read.
        Defaults to ``None``.

    data : str or list, optional
        A string containing the dssp file data, or a list of lines
        of such file.
        Defaults to ``None``.

    pdbid : any, optional
        An identification for the DSSP file being parsed.
        Deafults to None.

    reduced : bool
        Whether or not to reduce secondary structure representation
        only three types: loops 'L', helices 'H', and sheets 'E'.

    Attributes
    ----------
    ss : array
        If `data` or `fin` are given :attr:`ss` stores the secondary
        structure information DSSP Keys of the protein.

    """

    def __init__(
            self,
            *,
            fin=None,
            data=None,
            pdbid=None,
            reduced=False,
            ):

        self.pdbid = pdbid
        self.reduced = reduced

        if fin:
            self.read_dssp_data(Path(fin).read_text())
        elif data:
            self.read_dssp_data(data)
        else:
            self.data = None


    def __eq__(self, other):
        is_equal = [
            self.data == other.data,
            self.pdbid == other.pdbid,
            ]

        return all(is_equal)

    def read_dssp_data(self, data):
        """
        Read DSSP data into the parser object.

        Parameters
        ----------
        data : str or list of strings
            Has the same value as Class parameter `data`.
        """
        try:
            data = data.split('\n')
        except AttributeError:  # data already a list
            pass

        data = [i for i in data if i]  # removes empty strings

        try:
            data_header_index = self._finds_data_index(data)
        except IndexError as err:
            raise EXCPTS.DSSPParserError(self.pdbid) from err

        # data starts afterthe header
        # '!' appears in gap regions, so that line needs to be ignored.
        self.data = [d for d in data[data_header_index + 1:] if d[13] != '!']

        self.read_sec_structure()
        self.read_fasta()

    def read_sec_structure(self):
        """
        Read secondary structure information from DSSP files.

        Assigns :attr:`ss`.
        """
        self.ss = list_index_to_array(self.data, index=16)

        if self.reduced:
            self.ss = np.char.translate(self.ss, DEFS.dssp_trans)

        self._confirm_ss_data(self.ss)

    def read_fasta(self):
        """
        Read FASTA (primary sequence) information from DSSP data.

        Assigns :attr:`fasta`.
        """
        self.fasta = list_index_to_array(self.data, index=13)

    @classmethod
    def from_data_id_tuple(cls, subcmd_tuple, **kwargs):
        """
        Initiate from a tuple.

        Tuple of type (PDBID, DSSP DATA).
        """
        return cls(
            pdbid=libpdb.PDBIDFactory(subcmd_tuple[0]),
            data=subcmd_tuple[1],
            **kwargs,
            )

    @staticmethod
    def _confirm_ss_data(data):
        """Confirm secondary structure data characters are valid."""
        if not all((i in DEFS.dssp_ss_keys.valid for i in data)):
            raise EXCPTS.DSSPSecStructError()

    @staticmethod
    def _finds_data_index(data):
        """
        Find index for where item startswith '#'.

        Evaluates after left striping white spaces.
        """
        # brute force index finding
        i = 0
        line = data[i]
        # if not exausted, while breaks with IndexError
        while not line.lstrip().startswith('#'):
            i += 1
            line = data[i]
        else:
            return i


def list_index_to_array(
        list_,
        start=None,
        stop=None,
        step=None,
        sObj=None,
        index=None,
        ):
    """
    Extract slices of strings in lists to an array.

    At least one the named parameters must be provided.

    In case more than one parameter set is provided:
        the `start`, `stop` or `step` trio have the highest priority,
        followed by `sObj` and last `index`.

    Raises
    ------
    ValueError
        If no named parameter is provided.

    ValueError
        If sObj is provided and is not a ``slice`` object.
    """
    if any((i is not None for i in (start, stop, step))):
        index = slice(start, stop, step)

    elif sObj is not None:
        if isinstance(sObj, slice):
            index = sObj
        else:
            raise ValueError(
                'sObj must be slice type: {} given.'.format(type(sObj))
                )

    elif index is not None:
        index = index

    else:
        raise ValueError('At least one of the index args most be provided.')

    len_of_slice = len(list_[0][index])

    array = np.empty(
        len(list_),
        dtype='<U{}'.format(len_of_slice),
        )

    for i, line in enumerate(list_):
        array[i] = line[index]

    return array


@libcheck.kwargstype((str, Path, type(None)))
def export_ss_from_DSSP(*dssp_task_results, output='dssp.database'):
    """
    Export secondary structure information from :class:`DSSPParser` results.

    Parameters
    ----------
    dssp_task_results : multiple :class:`DSSPParser`
    """
    output_data = _concatenate_ss_from_dsspparsers(dssp_task_results)

    output_data = '\n'.join(output_data) + '\n'

    if output:
        opath = Path(output)
        opath.myparents().mkdir(parents=True, exist_ok=True)
        opath.write_text(output_data)
    else:
        sys.stdout.write(output_data)


def _concatenate_ss_from_dsspparsers(dsspparsers):
    output = []
    for dsspparser in dsspparsers:
        output.append(
            '{}|{}'.format(
                dsspparser.pdbid,
                ''.join(dsspparser.ss),
                )
            )

    output.sort(key=lambda x: x.split('|')[0])

    return output


def read_pipe_file(text):
    """
    Read IDPConfGen pipe file.

    Pipe files have the following structure:

    CODE|DATA
    CODE|DATA
    (...)

    Parameters
    ----------
    text : str
        The crude text to read.

    Returns
    -------
    tuple (str, str)
        Of codes and data.
    """
    lines = text.split('\n')
    elines = filter(bool, lines)
    #slines = [l.split('|') for l in elines]
    return {c:s for line in elines for c, s in (line.split('|'),)}
    #return zip(*(line.split('|') for line in text.split('\n') if line))


def group_by(data):
    """
    Groups data by indexes.

    Parameters
    ----------
    data : iterable
        The data to group by.

    Returns
    -------
    list : ((type, slice),)

    Examples
    --------
    >>> group_by('LLLLLSSSSSSEEEEE')
    [['L', slice(0, 5)], ['S', slice(5, 11)], ['E', slice(11,16)]]
    """
    prev = data[0]
    start = 0
    current = [prev]
    groups = []
    for i, datum in enumerate(data):
        if datum != prev:
            current.append(slice(start, i))
            groups.append(current)
            start = i
            current = [datum]
        prev = datum
    else:
        current.append(slice(start, i + 1))
        groups.append(current)
    assert groups
    assert isinstance(groups[0][0], str)
    assert isinstance(groups[0][1], slice)
    return groups

