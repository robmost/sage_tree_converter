import numpy as np
import h5py
import os
import matplotlib.pyplot as plt

# LHaloTree C-struct as numpy dtype (104 bytes)
HALO_DTYPE = np.dtype([
    ('Descendant', 'i4'), ('FirstProgenitor', 'i4'), ('NextProgenitor', 'i4'),
    ('FirstHaloInFOFgroup', 'i4'), ('NextHaloInFOFgroup', 'i4'),
    ('Len', 'i4'), ('M_Mean200', 'f4'), ('M_Crit200', 'f4'), ('M_TopHat', 'f4'),
    ('Pos', 'f4', (3,)), ('Vel', 'f4', (3,)), ('VelDisp', 'f4'), ('Vmax', 'f4'),
    ('Spin', 'f4', (3,)), ('MostBoundID', 'i8'), ('SnapNum', 'i4'),
    ('FileNr', 'i4'), ('SubhaloIndex', 'i4'), ('SubHalfMass', 'f4')
])

def plot_hmf(masses, snap_num, output_path):
    """Plot Halo Mass Function for validation."""
    plt.figure(figsize=(8, 6))
    log_masses = np.log10(masses[masses > 0])
    plt.hist(log_masses, bins=30, density=True, alpha=0.7, color='green')
    plt.xlabel(r'$\log_{10}(M_{vir} / [10^{10} M_\odot/h])$')
    plt.ylabel('Normalized Frequency')
    plt.title(f'Validation: Millennium HMF (Snap {snap_num})')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.savefig(output_path.replace('.hdf5', '_validation.png'))
    plt.close()

def convert(input_path, output_path, n_trees=10):
    """Convert Millennium binary trees to SAGE-compatible HDF5."""
    with open(input_path, 'rb') as f:
        ntrees = np.fromfile(f, dtype='i4', count=1)[0]
        tot_nhalos = np.fromfile(f, dtype='i4', count=1)[0]
        tree_nhalos = np.fromfile(f, dtype='i4', count=ntrees)
        
        halos_to_read = sum(tree_nhalos[:n_trees])
        halos = np.fromfile(f, dtype=HALO_DTYPE, count=halos_to_read)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as hf:
        hf.attrs['Ntrees'] = n_trees
        hf.attrs['TotNHalos'] = halos_to_read
        group = hf.create_group("Tree0")
        for field in halos.dtype.names:
            group.create_dataset(field, data=halos[field])
        hf.create_dataset("TreeNHalos", data=tree_nhalos[:n_trees])

    print(f"Successfully converted {n_trees} trees to {output_path}")
    plot_hmf(halos['M_TopHat'], halos['SnapNum'][0], output_path)
