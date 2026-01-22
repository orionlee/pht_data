import re
from pathlib import Path

import numpy as np
from zn_common import get_subject_ids_of_collection

# PHT Zooniverse Project ID used in API calls
PHT_ZN_ID = 7929


def save_subject_ids_of_page(out_path, subject_ids, call_i=None, call_kwargs=None):
    with open(out_path, "a") as f:
        np.savetxt(f, subject_ids, fmt="%s")

    return out_path


def _csv_path_of_collection(collection_name):
    collection_name_encoded = re.sub(r"[/\:]", "_", collection_name)
    return Path(f"data/cache/pht_coll_subj_ids_{collection_name_encoded}.csv")


def save_all_subject_ids_of_collection(
    collection_name, out_path=None, skip_if_exists=True
):
    if out_path is None:
        # default: saved to data cache dir
        out_path = _csv_path_of_collection(collection_name)

    if skip_if_exists and out_path.exists() and out_path.stat().st_size > 0:
        print(f"[DEBUG] collection {collection_name} skipped (with existing data)")
        return out_path

    def do_save(subject_ids):
        save_subject_ids_of_page(out_path, subject_ids, None, None)

    get_subject_ids_of_collection(collection_name, result_func=do_save)
    return out_path


def load_subject_ids_from_file(csv_path):
    return np.genfromtxt(Path(csv_path), dtype=int)
