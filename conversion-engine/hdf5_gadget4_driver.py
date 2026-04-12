import h5py
import numpy as np
import os

def convert(input_path, output_path, n_trees=None):
    """Convert Gadget-4 HDF5 trees to SAGE-compatible HDF5."""
    with h5py.File(input_path, 'r') as f_in:
        lengths = f_in['TreeTable/Length'][:]
        
        if n_trees is None:
            n_trees = len(lengths)
        else:
            n_trees = int(n_trees)
            
        total_halos_to_read = np.sum(lengths[:n_trees])
        halos = {}
        for key in f_in['TreeHalos'].keys():
            halos[key] = f_in[f'TreeHalos/{key}'][:total_halos_to_read]

        # Offset Gadget-4 tree-local pointers to absolute file indices
        offsets = f_in['TreeTable/StartOffset'][:n_trees]
        pointer_keys = ['TreeDescendant', 'TreeFirstProgenitor', 'TreeNextProgenitor', 
                        'TreeFirstHaloInFOFgroup', 'TreeNextHaloInFOFgroup']
        
        # Build an offset array that matches the size of total_halos_to_read
        # This expands the per-tree offset to a per-halo offset
        halo_offsets = np.repeat(offsets, lengths[:n_trees])
        
        for ptr_key in pointer_keys:
            if ptr_key in halos:
                data = halos[ptr_key]
                valid_mask = data != -1
                data[valid_mask] += halo_offsets[valid_mask]
                halos[ptr_key] = data

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f_out:
            f_out.attrs['Ntrees'] = n_trees
            f_out.attrs['TotNHalos'] = total_halos_to_read
            group = f_out.create_group("Tree0")

            # Direct mapping from Gadget-4 to SAGE schema based on confirmed mapping
            mapping = {
                'Descendant': 'TreeDescendant', 'FirstProgenitor': 'TreeFirstProgenitor',
                'NextProgenitor': 'TreeNextProgenitor', 'FirstHaloInFOFgroup': 'TreeFirstHaloInFOFgroup',
                'NextHaloInFOFgroup': 'TreeNextHaloInFOFgroup', 'Mvir': 'SubhaloMass',
                'Pos': 'SubhaloPos', 'Vel': 'SubhaloVel', 'Vmax': 'SubhaloVmax',
                'VelDisp': 'SubhaloVelDisp', 'SnapNum': 'SnapNum', 'Spin': 'SubhaloSpin'
            }
            for sage_key, g4_key in mapping.items():
                if g4_key in halos:
                    group.create_dataset(sage_key, data=halos[g4_key])
            f_out.create_dataset("TreeNHalos", data=lengths[:n_trees])

    print(f"Successfully converted {n_trees} Gadget-4 trees to {output_path}")
