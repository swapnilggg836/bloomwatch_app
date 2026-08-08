import os
import shutil
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import json

from pipeline import run_pipeline
from models import db, AnalysisHistory

# ---------------- Flask setup ----------------
app = Flask(__name__, static_folder=None)  # Disable default static handler to use custom fallback handler below
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "bloomwatch-secret-key-12345")

is_vercel = os.environ.get("VERCEL") is not None
if is_vercel:
    base_dir = "/tmp"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:////tmp/analysis.db")
else:
    base_dir = "."
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///analysis.db")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

UPLOAD_FOLDER = os.path.join(base_dir, "uploads")
OUTPUT_FOLDER = os.path.join(base_dir, "outputs")
STATIC_FOLDER = os.path.join(base_dir, "static") if is_vercel else "static"
ROOT_STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

with app.app_context():
    db.create_all()


# ---------------- Custom Static Handler ----------------
@app.route("/static/<path:filename>", endpoint="static")
def serve_custom_static(filename):

    # 1. Check in root project static folder (style.css, js/main.js, css/style.css, etc.)
    file_in_root = os.path.join(ROOT_STATIC_FOLDER, filename)
    if os.path.isfile(file_in_root):
        return send_file(file_in_root)

    # 2. Check in /tmp/static or local static folder (generated charts)
    file_in_static = os.path.join(STATIC_FOLDER, filename)
    if os.path.isfile(file_in_static):
        return send_file(file_in_static)

    # 3. Check in outputs folder
    file_in_outputs = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.isfile(file_in_outputs):
        return send_file(file_in_outputs)

    return "Static file not found", 404





# ---------------- Index / Upload ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        files = request.files.getlist("datafile")
        summaries = []

        for file in files:
            if file:
                filename = secure_filename(file.filename)
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(upload_path)

                # Run pipeline and get summary
                summary = run_pipeline(upload_path, OUTPUT_FOLDER)

                # Copy PNGs to static/ for display
                image_files = []
                for f in summary.get("out_files", []):
                    if f.endswith(".png"):
                        src = os.path.join(OUTPUT_FOLDER, f)
                        dst = os.path.join(STATIC_FOLDER, f)
                        shutil.copy(src, dst)
                        image_files.append(f)
                summary["image_files"] = image_files
                summaries.append(summary)

                # Save record in DB
                try:
                    record = AnalysisHistory(
                        input_file=summary.get("input_file", ""),
                        pdf_path=summary.get("pdf_path", ""),
                        metrics=json.dumps(summary.get("metrics", {}))
                    )
                    db.session.add(record)
                    db.session.commit()
                except Exception as e:
                    print("DB save error:", e)

        return render_template("results.html", summaries=summaries)

    return render_template("index.html")


# ---------------- Download PDF ----------------
@app.route("/download/<pdfname>")
def download(pdfname):
    pdf_path = os.path.join(OUTPUT_FOLDER, pdfname)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    return "PDF not found!", 404


# ---------------- Custom Analysis ----------------
@app.route("/custom_analysis", methods=["GET", "POST"])
def custom_analysis():
    result = None
    if request.method == "POST":
        relation = request.form.get("relation")
        if "vs" in relation:
            col1, col2 = [x.strip() for x in relation.split("vs")]
            result = analyze_relation(col1, col2)
    return render_template("custom_analysis.html", result=result)


# ---------------- History Dashboard ----------------
@app.route("/history")
def history():
    records = AnalysisHistory.query.order_by(AnalysisHistory.created_at.desc()).all()
    return render_template("history.html", records=records)


# ---------------- Suggestions Page ----------------
@app.route("/suggestions")
def suggestions():
    sample_suggestions = [
        "Reduce fertilizer usage by 10% based on last analysis.",
        "Irrigation is needed in Region X due to low soil moisture.",
        "Crop health risk detected: Possible nutrient deficiency.",
    ]
    return render_template("suggestions.html", suggestions=sample_suggestions)


# ---------------- Helper: Relation Analysis ----------------
def analyze_relation(col1, col2):
    out_dir = Path(OUTPUT_FOLDER)
    out_dir.mkdir(parents=True, exist_ok=True)
    combined_plot = out_dir.joinpath(f"{col1}_vs_{col2}.png")

    try:
        dfs = []
        for file in os.listdir(UPLOAD_FOLDER):
            if file.endswith(".csv"):
                df = pd.read_csv(os.path.join(UPLOAD_FOLDER, file), low_memory=False, on_bad_lines="skip")
                dfs.append(df)
        if not dfs:
            return "No CSV files found."

        df_all = pd.concat(dfs, ignore_index=True)
        df_all[col1] = pd.to_numeric(df_all[col1], errors="coerce")
        df_all[col2] = pd.to_numeric(df_all[col2], errors="coerce")
        df_all = df_all.dropna(subset=[col1, col2])

        plt.figure(figsize=(8, 5))
        plt.scatter(df_all[col1], df_all[col2], alpha=0.6)
        plt.xlabel(col1)
        plt.ylabel(col2)
        plt.title(f"{col1} vs {col2}")
        plt.tight_layout()
        plt.savefig(str(combined_plot), dpi=150)
        plt.close()

        shutil.copy(str(combined_plot), os.path.join(STATIC_FOLDER, combined_plot.name))
        return combined_plot.name

    except Exception as e:
        return f"Error: {e}"


# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
