"""
Client for building IDRs on PDB files in the cartesian coordinate space.

Methodology deviates from traditional IDP or beads-on-a-string FLDR/S approach.

Name: FLDR/S (Folded disordered region/structure sampling)
"""
import os
import random
from itertools import product

import numpy as np

from idpconfgen import Path
from idpconfgen.core.definitions import aa3to1, vdW_radii_tsai_1999
from idpconfgen.core.exceptions import IDPConfGenException
from idpconfgen.libs.libstructure import (
    Structure,
    structure_to_pdb,
    write_PDB,
    col_chainID,
    col_element,
    col_name,
    col_resName,
    col_resSeq,
    col_segid,
    col_serial,
    col_x,
    col_y,
    col_z,
    cols_coords,
    )

disorder_cases = {
    0: "N-IDR",
    1: "Break-IDR",
    2: "C-IDR",
    }


def tolerance_calculator(tolerance):
    """
    Calculate the max number of tolerated spherical clashes and distance.

    Parameter
    ---------
    tolerance : float
    
    Returns
    -------
    max_clash : int
    dist_tolerance : float
    """
    if tolerance > 1.0:
        tolerance = 1.0
    elif tolerance < 0.0:
        tolerance = 0.0
        
    max_clash = int(tolerance * 80)
    dist_tolerance = tolerance * 1.25
    
    return max_clash, dist_tolerance


def calculate_distance(coords1, coords2):
    """
    Calculate the distance between two 3D coordinates.
    
    Calculates the distance between 2 coordinates using Euclidean distance
    formula.
    
    Parameters
    ----------
    coords1 : np.ndarray
    
    coords2 : np.ndarray
    
    Return
    ------
    float distance
    """
    return np.sqrt(np.sum((coords1 - coords2) ** 2))


def calculate_angle(a, b, c):
    """
    Calculate angle between three 3D coordinates.

    Parameters
    ----------
    a : np.ndarray
    
    b : np.ndarray
    
    c : np.ndarray
    
    Return
    ------
    float angle in radians
    """
    ab = a - b
    cb = c - b

    # Calculate the dot product
    dot_product = np.dot(ab, cb)

    # Calculate the magnitudes of the vectors
    mag_ab = np.linalg.norm(ab)
    mag_cb = np.linalg.norm(cb)

    # Calculate the cosine of the angle between the vectors
    cos_angle = dot_product / (mag_ab * mag_cb)
    # Calculate the angle in radians
    angle = np.arccos(cos_angle)

    return angle


def consecutive_grouper(seq):
    """
    Use negative indexing to group together consecutive numbers.

    Reference
    ---------
    https://stackoverflow.com/questions/70363072/group-together-consecutive-numbers-in-a-list
    
    Parameters
    ----------
    seq : string
        Special sequence where indices of disordered residues are stored.
    
    Return
    ------
    bounds : list
        List of ranges for boundaries of disordered sequences.
    """
    grouped = [[seq[0]]]
    for x in seq[1:]:
        if x == grouped[-1][-1] + 1:
            grouped[-1].append(x)
        else:
            grouped.append([x])
            
    bounds = []
    for group in grouped:
        first = group[0]
        last = group[len(group) - 1]
        bounds.append((first, last + 1))
    
    return bounds


