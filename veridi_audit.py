"""
Veridi Logistics - Last Mile Delivery Audit  (single-file version for VS Code)

Run:  python veridi_audit.py          (plain script)
  or  open in VS Code and click "Run Cell" on each "# %%" block (Jupyter extension, Interactive Window)

Put these 6 CSVs in the SAME folder as this file (relative paths, no C:/ paths):
  olist_orders_dataset.csv, olist_order_reviews_dataset.csv, olist_customers_dataset.csv,
  olist_products_dataset.csv, olist_order_items_dataset.csv, product_category_name_translation.csv

Install:  pip install pandas numpy matplotlib seaborn streamlit plotly
Outputs:  charts/*.png, dashboard_orders.csv, state_summary.csv, category_summary.csv
"""

# %% [markdown]
# # Veridi Logistics: Last Mile Delivery Audit
# **Question:** Are we failing specific regions, or is this nationwide? Are our delivery estimates wrong?
# 
# **How to run (Colab):** Runtime > Run all. When prompted, upload the 6 Olist CSVs (or place them in the notebook folder). Paths are relative, nothing is hard-coded.

# %%
import os, numpy as np, pandas as pd
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid")
pd.set_option("display.float_format", "{:.2f}".format)
os.makedirs("charts", exist_ok=True)

FILES = ["olist_orders_dataset.csv","olist_order_reviews_dataset.csv","olist_customers_dataset.csv",
         "olist_products_dataset.csv","olist_order_items_dataset.csv","product_category_name_translation.csv"]
missing = [f for f in FILES if not os.path.exists(f)]
if missing:
    raise FileNotFoundError(f"Put these files next to this script: {missing}")

# %% [markdown]
# ## Story 1: Schema Builder (load + joins, no duplicated rows)

# %%
date_cols = ["order_purchase_timestamp","order_approved_at","order_delivered_carrier_date",
             "order_delivered_customer_date","order_estimated_delivery_date"]
orders    = pd.read_csv("olist_orders_dataset.csv", parse_dates=date_cols)
reviews   = pd.read_csv("olist_order_reviews_dataset.csv")
customers = pd.read_csv("olist_customers_dataset.csv")
products  = pd.read_csv("olist_products_dataset.csv")
items     = pd.read_csv("olist_order_items_dataset.csv")
trans     = pd.read_csv("product_category_name_translation.csv")

for n,d in [("orders",orders),("reviews",reviews),("customers",customers),("products",products),("items",items)]:
    print(f"{n:10s} rows={len(d):>7,}")

# --- Duplicate-risk checks (1-to-many traps) ---
print("\nOrders with >1 review:", (reviews.groupby("order_id").size() > 1).sum())
print("customer_id unique in customers:", customers.customer_id.is_unique)

# %%
# Reviews: some orders have several reviews -> collapse to ONE row per order (mean score) BEFORE joining
rev_1 = reviews.groupby("order_id", as_index=False).agg(review_score=("review_score","mean"),
                                                       n_reviews=("review_id","count"))

# Category: an order can hold many items -> keep the category of the first item (order_item_id == 1)
first_item = (items[items.order_item_id == 1][["order_id","product_id"]]
              .merge(products[["product_id","product_category_name"]], on="product_id", how="left")
              .merge(trans, on="product_category_name", how="left"))
first_item["category_en"] = first_item["product_category_name_english"].fillna("unknown")
first_item = first_item[["order_id","category_en"]]

master = (orders
  .merge(customers[["customer_id","customer_unique_id","customer_city","customer_state"]],
         on="customer_id", how="left", validate="many_to_one")
  .merge(rev_1,      on="order_id", how="left", validate="one_to_one")
  .merge(first_item, on="order_id", how="left", validate="one_to_one"))

assert len(master) == len(orders) and master.order_id.is_unique, "Join duplicated rows!"
print("Master rows:", len(master), "== orders:", len(orders), "OK, no duplicates")
print(master.head())

# %% [markdown]
# ## Story 2: The "Real" Delay Calculator
# `Days_Difference = estimated - actual`. **Positive = early, negative = late.**
# - On Time: delivered on/before estimate
# - Late: 0 to 5 days after estimate
# - Super Late: more than 5 days after estimate
# 
# Orders that were never delivered (canceled, unavailable, shipped, etc.) have no delivery date, so they are flagged and excluded from delay analysis.

# %%
master["Days_Difference"] = (master.order_estimated_delivery_date - master.order_delivered_customer_date).dt.total_seconds()/86400

def classify(d):
    if pd.isna(d): return np.nan
    if d >= 0:     return "On Time"
    if d >= -5:    return "Late"
    return "Super Late"
master["delivery_status"] = master.Days_Difference.map(classify)

master["exclusion_reason"] = np.where(master.order_status.ne("delivered"), "not delivered: " + master.order_status,
                              np.where(master.order_delivered_customer_date.isna(), "delivered but no date", ""))
print(master.exclusion_reason.replace("", "kept").value_counts())

