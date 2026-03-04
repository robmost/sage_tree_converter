import os
import re
import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class AHFDriver:
    """
    AHF Driver for converting N-snapshots and M MergerTree link files to SAGE HDF5.
    Supports snapshot skipping by resolving links via global ID mapping.
    """
    
    def __init__(self, halo_files, mtree_files):
        self.halo_files = sorted(halo_files)
        self.mtree_files = mtree_files # No sorting assumption needed for skipping
        
    def check_completeness(self, total_halos, links_found):
        """Verify if the data is sufficient for a SAGE tree."""
        if len(self.halo_files) < 2:
            print("ERROR: SAGE requires at least 2 snapshots to form a temporal tree.")
            return False
        
        if links_found == 0:
            print("ERROR: No valid links found between snapshots. Check if MergerTree IDs match Halo IDs.")
            return False
            
        return True

    def read_ahf_halos(self, path):
        """Read AHF halo catalog into a dictionary."""
        df = pd.read_csv(path, sep='\s+', comment='#', header=None)
        # Mapping: 0:ID, 3:Mhalo, 5-7:Pos, 8-10:Vel, 16:Vmax
        data = {
            'id': df[0].values,
            'Mvir': df[3].values / 1e10,
            'Pos': df[[5, 6, 7]].values / 1000.0,
            'Vel': df[[8, 9, 10]].values,
            'Vmax': df[16].values,
            'SnapNum': int(re.search(r'snap_(\d+)', path).group(1))
        }
        return data

    def convert(self, output_path):
        """
        Convert AHF catalogs and MergerTree links to SAGE HDF5.
        Uses a global ID map to handle snapshot skipping.
        """
        all_snap_data = []
        for h_file in reversed(self.halo_files):
            all_snap_data.append(self.read_ahf_halos(h_file))
            
        # 1. Flatten into combined arrays and build global ID map
        combined_mvir = np.concatenate([h['Mvir'] for h in all_snap_data])
        combined_pos = np.concatenate([h['Pos'] for h in all_snap_data])
        combined_vel = np.concatenate([h['Vel'] for h in all_snap_data])
        combined_snap = np.concatenate([np.full(len(h['id']), h['SnapNum']) for h in all_snap_data])
        combined_ids = np.concatenate([h['id'] for h in all_snap_data])
        
        total_halos = len(combined_ids)
        id_to_global_idx = {hid: i for i, hid in enumerate(combined_ids)}
        
        full_descendants = np.full(total_halos, -1, dtype='i4')
        full_first_progenitors = np.full(total_halos, -1, dtype='i4')
        
        # 2. Parse all MergerTree files and resolve links via global ID map
        links_established = 0
        for m_file in self.mtree_files:
            print(f"Parsing links in: {m_file}")
            with open(m_file, 'r') as f:
                lines = f.readlines()
            
            i = 1 # Skip header line
            while i < len(lines):
                line = lines[i].strip()
                if not line: 
                    i += 1
                    continue
                
                parts = line.split()
                if len(parts) < 2: # Likely a trailing ProgID line or corrupt
                    i += 1
                    continue
                    
                desc_id = int(parts[0])
                num_prog = int(parts[1])
                i += 1
                
                for p_idx_in_block in range(num_prog):
                    if i >= len(lines): break
                    prog_id = int(lines[i].strip().split()[0])
                    
                    # Resolve indices regardless of which snapshot they are from (Skipping support)
                    if desc_id in id_to_global_idx and prog_id in id_to_global_idx:
                        d_idx = id_to_global_idx[desc_id]
                        p_idx = id_to_global_idx[prog_id]
                        
                        # Link main progenitor (first in block)
                        if p_idx_in_block == 0:
                            full_descendants[p_idx] = d_idx
                            if full_first_progenitors[d_idx] == -1:
                                full_first_progenitors[d_idx] = p_idx
                                links_established += 1
                    i += 1

        if not self.check_completeness(total_halos, links_established):
            print("Conversion aborted due to incomplete data.")
            return

        # 3. Write HDF5
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f:
            f.attrs['Ntrees'] = 1
            f.attrs['TotNHalos'] = total_halos
            group = f.create_group("Tree0")
            group.create_dataset("Mvir", data=combined_mvir)
            group.create_dataset("Pos", data=combined_pos)
            group.create_dataset("Vel", data=combined_vel)
            group.create_dataset("SnapNum", data=combined_snap)
            group.create_dataset("Descendant", data=full_descendants)
            group.create_dataset("FirstProgenitor", data=full_first_progenitors)
            f.create_dataset("TreeNHalos", data=np.array([total_halos], dtype='i4'))

        print(f"Successfully converted {total_halos} halos and {links_established} links.")
        self.plot_validation(all_snap_data[0], output_path)

    def plot_validation(self, latest_snap_data, output_path):
        """Plot Halo Mass Function for the latest snapshot."""
        plt.figure(figsize=(8, 6))
        masses = latest_snap_data['Mvir']
        log_masses = np.log10(masses[masses > 0])
        plt.hist(log_masses, bins=30, density=True, alpha=0.7, color='steelblue')
        plt.xlabel(r'$\log_{10}(M_{vir} / [10^{10} M_\odot/h])$')
        plt.ylabel('Normalized Frequency')
        plt.title(f'Validation: HMF (Snap {latest_snap_data["SnapNum"]})')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.savefig(output_path.replace('.hdf5', '_validation.png'))
        plt.close()
