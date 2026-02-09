from types import SimpleNamespace

import pandas as pd
import tess_dv_fast


def is_time_compatible(
    marked_time, transit_spec, duration_fudge_factor, also_return_details=False
):
    ts = transit_spec  # shorthand
    epoch, period, duration_hr, label = (
        ts["epoch"],
        ts["period"],
        ts["duration_hr"],
        ts["label"],
    )
    # diff (in days) to the nearest expected transit from transit_spec
    diff = (marked_time - epoch) % period
    if diff > period / 2:  # normalize to [-period/2, period/2]
        diff = diff - period
    compatible = abs(diff) <= duration_hr / 2 / 24 * duration_fudge_factor

    if not also_return_details:
        return compatible
    # return compatible?, (label, diff_in_hr, diff_in_fraction_of_duration)
    # round the details for ease of subsequent processing
    return compatible, (label, round(diff * 24, 1), round(diff * 24 / duration_hr, 1))


def get_transit_specs(
    df,
    # the period range (in ratio) that are considered to be the same
    compat_period_ratios=(0.99, 1.01),
    # the minimum MES threshold for TCE1 weak secondary to be used.
    # Note: generally TCE pipeline considers weak secondary to be significant
    #       only if the MES > 7.1 .
    #       Here we use a smaller default to be more lenient for the purpose of matching users' marked transits.
    #       At times users pick up very shallow dips that are not deemed significant enough by MES metrics.
    weak_secondary_min_mes_threshold=3,
):
    # primary eclipse: TCE1 of the TCE with the longest baseline
    r1 = df.iloc[0]
    transit_spec1 = dict(
        epoch=r1.tce_time0bt,
        period=r1.tce_period,
        duration_hr=r1.tce_duration,
        label=r1.exomast_id,
        depth_pct=r1.tce_depth_pct,
    )

    # Looking for potential secondary eclipses, scenarios:
    # 1. No secondary eclipses, or TCE1 covers both primary and secondary eclipses
    # 2. identified in TCE2, with comparable period
    # 3. identified in TCE1's secondary eclipses (used in TCE weak secondary test)

    df_tce2 = df[df.exomast_id == r1.exomast_id.replace("TCE1", "TCE2")]
    r2 = df_tce2.iloc[0] if len(df_tce2) > 0 else None
    if (
        r2 is not None
        and compat_period_ratios[0]
        <= r2.tce_period / r1.tce_period
        <= compat_period_ratios[1]
    ):
        # case 2
        transit_spec2 = dict(
            epoch=r2.tce_time0bt,
            period=r2.tce_period,
            duration_hr=r2.tce_duration,
            label=r2.exomast_id,
            depth_pct=r2.tce_depth_pct,
        )
        return transit_spec1, transit_spec2, df[0:2]  # TCE1 and TCE2 are used
    # possibly case 1 or 3
    ws_phase_d, ws_mes_max = (
        r1.tce_ws_maxmesd,
        r1.tce_ws_maxmes,
    )  # only available in full db
    if ws_mes_max < weak_secondary_min_mes_threshold:
        # the secondary eclipse signals are too weak to be considered.
        # assumed to be case 1
        return transit_spec1, None, df[0:1]  # only TCE1 is  used
    # case 3
    transit_spec2 = dict(
        epoch=r1.tce_time0bt + ws_phase_d,  # applied the phase offset (in days)
        period=r1.tce_period,
        duration_hr=r1.tce_duration,  # no such data. so use the one from primary one as a proxy
        label=f"{r1.exomast_id}_sec",
        depth_pct=r1.wst_depth / 10000,  # covert from ppm to percent
    )
    return transit_spec1, transit_spec2, df[0:1]  # only TCE1 is  used


