import json
import requests
from textwrap import dedent

import pandas as pd

from .config import MODEL, OLLAMA_URL
from .regex_utils import extract_coop_entities_regex

# Path to the CSV exported from DuckDB
CSV_PATH = "/home/aw/cooperation/note_cooperation.csv"


def load_notes():
    """
    Load cooperation notes from CSV and return a DataFrame with a clean
    note_cooperation column.
    """
    df = pd.read_csv(CSV_PATH)
    if "note_cooperation" not in df.columns:
        raise ValueError(
            f"Expected column 'note_cooperation' in {CSV_PATH}, "
            f"got: {list(df.columns)}"
        )

    df = df.dropna(subset=["note_cooperation"])
    df["note_cooperation"] = df["note_cooperation"].astype(str).str.strip()
    return df


def normalize_batch_with_llm(candidates):
    """
    Send a small batch of organization name strings to the LLM.

    For each input string, the LLM returns:
      { "raw": "...", "normalized": "...", "type": "...", "country": "..." }

    The LLM must NOT group/merge inputs; it treats each line independently.
    """
    if not candidates:
        return []

    instruction = dedent(
        """
        You receive a list of organization name strings extracted from cooperation notes.
        For EACH input string, do NOT merge or group them. Treat each line independently.

        For each string:
          - "raw": the original string
          - "normalized": a concise, canonical organization name for that string only
          - "type": one of
              "company", "university", "research_institute",
              "public_authority", "ngo", "other"
          - "country": country name if obvious (e.g. "Sweden"), else ""

        Heuristics:
          - If the name ends with a common legal company suffix (case-insensitive, ignoring trailing dots), classify type="company"
          unless there is a very strong reason not to. Treat these as strong company signals:
          "AB", "Oy", "Oyj", "A/S",
          "GmbH", "GmbH & Co. KG", "AG",
          "Ltd", "Limited",
          "Inc", "Incorporated",
          "Corp", "Corporation",
          "LLC", "PLC",
          "NV", "N.V.", "BV", "B.V.",
          "S.A.", "SA", "SAS",
          "Srl", "SRL", "SpA", "S.p.A.",
          "Sp. z o.o.", "s.r.o.", "s.r.l.",
          "Ltda", "Ltée", "Pty Ltd", "Pte Ltd".
          - If the name contains "University", "Institute of Technology", or "College",
            classify type="university" unless it is clearly a department inside a company.
          - If the name contains "Authority", "Agency", "Ministry", or "Office"
            and looks governmental, classify type="public_authority".
          - If the name looks like a person's name (for example "First Last"),
            set normalized="" and type="other".
          - If the name clearly refers to a Swedish organization (has "AB"
            and/or the word "Sweden" or is a well-known Swedish company),
            set country="Sweden".

        Important:
          - Do NOT group or cluster multiple inputs into one organization.
          - Output one JSON object per input string, in the SAME ORDER.
          - If input is too vague to be an organization, set normalized="" and type="other".

        Respond ONLY with a JSON array of objects, e.g.:

        [
          {"raw": "...", "normalized": "...", "type": "company", "country": "Sweden"},
          ...
        ]
        """
    )

    text_block = "\n".join(f"- {c}" for c in candidates)
    prompt = instruction + "\n\nInput strings:\n" + text_block + "\n\nJSON:"

    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False},
    )
    resp.raise_for_status()

    # Top-level object from Ollama
    raw = resp.text
    print("----- RAW LLM RESPONSE START -----")
    print(raw)
    print("----- RAW LLM RESPONSE END -----")

    try:
        top = json.loads(raw)
    except Exception as e:
        print(f"Failed to parse top-level JSON: {e}")
        return []

    response_str = top.get("response", "")
    if not isinstance(response_str, str):
        print("No 'response' string in top-level JSON")
        return []

    # Extract the first JSON array inside the response string
    start = response_str.find("[")
    end = response_str.rfind("]")
    if start == -1 or end == -1 or end <= start:
        print("No JSON array brackets found inside 'response'")
        return []

    array_str = response_str[start : end + 1]

    try:
        arr = json.loads(array_str)
    except Exception as e:
        print(f"Failed to parse inner JSON array: {e}")
        print("Inner string was:")
        print(array_str)
        return []

    out = []
    for item in arr:
        out.append(
            {
                "raw": (item.get("raw") or "").strip(),
                "normalized": (item.get("normalized") or "").strip(),
                "type": (item.get("type") or "").strip() or "other",
                "country": (item.get("country") or "").strip(),
            }
        )
    return out


def build_institution_inventory(df, max_rows=50, batch_size=5):
    """
    df: DataFrame with at least column 'note_cooperation'.

    1) Extract regex-based organization candidates from up to max_rows notes.
    2) Deduplicate candidates.
    3) Normalize and classify each candidate in small batches via LLM.

    Returns a list of dicts:
      { "raw": "...", "normalized": "...", "type": "...", "country": "..." }
    """
    print(f"Building institution inventory from up to {max_rows} notes...")

    all_candidates = []
    for idx, (_, row) in enumerate(df.head(max_rows).iterrows(), start=1):
        raw = row["note_cooperation"]
        cands = extract_coop_entities_regex(raw)
        all_candidates.extend(cands)
        if idx % 500 == 0:
            print(f"  processed {idx} notes, current candidates: {len(all_candidates)}")

    # deduplicate
    all_candidates = sorted({c for c in all_candidates if c.strip()})
    print(f"Unique regex candidates: {len(all_candidates)}")

    results = []
    for i in range(0, len(all_candidates), batch_size):
        batch = all_candidates[i : i + batch_size]
        print(
            f"Normalizing batch {i}–{i + len(batch) - 1} "
            f"({i//batch_size + 1}/{(len(all_candidates)-1)//batch_size + 1}) ...",
            flush=True,
        )
        batch_res = normalize_batch_with_llm(batch)
        print(f"  -> got {len(batch_res)} items", flush=True)
        results.extend(batch_res)

    return results


if __name__ == "__main__":
    df = load_notes()
    print(f"Loaded {len(df)} cooperation notes from {CSV_PATH}")

    inst_rows = build_institution_inventory(df, max_rows=50, batch_size=5)
    print(f"Got {len(inst_rows)} normalized items")

    out_path = "/home/aw/cooperation/institution_inventory_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inst_rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path}")
