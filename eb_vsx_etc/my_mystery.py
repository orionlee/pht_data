from pathlib import Path

import pht_subj_comments
import pht_subj_ids


# My EBs, Long Period list
def save_mystery_subject_ids(skip_if_exists=True):
    out_path = Path("data/mystery_subj_ids.csv")
    mystery_coll = "orionlee/pht-mystery"
    _ = pht_subj_ids.save_all_subject_ids_of_collection(
        mystery_coll, out_path=out_path, skip_if_exists=skip_if_exists
    )


def load_mystery_subject_ids_from_file():
    return pht_subj_ids.load_subject_ids_from_file("data/mystery_subj_ids.csv")


def save_mystery_subject_comments(subject_ids=None):
    if subject_ids is None:
        subject_ids = load_mystery_subject_ids_from_file()
    print(
        f"Saving comments for {len(subject_ids)} subjects: {subject_ids[0]} ... {subject_ids[-1]}"
    )
    pht_subj_comments.save_subject_comments(subject_ids)


def search_mystery_subject_comments(search_text, subject_ids=None):
    if subject_ids is None:
        subject_ids = load_mystery_subject_ids_from_file()
    return pht_subj_comments.search_subject_comments(subject_ids, search_text)


#
# Top level driver
#
if __name__ == "__main__":
    save_mystery_subject_ids(skip_if_exists=True)
    # print(load_mystery_subject_ids_from_file())
    save_mystery_subject_comments()
