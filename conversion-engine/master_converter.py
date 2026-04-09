import os
import glob
import h5py
import numpy as np
import argparse

# Modular Drivers (Named by Format + Tooling)
from ascii_ahf_mergertree_driver import AHFDriver as ASCII_AHF_MergerTree_Driver
import binary_subfind_lhalotree_driver
import hdf5_gadget4_driver
import ascii_rockstar_consistenttrees_driver

class MasterConverter:
    """Universal entry point for merger tree conversion to SAGE HDF5."""

    def identify_format_and_tools(self, sample_file):
        """Identify simulation format based on file content and headers."""
        # 1. HDF5 Check
        try:
            with h5py.File(sample_file, 'r') as f:
                if 'TreeHalos' in f: return "HDF5_Gadget4"
                if 'Tree0' in f: return "SAGE-HDF5"
        except: pass

        # 2. ASCII Check
        try:
            with open(sample_file, 'r') as f:
                line = f.readline()
                if 'scale(0)' in line: return "ASCII_Rockstar_ConsistentTrees"
                if '#ID(1)' in line or 'hostHalo' in line: return "ASCII_AHF_MergerTree"
        except: pass

        # 3. Binary Check
        try:
            with open(sample_file, 'rb') as f:
                header = np.fromfile(f, dtype='i4', count=2)
                if len(header) == 2 and header[0] > 0 and header[1] > 0:
                    return "Binary_Subfind_LHaloTree"
        except: pass

        return "Unknown"

    def run(self, input_pattern, output_path, n_trees=None):
        files = glob.glob(input_pattern)
        if not files:
            print(f"Error: No files found matching {input_pattern}")
            return

        fmt_tag = self.identify_format_and_tools(files[0])
        print(f"Detected Format/Tooling: {fmt_tag}")

        if fmt_tag == "ASCII_AHF_MergerTree":
            halos = [f for f in files if '.AHF_halos' in f]
            links = [f for f in files if '_mtree' in f and all(x not in f for x in ['idx', 'croco'])]
            ASCII_AHF_MergerTree_Driver(halos, links).convert(output_path)
        elif fmt_tag == "ASCII_Rockstar_ConsistentTrees":
            ascii_rockstar_consistenttrees_driver.convert(files[0], output_path)
        elif fmt_tag == "Binary_Subfind_LHaloTree":
            binary_subfind_lhalotree_driver.convert(files, output_path, n_trees=n_trees)
        elif fmt_tag == "HDF5_Gadget4":
            hdf5_gadget4_driver.convert(files[0], output_path)
        else:
            print(f"Error: Format tag '{fmt_tag}' not supported or insufficient files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Universal Merger Tree Converter")
    parser.add_argument("--input", required=True, help="Glob pattern for input files")
    parser.add_argument("--output", required=True, help="Output HDF5 path")
    parser.add_argument("--n_trees", type=int, default=None, help="Number of trees to convert (for testing)")
    args = parser.parse_args()

    MasterConverter().run(args.input, args.output, n_trees=args.n_trees)
