"""General informational pages: Privacy Policy, Terms, About, Contact."""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("info", __name__)


@bp.route("/privacy")
def privacy() -> str:
    """Display the Privacy Policy page."""
    return render_template("privacy.html")


@bp.route("/terms")
def terms() -> str:
    """Display the Terms & Limitations page."""
    return render_template("terms.html")


@bp.route("/about")
def about() -> str:
    """Display the About page."""
    return render_template("about.html")


@bp.route("/accessibility")
def accessibility() -> str:
    """Display the Accessibility page."""
    return render_template("accessibility.html")


@bp.route("/upgrade")
def upgrade() -> str:
    """Display the Upgrade to Premium page."""
    return render_template("upgrade.html")


@bp.route("/contact")
def contact() -> str:
    """Display the Contact page."""
    return render_template("contact.html")
