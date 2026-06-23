"""Regression tests for error propagation through the batch runner (B3).

A failing driver must surface its real cause in JobResult.error - not the old
generic "Driver exited with an error. See messages above." string that hid the
real traceback (especially under --workers N, where worker stderr is lost).
"""

from pathlib import Path

from batch_runner import ConversionJob, JobResult, run_job

_GENERIC = "Driver exited with an error. See messages above."


def test_conversion_job_defaults():
    job = ConversionJob(
        name="j", format_id="subfind_gadget4_hdf5", input=Path("in"), output=Path("out")
    )
    assert job.output_format == "lhalo_hdf5"
    assert job.n_output_files == 1
    assert job.n_trees is None
    assert job.sim_params == {}


def test_bad_job_surfaces_real_cause(tmp_path):
    # A non-HDF5 file fed to the Gadget-4 HDF5 driver: h5py fails to open it.
    junk = tmp_path / "trees.hdf5"
    junk.write_bytes(b"this is not an HDF5 file\n")
    job = ConversionJob(
        name="bad",
        format_id="subfind_gadget4_hdf5",
        input=junk,
        output=tmp_path / "out.0.hdf5",
    )

    result = run_job(job)

    assert isinstance(result, JobResult)
    assert result.status == "failed"
    assert result.error
    # The real cause is reported, not the old generic placeholder.
    assert result.error != _GENERIC
    assert _GENERIC not in result.error
    assert "conversion failed" in result.error
