from pathlib import Path
import re
import shutil

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
    return Path(f"data/cache/ebp_coll_subj_ids_{collection_name_encoded}.csv")


def save_all_subject_ids_of_collection(collection_name, skip_if_exists=True):
    out_path = _csv_path_of_collection(collection_name)

    if skip_if_exists and out_path.exists() and out_path.stat().st_size > 0:
        print(f"[DEBUG] collection {collection_name} skipped (with existing data)")
        return out_path

    def do_save(subject_ids):
        save_subject_ids_of_page(out_path, subject_ids, None, None)

    get_subject_ids_of_collection(collection_name, result_func=do_save)
    return out_path


# My EBs, Long Period list
def save_eblp_subject_ids(skip_if_exists=True):
    out_path = Path("data/eblp_subj_ids.csv")
    eblp_coll = "orionlee/pht-eclipsing-binary-long-period"
    eblp_out_path = save_all_subject_ids_of_collection(eblp_coll, skip_if_exists=skip_if_exists)

    # eb_lp_out_path is in cache dir, copy it to main dir
    # the extra level of redirection is kept in case EB LP is change to comprise of additional tags/ collections
    shutil.copy2(eblp_out_path, out_path)


def load_eblp_subject_ids_from_file():
    csv_path = Path("data/eblp_subj_ids.csv")
    return np.genfromtxt(csv_path, dtype=int)


#
# Top level driver
#
if __name__ == "__main__":
    save_eblp_subject_ids(skip_if_exists=True)
