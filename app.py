"""Biryani Kitchen OS v2 - run:  pip install -r requirements.txt  then  streamlit run app.py"""
import os, math, random, datetime as dt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Biryani Kitchen OS", page_icon="🍗", layout="wide")
DATA = "data"
os.makedirs(DATA, exist_ok=True)

SCHEMA = {
    "sales": ["date", "channel", "plates", "revenue"],
    "waste": ["date", "plates", "reason"],
    "batches": ["date", "rice_kg", "boil_min", "dum_min", "taste", "problem", "notes"],
    "stock": ["item", "qty", "unit", "reorder_at"],
}
# Commission per channel (placeholders: check your real Swiggy/Zomato rates)
CHANNELS = {"Dine-in": 0.0, "Takeaway": 0.0, "WhatsApp": 0.0, "Swiggy": 0.25, "Zomato": 0.25}
# Recipe for 1 kg rice: name -> (qty, unit, price per kg/L in Rs: placeholders)
RECIPE = {
    "Rice": (1000, "g", 120), "Chicken": (1200, "g", 220), "Curd": (250, "g", 70),
    "Ginger-garlic paste": (120, "g", 150), "Green chilli paste": (30, "g", 120),
    "Red chilli powder": (15, "g", 300), "Turmeric": (3, "g", 200), "Biryani masala": (15, "g", 800),
    "Salt": (80, "g", 20), "Lemon juice": (40, "ml", 100), "Mint": (70, "g", 80),
    "Coriander leaves": (70, "g", 60), "Oil": (80, "ml", 130), "Ghee": (90, "g", 600),
    "Onions": (500, "g", 40), "Tomatoes": (300, "g", 40),
}
PLATES_PER_KG = 8
STEPS = ["Marinate chicken 4+ hours, chilled.",
         "Cook masala until oil separates; add chicken, cook 12-15 min (70% done).",
         "Boil rice in salty water to 70-80% done; drain at once.",
         "Layer masala, rice, birista, herbs, ghee, lemon. Seal the handi.",
         "Dum: 3 min high, then 20-25 min lowest on a tawa. Rest 10 min."]
CHECKLISTS = {
    "Opening": ["Wash hands, wear apron and cap", "Check fridge temp (below 5 C)", "Check chicken freshness and date",
                "Marinade ready (made last night)", "Birista ready", "Gas and water checked", "Tawa and handis clean"],
    "During service": ["Probe chicken core temp (above 75 C)", "Taste a spoon from every dum batch",
                       "Wipe counters every hour", "Log every batch in the app"],
    "Closing": ["Log unsold plates as waste", "Store leftovers below 5 C or discard",
                "Count cash vs UPI vs app sales", "Update stock quantities", "Switch off gas, lock up"],
}
SYS = ("You are a senior Tamil Muslim style biryani chef and restaurant business coach in Mysore, India. "
       "Be practical, concise, and encouraging. Use simple English and short bullet points. "
       "Base answers on the data given; if data is missing, say so.")

# ---------------- data helpers ----------------
def load(n):
    p = f"{DATA}/{n}.csv"
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=SCHEMA[n])

def save(n, df):
    df.to_csv(f"{DATA}/{n}.csv", index=False)

def add(n, row):
    save(n, pd.concat([load(n), pd.DataFrame([row], columns=SCHEMA[n])], ignore_index=True))

def batch_cost():
    return sum(q / 1000 * p for q, u, p in RECIPE.values())

def daily():
    s = load("sales")
    if s.empty:
        return pd.DataFrame(columns=["date", "plates", "revenue"])
    d = s.groupby("date", as_index=False)[["plates", "revenue"]].sum()
    d["date"] = pd.to_datetime(d["date"])
    return d

def stock_qty(name):
    k = load("stock")
    m = k[k["item"].astype(str).str.lower().str.startswith(name.lower())]
    return float(pd.to_numeric(m["qty"]).sum()) if len(m) else 0.0

