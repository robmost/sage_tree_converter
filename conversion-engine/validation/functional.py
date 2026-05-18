"""
functional.py — SAGE dry-run functional validation for converted output files.

Supports both lhalo_hdf5 (HDF5) and lhalo_binary output formats. Triggered only
when SAGE_BINARY_PATH is set in the environment. If the variable is absent, the
function returns immediately with status NOT_RUN.

Usage:
    from validation.functional import run_functional_validation
    result = run_functional_validation("output/test.0.hdf5", assets_dir="assets")
    result = run_functional_validation("output/test.0", assets_dir="assets",
                                       output_format="lhalo_binary",
                                       particle_mass=0.086)
    print(result["status"])  # "PASS", "FAIL", or "NOT_RUN"
"""

import os
import struct
import subprocess
from pathlib import Path

import h5py
import numpy as np

# ---------------------------------------------------------------------------
# SAGE parameter file templates (one per output format)
# ---------------------------------------------------------------------------

_PARAM_TEMPLATE_HDF5 = """\
% ================================================
% SAGE parameter file — functional validation dry run
% Generated automatically by validation/functional.py
% ================================================

%-- Simulation box and cosmology --%
% NOTE: BoxSize, Hubble_h, Omega, OmegaLambda are simulation-specific.
%       Set these to the correct values before running a real validation.
BoxSize             100.0               % Mpc/h — placeholder
PartMass            {particle_mass}     % 1e10 Msun/h (from Header/ParticleMass)
Hubble_h            0.0                 % placeholder — fill with simulation value
Omega               0.0                 % placeholder — fill with simulation value
OmegaLambda         0.0                 % placeholder — fill with simulation value
BaryonFrac          0.17

%-- Merger tree input --%
TreeType            lhalo_hdf5
TreeName            {tree_name}
TreeExtension       .hdf5
NtreesPerFile       -1                  % -1 = read from file Header

%-- Output --%
OutputDir           {output_dir}/
FileNameGalaxies    test_galaxies
NumOutputFiles      1

%-- Output snapshots: output at the single lowest-redshift snapshot --%
NumOutputs          1
OutputSnaps         {lowest_snap}

%-- SAGE physics switches: all off for a dry run --%
SFprescription      0
AGNrecipeOn         0
SupernovaRecipeOn   0
ReionizationOn      0
DiskInstabilityOn   0

%-- IMF --%
IMF                 Chabrier

%-- Cosmological file --%
FileWithSnapList
"""

_PARAM_TEMPLATE_BINARY = """\
% ================================================
% SAGE parameter file — functional validation dry run (binary trees)
% Generated automatically by validation/functional.py
% ================================================

%-- Simulation box and cosmology --%
% NOTE: BoxSize, Hubble_h, Omega, OmegaLambda are simulation-specific.
%       Set these to the correct values before running a real validation.
BoxSize             100.0               % Mpc/h — placeholder
PartMass            {particle_mass}     % 1e10 Msun/h
Hubble_h            0.0                 % placeholder — fill with simulation value
Omega               0.0                 % placeholder — fill with simulation value
OmegaLambda         0.0                 % placeholder — fill with simulation value
BaryonFrac          0.17

%-- Merger tree input --%
% lhalo_binary (TreeType=0): SAGE appends .<N> to TreeName.
% Output file test_<base>_STC.0 → TreeName = test_<base>_STC; FirstFile = 0; LastFile = 0.
TreeType            lhalo_binary
TreeName            {tree_name}
NtreesPerFile       -1                  % -1 = read from file header

%-- Output --%
OutputDir           {output_dir}/
FileNameGalaxies    test_galaxies
NumOutputFiles      1

%-- Output snapshots: output at the single lowest-redshift snapshot --%
NumOutputs          1
OutputSnaps         {lowest_snap}

%-- SAGE physics switches: all off for a dry run --%
SFprescription      0
AGNrecipeOn         0
SupernovaRecipeOn   0
ReionizationOn      0
DiskInstabilityOn   0

%-- IMF --%
IMF                 Chabrier

%-- Cosmological file --%
FileWithSnapList
"""

