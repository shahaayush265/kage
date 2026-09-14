"""Pure-Python ISO 9660 generator for cloud-init NoCloud configuration (cidata.iso).

Eliminates external tool dependencies like genisoimage, xorriso, or cloud-localds.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Union


def _both_endian_16(val: int) -> bytes:
    return struct.pack("<H", val) + struct.pack(">H", val)


def _both_endian_32(val: int) -> bytes:
    return struct.pack("<I", val) + struct.pack(">I", val)


def _iso_date_time_7(dt: datetime) -> bytes:
    # 7-byte binary date format used in directory records
    return struct.pack(
        "BBBBBBb",
        dt.year - 1900,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second,
        0,  # GMT offset in 15 min intervals
    )


def _iso_date_time_17(dt: datetime) -> bytes:
    # 17-byte ASCII date format used in volume descriptors
    s = dt.strftime("%Y%m%d%H%M%S00")
    return s.encode("ascii") + b"\x00"


class CloudInitIsoBuilder:
    """Creates a standards-compliant ISO 9660 filesystem with volume label CIDATA."""

    SECTOR_SIZE = 2048

    @classmethod
    def create_cidata_iso(
        cls,
        output_path: Union[str, Path],
        user_data: str,
        meta_data: str,
        network_config: str = "version: 2\n",
    ) -> Path:
        """Create a bootable NoCloud cidata.iso file containing user-data and meta-data."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        files: Dict[str, bytes] = {
            "user-data": user_data.encode("utf-8"),
            "meta-data": meta_data.encode("utf-8"),
            "network-config": network_config.encode("utf-8"),
        }

        iso_bytes = cls.build_iso(files, volume_id="cidata")
        out_p.write_bytes(iso_bytes)
        return out_p

    @classmethod
    def build_iso(cls, files: Dict[str, bytes], volume_id: str = "cidata") -> bytes:
        """Build ISO 9660 with Joliet extension for lowercase full filenames."""
        now = datetime.now(timezone.utc)

        # Layout calculation
        # Sectors 0-15: System area (16 sectors * 2048 = 32768 bytes)
        # Sector 16: Primary Volume Descriptor (PVD - ISO 9660)
        # Sector 17: Supplementary Volume Descriptor (SVD - Joliet UCS-2)
        # Sector 18: Volume Descriptor Set Terminator
        # Sector 19: ISO Path Table (L)
        # Sector 20: ISO Path Table (M)
        # Sector 21: Joliet Path Table (L)
        # Sector 22: Joliet Path Table (M)
        # Sector 23: Root Directory (ISO 9660)
        # Sector 24: Root Directory (Joliet)
        # Sector 25+: File Data Extents

        current_sector = 25
        file_extents: Dict[str, dict] = {}

        for fname, content in files.items():
            content_len = len(content)
            sectors_needed = (content_len + cls.SECTOR_SIZE - 1) // cls.SECTOR_SIZE
            if sectors_needed == 0:
                sectors_needed = 1
            file_extents[fname] = {
                "sector": current_sector,
                "length": content_len,
                "data": content,
                "sectors_needed": sectors_needed,
            }
            current_sector += sectors_needed

        total_sectors = current_sector

        # Build ISO root dir (level 1 / ISO 9660)
        iso_root_records = bytearray()
        # Record '.'
        dot_rec = cls._create_dir_record(
            extent_sector=23,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x00",
        )
        # Record '..'
        dotdot_rec = cls._create_dir_record(
            extent_sector=23,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x01",
        )
        iso_root_records.extend(dot_rec)
        iso_root_records.extend(dotdot_rec)

        for fname, info in file_extents.items():
            # Convert to ISO 9660 filename (uppercase, 8.3 with version ;1)
            iso_name = fname.upper().replace("-", "_") + ";1"
            rec = cls._create_dir_record(
                extent_sector=info["sector"],
                data_length=info["length"],
                dt=now,
                is_dir=False,
                ident=iso_name.encode("ascii"),
            )
            iso_root_records.extend(rec)

        iso_root_sector = bytes(iso_root_records).ljust(cls.SECTOR_SIZE, b"\x00")

        # Build Joliet root dir (UCS-2 Big Endian)
        joliet_root_records = bytearray()
        j_dot_rec = cls._create_dir_record(
            extent_sector=24,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x00",
        )
        j_dotdot_rec = cls._create_dir_record(
            extent_sector=24,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x01",
        )
        joliet_root_records.extend(j_dot_rec)
        joliet_root_records.extend(j_dotdot_rec)

        for fname, info in file_extents.items():
            # Joliet UCS-2 BE filename
            joliet_name = (fname + ";1").encode("utf-16-be")
            rec = cls._create_dir_record(
                extent_sector=info["sector"],
                data_length=info["length"],
                dt=now,
                is_dir=False,
                ident=joliet_name,
            )
            joliet_root_records.extend(rec)

        joliet_root_sector = bytes(joliet_root_records).ljust(cls.SECTOR_SIZE, b"\x00")

        # Build Root Directory Record for PVD (34 bytes)
        root_rec_pvd = cls._create_dir_record(
            extent_sector=23,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x00",
        )
        # Build Root Directory Record for Joliet SVD (34 bytes)
        root_rec_svd = cls._create_dir_record(
            extent_sector=24,
            data_length=cls.SECTOR_SIZE,
            dt=now,
            is_dir=True,
            ident=b"\x00",
        )

        # Primary Volume Descriptor (Sector 16)
        pvd = bytearray(cls.SECTOR_SIZE)
        pvd[0] = 1  # Primary Volume Descriptor
        pvd[1:6] = b"CD001"
        pvd[6] = 1  # Version
        pvd[8:40] = b"".ljust(32, b" ")  # System ID
        pvd[40:72] = volume_id.upper().encode("ascii").ljust(32, b" ")  # Volume ID
        pvd[80:88] = _both_endian_32(total_sectors)
        pvd[120:124] = _both_endian_16(1)  # Volume set size
        pvd[124:128] = _both_endian_16(1)  # Volume seq number
        pvd[128:132] = _both_endian_16(cls.SECTOR_SIZE)  # Logical block size
        pvd[132:140] = _both_endian_32(10)  # Path table size (approx)
        pvd[140:144] = struct.pack("<I", 19)  # Type L path table sector
        pvd[148:152] = struct.pack(">I", 20)  # Type M path table sector
        pvd[156 : 156 + len(root_rec_pvd)] = root_rec_pvd
        pvd[190:318] = volume_id.upper().encode("ascii").ljust(128, b" ")
        pvd[813:830] = _iso_date_time_17(now)  # Creation date
        pvd[830:847] = _iso_date_time_17(now)  # Modification date
        pvd[881] = 1  # File structure version

        # Supplementary Volume Descriptor (Sector 17 - Joliet)
        svd = bytearray(cls.SECTOR_SIZE)
        svd[0] = 2  # Supplementary Volume Descriptor
        svd[1:6] = b"CD001"
        svd[6] = 1  # Version
        svd[7] = 0  # Flags
        svd[8:40] = b"".ljust(32, b"\x00")  # System ID
        svd[40:72] = volume_id.encode("utf-16-be").ljust(32, b"\x00")  # Joliet Volume ID
        svd[80:88] = _both_endian_32(total_sectors)
        svd[88:120] = b"\x25\x2f\x45".ljust(32, b"\x00")  # Escape sequence for UCS-2 Level 3
        svd[120:124] = _both_endian_16(1)
        svd[124:128] = _both_endian_16(1)
        svd[128:132] = _both_endian_16(cls.SECTOR_SIZE)
        svd[132:140] = _both_endian_32(10)
        svd[140:144] = struct.pack("<I", 21)
        svd[148:152] = struct.pack(">I", 22)
        svd[156 : 156 + len(root_rec_svd)] = root_rec_svd
        svd[813:830] = _iso_date_time_17(now)
        svd[830:847] = _iso_date_time_17(now)
        svd[881] = 1

        # Volume Descriptor Set Terminator (Sector 18)
        term = bytearray(cls.SECTOR_SIZE)
        term[0] = 255  # Terminator
        term[1:6] = b"CD001"
        term[6] = 1

        # Path Tables (Sectors 19-22)
        path_l = bytearray(cls.SECTOR_SIZE)
        path_l[0] = 1  # Len of dir identifier
        path_l[1] = 0  # Ext attr length
        path_l[2:6] = struct.pack("<I", 23)  # Sector of dir
        path_l[6:8] = struct.pack("<H", 1)  # Parent dir index
        path_l[8] = 0  # Root ident

        path_m = bytearray(cls.SECTOR_SIZE)
        path_m[0] = 1
        path_m[1] = 0
        path_m[2:6] = struct.pack(">I", 23)
        path_m[6:8] = struct.pack(">H", 1)
        path_m[8] = 0

        j_path_l = bytearray(cls.SECTOR_SIZE)
        j_path_l[0] = 1
        j_path_l[1] = 0
        j_path_l[2:6] = struct.pack("<I", 24)
        j_path_l[6:8] = struct.pack("<H", 1)
        j_path_l[8] = 0

        j_path_m = bytearray(cls.SECTOR_SIZE)
        j_path_m[0] = 1
        j_path_m[1] = 0
        j_path_m[2:6] = struct.pack(">I", 24)
        j_path_m[6:8] = struct.pack(">H", 1)
        j_path_m[8] = 0

        # Assemble the full ISO image
        iso_image = bytearray()
        # 16 sectors system area
        iso_image.extend(b"\x00" * (16 * cls.SECTOR_SIZE))
        iso_image.extend(pvd)  # Sector 16
        iso_image.extend(svd)  # Sector 17
        iso_image.extend(term)  # Sector 18
        iso_image.extend(path_l)  # Sector 19
        iso_image.extend(path_m)  # Sector 20
        iso_image.extend(j_path_l)  # Sector 21
        iso_image.extend(j_path_m)  # Sector 22
        iso_image.extend(iso_root_sector)  # Sector 23
        iso_image.extend(joliet_root_sector)  # Sector 24

        # Add file data sectors
        for fname, info in file_extents.items():
            data = info["data"]
            padded = data.ljust(info["sectors_needed"] * cls.SECTOR_SIZE, b"\x00")
            iso_image.extend(padded)

        return bytes(iso_image)

    @staticmethod
    def _create_dir_record(
        extent_sector: int,
        data_length: int,
        dt: datetime,
        is_dir: bool,
        ident: bytes,
    ) -> bytes:
        ident_len = len(ident)
        rec_len = 33 + ident_len
        if rec_len % 2 != 0:
            rec_len += 1  # Must be even length

        rec = bytearray(rec_len)
        rec[0] = rec_len
        rec[1] = 0  # Ext attr length
        rec[2:10] = _both_endian_32(extent_sector)
        rec[10:18] = _both_endian_32(data_length)
        rec[18:25] = _iso_date_time_7(dt)
        rec[25] = 2 if is_dir else 0  # File flags: 2=Directory, 0=File
        rec[26] = 0  # File unit size
        rec[27] = 0  # Interleave gap
        rec[28:32] = _both_endian_16(1)  # Volume seq number
        rec[32] = ident_len
        rec[33 : 33 + ident_len] = ident
        return bytes(rec)
