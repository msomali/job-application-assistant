"""Generate tailored resumes using Claude + LaTeX."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError

from src.models import JobAnalysis, JobPosting, ResumeContent
from src.privacy import PIIGuard
from src.utils import retry

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"


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

RESUME_SYSTEM_PROMPT = """\
You are an expert resume writer. Create a tailored resume for the specified job.

Write in a natural, human voice as if a real person wrote it.

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
  - "dates": date range string
  - "bullets": list of 3-5 achievement bullets, tailored to highlight relevant experience. Write each bullet as a natural sentence. Quantify results where possible. Prioritize bullets that match the job requirements.
- "skills_section": string, comma-separated skills ordered by relevance to this job
- "education": list of objects, each with:
  - "degree": degree name
  - "institution": school name
  - "year": graduation year
  - "details": optional string for honors, relevant coursework
- "highlighted_projects": list of objects (include only if relevant), each with:
  - "name": project name
  - "description": 1-2 sentence description highlighting relevance to the role

Return ONLY valid JSON, no markdown fences."""


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def generate_resume_content(
    job: JobPosting, analysis: JobAnalysis, master_resume: dict, *, redact: bool = True
) -> ResumeContent:
    """Use Claude to generate tailored resume content.

    Args:
        job: The job posting to tailor the resume for.
        analysis: The job analysis with tailoring strategy.
        master_resume: The candidate's full resume data.
        redact: If True, redact PII before sending to Claude. Default True.
    """
    logger.info("Generating resume content for %s at %s", job.title, job.company)
    client = anthropic.Anthropic()

    guard = None
    resume_for_llm = master_resume
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume_for_llm = guard.redact_dict(master_resume)
        logger.info("PII redacted: %d fields protected", guard.field_count)

    requirements_text = "\n".join(f"- {r}" for r in job.requirements)
    keywords_text = ", ".join(analysis.keywords)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        system=[
            {
                "type": "text",
                "text": RESUME_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## Candidate's Full Profile\n{json.dumps(resume_for_llm, separators=(',', ':'))}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"## Job Posting\nTitle: {job.title}\nCompany: {job.company}\n"
                            f"Requirements:\n{requirements_text}\n\n"
                            f"## Tailoring Strategy\n{analysis.tailoring_strategy}\n\n"
                            f"## Keywords to Emphasize\n{keywords_text}"
                        ),
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text
    if guard:
        response_text = guard.restore(response_text)

    data = json.loads(response_text)
    logger.info("Resume content generated successfully")
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
        entries.append(
            f"\\cvsection{{{_escape_latex(exp['title'])} | "
            f"{_escape_latex(exp['company'])}}}{{{exp.get('dates', '')}}}\n"
            f"\\begin{{itemize}}\n{bullets}\n\\end{{itemize}}\n"
        )
    return "\n".join(entries)


def _build_education_latex(education: list[dict]) -> str:
    """Build LaTeX for the education section."""
    entries = []
    for edu in education:
        details = f" -- {_escape_latex(edu['details'])}" if edu.get("details") else ""
        entries.append(
            f"\\cvsection{{{_escape_latex(edu['degree'])} | "
            f"{_escape_latex(edu['institution'])}}}{{{edu.get('year', '')}}}\n"
            f"{details}\n"
        )
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


def render_resume(
    content: ResumeContent, master_resume: dict, output_dir: Path
) -> Path:
    """Render resume content to PDF via LaTeX."""
    logger.info("Rendering resume PDF to %s", output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE_PATH.read_text()

    name = _escape_latex(master_resume.get("name", "Your Name"))
    contact = _escape_latex(master_resume.get("contact", ""))

    latex = template.replace("%%NAME%%", name)
    latex = latex.replace("%%CONTACT%%", contact)
    latex = latex.replace("%%SUMMARY%%", _escape_latex(content.summary))
    latex = latex.replace("%%EXPERIENCE%%", _build_experience_latex(content.experience))
    latex = latex.replace("%%SKILLS%%", _escape_latex(content.skills_section))
    latex = latex.replace("%%EDUCATION%%", _build_education_latex(content.education))
    latex = latex.replace(
        "%%PROJECTS%%", _build_projects_latex(content.highlighted_projects)
    )

    tex_file = output_dir / "resume.tex"
    tex_file.write_text(latex)

    pdflatex = _find_pdflatex()
    subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-output-directory", str(output_dir), str(tex_file)],
        capture_output=True,
        check=True,
        timeout=30,
    )

    pdf_path = output_dir / "resume.pdf"
    if not pdf_path.exists():
        logger.error("Resume PDF generation failed. Check %s for logs.", output_dir)
        raise RuntimeError(f"PDF generation failed. Check {output_dir} for logs.")
    logger.info("Resume PDF generated: %s", pdf_path)
    return pdf_path
