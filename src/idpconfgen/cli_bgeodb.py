"""
Appends exact bond lengths (angstroms) and angles (radians) for each residue
in the IDPConformerGenerator database.

PROTOCOL:

1. Reads bacbkone coordinates (N, CA, C) from PDB/mmCIF files.
2. Calculates bond lengths and bend angles from the backbone.
3. Saves results to a JSON dictionary where keys are the input file names
    and the value is a dictionary containing 'N_CA', 'CA_C', 'C_Np1' for bond lengths
    and 'Cm1_N_CA', 'N_CA_C', 'CA_C_Np1' for bond angles with the order of usage in
    OMEGA, PHI, PSI, respectively per residue.
4. If `source` JSON file is given, updates that file with the new information.
    Pre-existing keys are deleted.
    
USAGE:
    $ idpconfgen bgeodb [PDBS]
    $ idpconfgen bgeodb [PDBS] -sc file.json
    $ idpconfgen bgeodb [PDBS] -sc file.json -n
    $ idpconfgen bgeodb [PDBS] -sc file.json -o my_new_bgeodb.json -n
"""
import argparse
import numpy as np
from functools import partial

from idpconfgen import Path, log
from idpconfgen.libs import libcli
from idpconfgen.libs.libio import (
    FileReaderIterator,
    read_dictionary_from_disk,
    save_dict_to_json,
)
from idpconfgen.libs.libmulticore import pool_function, starunpack
from idpconfgen.libs.libhigherlevel import cli_helper_calc_bgeo_angs
from idpconfgen.libs.libparse import pop_difference_with_log
from idpconfgen.logger import S, T, init_files, report_on_crash

LOGFILESNAME = '.idpconfgen_bgeodb'

_name = 'bgeodb'
_help = 'Calculate bond lengths and angles per residue for PDB files.'

_prog, _des, _usage = libcli.parse_doc_params(__doc__)

ap = libcli.CustomParser(
    prog=_prog,
    description=libcli.detailed.format(_des),
    usage=_usage,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )

libcli.add_argument_pdb_files(ap)
libcli.add_argument_source(ap)
libcli.add_argument_output(ap)
libcli.add_argument_degrees(ap)
libcli.add_argument_ncores(ap)

def main(
        pdb_files,
        source=None,
        output=None,
        degrees=False,
        ncores=1,
        func=None,    
        ):
    
    
    if source and not source.suffix == '.json':
        raise ValueError('Source file should have `.json` extension.')
    
    output = output or 'torsions.json'
    if not output.endswith('.json'):
        raise ValueError('Output file should have `.json` extension.')

    init_files(log, LOGFILESNAME)
    log.info(T('Extracting bond geometries'))
    
    if source:
        database_dict = read_dictionary_from_disk(source)
    
    log.info(T('reading input paths'))
    pdbs = FileReaderIterator(pdb_files, ext='.pdb')
    log.info(S('done'))
    
    consume = partial(starunpack, cli_helper_calc_bgeo_angs, degrees=degrees, decimals=15)

    execute = partial(
        report_on_crash,
        consume,
        ROC_exception=Exception,
        ROC_prefix=_name,
        )

    execute_pool = pool_function(execute, pdbs, ncores=ncores)
    
    bgeo_result = {
        Path(pdbid).stem: angles
        for pdbid, angles in execute_pool
    }
    
    if source:

        pop_difference_with_log(database_dict, bgeo_result)

        for key, value in bgeo_result.items():
            # where value is a dictionary {'Ca_C_Np1':, 'Ca_C_O':, 'Cm1_N_Ca':, 'N_Ca_C':}
            database_dict[key].update(value)

        save_dict_to_json(database_dict, output=output)

    else:
        save_dict_to_json(bgeo_result, output=output)
    
    return

if __name__ == '__main__':
    libcli.maincli(ap, main)