df = master[master.exclusion_reason == ""].copy()
df["is_late"]  = df.delivery_status.ne("On Time")
df["promised_days"] = (df.order_estimated_delivery_date - df.order_purchase_timestamp).dt.total_seconds()/86400
df["actual_days"]   = (df.order_delivered_customer_date - df.order_purchase_timestamp).dt.total_seconds()/86400
print(f"\nAnalysed orders: {len(df):,}")
print(df.delivery_status.value_counts(normalize=True).mul(100).round(1).astype(str) + "%")

# %% [markdown]
# ## Story 3: Geographic view (late % by state) + remoteness

# %%
state = (df.groupby("customer_state")
           .agg(orders=("order_id","count"), late_pct=("is_late","mean"),
                super_late_pct=("delivery_status", lambda s: (s=="Super Late").mean()),
                avg_score=("review_score","mean"), median_delay_days=("Days_Difference","median"))
           .reset_index())
state[["late_pct","super_late_pct"]] *= 100
state = state.sort_values("late_pct", ascending=False)
national = df.is_late.mean()*100
print(f"National late rate: {national:.1f}%")
NE = ["AL","BA","CE","MA","PB","PE","PI","RN","SE"]
print(f"Northeast late rate: {df[df.customer_state.isin(NE)].is_late.mean()*100:.1f}% | rest of Brazil: {df[~df.customer_state.isin(NE)].is_late.mean()*100:.1f}%")

plt.figure(figsize=(11,6))
sns.barplot(data=state, x="customer_state", y="late_pct", color="#d1495b", label="Late (any)")
sns.barplot(data=state, x="customer_state", y="super_late_pct", color="#6b0f1a", label="Super Late (>5d)")
plt.axhline(national, ls="--", c="k", lw=1); plt.text(len(state)-1, national+0.4, f"National {national:.1f}%", ha="right")
plt.title("% of late deliveries by customer state"); plt.ylabel("% of delivered orders"); plt.xlabel("State")
plt.legend(); plt.tight_layout(); plt.savefig("charts/chart_01.png", dpi=150, bbox_inches="tight"); plt.show()
print(state.head(10))

# %%
# Remoteness: distance from Sao Paulo (assumed main distribution hub; most sellers are there) using state-capital coordinates
cap = {"SP":(-23.55,-46.63),"RJ":(-22.91,-43.17),"MG":(-19.92,-43.94),"ES":(-20.32,-40.34),"PR":(-25.43,-49.27),
"SC":(-27.59,-48.55),"RS":(-30.03,-51.23),"MS":(-20.44,-54.65),"MT":(-15.60,-56.10),"GO":(-16.68,-49.25),
"DF":(-15.78,-47.93),"BA":(-12.97,-38.51),"SE":(-10.91,-37.07),"AL":(-9.67,-35.74),"PE":(-8.05,-34.88),
"PB":(-7.12,-34.86),"RN":(-5.79,-35.21),"CE":(-3.73,-38.53),"PI":(-5.09,-42.80),"MA":(-2.53,-44.30),
"PA":(-1.46,-48.50),"AP":0.03,"AM":(-3.12,-60.02),"RR":(2.82,-60.67),"AC":(-9.97,-67.81),"RO":(-8.76,-63.90),"TO":(-10.18,-48.33)}
cap["AP"] = (0.03,-51.07)
def hav(a,b):
    la1,lo1,la2,lo2 = map(np.radians,[*a,*b]); h = np.sin((la2-la1)/2)**2+np.cos(la1)*np.cos(la2)*np.sin((lo2-lo1)/2)**2
    return 6371*2*np.arcsin(np.sqrt(h))
state["km_from_SP"] = state.customer_state.map(lambda s: hav(cap["SP"], cap[s]))
r = state[["km_from_SP","late_pct"]].corr().iloc[0,1]

plt.figure(figsize=(9,6))
sns.regplot(data=state, x="km_from_SP", y="late_pct", scatter_kws={"s":state.orders/state.orders.max()*600+30}, color="#d1495b")
for _,row in state.iterrows(): plt.annotate(row.customer_state,(row.km_from_SP,row.late_pct),xytext=(4,4),textcoords="offset points",fontsize=8)
print(f"Correlation late % vs km from SP: r = {r:.2f}")
plt.title(f"Distance from Sao Paulo vs late % (r = {r:.2f}; bubble = order volume)")
plt.xlabel("km from Sao Paulo"); plt.ylabel("% late"); plt.tight_layout(); plt.savefig("charts/chart_02.png", dpi=150, bbox_inches="tight"); plt.show()

# %% [markdown]
# ## Story 4: Sentiment correlation (late delivery -> low reviews)

# %%
rv = df.dropna(subset=["review_score"])
by_status = rv.groupby("delivery_status").review_score.agg(["mean","count"]).reindex(["On Time","Late","Super Late"])
print(by_status)

fig,ax = plt.subplots(1,2,figsize=(14,5))
sns.barplot(x=by_status.index, y=by_status["mean"], hue=by_status.index, palette=["#2a9d8f","#e9c46a","#d1495b"], legend=False, ax=ax[0])
for i,v in enumerate(by_status["mean"]): ax[0].text(i, v+0.05, f"{v:.2f}", ha="center")
ax[0].set_ylim(0,5); ax[0].set_title("Avg review score by delivery status"); ax[0].set_ylabel("Avg score (1-5)")