def store_idp_paths(folder, temp_dir):
    """
    Store all of the paths for different cases of IDRs in a dictionary.

    Parameters
    ----------
    folder : Path
        Output folder of interest
    
    temp_dir : str
        Name of the temporary directory of interest
    
    Returns
    -------
    disorder_case : dict
        Dictionary of paths to conformers associated with each disorder case
    """
    case_path = {}
    
    try:
        if os.path.exists(folder.joinpath(temp_dir + disorder_cases[0])):
            fpath = folder.joinpath(temp_dir + disorder_cases[0])
            idr_confs = os.listdir(fpath)
            case_path[disorder_cases[0]] = \
                [Path(fpath.joinpath(cpath)) for cpath in idr_confs]
        if os.path.exists(folder.joinpath(temp_dir + disorder_cases[1])):
            # What to do if we have multiple breaks? Maybe split to subdirs
            fpath = folder.joinpath(temp_dir + disorder_cases[1])
            break_folders = os.listdir(fpath)
            for folder in break_folders:
                idr_folder_path = Path(fpath.joinpath(folder))
                idr_names = os.listdir(idr_folder_path)
                case_path[disorder_cases[1]] = \
                    [Path(idr_folder_path.joinpath(cpath)) for cpath in idr_names]
        if os.path.exists(folder.joinpath(temp_dir + disorder_cases[2])):
            fpath = folder.joinpath(temp_dir + disorder_cases[2])
            idr_confs = os.listdir(fpath)
            case_path[disorder_cases[2]] = \
                [Path(fpath.joinpath(cpath)) for cpath in idr_confs]
    except AttributeError:
        pass

    return case_path


def create_combinations(lst, num_combinations):
    """
    Create unique combinations between two lists.
    
    Made for N-IDR and C-IDR combinations. Where list1 = N-IDR paths,
    and list2 = C-IDR paths. Itertools product is used here because
    order matters.
    
    Parameters
    ----------
    lst : list
        Can be a list of lists, but normally in the order of
        N-IDR, Break-IDR, C-IDR paths
    
    num_combinations : int
    
    Return
    ------
    selected_combinations : list
        List of tuples of different combinations as follows:
        [(item from list 1, item from list 2), ...]
    """
    all_combinations = list(product(*lst))
    max_combinations = len(all_combinations)

    selected_combinations = \
        random.sample(all_combinations, min(num_combinations, max_combinations))

    return selected_combinations


def break_check(fdata):
    """
    Calculate where breaks are in the backbone.
    
    Inspired from `get_torsions` in `libhigherlevel`.

    Parameters
    ----------
    fdata : str, bytes or Path
        A path to the structure file, or the string representing
        the file.
        In fact, accepts any type `:class:libstructure.Structure` would
        accept.
    
    Return
    ------
    fld_seqs : list
        List of FASTA sequence of folded regions in the sequence of fdata.
    """
    structure = Structure(fdata)
    structure.build()
    structure.add_filter_backbone(minimal=True)

    data = structure.filtered_atoms
    names = data[:, col_name]
    coords_raw = structure.coords

    n_mask = names == 'N'
    ca_mask = names == 'CA'
    c_mask = names == 'C'

    n = coords_raw[n_mask, :]
    ca = coords_raw[ca_mask, :]
    c = coords_raw[c_mask, :]

    try:
        coords = np.empty((n.shape[0] * 3, 3), dtype=np.float64)
        coords[0::3, :] = n
        coords[1::3, :] = ca
        coords[2::3, :] = c
    except ValueError as err:
        errmsg = (
            'Coordinates do not match expectation. '
            'Some possibly missing.'
            )
        raise IDPConfGenException(errmsg) from err

    coords_distances = np.linalg.norm(coords[:-1, :] - coords[1:, :], axis=1)
    assert coords_distances.size == coords.shape[0] - 1
    
    if np.any(coords_distances > 2.1):
        whole = []
        for i, dist in enumerate(coords_distances):
            if dist < 2.1:
                whole.append(i)
        
        whole = consecutive_grouper(whole)
        fld_seqs = []
        for idx in whole:
            fld_idx = list(range(idx[0], idx[1], 3))
            fld_seqs.append(''.join(aa3to1.get(f) for f in data[:, col_resName][fld_idx].tolist()))  # noqa: E501
        
        return fld_seqs
    
    return


