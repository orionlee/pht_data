import json
from pathlib import Path

from ratelimit import limits, sleep_and_retry
from zn_common import bulk_process, fetch_json, json_np_dump

# throttle HTTP calls to Zooniverse
NUM_CALLS = 5
TEN_SECONDS = 10


@sleep_and_retry
@limits(calls=NUM_CALLS, period=TEN_SECONDS)
def _get_subject_comment_of_id_n_page(id, page):
    url = (
        f"https://talk.zooniverse.org/comments?http_cache=true&section=project-7929&focus_type=Subject"
        f"&sort=-created_at&focus_id={id}&page={page}"
    )
    return fetch_json(url)


def _get_subject_comments_of_id(id):
    # fetch all pages and combine them to 1 JSON object

    res = _get_subject_comment_of_id_n_page(id, 1)
    res["meta"]["subject_id"] = id  # add it to the result for ease of identification
    num_pages = res["meta"]["comments"]["page_count"]
    for page in range(2, num_pages + 1):
        page_res = _get_subject_comment_of_id_n_page(id, page)
        res["comments"] = res["comments"] + page_res["comments"]

    return res


def get_subject_comments_of_ids(ids, subject_result_func=None):
    kwargs_list = [dict(id=id) for id in ids]
    return bulk_process(
        _get_subject_comments_of_id,
        kwargs_list,
        process_result_func=subject_result_func,
    )


def _save_comments_of_subject(subject_comments, call_i, call_kwargs):
    id = subject_comments["meta"]["subject_id"]
    out_path = Path(
        f"data/cache/comments/c{id}.json"
    )  # the c prefix hints it is a comment

    out_path.parent.mkdir(parents=True, exist_ok=True)  # create basedir if not exists
    with open(out_path, "w") as f:
        json_np_dump(subject_comments, f)


def save_subject_comments(subject_ids):
    get_subject_comments_of_ids(
        subject_ids, subject_result_func=_save_comments_of_subject
    )


def load_subject_comments_of_id_from_file(subject_id):
    with open(f"data/cache/comments/c{subject_id}.json", "r") as f:
        return json.load(f)


def _to_comment_url(c):
    return f"/{c['project_slug']}/talk/{c['board_id']}/{c['discussion_id']}?comment={c['id']}"


def search_comments(comments_obj, search_text):
    """Search a comments object, usually all comments of a subject."""
    search_text = search_text.lower()
    res = []
    for c in comments_obj["comments"]:
        if search_text in c["body"].lower():
            res.append(_to_comment_url(c))
    return res


def search_subject_comments(subject_ids, search_text):
    """Search comments of a list of subjects."""
    res = []
    for id in subject_ids:
        c = load_subject_comments_of_id_from_file(id)
        search_result = search_comments(c, search_text)
        if len(search_result) > 0:
            res.append((id, search_result))
    return res
