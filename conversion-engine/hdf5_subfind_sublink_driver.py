import h5py
import numpy as np
import os

def convert(input_path, output_path, n_trees=None):
    """Convert Subfind/SubLink HDF5 to SAGE-compatible HDF5."""
    print(f"Converting SubLink trees from {input_path} to {output_path}...")
    
    with h5py.File(input_path, 'r') as f_in:
        # SubLink data may be in the root or inside a 'Subhalo'/'Tree' group
        src = f_in['Subhalo'] if 'Subhalo' in f_in else f_in
        
        if 'SubhaloMass' not in src:
            print("Error: Could not find 'SubhaloMass' dataset.")
            return
            
        total_halos = len(src['SubhaloMass'])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f_out:
            f_out.attrs['Ntrees'] = 1
            f_out.attrs['TotNHalos'] = total_halos
            group = f_out.create_group("Tree0")
            
            # Map based on hdf5_subfind_sublink.json
            mapping = {
                'Mvir': ('SubhaloMass', 1e10),
                'Pos': ('SubhaloPos', 1.0),
                'Vel': ('SubhaloVel', 1.0),
                'Vmax': ('SubhaloVmax', 1.0),
                'FirstProgenitor': ('FirstProgenitorID', 1.0),
                'NextProgenitor': ('NextProgenitorID', 1.0),
                'Descendant': ('DescendantID', 1.0),
                'SubhaloGroupNr': ('SubhaloGroupNr', 1.0)
            }
            
            for sage_key, (src_key, scale) in mapping.items():
                if src_key in src:
                    data = src[src_key][:]
                    if scale != 1.0:
                        data = data * scale
                    
                    if sage_key == 'SubhaloGroupNr':
                        continue # Process synthetic logic below instead
                    else:
                        group.create_dataset(sage_key, data=data)
            
            # Synthetic Logic for FirstHaloInFOFgroup and NextHaloInFOFgroup
            if 'SubhaloGroupNr' in src:
                group_nr = src['SubhaloGroupNr'][:]
                first_halo = np.full(total_halos, -1, dtype='i4')
                next_halo = np.full(total_halos, -1, dtype='i4')
                
                # FOF-based sorting means halons in same group are typically sequential
                current_grp = -1
                current_first = -1
                for i in range(total_halos):
                    if group_nr[i] != current_grp:
                        current_grp = group_nr[i]
                        current_first = i
                    first_halo[i] = current_first
                    if i + 1 < total_halos and group_nr[i+1] == current_grp:
                        next_halo[i] = i + 1
                        
                group.create_dataset('FirstHaloInFOFgroup', data=first_halo)
                group.create_dataset('NextHaloInFOFgroup', data=next_halo)

            f_out.create_dataset("TreeNHalos", data=np.array([total_halos], dtype='i4'))

    print(f"Successfully converted SubLink tree to {output_path}")