def align_coords(sample, target, case):
    """
    Translate and rotate coordinates based on the IDR case.
    
    Set of `target` coordinates should be for [[C], [N], [CA]].
    Where the `C` position is of the previous residue for N-IDR
    and next residue `C` for C-IDR.

    Parameters
    ----------
    sample : np.array
        Array format of the PDB of IDR in question. The return
        of `parse_pdb_to_array` from `libstructure`.
    
    target : np.array
        Set of 3D coordinates representing positions of C, N, CA
        fixed points to align to.
        
        For Break-IDR it would be (F, L), (CA, N) where "F" and "L"
        are the positions of "C" for the first and last bit of the
        chain break respectively and "CA" is for alignment to
        first part of break while "N" is for the last part.
    
    case : str
        IDR case as mentioned above (N-IDR, C-IDR, Break-IDR).
    
    Returns
    -------
    sample : np.array
        New array format of the PDB now with coordinates rotated
        and translated about target.
    """
    atom_names = sample[:, col_name]
    res_seq = sample[:, col_resSeq].astype(int)

    first_seq = res_seq[0]
    last_seq = res_seq[-1]

    idr_term_idx = {}

    if case == disorder_cases[0]:  # N-IDR
        # In the case of N-IDR, we want to move relative to C-term
        for i, _atom in enumerate(atom_names):
            # Use last residues of N-IDR for alignment
            j = len(atom_names) - 1 - i
            seq = res_seq[j]

            if seq == last_seq and atom_names[j] == "N":
                idr_term_idx["N"] = j
            elif seq == last_seq and atom_names[j] == "CA":
                idr_term_idx["CA"] = j
            elif seq == last_seq - 1 and atom_names[j] == "C":
                idr_term_idx["C"] = j
            elif seq == last_seq - 2:
                break
    elif case == disorder_cases[2]:  # C-IDR
        # We want to move relative to N-term of fragment
        for i, atom in enumerate(atom_names):
            seq = res_seq[i]

            # Use first residues of C-IDR for alignment
            if seq == first_seq + 1 and atom == "N":
                idr_term_idx["N"] = i
            elif seq == first_seq + 1 and atom == "CA":
                idr_term_idx["CA"] = i
            elif seq == first_seq and atom == "C":
                idr_term_idx["C"] = i
            elif seq == first_seq + 2:
                break

    idr_Cxyz = sample[idr_term_idx["C"]][cols_coords].astype(float).tolist()
    idr_Nxyz = sample[idr_term_idx["N"]][cols_coords].astype(float).tolist()
    idr_CAxyz = sample[idr_term_idx["CA"]][cols_coords].astype(float).tolist()
    idr_xyz = sample[:, cols_coords].astype(float)

    idr_coords = np.array([idr_Cxyz, idr_Nxyz, idr_CAxyz])

    centered_idr = idr_coords - idr_coords.mean(axis=0)
    centered_fld = target - target.mean(axis=0)

    covariance_matrix = np.dot(centered_idr.T, centered_fld)
    U, S, Vt = np.linalg.svd(covariance_matrix)
    rotation_matrix = np.dot(U, Vt)

    rotated_points = np.dot(idr_xyz, rotation_matrix)
    sample[:, cols_coords] = rotated_points.astype(str)

    translation_vector = \
        target[0] - sample[idr_term_idx["C"]][cols_coords].astype(float)

    for i, coords in enumerate(sample[:, cols_coords]):
        x = str(round(translation_vector[0] + float(coords[0]), 3))
        y = str(round(translation_vector[1] + float(coords[1]), 3))
        z = str(round(translation_vector[2] + float(coords[2]), 3))

        sample[i][col_x] = x
        sample[i][col_y] = y
        sample[i][col_z] = z

    return sample


