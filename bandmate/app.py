import os, io
from flask import Flask, render_template, request, redirect, url_for, send_file
from utils import ocr_images_to_text, detect_task_type, generate_feedback, build_docx, build_pdf, weighted_overall

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "bandmate-secret")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB per request

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/process")
def process():
    files = request.files.getlist("images")
    if not files or files[0].filename == "":
        # nothing selected
        return render_template("result.html",
                               error="No photo was selected. Please tap 'Take Photo / Upload'.")
    try:
        task_type = request.form.get("task_type", "auto")
        student_name = request.form.get("student_name", "").strip()
        teacher_notes = request.form.get("teacher_notes", "").strip()

        extracted = ocr_images_to_text(files)
        if task_type == "auto":
            task_type = detect_task_type(extracted)

        # initial page to let user inspect the OCR text
        return render_template("result.html",
                               extracted_text=extracted,
                               task_type=task_type,
                               student_name=student_name,
                               teacher_notes=teacher_notes,
                               feedback=None,
                               weights={"w_task":1.0,"w_coh":1.0,"w_lex":1.0,"w_gra":1.0})
    except Exception as e:
        return render_template("result.html", error=f"Failed to process image(s): {e}")

@app.post("/analyze")
def analyze():
    try:
        extracted_text = request.form.get("extracted_text","").strip()
        if not extracted_text:
            return render_template("result.html", error="No text to analyze.", feedback=None)

        task_type = request.form.get("task_type","Task 2")
        student_name = request.form.get("student_name","").strip()
        teacher_notes = request.form.get("teacher_notes","").strip()

        weights = {
            "w_task": float(request.form.get("w_task", 1.0)),
            "w_coh": float(request.form.get("w_coh", 1.0)),
            "w_lex": float(request.form.get("w_lex", 1.0)),
            "w_gra": float(request.form.get("w_gra", 1.0)),
        }

        fb = generate_feedback(extracted_text, task_type, teacher_notes)
        fb["bands"]["overall"] = weighted_overall(fb["bands"], **weights)

        return render_template("result.html",
                               extracted_text=extracted_text,
                               task_type=task_type,
                               student_name=student_name,
                               teacher_notes=teacher_notes,
                               feedback=fb,
                               weights=weights)
    except Exception as e:
        return render_template("result.html", error=f"Analysis failed: {e}")

@app.post("/download_docx")
def download_docx():
    from json import loads
    try:
        student_name = request.form.get("student_name","")
        task_type = request.form.get("task_type","Task 2")
        extracted_text = request.form.get("extracted_text","")
        feedback = loads(request.form.get("feedback","{}"))
        data = build_docx(student_name, task_type, extracted_text, feedback)
        filename = f"{student_name or 'IELTS'}_{task_type}_feedback.docx".replace(" ","_")
        return send_file(io.BytesIO(data), as_attachment=True,
                         download_name=filename,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as e:
        return render_template("result.html", error=f"DOCX build failed: {e}")

@app.post("/download_pdf")
def download_pdf():
    from json import loads
    try:
        student_name = request.form.get("student_name","")
        task_type = request.form.get("task_type","Task 2")
        extracted_text = request.form.get("extracted_text","")
        feedback = loads(request.form.get("feedback","{}"))
        data = build_pdf(student_name, task_type, extracted_text, feedback)
        filename = f"{student_name or 'IELTS'}_{task_type}_feedback.pdf".replace(" ","_")
        return send_file(io.BytesIO(data), as_attachment=True,
                         download_name=filename,
                         mimetype="application/pdf")
    except Exception as e:
        return render_template("result.html", error=f"PDF build failed: {e}")

if __name__ == "__main__":
    app.run(debug=True)

