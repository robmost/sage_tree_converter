import h5py
import numpy as np
import os
import matplotlib.pyplot as plt

def plot_hmf(masses, snap_num, output_path):
    """Plot Halo Mass Function for validation."""
    plt.figure(figsize=(8, 6))
    log_masses = np.log10(masses[masses > 0])
    plt.hist(log_masses, bins=30, density=True, alpha=0.7, color='orange')
    plt.xlabel(r'$\log_{10}(M_{vir} / [10^{10} M_\odot/h])$')
    plt.ylabel('Normalized Frequency')
    plt.title(f'Validation: Gadget-4 HMF (Snap {snap_num})')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.savefig(output_path.replace('.hdf5', '_validation.png'))
    plt.close()

def convert(input_path, output_path, n_trees=10):
    """Convert Gadget-4 HDF5 trees to SAGE-compatible HDF5."""
    with h5py.File(input_path, 'r') as f_in:
        lengths = f_in['TreeTable/Length'][:]
        total_halos_to_read = np.sum(lengths[:n_trees])
        halos = {}
        for key in f_in['TreeHalos'].keys():
            halos[key] = f_in[f'TreeHalos/{key}'][:total_halos_to_read]
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f_out:
            f_out.attrs['Ntrees'] = n_trees
            f_out.attrs['TotNHalos'] = total_halos_to_read
            group = f_out.create_group("Tree0")
            
            # Direct mapping from Gadget-4 to SAGE/Millennium schema
            mapping = {
                'Descendant': 'TreeDescendant', 'FirstProgenitor': 'TreeFirstProgenitor',
                'NextProgenitor': 'TreeNextProgenitor', 'FirstHaloInFOFgroup': 'TreeFirstHaloInFOFgroup',
                'NextHaloInFOFgroup': 'TreeNextHaloInFOFgroup', 'Mvir': 'SubhaloMass',
                'Pos': 'SubhaloPos', 'Vel': 'SubhaloVel', 'Vmax': 'SubhaloVmax',
                'VelDisp': 'SubhaloVelDisp', 'SnapNum': 'SnapNum'
            }
            for sage_key, g4_key in mapping.items():
                group.create_dataset(sage_key, data=halos[g4_key])
            f_out.create_dataset("TreeNHalos", data=lengths[:n_trees])

    print(f"Successfully converted {n_trees} Gadget-4 trees to {output_path}")
    plot_hmf(halos['SubhaloMass'], halos['SnapNum'][0], output_path)
