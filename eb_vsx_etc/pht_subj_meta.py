import re
from pathlib import Path

from common import to_csv
from zn_common import bulk_process, get_subject_meta_of_id


def _get_pht_subject_meta_of_id(id, json=False):
    res = get_subject_meta_of_id(id)
    if json:
        return res

    subject = res["subjects"][0]

    tic_id = int(subject["metadata"].get("!TIC ID", -1))
    tmag = float(
        subject["metadata"].get("Magnitude", -1)
    )  # might be useful , without extra lookup to MAST

    # extract subject image's uuid
    img_url = subject["locations"][0].get("image/png", "")
    img_id = img_url
    match_res = re.match(
        r"https://panoptes-uploads.zooniverse.org/subject_location/(.+)[.]png", img_url
    )
    if match_res is not None:
        img_id = match_res[1]

    res = dict(
        subject_id=int(subject["id"]),
        tic_id=tic_id,
        img_id=img_id,
        tmag=tmag,
    )
    return res


def get_subject_meta_of_ids(ids, subject_result_func=None):
    kwargs_list = [dict(id=id) for id in ids]
    return bulk_process(
        _get_pht_subject_meta_of_id,
        kwargs_list,
        process_result_func=subject_result_func,
    )


def save_subject_meta(
    subject_ids,
    out_path,
    fieldnames=["subject_id", "tic_id", "img_id", "tmag"],
    skip_if_exists=True,
):
    if not isinstance(out_path, Path):
        out_path = Path(out_path)

    # Note: the logic here will append to an existing csv if the file exists
    # One needs to remove the existing file beforehand if that is not desired.
    def do_save(subject_meta, call_i, call_kwargs):
        to_csv(subject_meta, out_path, mode="a", fieldnames=fieldnames)

    if skip_if_exists and out_path.exists() and out_path.stat().st_size > 0:
        print(
            f"[DEBUG] Save Subject Metadata to {out_path} skipped (with existing data)"
        )
        return

    get_subject_meta_of_ids(subject_ids, subject_result_func=do_save)