def sliding_window(
        cterm_idr,
        nterm_idr_lib,
        max_clash,
        tolerance,
        output_folder,
        ):
    """
    Sliding window search protocol to find possible pairs of chains
    that will close the break.

    Parameters
    ----------
    cterm_idr : str or Path
        Path to the IDR chain of interest from C-term side of break
    
    nterm_idr_lib : list
        List of paths of IDR chains from N-term side of break
    
    max_clash : int
        Integer number for maximum number of allowed clashes
    
    tolerance : float
        Tolerance applicable to vdW clash validation in Angstroms
    
    output_folder : str
        Output folder to store conformers with matches
    
    Returns
    -------
    False
        If no matches have been found. Otherwise write them to output folder.
    """
    matches = 0
    idr_struc = Structure(Path(cterm_idr))
    idr_struc.build()
    idr_arr = idr_struc.data_array
    idr_name = idr_arr[:, col_name]
    idr_coords = idr_arr[:, cols_coords].astype(float)
    idr_resseq = idr_arr[:, col_resSeq].astype(int)
    
    idr_C = []
    idr_CA = []
    idr_O = []
    idr_res = []
    for n, name in enumerate(idr_name):
        if name == 'C':
            idr_C.append(idr_coords[n])
            idr_res.append(idr_resseq[n])
        elif name == 'CA':
            idr_CA.append(idr_coords[n])
        elif name == 'O':
            idr_O.append(idr_coords[n])
    
    for nterm_idr in nterm_idr_lib:
        nterm_idr_struc = Structure(Path(nterm_idr))
        nterm_idr_struc.build()
        nterm_idr_arr = nterm_idr_struc.data_array
        nterm_idr_name = nterm_idr_arr[:, col_name]
        nterm_idr_coords = nterm_idr_arr[:, cols_coords].astype(float)
        
        nterm_idr_N = []
        nterm_idr_CA = []
        for n, name in enumerate(nterm_idr_name):
            if name == 'N':
                nterm_idr_N.append(nterm_idr_coords[n])
            elif name == 'CA':
                nterm_idr_CA.append(nterm_idr_coords[n])
        
        for i, curr_c in enumerate(idr_C):
            try:
                next_n = nterm_idr_N[i + 1]
                next_ca = nterm_idr_CA[i + 1]
            except IndexError:
                break
            CN_dist = calculate_distance(curr_c, next_n)
            CCA_dist = calculate_distance(curr_c, next_ca)
            CACN_ang = calculate_angle(idr_CA[i], curr_c, next_n)
            # Refer to distances and angles in `core/build_definitions.py`
            if 1.32 <= CN_dist <= 1.56 and 1.91 <= CACN_ang <= 2.15 and 2.2 <= CCA_dist <= 2.7:  # noqa: E501
                term_residue = idr_res[i]
                
                idr_list = []
                for p, _ in enumerate(idr_resseq):
                    next = idr_resseq[p + 1]
                    idr_list.append(idr_arr[p])
                    nterm_idr_arr = nterm_idr_arr[1:]
                    if next == term_residue + 1:
                        break
                idr_arr = np.array(idr_list)
                    
                nterm_idr_struc._data_array = nterm_idr_arr
                
                clashes, _ = count_clashes(
                    idr_arr,
                    nterm_idr_struc,
                    disorder_cases[1],
                    max_clash,
                    tolerance,
                    )
                
                if type(clashes) is int:
                    nterm_idr_list = nterm_idr_arr.tolist()
                    final_struc_arr = np.array(idr_list + nterm_idr_list)
                    final_struc_name = final_struc_arr[:, col_name]
                    final_struc_res = final_struc_arr[:, col_resSeq].astype(int)
                    H_idx = -1  # for cases like Proline without "H"
                    for idx, name in enumerate(final_struc_name):
                        if final_struc_res[idx] == term_residue:
                            if name == 'O':
                                O_idx = idx
                        elif final_struc_res[idx] == term_residue + 1:
                            if name == 'H':
                                H_idx = idx
                        elif final_struc_res[idx] == term_residue + 2:
                            break
                    
                    # Fix the position of the Carbonyl O and Nitrogen H
                    CO_length = calculate_distance(curr_c, idr_O[i])
                    CAC_O_vec = idr_CA[i] - curr_c
                    NC_O_vec = next_n - curr_c
                    O_angle = np.arccos(np.dot(CAC_O_vec, NC_O_vec) / (np.linalg.norm(CAC_O_vec) * np.linalg.norm(NC_O_vec)))  # noqa: E501
                    O_vector = CO_length * np.sin(O_angle / 2) * (CAC_O_vec / np.linalg.norm(CAC_O_vec)) + CO_length * np.sin(O_angle / 2) * (NC_O_vec / np.linalg.norm(NC_O_vec))  # noqa: E501
                    new_O_xyz = curr_c - O_vector
                    
                    NH_length = 1.0
                    CN_H_vec = curr_c - next_n
                    CAN_H_vec = next_ca - next_n
                    H_angle = np.arccos(np.dot(CN_H_vec, CAN_H_vec) / (np.linalg.norm(CN_H_vec) * np.linalg.norm(CAN_H_vec)))  # noqa: E501
                    H_vector = NH_length * np.sin(H_angle / 2) * (CN_H_vec / np.linalg.norm(CN_H_vec)) + NH_length * np.sin(H_angle / 2) * (CAN_H_vec / np.linalg.norm(CAN_H_vec))  # noqa: E501
                    new_H_xyz = next_n - H_vector
                    
                    final_struc_arr[:, col_x][O_idx] = str(new_O_xyz[0])
                    final_struc_arr[:, col_y][O_idx] = str(new_O_xyz[1])
                    final_struc_arr[:, col_z][O_idx] = str(new_O_xyz[2])
                    if H_idx > 0:
                        final_struc_arr[:, col_x][H_idx] = str(new_H_xyz[0])
                        final_struc_arr[:, col_y][H_idx] = str(new_H_xyz[1])
                        final_struc_arr[:, col_z][H_idx] = str(new_H_xyz[2])
                    
                    final_struc = structure_to_pdb(final_struc_arr)
                    cterm_idr_stem = Path(cterm_idr).stem
                    nterm_idr_stem = Path(nterm_idr).stem
                    matches += 1
                    write_PDB(final_struc, output_folder + f"{cterm_idr_stem}+{nterm_idr_stem}.pdb")  # noqa: E501

    return matches


