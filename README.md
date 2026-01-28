# exjobb_cooperation
```
COPY (
  SELECT pid, note_cooperation
  FROM note_cooperation
  WHERE note_cooperation IS NOT NULL
) TO 'note_cooperation.csv'
WITH (HEADER, DELIMITER ',');
```

Running coop_inventory.py 
```
cd /home/aw
nohup python -m cooperation.coop_inventory > coop_inventory.log 2>&1 &

```


Input file: note_cooperation.csv  
```
pid,note_cooperation
1138389,"{'pid': 1138389, 'org_coop': Skanska Sverige AB}"
550267,"{'pid': 550267, 'org_coop': ABB LV Motors,Åke Andersson}"
693749,"{'pid': 693749, 'org_coop': Stoneridge Electronics}"
724369,"{'pid': 724369, 'org_coop': Mostphotos}"
743805,"{'pid': 743805, 'org_coop': Ute's group, MTC, Karolinska Institute}"
542132,"{'pid': 542132, 'org_coop': Tobii Technology AB}"
706730,"{'pid': 706730, 'org_coop': DGC One AB}"
1230122,"{'pid': 1230122, 'org_coop': KRY}"
1252231,"{'pid': 1252231, 'org_coop': H&E Solutions}"
```
Output file: institution_inventory_raw.json
``` {
    "raw": "Abb Lv Motors",
    "normalized": "ABB LV Motors",
    "type": "company",
    "country": ""
  },
  {
    "raw": "Beyond Atlas",
    "normalized": "Beyond Atlas",
    "type": "other",
    "country": ""
  },
  {
    "raw": "Dgc One Ab",
    "normalized": "DGC One AB",
    "type": "company",
    "country": ""
  },
  {
    "raw": "Ericsson Ab",
    "normalized": "Ericsson AB",
    "type": "company",
    "country": "Sweden"
  },
  {
    "raw": "H&E Solutions",
    "normalized": "H&E Solutions",
    "type": "other",
    "country": ""
  },
  {
    "raw": "Hbo Europe",
    "normalized": "HBO Europe",
    "type": "company",
    "country": ""
  },
  {
    "raw": "Iggesund Paperboard",
    "normalized": "Iggesund Paperboard",
    "type": "company",
    "country": "Sweden"
  }

```


***

## `CSV_PATH` and imports

- You point to a CSV file (`note_cooperation.csv`) that you exported from DuckDB.
- That CSV is expected to contain a column called `note_cooperation` with the raw cooperation text per publication.

***

## `load_notes()`

Purpose: **load your CSV and prepare the raw text column**.

What it does:

1. Reads `note_cooperation.csv` into a pandas DataFrame.
2. Checks that there is a column named `note_cooperation`. If not, it raises an error so you notice early.
3. Drops rows where `note_cooperation` is missing (`NaN`).
4. Forces the column to string and strips leading/trailing whitespace.
5. Returns this cleaned DataFrame.

Intuitively: “Give me all cooperation notes as clean text, one row per note.”

***

## `normalize_batch_with_llm(candidates)`

Purpose: **send a small list of organization strings to the LLM and get normalized metadata back**.

Input: `candidates` is a Python list like `["ABB LV Motors", "Scania CV AB", ...]`.

What it does:

1. If the list is empty, it returns `[]` immediately.
2. Builds a long instruction string that tells the LLM:
    - You will see several organization name strings.
    - For each one, independently, return an object with:
        - `raw` (original string)
        - `normalized` (canonical org name)
        - `type` (company / university / etc.)
        - `country` (if obvious)
    - Also gives some heuristics (AB/Ltd → company, University → university, etc.).
    - Asks for a pure JSON array as the response.
3. Builds a text block listing the candidates, one per line prefixed with `- `.
4. Concatenates instruction + “Input strings:” + the list + “JSON:” into a single prompt.
5. Sends this prompt to your local LLM HTTP endpoint (Ollama) with `requests.post(...)`.
6. Prints the raw HTTP response for debugging.
7. Tries to parse the HTTP response as JSON and extract the model’s textual `response` field.
8. Inside that response string, finds the first `[` and last `]` and takes that substring, assuming it is the JSON array the model produced.
9. Parses that substring as JSON; if this fails at any stage, it logs and returns `[]`.
10. For each item in the parsed array, it builds a cleaned dict:

```python
{
  "raw": "...",
  "normalized": "...",
  "type": "...",   # defaulting to "other" if missing/empty
  "country": "..."
}
```

11. Returns the list of these dicts.

Intuitively: “Given up to N organization strings, ask the LLM to classify and normalize each, and give me back a clean JSON list.”

***

## `build_institution_inventory(df, max_rows=50, batch_size=5)`

Purpose: **scan many cooperation notes, pull out candidate organizations, and normalize them in batches via the LLM**.

Inputs:

- `df`: the DataFrame from `load_notes()` (has a `note_cooperation` column).
- `max_rows`: how many notes to process at most.
- `batch_size`: how many candidate names to send to the LLM in one go.

What it does:

1. Prints a message like “Building institution inventory from up to 50 notes…”.
2. Initializes an empty list `all_candidates`.
3. Loops over the first `max_rows` rows of the DataFrame:
    - For each row, gets the raw text `raw = row["note_cooperation"]`.
    - Calls `extract_coop_entities_regex(raw)`, which is your own helper that uses regular expressions to extract potential organization names from that text.
    - Extends `all_candidates` with whatever `extract_coop_entities_regex` found.
    - Every 500 notes (for large runs) it prints progress.
4. After the loop, deduplicates the candidates:
    - Strips out empty/whitespace‑only strings.
    - Uses a set to make them unique, then sorts them into a list.
    - Prints how many unique candidates it ended up with.
5. Initializes `results = []`.
6. Walks through `all_candidates` in chunks (`batch_size` at a time):
    - For each batch, prints a “Normalizing batch …” progress line with batch numbers.
    - Calls `normalize_batch_with_llm(batch)`.
    - Prints how many items came back from that batch.
    - Extends `results` with those normalized items.
7. Returns `results`: a list of dicts of the form

```python
{
  "raw": "...",
  "normalized": "...",
  "type": "...",
  "country": "..."
}
```


Intuitively: “From up to N notes, extract all distinct organization‑looking fragments with regex, then feed them in small batches to the LLM and collect a unified list of normalized organizations.”

***

## `if __name__ == "__main__":` block

Purpose: **make the script runnable as a standalone command**.

What it does when you run `python script.py`:

1. Calls `load_notes()`, gets your cooperation notes, prints how many rows were loaded.
2. Calls `build_institution_inventory(df, max_rows=50, batch_size=5)` to build your inventory:
    - With the current defaults, it only uses the first 50 notes and sends 5 candidates per LLM call (good for testing).
3. Prints how many normalized items it got.
4. Writes them to `/home/aw/cooperation/institution_inventory_raw.json` as pretty‑printed JSON (UTF‑8, no ASCII escaping).
5. Prints “Wrote /home/aw/cooperation/institution_inventory_raw.json”.

Intuitively: “Load notes → extract + normalize all orgs → save a JSON inventory file on disk.”

***




