import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# -------------------- PDF Generator -------------------- #
def generate_pdf(summary, output_dir, basename):
    out = Path(output_dir)
    pdf_path = out.joinpath(f"{basename}.pdf")
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("BloomWatch Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Input file: {summary.get('input_file','-')}", styles["Normal"]))
    story.append(Paragraph(f"Rows (original): {summary.get('rows_original','-')}", styles["Normal"]))
    story.append(Paragraph(f"Rows (cleaned): {summary.get('rows_cleaned','-')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    if summary.get("metrics"):
        metrics = summary["metrics"]
        if "accuracy" in metrics:
            story.append(Paragraph(f"Model accuracy: {metrics['accuracy']:.3f}", styles["Normal"]))
        story.append(Spacer(1, 12))

    for name in summary.get("out_files", []):
        img_path = out.joinpath(name)
        if img_path.exists() and img_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            try:
                story.append(Image(str(img_path), width=450, height=250))
                story.append(Spacer(1, 12))
            except Exception:
                continue

    doc.build(story)
    return pdf_path


# -------------------- Manual Relation Analysis -------------------- #
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

        if dfs:
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
            return str(combined_plot.name)
    except Exception as e:
        return f"Error: {e}"


# -------------------- Automatic Suggestions -------------------- #
def auto_relation_suggestions():
    """Automatically suggest top correlations"""
    dfs = []
    for file in os.listdir(UPLOAD_FOLDER):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(UPLOAD_FOLDER, file), low_memory=False, on_bad_lines="skip")
            dfs.append(df)

    if not dfs:
        return []

    df_all = pd.concat(dfs, ignore_index=True)
    df_num = df_all.select_dtypes(include="number")

    if df_num.empty:
        return []

    corrs = df_num.corr().abs().unstack().sort_values(ascending=False)
    suggestions = []
    for (c1, c2), val in corrs.items():
        if c1 != c2 and val > 0.6:  # only strong correlations
            suggestions.append(f"{c1} vs {c2} (corr={val:.2f})")

    return list(set(suggestions[:5]))
