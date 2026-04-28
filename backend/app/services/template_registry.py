"""Shared template registry for price list, order validation and printing."""

from pathlib import Path

from app.services.docx_service import TEMPLATES_DIR

SELLABLE_TEMPLATES = frozenset(
    {
        "zaiavlenie.docx",
        "DKP.docx",
        "akt_pp.docx",
        "doverennost.docx",
        "dkp_pieces.docx",
        "dkp_dar.docx",
        "mreo.docx",
        "prokuratura.docx",
        "number.docx",
        "gosuslugi_signup",
    }
)

PLATE_DOCUMENT_TEMPLATES = frozenset({"zaiavlenie_na_nomera.docx"})
PAYMENT_ONLY_TEMPLATES = frozenset({"gosuslugi_signup"})


def is_sellable_template(template_name: str) -> bool:
    return template_name in SELLABLE_TEMPLATES


def is_printable_template(template_name: str) -> bool:
    return template_name in (SELLABLE_TEMPLATES - PAYMENT_ONLY_TEMPLATES) or template_name in PLATE_DOCUMENT_TEMPLATES


def template_exists(template_name: str) -> bool:
    if template_name == "zaiavlenie_na_nomera.docx":
        return (TEMPLATES_DIR / template_name).is_file() or (TEMPLATES_DIR / "zaiavlenie.docx").is_file()
    return (TEMPLATES_DIR / template_name).is_file()


def supported_sellable_templates() -> set[str]:
    return PAYMENT_ONLY_TEMPLATES | {template for template in SELLABLE_TEMPLATES if template_exists(template)}
