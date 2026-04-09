import h5py
import numpy as np
import os
from collections import defaultdict

def convert(input_path, output_path):
    """Convert Rockstar/ConsistentTrees ASCII to SAGE-compatible HDF5."""
    print(f"Converting {input_path} to {output_path}...")
    
    # 1. Load Data
    halos = []
    with open(input_path, 'r') as f:
        for line in f:
            if line.startswith('#'): continue
            parts = line.split()
            if not parts or len(parts) < 32: continue
            
            try:
                # ID(1), DescID(3), Mvir(10), Vmax(16), X(17), Y(18), Z(19), 
                # VX(20), VY(21), VZ(22), Snap(31), RootID(29), Spin(26)
                halos.append({
                    'id': int(parts[1]),
                    'desc_id': int(parts[3]),
                    'mvir': float(parts[10]) / 1e10, # SAGE units: 10^10 Msun/h
                    'vmax': float(parts[16]),
                    'pos': [float(parts[17]), float(parts[18]), float(parts[19])],
                    'vel': [float(parts[20]), float(parts[21]), float(parts[22])],
                    'snap': int(parts[31]),
                    'root_id': int(parts[29]),
                    'spin': float(parts[26])
                })
            except (ValueError, IndexError):
                continue

    if not halos:
        print("Error: No valid halos found.")
        return

    # 2. Group into Trees by RootID
    trees_raw = defaultdict(list)
    for h in halos:
        trees_raw[h['root_id']].append(h)

    # 3. Write HDF5
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f:
        f.attrs['Ntrees'] = len(trees_raw)
        f.attrs['TotNHalos'] = len(halos)
        
        tree_nhalos = []
        for i, (root_id, tree_halos) in enumerate(trees_raw.items()):
            tree_grp = f.create_group(f"Tree{i}")
            tree_nhalos.append(len(tree_halos))
            
            # Localize pointers within this tree
            id_to_local_idx = {h['id']: idx for idx, h in enumerate(tree_halos)}
            
            # Map progenitors to find First/Next
            desc_to_progs = defaultdict(list)
            for idx, h in enumerate(tree_halos):
                # Only if descendant is in the SAME tree
                desc_local_idx = id_to_local_idx.get(h['desc_id'], -1)
                h['local_desc_idx'] = desc_local_idx
                if desc_local_idx != -1:
                    desc_to_progs[desc_local_idx].append(idx)

            first_prog = np.full(len(tree_halos), -1, dtype='i4')
            next_prog = np.full(len(tree_halos), -1, dtype='i4')
            descendant = np.array([h['local_desc_idx'] for h in tree_halos], dtype='i4')

            for desc_idx, prog_indices in desc_to_progs.items():
                # Sort by mass for main progenitor
                prog_indices.sort(key=lambda idx: tree_halos[idx]['mvir'], reverse=True)
                first_prog[desc_idx] = prog_indices[0]
                for p in range(len(prog_indices) - 1):
                    next_prog[prog_indices[p]] = prog_indices[p+1]
            
            # Prepare datasets
            data = {
                'Descendant': descendant,
                'FirstProgenitor': first_prog,
                'NextProgenitor': next_prog,
                'Mvir': np.array([h['mvir'] for h in tree_halos], dtype='f4'),
                'Vmax': np.array([h['vmax'] for h in tree_halos], dtype='f4'),
                'Pos': np.array([h['pos'] for h in tree_halos], dtype='f4'),
                'Vel': np.array([h['vel'] for h in tree_halos], dtype='f4'),
                'SnapNum': np.array([h['snap'] for h in tree_halos], dtype='i4'),
                'Spin': np.array([h['spin'] for h in tree_halos], dtype='f4'),
                'OriginalID': np.array([h['id'] for h in tree_halos], dtype='i8')
            }
            
            for key, val in data.items():
                tree_grp.create_dataset(key, data=val)
        
        f.create_dataset("TreeNHalos", data=np.array(tree_nhalos, dtype='i4'))

    print(f"Successfully converted {len(halos)} halos across {len(trees_raw)} trees.")
