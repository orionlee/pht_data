#
# plot CTC subject, along with TCE vetting results (a simplified transit model, etc.)
#
import astropy.units as u
import lc_lctools
import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
from astropy.modeling.functional_models import Box1D
from astropy.time import Time


def time_to_ph(time, period, t0, pshift=0.0):
    """Convert time to normalized phase of [-0.5, +0.5]."""
    time = np.array(time)
    ph = np.mod((time - t0) / period, 1.0) + pshift
    ph[ph < 0.0] += 1.0
    ph[ph > 0.5] -= 1.0

    return ph


def box_transit_model(
    time_obj, transit_spec1, transit_spec2, time_in_equal_space=True, return_lc=True
):
    def box1d(x, transit_spec):
        x_ph = time_to_ph(x, transit_spec["period"], transit_spec["epoch"])

        return Box1D.evaluate(
            x_ph,
            amplitude=-transit_spec["depth_pct"] / 100,
            x_0=0,
            # width in the unit of normalized phase
            width=transit_spec["duration_hr"] / 24 / transit_spec["period"],
        )

    x = time_obj.value
    if time_in_equal_space:
        # use evenly-space time to avoid distortion due to data gaps
        x = np.linspace(x[0], x[-1], num=len(x), endpoint=True)

    # baseline is 0, so they can be combined easily
    y = box1d(x, transit_spec1)
    if transit_spec2 is not None:
        y2 = box1d(x, transit_spec2)
        y = y + y2
    # shifted to 1 normalized
    y = y + 1

    if not return_lc:
        return x, y
    lc = lk.LightCurve(
        time=Time(x, format=time_obj.format, scale=time_obj.scale),
        flux=y * u.dimensionless_unscaled,
    )
    lc.meta["NORMALIZED"] = True
    return lc


def select_columns(lc, columns=["flux", "flux_err"]):
    lc_subset = type(lc)(time=lc.time.copy())
    lc_subset.meta.update(lc.meta)
    for c in columns:
        lc_subset[c] = lc[c]
    return lc_subset


def plot_subject_with_vetting_result(
    input_row,
    vetting_result,
    vetting_diagnostics,
    plot_model=True,
    lc_src="mast",
    lctools_zip_dir=".",
    ax=None,
    figsize=(10, 3),
):
    r = input_row  # shorthand

    if lc_src == "mast":
        lc = lk.search_lightcurve(
            f"TIC{r.tic}",
            sector=r.sector,
            mission="TESS",
            author="SPOC",
            exptime="short",
        )[0].download()
        lc = lc.normalize()
    elif lc_src == "lctools":
        lc = lc_lctools.get_lc(r.tic, r.sector, lctools_zip_dir=lctools_zip_dir)
    else:
        raise ValueError(f"Unsupported LC source: {lc_src}")

    with plt.style.context(lk.MPLSTYLE):
        if ax is None:
            ax = plt.figure(figsize=figsize).gca()

        if lc_src == "mast":
            # plot the 2-min cadence data and a binned version
            lc_b = select_columns(lc).bin(time_bin_size=10 * u.min)
            lc.scatter(ax=ax, c="orange", alpha=0.5, label=f"{lc.label}, S.{lc.sector}")
            lc_b.scatter(ax=ax, c="black", alpha=0.5, label=None)
        elif lc_src == "lctools":
            # lctools data is already binned
            lc.scatter(ax=ax, c="black", alpha=0.5, label=f"{lc.label}, S.{lc.sector}")

        if plot_model:
            lc_model = box_transit_model(
                lc.time,
                vetting_diagnostics.transit_spec1,
                vetting_diagnostics.transit_spec2,
            )
            lc_model.plot(ax=ax, c="red", alpha=0.7, lw=2, ls="-")

        marked_matched = [t[0] for t in vetting_result["matched"]]
        ax.vlines(
            marked_matched,
            ymin=0,
            ymax=0.15,
            transform=ax.get_xaxis_transform(),
            lw=2.5,
            ls="--",
            colors="gray",
        )

        # de-emphasize marked transits that match TCE prediction
        marked_not_matched = [t[0] for t in vetting_result["not_matched"]]
        ax.vlines(
            marked_not_matched,
            ymin=0,
            ymax=0.15,
            transform=ax.get_xaxis_transform(),
            lw=4,
            ls="--",
            colors="brown",
        )

        ax.legend(loc="upper right")
        if getattr(r, "subject") is not None:
            ax.set_title(f"{vetting_result['classification']} - {r.subject}")
        else:
            ax.set_title(
                f"{vetting_result['classification']} - TIC {r.tic} , S.{r.sector}"
            )

    return ax