# numpy dtype for reading binary halo records (matches struct halo_data in core_simulation.h)
_BINARY_HALO_DTYPE = np.dtype(
    [
        ("Descendant", np.int32),
        ("FirstProgenitor", np.int32),
        ("NextProgenitor", np.int32),
        ("FirstHaloInFOFgroup", np.int32),
        ("NextHaloInFOFgroup", np.int32),
        ("Len", np.int32),
        ("M_Mean200", np.float32),
        ("Mvir", np.float32),
        ("M_TopHat", np.float32),
        ("Pos", np.float32, 3),
        ("Vel", np.float32, 3),
        ("VelDisp", np.float32),
        ("Vmax", np.float32),
        ("Spin", np.float32, 3),
        ("MostBoundID", np.int64),
        ("SnapNum", np.int32),
        ("FileNr", np.int32),
        ("SubhaloIndex", np.int32),
        ("SubHalfMass", np.float32),
    ]
)


def _read_hdf5_params(hdf5_path: str) -> tuple[float, int]:
    """Return (particle_mass, lowest_redshift_snap) from an HDF5 output file."""
    with h5py.File(hdf5_path, "r") as f:
        hdr: h5py.Group = f["Header"]  # type: ignore[assignment]
        particle_mass = float(hdr.attrs.get("ParticleMass", 0.0))
        max_snap = 0
        for key in f.keys():
            if key.startswith("Tree"):
                grp: h5py.Group = f[key]  # type: ignore[assignment]
                snap_arr = np.asarray(grp["SnapNum"])  # type: ignore[arg-type]
                tree_max = int(np.max(snap_arr))
                if tree_max > max_snap:
                    max_snap = tree_max
    return particle_mass, max_snap


def _read_binary_params(binary_path: str) -> int:
    """Return the lowest-redshift snapshot number from a binary output file.

    Particle mass is not stored in the binary format — the caller must supply it
    via the particle_mass parameter of run_functional_validation().
    """
    with open(binary_path, "rb") as f:
        nforests, totnhalos = struct.unpack("<ii", f.read(8))
        nhalos_per_forest = np.frombuffer(f.read(nforests * 4), dtype=np.int32)
        max_snap = -1
        for n in nhalos_per_forest:
            if n == 0:
                continue
            raw = f.read(int(n) * _BINARY_HALO_DTYPE.itemsize)
            halos = np.frombuffer(raw, dtype=_BINARY_HALO_DTYPE)
            tree_max = int(halos["SnapNum"].max())
            if tree_max > max_snap:
                max_snap = tree_max
    return max_snap


