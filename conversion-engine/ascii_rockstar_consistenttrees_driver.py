import h5py
import numpy as np
import os
from collections import defaultdict

def convert(input_path, output_path, n_trees=None):
    """Convert Rockstar/ConsistentTrees ASCII to SAGE-compatible HDF5 memory efficiently using chunked streaming."""
    print(f"Converting {input_path} to {output_path} (n_trees={n_trees})...")
    import glob
    
    files = glob.glob(input_path) if '*' in input_path else [input_path]
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with h5py.File(output_path, 'w') as f:
        tree_idx = 0
        tot_nhalos = 0
        tree_nhalos = []
        
        for file in files:
            print(f"Streaming {file} in chunks...")
            
            trees_chunk = defaultdict(list)
            
            def flush_chunk():
                nonlocal tree_idx, tot_nhalos
                for root_id, tree_halos in list(trees_chunk.items()):
                    if n_trees is not None and tree_idx >= n_trees:
                        break
                        
                    if not tree_halos: continue
                    
                    tree_grp = f.create_group(f"Tree{tree_idx}")
                    tree_nhalos.append(len(tree_halos))
                    tot_nhalos += len(tree_halos)
                    
                    id_to_local_idx = {h['id']: idx for idx, h in enumerate(tree_halos)}
                    desc_to_progs = defaultdict(list)
                    for idx, h in enumerate(tree_halos):
                        desc_local_idx = id_to_local_idx.get(h['desc_id'], -1)
                        h['local_desc_idx'] = desc_local_idx
                        if desc_local_idx != -1:
                            desc_to_progs[desc_local_idx].append(idx)

                    first_prog = np.full(len(tree_halos), -1, dtype='i4')
                    next_prog = np.full(len(tree_halos), -1, dtype='i4')
                    descendant = np.array([h['local_desc_idx'] for h in tree_halos], dtype='i4')

                    for desc_idx, prog_indices in desc_to_progs.items():
                        prog_indices.sort(key=lambda idx: tree_halos[idx]['mvir'], reverse=True)
                        first_prog[desc_idx] = prog_indices[0]
                        for p in range(len(prog_indices) - 1):
                            next_prog[prog_indices[p]] = prog_indices[p+1]
                            
                    first_fof = np.full(len(tree_halos), -1, dtype='i4')
                    next_fof = np.full(len(tree_halos), -1, dtype='i4')
                    snaps = defaultdict(list)
                    for idx, h in enumerate(tree_halos):
                        snaps[h['snap']].append(idx)
                        
                    for snap, idxs in snaps.items():
                        hosts = {}
                        for idx in idxs:
                            h = tree_halos[idx]
                            host_id = h['id'] if h['upid'] == -1 else h['upid']
                            if host_id not in hosts: hosts[host_id] = []
                            hosts[host_id].append(idx)
                            
                        for host_id, fof_members in hosts.items():
                            fof_members.sort(key=lambda idx: tree_halos[idx]['mvir'], reverse=True)
                            first_idx = fof_members[0]
                            for p in range(len(fof_members)):
                                first_fof[fof_members[p]] = first_idx
                                if p < len(fof_members) - 1:
                                    next_fof[fof_members[p]] = fof_members[p+1]

                    mvir_arr = np.array([h['mvir'] for h in tree_halos], dtype='f4')
                    data = {
                        'Descendant': descendant,
                        'FirstProgenitor': first_prog,
                        'NextProgenitor': next_prog,
                        'FirstHaloInFOFgroup': first_fof,
                        'NextHaloInFOFgroup': next_fof,
                        'Mvir': mvir_arr,
                        'M_Mean200': mvir_arr.copy(),
                        'M_TopHat': mvir_arr.copy(),
                        'Vmax': np.array([h['vmax'] for h in tree_halos], dtype='f4'),
                        'Pos': np.array([h['pos'] for h in tree_halos], dtype='f4'),
                        'Vel': np.array([h['vel'] for h in tree_halos], dtype='f4'),
                        'SnapNum': np.array([h['snap'] for h in tree_halos], dtype='i4'),
                        'Spin': np.array([[h['spin'], 0.0, 0.0] for h in tree_halos], dtype='f4'),
                        'OriginalID': np.array([h['id'] for h in tree_halos], dtype='i8')
                    }
                    
                    for key, val in data.items():
                        tree_grp.create_dataset(key, data=val)
                    
                    tree_idx += 1
                
                trees_chunk.clear()

            with open(file, 'r') as file_obj:
                for line in file_obj:
                    if line.startswith('#'): continue
                    parts = line.split()
                    if not parts or len(parts) < 32: continue
                    
                    try:
                        root_id = int(parts[29])
                        
                        trees_chunk[root_id].append({
                            'id': int(parts[1]),
                            'desc_id': int(parts[3]),
                            'pid': int(parts[5]),
                            'upid': int(parts[6]),
                            'mvir': float(parts[10]) / 1e10,
                            'vmax': float(parts[16]),
                            'pos': [float(parts[17]), float(parts[18]), float(parts[19])],
                            'vel': [float(parts[20]), float(parts[21]), float(parts[22])],
                            'snap': int(parts[31]),
                            'root_id': root_id,
                            'spin': float(parts[26])
                        })
                        
                        # Flush every 5000 trees to keep memory low
                        if len(trees_chunk) >= 5000:
                            flush_chunk()
                            
                    except (ValueError, IndexError):
                        continue
                        
                # Flush remaining
                flush_chunk()
                
            if n_trees is not None and tree_idx >= n_trees:
                break
                
        f.attrs['Ntrees'] = tree_idx
        f.attrs['TotNHalos'] = tot_nhalos
        f.create_dataset("TreeNHalos", data=np.array(tree_nhalos, dtype='i4'))

    print(f"Successfully converted {tot_nhalos} halos across {tree_idx} trees.")
