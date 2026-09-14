"""Tests for pure-Python cloud-init ISO 9660 generation."""

from kage.hypervisor.cloud_init import CloudInitIsoBuilder


def test_build_cidata_iso(tmp_path):
    iso_file = tmp_path / "cidata.iso"
    user_data = "#cloud-config\nhostname: kage-test\n"
    meta_data = "instance-id: kage-test-1\nlocal-hostname: kage-test\n"

    CloudInitIsoBuilder.create_cidata_iso(
        output_path=iso_file,
        user_data=user_data,
        meta_data=meta_data,
    )

    assert iso_file.exists()
    assert iso_file.stat().st_size > 32768  # At least > 16 sectors

    # Read ISO bytes and verify signatures
    data = iso_file.read_bytes()
    # PVD at sector 16 (offset 32768)
    pvd_offset = 16 * 2048
    assert data[pvd_offset] == 1  # Primary descriptor
    assert data[pvd_offset + 1 : pvd_offset + 6] == b"CD001"
    assert b"CIDATA" in data[pvd_offset + 40 : pvd_offset + 72]

    # SVD at sector 17 (offset 34816)
    svd_offset = 17 * 2048
    assert data[svd_offset] == 2  # Supplementary descriptor
    assert data[svd_offset + 1 : svd_offset + 6] == b"CD001"
    # Terminator at sector 18 (offset 36864)
    term_offset = 18 * 2048
    assert data[term_offset] == 255
