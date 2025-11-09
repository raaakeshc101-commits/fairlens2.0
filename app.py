import streamlit as st
import pandas as pd
import numpy as np
import io

# -----------------------------
# App config
# -----------------------------
st.set_page_config(page_title="FairLens Pro v2", layout="wide")
st.title("FairLens Pro v2 — Performance Appraisal Auditor")
st.caption("Collect ratings + comments, audit text bias, and run group fairness checks (privacy-first demo).")

# -----------------------------
# Bias rules (simple, transparent)
# -----------------------------
VAGUE = [
    "hard worker", "good attitude", "average", "improve communication", "team player",
    "works well under pressure", "strong potential", "fit", "not a good fit"
]
BIAS = [
    "young", "old", "energetic", "emotional", "bossy", "cultural fit", "girls", "guys", "aggressive"
]

def find_flags(text: str):
    if not text:
        return []
    text_l = text.lower()
    flags = []
    for term in VAGUE + BIAS:
        start = 0
        while True:
            idx = text_l.find(term, start)
            if idx == -1:
                break
            flags.append({
                "phrase": term,
                "category": "Vague" if term in VAGUE else "Bias",
                "index": idx
            })
            start = idx + len(term)
    return flags

# -----------------------------
# Session state for data (no DB; privacy-safe demo)
# -----------------------------
if "reviews" not in st.session_state:
    # Seed demo data (anonymized)
    st.session_state.reviews = pd.DataFrame({
        "employee_id": [f"E{i:03d}" for i in range(1, 11)],
        "role": ["Manager"]*5 + ["Analyst"]*5,
        "gender": ["F","M","F","M","F","M","F","M","F","M"],
        "kpi_rating": [4,3,4,3,4,3,3,3,4,3],
        "competency_rating": [4,4,3,3,4,3,3,3,4,3],
        "initiative_rating": [4,3,3,3,4,3,3,3,4,3],
        "overall_rating": [4,3,3,3,4,3,3,3,4,3],
        "comment": [
            "Strong potential; team player.",
            "Meets goals but not a good fit.",
            "Hard worker; needs to improve communication.",
            "Energetic and ambitious.",
            "Good attitude; works well under pressure.",
            "Can be emotional in feedback.",
            "Average performance; can step up.",
            "Aggressive at times.",
            "Great culture fit.",
            "Bossy in team settings."
        ]
    })

# -----------------------------
# Tabs
# -----------------------------
tab_submit, tab_audit, tab_priv = st.tabs(["Submit Review", "Audit Dashboard", "Privacy & Export"])

