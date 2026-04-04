"""Generate tailored resumes using Claude + LaTeX."""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from anthropic import APIError, APITimeoutError, RateLimitError

from src.llm import get_router, parse_json_response
from src.models import JobAnalysis, JobPosting, ResumeContent
from src.privacy import PIIGuard
from src.utils import retry

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent.parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent.parent.parent / "data" / "screening_answers.json"


def _find_pdflatex() -> str:
    """Find pdflatex binary, checking common locations and PATH."""
    # Check environment override first
    env_path = os.environ.get("PDFLATEX_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    # Check PATH
    found = shutil.which("pdflatex")
    if found:
        return found
    # Check common locations
    for candidate in [
        "/Library/TeX/texbin/pdflatex",  # macOS MacTeX
        "/usr/local/texlive/2025/bin/universal-darwin/pdflatex",  # macOS alt
        "/usr/bin/pdflatex",  # Linux
        "/usr/local/bin/pdflatex",  # Linux alt
    ]:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "pdflatex not found. Install LaTeX or set PDFLATEX_PATH environment variable."
    )

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "resume.tex"

RESUME_SYSTEM_PROMPT_1PAGE = """\
You are an expert resume writer. Create a tailored ONE-PAGE resume for the specified job.

CRITICAL CONSTRAINT: This resume MUST fit on a single page. Be ruthlessly selective.

ROLE SELECTION RULES:
- Include ONLY the {max_roles} most relevant roles to this specific job.
- For junior/entry-level positions: prioritize the most recent 2 roles and any internships or projects directly relevant to the job.
- For mid/senior positions: prioritize roles that demonstrate progression and direct skill overlap.
- OMIT roles that don't contribute to the narrative for THIS job, even if they're recent.
- The exact bullet count per role is specified in the Content Plan below. Follow it exactly.

CONTENT PRIORITY (in order — stop when the page is full):
1. Name, contact info (provided separately)
2. Experience (most relevant roles, bullet count per Content Plan)
3. Skills (one line, most relevant first)
4. Education (degree, school, location, full date range — one line each)
5. Certifications, Projects, Professional Summary — as specified in Content Plan

IMPORTANT STYLE RULES:
- Write naturally. Every bullet should read like a person describing their work, not like AI output.
- DO NOT use hyphens or em dashes to connect sentence fragments (e.g., never write "Built X — resulting in Y").
- Use complete, flowing sentences. Start with strong action verbs.
- Be specific and quantify results, but keep the tone conversational and authentic.
- Avoid buzzword stacking. Use plain language where possible.
- Each bullet should be 130-180 characters long (wraps to exactly 2 printed lines in the PDF).

Return a JSON object with these fields:

- "summary": string or null (include ONLY if space allows — for 1-page resumes, often skip this)
- "experience": list of objects (MAX {max_roles} roles), each with:
  - "title": job title
  - "company": company name
  - "location": city/state or city/country (from the candidate profile)
  - "dates": date range string
  - "bullets": list of achievement bullets (count specified in Content Plan). Prioritize bullets that match the job requirements.
- "skills_section": string, comma-separated skills ordered by relevance to this job (one line)
- "education": list of objects, each with:
  - "degree": degree name
  - "institution": school name
  - "location": city/state or city/country (from the candidate profile)
  - "dates": full date range (e.g., "Aug 2023 - Dec 2024"), NOT just the graduation year
  - "details": optional string (only if directly relevant, e.g., relevant thesis)
- "certifications": list of strings (include only if relevant and space allows, otherwise empty list)
- "highlighted_projects": list of objects (include ONLY if highly relevant and space allows), each with:
  - "name": project name
  - "description": 1 sentence max

Return ONLY valid JSON, no markdown fences."""