def kpis():
    s, w, b, k = load("sales"), load("waste"), load("batches"), load("stock")
    cut = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    s7, w7 = s[s["date"] >= cut], w[w["date"] >= cut]
    plates, rev = s7["plates"].sum(), s7["revenue"].sum()
    net = (s7["revenue"] * (1 - s7["channel"].map(CHANNELS).fillna(0))).sum()
    wasted = w7["plates"].sum()
    waste_pct = wasted / (plates + wasted) * 100 if plates + wasted > 0 else 0
    price = rev / plates if plates else 0
    fc = batch_cost() / PLATES_PER_KG / price * 100 if price else None
    taste = pd.to_numeric(b.tail(10)["taste"]).mean() if len(b) else None
    kk = k.copy()
    kk["qty"], kk["reorder_at"] = pd.to_numeric(kk["qty"]), pd.to_numeric(kk["reorder_at"])
    low = kk[kk["qty"] <= kk["reorder_at"]]["item"].tolist()
    today = s[s["date"] == dt.date.today().isoformat()]["plates"].sum()
    alerts, score = [], 100
    if fc and fc > 35: alerts.append(("error", f"Food cost is {fc:.0f}% (target 35% or less). Check supplier rates or portion size.")); score -= 20
    if waste_pct > 8: alerts.append(("error", f"Waste is {waste_pct:.1f}% this week. Cook smaller batches.")); score -= 20
    elif waste_pct > 5: alerts.append(("warning", f"Waste is {waste_pct:.1f}%. Watch the prep plan.")); score -= 8
    if taste is not None and taste < 4: alerts.append(("warning", f"Average taste score is {taste:.1f}/5 over the last 10 batches.")); score -= 15
    if low: alerts.append(("warning", "Low stock: " + ", ".join(low))); score -= 5 * min(len(low), 4)
    if not alerts: alerts.append(("success", "All good. Keep logging daily to keep it that way."))
    return dict(plates=plates, rev=rev, net=net, wasted=wasted, waste_pct=waste_pct, fc=fc, taste=taste,
                low=low, today=today, alerts=alerts, score=max(score, 0), price=price)

def snapshot():
    k = kpis()
    b = load("batches").tail(8).to_string(index=False)
    return (f"LAST 7 DAYS: plates {k['plates']}, revenue Rs {k['rev']:.0f}, net after commission Rs {k['net']:.0f}, "
            f"wasted plates {k['wasted']} ({k['waste_pct']:.1f}%), food cost % {k['fc']}, avg taste {k['taste']}, "
            f"low stock {k['low']}.\nRECENT BATCHES:\n{b}\nRECIPE PER 1 KG RICE: "
            + ", ".join(f"{n} {q}{u}" for n, (q, u, _) in RECIPE.items()) + "\nMETHOD: " + " ".join(STEPS))

# ---------------- sidebar + AI ----------------
def saved_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")

st.sidebar.title("🍗 Biryani Kitchen OS")
page = st.sidebar.radio("Go to", ["🏠 Command Center", "📈 Prep Planner", "💰 Sales & Waste", "🍚 Kitchen Lab",
                                  "📦 Stock", "⭐ Review Agent", "💬 Ask Your Manager", "✅ Checklists"])
KEY = saved_key() or st.sidebar.text_input("Gemini API key", type="password")
MODEL = st.sidebar.text_input("Gemini model", "gemini-2.5-flash")

