import pandas as pd


def read_ctc_subjects(
    filepath="data/cache/ctc_subjects.csv", sep=";", transit_time_ndigits=2
):
    # Note: the default field separator is ";" instead of "," , because marked_transits values are comma-separated
    def parse_transit_times(val_str):
        # assumes the input is in the form of [1.2, 3.45, 6.78], with empty ones being []
        if val_str == "[]":
            return []
        return [round(float(t), transit_time_ndigits) for t in val_str[1:-1].split(",")]

    df = pd.read_csv(filepath, sep=sep)
    df.marked_transits = [parse_transit_times(v) for v in df.marked_transits]
    # idx is used internally to ensure the log entries are ordered based on order of entries, not relevant externally
    df.drop(columns=["idx"], inplace=True)
    return df
