"""Browser automation for job applications using Claude Computer Use + Playwright.

Claude sees screenshots and decides what to click/type. Playwright executes the actions.
This gives Claude visual understanding of application forms while we maintain
programmatic browser control.
"""

import asyncio
import base64
import json
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page, async_playwright

from src.agent.telegram_bot import request_approval, send_notification, send_photo
from src.scraper.browser_session import has_session, session_path

logger = logging.getLogger(__name__)

# Screen dimensions for Claude Computer Use
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 800

# Beta header and tool version for Claude Computer Use
# Use latest version for Opus 4.6 / Sonnet 4.6 / Opus 4.5
BETA_HEADER = "computer-use-2025-01-24"
TOOL_VERSION = "20250124"
MODEL = "claude-sonnet-4-20250514"

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"

# Pause signal mechanism — set by Telegram bot or CLI
_pause_signals: dict[int, asyncio.Event] = {}  # job_id -> Event


def request_pause(job_id: int) -> None:
    """Signal the Computer Use loop to pause at the next step."""
    _pause_signals.setdefault(job_id, asyncio.Event()).set()


def is_pause_requested(job_id: int) -> bool:
    """Check if a pause has been requested for this job."""
    event = _pause_signals.get(job_id)
    return event is not None and event.is_set()


def clear_pause_signal(job_id: int) -> None:
    """Clear the pause signal after pausing."""
    _pause_signals.pop(job_id, None)


async def _take_screenshot(page: Page) -> str:
    """Take a screenshot and return as compressed JPEG base64.

    JPEG at quality 60 is typically 3-5x smaller than PNG for screenshots
    while remaining perfectly readable for form fields and text.
    Dimensions stay at viewport size so Claude's coordinate mapping is correct.
    """
    from io import BytesIO

    from PIL import Image

    screenshot_bytes = await page.screenshot(full_page=False)
    img = Image.open(BytesIO(screenshot_bytes))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