def count_clashes(
        fragment,
        parent,
        case=None,
        max_clash=40,
        tolerance=0.4,
        ):
    """
    Check for steric clashes between two protein chains using vdW radii.

    Parameters
    ----------
    fragment : np.array
        Array of the IDR fragment of interest
    
    parent : IDPConformerGenerator.Structure
        Structure of static protein chain of interest.
        Must already be built using `.build()`
    
    case : str, optional
        Disorder case of interest will change how clash is calculated
    
    max_clash : int, optional
        Integer number for maximum number of allowed clashes
    
    tolerance : float, optional
        Tolerance applicable to vdW clash validation in Angstroms
    
    Returns
    -------
    num_clashes : int or Bool
        Number of steric clashes determined using vdW radii
    
    fragment : np.array
        Array of the IDR fragment of interest
    """
    num_clashes = 0
    
    parent_atoms = parent.data_array[:, col_element]
    fragment_atoms = fragment[:, col_element]
    fragment_seq = fragment[:, col_resSeq]
    parent_coords = parent.data_array[:, cols_coords].astype(float)
    fragment_coords = fragment[:, cols_coords].astype(float)
    
    first_r = int(fragment_seq[0])
    last_r = int(fragment_seq[len(fragment_seq) - 1])
    
    if case == disorder_cases[0] or disorder_cases[1]:
        # N-IDR or Break-IDR, remove last 3 resiudes of fragment from consideration
        for i, _ in enumerate(fragment_seq):
            j = len(fragment_seq) - 1 - i
            try:  # In case the user wants to build less than 3 residues
                prev = int(fragment_seq[j - 1])
            except IndexError:
                continue
            fragment_atoms = fragment_atoms[:-1]
            fragment_coords = fragment_coords[:-1]
            if last_r - prev == 3:
                break
    elif case == disorder_cases[2]:
        # C-IDR, remove first 3 residues of fragment from consideration
        for i, _ in enumerate(fragment_seq):
            try:  # In case the user wants to build less than 3 residues
                next = int(fragment_seq[i + 1])
            except IndexError:
                continue
            fragment_atoms = fragment_atoms[1:]
            fragment_coords = fragment_coords[1:]
            if next - first_r == 3:
                break

    # Loop through all pairs of atoms in the 2 protein chains
    for i, atom1 in enumerate(parent_atoms):
        for j, atom2 in enumerate(fragment_atoms):
            # calculate distance between atoms
            distance = calculate_distance(parent_coords[i], fragment_coords[j])
            
            # get vdW radii for each atom
            vdw_radius1 = vdW_radii_tsai_1999[atom1]
            vdw_radius2 = vdW_radii_tsai_1999[atom2]
            
            # Check if a steric clash is detected by comparing
            # distance between atoms to the sum of their vdW radii
            if num_clashes > max_clash:
                return True, fragment
            if distance < vdw_radius1 + vdw_radius2 + tolerance:
                num_clashes += 1
    
    return num_clashes, fragment


