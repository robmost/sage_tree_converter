import os
import re
import h5py
import numpy as np
import pandas as pd

class AHFDriver:
    """
    AHF Driver for converting N-snapshots and M MergerTree link files to SAGE HDF5.
    Implements SAGE pointer synthesization and synthetic mass approximations.
    """

    def __init__(self, halo_files, mtree_files):
        # Sort such that snapshot 0 is first, N is last, but since we read backwards, we sort naturally
        # and then process reversed
        self.halo_files = sorted(halo_files)
        self.mtree_files = mtree_files

    def check_completeness(self, total_halos, links_found):
        if len(self.halo_files) < 2:
            print("ERROR: SAGE requires at least 2 snapshots to form a temporal tree.")
            return False
        if links_found == 0:
            print("ERROR: No valid links found between snapshots.")
            return False
        return True

    def read_ahf_halos(self, path):
        """Read AHF halo catalog into a dictionary."""
        print(f"Reading {path}...")
        df = pd.read_csv(path, sep=r'\s+', comment='#', header=None)
        
        # 0:ID, 1:hostHalo, 3:Mhalo, 5-7:Pos, 8-10:Vel, 16:Vmax, 18:sigV
        n_halos = len(df)
        # AHF provides a dimensionless unit vector for the axis of rotation (Lx, Ly, Lz).
        # SAGE requires a 3-component Specific Angular Momentum vector (j = L/M).
        # Without Vvir and Rvir, we cannot safely reconstruct the full vector magnitude.
        # Fallback to zero array.
        spin_array = np.zeros((n_halos, 3), dtype='f4')
        
        data = {
            'id': df[0].values,
            'hostHalo': df[1].values,
            'Mvir': df[3].values / 1e10,
            'M_Mean200': df[3].values / 1e10,
            'M_TopHat': df[3].values / 1e10,
            'Pos': df[[5, 6, 7]].values / 1000.0,
            'Vel': df[[8, 9, 10]].values,
            'Vmax': df[16].values,
            'VelDisp': df[18].values,
            'Spin': spin_array,
            'SnapNum': int(re.search(r'snap_(\d+)', path).group(1))
        }
        return data

    def convert(self, output_path, n_trees=None):
        all_snap_data = []
        for h_file in reversed(self.halo_files): # Start from lowest redshift
            all_snap_data.append(self.read_ahf_halos(h_file))

        # Flatten all snapshots
        combined_ids = np.concatenate([h['id'] for h in all_snap_data])
        combined_host = np.concatenate([h['hostHalo'] for h in all_snap_data])
        combined_mvir = np.concatenate([h['Mvir'] for h in all_snap_data])
        combined_m200 = np.concatenate([h['M_Mean200'] for h in all_snap_data])
        combined_mtop = np.concatenate([h['M_TopHat'] for h in all_snap_data])
        combined_pos = np.concatenate([h['Pos'] for h in all_snap_data])
        combined_vel = np.concatenate([h['Vel'] for h in all_snap_data])
        combined_vmax = np.concatenate([h['Vmax'] for h in all_snap_data])
        combined_veldisp = np.concatenate([h['VelDisp'] for h in all_snap_data])
        combined_spin = np.concatenate([h['Spin'] for h in all_snap_data])
        combined_snap = np.concatenate([np.full(len(h['id']), h['SnapNum']) for h in all_snap_data])
        
        total_halos = len(combined_ids)
        id_to_global_idx = {hid: i for i, hid in enumerate(combined_ids)}

        # Initialize SAGE Pointers
        full_descendants = np.full(total_halos, -1, dtype='i4')
        full_first_progenitors = np.full(total_halos, -1, dtype='i4')
        full_next_progenitors = np.full(total_halos, -1, dtype='i4')
        full_first_halo_in_fof = np.full(total_halos, -1, dtype='i4')
        full_next_halo_in_fof = np.full(total_halos, -1, dtype='i4')

        # Construct FOF Groups (Spatial Links within same snapshot)
        print("Constructing FOF spatial links...")
        
        # We need to process each snapshot separately to avoid cross-snapshot FOF linking
        offset = 0
        for h in all_snap_data:
            snap_len = len(h['id'])
            snap_host = h['hostHalo']
            snap_ids = h['id']
            
            # Local ID to local index mapping for this snapshot
            local_id_to_idx = {hid: (i + offset) for i, hid in enumerate(snap_ids)}
            
            last_subhalo_idx = {}
            for i in range(snap_len):
                global_idx = i + offset
                host_id = snap_host[i]
                
                if host_id == 0 or host_id not in local_id_to_idx:
                    # It's a host (or host is missing from catalog)
                    full_first_halo_in_fof[global_idx] = global_idx
                    last_subhalo_idx[snap_ids[i]] = global_idx
                else:
                    # It's a subhalo
                    host_global_idx = local_id_to_idx[host_id]
                    full_first_halo_in_fof[global_idx] = host_global_idx
                    
                    if host_id in last_subhalo_idx:
                        # Link previous subhalo's next pointer to this one
                        prev_idx = last_subhalo_idx[host_id]
                        full_next_halo_in_fof[prev_idx] = global_idx
                    
                    # Update last known subhalo for this host
                    last_subhalo_idx[host_id] = global_idx
                    
            offset += snap_len

        # Parse MergerTree (Temporal Links)
        links_established = 0
        for m_file in self.mtree_files:
            print(f"Parsing temporal links in: {m_file}")
            with open(m_file, 'r') as f:
                lines = f.readlines()

            i = 1 # Skip header
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue

                parts = line.split()
                if len(parts) < 2:
                    i += 1
                    continue

                desc_id = int(parts[0])
                num_prog = int(parts[1])
                i += 1

                for p_idx_in_block in range(num_prog):
                    if i >= len(lines): break
                    prog_id = int(lines[i].strip().split()[0])

                    if desc_id in id_to_global_idx and prog_id in id_to_global_idx:
                        d_idx = id_to_global_idx[desc_id]
                        p_idx = id_to_global_idx[prog_id]

                        # descendant always points to main progenitor? No, prog points to desc.
                        full_descendants[p_idx] = d_idx

                        if p_idx_in_block == 0:
                            if full_first_progenitors[d_idx] == -1:
                                full_first_progenitors[d_idx] = p_idx
                                links_established += 1
                        else:
                            # Find the last progenitor and link it
                            curr_prog = full_first_progenitors[d_idx]
                            if curr_prog != -1:
                                while full_next_progenitors[curr_prog] != -1:
                                    curr_prog = full_next_progenitors[curr_prog]
                                full_next_progenitors[curr_prog] = p_idx

                    i += 1

        if not self.check_completeness(total_halos, links_established):
            return

        # If n_trees is set, we sample the data (Take top N massive halos at Z=0 and trace back)
        if n_trees is not None and n_trees < total_halos:
            print(f"Sampling tree to top {n_trees} massive root halos...")
            valid_indices = set()
            
            # Find roots (halos with no descendants)
            roots = np.where(full_descendants == -1)[0]
            # Sort roots by mass descending
            roots_sorted = roots[np.argsort(combined_mvir[roots])[::-1]]
            sampled_roots = roots_sorted[:n_trees]
            
            # Trace lineages
            for root_idx in sampled_roots:
                queue = [root_idx]
                while queue:
                    curr = queue.pop(0)
                    valid_indices.add(curr)
                    
                    # Add progenitors
                    prog = full_first_progenitors[curr]
                    while prog != -1:
                        queue.append(prog)
                        prog = full_next_progenitors[prog]
                        
            valid_indices = sorted(list(valid_indices))
            
            # Re-map global indices
            old_to_new_idx = {old: new for new, old in enumerate(valid_indices)}
            old_to_new_idx[-1] = -1
            
            combined_ids = combined_ids[valid_indices]
            combined_mvir = combined_mvir[valid_indices]
            combined_m200 = combined_m200[valid_indices]
            combined_mtop = combined_mtop[valid_indices]
            combined_pos = combined_pos[valid_indices]
            combined_vel = combined_vel[valid_indices]
            combined_vmax = combined_vmax[valid_indices]
            combined_veldisp = combined_veldisp[valid_indices]
            combined_spin = combined_spin[valid_indices]
            combined_snap = combined_snap[valid_indices]
            
            full_descendants = np.array([old_to_new_idx.get(full_descendants[i], -1) for i in valid_indices], dtype='i4')
            full_first_progenitors = np.array([old_to_new_idx.get(full_first_progenitors[i], -1) for i in valid_indices], dtype='i4')
            full_next_progenitors = np.array([old_to_new_idx.get(full_next_progenitors[i], -1) for i in valid_indices], dtype='i4')
            full_first_halo_in_fof = np.array([old_to_new_idx.get(full_first_halo_in_fof[i], -1) for i in valid_indices], dtype='i4')
            # If a host was dropped during sampling, the subhalo becomes its own host in the subset
            missing_hosts = (full_first_halo_in_fof == -1)
            full_first_halo_in_fof[missing_hosts] = np.arange(len(valid_indices))[missing_hosts]
            
            full_next_halo_in_fof = np.array([old_to_new_idx.get(full_next_halo_in_fof[i], -1) for i in valid_indices], dtype='i4')
            
            total_halos = len(valid_indices)

        # Write HDF5
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with h5py.File(output_path, 'w') as f:
            f.attrs['Ntrees'] = 1
            f.attrs['TotNHalos'] = total_halos
            group = f.create_group("Tree0")
            group.create_dataset("Mvir", data=combined_mvir)
            group.create_dataset("M_Mean200", data=combined_m200)
            group.create_dataset("M_TopHat", data=combined_mtop)
            group.create_dataset("Pos", data=combined_pos)
            group.create_dataset("Vel", data=combined_vel)
            group.create_dataset("Vmax", data=combined_vmax)
            group.create_dataset("VelDisp", data=combined_veldisp)
            group.create_dataset("Spin", data=combined_spin)
            group.create_dataset("SnapNum", data=combined_snap)
            group.create_dataset("Descendant", data=full_descendants)
            group.create_dataset("FirstProgenitor", data=full_first_progenitors)
            group.create_dataset("NextProgenitor", data=full_next_progenitors)
            group.create_dataset("FirstHaloInFOFgroup", data=full_first_halo_in_fof)
            group.create_dataset("NextHaloInFOFgroup", data=full_next_halo_in_fof)
            f.create_dataset("TreeNHalos", data=np.array([total_halos], dtype='i4'))

        print(f"Successfully converted {total_halos} halos to {output_path}")