def run_functional_validation(
    output_path: str,
    assets_dir: str = "assets",
    output_format: str = "lhalo_hdf5",
    particle_mass: float | None = None,
    param_overrides: dict | None = None,
) -> dict:
    """Run a SAGE dry run on a converted output file.

    Parameters
    ----------
    output_path : str
        Path to the converted output file. For lhalo_hdf5: a .hdf5 file.
        For lhalo_binary: a binary file (e.g. test_<base>_STC.0, no extension).
    assets_dir : str
        Working directory for intermediate files (parameter file, SAGE output).
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. Controls TreeType in the
        generated SAGE parameter file and which reader is used to extract
        particle_mass and lowest_snap.
    particle_mass : float or None
        Dark matter particle mass in 10^10 Msun/h. Required when output_format
        is 'lhalo_binary' (binary files do not store particle mass). Ignored
        when output_format is 'lhalo_hdf5' (read from HDF5 Header attribute).
    param_overrides : dict or None
        Optional key-value pairs to override additional parameter file
        placeholders (e.g. {'BoxSize': '25.0'}).

    Returns
    -------
    dict with keys:
        "status"     : "PASS" | "FAIL" | "NOT_RUN"
        "reason"     : str — human-readable summary
        "returncode" : int | None
        "stdout"     : str
        "stderr"     : str
        "log_path"   : str | None — path to the parameter file used
    """
    sage_binary = os.environ.get("SAGE_BINARY_PATH")
    if not sage_binary:
        return {
            "status": "NOT_RUN",
            "reason": (
                "SAGE_BINARY_PATH is not set in the environment. Functional validation skipped."
            ),
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "log_path": None,
        }

    if not os.path.isfile(sage_binary):
        in_container = (
            os.path.exists("/.dockerenv")
            or "APPTAINER_CONTAINER" in os.environ
            or "SINGULARITY_CONTAINER" in os.environ
        )
        if in_container:
            return {
                "status": "NOT_RUN",
                "reason": (
                    f"SAGE_BINARY_PATH='{sage_binary}' is set but the path is not "
                    "accessible inside the container. To enable functional validation, "
                    "bind-mount the directory containing the binary into the container. "
                    "See README.md §Container Setup and container/docker-compose.yml for "
                    "instructions."
                ),
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "log_path": None,
            }
        return {
            "status": "FAIL",
            "reason": f"SAGE_BINARY_PATH='{sage_binary}' does not point to an existing file.",
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "log_path": None,
        }

    # -----------------------------------------------------------------------
    # Read parameters from the output file
    # -----------------------------------------------------------------------
    try:
        if output_format == "lhalo_hdf5":
            file_particle_mass, lowest_snap = _read_hdf5_params(output_path)
            if particle_mass is None:
                particle_mass = file_particle_mass
        elif output_format == "lhalo_binary":
            if particle_mass is None:
                return {
                    "status": "FAIL",
                    "reason": (
                        "particle_mass must be supplied for lhalo_binary output "
                        "(binary files do not store ParticleMass in the header)."
                    ),
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "log_path": None,
                }
            lowest_snap = _read_binary_params(output_path)
        else:
            return {
                "status": "FAIL",
                "reason": f"Unknown output_format '{output_format}'.",
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "log_path": None,
            }
    except Exception as exc:
        return {
            "status": "FAIL",
            "reason": f"Could not read parameters from output file: {exc}",
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "log_path": None,
        }

    # -----------------------------------------------------------------------
    # Build tree_name: SAGE appends .<N>.hdf5 (HDF5) or .<N> (binary) to TreeName.
    # Strip the trailing .0.hdf5 or .0 suffix so SAGE reconstructs the full name.
    # -----------------------------------------------------------------------
    output_stem = str(Path(output_path).resolve())
    # Remove known suffixes: .0.hdf5 → strip .hdf5 then .0; .0 → strip .0
    if output_stem.endswith(".hdf5"):
        output_stem = output_stem[: -len(".hdf5")]
    # Strip the trailing .<N> (file index) so TreeName is the bare base
    stem_path = Path(output_stem)
    if stem_path.suffix and stem_path.suffix.lstrip(".").isdigit():
        tree_name = str(stem_path.with_suffix(""))
    else:
        tree_name = output_stem

    # -----------------------------------------------------------------------
    # Write SAGE parameter file
    # -----------------------------------------------------------------------
    assets_path = Path(assets_dir)
    sage_output_dir = assets_path / "sage_test_output"
    sage_output_dir.mkdir(parents=True, exist_ok=True)

    param_values = {
        "particle_mass": f"{particle_mass:.6g}",
        "tree_name": tree_name,
        "output_dir": str(sage_output_dir.resolve()),
        "lowest_snap": str(lowest_snap),
    }
    if param_overrides:
        param_values.update(param_overrides)

    template = _PARAM_TEMPLATE_BINARY if output_format == "lhalo_binary" else _PARAM_TEMPLATE_HDF5
    param_content = template.format(**param_values)
    param_file = assets_path / "test_sage_params.par"
    param_file.write_text(param_content)

    # -----------------------------------------------------------------------
    # Run SAGE
    # -----------------------------------------------------------------------
    try:
        proc = subprocess.run(
            [sage_binary, str(param_file)],
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return {
            "status": "FAIL",
            "reason": f"Failed to launch SAGE binary: {exc}",
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "log_path": str(param_file),
        }

    if proc.returncode == 0:
        return {
            "status": "PASS",
            "reason": "SAGE exited with status 0.",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "log_path": str(param_file),
        }
    else:
        return {
            "status": "FAIL",
            "reason": (
                f"SAGE exited with non-zero status {proc.returncode}. "
                "See stdout/stderr for details."
            ),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "log_path": str(param_file),
        }
