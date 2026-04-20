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

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f_out:
            f_out.attrs['Ntrees'] = n_trees
            f_out.attrs['TotNHalos'] = total_halos_to_read

            # Direct mapping from Gadget-4 to SAGE schema based on confirmed mapping
            mapping = {
                'Descendant': 'TreeDescendant', 'FirstProgenitor': 'TreeFirstProgenitor',
                'NextProgenitor': 'TreeNextProgenitor', 'FirstHaloInFOFgroup': 'TreeFirstHaloInFOFgroup',
                'NextHaloInFOFgroup': 'TreeNextHaloInFOFgroup', 'Mvir': 'SubhaloMass',
                'Pos': 'SubhaloPos', 'Vel': 'SubhaloVel', 'Vmax': 'SubhaloVmax',
                'VelDisp': 'SubhaloVelDisp', 'SnapNum': 'SnapNum', 'Spin': 'SubhaloSpin'
            }

            offset = 0
            for i, nhalos in enumerate(lengths[:n_trees]):
                group = f_out.create_group(f"Tree{i}")
                for sage_key, g4_key in mapping.items():
                    if g4_key in halos:
                        data = halos[g4_key][offset:offset+nhalos]
                        group.create_dataset(sage_key, data=data)
                offset += nhalos

            f_out.create_dataset("TreeNHalos", data=lengths[:n_trees])

    print(f"Successfully converted {n_trees} Gadget-4 trees to {output_path}")
