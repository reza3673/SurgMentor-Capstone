# scripts/01_prepare_data.py
"""
Phase 1A — DATA PREPARATION
============================
Reads data/cases.xlsx, cleans each row, and converts it into a rich
clinical case narrative ready for embedding.

Run:
    python scripts/01_prepare_data.py

Output:
    data/prepared_cases.json

Course concept: Deployability (Day 5) — reproducible data pipeline with a
single command. Any contributor can regenerate the vector store from source.
"""

import json
import os
import re

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
INPUT_FILE  = "./data/cases.xlsx"
OUTPUT_FILE = "./data/prepared_cases.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe(val, default: str = "Not documented") -> str:
    """Convert NaN / None / empty cell to a safe default string."""
    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "nan":
        return default
    return str(val).strip()


def format_lab_block(raw: str) -> str:
    """
    Convert raw lab text from Excel into a clean, aligned, grouped layout.

    Input example:
        Inflammatory Markers
        WBC: 17.4 x10^9/L
        CRP: 158 mg/L

    Output example:
        Inflammatory Markers
        WBC   17.4 x10^9/L
        CRP   158 mg/L

    Rules:
    - Lines with "param: value" are data rows.
    - Lines without a colon (or empty value) are category headers.
    - Lines starting with digit/operator after a header are standalone values.
    """
    stripped = str(raw).strip()
    if not stripped or stripped.lower() in ("not documented", "non", "nan"):
        return stripped
    if "\n" not in stripped and ":" not in stripped:
        return stripped

    lines = [l.strip() for l in stripped.split("\n") if l.strip()]

    # Parse into groups: [(header, [(param, value), ...]), ...]
    groups   = []
    header   = ""
    rows     = []
    buffered = None

    def flush():
        if rows:
            groups.append((header, list(rows)))

    for line in lines:
        if ":" in line:
            param, _, val = line.partition(":")
            val = val.strip()
            if val:
                if buffered is not None:
                    flush()
                    rows.clear()
                    header   = buffered
                    buffered = None
                rows.append((param.strip(), val))
            else:
                if buffered is not None:
                    flush()
                    rows.clear()
                    header = buffered
                elif rows:
                    flush()
                    rows.clear()
                    header = ""
                buffered = param.strip()
        else:
            if re.match(r"^[\d<>+-]", line):
                if buffered is not None:
                    flush()
                    rows.clear()
                    rows.append((buffered, line))
                    header   = ""
                    buffered = None
                else:
                    rows.append(("", line))
            else:
                if buffered is not None:
                    flush()
                    rows.clear()
                    header = buffered
                elif rows:
                    flush()
                    rows.clear()
                    header = ""
                buffered = line

    if buffered is not None:
        flush()
        rows.clear()
        header   = buffered
        buffered = None
    flush()

    parts = []
    for grp_header, grp_rows in groups:
        if not grp_rows:
            continue
        max_param = max((len(p) for p, _ in grp_rows if p), default=0)
        col = max_param + 3
        block_lines = []
        for param, val in grp_rows:
            block_lines.append(f"{param:<{col}}{val}" if param else val)
        block = "\n".join(block_lines)
        parts.append(f"{grp_header}\n{block}" if grp_header else block)

    return "\n\n".join(parts) if parts else stripped


# ── Core conversion ───────────────────────────────────────────────────────────

