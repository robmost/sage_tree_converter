import numpy as np
import h5py
import os

# LHaloTree C-struct as numpy dtype (104 bytes)
HALO_DTYPE = np.dtype([
    ('Descendant', 'i4'), ('FirstProgenitor', 'i4'), ('NextProgenitor', 'i4'),
    ('FirstHaloInFOFgroup', 'i4'), ('NextHaloInFOFgroup', 'i4'),
    ('Len', 'i4'), ('M_Mean200', 'f4'), ('M_Crit200', 'f4'), ('M_TopHat', 'f4'),
    ('Pos', 'f4', (3,)), ('Vel', 'f4', (3,)), ('VelDisp', 'f4'), ('Vmax', 'f4'),
    ('Spin', 'f4', (3,)), ('MostBoundID', 'i8'), ('SnapNum', 'i4'),
    ('FileNr', 'i4'), ('SubhaloIndex', 'i4'), ('SubHalfMass', 'f4')
])

def convert(input_paths, output_path, n_trees=None):
    """Convert Millennium binary trees to SAGE-compatible HDF5."""
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    input_paths.sort() # Ensure consistent order

    all_halos = []
    all_tree_nhalos = []
    total_trees_read = 0

    for input_path in input_paths:
        with open(input_path, 'rb') as f:
            ntrees = np.fromfile(f, dtype='i4', count=1)[0]
            tot_nhalos = np.fromfile(f, dtype='i4', count=1)[0]
            tree_nhalos = np.fromfile(f, dtype='i4', count=ntrees)

            trees_to_read = ntrees
            if n_trees is not None:
                if total_trees_read >= n_trees:
                    break
                if total_trees_read + ntrees > n_trees:
                    trees_to_read = n_trees - total_trees_read

            halos_to_read = sum(tree_nhalos[:trees_to_read])
            halos = np.fromfile(f, dtype=HALO_DTYPE, count=halos_to_read)

            all_halos.append(halos)
            all_tree_nhalos.append(tree_nhalos[:trees_to_read])

            total_trees_read += trees_to_read
            print(f"Read {trees_to_read} trees from {input_path}")

    if not all_halos:
        print("No trees read.")
        return

    combined_halos = np.concatenate(all_halos)
    combined_tree_nhalos = np.concatenate(all_tree_nhalos)
    
    # LHaloTree pointers are internal to each tree.
    # To store them in a single flat HDF5 dataset, they must be offset globally.
    tree_offsets = np.concatenate([[0], np.cumsum(combined_tree_nhalos)[:-1]])
    
    # We must apply this offset to all halos, but ONLY if the pointer != -1
    # We can do this by constructing an array of offsets the same length as combined_halos
    halo_offsets = np.repeat(tree_offsets, combined_tree_nhalos)
    
    pointer_fields = ['Descendant', 'FirstProgenitor', 'NextProgenitor', 'FirstHaloInFOFgroup', 'NextHaloInFOFgroup']
    for field in pointer_fields:
        mask = combined_halos[field] != -1
        combined_halos[field][mask] += halo_offsets[mask]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as hf:
        hf.attrs['Ntrees'] = total_trees_read
        hf.attrs['TotNHalos'] = len(combined_halos)
        group = hf.create_group("Tree0")

        # Field mapping based on SAGE standards
        mapping = {
            'M_TopHat': 'Mvir',
            'Pos': 'Pos',
            'Vel': 'Vel',
            'Vmax': 'Vmax',
            'SnapNum': 'SnapNum',
            'Descendant': 'Descendant',
            'FirstProgenitor': 'FirstProgenitor',
            'NextProgenitor': 'NextProgenitor',
            'FirstHaloInFOFgroup': 'FirstHaloInFOFgroup',
            'NextHaloInFOFgroup': 'NextHaloInFOFgroup',
            'Len': 'Len',
            'M_Mean200': 'M_Mean200',
            'M_Crit200': 'M_Crit200',
            'VelDisp': 'VelDisp',
            'Spin': 'Spin',
            'MostBoundID': 'MostBoundID',
            'FileNr': 'FileNr',
            'SubhaloIndex': 'SubhaloIndex',
            'SubHalfMass': 'SubHalfMass'
        }

        for old_field, new_field in mapping.items():
            if old_field in combined_halos.dtype.names:
                if new_field == 'Mvir':
                    group.create_dataset(new_field, data=combined_halos[old_field] * 1e10)
                else:
                    group.create_dataset(new_field, data=combined_halos[old_field])

        hf.create_dataset("TreeNHalos", data=combined_tree_nhalos)

    print(f"Successfully converted {total_trees_read} trees to {output_path}")