b = rv.assign(delay_bucket=(-rv.Days_Difference).clip(-15,20).round())   # + = days late
curve = b.groupby("delay_bucket").review_score.mean()
ax[1].plot(curve.index, curve.values, marker="o", color="#264653"); ax[1].axvline(0, ls="--", c="grey")
ax[1].set_title("Avg review score vs days late (negative = early)"); ax[1].set_xlabel("Days late (clipped -15..20)"); ax[1].set_ylabel("Avg score")
plt.tight_layout(); plt.savefig("charts/chart_03.png", dpi=150, bbox_inches="tight"); plt.show()

print("Correlation (days late vs score):", round((-rv.Days_Difference).corr(rv.review_score),3))

# %% [markdown]
# ## Bonus: Product categories in English

# %%
cat = (df[df.category_en!="unknown"].groupby("category_en")
         .agg(orders=("order_id","count"), late_pct=("is_late","mean"), avg_score=("review_score","mean"),
              avg_actual_days=("actual_days","mean")).reset_index())
cat["late_pct"] *= 100
cat = cat[cat.orders >= 200].sort_values("late_pct", ascending=False)   # ignore tiny categories
plt.figure(figsize=(10,6)); sns.barplot(data=cat.head(15), y="category_en", x="late_pct", color="#d1495b")
plt.title("Top 15 categories by % late (min 200 orders)"); plt.xlabel("% late"); plt.ylabel(""); plt.tight_layout(); plt.savefig("charts/chart_04.png", dpi=150, bbox_inches="tight"); plt.show()
print(cat.head(10))

# %% [markdown]
# ## Candidate's Choice: Promise Accuracy Gap
# **Why it matters:** the CEO suspects we *over-promise*. Comparing the delivery time we promise with what actually happens per state, and computing the estimate that would have been safe, turns "we are late" into an actionable fix: recalibrate the estimate for the worst states. It also shows whether the problem is slow shipping or bad estimating.

# %%
gap = (df.groupby("customer_state")
         .agg(orders=("order_id","count"), promised_median=("promised_days","median"),
              actual_median=("actual_days","median"), actual_p90=("actual_days",lambda s: s.quantile(.9)))
         .reset_index())
gap["recommended_promise_days"] = np.ceil(gap.actual_p90)          # 90% of orders would arrive within this
gap["padding_needed_days"] = (gap.recommended_promise_days - gap.promised_median).clip(lower=0)   # only ever EXTEND a promise
gap = gap.merge(state[["customer_state","late_pct"]], on="customer_state").sort_values("late_pct", ascending=False)

x = np.arange(len(gap)); w = .38
plt.figure(figsize=(12,5))
plt.bar(x-w/2, gap.promised_median, w, label="Promised (median days)", color="#457b9d")
plt.bar(x+w/2, gap.actual_median,   w, label="Actual (median days)",   color="#e76f51")
plt.plot(x, gap.recommended_promise_days, "k^", label="Recommended promise (P90 actual)")
plt.xticks(x, gap.customer_state); plt.title("Promised vs actual delivery time by state (sorted by late %)")
plt.ylabel("Days from purchase"); plt.legend(); plt.tight_layout(); plt.savefig("charts/chart_05.png", dpi=150, bbox_inches="tight"); plt.show()

# What-if: extend the promise ONLY where it is too tight (never shorten a generous one)
p = df.merge(gap[["customer_state","recommended_promise_days"]], on="customer_state")
p["new_promise_days"] = np.maximum(p.promised_days, p.recommended_promise_days)
late_now, late_new = p.is_late.mean()*100, (p.actual_days > p.new_promise_days).mean()*100
print(f"Late rate today: {late_now:.1f}%  ->  with state-level padded promise: {late_new:.1f}%")
print(f"National median promised: {df.promised_days.median():.1f} d | median actual: {df.actual_days.median():.1f} d")
print("States needing extra padding:", (gap.padding_needed_days > 0).sum(), "of", len(gap))
print(gap)

# %% [markdown]
# ## Export data for the dashboard

# %%
df_out = df[["order_id","customer_state","category_en","order_purchase_timestamp","promised_days","actual_days",
             "Days_Difference","delivery_status","review_score"]]
df_out.to_csv("dashboard_orders.csv", index=False)
state.merge(gap[["customer_state","promised_median","actual_median","recommended_promise_days","padding_needed_days"]], on="customer_state").to_csv("state_summary.csv", index=False)
cat.to_csv("category_summary.csv", index=False)
print("Saved dashboard_orders.csv, state_summary.csv, category_summary.csv")

# %% [markdown]
# ## Key findings (fill in after running)
# 1. National late rate: ___% (Super Late ___%)
# 2. Worst states: ___ ; correlation of late % with distance from SP: r = ___
# 3. Avg score: On Time ___ vs Late ___ vs Super Late ___
# 4. Promise gap: median promised ___ d vs actual ___ d; a state-level P90 promise cuts late orders from ___% to ___%
