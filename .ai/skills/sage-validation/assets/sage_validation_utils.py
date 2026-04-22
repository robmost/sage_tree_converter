import numpy as np
import matplotlib.pyplot as plt
import os
import sys

STYLE_PATH = '.ai/skills/sage-validation/assets/sage_validation.mplstyle'
if os.path.exists(STYLE_PATH):
    plt.style.use(STYLE_PATH)

# The 7 mandatory plots defined by the SAGE Validation Protocol
REQUIRED_PLOTS = ["mah", "merger_rate", "spin", "velocity", "lifespan", "hmf", "spatial"]

def calculate_relative_difference(input_data, output_data, threshold=1e-8):
    """
    Computes (out - inp) / inp.
    Includes anti-cheating checks that raise exceptions to prevent context drift shortcuts.
    """
    inp = np.asarray(input_data, dtype=np.float32)
    out = np.asarray(output_data, dtype=np.float32)

    if inp.shape == out.shape and np.allclose(inp, out, atol=threshold):
        raise ValueError("ANTI-CHEATING FAILURE: Input and Output arrays are perfectly identical (rel_diff=0.0). "
                         "You MUST NOT derive 'Input' from 'Output' (or vice versa). "
                         "Read the raw Input files independently.")

    diff = np.zeros_like(inp)
    mask = inp != 0
    diff[mask] = (out[mask] - inp[mask]) / inp[mask]
    
    # Check for linear scaling "cheating"
    if np.sum(mask) > 1:
        diff_var = np.var(diff[mask])
        if diff_var < 1e-12 and not np.allclose(diff[mask], 0.0, atol=threshold):
            raise ValueError(f"ANTI-CHEATING FAILURE: The relative difference is perfectly constant (variance={diff_var:.2e}). "
                             "This strongly indicates the Input array was mathematically derived from the Output array via linear scaling. "
                             "You MUST NOT derive Input from Output. Read the raw Input files independently.")
            
    return diff

def verify_completeness(dataset_name):
    """
    Checks the output directory for the presence of all 7 mandatory validation plots.
    """
    print(f"\n--- Validation Completeness Report: {dataset_name} ---")
    missing = []
    for plot_id in REQUIRED_PLOTS:
        filename = f'output/1_validation_{plot_id}_{dataset_name}.png'
        if os.path.exists(filename):
            print(f"[PASS] Found: {filename}")
        else:
            print(f"[FAIL] MISSING: {filename}")
            missing.append(plot_id)

    if not missing:
        print("\033[92m[SUCCESS] All 7 mandatory visualisations are present.\033[0m")
        return True
    else:
        err_msg = f"ANTI-CHEATING FAILURE: Missing {len(missing)} mandatory plot(s): {', '.join(missing)}. You MUST generate all 7 visualisations."
        print(f"\033[91m{err_msg}\033[0m", file=sys.stderr)
        raise AssertionError(err_msg)

def plot_3x3_evolution(plot_id, dataset_name, snapnums, input_arrays, output_arrays, labels, y_label, halo_ids, is_log_y=False):
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    fig.suptitle(f"{plot_id} - {dataset_name}", fontsize=16)

    for row in range(3):
        ax_in = axes[row, 0]
        ax_out = axes[row, 1]
        ax_diff = axes[row, 2]

        snaps = snapnums[row]
        inp_data = input_arrays[row]
        out_data = output_arrays[row]

        # Anti-cheating check for evolution rows
        for h_idx in range(len(inp_data)):
            if np.array_equal(inp_data[h_idx], out_data[h_idx]):
                raise ValueError(f"ANTI-CHEATING FAILURE: Evolution branch for halo {halo_ids[row][h_idx]} "
                                 f"is identical in Input and Output. You MUST NOT derive 'Input' from 'Output'.")

        for h_idx in range(len(inp_data)):
            id_str = str(halo_ids[row][h_idx])
            if len(id_str) > 10:
                id_str = id_str[:4] + ".." + id_str[-4:]
            label_text = f"ID: {id_str}"
            ax_in.plot(snaps[h_idx], inp_data[h_idx], alpha=0.7, marker='.', markersize=5, label=label_text)

        for h_idx in range(len(out_data)):
            id_str = str(halo_ids[row][h_idx])
            if len(id_str) > 10:
                id_str = id_str[:4] + ".." + id_str[-4:]
            label_text = f"ID: {id_str}"
            ax_out.plot(snaps[h_idx], out_data[h_idx], alpha=0.7, marker='.', markersize=5, label=label_text)

        ax_in.legend(fontsize='x-small', loc='best')
        ax_out.legend(fontsize='x-small', loc='best')

        all_snaps = np.unique(np.concatenate(snaps))
        avg_diff = []
        for snap in all_snaps:
            diffs_at_snap = []
            for h_idx in range(len(inp_data)):
                idx = np.where(snaps[h_idx] == snap)[0]
                if len(idx) > 0:
                    i_val = inp_data[h_idx][idx[0]]
                    o_val = out_data[h_idx][idx[0]]
                    if i_val != 0:
                        diffs_at_snap.append((o_val - i_val) / i_val)
                    else:
                        diffs_at_snap.append(0.0)
            avg_diff.append(np.mean(diffs_at_snap) if diffs_at_snap else 0.0)

        ax_diff.plot(all_snaps, avg_diff, color='red', linewidth=2, label='Mean Rel Diff')
        ax_diff.legend()

        for col, ax in enumerate([ax_in, ax_out, ax_diff]):
            ax.set_xlabel('Snapshot Number')
            if col == 0:
                ax.set_ylabel(f"Input {y_label}\n({labels[row]})")
            elif col == 1:
                ax.set_ylabel(f"Output {y_label}")
            else:
                ax.set_ylabel("Relative Difference")
                ax.axhline(0, color='black', linestyle='--', alpha=0.5)

            if is_log_y and col in [0, 1]:
                data_to_check = inp_data if col == 0 else out_data
                any_non_positive = any(np.any(np.asarray(h_data) <= 0) for h_data in data_to_check)
                ax.set_yscale('symlog' if any_non_positive else 'log')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    os.makedirs('output', exist_ok=True)
    plt.savefig(f'output/1_validation_{plot_id}_{dataset_name}.png', dpi=300)
    plt.close()

