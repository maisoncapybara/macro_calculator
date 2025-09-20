# app.py
# Streamlit Macro Calculator (with Presets + Macro Styles)
import math
import json
import streamlit as st

# ----------------------------
# Helper math
# ----------------------------
def round_n(n, d=0):
    f = 10 ** d
    return round((n + 1e-12) * f) / f

# Unit transforms
def lb_to_kg(lb): return lb * 0.45359237
def kg_to_lb(kg): return kg / 0.45359237
def cm_to_in(cm): return cm / 2.54
def in_to_cm(inch): return inch * 2.54

# Activity multipliers (common ACSM-style set)
ACTIVITY = {
    "Sedentary (1.2)": 1.2,
    "Light (1.375)": 1.375,
    "Moderate (1.55)": 1.55,
    "Very (1.725)": 1.725,
    "Athlete (1.9)": 1.9,
}

# BMR equations
def mifflin_st_jeor(sex, weight_kg, height_cm, age):
    # BMR = (10 × weight[kg]) + (6.25 × height[cm]) − (5 × age) + s; s=+5 male, -161 female
    s = 5 if sex == "Male" else -161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + s

def katch_mc_ardle(lean_mass_kg):
    # BMR = 370 + 21.6 × LBM[kg]
    return 370 + 21.6 * lean_mass_kg

# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title="Macro Calculator", page_icon="🧮", layout="centered")

st.title("🧮 Macro Calculator")
st.caption("BMR via **Katch–McArdle** (if body fat % is provided) or **Mifflin–St Jeor**, "
           "then TDEE × goal. Protein & fat by rules; carbs fill the rest.")

with st.sidebar:
    st.header("Inputs")

    units = st.radio("Units", ["Imperial (lb, ft/in)", "Metric (kg, cm)"], index=0)
    sex = st.selectbox("Sex", ["Male", "Female"], index=0)
    age = st.number_input("Age (years)", min_value=14, max_value=90, value=30, step=1)

    if units.startswith("Imperial"):
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            ft = st.number_input("Height (ft)", min_value=3, max_value=8, value=5, step=1)
        with col_h2:
            inch = st.number_input("Height (in)", min_value=0, max_value=11, value=10, step=1)
        weight_lb = st.number_input("Weight (lb)", min_value=60.0, max_value=600.0, value=170.0, step=0.5)
        height_cm = in_to_cm(ft * 12 + inch)
        weight_kg = lb_to_kg(weight_lb)
    else:
        height_cm = st.number_input("Height (cm)", min_value=120.0, max_value=230.0, value=178.0, step=0.5)
        weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=77.1, step=0.1)

    body_fat = st.number_input("Body Fat % (optional)", min_value=0.0, max_value=70.0, value=18.0, step=0.5, help="Enables Katch–McArdle if set")
    activity_label = st.selectbox("Activity", list(ACTIVITY.keys()), index=2)
    activity_mult = ACTIVITY[activity_label]

    st.divider()
    st.subheader("Goal & Rules (Base Values)")

    # Base controls (these are your manual values; presets/styles can override them for calculations)
    base_calorie_delta_pct = st.slider("Calorie change (cut - / bulk +)", min_value=-30, max_value=20, value=0, step=1)
    override_calories = st.number_input("Override calories (optional)", min_value=0, max_value=10000, value=0, step=25, help="If set (>0), replaces TDEE×goal")

    base_protein_per_lb = st.slider("Protein per lb (or per lb lean mass)", min_value=0.6, max_value=1.2, value=0.9, step=0.01)
    use_lean_mass = st.checkbox("Use lean mass for protein (if BF% provided)", value=True)
    base_fat_percent = st.slider("Fat % of calories", min_value=20, max_value=40, value=30, step=1)
    meals = st.number_input("Meals per day", min_value=1, max_value=8, value=3, step=1)

    st.divider()
    st.subheader("Presets & Styles")

    # --- Tweak #1: Goal Presets ---
    preset = st.selectbox(
        "Preset",
        ["Custom", "Cut (-20%)", "Recomp (0%)", "Lean Bulk (+10%)"],
        index=0,
        help="Quickly apply typical settings; you can still tweak anything."
    )

    # --- Tweak #2: Macro Style selector ---
    style = st.selectbox(
        "Macro style",
        ["Balanced (30% fat)", "Low-carb (35% fat)", "High-carb (25% fat)"],
        index=0
    )

# ----- Derived values from inputs -----
lean_mass_kg = None
if body_fat is not None and body_fat >= 0:
    bf = min(max(body_fat, 0.0), 70.0) / 100.0
    lean_mass_kg = weight_kg * (1 - bf)

# Choose BMR formula
if lean_mass_kg is not None and not math.isnan(lean_mass_kg):
    bmr = katch_mc_ardle(lean_mass_kg)
    bmr_method = "Katch–McArdle"
else:
    bmr = mifflin_st_jeor(sex, weight_kg, height_cm, age)
    bmr_method = "Mifflin–St Jeor"

tdee = bmr * activity_mult

# -----------------------------------
# Apply Preset & Style (non-destructive)
# We compute "calc_*" values based on the user's base settings, then layer preset/style overrides.
# -----------------------------------
calc_calorie_delta_pct = base_calorie_delta_pct
calc_protein_per_lb = base_protein_per_lb
calc_fat_percent = base_fat_percent

# Style sets fat% first
if style.startswith("Balanced"):
    calc_fat_percent = 30
elif style.startswith("Low-carb"):
    calc_fat_percent = 35
else:  # High-carb
    calc_fat_percent = 25