def psurgeon(idp_struc, fld_struc, case, ranges):
    """
    Protein surgeon grafts disordered regions onto folded structures.

    Parameters
    ----------
    idp_struc : Path or IDPConformerGenerator.Structure
        Donor conformer to graft
    
    case : str
        Case could be `nidr`, `cidr`, or `break` as defined above

    fld_struc : Path or IDPConformerGenerator.Structure
        Folded structure to be grafted on
    
    ranges : tuple of int
        For Break-IDR, what residue ranges for the chain break

    Returns
    -------
    new_struc_arr : np.ndarray (N x 16)
        Array format of the PDB file.
    """
    if type(fld_struc) is Path:
        fld = Structure(fld_struc)
        fld.build()
        fld_seq = fld.data_array[:, col_resSeq]
        fld_data_array = fld.data_array
    else:
        fld_seq = fld_struc.data_array[:, col_resSeq]
        fld_data_array = fld_struc.data_array
        
    if type(idp_struc) is Path:
        idr = Structure(idp_struc)
        idr.build()
        idr_seq = idr.data_array[:, col_resSeq]
        idr_data_array = idr.data_array
    elif type(idp_struc) is tuple:
        nidr = Structure(idp_struc[0])
        cidr = Structure(idp_struc[1])
        nidr.build()
        cidr.build()
    else:
        idr_seq = idp_struc[:, col_resSeq]
        idr_data_array = idp_struc
    
    if case == disorder_cases[0]:
        # N-IDR, remove last resiude of fragment
        # and remove the first residue of folded-domain
        for i, _seq in enumerate(idr_seq):
            j = len(idr_seq) - 1 - i
            curr = idr_seq[j]
            prev = idr_seq[j - 1]
            idr_data_array = idr_data_array[:-1]
            if prev != curr:
                break
        
        idr._data_array = idr_data_array
        
        for i, _seq in enumerate(fld_seq):
            curr = fld_seq[i]
            next = fld_seq[i + 1]
            fld_data_array = fld_data_array[1:]
            if next != curr:
                break
        
        fld._data_array = fld_data_array
        
        new_struc_arr = np.append(idr.data_array, fld.data_array, axis=0)
        
    elif case == disorder_cases[1]:
        lower = ranges[0]
        upper = ranges[1]
        # Break-IDR, remove first residue of fragment
        # and residues on folded protein between the break
        for i, seq in enumerate(idr_seq):
            try:
                next = idr_seq[i + 1]
            except IndexError:
                continue
            
            idr_data_array = idr_data_array[1:]
            if next != seq:
                break
        
        og_fld_list = fld_data_array.tolist()
        idr_data_list = idr_data_array.tolist()
        fld_data_list = []
        # Find the position to insert IDR
        # Remove the first and last residue at the break site
        first_fld_seq = int(fld_seq[0])
        actual_lower = first_fld_seq + lower - 1
        actual_upper = first_fld_seq + upper
        found = False
        for i, seq in enumerate(fld_seq):
            seq = int(seq)
            if seq == actual_lower or seq == actual_upper:
                if found is False:
                    found = True
                    insert_idx = i
            else:
                fld_data_list.append(og_fld_list[i])
        
        idr_seq = idr_data_array[:, col_resSeq].astype(int)
 
        for i, row in enumerate(idr_data_list):
            # Fix residue numbering for IDR (we know it starts at 1)
            row[col_resSeq] = str(idr_seq[i] + actual_lower - 2)
            fld_data_list.insert(insert_idx + i, row)
        
        new_struc_arr = np.array(fld_data_list)
    
    elif case == disorder_cases[2]:
        # C-IDR, remove last resiude of folded protein
        # and remove the first residue of C-IDR
        for i, _seq in enumerate(fld_seq):
            j = len(fld_seq) - 1 - i
            curr = fld_seq[j]
            prev = fld_seq[j - 1]
            fld_data_array = fld_data_array[:-1]
            if prev != curr:
                break
        
        fld._data_array = fld_data_array
        
        for i, _ in enumerate(idr_seq):
            curr = idr_seq[i]
            next = idr_seq[i + 1]
            idr_data_array = idr_data_array[1:]
            if next != curr:
                break
        
        idr._data_array = idr_data_array

        # Fix residue connectivity issue
        last_residue_fld = int(fld.data_array[:, col_resSeq][-1])
        curr_residue = last_residue_fld + 1
        idr_seq = idr.data_array[:, col_resSeq]
        for i, seq in enumerate(idr_seq):
            curr = seq
            idr._data_array[:, col_resSeq][i] = str(curr_residue)
            try:
                if idr_seq[i + 1] != curr:
                    curr_residue += 1
            except IndexError:
                break
        
        # Initialize and clean new structure
        new_struc_arr = np.append(fld.data_array, idr.data_array, axis=0)
        
    elif case == disorder_cases[0] + disorder_cases[2]:
        nidr_seq = nidr.data_array[:, col_resSeq]
        cidr_seq = cidr.data_array[:, col_resSeq]
        nidr_data_array = nidr.data_array
        cidr_data_array = cidr.data_array
        
        # For cases where we have both C-IDR and N-IDR
        # idp_struc should be a list of tuple (N-IDR, C-IDR) paths
        # N-IDR, remove last resiude of fragment
        for i, _seq in enumerate(nidr_seq):
            j = len(nidr_seq) - 1 - i
            curr = nidr_seq[j]
            prev = nidr_seq[j - 1]
            nidr_data_array = nidr_data_array[:-1]
            if prev != curr:
                break
        
        nidr._data_array = nidr_data_array
        
        # Remove first residue of folded domain
        for i, _seq in enumerate(fld_seq):
            curr = fld_seq[i]
            next = fld_seq[i + 1]
            fld_data_array = fld_data_array[1:]
            if next != curr:
                break
        
        fld._data_array = fld_data_array
        
        new_struc_arr = np.append(nidr.data_array, fld.data_array, axis=0)
        new_struc_seq = new_struc_arr[:, col_resSeq]
        
        # Remove last residue of folded domain (now protein)
        for i, _ in enumerate(new_struc_seq):
            j = len(new_struc_seq) - 1 - i
            curr = new_struc_seq[j]
            prev = new_struc_seq[j - 1]
            new_struc_arr = new_struc_arr[:-1]
            if prev != curr:
                break
        
        # Remove first residue of C-IDR
        for i, _ in enumerate(cidr_seq):
            curr = cidr_seq[i]
            next = cidr_seq[i + 1]
            cidr_data_array = cidr_data_array[1:]
            if next != curr:
                break
            
        cidr._data_array = cidr_data_array
        
        # Fix residue connectivity issue
        last_residue_fld = int(new_struc_arr[:, col_resSeq][-1])
        curr_residue = last_residue_fld + 1
        cidr_seq = cidr.data_array[:, col_resSeq]
        for i, seq in enumerate(cidr_seq):
            curr = seq
            cidr._data_array[:, col_resSeq][i] = str(curr_residue)
            try:
                if cidr_seq[i + 1] != curr:
                    curr_residue += 1
            except IndexError:
                break
        
        new_struc_arr = np.append(new_struc_arr, cidr.data_array, axis=0)
        
    new_serial = [str(i) for i in range(1, len(new_struc_arr) + 1)]
    new_struc_arr[:, col_serial] = new_serial
    new_struc_arr[:, col_chainID] = "A"
    new_struc_arr[:, col_segid] = "A"
    
    return new_struc_arr