async def _save_screenshot(page: Page, name: str) -> str:
    """Take a screenshot and save to disk. Returns the file path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    return str(path)


def _pick_upload_file(
    claude_text: str, page_url: str, resume_path: str, cover_letter_path: str
) -> str | None:
    """Decide which PDF to upload based on Claude's commentary and page context.

    Checks Claude's latest text output and the page URL for clues about whether
    the form wants a resume or cover letter.
    """
    context = (claude_text or "").lower()
    url_lower = (page_url or "").lower()
    combined = context + " " + url_lower

    cover_keywords = ("cover letter", "cover_letter", "coverletter", "motivation letter")

    # Check for cover letter first (more specific)
    if any(kw in combined for kw in cover_keywords) and cover_letter_path:
        return cover_letter_path
    # Default to resume for any upload prompt
    if resume_path:
        return resume_path
    return cover_letter_path or None


def _prune_old_screenshots(messages: list[dict], keep_recent: int = 3) -> list[dict]:
    """Replace base64 image data in older messages with a text placeholder.

    Keeps the most recent `keep_recent` screenshots intact so Claude has context,
    but strips older ones to prevent token count from exploding over many loop steps.
    Always preserves the first message (initial screenshot).
    """
    # Find indices of messages that contain images
    image_indices = []
    for i, msg in enumerate(messages):
        content = msg.get("content")
        if not content:
            continue
        # content can be a list of blocks or a ContentBlock object list
        items = content if isinstance(content, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("type") == "image":
                image_indices.append(i)
                break
            if isinstance(item, dict):
                # tool_result with nested image
                nested = item.get("content", [])
                if isinstance(nested, list):
                    for sub in nested:
                        if isinstance(sub, dict) and sub.get("type") == "image":
                            image_indices.append(i)
                            break

    if len(image_indices) <= keep_recent + 1:
        return messages  # nothing to prune (keep_recent + first)

    # Indices to strip (skip first, skip last keep_recent)
    to_strip = set(image_indices[1:-keep_recent]) if keep_recent > 0 else set(image_indices[1:])

    pruned = []
    for i, msg in enumerate(messages):
        if i not in to_strip:
            pruned.append(msg)
            continue
        # Deep-copy and replace images with placeholder text
        new_msg = {"role": msg["role"], "content": []}
        items = msg["content"] if isinstance(msg["content"], list) else []
        for item in items:
            if isinstance(item, dict) and item.get("type") == "image":
                new_msg["content"].append({"type": "text", "text": "[screenshot omitted]"})
            elif isinstance(item, dict) and "content" in item and isinstance(item["content"], list):
                new_item = {**item, "content": []}
                for sub in item["content"]:
                    if isinstance(sub, dict) and sub.get("type") == "image":
                        new_item["content"].append({"type": "text", "text": "[screenshot omitted]"})
                    else:
                        new_item["content"].append(sub)
                new_msg["content"].append(new_item)
            else:
                new_msg["content"].append(item)
        pruned.append(new_msg)
    return pruned


async def _execute_action(page: Page, action: dict) -> str | None:
    """Execute a Computer Use action on the Playwright page.

    Returns base64 screenshot after action, or None if action is screenshot.
    """
    action_type = action.get("action")

    if action_type == "screenshot":
        return await _take_screenshot(page)

    elif action_type == "left_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y)

    elif action_type == "right_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y, button="right")

    elif action_type == "double_click":
        x, y = action["coordinate"]
        await page.mouse.dblclick(x, y)

    elif action_type == "middle_click":
        x, y = action["coordinate"]
        await page.mouse.click(x, y, button="middle")

    elif action_type == "mouse_move":
        x, y = action["coordinate"]
        await page.mouse.move(x, y)

    elif action_type == "type":
        text = action.get("text", "")
        await page.keyboard.type(text, delay=50)

    elif action_type == "key":
        key = action.get("text", "")
        # Map Claude's key names to Playwright key names
        key_map = {
            "Return": "Enter",
            "BackSpace": "Backspace",
            "space": " ",
            "Tab": "Tab",
            "Escape": "Escape",
            "Up": "ArrowUp",
            "Down": "ArrowDown",
            "Left": "ArrowLeft",
            "Right": "ArrowRight",
        }
        # Handle modifier combos like "ctrl+a"
        if "+" in key:
            parts = key.split("+")
            modifiers = []
            final_key = parts[-1]
            for mod in parts[:-1]:
                mod_lower = mod.lower().strip()
                if mod_lower in ("ctrl", "control"):
                    modifiers.append("Control")
                elif mod_lower in ("alt", "option"):
                    modifiers.append("Alt")
                elif mod_lower in ("shift",):
                    modifiers.append("Shift")
                elif mod_lower in ("meta", "super", "command", "cmd"):
                    modifiers.append("Meta")
            for m in modifiers:
                await page.keyboard.down(m)
            await page.keyboard.press(key_map.get(final_key, final_key))
            for m in reversed(modifiers):
                await page.keyboard.up(m)
        else:
            await page.keyboard.press(key_map.get(key, key))

    elif action_type == "scroll":
        x, y = action["coordinate"]
        direction = action.get("direction", "down")
        amount = action.get("amount", 3)
        delta = amount * 100
        if direction == "up":
            delta = -delta
        elif direction == "left":
            await page.mouse.move(x, y)
            await page.evaluate(f"window.scrollBy(-{delta}, 0)")
            await asyncio.sleep(0.3)
            return await _take_screenshot(page)
        elif direction == "right":
            await page.mouse.move(x, y)
            await page.evaluate(f"window.scrollBy({delta}, 0)")
            await asyncio.sleep(0.3)
            return await _take_screenshot(page)
        await page.mouse.move(x, y)
        await page.mouse.wheel(0, delta)

    elif action_type == "drag":
        sx, sy = action.get("start_coordinate", action.get("coordinate", [0, 0]))
        ex, ey = action["end_coordinate"]
        await page.mouse.move(sx, sy)
        await page.mouse.down()
        await page.mouse.move(ex, ey, steps=10)
        await page.mouse.up()

    elif action_type == "wait":
        await asyncio.sleep(action.get("duration", 2))

    # Brief pause after action, then screenshot
    await asyncio.sleep(0.5)
    return await _take_screenshot(page)


def _strip_images_for_storage(messages: list) -> list:
    """Strip base64 image data from messages before saving to DB.

    Replaces image content with a placeholder to keep message structure intact
    while avoiding multi-MB JSON in the database.
    """
    stripped = []
    for msg in messages:
        new_msg = {"role": msg["role"]}
        content = msg.get("content")
        if isinstance(content, list):
            new_content = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image":
                    new_content.append({"type": "text", "text": "[screenshot taken]"})
                elif isinstance(block, dict):
                    new_content.append(block)
                else:
                    # Anthropic response objects — serialize text only
                    if hasattr(block, "type"):
                        if block.type == "text":
                            new_content.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            new_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })
                    else:
                        new_content.append(block)
            new_msg["content"] = new_content
        else:
            new_msg["content"] = content
        stripped.append(new_msg)
    return stripped


async def _replay_actions(page: Page, actions: list[dict], resume_path: str, cover_letter_path: str) -> dict:
    """Replay saved form actions without any API calls.

    Executes each recorded action in sequence. If a file chooser triggers,
    handles it the same way the live loop does. Returns a result dict.
    """
    logger.info("Replaying %d saved actions (no API calls)", len(actions))
    for i, act in enumerate(actions):
        action_data = act["action_data"]
        action_type = act["action_type"]

        if action_type == "file_upload":
            # Recorded file upload — re-trigger via click + file chooser
            try:
                async with page.expect_file_chooser(timeout=3000) as fc_info:
                    x, y = action_data["coordinate"]
                    await page.mouse.click(x, y)
                chooser = await fc_info.value
                file_path = action_data.get("file_path", "")
                # Remap to current paths (may have changed)
                if "cover" in file_path.lower() and cover_letter_path:
                    await chooser.set_files(cover_letter_path)
                elif resume_path:
                    await chooser.set_files(resume_path)
                await asyncio.sleep(0.5)
            except (TimeoutError, PlaywrightTimeoutError):
                logger.warning("Replay step %d: file chooser not triggered, skipping", i)
        else:
            await _execute_action(page, action_data)

        # Human-like delay between actions to avoid spam detection
        await asyncio.sleep(random.uniform(0.8, 2.0))  # noqa: S311

        logger.debug("Replayed step %d/%d: %s", i + 1, len(actions), action_type)

    # Take final screenshot to check state
    final_screenshot = await _take_screenshot(page)
    return {
        "status": "ready_to_submit",
        "steps_taken": len(actions),
        "replayed": True,
        "final_screenshot_b64": final_screenshot,
    }


def _build_tools() -> list[dict]:
    """Build the Computer Use tool definition."""
    return [
        {
            "type": f"computer_{TOOL_VERSION}",
            "name": "computer",
            "display_width_px": DISPLAY_WIDTH,
            "display_height_px": DISPLAY_HEIGHT,
        }
    ]


async def _computer_use_loop(
    page: Page,
    task_prompt: str,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
    max_steps: int = 50,
    job_id: int | None = None,
    resume_state: dict | None = None,
) -> dict[str, Any]:
    """Run the Computer Use agentic loop.

    Claude sees screenshots, decides actions, we execute them via Playwright.
    Stops when Claude says it's done, we hit max_steps, or a pause is requested.

    If resume_state is provided, the loop resumes from saved state (messages + step).
    """
    start_step = 0
    if resume_state:
        start_step = resume_state.get("step", 0)
        logger.info("Resuming computer use loop from step %d (max_steps=%d)", start_step, max_steps)
    else:
        logger.info("Starting computer use loop (max_steps=%d)", max_steps)
    client = anthropic.Anthropic(max_retries=5)

    # Take initial screenshot
    initial_screenshot = await _take_screenshot(page)

    # Load screening answers knowledge base
    qa_path = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"
    screening_answers = {}
    if qa_path.exists():
        screening_answers = json.loads(qa_path.read_text())

    # Build contact info from either structured or string contact field
    contact = master_resume.get("contact", "")
    if isinstance(contact, dict):
        contact_info = (
            f"- Name: {master_resume.get('name', '')}\n"
            f"- Email: {contact.get('email', '')}\n"
            f"- Phone: {contact.get('phone', '')}\n"
            f"- Location: {contact.get('city', '')}, {contact.get('state', '')}\n"
            f"- LinkedIn: {contact.get('linkedin', '')}\n"
            f"- GitHub: {contact.get('github', '')}\n"
            f"- Website: {contact.get('website', '')}"
        )
    else:
        personal = screening_answers.get("personal", {})
        contact_info = (
            f"- Name: {personal.get('full_name', master_resume.get('name', ''))}\n"
            f"- Email: {personal.get('email', '')}\n"
            f"- Phone: {personal.get('phone', '')}\n"
            f"- Location: {personal.get('city', '')}, {personal.get('state', '')}\n"
            f"- LinkedIn: {personal.get('linkedin', '')}\n"
            f"- GitHub: {personal.get('github', '')}\n"
            f"- Website: {personal.get('website', '')}"
        )

    # Format screening Q&A for the prompt
    qa_sections = []
    if screening_answers.get("work_authorization"):
        wa = screening_answers["work_authorization"]
        qa_sections.append(
            "WORK AUTHORIZATION:\n"
            f"- Authorized to work in US: {'Yes' if wa.get('authorized_to_work_in_us') else 'No'}\n"
            f"- Require sponsorship: {'Yes' if wa.get('require_sponsorship') else 'No'}\n"
            f"- Visa status: {wa.get('visa_status', 'N/A')}"
        )
    if screening_answers.get("experience"):
        exp = screening_answers["experience"]
        exp_lines = [f"- {k.replace('years_', '').replace('_', ' ').title()}: {v}" for k, v in exp.items()]
        qa_sections.append("YEARS OF EXPERIENCE:\n" + "\n".join(exp_lines))
    if screening_answers.get("education"):
        edu = screening_answers["education"]
        qa_sections.append(
            "EDUCATION:\n"
            f"- Highest degree: {edu.get('highest_degree', '')}\n"
            f"- Field: {edu.get('degree_field', '')}\n"
            f"- University: {edu.get('university', '')}\n"
            f"- Graduation: {edu.get('graduation_year', '')}"
        )
    if screening_answers.get("job_preferences"):
        pref = screening_answers["job_preferences"]
        qa_sections.append(
            "JOB PREFERENCES:\n"
            f"- Desired salary: {pref.get('desired_salary', 'Negotiable')}\n"
            f"- Start date: {pref.get('start_date', 'Flexible')}\n"
            f"- Willing to relocate: {'Yes' if pref.get('willing_to_relocate') else 'No'}\n"
            f"- Remote preference: {pref.get('remote_preference', 'Open')}\n"
            f"- Travel: {pref.get('travel_percentage', 'N/A')}"
        )
    if screening_answers.get("common_questions"):
        cq = screening_answers["common_questions"]
        cq_lines = []
        for k, v in cq.items():
            if isinstance(v, bool):
                v = "Yes" if v else "No"
            label = k.replace("_", " ").title()
            cq_lines.append(f"Q: {label}\nA: {v}")
        qa_sections.append("COMMON SCREENING QUESTIONS:\n" + "\n\n".join(cq_lines))
    if screening_answers.get("diversity"):
        div = screening_answers["diversity"]
        qa_sections.append(
            "EEO/DIVERSITY (only if required):\n"
            f"- Gender: {div.get('gender', 'Prefer not to say')}\n"
            f"- Race/Ethnicity: {div.get('race_ethnicity', 'Prefer not to say')}\n"
            f"- Veteran: {div.get('veteran_status', 'Prefer not to say')}\n"
            f"- Disability: {div.get('disability_status', 'Prefer not to say')}"
        )

    qa_block = "\n\n".join(qa_sections)

    # Load cached answers from database
    from src.db.database import init_db as _init_db
    from src.db.database import list_answers
    _init_db()
    cached = list_answers(limit=100)
    cached_block = ""
    if cached:
        cached_lines = []
        for a in cached:
            cached_lines.append(f"Q: {a['question']}\nA: {a['answer']}")
        cached_block = "\n\n".join(cached_lines)

    # Static instructions (same across all applications — cached)
    static_instructions = """\