def make_demo():
    random.seed(7)
    today, sales, waste, batches = dt.date.today(), [], [], []
    split = {"Dine-in": .35, "Takeaway": .2, "Swiggy": .25, "Zomato": .15, "WhatsApp": .05}
    for i in range(28, 0, -1):
        d = today - dt.timedelta(days=i)
        base = 60 + (25 if d.weekday() >= 5 else 0) + random.randint(-8, 8)
        for ch, f in split.items():
            n = int(base * f)
            sales.append([d.isoformat(), ch, n, n * random.choice([210, 220, 230])])
        waste.append([d.isoformat(), random.randint(1, 7), random.choice(["Unsold", "Spoiled", "Spillage"])])
        if i % 2 == 0:
            boil, dum = random.randint(5, 10), random.randint(16, 30)
            t = 5 - abs(dum - 24) * 0.15 - abs(boil - 7) * 0.2 + random.uniform(-.3, .3)
            t = round(max(1, min(5, t)) * 2) / 2
            prob = "None" if t >= 3.5 else random.choice(["Rice too soft", "Too dry", "Bland"])
            batches.append([d.isoformat(), 5, boil, dum, t, prob, ""])
    save("sales", pd.DataFrame(sales, columns=SCHEMA["sales"]))
    save("waste", pd.DataFrame(waste, columns=SCHEMA["waste"]))
    save("batches", pd.DataFrame(batches, columns=SCHEMA["batches"]))
    save("stock", pd.DataFrame([["Rice", 12, "kg", 10], ["Chicken", 8, "kg", 15], ["Onions", 20, "kg", 8],
                                ["Ghee", 3, "kg", 2], ["Oil", 10, "L", 5], ["Curd", 4, "kg", 5]], columns=SCHEMA["stock"]))

if st.sidebar.button("Load demo data"):
    make_demo()
    st.sidebar.success("Demo data loaded (28 days). Replace with real data when you start.")

def ai(prompt, system=SYS):
    if not KEY:
        return "Add your Gemini API key in the sidebar first."
    try:
        from google import genai
        from google.genai import types
        r = genai.Client(api_key=KEY).models.generate_content(
            model=MODEL, contents=prompt, config=types.GenerateContentConfig(system_instruction=system))
        return r.text
    except Exception as e:
        return f"AI call failed: {e}\n\nIf the model is not found, change the model name in the sidebar."

# ---------------- pages ----------------
if page == "🏠 Command Center":
    st.title("🏠 Command Center")
    k = kpis()
    c = st.columns(6)
    c[0].metric("Plates today", int(k["today"]))
    c[1].metric("7-day revenue", f"Rs {k['rev']:,.0f}")
    c[2].metric("Net after commission", f"Rs {k['net']:,.0f}")
    c[3].metric("Food cost %", f"{k['fc']:.0f}%" if k["fc"] else "-")
    c[4].metric("Waste %", f"{k['waste_pct']:.1f}%")
    c[5].metric("Health score", f"{k['score']}/100")
    st.progress(k["score"] / 100)
    for lvl, msg in k["alerts"]:
        getattr(st, lvl)(msg)
    d = daily().tail(28)
    if len(d):
        st.subheader("Revenue, last 28 days")
        st.bar_chart(d.set_index("date")["revenue"])
    else:
        st.info("No data yet. Click 'Load demo data' in the sidebar to see the app come alive.")
    if st.button("☀️ Generate my morning briefing"):
        with st.spinner("Reading your numbers..."):
            st.markdown(ai(snapshot() + "\n\nWrite a morning briefing: 3 wins, 3 risks, 3 actions for today.")) 

elif page == "📈 Prep Planner":
    st.title("📈 Prep Planner: what to cook and buy")
    day = st.date_input("Plan for", dt.date.today() + dt.timedelta(days=1))
    FACT = {"Normal day": 1.0, "Rainy day": 0.85, "Festival / holiday": 1.3,
            "Cricket match / event": 1.2, "Exam season / low footfall": 0.9}
    ev = st.selectbox("Special day?", list(FACT))
    factor = FACT[ev]
    d = daily()
    d = d[d["date"] >= pd.Timestamp(day) - pd.Timedelta(days=35)] if len(d) else d
    if d.empty:
        st.info("Need sales history. Log sales or load demo data.")
    else:
        same = d[d["date"].dt.weekday == day.weekday()]
        base = same["plates"].mean() if len(same) >= 2 else d["plates"].mean()
        plates = int(round(base * factor * 1.05))
        rice = math.ceil(plates / PLATES_PER_KG * 2) / 2
        batches = math.ceil(rice / 5)
        c = st.columns(4)
        c[0].metric("Forecast plates", plates)
        c[1].metric("Rice to cook", f"{rice} kg")
        c[2].metric("Chicken", f"{rice * 1.2:.1f} kg")
        c[3].metric("Dum batches (5 kg each)", batches)
        st.caption(f"Based on the average of the same weekday over the last 5 weeks, x{factor} for '{ev}', plus 5% buffer.")
        rows = [{"Item": n, "Needed": round(q * rice / (1000 if u == "g" else 1000), 2), "Unit": "kg" if u == "g" else "L",
                 "Cost Rs": round(q / 1000 * p * rice)} for n, (q, u, p) in RECIPE.items()]
        st.subheader("Shopping list")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.metric("Estimated ingredient cost", f"Rs {sum(r['Cost Rs'] for r in rows):,}")
        for n, need in [("Rice", rice), ("Chicken", rice * 1.2)]:
            have = stock_qty(n)
            (st.error if have < need else st.success)(
                f"{n}: need {need:.1f} kg, have {have:.1f} kg" + (f". BUY {need - have:.1f} kg more." if have < need else ". Enough."))

