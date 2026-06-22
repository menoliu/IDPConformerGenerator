AlphaFlex (AFX-IDPCG) Protocols
===============================
Scripts for building, analysis, benchmarking, and scoring of AFX-IDPCG ensembles can be found in the ``.zip`` file within this directory. Scripts are archived to prevent
interference with the main IDPConformerGenerator package.

AFX-IDPCG Python scripts must be run within the ``idpconfgen`` Python environment created during the installation of IDPConformerGenerator.

The ``idpconfgen`` conda environment will need to be updated with the following packages for building ensembles::

    conda install -c conda-forge pdbfixer
    pip install pdb-tools
    pip install chardet==5.2.0
    pip install tqdm==4.67.1
    pip install biopython==1.85
    pip install mdtraj==1.11.0

The AlphaFlex database (``AlphaFlex_database_July2024_v2.json``) is a standard JSON dictionary database where each key is a UniProt ID and the values correspond
to IDR boundaries (``idrs``), mean PAEs between folded (F) and disordered (D) regions (``mean_pae``), and any interactions
between folded domains where the mean PAE is less than 15 Angstroms is documented in ``interactions``.

The ``AF2_9606_HUMAN_v4_num_residues.json`` is a database that contains the total length of the amino-acid residues from the
AlphaFold2 9606 Human v4 database. Full-length protein sequences can be found in the ``AF2_9606_HUMAN_v4_sequences.fasta`` file.

Transmembrane Proteins
----------------------
Although the logic for building transmembrane proteins is the same, annotating proteins with transmembrane regions requires an additional step.
Within the scripts .ZIP file, the ``transmembrane`` folder contains scripts for finding, annotating, and building transmembrane proteins. Steps are ``tm01, tm02_1, tm02_2, tm02_3, tm03`` within the folder.

To run ``tm02_1``, a python environment with TMbed v1.0.2 is required. Please see the `TMbed repository <https://github.com/BernhoferM/TMbed>`_ for details.
However, the ``step2_tmbed_uniprot_full_boundaries.json`` file is already provided in the Zenodo repository.

Benchmarking/Scoring
--------------------
For benchmarking against experimental SAXS curves, Pepsi-SAXS v3.0 is included in the scripts .ZIP file.
For benchmarking against experimental NMR chemical shift data, a UCBShiftv2 docker container is required. Please see the `UCBShiftv2 repository <https://github.com/menoliu/UCBShiftv2>`_ for details.

The surface chemistry profiler requires the installation an additional Python package::
    pip install freesasa==2.2.1

Resources
---------
- AlphaFlex Manuscript (pre-print): https://doi.org/10.1101/2025.11.24.690279
- AlphaFlex Zenodo Repository: https://zenodo.org/records/17684897