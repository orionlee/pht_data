import shutil
from pathlib import Path

import pht_subj_ids
import pht_subj_meta


# My EBs, Long Period list
def save_eblp_subject_ids(skip_if_exists=True):
    out_path = Path("data/eblp_subj_ids.csv")
    eblp_coll = "orionlee/pht-eclipsing-binary-long-period"
    eblp_out_path = pht_subj_ids.save_all_subject_ids_of_collection(
        eblp_coll, skip_if_exists=skip_if_exists
    )

    # eb_lp_out_path is in cache dir, copy it to main dir
    # the extra level of redirection is kept in case EB LP is change to comprise of additional tags/ collections
    shutil.copy2(eblp_out_path, out_path)


def load_eblp_subject_ids_from_file():
    return pht_subj_ids.load_subject_ids_from_file("data/eblp_subj_ids.csv")


def save_eblp_subject_meta(skip_if_exists=True):
    subject_ids = load_eblp_subject_ids_from_file()
    print(
        f"EBLP Subject Metadata for {len(subject_ids)} subjects: {subject_ids[0]} ... {subject_ids[-1]}"
    )
    pht_subj_meta.save_subject_meta(
        subject_ids, "data/eblp_subj_meta.csv", skip_if_exists=skip_if_exists
    )


#
# Top level driver
#
if __name__ == "__main__":
    save_eblp_subject_ids(skip_if_exists=True)
    # print(load_eblp_subject_ids_from_file())
    save_eblp_subject_meta(skip_if_exists=True)