# -----------------------------
# TAB 1: Submit Review (data entry form)
# -----------------------------
with tab_submit:
    st.subheader("Submit a Performance Review (Anonymized)")
    st.write("**No names/PII.** Use an ID, plus role & gender for fairness checks.")

    with st.form("review_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            employee_id = st.text_input("Employee ID (e.g., E011)")
        with col2:
            role = st.selectbox("Role", ["Manager", "Analyst", "Engineer", "Sales", "Other"])
        with col3:
            gender = st.selectbox("Gender (for demo parity)", ["F", "M", "Non-binary/Other"])

        st.markdown("**Ratings (1–5)**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi = st.slider("KPI", 1, 5, 3)
        with c2:
            comp = st.slider("Competency", 1, 5, 3)
        with c3:
            initv = st.slider("Initiative", 1, 5, 3)
        with c4:
            overall = st.slider("Overall", 1, 5, 3)

        comment = st.text_area("Manager Comment (no PII)",
                               value="She is a hard worker and a good cultural fit but needs to improve communication.",
                               height=140)

        submitted = st.form_submit_button("Save Review", type="primary")

    if submitted:
        if not employee_id.strip():
            st.error("Please provide an Employee ID (anonymized).")
        else:
            new_row = pd.DataFrame([{
                "employee_id": employee_id.strip(),
                "role": role,
                "gender": gender,
                "kpi_rating": kpi,
                "competency_rating": comp,
                "initiative_rating": initv,
                "overall_rating": overall,
                "comment": comment.strip()
            }])
            st.session_state.reviews = pd.concat([st.session_state.reviews, new_row], ignore_index=True)
            st.success(f"Saved review for {employee_id.strip()} ✅")

    st.markdown("#### Current (Anonymized) Reviews in Session")
    st.dataframe(st.session_state.reviews, use_container_width=True, height=300)
    st.caption("Data is session-scoped for demo. Export in the 'Privacy & Export' tab. No server persistence.")

# -----------------------------
# TAB 2: Audit Dashboard (text flags + fairness on ratings)
# -----------------------------
with tab_audit:
    st.subheader("Audit Dashboard")

    # Optional upload to replace session data (for demonstrations)
    uploaded = st.file_uploader("Optional: Upload CSV to replace session data (columns must match).", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            needed = {"employee_id","role","gender","kpi_rating","competency_rating","initiative_rating","overall_rating","comment"}
            if not needed.issubset(df_up.columns):
                st.error(f"CSV missing columns. Required: {sorted(list(needed))}")
            else:
                st.session_state.reviews = df_up.copy()
                st.success("Uploaded CSV loaded into session.")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

    df = st.session_state.reviews.copy()

    # ----- Text bias flags -----
    st.markdown("### Text Bias Flags (Narrative Layer)")
    # Build flags table
    all_flags = []
    for _, row in df.iterrows():
        flags = find_flags(str(row.get("comment", "")))
        if flags:
            for f in flags:
                all_flags.append({
                    "employee_id": row["employee_id"],
                    "role": row["role"],
                    "gender": row["gender"],
                    "phrase": f["phrase"],
                    "category": f["category"]
                })
    if all_flags:
        flag_df = pd.DataFrame(all_flags)
        st.dataframe(flag_df, use_container_width=True, height=250)
        st.caption("Flags are transparent and rule-based to support explainability. Use as coaching signals, not final judgments.")
        by_cat = flag_df.groupby("category")["phrase"].count().rename("count").reset_index()
        st.bar_chart(by_cat.set_index("category"))
    else:
        st.info("No flags detected by v2 rules in current session data.")

    st.markdown("---")

    # ----- Ratings fairness -----
    st.markdown("### Ratings Fairness (Numeric Layer)")
    by_group = st.selectbox("Compare by group", ["gender", "role"])
    # Summary stats
    cols = ["kpi_rating","competency_rating","initiative_rating","overall_rating"]
    summary = df.groupby(by_group)[cols].agg(["mean","count"]).round(2)
    st.dataframe(summary, use_container_width=True)

    # Mean gap on overall
    st.markdown("#### Mean Overall Rating Gap")
    groups = df[by_group].dropna().unique()
    if len(groups) >= 2:
        # Only compare top two by count for a clean demo
        counts = df[by_group].value_counts().index.tolist()
        g1 = counts[0]
        g2 = counts[1] if len(counts) > 1 else groups[1]
        m1 = df[df[by_group]==g1]["overall_rating"].mean()
        m2 = df[df[by_group]==g2]["overall_rating"].mean()
        gap = abs(m1 - m2)
        st.write(f"{by_group}={g1}: {m1:.2f}  vs  {by_group}={g2}: {m2:.2f}  → **Gap = {gap:.2f}**")
        if gap >= 0.30:
            st.warning("Gap ≥ 0.30 on a 1–5 scale may warrant review (training/calibration/data quality).")
        else:
            st.success("Mean gap < 0.30; no strong disparity indicated.")
    else:
        st.info("Provide at least two groups to compute a mean gap.")

    # AIR proxy on 'meets/exceeds'
    st.markdown("#### Meets/Exceeds Parity (AIR proxy)")
    threshold = st.slider("Meets/Exceeds threshold (Overall ≥)", 1.0, 5.0, 3.0, 0.5)
    rates = (df.assign(meets=(df["overall_rating"] >= threshold))
               .groupby(by_group)["meets"].mean()
               .rename("rate")
               .reset_index())
    st.dataframe(rates, use_container_width=True)
    if len(rates) >= 2:
        top = rates["rate"].max()
        bottom = rates["rate"].min()
        air = (bottom / top) if top > 0 else np.nan
        st.write(f"AIR (min/max) = **{air:.2f}**  (rule-of-thumb: ≥ 0.80)")
        if air < 0.80:
            st.error("AIR < 0.80 — investigate potential disparity (sample size, criteria clarity, rater training).")
        else:
            st.success("AIR ≥ 0.80 — no adverse impact signal on this proxy metric.")
    else:
        st.info("Provide at least two groups to compute AIR.")

    st.caption("Note: These are indicators for coaching and monitoring — not dispositive findings. Human review required.")

# -----------------------------
# TAB 3: Privacy & Export
# -----------------------------
with tab_priv:
    st.subheader("Privacy, Governance & Export")
    st.markdown("""
- **No PII**: Use anonymized IDs only.
- **Aggregation-first**: Share team-level views only when **n ≥ 5** per group.
- **Retention (demo)**: Session-based; no server persistence. Export locally if needed.
- **Explainability**: Rule-based flags are transparent and editable.
- **Compliance touchpoints**: Title VII principles, NIST AI RMF; AIR used as a rule-of-thumb (≥ 0.80).
    """)

    # Export current session data
    buf = io.StringIO()
    st.session_state.reviews.to_csv(buf, index=False)
    st.download_button("Download Current Reviews CSV", buf.getvalue(), file_name="fairlens_reviews.csv")

    # Provide a clean rules list for transparency
    rules = pd.DataFrame({
        "term": VAGUE + BIAS,
        "category": ["Vague"]*len(VAGUE) + ["Bias"]*len(BIAS)
    })
    buf2 = io.StringIO()
    rules.to_csv(buf2, index=False)
    st.download_button("Download Rules (Transparency)", buf2.getvalue(), file_name="fairlens_rules.csv")

st.caption("© FairLens Pro v2 — educational demo. Replace lists/thresholds with your org standards during deployment.")