elif page == "💰 Sales & Waste":
    st.title("💰 Sales & Waste")
    a, b = st.columns(2)
    with a.form("sale"):
        st.subheader("Log sales")
        d = st.date_input("Date", dt.date.today(), key="sd")
        ch = st.selectbox("Channel", list(CHANNELS))
        n = st.number_input("Plates", 0, 500, 20)
        r = st.number_input("Revenue (Rs)", 0, 100000, 4400, 50)
        if st.form_submit_button("Save sales"):
            add("sales", [d.isoformat(), ch, n, r]); st.success("Saved")
    with b.form("waste"):
        st.subheader("Log waste")
        d = st.date_input("Date", dt.date.today(), key="wd")
        n = st.number_input("Plates wasted", 0, 200, 3)
        why = st.selectbox("Reason", ["Unsold", "Spoiled", "Spillage", "Wrong order", "Other"])
        if st.form_submit_button("Save waste"):
            add("waste", [d.isoformat(), n, why]); st.success("Saved")
    s = load("sales")
    if len(s):
        g = s.groupby("channel")[["plates", "revenue"]].sum()
        g["commission %"] = [CHANNELS.get(c, 0) * 100 for c in g.index]
        g["net revenue"] = g["revenue"] * (1 - g["commission %"] / 100)
        st.subheader("Which channel really earns?")
        st.dataframe(g.round(0), use_container_width=True)
        st.bar_chart(g["net revenue"])
        best = g["net revenue"].idxmax()
        st.info(f"Highest net earner: {best}. Delivery apps keep {int(CHANNELS['Swiggy'] * 100)}%, so push WhatsApp and dine-in offers.")
    w = load("waste")
    if len(w):
        st.subheader("Why we waste food")
        st.bar_chart(w.groupby("reason")["plates"].sum())

elif page == "🍚 Kitchen Lab":
    st.title("🍚 Kitchen Lab")
    t1, t2, t3, t4 = st.tabs(["Recipe scaler", "Log a batch", "Golden settings finder", "AI fixer"])
    with t1:
        kg = st.number_input("Rice batch (kg)", 1.0, 50.0, 5.0, 0.5)
        st.dataframe(pd.DataFrame([{"Ingredient": n, "Amount": round(q * kg), "Unit": u} for n, (q, u, _) in RECIPE.items()]),
                     use_container_width=True, hide_index=True)
        for i, s in enumerate(STEPS, 1): st.write(f"{i}. {s}")
    with t2.form("batch"):
        c = st.columns(4)
        kg2 = c[0].number_input("Rice kg", 1.0, 50.0, 5.0, 0.5)
        boil = c[1].number_input("Boil min", 1, 30, 7)
        dum = c[2].number_input("Dum min", 5, 60, 24)
        taste = c[3].slider("Taste", 1.0, 5.0, 4.0, 0.5)
        prob = st.selectbox("Problem", ["None", "Rice too soft", "Rice undercooked", "Too dry", "Too spicy", "Bland", "Burnt bottom", "Other"])
        note = st.text_input("Notes")
        if st.form_submit_button("Save batch"):
            add("batches", [dt.date.today().isoformat(), kg2, boil, dum, taste, prob, note]); st.success("Saved")
    with t3:
        b = load("batches")
        if len(b) < 6:
            st.info("Log at least 6 batches (or load demo data) and the app will find your best settings.")
        else:
            b["taste"] = pd.to_numeric(b["taste"])
            top = b[b["taste"] >= b["taste"].quantile(0.75)]
            st.success(f"Your best batches (taste {top['taste'].mean():.1f}/5) used: rice boil {top['boil_min'].mean():.1f} min, "
                       f"dum {top['dum_min'].mean():.0f} min. Dum range: {top['dum_min'].min()} to {top['dum_min'].max()} min.")
            b["dum band"] = pd.cut(pd.to_numeric(b["dum_min"]), [0, 18, 22, 26, 60], labels=["<18", "18-22", "22-26", ">26"])
            st.bar_chart(b.groupby("dum band", observed=True)["taste"].mean())
            st.line_chart(b.set_index("date")["taste"])
            st.caption("Lock these settings into your written recipe and train the team on them.")
    with t4:
        issue = st.text_area("What went wrong? (taste, texture, timing, smell)")
        if st.button("Get fix") and issue.strip():
            with st.spinner("Thinking..."):
                st.markdown(ai(snapshot() + "\n\nProblem: " + issue + "\nGive: likely cause, fix for this batch, one change for next batch."))

