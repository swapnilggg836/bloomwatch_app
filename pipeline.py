# ---------------- pipeline.py ----------------
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Server-side backend
import matplotlib.pyplot as plt
import seaborn as sns
import os, json
from pathlib import Path
from utils import generate_pdf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib, warnings
from models import db, AnalysisHistory

warnings.filterwarnings("ignore")
sns.set(style="whitegrid")

COLS = {
    "lat": "Observation Latitude",
    "lon": "Observation Longitude",
    "date": "Measurement Date (UTC)",
    "time": "Measurement Time (UTC)",
    "total_cloud_pct": "Total Cloud Cover %",
    "surface_temp": "Surface Air Temperature",
    "surface_rh": "Surface Relative Humidity %"
}

def safe_basename(path):
    return Path(path).stem

def run_pipeline(csv_path, output_dir, save_db=True):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    basename = safe_basename(csv_path)
    safe_name = basename.replace(" ", "_")
    summary = {"input_file": os.path.basename(csv_path)}

    # ---------------- Load CSV ----------------
    try:
        df = pd.read_csv(csv_path, low_memory=False, quotechar='"', on_bad_lines='skip')
    except Exception:
        df = pd.read_csv(csv_path, low_memory=False, engine="python", on_bad_lines='skip')

    summary["rows_original"] = int(df.shape[0])
    summary["cols_original"] = int(df.shape[1])

    # ---------------- Clean ----------------
    if COLS["date"] in df.columns and COLS["time"] in df.columns:
        df["measurement_datetime"] = pd.to_datetime(
            df[COLS["date"]].astype(str) + " " + df[COLS["time"]].astype(str), errors="coerce"
        )
    elif COLS["date"] in df.columns:
        df["measurement_datetime"] = pd.to_datetime(df[COLS["date"]].astype(str), errors="coerce")
    else:
        df["measurement_datetime"] = pd.to_datetime(df.iloc[:,0].astype(str), errors="coerce")

    for col in [COLS["total_cloud_pct"], COLS["surface_temp"], COLS["surface_rh"]]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    req_cols = [c for c in [COLS["lat"], COLS["lon"], "measurement_datetime"] if c in df.columns]
    df = df.dropna(subset=req_cols)
    summary["rows_cleaned"] = int(df.shape[0])

    # ---------------- Create plots ----------------
    out_files = []

    # Daily aggregation plot
    if "measurement_datetime" in df.columns:
        df["date"] = df["measurement_datetime"].dt.date
        numeric_cols = [c for c in [COLS["total_cloud_pct"], COLS["surface_temp"]] if c in df.columns]
        if numeric_cols:
            daily = df.groupby("date")[numeric_cols].mean().reset_index()
            plt.figure(figsize=(10,5))
            for col in numeric_cols:
                plt.plot(daily["date"], daily[col], label=col)
            plt.title("Daily Averages")
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()
            daily_file = out_dir.joinpath(f"{safe_name}_daily.png")
            plt.savefig(str(daily_file), dpi=150)
            plt.close()
            out_files.append(daily_file.name)

    # Histograms
    for col, title in [(COLS["surface_temp"], "Surface Temp"), (COLS["total_cloud_pct"], "Cloud Cover")]:
        if col in df.columns:
            plt.figure(figsize=(6,4))
            sns.histplot(df[col].dropna(), kde=True, bins=30)
            plt.title(f"{title} Distribution")
            plt.tight_layout()
            hist_file = out_dir.joinpath(f"{safe_name}_hist_{col.split()[0]}.png")
            plt.savefig(str(hist_file), dpi=150)
            plt.close()
            out_files.append(hist_file.name)

    # Geo scatter
    try:
        if COLS["lat"] in df.columns and COLS["lon"] in df.columns:
            sample = df.dropna(subset=[COLS["lat"], COLS["lon"]]).sample(min(2000, len(df)), random_state=42)
            plt.figure(figsize=(8,4))
            plt.scatter(sample[COLS["lon"]], sample[COLS["lat"]], s=6, alpha=0.6)
            plt.title("Location Scatter")
            plt.tight_layout()
            geo_file = out_dir.joinpath(f"{safe_name}_geo.png")
            plt.savefig(str(geo_file), dpi=150)
            plt.close()
            out_files.append(geo_file.name)
    except Exception:
        pass

    # ---------------- Bloom classifier ----------------
    if "is_bloom" not in df.columns:
        if COLS["total_cloud_pct"] in df.columns and COLS["surface_temp"] in df.columns:
            df["is_bloom"] = ((df[COLS["total_cloud_pct"]] < 30) &
                              (df[COLS["surface_temp"]].between(10,35))).astype(int)
        else:
            df["is_bloom"] = 0

    model_file = out_dir.joinpath(f"{safe_name}_model.pkl")
    metrics = {}
    try:
        X_cols = [c for c in [COLS["total_cloud_pct"], COLS["surface_temp"]] if c in df.columns]
        if len(X_cols) >= 1 and df["is_bloom"].nunique() > 1:
            X = df[X_cols].fillna(0)
            y = df["is_bloom"].astype(int)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            clf = RandomForestClassifier(n_estimators=100, random_state=42)
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            metrics["accuracy"] = float(accuracy_score(y_test, y_pred))
            metrics["report"] = classification_report(y_test, y_pred, digits=3, output_dict=True)
            joblib.dump(clf, str(model_file))
            out_files.append(model_file.name)
    except Exception as e:
        metrics["train_error"] = str(e)

    # ---------------- Summary ----------------
    summary.update({
        "out_files": out_files,
        "metrics": metrics
    })

    summary_file = out_dir.joinpath(f"{safe_name}_summary.json")
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---------------- Generate PDF ----------------
    pdf_path = generate_pdf(summary, out_dir, safe_name)
    summary["pdf_path"] = os.path.basename(pdf_path)
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---------------- Save to DB ----------------
    if save_db:
        try:
            record = AnalysisHistory(
                input_file=summary["input_file"],
                pdf_path=summary["pdf_path"],
                metrics=json.dumps(metrics)
            )
            db.session.add(record)
            db.session.commit()
        except Exception as e:
            print("DB save error:", e)

    return summary
