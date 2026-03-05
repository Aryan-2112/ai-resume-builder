import streamlit as st
from fpdf import FPDF
import re
import os
from collections import Counter
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# -------- Load .env --------
load_dotenv()

# -------- Page Config --------
st.set_page_config(page_title="AI Resume Builder", page_icon="📄", layout="wide")

# -------- Hugging Face API --------
API_TOKEN = os.getenv("HF_TOKEN", "")

# Show warning in sidebar if token is missing
if not API_TOKEN:
    st.sidebar.error("⚠️ HF_TOKEN not found. Add it to your .env file.")

def query_hf(prompt, max_tokens=800):
    try:
        client = InferenceClient(provider="novita", api_key=API_TOKEN)
        completion = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# -------- ATS Score --------
COMMON_ATS_KEYWORDS = [
    "experience", "skills", "education", "project", "team", "leadership",
    "communication", "problem-solving", "analytical", "management", "development",
    "python", "java", "sql", "machine learning", "data", "cloud", "agile", "scrum"
]

def calculate_ats_score(resume_text):
    text_lower = resume_text.lower()
    score = 0
    matched = []
    missing = []

    # Section headings check (20 pts)
    sections = ["education", "skills", "experience", "projects", "objective", "summary"]
    found_sections = [s for s in sections if s in text_lower]
    score += len(found_sections) * 3

    # Length check (10 pts)
    word_count = len(resume_text.split())
    if 300 <= word_count <= 800:
        score += 10
    elif word_count > 100:
        score += 5

    # Keyword match (50 pts)
    for kw in COMMON_ATS_KEYWORDS:
        if kw in text_lower:
            matched.append(kw)
            score += 2
        else:
            missing.append(kw)

    # Bullet points / structure (10 pts)
    if "-" in resume_text or "•" in resume_text or "*" in resume_text:
        score += 10

    # Contact info (10 pts)
    if "@" in resume_text:
        score += 5
    if any(c.isdigit() for c in resume_text):
        score += 5

    score = min(score, 100)
    return score, matched, missing[:8]

# -------- Keyword Matcher --------
def match_keywords(resume_text, job_description):
    def extract_keywords(text):
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        stopwords = {"with","that","this","from","have","will","your","their","they","been","also","more","which","about","into","other","some","what","when","each","than","then","these","those","both","such","after"}
        return set(w for w in words if w not in stopwords)

    resume_kws = extract_keywords(resume_text)
    job_kws = extract_keywords(job_description)

    matched = job_kws & resume_kws
    missing = job_kws - resume_kws
    match_pct = int(len(matched) / len(job_kws) * 100) if job_kws else 0

    # Return top 15 most impactful missing keywords
    top_missing = sorted(missing, key=lambda w: -len(w))[:15]
    return match_pct, sorted(matched)[:15], top_missing

# -------- PDF Generator --------
TEMPLATE_STYLES = {
    "Classic": {"font": "Arial", "title_size": 16, "body_size": 11, "accent": (0, 0, 0)},
    "Modern":  {"font": "Helvetica", "title_size": 18, "body_size": 11, "accent": (41, 128, 185)},
    "Minimal": {"font": "Times", "title_size": 15, "body_size": 11, "accent": (100, 100, 100)},
}

def generate_pdf(resume_text, name, template="Classic"):
    style = TEMPLATE_STYLES[template]
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    r, g, b = style["accent"]

    # Header
    pdf.set_font(style["font"], "B", style["title_size"])
    pdf.set_text_color(r, g, b)
    pdf.cell(0, 12, name if name else "Resume", ln=True, align="C")
    pdf.set_draw_color(r, g, b)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    # Body
    pdf.set_font(style["font"], size=style["body_size"])
    pdf.set_text_color(0, 0, 0)

    for line in resume_text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue
        # Detect headings (ALL CAPS or ends with :)
        if line.isupper() or (line.endswith(":") and len(line) < 40):
            pdf.set_font(style["font"], "B", style["body_size"] + 1)
            pdf.set_text_color(r, g, b)
            pdf.ln(2)
            pdf.multi_cell(0, 8, line)
            pdf.set_font(style["font"], size=style["body_size"])
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.multi_cell(0, 7, line)

    pdf_path = "/tmp/resume_output.pdf"
    pdf.output(pdf_path)
    return pdf_path