def _has_significant_secondary(
    df,
    # If secondary dips are from TCE1 weak secondary,
    # the minimum MES threshold for them to be considered significant, and assumed to be EB
    # by the logic here.
    # Here the standard 7.1 MES is used (as opposed to the more lenient threshold in get_transit_specs(),
    # so that if a target is flagged as EB due to TCE1 weak secondary dips,
    # we can be reasonably sure that the the secondary dips are real (and thus likely to be EB).
    weak_secondary_min_mes_threshold=7.1,
):
    # Note: the df supplied is assumed to contain only relevant TCEs, i.e.,
    # after the filtering done by get_transit_specs()

    # Either 1) secondary is captured in TCE2
    if len(df) > 1:
        return True

    # Or 2) TCE1 weak secondary is significant enough
    if df.iloc[0].tce_ws_maxmes > weak_secondary_min_mes_threshold:
        return True

    # Limitation: we can't tell the case TCE1 has significant odd-even depth difference

    return False


def _get_tce_type(
    df,
    centroid_offset_sig_max_threshold=3,
    planet_radius_in_jup_max_threshold=2.5,
):
    # Some discussions on the MES > 7.1 for TCE weak secondary tests:
    # - https://iopscience.iop.org/article/10.3847/1538-3881/ae03a4, section 6.7
    # - https://iopscience.iop.org/article/10.1088/1538-3873/aab694, section 3.1

    # Note: the df supplied is assumed to contain only relevant TCEs, i.e.,
    # after the filtering done by get_transit_specs()
    r = df.iloc[0]

    is_tic_offset_sig = r.tce_ditco_msky_sig > centroid_offset_sig_max_threshold
    is_planet_size = r.tce_prad_jup < planet_radius_in_jup_max_threshold

    # indicate TCE result uncertain
    uncertain_flag = (
        # planet size is base on assuming stellar radius is 1 solar,
        r.tce_sradius_prov_is_solar
        or (
            # no TicOffset available (that's how it's represented in the source TCE CSVs)
            str(r.tce_ditco_msky) == "0.0" and str(r.tce_ditco_msky_sig) == "-0.0"
        )
    )

    if is_tic_offset_sig:
        type = "BEB"  # OPEN: it could be nearby planet candidate, but we don't care about it for now
        # OPEN: limitation, even if the centroid offset is small, it could still be an BEB
        # if the centroid is actually closer to a close by nearby star, but we can't tell with the info available here.
    elif is_planet_size:
        # dips shallow enough to be transits.
        # heuristics: if secondary dips are detected, assume it's EB, otherwise it's PC
        if _has_significant_secondary(df):
            type = "EB"
        else:
            # case no significant secondary detected, assumed to be PC
            type = "PC"
    else:
        # larger than planet size
        type = "EB"
    suffix = "?" if uncertain_flag else ""
    type = f"{type}{suffix}"
    if type == "BEB?":
        # special case for BEB, we don't really care if target stellar radius is unreliable.
        type = "BEB"
    return type


def get_classification(all_matched, tce_type):
    # OPEN: handle IBD "Interesting (but discard)", but I can only handle a subset of cases
    # 1. Can identify EB/BEBS with eclipses shallow enough to be IBD
    # 2. but cannot reliably tell if there are odd/even depth difference.
    #    a. can reliably tell if secondary eclipses are from TCE2, but fail if secondary eclipses are from TCE1
    if all_matched == "False":
        return "Uncertain-NoMatchedTime"  # TCE vet is silent about the target
    if all_matched == "True" or all_matched == "Partial":
        if all_matched == "Partial":
            return f"{tce_type}-Partial"
        else:
            return tce_type
    raise ValueError(f"Unrecognized value for `all_matched`: {all_matched}")