elif page == "📦 Stock":
    st.title("📦 Stock")
    st.caption("Edit the table directly, add rows at the bottom, then press Save.")
    ed = st.data_editor(load("stock"), num_rows="dynamic", use_container_width=True)
    if st.button("Save stock"):
        save("stock", ed); st.success("Saved")
    k = ed.copy()
    k["qty"], k["reorder_at"] = pd.to_numeric(k["qty"], errors="coerce"), pd.to_numeric(k["reorder_at"], errors="coerce")
    for _, r in k[k["qty"] <= k["reorder_at"]].iterrows():
        st.warning(f"Reorder {r['item']}: only {r['qty']} {r['unit']} left")
    low = k[k["qty"] <= k["reorder_at"]]
    if len(low) and st.button("Draft supplier WhatsApp message"):
        st.code(ai("Write a short polite WhatsApp message in simple English to my supplier ordering these low items: "
                   + low.to_string(index=False) + ". Ask for today's rate and delivery time."))

elif page == "⭐ Review Agent":
    st.title("⭐ Review Agent")
    st.caption("Paste customer reviews from Zomato, Swiggy or Google. The agent finds patterns and drafts replies.")
    txt = st.text_area("Paste reviews (one per line)", height=200)
    if st.button("Analyze") and txt.strip():
        with st.spinner("Reading reviews..."):
            st.markdown(ai("Analyze these restaurant reviews:\n" + txt + "\n\nGive: 1) overall sentiment, 2) top 3 complaints, "
                           "3) top 3 praises, 4) 3 concrete kitchen/service fixes, 5) a polite short reply for each review."))

elif page == "💬 Ask Your Manager":
    st.title("💬 Ask Your Manager")
    st.caption("Your AI manager has read your sales, waste, stock and batch data. Ask anything.")
    st.session_state.setdefault("chat", [])
    for m in st.session_state.chat:
        st.chat_message(m["role"]).write(m["content"])
    q = st.chat_input("e.g. Why is my profit low? What should I cook for Saturday?")
    if q:
        st.session_state.chat.append({"role": "user", "content": q})
        st.chat_message("user").write(q)
        hist = "\n".join(f"{m['role']}: {m['content']}" for m in st.session_state.chat[-6:])
        with st.spinner("Thinking..."):
            ans = ai(hist, SYS + "\n\nBUSINESS DATA:\n" + snapshot())
        st.session_state.chat.append({"role": "assistant", "content": ans})
        st.chat_message("assistant").write(ans)

elif page == "✅ Checklists":
    st.title("✅ Daily Checklists")
    today = dt.date.today().isoformat()
    for name, items in CHECKLISTS.items():
        st.subheader(name)
        done = sum(st.checkbox(it, key=f"{today}_{name}_{i}") for i, it in enumerate(items))
        st.progress(done / len(items), text=f"{done}/{len(items)} done")
    