''' Deprecated code.
def pmover(case, fld_xyz, idp_path):
    """
    Protein cartesian space mover.
    
    Shifts entire protein chain based on one point.

    Parameters
    ----------
    case : string
        Case could be `nidr`, `cidr`, or `break` as defined above.
    
    fld_xyz : tuple
        Backbone N(x, y, z) float coordinates of interest
        where we want to move the IDP chain relative to.
    
    idp_path : Path
        Path to the IDP conformer we want to move.
    
    Returns
    -------
    Overwrites PDB of IDP conformer with new coordinates.
    """
    Nx = fld_xyz[0]
    Ny = fld_xyz[1]
    Nz = fld_xyz[2]
    
    structure = Structure(idp_path)
    structure.build()
    atom_names = structure.data_array[:, col_name]
    
    if case == disorder_cases[0]:  # N-IDR
        # In the case of N-IDR, we want to move relative to C-term
        # A little bit complicated, need to calculate difference between
        # C-term Nitrogen on IDP and N(x,y,z)
        for i, atom in enumerate(atom_names):
            if atom_names[len(atom_names) - 1 - i] == "N":
                index = len(atom_names) - 1 - i
                break
    elif case == disorder_cases[1]:  # break
        pass
    elif case == disorder_cases[2]:  # C-IDR
        # In the case of C-IDR, we want to move relative to first N
        for i, atom in enumerate(atom_names):
            if atom == "N":
                index = i
                break
    
    idp_xyz = structure.data_array[index][cols_coords]
    dx = Nx - float(idp_xyz[0])
    dy = Ny - float(idp_xyz[1])
    dz = Nz - float(idp_xyz[2])
    
    for i, coords in enumerate(structure.data_array[:, cols_coords]):
        x = str(round(dx + float(coords[0]), 3))
        y = str(round(dy + float(coords[1]), 3))
        z = str(round(dz + float(coords[2]), 3))
        
        structure.data_array[i][col_x] = x
        structure.data_array[i][col_y] = y
        structure.data_array[i][col_z] = z
    
    structure.write_PDB(idp_path)
    
    return


def rotator(chain, case):
    """
    Rotation function that rotates the protein chain randomly.
    
    The point of rotation depends on the case of IDR.
    For example, with N-IDR, the point of rotation is about
    the CA atom at the C-term of the IDR chain.
    
    Parameters
    ----------
    chain : Path or IDPConformerGenerator.Structure
        Chain of interest we want to rotate.
    
    case : string
        Disordered case of interest determines which point
        to rotate about.

    Returns
    -------
    idp : IDPConformerGenerator.Structure
        Structure object with the new rotated coordinates.
    """
    minrad = 0
    maxrad = 2 * np.pi
    # Select random angle to rotate
    angle = random.uniform(minrad, maxrad)
    
    if type(chain) is Path:
        idp = Structure(chain)
        idp.build()
    else:
        idp = chain
        
    atom_names = idp.data_array[:, col_name]
    
    if case == disorder_cases[0]:  # N-IDR
        for i, atom in enumerate(atom_names):
            if atom_names[len(atom_names) - 1 - i] == "N":
                index = len(atom_names) - 1 - i
                break
    elif case == disorder_cases[2]:  # C-IDR
        for i, atom in enumerate(atom_names):
            if atom == "N":
                index = i
                break
    
    # Create a 3x3 rotation matrix
    rotation_matrix = np.array(
        [[np.cos(angle), -np.sin(angle), 0],
        [np.sin(angle), np.cos(angle), 0],
        [0, 0, 1]]
    )
    
    # Mark the fixed point and translate point as the origin
    point_xyz = idp.data_array[index][cols_coords].astype(float)
    coords = idp.data_array[:, cols_coords].astype(float) - point_xyz
    
    # Rotate coordinates about a random angle and translate point back
    rotated_coords = np.dot(rotation_matrix, coords.T).T
    rotated_coords += point_xyz
    
    idp.data_array[:, cols_coords] = rotated_coords.astype(str)
    
    return idp, chain  # returns original chain/path also
'''