RESUME_SYSTEM_PROMPT_MULTI = """\
You are an expert resume writer. Create a tailored resume for the specified job.
This resume can be up to {max_pages} pages.

Write in a natural, human voice as if a real person wrote it.

ROLE SELECTION RULES:
- Include the most relevant roles first, up to {max_roles} roles.
- For junior/entry-level positions: prioritize recent roles and directly relevant experience.
- For mid/senior positions: show career progression and leadership growth.
- OMIT roles that don't contribute to the narrative for THIS job.

IMPORTANT STYLE RULES:
- Write naturally. Every bullet should read like a person describing their work, not like AI output.
- DO NOT use hyphens or em dashes to connect sentence fragments (e.g., never write "Built X — resulting in Y").
- Use complete, flowing sentences. Start with strong action verbs.
- Be specific and quantify results, but keep the tone conversational and authentic.
- Avoid buzzword stacking. Use plain language where possible.

Return a JSON object with these fields:

- "summary": string, 2-3 sentence professional summary tailored to this role
- "experience": list of objects, each with:
  - "title": job title
  - "company": company name
  - "location": city/state or city/country (from the candidate profile)
  - "dates": date range string
  - "bullets": list of achievement bullets (exact count specified in Content Plan). Write each bullet as a natural sentence. Quantify results where possible. Prioritize bullets that match the job requirements. Each bullet should be 130-180 characters.
- "skills_section": string, comma-separated skills ordered by relevance to this job
- "education": list of objects, each with:
  - "degree": degree name
  - "institution": school name
  - "location": city/state or city/country (from the candidate profile)
  - "dates": full date range (e.g., "Aug 2023 - Dec 2024"), NOT just the graduation year
  - "details": optional string for honors, relevant coursework
- "certifications": list of strings (include if relevant, otherwise empty list)
- "highlighted_projects": list of objects (include only if relevant), each with:
  - "name": project name
  - "description": 1-2 sentence description highlighting relevance to the role

Return ONLY valid JSON, no markdown fences."""


def _get_experience_level(job: JobPosting) -> str:
    """Infer the experience level from job posting."""
    level = (job.experience_level or "").lower()
    title = job.title.lower()
    desc = (job.description or "").lower()[:2000]

    if any(k in level or k in title for k in ("junior", "entry", "associate", "jr", "i ", " 1", " i")):
        return "junior"
    if any(k in level or k in title for k in ("senior", "sr", "lead", "principal", "staff", "iii", " 3")):
        return "senior"
    if any(k in desc for k in ("1-3 years", "1-2 years", "0-2 years", "entry level")):
        return "junior"
    if any(k in desc for k in ("7+ years", "8+ years", "10+ years", "senior", "lead")):
        return "senior"
    return "mid"


