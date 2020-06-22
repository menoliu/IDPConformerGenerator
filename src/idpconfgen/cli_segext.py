"""
Extract secondary structure protein segments from PDBs.

Requires a *.dssp file as generated by `idpconfgen ssext` CLI.

USAGE:

idpcfongen segext PDBS_FOLDER DSSPFILE -d OUTPUTFOLDER -s [L/H/E/A]
"""
import argparse
from functools import partial

from idpconfgen import Path, log
from idpconfgen.core import definitions as DEFS
from idpconfgen.libs import libcli, libio, libstructure, libparse, libpdb
from idpconfgen.logger import S, T, init_files
from idpconfgen.libs.libhigherlevel import extract_secondary_structure
from idpconfgen.libs.libio import read_dictionary_from_disk, FileReaderIterator, save_pairs_to_disk
from idpconfgen.libs.libmulticore import pool_function_in_chunks, consume_iterable_in_list


LOGFILESNAMES = '.idpconfgen_segext'

_name = 'ssext'
_help = 'Extract secondary structure elements from PDBs.'
_prog, _des, _us = libcli.parse_doc_params(__doc__)

ap = libcli.CustomParser(
    prog=_prog,
    description=libcli.detailed.format(_des),
    usage=_us,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )

libcli.add_argument_pdb_files(ap)

ap.add_argument(
    'sscalc_file',
    help='The DSSP file as saved by IDPConfGen SSCALC CLI',
    )

libcli.add_argument_destination_folder(ap)

ap.add_argument(
    '-s',
    '--structure',
    help=(
        'The secondary structure type to extract. '
        'Defaults to \'all\'. '
        'A subfolder is created for each secondary structure type'
        ),
    default='all',
    nargs='+',
    )

ap.add_argument(
    '-a',
    '--atoms',
    help=(
        'List of atom names to save in the selection.\n'
        'Defaults to `N`, `CA`, and `C`.'
        ),
    default='all',  # ('N', 'CA', 'C'),
    nargs='+',
    )
libcli.add_argument_minimum(ap)
libcli.add_argument_ncores(ap)



def main(
        pdb_files,
        sscalc_file,
        atoms='all',
        minimum=4,
        destination=None,
        structure='all',
        func=None,
        ncores=1,
        chunks=5000,
        ):

    ssdata = read_dictionary_from_disk(sscalc_file)
    pdbs2operate = FileReaderIterator(pdb_files, ext='.pdb')

    execute = partial(
        # multiprocessing function
        pool_function_in_chunks,
        # wrapper around generator
        consume_iterable_in_list,
        # items
        pdbs2operate,
        # func to operate
        extract_secondary_structure,
        # multicore kwargs
        ncores=ncores,
        chunks=chunks,
        # func kwargs
        atoms=atoms,
        ssdata=ssdata,
        structure=structure,
        minimum=minimum,
        )

    for chunk in execute():
        for pairs in chunk:
            save_pairs_to_disk(pairs, destination=destination)


if __name__ == '__main__':
    libcli.maincli()