# -------- Sidebar Inputs --------
st.sidebar.header("👤 Personal Info")
name     = st.sidebar.text_input("Full Name")
email    = st.sidebar.text_input("Email")
phone    = st.sidebar.text_input("Phone")
linkedin = st.sidebar.text_input("LinkedIn URL (optional)")
location = st.sidebar.text_input("City, Country (optional)")

st.sidebar.header("📝 Resume Details")
education  = st.sidebar.text_area("Education", height=80)
skills     = st.sidebar.text_area("Skills", height=80)
projects   = st.sidebar.text_area("Projects / Experience", height=100)
objective  = st.sidebar.text_area("Career Objective", height=80)

st.sidebar.header("🎨 Template")
template = st.sidebar.selectbox("Choose Style", ["Classic", "Modern", "Minimal"])

# -------- Main Tabs --------
st.title("📄 AI Resume Builder")
tab1, tab2, tab3, tab4 = st.tabs(["✍️ Generate Resume", "📊 ATS Score", "🔍 Job Match", "💌 Cover Letter"])

# ---- Tab 1: Generate Resume ----
with tab1:
    st.subheader("Generate Your AI-Powered Resume")
    if st.button("🚀 Generate Resume", type="primary"):
        if not name or not skills:
            st.warning("Please fill in at least your Name and Skills.")
        else:
            with st.spinner("Generating your resume..."):
                prompt = f"""[INST] Write a professional resume for the following person. Use clear section headings in uppercase (OBJECTIVE, EDUCATION, SKILLS, EXPERIENCE/PROJECTS). Be concise and professional.

Name: {name}
Email: {email}
Phone: {phone}
{"LinkedIn: " + linkedin if linkedin else ""}
{"Location: " + location if location else ""}
Education: {education}
Skills: {skills}
Projects/Experience: {projects}
Career Objective: {objective}
[/INST]"""
                resume_text = query_hf(prompt)

            st.session_state["resume_text"] = resume_text
            st.session_state["name"] = name

    if "resume_text" in st.session_state:
        resume_text = st.session_state["resume_text"]
        st.text_area("Generated Resume", resume_text, height=450)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Download PDF"):
                pdf_path = generate_pdf(resume_text, st.session_state.get("name",""), template)
                with open(pdf_path, "rb") as f:
                    st.download_button("⬇️ Download Resume PDF", f, "AI_Resume.pdf", mime="application/pdf")
        with col2:
            if st.button("📋 Copy to Clipboard"):
                st.code(resume_text)
                st.info("Select all text above and copy.")

# ---- Tab 2: ATS Score ----
with tab2:
    st.subheader("📊 ATS Compatibility Score")
    st.write("Check how well your resume performs against Applicant Tracking Systems.")

    ats_input = st.text_area("Paste your resume text here:", height=300,
                              value=st.session_state.get("resume_text", ""))

    if st.button("🔍 Check ATS Score"):
        if not ats_input.strip():
            st.warning("Please paste your resume text.")
        else:
            score, matched, missing = calculate_ats_score(ats_input)

            col1, col2, col3 = st.columns(3)
            col1.metric("ATS Score", f"{score}/100")
            col2.metric("Keywords Found", len(matched))
            col3.metric("Missing Keywords", len(missing))

            # Score bar
            color = "green" if score >= 70 else "orange" if score >= 50 else "red"
            st.markdown(f"""
            <div style="background:#eee;border-radius:8px;height:24px;width:100%">
              <div style="background:{color};width:{score}%;height:24px;border-radius:8px;
                          display:flex;align-items:center;justify-content:center;color:white;font-weight:bold">
                {score}%
              </div>
            </div>""", unsafe_allow_html=True)
            st.markdown("")

            col_a, col_b = st.columns(2)
            with col_a:
                st.success("✅ Matched Keywords")
                st.write(", ".join(matched) if matched else "None found")
            with col_b:
                st.error("❌ Suggested Keywords to Add")
                st.write(", ".join(missing) if missing else "Great coverage!")

            # Tips
            st.subheader("💡 Improvement Tips")
            if score < 70:
                tips = [
                    "Add measurable achievements (e.g., 'Increased efficiency by 30%')",
                    "Include all standard sections: Objective, Education, Skills, Experience",
                    f"Add missing keywords: {', '.join(missing[:5])}",
                    "Use bullet points for experience/projects",
                    "Keep resume between 300–800 words",
                ]
                for tip in tips:
                    st.markdown(f"- {tip}")
            else:
                st.success("Your resume looks ATS-friendly! Minor tweaks can push it higher.")

