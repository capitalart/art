
"""Static documentation pages served through Flask routes."""

from __future__ import annotations

from flask import Blueprint, render_template
from routes import utils

bp = Blueprint('documentation', __name__, url_prefix='/docs')

@bp.route('/project-readme')
def project_readme():
    """Render the main project README."""
    return render_template('documentation/project_readme.html', menu=utils.get_menu())

@bp.route('/changelog')
def changelog():
    """Show the project changelog."""
    return render_template('documentation/changelog.html', menu=utils.get_menu())

@bp.route('/qa-audit-index')
def qa_audit_index():
    """Overview page for QA audit reports."""
    return render_template('documentation/qa_audit_index.html', menu=utils.get_menu())

@bp.route('/task-list')
def task_list():
    """Display the internal task list."""
    return render_template('documentation/task_list.html', menu=utils.get_menu())

@bp.route('/delete-candidates')
def delete_candidates():
    """List documentation pages marked for potential deletion."""
    return render_template('documentation/delete_candidates.html', menu=utils.get_menu())

@bp.route('/sitemap')
def sitemap():
    """Site map for navigating documentation pages."""
    return render_template('documentation/sitemap.html', menu=utils.get_menu())

@bp.route('/api-reference')
def api_reference():
    """API reference index page."""
    return render_template('documentation/api_reference.html', menu=utils.get_menu())

@bp.route('/how-to-guides')
def how_to_guides():
    """Entry point for how-to guides."""
    return render_template('documentation/how_to_guides.html', menu=utils.get_menu())

@bp.route('/faq')
def faq():
    """Frequently asked questions."""
    return render_template('documentation/faq.html', menu=utils.get_menu())

@bp.route('/howto-home')
def howto_home():
    """How-to guide: Home page."""
    return render_template('documentation/howto_home.html', menu=utils.get_menu())

@bp.route('/howto-upload')
def howto_upload():
    """Guide for uploading artwork."""
    return render_template('documentation/howto_upload.html', menu=utils.get_menu())

@bp.route('/howto-analyze')
def howto_analyze():
    """Guide for running AI analysis."""
    return render_template('documentation/howto_analyze.html', menu=utils.get_menu())

@bp.route('/howto-gallery')
def howto_gallery():
    """Guide to the gallery views."""
    return render_template('documentation/howto_gallery.html', menu=utils.get_menu())

@bp.route('/howto-exports')
def howto_exports():
    """Guide for exporting listings."""
    return render_template('documentation/howto_exports.html', menu=utils.get_menu())

@bp.route('/howto-whisperer')
def howto_whisperer():
    """Guide for the Prompt Whisperer tool."""
    return render_template('documentation/howto_whisperer.html', menu=utils.get_menu())
