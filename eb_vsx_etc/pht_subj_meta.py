from pathlib import Path
import re

from common import to_csv
from zn_common import get_subject_meta_of_id, bulk_process
from pht_subj_ids import load_eblp_subject_ids_from_file


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


def save_eblp_subject_meta(skip_if_exists=True):
    def do_save(subject_meta, call_i, call_kwargs):
        out_path = Path("data/eblp_subj_meta.csv")
        fieldnames = ["subject_id", "tic_id", "img_id", "tmag"]
        to_csv(subject_meta, out_path, mode="a", fieldnames=fieldnames)

    ids = load_eblp_subject_ids_from_file()
    print(f"EBLP Meta for {len(ids)} subjects: {ids[0]} ... {ids[-1]}")
    get_subject_meta_of_ids(ids, subject_result_func=do_save)


#
# Top level driver
#
if __name__ == "__main__":
    save_eblp_subject_meta()
