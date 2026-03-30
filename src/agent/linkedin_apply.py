"""LinkedIn Easy Apply form filling via DOM selectors.

Detects LinkedIn Easy Apply and fills forms using DOM-based selectors
instead of Computer Use (screenshot + Claude). Much faster and cheaper.

Falls back to Computer Use for non-LinkedIn or non-Easy Apply sites.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import anthropic
from playwright.async_api import Page

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Easy Apply modal selectors
MODAL_SELECTORS = {
    "modal": "div.jobs-easy-apply-modal, div[class*='easy-apply-modal']",
    "next_button": "button[aria-label='Continue to next step'], button[data-easy-apply-next-button]",
    "review_button": "button[aria-label='Review your application'], button[data-easy-apply-review-button]",
    "submit_button": "button[aria-label='Submit application'], button[data-easy-apply-submit-button]",
    "dismiss_button": "button[aria-label='Dismiss'], button.artdeco-modal__dismiss",
    "error_message": "div.artdeco-inline-feedback--error",
    "progress_bar": "progress.artdeco-completeness-meter-linear__progress-element",
}


@dataclass
class FormField:
    """A detected form field in the Easy Apply modal."""

    type: str  # text, textarea, select, radio, checkbox, file
    label: str
    element_selector: str
    options: list[str] = field(default_factory=list)
    required: bool = False
    value: str | None = None


async def is_easy_apply(page: Page) -> bool:
    """Detect if current page has a LinkedIn Easy Apply button."""
    try:
        button = await page.query_selector(
            "button.jobs-apply-button, button[class*='jobs-apply-button']"
        )
        if button:
            text = (await button.inner_text()).strip().lower()
            return "easy apply" in text
    except Exception:
        pass
    return False


async def _get_label_for(page: Page, element) -> str:
    """Get the label text for a form element."""
    # Try aria-label
    label = await element.get_attribute("aria-label")
    if label:
        return label.strip()

    # Try associated <label>
    el_id = await element.get_attribute("id")
    if el_id:
        label_el = await page.query_selector(f"label[for='{el_id}']")
        if label_el:
            return (await label_el.inner_text()).strip()

    # Try parent label
    parent = await element.evaluate_handle("el => el.closest('label')")
    if parent:
        try:
            text = await parent.evaluate("el => el.textContent")
            if text:
                return text.strip()
        except Exception:
            pass

    # Try preceding text/label in parent container
    parent_div = await element.evaluate_handle(
        "el => el.closest('.fb-dash-form-element, .jobs-easy-apply-form-section__grouping')"
    )
    if parent_div:
        try:
            label_el = await parent_div.evaluate_handle("el => el.querySelector('label, span.t-14')")
            if label_el:
                text = await label_el.evaluate("el => el.textContent")
                if text:
                    return text.strip()
        except Exception:
            pass

    # Fallback: placeholder
    placeholder = await element.get_attribute("placeholder")
    if placeholder:
        return placeholder.strip()

    return ""


async def _detect_fields(page: Page) -> list[FormField]:
    """Find all form fields in the current Easy Apply step."""
    fields = []

    # Text inputs
    for selector in [
        "input[type='text']", "input[type='tel']", "input[type='email']",
        "input[type='url']", "input[type='number']",
    ]:
        elements = await page.query_selector_all(
            f"{MODAL_SELECTORS['modal']} {selector}"
        )
        for el in elements:
            is_hidden = await el.evaluate("el => el.offsetParent === null")
            if is_hidden:
                continue
            label = await _get_label_for(page, el)
            required = await el.get_attribute("required") is not None
            fields.append(FormField(
                type="text",
                label=label,
                element_selector=f"{selector}",
                required=required,
            ))

    # Textareas
    elements = await page.query_selector_all(
        f"{MODAL_SELECTORS['modal']} textarea"
    )
    for el in elements:
        is_hidden = await el.evaluate("el => el.offsetParent === null")
        if is_hidden:
            continue
        label = await _get_label_for(page, el)
        required = await el.get_attribute("required") is not None
        fields.append(FormField(
            type="textarea",
            label=label,
            element_selector="textarea",
            required=required,
        ))

    # Select dropdowns
    elements = await page.query_selector_all(
        f"{MODAL_SELECTORS['modal']} select"
    )
    for el in elements:
        is_hidden = await el.evaluate("el => el.offsetParent === null")
        if is_hidden:
            continue
        label = await _get_label_for(page, el)
        options_els = await el.query_selector_all("option")
        options = []
        for opt in options_els:
            text = (await opt.inner_text()).strip()
            value = await opt.get_attribute("value")
            if text and value:
                options.append(text)
        required = await el.get_attribute("required") is not None
        fields.append(FormField(
            type="select",
            label=label,
            element_selector="select",
            options=options,
            required=required,
        ))

    # Radio button groups (fieldsets)
    fieldsets = await page.query_selector_all(
        f"{MODAL_SELECTORS['modal']} fieldset"
    )
    for fs in fieldsets:
        legend = await fs.query_selector("legend, span.fb-dash-form-element__label")
        label = (await legend.inner_text()).strip() if legend else ""
        radios = await fs.query_selector_all("input[type='radio']")
        options = []
        for radio in radios:
            radio_label = await _get_label_for(page, radio)
            if radio_label:
                options.append(radio_label)
        fields.append(FormField(
            type="radio",
            label=label,
            element_selector="fieldset",
            options=options,
        ))

    # Checkboxes (standalone, not in fieldsets)
    checkboxes = await page.query_selector_all(
        f"{MODAL_SELECTORS['modal']} input[type='checkbox']"
    )
    for cb in checkboxes:
        is_hidden = await cb.evaluate("el => el.offsetParent === null")
        if is_hidden:
            continue
        label = await _get_label_for(page, cb)
        fields.append(FormField(
            type="checkbox",
            label=label,
            element_selector="input[type='checkbox']",
        ))

    # File inputs
    file_inputs = await page.query_selector_all(
        f"{MODAL_SELECTORS['modal']} input[type='file']"
    )
    for fi in file_inputs:
        label = await _get_label_for(page, fi)
        fields.append(FormField(
            type="file",
            label=label,
            element_selector="input[type='file']",
        ))

    return fields


def _resolve_from_resume(label: str, master_resume: dict) -> str | None:
    """Try to resolve a field value directly from master resume data."""
    label_lower = label.lower()

    contact = master_resume.get("contact", {})
    if isinstance(contact, str):
        contact = {}

    # Order matters — more specific keys checked first
    mappings = [
        ("first name", master_resume.get("name", "").split()[0] if master_resume.get("name") else ""),
        ("last name", " ".join(master_resume.get("name", "").split()[1:]) if master_resume.get("name") else ""),
        ("full name", master_resume.get("name", "")),
        ("name", master_resume.get("name", "")),
        ("email", contact.get("email", "")),
        ("phone", contact.get("phone", "")),
        ("city", contact.get("city", "")),
        ("state", contact.get("state", "")),
        ("zip", contact.get("zip", "")),
        ("linkedin", contact.get("linkedin", "")),
        ("github", contact.get("github", "")),
        ("website", contact.get("website", "")),
        ("portfolio", contact.get("website", "")),
    ]

    for key, value in mappings:
        if key in label_lower and value:
            return value

    return None


def _resolve_from_answers(label: str, answers_db) -> str | None:
    """Try to resolve a field value from the answer cache."""
    if not answers_db:
        return None

    # Exact match
    from src.db.database import find_answer, find_answer_fuzzy
    result = find_answer(label)
    if result:
        return result["answer"]

    # Fuzzy match
    result = find_answer_fuzzy(label, threshold=0.65)
    if result:
        return result["answer"]

    return None


def _best_option_match(target: str, options: list[str]) -> str | None:
    """Find the best matching option from a list using fuzzy matching."""
    if not options or not target:
        return None

    target_lower = target.lower().strip()
    best_score = 0
    best_option = None

    for option in options:
        option_lower = option.lower().strip()

        # Exact match
        if target_lower == option_lower:
            return option

        # Contains match
        if target_lower in option_lower or option_lower in target_lower:
            return option

        # Fuzzy match
        score = SequenceMatcher(None, target_lower, option_lower).ratio()
        if score > best_score:
            best_score = score
            best_option = option

    return best_option if best_score >= 0.5 else None


async def _ask_claude_for_answer(question: str, options: list[str] | None, master_resume: dict) -> str:
    """Ask Claude Haiku for an answer to an unknown question."""
    client = anthropic.Anthropic()

    prompt = f"Answer this job application question concisely:\n\nQ: {question}"
    if options:
        prompt += f"\n\nOptions: {', '.join(options)}"
    prompt += "\n\nAnswer with just the answer text, nothing else."

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=200,
        system=(
            "You are filling out a job application. Answer questions based on the applicant's resume. "
            "Be concise. For yes/no questions, answer just 'Yes' or 'No'. "
            f"Applicant: {master_resume.get('name', 'Unknown')}"
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response.content[0].text.strip()

    # Cache the answer for reuse
    try:
        from src.db.database import save_answer
        save_answer(question, answer, source="llm", category="application")
    except Exception as e:
        logger.debug("Could not cache answer: %s", e)

    return answer


async def _fill_field(page: Page, field_info: FormField, value: str) -> bool:
    """Fill a single form field with the given value."""
    try:
        modal = await page.query_selector(MODAL_SELECTORS["modal"])
        if not modal:
            return False

        if field_info.type in ("text", "textarea"):
            elements = await modal.query_selector_all(field_info.element_selector)
            for el in elements:
                label = await _get_label_for(page, el)
                if label == field_info.label:
                    await el.click()
                    await el.fill("")  # Clear first
                    await el.fill(value)
                    logger.debug("Filled '%s' with '%s'", field_info.label, value[:50])
                    return True

        elif field_info.type == "select":
            elements = await modal.query_selector_all("select")
            for el in elements:
                label = await _get_label_for(page, el)
                if label == field_info.label:
                    match = _best_option_match(value, field_info.options)
                    if match:
                        await el.select_option(label=match)
                        logger.debug("Selected '%s' for '%s'", match, field_info.label)
                        return True

        elif field_info.type == "radio":
            fieldsets = await modal.query_selector_all("fieldset")
            for fs in fieldsets:
                legend = await fs.query_selector("legend, span.fb-dash-form-element__label")
                if legend and field_info.label in (await legend.inner_text()).strip():
                    radios = await fs.query_selector_all("input[type='radio']")
                    for radio in radios:
                        radio_label = await _get_label_for(page, radio)
                        if radio_label and _best_option_match(value, [radio_label]):
                            await radio.click()
                            logger.debug("Selected radio '%s' for '%s'", radio_label, field_info.label)
                            return True

        elif field_info.type == "checkbox":
            checkboxes = await modal.query_selector_all("input[type='checkbox']")
            for cb in checkboxes:
                label = await _get_label_for(page, cb)
                if label == field_info.label:
                    checked = await cb.is_checked()
                    should_check = value.lower() in ("yes", "true", "1", "checked")
                    if should_check != checked:
                        await cb.click()
                    logger.debug("Set checkbox '%s' to %s", field_info.label, should_check)
                    return True

        elif field_info.type == "file":
            file_inputs = await modal.query_selector_all("input[type='file']")
            for fi in file_inputs:
                label = await _get_label_for(page, fi)
                if label == field_info.label or not label:
                    if Path(value).exists():
                        await fi.set_input_files(value)
                        logger.debug("Uploaded file '%s' for '%s'", value, field_info.label)
                        return True

    except Exception as e:
        logger.warning("Failed to fill field '%s': %s", field_info.label, e)

    return False


async def _fill_current_step(
    page: Page,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
) -> int:
    """Detect and fill all fields in the current Easy Apply step.

    Returns count of fields filled.
    """
    fields = await _detect_fields(page)
    if not fields:
        return 0

    filled = 0
    for f in fields:
        value = None

        # Priority 1: Direct resume mapping
        if f.type in ("text", "textarea"):
            value = _resolve_from_resume(f.label, master_resume)

        # Priority 2: Answer cache
        if not value:
            value = _resolve_from_answers(f.label, True)

        # Priority 3: File upload
        if f.type == "file":
            label_lower = f.label.lower()
            if "resume" in label_lower or "cv" in label_lower:
                value = resume_path
            elif "cover" in label_lower:
                value = cover_letter_path
            elif resume_path:
                value = resume_path  # Default to resume

        # Priority 4: Select/radio — try answer cache then Claude
        if not value and f.type in ("select", "radio") and f.options:
            cached = _resolve_from_answers(f.label, True)
            if cached:
                value = cached
            else:
                value = await _ask_claude_for_answer(f.label, f.options, master_resume)

        # Priority 5: Claude for unknown text fields
        if not value and f.type in ("text", "textarea") and f.required:
            value = await _ask_claude_for_answer(f.label, None, master_resume)

        if value:
            success = await _fill_field(page, f, value)
            if success:
                filled += 1

    return filled


async def fill_easy_apply(
    page: Page,
    master_resume: dict,
    resume_path: str,
    cover_letter_path: str,
    max_steps: int = 15,
) -> dict:
    """Fill LinkedIn Easy Apply form using DOM selectors.

    Returns dict with status, steps_taken, message
    (Same format as computer_use.fill_application result)
    """
    logger.info("Starting Easy Apply form fill")

    result = {
        "status": "in_progress",
        "steps_taken": 0,
        "screenshots": [],
    }

    # Click the Easy Apply button
    try:
        apply_btn = await page.query_selector(
            "button.jobs-apply-button, button[class*='jobs-apply-button']"
        )
        if apply_btn:
            await apply_btn.click()
            await asyncio.sleep(1.5)
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Could not click Easy Apply button: {e}"
        return result

    # Wait for modal to appear
    try:
        await page.wait_for_selector(MODAL_SELECTORS["modal"], timeout=5000)
    except Exception:
        result["status"] = "blocked"
        result["message"] = "Easy Apply modal did not open"
        return result

    for step in range(max_steps):
        result["steps_taken"] = step + 1

        # Fill fields in current step
        filled = await _fill_current_step(page, master_resume, resume_path, cover_letter_path)
        logger.info("Easy Apply step %d: filled %d fields", step + 1, filled)

        await asyncio.sleep(0.5)

        # Check for errors
        errors = await page.query_selector_all(MODAL_SELECTORS["error_message"])
        if errors:
            for err in errors:
                err_text = (await err.inner_text()).strip()
                if err_text:
                    logger.warning("Form error: %s", err_text)

        # Try to advance: Review > Next > Submit
        advanced = False

        # Check for submit button (final step)
        submit_btn = await page.query_selector(MODAL_SELECTORS["submit_button"])
        if submit_btn:
            is_visible = await submit_btn.evaluate("el => el.offsetParent !== null")
            if is_visible:
                result["status"] = "ready_to_submit"
                result["message"] = "Easy Apply form ready to submit"
                # Save screenshot of review page
                from src.agent.computer_use import _save_screenshot
                final_path = await _save_screenshot(page, "easy_apply_review")
                result["final_screenshot"] = final_path
                logger.info("Easy Apply ready to submit after %d steps", step + 1)
                return result

        # Check for review button
        review_btn = await page.query_selector(MODAL_SELECTORS["review_button"])
        if review_btn:
            is_visible = await review_btn.evaluate("el => el.offsetParent !== null")
            if is_visible:
                await review_btn.click()
                await asyncio.sleep(1)
                advanced = True

        # Check for next button
        if not advanced:
            next_btn = await page.query_selector(MODAL_SELECTORS["next_button"])
            if next_btn:
                is_visible = await next_btn.evaluate("el => el.offsetParent !== null")
                if is_visible:
                    await next_btn.click()
                    await asyncio.sleep(1)
                    advanced = True

        if not advanced:
            # No button found — might be done or stuck
            # Check if modal is still open
            modal = await page.query_selector(MODAL_SELECTORS["modal"])
            if not modal:
                result["status"] = "completed"
                result["message"] = "Easy Apply modal closed"
                return result

            # Stuck — no buttons to click
            result["status"] = "blocked"
            result["message"] = "No next/review/submit button found"
            return result

    result["status"] = "max_steps_reached"
    result["message"] = f"Reached max {max_steps} steps"
    return result
