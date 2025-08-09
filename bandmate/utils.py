import os, io, re, json, datetime
from typing import Dict, Any
from PIL import Image
import pytesseract

def ocr_images_to_text(images) -> str:
    chunks = []
    for idx, file in enumerate(images, start=1):
        img = Image.open(file.stream).convert("L")
        text = pytesseract.image_to_string(img, lang="eng")
        chunks.append(f"[Page {idx}]\n{text.strip()}")
    return "\n\n".join(chunks).strip()

def detect_task_type(text:str)->str:
    tl = text.lower()
    if any(k in tl for k in ["diagram","map","chart","table","figure","process"]):
        return "Task 1"
    return "Task 2" if len(text.split())>=200 else "Task 2"

def _band_clamp(x): 
    try: return max(0.0,min(9.0, round(float(x)*2)/2))
    except: return 6.0

def generate_feedback(text:str, task_type:str, notes:str)->Dict[str,Any]:
    length=len(text.split())
    bands={"task":6.0,"coherence":6.0,"lexical":6.0,"grammar":6.0}
    actions=[]
    if task_type=="Task 2" and length<250:
        bands["task"]=5.0; actions.append("- Develop ideas further; aim for 250+ words.")
    if re.search(r"\b(i|im|dont|cant|wont)\b", text.lower()):
        bands["grammar"]=5.5; actions.append("- Capitalize 'I' and use correct contractions (don't, can't).")
    overall=_band_clamp(sum(bands.values())/4)
    summary=f"{task_type} draft (~{length} words). Strengths and areas to improve across idea development, coherence, vocabulary variety, and accuracy."
    if not actions:
        actions=["- Use paragraph topic sentences.","- Add linking devices naturally.",
                 "- Vary sentence structures.","- Check articles and subject–verb agreement."]
    return {"summary":summary,"actions":"\n".join(actions),"bands":{**bands,"overall":overall}}

from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

def build_docx(student_name:str, task_type:str, text:str, feedback:Dict[str,Any])->bytes:
    doc=Document(); doc.add_heading(f"BandMate — IELTS {task_type} Feedback",1)
    if student_name: doc.add_paragraph(f"Student: {student_name}")
    doc.add_paragraph(" "); doc.add_heading("Summary",2); doc.add_paragraph(feedback["summary"])
    b=feedback["bands"]; doc.add_heading("Band Estimates",2)
    doc.add_paragraph(f"Task Response/Achievement: {b['task']}")
    doc.add_paragraph(f"Coherence & Cohesion: {b['coherence']}")
    doc.add_paragraph(f"Lexical Resource: {b['lexical']}")
    doc.add_paragraph(f"Grammatical Range & Accuracy: {b['grammar']}")
    doc.add_paragraph(f"Overall: {b['overall']}")
    doc.add_heading("Actionable Suggestions",2)
    for line in feedback["actions"].splitlines():
        if line.strip(): p=doc.add_paragraph(line.strip()); p.style='List Bullet'
    doc.add_heading("Student Text (OCR)",2); doc.add_paragraph(text)
    bio=io.BytesIO(); doc.save(bio); return bio.getvalue()

def build_pdf(student_name:str, task_type:str, text:str, feedback:Dict[str,Any])->bytes:
    bio=io.BytesIO(); c=canvas.Canvas(bio, pagesize=A4); w,h=A4; x,y=2*cm,h-2*cm
    def ln(s,lead=14,bold=False):
        nonlocal y
        if y<2*cm: c.showPage(); y=h-2*cm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 11); c.drawString(x,y,s); y-=lead
    ln(f"BandMate — IELTS {task_type} Feedback",20,True)
    ln(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),12)
    if student_name: ln(f"Student: {student_name}",16)
    ln("Summary",16,True)
    for t in feedback["summary"].splitlines(): ln(t)
    b=feedback["bands"]; ln("Band Estimates",16,True)
    for k,l in [("task","Task Response/Achievement"),("coherence","Coherence & Cohesion"),("lexical","Lexical Resource"),("grammar","Grammatical Range & Accuracy"),("overall","Overall")]:
        ln(f"{l}: {b[k]}")
    ln("Actionable Suggestions",16,True)
    for t in feedback["actions"].splitlines(): ln(t)
    ln("Student Text (OCR)",16,True); c.setFont("Helvetica",10)
    for t in text.splitlines(): ln(t,12)
    c.showPage(); c.save(); return bio.getvalue()

def weighted_overall(bands:dict, w_task:float, w_coh:float, w_lex:float, w_gra:float)->float:
    tot=w_task+w_coh+w_lex+w_gra
    raw=(bands["task"]*w_task+bands["coherence"]*w_coh+bands["lexical"]*w_lex+bands["grammar"]*w_gra)/max(0.0001,tot)
    return _band_clamp(raw)
