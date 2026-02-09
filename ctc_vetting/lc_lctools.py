import zipfile

from astropy.table import Table
from astropy.time import Time
import lightkurve as lk


def get_lc(tic, sector, lctools_zip_dir):
    def lctools_id_to_tic(lctools_id):
        if (
            lctools_id > 9999999999
        ):  # do conversion if it has > 10 digits  (lctools converted the tic if it has <= 6 digits)
            return lctools_id - 10000000000
        else:
            return lctools_id

    def tic_to_lctools_id(tic):
        # TIC with 6 digits or less gets mapped
        # e.g, 2502532 => 1002502532
        if tic < 1000000:
            return tic + 10000000000
        else:
            return tic

    lctools_zip_path = f"{lctools_zip_dir}/Lightcurves_TESS_S{sector:03}.zip"

    with zipfile.ZipFile(lctools_zip_path) as z:
        lctools_id = tic_to_lctools_id(tic)
        lc_filepath = [
            n for n in z.namelist() if str(lctools_id) in n and n.endswith(".txt")
        ]
        if len(lc_filepath) < 1:
            return None
        lc_filepath = lc_filepath[0]

        with z.open(lc_filepath) as lc_file:
            tab = Table.read(lc_file, format="ascii.csv")
            lc = lk.LightCurve(
                time=Time(tab["#Time (BTJD)"], format="btjd"),
                flux=tab["Normalized PDCSAP_FLUX"],
            )

            m = lc.meta
            m["SECTOR"] = sector
            m["TICID"] = tic
            m["TARGETID"] = tic
            m["LABEL"] = f"TIC {tic}"
            m["OBJECT"] = f"TIC {tic}"
            m["NORMALIZED"] = True
            m["CREATOR"] = "lctools"
            m["FLUX_ORIGIN"] = "pdcsap_flux"

            return lc