# Preset can also set delta & protein (and ensure fat% reasonable)
if preset != "Custom":
    if preset.startswith("Cut"):
        calc_calorie_delta_pct = -20
        calc_protein_per_lb = max(calc_protein_per_lb, 1.0)
        calc_fat_percent = max(calc_fat_percent, 25)
    elif preset.startswith("Recomp"):
        calc_calorie_delta_pct = 0
        calc_protein_per_lb = max(calc_protein_per_lb, 0.9)
        if calc_fat_percent < 25 or calc_fat_percent > 35:
            calc_fat_percent = 30
    elif preset.startswith("Lean Bulk"):
        calc_calorie_delta_pct = 10
        calc_protein_per_lb = max(calc_protein_per_lb, 0.8)
        if calc_fat_percent < 25 or calc_fat_percent > 35:
            calc_fat_percent = 30

# Target calories
if override_calories and override_calories > 0:
    target_cal = float(override_calories)
    goal_source = "Override"
else:
    target_cal = tdee * (1 + calc_calorie_delta_pct / 100.0)
    goal_source = "TDEE × goal"

# Macro math
if use_lean_mass and lean_mass_kg is not None:
    basis_lb = kg_to_lb(lean_mass_kg)
else:
    basis_lb = kg_to_lb(weight_kg)

grams_protein = basis_lb * calc_protein_per_lb
kcal_protein = grams_protein * 4.0

kcal_fat = target_cal * (calc_fat_percent / 100.0)
grams_fat = kcal_fat / 9.0

kcal_carb = max(target_cal - (kcal_protein + kcal_fat), 0.0)
grams_carb = kcal_carb / 4.0

pct_protein = (kcal_protein / target_cal) * 100.0 if target_cal > 0 else 0.0
pct_fat = (kcal_fat / target_cal) * 100.0 if target_cal > 0 else 0.0
pct_carb = (kcal_carb / target_cal) * 100.0 if target_cal > 0 else 0.0

# ----------------------------
# Output UI
# ----------------------------
st.subheader("Results")

c1, c2, c3 = st.columns(3)
c1.metric("BMR (kcal/day)", f"{round_n(bmr)}", help=bmr_method)
c2.metric("TDEE (kcal/day)", f"{round_n(tdee)}", help=f"Activity: {activity_label}")
delta_pct = ((target_cal - tdee) / tdee * 100.0) if tdee > 0 else 0.0
c3.metric("Target Calories", f"{round_n(target_cal)}", f"{round_n(delta_pct,1)}% vs TDEE")

st.markdown("### Applied Settings")
st.write({
    "Preset": preset,
    "Style": style,
    "Calorie change (%)": calc_calorie_delta_pct if goal_source != "Override" else f"(override) {calc_calorie_delta_pct}",
    "Protein (g/lb basis)": round_n(calc_protein_per_lb, 2),
    "Fat (% kcal)": calc_fat_percent,
    "Protein basis": "Lean mass" if (use_lean_mass and lean_mass_kg is not None) else "Body weight",
    "Goal source": goal_source,
})

st.markdown("### Macros per day")
st.dataframe(
    {
        "Macro": ["Protein", "Fat", "Carbs"],
        "Grams": [round_n(grams_protein), round_n(grams_fat), round_n(grams_carb)],
        "Calories": [round_n(kcal_protein), round_n(kcal_fat), round_n(kcal_carb)],
        "Percent": [round_n(pct_protein), round_n(pct_fat), round_n(pct_carb)],
    },
    use_container_width=True,
)

st.markdown(f"### Per Meal (×{meals})")
per_meal = {
    "Protein (g)": round_n(grams_protein / meals, 1) if meals else 0,
    "Fat (g)": round_n(grams_fat / meals, 1) if meals else 0,
    "Carbs (g)": round_n(grams_carb / meals, 1) if meals else 0,
}
st.write(per_meal)

# Notes
with st.expander("Notes"):
    st.write(
        "- Protein range of 0.6–1.2 g/lb (≈1.3–2.6 g/kg) of bodyweight or **lean mass** is commonly used.\n"
        "- Fat at ~20–40% of calories helps cover essential fatty acids.\n"
        "- Carbs fill remaining calories after protein & fat.\n"
        "- Activity multipliers estimate expenditure—adjust calories based on progress over 2–3 weeks."
    )

# Export plan button
export_payload = {
    "inputs": {
        "units": "imperial" if units.startswith("Imperial") else "metric",
        "sex": sex,
        "age": age,
        "height_cm": round_n(height_cm, 1),
        "weight_kg": round_n(weight_kg, 1),
        "bodyFatPct": body_fat,
        "activity": activity_label,
        "calorieDeltaPct_applied": calc_calorie_delta_pct,
        "overrideCalories": override_calories,
        "proteinPerLb_applied": calc_protein_per_lb,
        "useLeanMassForProtein": use_lean_mass,
        "fatPercent_applied": calc_fat_percent,
        "meals": meals,
        "preset": preset,
        "style": style,
    },
    "results": {
        "bmr": round_n(bmr),
        "tdee": round_n(tdee),
        "targetCalories": round_n(target_cal),
        "macros": {
            "protein": {"g": round_n(grams_protein), "kcal": round_n(kcal_protein), "pct": round_n(pct_protein)},
            "fat": {"g": round_n(grams_fat), "kcal": round_n(kcal_fat), "pct": round_n(pct_fat)},
            "carbs": {"g": round_n(grams_carb), "kcal": round_n(kcal_carb), "pct": round_n(pct_carb)},
        },
        "perMeal": {
            "protein_g": round_n(per_meal["Protein (g)"], 1),
            "fat_g": round_n(per_meal["Fat (g)"], 1),
            "carbs_g": round_n(per_meal["Carbs (g)"], 1),
        },
    },
}
st.download_button(
    "Download plan (JSON)",
    data=json.dumps(export_payload, indent=2),
    file_name="macro-plan.json",
    mime="application/json",
)