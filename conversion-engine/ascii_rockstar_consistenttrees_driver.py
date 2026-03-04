import h5py
import numpy as np
import os
import matplotlib.pyplot as plt

def plot_hmf(masses, snap_num, output_path):
    """Plot Halo Mass Function for validation."""
    plt.figure(figsize=(8, 6))
    log_masses = np.log10(masses[masses > 0])
    plt.hist(log_masses, bins=30, density=True, alpha=0.7, color='purple')
    plt.xlabel(r'$\log_{10}(M_{vir} / [M_\odot/h])$')
    plt.ylabel('Normalized Frequency')
    plt.title(f'Validation: Bolshoi HMF (Snap {snap_num})')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.savefig(output_path.replace('.hdf5', '_validation.png'))
    plt.close()

def convert(input_path, output_path, n_lines=10000):
    """Convert Bolshoi (Rockstar/ConsistentTrees) ASCII to SAGE-compatible HDF5."""
    halos = []
    with open(input_path, 'r') as f:
        count = 0
        for line in f:
            if line.startswith('#'): continue
            parts = line.split()
            if not parts: continue
            try:
                # Based on ConsistentTrees ASCII column mapping
                halos.append({
                    'Descendant': int(parts[3]), 'id': int(parts[1]),
                    'Mvir': float(parts[10]), 'Vmax': float(parts[16]),
                    'Pos': [float(parts[17]), float(parts[18]), float(parts[19])],
                    'Vel': [float(parts[20]), float(parts[21]), float(parts[22])],
                    'SnapNum': int(parts[31]), 'DepthFirstID': int(parts[28])
                })
            except: continue
            count += 1
            if count >= n_lines: break

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f_out:
        f_out.attrs['Ntrees'] = 1
        f_out.attrs['TotNHalos'] = len(halos)
        group = f_out.create_group("Tree0")
        for key in halos[0].keys():
            group.create_dataset(key, data=np.array([h[key] for h in halos]))
        f_out.create_dataset("TreeNHalos", data=np.array([len(halos)], dtype='i4'))

    print(f"Successfully converted {len(halos)} Bolshoi halos to {output_path}")
    plot_hmf(np.array([h['Mvir'] for h in halos]), halos[0]['SnapNum'], output_path)