def row_to_document(row: dict) -> str:
    """
    Convert a single Excel row into a rich clinical case narrative.
    High-quality text → high-quality retrieval embeddings.
    """
    return f"""CLINICAL CASE ID: {safe(row.get('Id', 'Unknown'))}

DIAGNOSIS: {safe(row.get('Diagnosis_short', 'Unknown'))}
KEYWORDS: {safe(row.get('Diagnosis_keywords', 'None'))}

PATIENT PROFILE:
- Age: {safe(row.get('Age'))} years old
- Sex: {safe(row.get('Sex'))}
- Disease Category: {safe(row.get('Disease'))}

HISTORY OF PRESENTING COMPLAINT:
{safe(row.get('History_text'))}

SYMPTOM ANALYSIS:
- Chief Complaints: {safe(row.get('Complaints'))}
- Site: {safe(row.get('Site'))}
- Onset: {safe(row.get('Onset'))}
- Character: {safe(row.get('Character'))}
- Radiation: {safe(row.get('Radiation'))}
- Associated Symptoms: {safe(row.get('Associative symptoms'))}
- Timing: {safe(row.get('Timing'))}
- Exacerbating Factors: {safe(row.get('Exacerbating'))}
- Relieving Factors: {safe(row.get('Relief'))}
- TBC: {safe(row.get('TBC'))}

PHYSICAL EXAMINATION:
{safe(row.get('Exam'))}

INVESTIGATIONS:
- Blood Type: {safe(row.get('Blood_type'))}
- Blood Infections: {safe(row.get('Blood_infections'))}
- HCG: {safe(row.get('HGC'))}

Biochemistry:
{format_lab_block(safe(row.get('Biochemystry')))}

Urine Analysis:
{format_lab_block(safe(row.get('Urine_analysis')))}

Coagulation:
{format_lab_block(safe(row.get('Coagulation')))}

IMAGING:
- Abdominal Ultrasound: {safe(row.get('Abdomen_US'))}
- CT Scan: {safe(row.get('CT_text'))}
- Chest X-Ray: {safe(row.get('CXR'))}

CONCLUSION / CLINICAL REASONING:
{safe(row.get('Conclusion'))}

EXPLANATION:
{safe(row.get('Explanation'))}""".strip()


def row_to_metadata(row: dict) -> dict:
    """
    Extract ChromaDB metadata fields used for retrieval filtering.
    (diagnosis, disease category, imaging availability, patient demographics)
    """
    return {
        "case_id":   safe(row.get("Id",                "unknown")),
        "disease":   safe(row.get("Disease",            "unknown")),
        "diagnosis": safe(row.get("Diagnosis_short",    "unknown")),
        "keywords":  safe(row.get("Diagnosis_keywords", "")),
        "age":       safe(row.get("Age",                "0")),
        "sex":       safe(row.get("Sex",                "unknown")),
        "has_ct": "yes" if (
            pd.notna(row.get("CT_text")) and
            str(row.get("CT_text")).strip() != ""
        ) else "no",
        "has_us": "yes" if (
            pd.notna(row.get("Abdomen_US")) and
            str(row.get("Abdomen_US")).strip() != ""
        ) else "no",
        "ct_urls":    safe(row.get("CT_urls",    ""), default=""),
        "video_urls": safe(row.get("video_urls", ""), default=""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SurgMentor — Phase 1A: Data Preparation")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            "Ensure data/cases.xlsx is present before running this script."
        )

    print(f"\nLoading {INPUT_FILE} ...")
    df = pd.read_excel(INPUT_FILE, engine="openpyxl")
    df.columns = [col.strip() for col in df.columns]

    print(f"Loaded {len(df)} rows")
    print(f"Columns: {list(df.columns)}\n")

    prepared = []
    skipped  = 0

    for idx, row in df.iterrows():
        try:
            prepared.append({
                "id":       f"case_{safe(row.get('Id', idx))}",
                "text":     row_to_document(row),
                "metadata": row_to_metadata(row),
            })
        except Exception as e:
            print(f"WARNING: Skipped row {idx}: {e}")
            skipped += 1

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(prepared, f, indent=2, ensure_ascii=False)

    print(f"Prepared : {len(prepared)} cases")
    print(f"Skipped  : {skipped} cases")
    print(f"Saved to : {OUTPUT_FILE}")

    if prepared:
        print("\n" + "=" * 60)
        print("PREVIEW — Case 1:")
        print("=" * 60)
        print(prepared[0]["text"][:500])
        print("...\n")
        print("METADATA:", prepared[0]["metadata"])

    print("\nScript 01 complete. Next: python scripts/02_embed_and_store.py")


if __name__ == "__main__":
    main()
