"""Biryani Kitchen OS - starter app (Google Gemini version).
Run:  pip install -r requirements.txt   then   streamlit run app.py
"""
import os
import datetime as dt
import pandas as pd
import streamlit as st

LOG_FILE = "batch_log.csv"
LOG_COLS = ["date", "rice_kg", "rice_boil_min", "dum_min", "taste_1to5", "problem", "notes"]

# Master recipe for 1 kg rice: name -> (quantity, unit, price per kg or litre in Rs).
# Prices are placeholders. Replace them with your real Mysore supplier rates.
RECIPE = {
    "Rice (seeraga samba/basmati)": (1000, "g", 120),
    "Chicken, bone-in": (1200, "g", 220),
    "Curd": (250, "g", 70),
    "Ginger-garlic paste": (120, "g", 150),
    "Green chilli paste": (30, "g", 120),
    "Red chilli powder": (15, "g", 300),
    "Turmeric": (3, "g", 200),
    "Biryani masala": (15, "g", 800),
    "Salt (marinade + rice water)": (80, "g", 20),
    "Lemon juice": (40, "ml", 100),
    "Mint": (70, "g", 80),
    "Coriander leaves": (70, "g", 60),
    "Oil": (80, "ml", 130),
    "Ghee": (90, "g", 600),
    "Onions": (500, "g", 40),
    "Tomatoes": (300, "g", 40),
}

STEPS = [
    "Marinate chicken 4+ hours (chilled).",
    "Cook masala base until oil separates; add chicken, cook 12-15 min (70% done).",
    "Boil rice in salty water to 70-80% done, drain immediately.",
    "Layer masala, rice, birista, herbs, ghee, lemon. Seal handi.",
    "Dum: 3 min high, then 20-25 min lowest on a tawa. Rest 10 min.",
]

SYSTEM_PROMPT = (
    "You are a senior Tamil Muslim style biryani chef and kitchen quality consultant. "
    "Give short, practical fixes in simple English: 1) likely cause, 2) fix for this batch, "
    "3) one change for the next batch. Change only one variable at a time. Be concise."
)

st.set_page_config(page_title="Biryani Kitchen OS", page_icon="🍗", layout="wide")
st.title("🍗 Biryani Kitchen OS")

tab1, tab2, tab3, tab4 = st.tabs(["Recipe scaler", "Batch log", "AI fixer", "Cost"])


def load_log():
    if os.path.exists(LOG_FILE):
        return pd.read_csv(LOG_FILE)
    return pd.DataFrame(columns=LOG_COLS)


def recipe_text(rice_kg):
    return "\n".join(f"- {k}: {v[0] * rice_kg:.0f} {v[1]}" for k, v in RECIPE.items())


def get_saved_key():
    """Look for the Gemini key in Streamlit secrets, then in environment variables."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


# ---------- Tab 1: Recipe scaler ----------
with tab1:
    rice_kg = st.number_input("Rice batch size (kg)", 1.0, 50.0, 5.0, 0.5)
    df = pd.DataFrame(
        [{"Ingredient": k, "Amount": round(v[0] * rice_kg), "Unit": v[1]} for k, v in RECIPE.items()]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.subheader("Method")
    for i, s in enumerate(STEPS, 1):
        st.write(f"{i}. {s}")
    st.info("Rule: weigh everything. Undercooked rice is better than overcooked, because dum finishes it.")

# ---------- Tab 2: Batch log ----------
with tab2:
    st.subheader("Log every batch")
    with st.form("log_form"):
        c1, c2, c3, c4 = st.columns(4)
        rk = c1.number_input("Rice kg", 1.0, 50.0, 5.0, 0.5)
        boil = c2.number_input("Rice boil (min)", 1, 30, 7)
        dum = c3.number_input("Dum (min)", 5, 60, 25)
        taste = c4.slider("Taste score", 1, 5, 4)
        problem = st.selectbox(
            "Problem",
            ["None", "Rice too soft", "Rice undercooked", "Too dry", "Too spicy", "Bland", "Burnt bottom", "Other"],
        )
        notes = st.text_input("Notes")
        if st.form_submit_button("Save batch"):
            new = pd.DataFrame(
                [[dt.date.today().isoformat(), rk, boil, dum, taste, problem, notes]], columns=LOG_COLS
            )
            pd.concat([load_log(), new]).to_csv(LOG_FILE, index=False)
            st.success("Saved")
    log = load_log()
    if not log.empty:
        st.line_chart(log.reset_index()["taste_1to5"])
        st.dataframe(log.tail(20), use_container_width=True, hide_index=True)
        st.caption("Problem count: " + str(log["problem"].value_counts().to_dict()))

# ---------- Tab 3: AI fixer (Google Gemini) ----------
with tab3:
    st.subheader("Describe a problem, get a fix")
    saved_key = get_saved_key()
    if saved_key:
        st.success("Gemini API key found.")
        key = saved_key
    else:
        key = st.text_input("Paste your Gemini API key", type="password")
    model = st.text_input("Gemini model", value="gemini-2.5-flash")
    issue = st.text_area("What went wrong? (taste, texture, timing, smell...)")

    if st.button("Get fix"):
        if not key:
            st.warning("Please add your Gemini API key first.")
        elif not issue.strip():
            st.warning("Please describe the problem first.")
        else:
            try:
                from google import genai
                from google.genai import types

                recent = load_log().tail(10).to_string(index=False)
                prompt = (
                    f"Base recipe (per 1 kg rice):\n{recipe_text(1)}\n\n"
                    "Method:\n" + "\n".join(STEPS) +
                    f"\n\nRecent batch log:\n{recent}\n\nProblem: {issue}"
                )
                client = genai.Client(api_key=key)
                with st.spinner("Thinking..."):
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                    )
                st.markdown(resp.text)
            except Exception as e:
                st.error(f"AI call failed: {e}")
                st.caption("If it says model not found, try another Gemini model name in the box above.")

# ---------- Tab 4: Cost ----------
with tab4:
    st.subheader("Food cost per plate")
    st.caption("Prices are placeholders per kg or litre. Replace them with your supplier rates.")
    plates = st.number_input("Plates per 1 kg rice batch", 4, 20, 8)
    price = st.number_input("Selling price per plate (Rs)", 50, 1000, 220)
    rows = []
    for k, (q, u, p) in RECIPE.items():
        p_new = st.number_input(f"{k} (Rs per kg/L)", 0, 5000, p, key=f"p_{k}")
        rows.append({"Ingredient": k, "Cost (Rs)": round(q / 1000 * p_new, 1)})
    total = pd.DataFrame(rows)["Cost (Rs)"].sum()
    per_plate = total / plates
    pct = per_plate / price * 100
    c1, c2, c3 = st.columns(3)
    c1.metric("Batch cost", f"Rs {total:.0f}")
    c2.metric("Cost per plate", f"Rs {per_plate:.0f}")
    c3.metric("Food cost %", f"{pct:.0f}%", "OK" if pct <= 35 else "Too high",
              delta_color="normal" if pct <= 35 else "inverse")
