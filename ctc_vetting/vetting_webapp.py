import base64
import logging
import re
from io import BytesIO
from types import SimpleNamespace

import matplotlib
import tess_dv_fast
import vetting_by_tce
import vetting_by_tce_plot
from flask import Flask, request

# to avoid "UserWarning: Starting a Matplotlib GUI outside of the main thread will likely fail." in flask
matplotlib.use("Agg")

app = Flask(__name__)
log = logging.getLogger(__name__)

# Configuration for `vet()`
duration_fudge_factor = 1.0
lc_src = "mast"  # "mast", "lctools"
lctools_zip_dir = "."

# import lightkurve as lk  # config lightkurve cache dir for lc_src == "mast"
# lk.conf.cache_dir

# Test:
# http://127.0.0.1:5000/vet?tic=1400824435&sector=78&marked_transits=[3451.196327263678,%203440.4646207512405,%203438.151243255724,%203435.9750799622693]


def _render_home():
    html = """\
<!DOCTYPE html>
<html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="icon" href="data:,">
        <title>PHT CTC Subject Vetting</title>
    </head>
    <body>
        <h1>PHT CTC Subject Vetting</h1>
    </body>
</html>
"""
    return html


def _parse_transit_times(val_str, transit_time_ndigits=2):
    # assumes the input is in the form of [1.2, 3.45, 6.78], with empty ones being []
    if val_str == "[]":
        return []
    if val_str == "0":  # in some CTC subjects,  marked_transits is "0" for unknown reason
        return []
    return [round(float(t), transit_time_ndigits) for t in val_str[1:-1].split(",")]


def _fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(
        buf, format="png", bbox_inches="tight"
    )  # bbox_inches="tight":  avoid the bottom from being cropped

    # Encode the image data in Base64
    return base64.b64encode(buf.getbuffer()).decode("ascii")


def _res_to_html(res, plot_html):
    def abbrev_tce(tce_str):
        return re.sub(r"^TIC.+TCE", "tce", tce_str)

    def r_matched(matched, label):
        html = f"<i>{label}</i><br>"
        if matched is not None and len(matched) > 0:
            trs = ""
            for m in matched:
                trs += f"<tr><td>{m[0]}</td><td>{abbrev_tce(m[1][0])}</td><td>{m[1][1]}</td><td>{m[1][2]}</td></tr>"
            html += f"""
<table>
    <thead><th>time</th><th>TCE</th><th>diff (hr)</th><th>diff (fraction)</th></tead>
    <tbody>{trs}</tbody>
</table>
"""
        else:
            html += "<p>None</p>"

        return html

    abbrev_k_map = {
        "fraction_matched": "fraction",
        "num_matched": "#matched",
        "num_marked_transits": "#marked_transits",
    }

    ths, tds = "", ""
    for k, v in res.items():
        if k in ["matched", "not_matched"]:
            continue
        ths += f"<th>{abbrev_k_map.get(k, k)}</th>"
        tds += f"<td>{v}</td>"
    return f"""
<div class="ctr-2col matched-result">
    <div class="col">
        <table id="vetting_result_summary">
            <thead><tr>{ths}</tr></thead>
            <tbody><tr>{tds}</tr></tbody>
        </table>
        <div style="height: 1rem;"></div>
        <div class="ctr-2col matched-result">
            <div class="col">{r_matched(res.get("not_matched"), "not matched:")}</div>
            <div class="col">{r_matched(res.get("matched"), "matched:")}</div>
        </div>
    </div>
    <div class="col">
        {plot_html}
    </div>
</div>
"""