# ---- Tab 3: Job Keyword Matcher ----
with tab3:
    st.subheader("🔍 Job Description Keyword Matcher")
    st.write("Paste a job description to see how well your resume matches it.")

    col1, col2 = st.columns(2)
    with col1:
        resume_for_match = st.text_area("Your Resume Text", height=300,
                                         value=st.session_state.get("resume_text", ""))
    with col2:
        job_desc = st.text_area("Job Description", height=300,
                                 placeholder="Paste the job posting here...")

    if st.button("⚡ Match Keywords"):
        if not resume_for_match.strip() or not job_desc.strip():
            st.warning("Please provide both your resume and the job description.")
        else:
            match_pct, matched_kws, missing_kws = match_keywords(resume_for_match, job_desc)

            st.metric("Match Score", f"{match_pct}%")

            color = "green" if match_pct >= 60 else "orange" if match_pct >= 40 else "red"
            st.markdown(f"""
            <div style="background:#eee;border-radius:8px;height:24px;width:100%">
              <div style="background:{color};width:{match_pct}%;height:24px;border-radius:8px;
                          display:flex;align-items:center;justify-content:center;color:white;font-weight:bold">
                {match_pct}%
              </div>
            </div>""", unsafe_allow_html=True)
            st.markdown("")

            col_a, col_b = st.columns(2)
            with col_a:
                st.success(f"✅ Matched ({len(matched_kws)})")
                st.write(", ".join(matched_kws) if matched_kws else "No matches")
            with col_b:
                st.error(f"❌ Missing from Resume ({len(missing_kws)})")
                st.write(", ".join(missing_kws) if missing_kws else "Excellent match!")

            if missing_kws:
                st.info(f"💡 Try adding these to your resume: **{', '.join(missing_kws[:8])}**")

            # AI Tailoring Suggestion
            if st.button("🤖 Get AI Suggestions to Tailor Resume"):
                with st.spinner("Generating tailoring suggestions..."):
                    tailor_prompt = f"""[INST] Given this job description, suggest 5 specific improvements to tailor this resume. Focus on missing keywords and skills.

Job Description (excerpt): {job_desc[:500]}
Missing Keywords: {', '.join(missing_kws[:10])}

Give 5 specific, actionable suggestions. [/INST]"""
                    suggestions = query_hf(tailor_prompt, max_tokens=400)
                st.subheader("🎯 Tailoring Suggestions")
                st.write(suggestions)

# ---- Tab 4: Cover Letter ----
with tab4:
    st.subheader("💌 AI Cover Letter Generator")

    col1, col2 = st.columns(2)
    with col1:
        company_name  = st.text_input("Company Name")
        job_title     = st.text_input("Job Title / Role")
        hiring_manager = st.text_input("Hiring Manager Name (optional)", placeholder="e.g. Mr. Smith")
    with col2:
        tone = st.selectbox("Tone", ["Professional", "Enthusiastic", "Concise"])
        job_desc_cl   = st.text_area("Job Description (paste key points)", height=120)

    if st.button("✉️ Generate Cover Letter", type="primary"):
        if not company_name or not job_title:
            st.warning("Please enter the company name and job title.")
        else:
            with st.spinner("Writing your cover letter..."):
                cl_prompt = f"""[INST] Write a {tone.lower()} cover letter for the following:

Applicant: {name or "the applicant"}
Applying for: {job_title} at {company_name}
{"Addressed to: " + hiring_manager if hiring_manager else ""}
Applicant Skills: {skills or "as described in the resume"}
Job Requirements: {job_desc_cl or "as per the job posting"}

Write a 3-paragraph cover letter. Opening: express interest. Middle: match skills to the role. Closing: call to action. [/INST]"""
                cover_letter = query_hf(cl_prompt, max_tokens=600)

            st.session_state["cover_letter"] = cover_letter

    if "cover_letter" in st.session_state:
        cl_text = st.session_state["cover_letter"]
        st.text_area("Your Cover Letter", cl_text, height=350)

        if st.button("📄 Download Cover Letter PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_margins(25, 25, 25)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 12, f"Cover Letter – {job_title}", ln=True)
            pdf.set_font("Arial", size=11)
            pdf.ln(4)
            for line in cl_text.split("\n"):
                pdf.multi_cell(0, 7, line.strip())
                if not line.strip():
                    pdf.ln(2)
            cl_path = "/tmp/cover_letter.pdf"
            pdf.output(cl_path)
            with open(cl_path, "rb") as f:
                st.download_button("⬇️ Download Cover Letter PDF", f, "Cover_Letter.pdf", mime="application/pdf")
