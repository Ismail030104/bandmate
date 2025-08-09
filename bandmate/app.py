import os, io, json, zipfile, csv, datetime, tempfile
from flask import Flask, render_template, request, redirect, url_for, send_file, session
from utils import ocr_images_to_text, detect_task_type, generate_feedback, build_docx, build_pdf, weighted_overall

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY","change-me")

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/process")
def process():
    files = request.files.getlist("images")
    if not files or files[0].filename == "":
        return redirect(url_for("index"))
    task_type = request.form.get("task_type","auto")
    student_name = request.form.get("student_name","")
    teacher_notes = request.form.get("teacher_notes","")
    weights = {
        "w_task": float(request.form.get("w_task", 1.0)),
        "w_coh": float(request.form.get("w_coh", 1.0)),
        "w_lex": float(request.form.get("w_lex", 1.0)),
        "w_gra": float(request.form.get("w_gra", 1.0)),
    }
    extracted = ocr_images_to_text(files)
    if task_type == "auto":
        task_type = detect_task_type(extracted)
    session["pre"] = {"task_type":task_type,"student_name":student_name,"teacher_notes":teacher_notes, **weights}
    return render_template("result.html",
                           extracted_text=extracted,
                           task_type=task_type,
                           student_name=student_name,
                           teacher_notes=teacher_notes,
                           feedback=None,
                           weights=weights)

@app.post("/analyze")
def analyze():
    extracted_text = request.form.get("extracted_text","").strip()
    task_type = request.form.get("task_type","Task 2")
    student_name = request.form.get("student_name","")
    teacher_notes = request.form.get("teacher_notes","")
    weights = {
        "w_task": float(request.form.get("w_task", 1.0)),
        "w_coh": float(request.form.get("w_coh", 1.0)),
        "w_lex": float(request.form.get("w_lex", 1.0)),
        "w_gra": float(request.form.get("w_gra", 1.0)),
    }
    fb = generate_feedback(extracted_text, task_type, teacher_notes)
    fb["bands"]["overall"] = weighted_overall(fb["bands"], **weights)
    session["last_feedback"] = fb; session["last_weights"] = weights
    return render_template("result.html",
                           extracted_text=extracted_text,
                           task_type=task_type,
                           student_name=student_name,
                           teacher_notes=teacher_notes,
                           feedback=fb,
                           weights=weights)

@app.post("/download_docx")
def download_docx():
    student_name = request.form.get("student_name","")
    task_type = request.form.get("task_type","Task 2")
    extracted_text = request.form.get("extracted_text","")
    feedback = json.loads(request.form.get("feedback"))
    data = build_docx(student_name, task_type, extracted_text, feedback)
    filename = f"{student_name or 'IELTS'}_{task_type}_feedback.docx".replace(" ","_")
    return send_file(io.BytesIO(data), as_attachment=True,
                     download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.post("/download_pdf")
def download_pdf():
    student_name = request.form.get("student_name","")
    task_type = request.form.get("task_type","Task 2")
    extracted_text = request.form.get("extracted_text","")
    feedback = json.loads(request.form.get("feedback"))
    data = build_pdf(student_name, task_type, extracted_text, feedback)
    filename = f"{student_name or 'IELTS'}_{task_type}_feedback.pdf".replace(" ","_")
    return send_file(io.BytesIO(data), as_attachment=True,
                     download_name=filename,
                     mimetype="application/pdf")

ALLOWED_IMG = {".png",".jpg",".jpeg",".webp"}

@app.post("/batch")
def batch():
    zf = request.files.get("zipfile")
    task_type = request.form.get("task_type","Task 2")
    teacher_notes = request.form.get("teacher_notes","")
    if not zf or not zf.filename.lower().endswith(".zip"):
        return redirect(url_for("index"))

    tmpdir = tempfile.mkdtemp(prefix="bandmate_batch_")
    zip_path = os.path.join(tmpdir, "in.zip"); zf.save(zip_path)
    with zipfile.ZipFile(zip_path) as z: z.extractall(tmpdir)

    summary_rows = [["Student","Task","Words","Task","Coherence","Lexical","Grammar","Overall"]]
    out_zip_bio = io.BytesIO()
    with zipfile.ZipFile(out_zip_bio, "w", zipfile.ZIP_DEFLATED) as zout:
        for root, dirs, files in os.walk(tmpdir):
            if root == tmpdir:
                for d in dirs:
                    student_dir = os.path.join(root, d)
                    images = []
                    for f in sorted(os.listdir(student_dir)):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ALLOWED_IMG:
                            images.append(open(os.path.join(student_dir, f), "rb"))
                    if not images: continue
                    from types import SimpleNamespace
                    fs_list = [SimpleNamespace(stream=img) for img in images]
                    text = ocr_images_to_text(fs_list)
                    fb = generate_feedback(text, task_type, teacher_notes)
                    docx_bytes = build_docx(d, task_type, text, fb)
                    pdf_bytes = build_pdf(d, task_type, text, fb)
                    zout.writestr(f"{d}/{d}_{task_type}_feedback.docx", docx_bytes)
                    zout.writestr(f"{d}/{task_type}_{d}_feedback.pdf", pdf_bytes)
                    words = len(text.split()); b = fb["bands"]
                    summary_rows.append([d, task_type, words, b["task"], b["coherence"], b["lexical"], b["grammar"], b["overall"]])
        import csv
        csv_io = io.StringIO(); cw = csv.writer(csv_io); cw.writerows(summary_rows)
        zout.writestr("SUMMARY.csv", csv_io.getvalue().encode("utf-8"))

    out_zip_bio.seek(0); dt = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(out_zip_bio, as_attachment=True,
                     download_name=f"bandmate_batch_results_{dt}.zip",
                     mimetype="application/zip")

if __name__ == "__main__":
    app.run(debug=True)