def _build_content_plan(master_resume: dict, exp_level: str, pages: int) -> dict:
    """Pre-analyze master resume and build a content plan for Claude.

    Uses point-based measurements from the actual LaTeX template to calculate
    exactly how much content fits on the page. All constants were measured
    empirically using savebox heights with the resume.tex template
    (10pt lmodern, letterpaper, 0.5in/0.4in margins).

    Component heights (in points, from savebox measurements):
      Header (name + contact):      48 pt
      Section header (\\section*):  22 pt
      Summary (header + 3-line):    49 pt
      Role base (title + itemize):  11 pt  (without bullets)
      Bullet (2-line wrap):         25 pt  (incremental per bullet)
      Skills section (2-line):      44 pt
      Education entry (+ location): 22 pt  (per degree)
      Certs section (1-line):       32 pt
      Project entry (title+bullet): 39 pt  (incremental per project)

    Page budget: 706 pt (savebox height that fits 1 page with 15pt safety).
    Empirically verified: 3r×5b+0proj (663pt) fits, 3r×6b (738pt) overflows.
    """
    n_experiences = len(master_resume.get("experience", []))
    n_projects = len(master_resume.get("projects", []))
    n_certs = len(master_resume.get("certifications", []))
    n_education = len(master_resume.get("education", []))
    has_summary = bool(master_resume.get("summary"))

    # Point-based constants (measured from LaTeX template)
    PAGE_BUDGET = 722 * pages   # savebox pts that fit on page (8pt safety from 730 boundary)
    HEADER_PT = 48              # name + contact line
    SECTION_HDR_PT = 22         # \section*{...} with rule + spacing
    SUMMARY_PT = 49             # section header + ~3 lines of text
    ROLE_BASE_PT = 11           # cvsection title + itemize env overhead
    BULLET_PT = 25              # one 2-line bullet (incremental)
    SKILLS_PT = 44              # section header + 2-line skills list
    EDU_HDR_PT = 22             # Education section header
    EDU_ENTRY_PT = 22           # one degree entry (title + location line)
    CERTS_PT = 32               # section header + 1-line certs
    PROJ_HDR_PT = 22            # Projects section header
    PROJ_ENTRY_PT = 39          # one project (title + 1 two-line bullet)

    # Fixed costs (always present)
    fixed = HEADER_PT + SECTION_HDR_PT + SKILLS_PT + EDU_HDR_PT + (n_education * EDU_ENTRY_PT)
    budget = PAGE_BUDGET - fixed

    # Determine initial role count based on experience level
    if n_experiences <= 3:
        max_roles = n_experiences
        content_thin = True
    else:
        content_thin = False
        if pages == 1:
            max_roles = 3 if exp_level == "junior" else min(4, n_experiences)
        else:
            max_roles = min(6, n_experiences)

    # Evaluate candidate fill strategies and pick the one with least waste.
    # Each candidate is (bullets_per_role, include_summary, include_certs,
    #                     include_projects, max_projects, waste_pt)
    max_bpr = 5 if pages == 1 else 6
    if content_thin:
        max_bpr = 6
    proj_cap = 2 if pages == 1 else 3

    best = None
    for bpr in range(3, max_bpr + 1):
        exp_cost = max_roles * (ROLE_BASE_PT + bpr * BULLET_PT)
        rem = budget - exp_cost
        if rem < 0:
            break

        # Always try to include summary and certs
        s = has_summary and rem >= SUMMARY_PT
        if s:
            rem -= SUMMARY_PT
        c = n_certs > 0 and rem >= CERTS_PT
        if c:
            rem -= CERTS_PT

        # Try with projects
        np = 0
        if n_projects > 0 and rem >= PROJ_HDR_PT + PROJ_ENTRY_PT:
            rem -= PROJ_HDR_PT
            while np < min(n_projects, proj_cap) and rem >= PROJ_ENTRY_PT:
                np += 1
                rem -= PROJ_ENTRY_PT

        # Pick the option with least waste (rem closest to 0 but >= 0)
        if rem >= 0 and (best is None or rem < best[5]):
            best = (bpr, s, c, np > 0, np, rem)

    bullets_per_role, include_summary, include_certs, include_projects, max_projects, _ = best

    return {
        "max_roles": max_roles,
        "bullets_per_role": bullets_per_role,
        "include_summary": include_summary,
        "include_certs": include_certs,
        "include_projects": include_projects,
        "max_projects": max_projects,
        "content_thin": content_thin,
        "total_experiences_available": n_experiences,
        "total_projects_available": n_projects,
        "total_certs_available": n_certs,
    }


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def generate_resume_content(
    job: JobPosting, analysis: JobAnalysis, master_resume: dict,
    *, redact: bool = True, pages: int = 1,
) -> ResumeContent:
    """Use Claude to generate tailored resume content.

    Args:
        job: The job posting to tailor the resume for.
        analysis: The job analysis with tailoring strategy.
        master_resume: The candidate's full resume data.
        redact: If True, redact PII before sending to Claude. Default True.
        pages: Target page count. Default 1 (single-page resume).
    """
    logger.info("Generating %d-page resume for %s at %s", pages, job.title, job.company)

    guard = None
    resume_for_llm = master_resume
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume_for_llm = guard.redact_dict(master_resume)
        logger.info("PII redacted: %d fields protected", guard.field_count)

    # Pre-analyze content and build a plan
    exp_level = _get_experience_level(job)
    plan = _build_content_plan(master_resume, exp_level, pages)

    if pages == 1:
        system_prompt = RESUME_SYSTEM_PROMPT_1PAGE.format(max_roles=plan["max_roles"])
    else:
        system_prompt = RESUME_SYSTEM_PROMPT_MULTI.format(
            max_pages=pages, max_roles=plan["max_roles"]
        )

    requirements_text = "\n".join(f"- {r}" for r in job.requirements)
    keywords_text = ", ".join(analysis.keywords)

    # Build precise content instructions from the plan
    content_instructions = (
        f"\n\n## Content Plan (follow exactly)\n"
        f"- Experience level: {exp_level}\n"
        f"- Include exactly {plan['max_roles']} roles "
        f"(candidate has {plan['total_experiences_available']} total — "
    )
    if plan["content_thin"]:
        content_instructions += (
            "this is ALL their experience, include every role. "
            "Tailor each role's bullets to show relevance to this job, "
            "even if the role itself isn't a perfect match. Show career flow.)\n"
        )
    else:
        content_instructions += "select the most relevant ones.)\n"

    content_instructions += (
        f"- EXACTLY {plan['bullets_per_role']} bullets per role "
        "(this count is calculated to fill the page — do NOT use fewer)\n"
        "- Each bullet should be 130-180 characters (wraps to exactly 2 printed lines)\n"
    )

    if plan["include_summary"]:
        content_instructions += "- INCLUDE a 2-3 sentence professional summary\n"
    else:
        content_instructions += "- OMIT summary (set to null) — not enough space\n"

    if plan["include_certs"] and plan["total_certs_available"] > 0:
        content_instructions += (
            f"- INCLUDE certifications (pick most relevant from "
            f"{plan['total_certs_available']} available)\n"
        )
    else:
        content_instructions += "- OMIT certifications (empty list)\n"

    if plan["include_projects"] and plan["max_projects"] > 0:
        content_instructions += (
            f"- INCLUDE up to {plan['max_projects']} projects "
            f"(pick most relevant from {plan['total_projects_available']} available)\n"
        )
    else:
        content_instructions += "- OMIT projects (empty list)\n"

    content_instructions += (
        f"\nGOAL: Fill the entire {pages}-page resume with no gaps. "
        "Every line should earn its place. If you have space, add more detail to bullets."
    )

    logger.info("Content plan: %s", plan)

    cached_content = (
        f"## Candidate's Full Profile\n{json.dumps(resume_for_llm, separators=(',', ':'))}"
    )
    variable_content = (
        f"## Job Posting\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Requirements:\n{requirements_text}\n\n"
        f"## Tailoring Strategy\n{analysis.tailoring_strategy}\n\n"
        f"## Keywords to Emphasize\n{keywords_text}"
        f"{content_instructions}"
    )

    router = get_router()
    response = router.generate_with_cache(
        task="resume_generation",
        system=system_prompt,
        cached_content=cached_content,
        variable_content=variable_content,
        max_tokens=3000,
    )

    response_text = response.text
    if guard:
        response_text = guard.restore(response_text)

    data = parse_json_response(response_text)
    logger.info("Resume content generated (%d-page, %s-level, %d roles, plan=%s, provider=%s)",
                pages, exp_level, len(data.get("experience", [])), plan, response.provider)
    return ResumeContent(**data)


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters to prevent injection."""
    # Backslash MUST be first to avoid double-escaping
    text = text.replace("\\", r"\textbackslash{}")
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _build_experience_latex(experience: list[dict]) -> str:
    """Build LaTeX for the experience section."""
    entries = []
    for exp in experience:
        bullets = "\n".join(
            f"    \\item {_escape_latex(b)}" for b in exp.get("bullets", [])
        )
        location = exp.get("location", "")
        header = f"{_escape_latex(exp['title'])} | {_escape_latex(exp['company'])}"
        if location:
            header += f", {_escape_latex(location)}"
        entries.append(
            f"\\cvsection{{{header}}}{{{exp.get('dates', '')}}}\n"
            f"\\begin{{itemize}}\n{bullets}\n\\end{{itemize}}\n"
        )
    return "\n".join(entries)


def _build_education_latex(education: list[dict]) -> str:
    """Build LaTeX for the education section."""
    entries = []
    for edu in education:
        details = f" -- {_escape_latex(edu['details'])}" if edu.get("details") else ""
        location = edu.get("location", "")
        # Use "dates" if available (full range), fall back to "year"
        date_str = edu.get("dates", edu.get("year", ""))
        # Degree + institution on first line with dates right-aligned
        header = f"{_escape_latex(edu['degree'])} | {_escape_latex(edu['institution'])}"
        entry = f"\\cvsection{{{header}}}{{{date_str}}}\n"
        # Location on a compact second line
        if location:
            entry += f"\\hspace{{1.5em}}\\textit{{{_escape_latex(location)}}}\n"
        if details:
            entry += f"{details}\n"
        entries.append(entry)
    return "\n".join(entries)


def _build_projects_latex(projects: list[dict]) -> str:
    """Build LaTeX for the projects section."""
    if not projects:
        return ""
    entries = []
    for proj in projects:
        entries.append(
            f"\\textbf{{{_escape_latex(proj['name'])}}} -- "
            f"{_escape_latex(proj['description'])}\n"
        )
    return "\\section*{Projects}\n" + "\n".join(entries)


def _build_certifications_latex(certifications: list[str]) -> str:
    """Build LaTeX for the certifications section."""
    if not certifications:
        return ""
    certs = ", ".join(_escape_latex(c) for c in certifications)
    return f"\\section*{{Certifications}}\n{certs}\n"


def render_resume(
    content: ResumeContent, master_resume: dict, output_dir: Path, *, pages: int = 1,
) -> Path:
    """Render resume content to PDF via LaTeX.

    Args:
        pages: Target page count. 1 = compact single-page layout. >1 = relaxed multi-page.
    """
    logger.info("Rendering %d-page resume PDF to %s", pages, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE_PATH.read_text()

    name = _escape_latex(master_resume.get("name", "Your Name"))
    contact = _escape_latex(master_resume.get("contact", ""))

    # Summary: only include if present (Claude may omit for 1-page)
    summary_latex = ""
    if content.summary:
        summary_latex = f"\\section*{{Professional Summary}}\n{_escape_latex(content.summary)}\n"

    latex = template.replace("%%NAME%%", name)
    latex = latex.replace("%%CONTACT%%", contact)
    latex = latex.replace("%%SUMMARY%%", summary_latex)
    latex = latex.replace("%%EXPERIENCE%%", _build_experience_latex(content.experience))
    latex = latex.replace("%%SKILLS%%", _escape_latex(content.skills_section))
    latex = latex.replace("%%EDUCATION%%", _build_education_latex(content.education))
    latex = latex.replace("%%CERTIFICATIONS%%", _build_certifications_latex(content.certifications))
    latex = latex.replace("%%PROJECTS%%", _build_projects_latex(content.highlighted_projects))

    tex_file = output_dir / "resume.tex"
    tex_file.write_text(latex)

    pdflatex = _find_pdflatex()
    result = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-output-directory", str(output_dir), str(tex_file)],
        capture_output=True,
        timeout=30,
    )

    pdf_path = output_dir / "resume.pdf"
    if not pdf_path.exists():
        logger.error("Resume PDF generation failed. LaTeX log:\n%s", result.stdout.decode()[-2000:])
        raise RuntimeError(f"PDF generation failed. Check {output_dir} for logs.")

    # Check page count
    actual_pages = _count_pdf_pages(pdf_path)
    if actual_pages > pages:
        logger.warning(
            "Resume is %d pages (target: %d). Consider reducing content.", actual_pages, pages
        )

    logger.info("Resume PDF generated: %s (%d pages)", pdf_path, actual_pages)
    return pdf_path


def _count_pdf_pages(pdf_path: Path) -> int:
    """Count pages in a PDF file."""
    try:
        content = pdf_path.read_bytes()
        # Look for /Count N in the page tree root
        match = re.search(rb"/Count\s+(\d+)", content)
        if match:
            return int(match.group(1))
        # Fallback: count /Type /Page (not /Pages)
        return max(1, len(re.findall(rb"/Type\s*/Page[^s]", content)))
    except Exception:
        return 1