You are filling out a job application form in a web browser. You can see the page via screenshots and control it with mouse/keyboard actions.

ATS SYSTEM TIPS:
- Greenhouse (boards.greenhouse.io): Multi-step forms. Look for "Apply for this Job" button first. Resume upload usually on first page. Custom questions on later pages.
- Lever (jobs.lever.co): Single-page form usually. Resume upload + basic info + optional questions.
- Ashby (jobs.ashbyhq.com): Clean single-page forms. Resume upload with drag-and-drop or file picker.
- Workday (myworkdayjobs.com): Multi-step wizard. Often requires creating an account first — if login/signup appears, say BLOCKED.
- Taleo (taleo.net): Legacy multi-page forms. May have "autofill from resume" option — skip it, fill manually.
- iCIMS: Similar to Workday, may require account creation.
- If the form requires creating an account or logging in, say "BLOCKED: requires account creation" — do not create accounts.

Instructions:
1. Fill in all required fields using the applicant's information below
2. For file uploads (resume/cover letter): just click the upload button or file input area. The file dialog will be handled automatically — do NOT try to type file paths or navigate the OS file picker. After clicking upload, wait for the screenshot to confirm the file was attached.
3. Upload the cover letter PDF when asked for a cover letter separately
4. For screening questions, use the knowledge base below for consistent answers
5. For questions not in the knowledge base, answer based on the applicant's experience or select "Prefer not to say"
6. For salary fields, enter a reasonable range or leave blank if optional
7. For dropdown menus, click to open then select the closest matching option
8. If a field has autocomplete suggestions, type slowly and select the right match
9. When you reach the final submit button, STOP and say "READY_TO_SUBMIT" — do NOT click submit
10. If you encounter an error or get stuck, say "BLOCKED: <reason>"
11. Be careful and methodical. Check each field before moving on."""

    # Applicant-specific context (same across all steps within one application — cached)
    applicant_context = (
        f"Your task: {task_prompt}\n\n"
        f"APPLICANT INFORMATION:\n{contact_info}\n\n"
        f"Resume PDF: {resume_path}\n"
        f"Cover Letter PDF: {cover_letter_path}\n\n"
        f"SCREENING ANSWERS KNOWLEDGE BASE:\n{qa_block}\n\n"
        f"CACHED ANSWERS (previously used — prefer these for consistency):\n"
        f"{cached_block if cached_block else 'No cached answers yet.'}"
    )

    system_prompt = [
        {
            "type": "text",
            "text": static_instructions,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": applicant_context,
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if resume_state and resume_state.get("messages"):
        # Resuming: use saved messages but append a fresh screenshot of current page
        messages = resume_state["messages"]
        fresh_screenshot = await _take_screenshot(page)
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "The application was paused and has been resumed. "
                        "Here is the current state of the page. Continue where you left off."
                    ),
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": fresh_screenshot,
                    },
                },
            ],
        })
    else:
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Here is the current state of the application page. Please start filling it out.",
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": initial_screenshot,
                        },
                    },
                ],
            }
        ]

    result = {
        "status": "in_progress",
        "steps_taken": start_step,
        "screenshots": [],
    }

    # Record actions for replay on retry
    recorded_actions: list[dict] = []

    for step in range(start_step, max_steps):
        # Check for pause signal
        if job_id is not None and is_pause_requested(job_id):
            clear_pause_signal(job_id)
            # Strip base64 images from messages before saving (too large for DB)
            saveable_messages = _strip_images_for_storage(messages)
            last_screenshot = await _take_screenshot(page)
            from src.db.database import save_pause_state
            save_pause_state(job_id, step, saveable_messages, last_screenshot)
            result["status"] = "paused"
            result["steps_taken"] = step
            final_path = await _save_screenshot(page, f"paused_{job_id}")
            result["final_screenshot"] = final_path
            logger.info("Application paused at step %d for job %d", step, job_id)
            return result
        # Prune old screenshots to keep token count manageable
        pruned_messages = _prune_old_screenshots(messages, keep_recent=3)

        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=_build_tools(),
            messages=pruned_messages,
            betas=[BETA_HEADER],
        )

        # Process response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if Claude is done (no tool use, just text)
        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        text_blocks = [b for b in assistant_content if b.type == "text"]
        full_text = " ".join(b.text for b in text_blocks)

        if not tool_uses:
            # Claude sent only text — check for completion signals

            if "READY_TO_SUBMIT" in full_text:
                result["status"] = "ready_to_submit"
                result["steps_taken"] = step + 1
                result["recorded_actions"] = recorded_actions
                logger.info("Application form ready to submit after %d steps", step + 1)
                # Save actions immediately — form is filled, don't wait for approval
                if recorded_actions and task_prompt:
                    try:
                        import re as _re

                        from src.db.database import save_form_actions
                        url_match = _re.search(r"https?://\S+", task_prompt)
                        if url_match:
                            save_form_actions(url_match.group().rstrip("."), recorded_actions)
                    except Exception as e:
                        logger.warning("Could not save form actions: %s", e)
                break
            elif "BLOCKED" in full_text:
                result["status"] = "blocked"
                result["message"] = full_text
                logger.warning("Application blocked after %d steps: %s", step + 1, full_text[:200])
                result["steps_taken"] = step + 1
                break
            else:
                result["status"] = "completed"
                result["message"] = full_text
                result["steps_taken"] = step + 1
                break

        # Execute each tool use
        tool_results = []
        for tool_use in tool_uses:
            if tool_use.name == "computer":
                action = tool_use.input
                screenshot_b64 = None

                # For clicks, intercept file chooser dialogs before the click fires
                if action.get("action") == "left_click":
                    try:
                        async with page.expect_file_chooser(timeout=2000) as fc_info:
                            x, y = action["coordinate"]
                            await page.mouse.click(x, y)
                        # File dialog was triggered — pick the right file
                        chooser = await fc_info.value
                        file_to_upload = _pick_upload_file(
                            full_text, page.url, resume_path, cover_letter_path
                        )
                        if file_to_upload:
                            await chooser.set_files(file_to_upload)
                            logger.info("Uploaded file via chooser: %s", file_to_upload)
                        await asyncio.sleep(0.5)
                        screenshot_b64 = await _take_screenshot(page)
                        # Record as file upload
                        recorded_actions.append({
                            "action_type": "file_upload",
                            "action_data": {**action, "file_path": file_to_upload or ""},
                            "page_url": page.url,
                        })
                    except (TimeoutError, PlaywrightTimeoutError):
                        # No file dialog — normal click, take screenshot
                        screenshot_b64 = await _take_screenshot(page)
                        recorded_actions.append({
                            "action_type": action.get("action", "unknown"),
                            "action_data": action,
                            "page_url": page.url,
                        })
                else:
                    screenshot_b64 = await _execute_action(page, action)
                    recorded_actions.append({
                        "action_type": action.get("action", "unknown"),
                        "action_data": action,
                        "page_url": page.url,
                    })

                if screenshot_b64:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": screenshot_b64,
                                },
                            }
                        ],
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": [{"type": "text", "text": "Action executed."}],
                    })

        messages.append({"role": "user", "content": tool_results})
        result["steps_taken"] = step + 1

    else:
        result["status"] = "max_steps_reached"

    # Save final screenshot
    final_path = await _save_screenshot(page, "final_application_state")
    result["final_screenshot"] = final_path
    result["screenshots"].append(final_path)

    return result


async def fill_application(
    application_url: str,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
    job_id: int,
    headless: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    """Fill out a job application form using Claude Computer Use.

    Args:
        application_url: URL of the application page
        master_resume: User's master resume data
        resume_path: Path to the tailored resume PDF
        cover_letter_path: Path to the tailored cover letter PDF
        job_id: Job ID for tracking
        headless: Run browser without visible window
        resume: Resume from a previously paused state

    Returns:
        Dict with status, screenshots, and result info
    """
    # Load pause state if resuming
    resume_state = None
    if resume:
        from src.db.database import clear_pause_state, get_pause_state
        resume_state = get_pause_state(job_id)
        if resume_state:
            logger.info("Resuming application for job %d from step %d", job_id, resume_state["step"])
        else:
            logger.warning("No pause state found for job %d, starting fresh", job_id)

    logger.info("Starting application fill for job %d at %s", job_id, application_url)

    # Detect site for session loading
    from urllib.parse import urlparse

    domain = urlparse(application_url).netloc.lower()
    session_name = "default"
    if "linkedin.com" in domain:
        session_name = "linkedin"
    elif "indeed.com" in domain:
        session_name = "indeed"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
        # Load saved session if available
        if has_session(session_name):
            context_kwargs["storage_state"] = str(session_path(session_name))
            logger.info("Loaded browser session: %s", session_name)
        elif session_name != "default" and has_session("default"):
            context_kwargs["storage_state"] = str(session_path("default"))
            logger.info("Loaded default browser session")

        context = await browser.new_context(**context_kwargs)
        # Hide automation indicators from ATS anti-spam detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = await context.new_page()

        try:
            # Navigate to application page
            await page.goto(application_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let page fully render

            # Hybrid routing: Easy Apply (DOM selectors) vs Computer Use (screenshots)
            from src.agent.linkedin_apply import fill_easy_apply, is_easy_apply

            if await is_easy_apply(page):
                logger.info("LinkedIn Easy Apply detected — using DOM selectors")
                result = await fill_easy_apply(
                    page=page,
                    master_resume=master_resume,
                    resume_path=resume_path,
                    cover_letter_path=cover_letter_path,
                )
            else:
                # Check for cached actions from a previous attempt
                from src.db.database import get_form_actions
                cached_actions = get_form_actions(application_url)

                if cached_actions and not resume:
                    logger.info("Found %d cached actions — replaying", len(cached_actions))
                    await send_notification(
                        f"Replaying cached form for job #{job_id} ({len(cached_actions)} actions, no API calls)..."
                    )
                    try:
                        result = await _replay_actions(
                            page, cached_actions, resume_path, cover_letter_path
                        )
                        # Save screenshot for review
                        final_path = await _save_screenshot(page, "final_application_state")
                        result["final_screenshot"] = final_path
                    except Exception as replay_err:
                        logger.warning("Replay failed (%s), falling back to live mode", replay_err)
                        # Reload page and fall through to live mode
                        await page.goto(application_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)
                        cached_actions = None  # trigger live mode below

                if not cached_actions or resume:
                    logger.info("Standard application — using Computer Use")
                    result = await _computer_use_loop(
                        page=page,
                        task_prompt=(
                            f"Fill out this job application form at {application_url}. "
                            "Fill in all fields with the applicant's information. "
                            "Upload the resume and cover letter when prompted. "
                            "Do NOT click the final submit button — stop and say READY_TO_SUBMIT."
                        ),
                        master_resume=master_resume,
                        resume_path=resume_path,
                        cover_letter_path=cover_letter_path,
                        job_id=job_id,
                        resume_state=resume_state,
                    )

            # If paused, return immediately (state already saved to DB)
            if result["status"] == "paused":
                await browser.close()
                return result

            # Clear pause state on completion if we were resuming
            if resume_state:
                from src.db.database import clear_pause_state
                clear_pause_state(job_id)

            # If ready to submit, send screenshot for approval
            if result["status"] == "ready_to_submit":
                logger.info("Sending approval request for job %d", job_id)
                screenshot_path = result.get("final_screenshot")
                if screenshot_path:
                    await send_photo(
                        screenshot_path,
                        caption=f"Application for job #{job_id} is ready. Review the form above.",
                    )

                approved = await request_approval(
                    job_id,
                    f"Application form for job #{job_id} has been filled out. "
                    "A screenshot of the form was sent. "
                    "Reply *submit* to confirm submission or *skip* to cancel.",
                )

                if approved:
                    # Try direct DOM click on submit button (no API call needed)
                    submit_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button:has-text("Submit")',
                        'button:has-text("Apply")',
                        'button:has-text("Submit Application")',
                        'button:has-text("Submit application")',
                        'a:has-text("Submit")',
                    ]
                    clicked = False
                    for selector in submit_selectors:
                        try:
                            btn = await page.query_selector(selector)
                            if btn and await btn.is_visible():
                                await btn.click()
                                clicked = True
                                logger.info("Clicked submit via DOM selector: %s", selector)
                                break
                        except Exception:
                            continue

                    if not clicked:
                        # Fallback: use Claude to find and click the submit button
                        logger.info("No DOM submit button found, using Claude fallback")
                        try:
                            submit_screenshot = await _take_screenshot(page)
                            submit_response = anthropic.Anthropic(max_retries=5).beta.messages.create(
                                model=MODEL,
                                max_tokens=1024,
                                system="Click the submit/apply button on this page. Just click it, nothing else.",
                                tools=_build_tools(),
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "image",
                                                "source": {
                                                    "type": "base64",
                                                    "media_type": "image/jpeg",
                                                    "data": submit_screenshot,
                                                },
                                            },
                                            {"type": "text", "text": "Click the submit/apply button now."},
                                        ],
                                    }
                                ],
                                betas=[BETA_HEADER],
                            )
                            for block in submit_response.content:
                                if block.type == "tool_use" and block.name == "computer":
                                    await _execute_action(page, block.input)
                                    clicked = True
                        except Exception as e:
                            logger.warning("Claude submit fallback failed: %s", e)

                    # Wait for the page DOM to show a result message after submit
                    all_signals = [
                        "thank you", "application submitted", "successfully submitted",
                        "application received", "we received your", "you have applied",
                        "application complete", "submission confirmed", "has been submitted",
                        "something went wrong", "please try again",
                        "required field", "fix the following", "has been flagged",
                        "could not be submitted", "unable to submit",
                    ]
                    js_signals = "[" + ",".join(f"'{s}'" for s in all_signals) + "]"
                    try:
                        await page.wait_for_function(
                            f"""() => {{
                                const text = document.body.innerText.toLowerCase();
                                return {js_signals}.some(s => text.includes(s));
                            }}""",
                            timeout=20000,
                        )
                    except Exception:
                        # Fallback: wait for networkidle if no signal detected
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        # Extra pause for slow AJAX updates
                        await asyncio.sleep(3)

                    # Check for success/error indicators in the page
                    page_text = await page.inner_text("body")
                    page_lower = page_text.lower()
                    success_signals = [
                        "thank you", "application submitted", "successfully submitted",
                        "application received", "we received your", "you have applied",
                        "application complete", "submission confirmed", "has been submitted",
                        "under review", "under consideration",
                    ]
                    error_signals = [
                        "something went wrong", "please try again",
                        "required field", "fix the following", "has been flagged",
                        "could not be submitted", "unable to submit",
                        "flagged as", "possible spam", "not submitted",
                    ]

                    is_success = any(s in page_lower for s in success_signals)
                    is_error = any(s in page_lower for s in error_signals) and not is_success

                    confirmation_path = await _save_screenshot(page, f"submitted_{job_id}")
                    result["confirmation_screenshot"] = confirmation_path

                    # Extract the ATS message (first ~500 chars of visible text for reason)
                    ats_reason = None
                    for signal in (error_signals if is_error else success_signals):
                        idx = page_lower.find(signal)
                        if idx != -1:
                            # Grab surrounding context (up to 500 chars)
                            start = max(0, idx - 50)
                            ats_reason = page_text[start:start + 500].strip()
                            break

                    from src.db.database import log_application_event, update_application

                    current_url = page.url
                    was_replay = bool(result.get("replayed"))
                    steps = result.get("steps_taken", 0)

                    if is_error:
                        # Determine specific event type
                        is_flagged = any(
                            s in page_lower
                            for s in ("flagged", "spam", "possible spam")
                        )
                        event_type = "flagged" if is_flagged else "failed"

                        result["status"] = "failed"
                        result["message"] = ats_reason or "Submit clicked but page shows an error"
                        logger.warning("Post-submit page shows error for job %d", job_id)

                        log_application_event(
                            job_id=job_id,
                            event_type=event_type,
                            outcome="failure",
                            reason=ats_reason,
                            page_url=current_url,
                            screenshot_path=confirmation_path,
                            steps_taken=steps,
                            was_replay=was_replay,
                        )
                        update_application(
                            job_id,
                            status="failed",
                            submission_outcome="failure",
                            failure_reason=ats_reason,
                        )

                        await send_photo(
                            confirmation_path,
                            caption=(
                                f"Job #{job_id}: Application failed.\n"
                                f"Reason: {ats_reason or 'Unknown — review screenshot.'}"
                            ),
                        )
                    else:
                        result["status"] = "submitted"
                        logger.info("Application submitted for job %d", job_id)

                        log_application_event(
                            job_id=job_id,
                            event_type="submitted",
                            outcome="success",
                            reason=ats_reason,
                            page_url=current_url,
                            screenshot_path=confirmation_path,
                            steps_taken=steps,
                            was_replay=was_replay,
                        )
                        update_application(
                            job_id,
                            status="applied",
                            submission_outcome="success",
                            applied_at=datetime.now(UTC).isoformat(),
                        )

                        caption = f"Application for job #{job_id} submitted!"
                        if ats_reason:
                            caption += f"\n{ats_reason[:200]}"
                        await send_photo(confirmation_path, caption=caption)
                        await send_notification(f"Application for job #{job_id} submitted successfully.")

                    # Cache actions for replay if retried (e.g. same ATS form layout)
                    if result.get("recorded_actions"):
                        try:
                            from src.db.database import save_form_actions
                            save_form_actions(application_url, result["recorded_actions"])
                        except Exception as e:
                            logger.warning("Could not save form actions: %s", e)

                    # Save browser session for reuse
                    try:
                        await context.storage_state(path=str(session_path(session_name)))
                        logger.info("Saved browser session: %s", session_name)
                    except Exception as e:
                        logger.warning("Could not save browser session: %s", e)
                else:
                    result["status"] = "skipped_by_user"
                    logger.info("Application skipped by user for job %d", job_id)
                    from src.db.database import log_application_event
                    log_application_event(
                        job_id=job_id,
                        event_type="skipped",
                        outcome="unknown",
                        reason="Skipped by user at submit approval",
                        steps_taken=result.get("steps_taken", 0),
                    )
                    await send_notification(f"Application for job #{job_id} was skipped.")

                # Save actions even on skip — form was filled successfully
                if result.get("recorded_actions") and not result.get("replayed"):
                    try:
                        from src.db.database import save_form_actions
                        save_form_actions(application_url, result["recorded_actions"])
                    except Exception as e:
                        logger.warning("Could not save form actions: %s", e)

        except Exception as e:
            logger.exception("Application error for job %d", job_id)
            result = {
                "status": "error",
                "error": str(e),
                "steps_taken": 0,
            }
            # Save error screenshot
            error_path = None
            try:
                error_path = await _save_screenshot(page, f"error_{job_id}")
                result["error_screenshot"] = error_path
            except Exception as e2:
                logger.warning("Could not save error screenshot: %s", e2)
            # Log the error event
            try:
                from src.db.database import log_application_event, update_application
                log_application_event(
                    job_id=job_id,
                    event_type="error",
                    outcome="failure",
                    reason=str(e)[:500],
                    screenshot_path=error_path,
                )
                update_application(
                    job_id,
                    status="failed",
                    submission_outcome="failure",
                    failure_reason=str(e)[:500],
                )
            except Exception as e3:
                logger.warning("Could not log application error event: %s", e3)

        finally:
            await browser.close()

    return result
