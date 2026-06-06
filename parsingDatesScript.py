import os
import re
import pandas as pd
from datetime import datetime

'''
This script's purpose is to assign commit timestamps to each assignment attempt per student. 

Input: Two folders one with dates (student commit times) and the other is grading_dates (when Dr. Keen pulled all student commits).
    The subdirectory structure is as follows: dates -> (name of quarter) -> (assignment num) -> (student commit dates)
Output: This script outputs a csv file per quarter of data. 
'''

DATES_ROOT = "dates"
GRADING_ROOT = "grading_dates"
SCORES_ROOT = "scores"

COMMIT_RE = re.compile(r"Date:\s*(.+)")
GRADING_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(\d+)/")

def parse_commit_dates(path):
    commits = []
    with open(path) as f:
        for line in f:
            m = COMMIT_RE.search(line)
            if m:
                dt = datetime.strptime(
                    m.group(1),
                    "%a %b %d %H:%M:%S %Y %z"
                )

                # convert everything to -0800 (PST)
                dt = dt.astimezone(datetime.strptime("-0800", "%z").tzinfo)

                commits.append(dt)
    return sorted(commits)


def latest_before(commits, cutoff):
    valid = [c for c in commits if c.replace(tzinfo=None) <= cutoff]
    return max(valid) if valid else None


def parse_grading_dates(path):
    pulls = {}
    with open(path) as f:
        for line in f:
            m = GRADING_RE.search(line)
            if m:
                d, t, v = m.groups()
                pulls[int(v)] = datetime.strptime(
                    f"{d} {t}", "%Y-%m-%d %H:%M"
                )
    return pulls

for quarter in sorted(os.listdir(DATES_ROOT)):
    dates_q = os.path.join(DATES_ROOT, quarter)
    grading_q = os.path.join(GRADING_ROOT, quarter)

    if not os.path.isdir(dates_q):
        continue

    print(f"\nProcessing {quarter}")

    rows = {}
    columns = ["Student"]

    for hw in sorted(os.listdir(dates_q)):
        if not hw.startswith("hw"):
            continue

        assign = hw.replace("hw", "")
        dates_hw = os.path.join(dates_q, hw)
        grading_hw = os.path.join(grading_q, hw)

        grading_file = os.path.join(grading_hw, "dates")
        if not os.path.isfile(grading_file):
            print(f"Missing grading file: {grading_file}")
            continue

        grading_pulls = parse_grading_dates(grading_file)
        if not grading_pulls:
            print(f"No grading pulls in {grading_file}")
            continue

        for v in sorted(grading_pulls):
            col = f"Assign {assign} v.{v}"
            if col not in columns:
                columns.append(col)

        for student_file in os.listdir(dates_hw):
            student_path = os.path.join(dates_hw, student_file)
            if not os.path.isfile(student_path):
                continue

            student = student_file.replace(".dates", "")
            rows.setdefault(student, {"Student": student})

            commits = parse_commit_dates(student_path)

            for v, pull_time in grading_pulls.items():
                col = f"Assign {assign} v.{v}"
                selected = latest_before(commits, pull_time)

                rows[student][col] = (
                    selected.strftime("%a %b %d %H:%M:%S %Y %z")
                    if selected else "none"
                )

    if len(columns) == 1:
        print(f"No assignments found for {quarter}")
        continue

    df = pd.DataFrame.from_dict(rows, orient="index")
    df = df.reindex(columns=columns)
    df.sort_values("Student", inplace=True)

    scores_file = os.path.join(
        SCORES_ROOT,
        quarter,
        f"{quarter}_hw.xlsx"
    )

    if os.path.isfile(scores_file):
        print(f"Applying scores from {scores_file}")
        df_scores = pd.read_excel(scores_file)

        df.set_index("Student", inplace=True)
        df_scores.set_index("Student", inplace=True)

        df_scores = df_scores.reindex(df.index)

        common_cols = set(df.columns) & set(df_scores.columns)

        for col in common_cols:
            mask = df_scores[col].astype(str).str.lower() == "none"
            df.loc[mask, col] = "none"

        df.reset_index(inplace=True)
    else:
        print(f"No scores file found for {quarter}")

    df = df.fillna("none")
    df.replace("", "none", inplace=True)

    out_file = f"{quarter}_commit_dates.csv"
    df.to_csv(out_file, index=False)
    print(f"Created {out_file}")