def plot_1x3_histogram(plot_id, dataset_name, input_data, output_data, x_label, is_log_x=False, is_log_y=False, bins=50):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"{plot_id} - {dataset_name}", fontsize=16)

    inp_clean = input_data[np.isfinite(input_data)]
    out_clean = output_data[np.isfinite(output_data)]

    if is_log_x:
        inp_clean = inp_clean[inp_clean > 0]
        out_clean = out_clean[out_clean > 0]

    if len(inp_clean) == 0 or len(out_clean) == 0:
        print(f"Warning: No valid data to plot for {plot_id}.")
        return

    min_val = min(np.min(inp_clean), np.min(out_clean))
    max_val = max(np.max(inp_clean), np.max(out_clean))

    if is_log_x and min_val > 0:
        bin_edges = np.logspace(np.log10(min_val), np.log10(max_val), bins)
    else:
        bin_edges = np.linspace(min_val, max_val, bins)

    inp_counts, _ = np.histogram(inp_clean, bins=bin_edges)
    out_counts, _ = np.histogram(out_clean, bins=bin_edges)
    bin_centers = 0.5 * (bin_edges[1:] + bin_edges[:-1])

    mask_inp = inp_counts > 0
    axes[0].plot(bin_centers[mask_inp], inp_counts[mask_inp], marker='o', linestyle='-', markersize=4)
    axes[0].set_ylabel('Halo Count')
    axes[0].set_title('Input Data')

    mask_out = out_counts > 0
    axes[1].plot(bin_centers[mask_out], out_counts[mask_out], marker='o', linestyle='-', markersize=4)
    axes[1].set_ylabel('Halo Count')
    axes[1].set_title('Output Data')

    rel_diff = calculate_relative_difference(inp_counts, out_counts)
    axes[2].plot(bin_centers, rel_diff, marker='o', linestyle='-', color='red', markersize=4)
    axes[2].axhline(0, color='black', linestyle='--', alpha=0.5)
    axes[2].set_ylabel('Relative Difference (Counts)')
    axes[2].set_title('Relative Difference')

    for i, ax in enumerate(axes):
        ax.set_xlabel(x_label)
        if is_log_x:
            ax.set_xscale('log')
        if is_log_y and i < 2:
            ax.set_yscale('log')

    plt.tight_layout()
    os.makedirs('output', exist_ok=True)
    plt.savefig(f'output/1_validation_{plot_id}_{dataset_name}.png', dpi=300)
    plt.close()

def plot_1x3_hexbin(plot_id, dataset_name, inp_x, inp_y, out_x, out_y, x_label, y_label):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"{plot_id} - {dataset_name}", fontsize=16)

    hb1 = axes[0].hexbin(inp_x, inp_y, gridsize=50, cmap='viridis', bins='log')
    axes[0].set_title('Input Data')
    axes[0].set_xlabel(x_label)
    axes[0].set_ylabel(y_label)
    fig.colorbar(hb1, ax=axes[0])

    hb2 = axes[1].hexbin(out_x, out_y, gridsize=50, cmap='viridis', bins='log')
    axes[1].set_title('Output Data')
    axes[1].set_xlabel(x_label)
    axes[1].set_ylabel(y_label)
    fig.colorbar(hb2, ax=axes[1])

    inp_r = np.sqrt(inp_x**2 + inp_y**2)
    out_r = np.sqrt(out_x**2 + out_y**2)
    diff_r = calculate_relative_difference(inp_r, out_r)

    hb3 = axes[2].hexbin(inp_r, diff_r, gridsize=50, cmap='inferno', bins='log')
    axes[2].set_title('Radial Relative Difference')
    axes[2].set_xlabel('Input Radial Distance')
    axes[2].set_ylabel('Relative Difference')
    fig.colorbar(hb3, ax=axes[2])

    plt.tight_layout()
    os.makedirs('output', exist_ok=True)
    plt.savefig(f'output/1_validation_{plot_id}_{dataset_name}.png', dpi=300)
    plt.close()