def _render_vet_result(r, res, diagnostics):
    main_content = ""

    # LC plot
    if diagnostics.df_tces is not None:
        ax = vetting_by_tce_plot.plot_subject_with_vetting_result(
            r, res, diagnostics, lc_src=lc_src, lctools_zip_dir=lctools_zip_dir
        )
        plot_data = _fig_to_base64(ax.get_figure())
        plot_html = (
            f"""<img src="data:image/png;base64,{plot_data}" alt="Lightcurve Plot">"""
        )
    else:
        plot_html = ""

    # vetting result and the LC plot
    main_content += _res_to_html(res, plot_html)

    main_content += """<div style="height: 1rem;"></div>"""

    main_content += "<h4>TCEe used in matching</h4>"
    if diagnostics.df_tces is not None:
        main_content += tess_dv_fast.display_tce_infos(  # pyright: ignore[reportOperatorIssue]
            diagnostics.df_tces,
            return_as="html",
        )
    else:
        main_content += "<p>None</p>"

    main_content += "<hr>"

    df_all_tces = diagnostics.df_all_tces
    df_sector_tces = (
        df_all_tces[df_all_tces.sectors == f"s00{r.sector}-s00{r.sector}"]
        if df_all_tces is not None
        else None
    )

    main_content += f"<h4>Sector {r.sector} TCEs</h4>"
    main_content += tess_dv_fast.display_tce_infos(  # pyright: ignore[reportOperatorIssue]
        df_sector_tces,
        return_as="html",
        no_tce_html="None",
    )

    main_content += "<hr>"

    all_tces_html = tess_dv_fast.display_tce_infos(  # pyright: ignore[reportOperatorIssue]
        df_all_tces,
        return_as="html",
        no_tce_html="None",
    )

    open_attr = (
        "open"
        if df_all_tces is None or len(df_all_tces) < 1 or len(df_sector_tces) < 1
        else ""
    )

    main_content += f"""\
<details {open_attr}>
    <summary><b>All TCEs</b></summary>
    {all_tces_html}
</details>"""

    return main_content


@app.route("/vet")
def vet():
    """Main search endpoint for TESS TCEs."""
    tic = request.args.get("tic", None)
    # case return search form
    if tic is None:
        return _render_home()
    tic = int(tic)

    sector = request.args.get("sector", None)  # required
    sector = int(sector)

    marked_transits = request.args.get("marked_transits", "[]")
    marked_transits = _parse_transit_times(marked_transits)

    subject = request.args.get("subject", None)  # optional, only used in plot label
    if subject is not None:
        subject = int(subject)

    r = SimpleNamespace(
        tic=tic, sector=sector, marked_transits=marked_transits, subject=subject
    )

    res, diagnostics = vetting_by_tce.vet(
        r, duration_fudge_factor=duration_fudge_factor, also_return_diagnostics=True
    )

    main_content = _render_vet_result(r, res, diagnostics)

    css = """
body {
    margin-left: 16px;
}

td { /* increasing horizontal spacing, primarily for TCE tables */
    padding: 2px 0.5ch;
}

tbody tr:nth-child(even) { /* primarily for TCE tables */
    background-color: #f5f5f5;
}

table#vetting_result_summary {
    background-color: #eee;
}
table#vetting_result_summary thead {
    border-bottom: 1px solid black;
    padding-bottom: 4px;
}
table#vetting_result_summary th:nth-child(even), table#vetting_result_summary td:nth-child(even) {
    background-color: #e7e7e7;
}
table#vetting_result_summary th, table#vetting_result_summary td {
    padding: 2px 1ch;
}

.ctr-2col {
    display: flex;
    /* Adds space between columns */
    gap: 6ch;
}

.column {
    padding: 1rem;
    background-color: #f0f077;
}

.matched-result td {
    padding: 2px 1ch;
}

"""

    if subject is not None:
        target_label = f"Subject {subject} / TIC {tic}, S. {sector}"
    else:
        target_label = f"TIC {tic}, S. {sector}"

    return f"""\
<!DOCTYPE html>
<html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="icon" href="data:,">
        <style>{css}</style>
        <title>{res["classification"]} , {res.get("ibd", "N/A")} | {target_label} | PHT CTC Subject Vetting</title>
    </head>
    <body>
        <h1>Vetting Result for {target_label}</h1>
        <div style="height: 1rem;"></div>
        {main_content}
    </body>
</html>
"""