def vet(
    tic_w_marked_transits,
    duration_fudge_factor=1.0,
    ibd_depth_pct_max_threshold=20,
    also_return_diagnostics=False,
):
    tic, marked_transits = (
        tic_w_marked_transits.tic,
        tic_w_marked_transits.marked_transits,
    )

    df = tess_dv_fast.get_tce_infos_of_tic(tic)
    if len(marked_transits) < 1:
        # case no marked transits (e.g., from algorithm pipeline)
        res = dict(classification="", all_matched="")
        if also_return_diagnostics:
            return res, SimpleNamespace(
                df_tces=None, transit_spec1=None, transit_spec2=None, df_all_tces=None
            )
        else:
            return res
    if len(df) < 1:  # case no TCE
        res = dict(classification="Uncertain-NoTCE", all_matched="NA")
        if also_return_diagnostics:
            return res, SimpleNamespace(
                df_tces=None, transit_spec1=None, transit_spec2=None, df_all_tces=None
            )
        else:
            return res

    # df_transit_specs: a subset of the df with the relevant TCEs
    transit_spec1, transit_spec2, df_transit_specs = get_transit_specs(df)
    # MUST pass df_transit_specs instead of df,
    # as get_tce_type() assumes the dataframe supplied only contains TCEs
    # relevant to the identified primary / secondary dips, and nothing more.
    tce_type = _get_tce_type(df_transit_specs)

    matched, not_matched = [], []
    for marked_time in marked_transits:
        compatible1, details1 = is_time_compatible(
            marked_time, transit_spec1, duration_fudge_factor, also_return_details=True
        )
        if compatible1:
            matched.append((marked_time, details1))
            continue
        compatible2, details2 = False, None
        if transit_spec2 is not None:
            compatible2, details2 = is_time_compatible(
                marked_time,
                transit_spec2,
                duration_fudge_factor,
                also_return_details=True,
            )
            if compatible2:
                matched.append((marked_time, details2))
                continue
        # not compatible with primary or secondary, return the closest one
        if details2 is None or abs(details1[1]) < abs(details2[1]):
            not_matched.append((marked_time, details1))
        else:
            not_matched.append((marked_time, details2))

    # all_matched + tce_type forms overall assessment
    if len(matched) == len(marked_transits):
        all_matched = "True"
    elif len(matched) > 0:
        all_matched = "Partial"
    else:
        all_matched = "False"
    # also all_matched is in the form of Uncertain-* , for cases there is no TIC, short-circuited in the above codes

    classification = get_classification(all_matched, tce_type)

    # ibd: interesting (but discard)
    if classification.startswith("PC"):
        ibd = "No"
    elif classification.startswith("EB") or classification.startswith("BEB"):
        if transit_spec1["depth_pct"] < ibd_depth_pct_max_threshold:
            if _has_significant_secondary(df_transit_specs):
                ibd = "No"
            else:
                # for shallow enough dips but no significant secondary detected.
                # Limitation: we can't tell the case TCE1 has significant odd-even depth difference
                # , and will incorrectly marked it as Yes
                ibd = "Maybe"
        else:
            # dips too deep
            ibd = "No"
    else:
        # case classification is uncertain
        ibd = ""

    res = dict(
        classification=classification,
        ibd=ibd,
        tce_type=tce_type,
        all_matched=all_matched,
        fraction_matched=round(len(matched) / len(marked_transits), 2),
        num_matched=len(matched),
        num_marked_transits=len(marked_transits),
        not_matched=not_matched,
        matched=matched,
    )
    if not also_return_diagnostics:
        return res
    diagnostics = SimpleNamespace(
        df_tces=df_transit_specs,
        transit_spec1=transit_spec1,
        transit_spec2=transit_spec2,
        df_all_tces=df,
    )
    return res, diagnostics


def vet_all(df, id_colname, **kwargs):
    res_list = []
    for _, r in df.iterrows():
        res = {id_colname: r[id_colname]}
        _res, _diagnostics = vet(r, also_return_diagnostics=True, **kwargs)
        res.update(_res)
        # for diagnostics purposes
        res["transit_spec1"] = _diagnostics.transit_spec1
        res["transit_spec2"] = _diagnostics.transit_spec2
        res_list.append(res)

    df = pd.DataFrame(res_list)
    for colname in ["num_matched", "num_marked_transits"]:
        df[colname] = df[colname].astype("Int64")
    return df
