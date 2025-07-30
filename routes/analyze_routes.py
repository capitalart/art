# /home/dream/dreamartmachine/routes/analyze_routes.py
# ==============================================================================
# 📄 File: analyze_routes.py (DreamArtMachine Artwork Analysis & Management Routes)
# 📅 Last Modified: 10 June 2025 (Definitive rewrite to fix all data handling, display, and async bugs)
# ==============================================================================

# === [ analyze-routes-py-1: Imports and Global Setup ] ===
import logging
import json
import os
import shutil
import re
import urllib.parse
import base64
import csv
from io import StringIO
import math
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

from fastapi import (
    APIRouter, Request, Depends, Form, HTTPException, status, Query, File, UploadFile
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.datastructures import URL
from starlette.routing import NoMatchFound
import openai

from .. import crud
from ..models import Artwork, User as UserModel
from ..config import settings
from ..database import get_db
from ..dependencies import login_required, get_current_active_user
from ..utils.template_engine import templates
from ..services.artwork_analysis_service import analyze_single_artwork, update_artwork_with_analysis_results
from ..utils.content_blocks import (
    get_aspect_ratio_block,
    get_dot_painting_history_block,
)
from ..utils.file_utils import (
    get_artwork_display_url,
    generate_seo_filename as generate_seo_filename_util,
    generate_sku as generate_sku_util,
    organize_artwork_files,
    archive_original_file as archive_original_file_util,
    restore_archived_file as restore_archived_file_util,
    clean_tags_for_etsy,
    get_image_path_for_openai_analysis,
)
from ..utils.template_helpers import clean_listing_text
from ..utils.ai_utils import get_ai_profile_settings, get_short_prompt_hint, execute_openai_vision_analysis

router = APIRouter(prefix="/analyze", tags=["Artwork Analysis & Management"], dependencies=[Depends(login_required)])
logger = logging.getLogger(__name__)

# Module-level constants
AI_PROFILE_SETTINGS_FILE_PATH = settings.AI_PROFILE_SETTINGS_FILE
ETSY_MASTER_TEMPLATE_PATH = settings.ETSY_MASTER_TEMPLATE_PATH
FINALISED_ART_DIR_PATH = settings.FINALIZED_ARTWORK_DIR_ABSOLUTE
# === [ End of Section 1 ] ===


# === [ analyze-routes-py-2: Internal Helper Functions ] ===
def _get_artwork_or_404(artwork_id: int, db: Session, current_user: UserModel) -> Artwork:
    """Synchronous helper to fetch an artwork or raise 404/403."""
    artwork = crud.get_artwork(db, artwork_id=artwork_id)
    if not artwork:
        logger.warning(f"Artwork ID {artwork_id} not found (access by {current_user.username}).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artwork ID {artwork_id} not found.")
    if not current_user.is_superuser and artwork.user_id != current_user.id:
        logger.warning(f"Unauthorized access attempt by {current_user.username} to Artwork ID {artwork_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this artwork.")
    return artwork
# === [ End of Section 2 ] ===


# === [ analyze-routes-py-3: Main Analysis Dashboard Route ] ===
@router.get("/", response_class=HTMLResponse, name="analyze_artworks_page")
async def display_analysis_dashboard(
    request: Request, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user),
    artwork_id: Optional[int] = Query(None), processed_artwork_id: Optional[int] = Query(None),
    artwork_filename: Optional[str] = Query(None),
    message: Optional[str] = Query(None), error_message: Optional[str] = Query(None)
):
    """Displays the main artwork analysis dashboard, populating it with data for a selected artwork if provided."""
    logger.info(f"User '{current_user.username}' accessed /analyze with artwork_id={artwork_id}")
    
    available_ai_profiles, current_ai_profile_key = [], "EtsyAustralianArt"
    try:
        with AI_PROFILE_SETTINGS_FILE_PATH.open("r", encoding="utf-8") as f:
            settings_json = json.load(f)
        available_ai_profiles = list(settings_json.get("profiles", {}).keys())
        current_ai_profile_key = settings_json.get(
            "current_profile",
            available_ai_profiles[0] if available_ai_profiles else current_ai_profile_key,
        )
    except Exception as e:
        logger.error(f"Failed to load AI profiles: {e}")
        error_message = "Could not load AI profiles from settings."

    display_id = processed_artwork_id or artwork_id
    artwork = _get_artwork_or_404(display_id, db, current_user) if display_id else crud.get_artwork_by_filename(db, filename=artwork_filename) if artwork_filename else None

    form_details = {}
    parsed_tags_for_preview = []
    if artwork:
        form_details = {
            "id": artwork.id, "filename": artwork.original_filename,
            "title_for_form": artwork.generated_title or get_short_prompt_hint(artwork.original_filename),
            "image_url_for_form_preview": get_artwork_display_url(request, artwork.thumb_path, artwork.status),
            "viewer_page_url_for_full_size_image": str(request.url_for('view_full_size_artwork_image_on_analyze', artwork_id=artwork.id)),
            "aspect_ratio_for_form": artwork.aspect_ratio_str,
            "description_from_db": artwork.generated_description or "",
            "tags_input_from_db": artwork.generated_tags_keywords or "",
            "notes_from_db": artwork.notes or "", "current_status": artwork.status,
            "resolution_metric": artwork.resolution, "dpi_metric": artwork.dpi,
            "filesize_metric": artwork.file_size_mb_str, "icc_profile_metric": artwork.icc_profile_name,
        }
        if artwork.generated_tags_keywords:
            try:
                tags_list = json.loads(artwork.generated_tags_keywords)
                parsed_tags_for_preview = clean_tags_for_etsy(json.dumps(tags_list))
            except (json.JSONDecodeError, TypeError):
                parsed_tags_for_preview = clean_tags_for_etsy(artwork.generated_tags_keywords)

    gallery_raw = crud.get_artworks_ordered_by_timestamp_paginated(
        db, limit=50, owner_id=None if current_user.is_superuser else current_user.id
    )
    artworks_for_gallery = [
        {
            "id": art.id,
            "original_filename": art.original_filename,
            "thumb_url": get_artwork_display_url(request, art.thumb_path, art.status),
            "status_raw": art.status or "unknown",
            "status_display": (art.status or "Unknown").replace("_", " ").title(),
            "generated_title_display": art.generated_title or get_short_prompt_hint(art.original_filename),
            "sku_display": art.sku,
        }
        for art in gallery_raw
    ]

    context = {
        "page_title": "Analyze Artwork & Generate Listings",
        "artworks_for_gallery": artworks_for_gallery,
        "selected_artwork_for_form": form_details,
        "ai_listing_preview_artwork": artwork,
        "parsed_tags_for_preview": parsed_tags_for_preview,
        "available_ai_profiles": available_ai_profiles,
        "current_ai_profile_key": current_ai_profile_key,
        "message": message,
        "error_message": error_message,
        "current_user": current_user,
        "current_page_nav": "analyze",
    }
    return templates.TemplateResponse(request, "analyze.html", context)
# === [ End of Section 3 ] ===

# === [ analyze-routes-py-4: Artwork Viewer Route ] ===
@router.get("/viewer/{artwork_id}", response_class=HTMLResponse, name="view_full_size_artwork_image_on_analyze")
async def view_full_size_artwork_image_analyze_context_route(
    artwork_id: int, request: Request, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)
):
    """Displays the full-size image in a viewer page, in the context of the analyze workflow."""
    artwork = _get_artwork_or_404(artwork_id, db, current_user)

    path_for_viewer_str: Optional[str] = None
    if artwork.status in ["finalized", "ready_for_export"] and artwork.renamed_artwork_path:
         path_for_viewer_str = artwork.renamed_artwork_path
    else:
         path_for_viewer_str = artwork.original_file_storage_path

    full_image_url = get_artwork_display_url(request, path_for_viewer_str, artwork.status)
    from starlette.datastructures import URL
    back_url = str(URL(str(request.url_for('analyze_artworks_page'))).include_query_params(artwork_id=artwork_id))

    context = {
        "artwork_id": artwork.id,
        "artwork_title": artwork.generated_title or artwork.original_filename,
        "full_image_url": full_image_url,
        "back_to_analyze_url": back_url,
    }
    return templates.TemplateResponse(request, "full_image_viewer.html", context)


# === [ analyze-routes-py-4b: Trigger Analysis by Artwork ID Route | PATCHED FOR TYPE SAFETY ] ===
@router.post("/{artwork_id}/by-ai", name="trigger_ai_analysis")
async def trigger_ai_analysis_route(
    artwork_id: int,
    request: Request,
    profile_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """
    Initiates AI analysis for a single artwork and redirects back.

    Accepts either an artwork_id (int) or full Artwork object.
    All handling is now type-safe.
    """
    logger.info(f"User '{current_user.username}' requested AI analysis for artwork ID {artwork_id}.")
    analyze_page_url = str(request.url_for("analyze_artworks_page"))
    
    # Always fetch Artwork by ID, so we have the freshest data
    try:
        artwork_db = _get_artwork_or_404(int(artwork_id), db, current_user)
    except Exception as e:
        error_msg = f"Artwork not found or not accessible: {e}"
        logger.error(error_msg)
        return RedirectResponse(
            f"{analyze_page_url}?artwork_id={artwork_id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )

    # Run AI analysis (returns a dict or None)
    try:
        analysis_results = await analyze_single_artwork(
            db,
            artwork_db,
            current_user,
            profile_key_override=profile_key,
        )
    except Exception as e:
        error_msg = f"AI analysis crashed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )
    if not analysis_results:
        error_msg = f"AI analysis failed: {getattr(analysis_results, 'error', 'Unknown error')}"
        logger.error(error_msg)
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )

    # Update artwork with results (always pass ID, never Artwork object!)
    try:
        update_success = update_artwork_with_analysis_results(db, artwork_db.id, analysis_results)
    except Exception as e:
        error_msg = f"Error updating artwork with analysis results: {str(e)}"
        logger.error(error_msg, exc_info=True)
        update_success = False

    if not update_success:
        error_msg = "Failed to save AI analysis results to the database."
        logger.error(error_msg)
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )

    success_msg = "Artwork analyzed successfully."
    return RedirectResponse(
        f"{analyze_page_url}?processed_artwork_id={artwork_id}&message={urllib.parse.quote(success_msg)}",
        status_code=303,
    )
# === [ End of Section 4b | PATCHED FOR TYPE SAFETY ] ===

# === [ analyze-routes-py-5: AI Analysis Form Submission Route ] ===
@router.post("/process-analysis-vision/", name="process_analysis_form_submission_vision_original")
async def process_analysis_form_submission_original_vision_route(
    request: Request, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user),
    original_filename: str = Form(...), ai_profile_key: str = Form(...),
    description: str = Form(""), tags_input: str = Form(""), user_notes: Optional[str] = Form(None)
):
    """Handles the AI analysis form submission.

    This route must remain named ``process_analysis_form_submission_vision_original``
    so that ``url_for('process_analysis_form_submission_vision_original')`` in
    ``templates/analyze.html`` resolves correctly.
    """
    logger.info(
        f"User '{current_user.username}' POST /process-analysis-vision/ for '{original_filename}', Profile: '{ai_profile_key}'."
    )

    analyze_page_url = str(request.url_for('analyze_artworks_page'))

    # -------------------------------------------------------------------------
    # 1. Lookup artwork in DB
    # -------------------------------------------------------------------------
    artwork_db = crud.get_artwork_by_filename(db, filename=original_filename)
    if not artwork_db:
        error_msg = f"Artwork '{original_filename}' not found or is archived. Cannot perform AI analysis."
        logger.error(error_msg)
        return RedirectResponse(
            f"{analyze_page_url}?error_message={urllib.parse.quote(error_msg)}&artwork_filename={urllib.parse.quote(original_filename)}",
            status_code=303,
        )

    # -------------------------------------------------------------------------
    # 2. Perform AI analysis
    # -------------------------------------------------------------------------
    analysis_results = await analyze_single_artwork(
        db,
        artwork_db,
        current_user,
        profile_key_override=ai_profile_key,
        user_notes_override=user_notes or description,
    )

    if analysis_results:
        update_artwork_with_analysis_results(db, artwork_db.id, analysis_results)
        db.refresh(artwork_db)
    else:
        error_msg = "AI analysis failed"
        logger.error(error_msg)
        artwork_db.status = "error_ai_analysis"
        db.commit()
        redirect_url = (
            f"{analyze_page_url}?processed_artwork_id={artwork_db.id}&error_message={urllib.parse.quote(error_msg)}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    # -------------------------------------------------------------------------
    # 3. Generate SKU and SEO filename
    # -------------------------------------------------------------------------
    if not artwork_db.sku:
        artwork_db.sku = generate_sku_util(db, "RC")
    if not artwork_db.seo_filename:
        artwork_db.seo_filename = generate_seo_filename_util(
            title=artwork_db.generated_title or "artwork",
            sku=artwork_db.sku,
            file_extension=Path(artwork_db.original_filename).suffix.lstrip("."),
        )
    db.commit()

    # -------------------------------------------------------------------------
    # 4. Move artwork files to finalized location
    # -------------------------------------------------------------------------
    try:
        from ..utils.file_utils import move_files_to_finalized_artwork

        temp_folder = artwork_db.artwork_base_folder_path or Path(artwork_db.original_file_storage_path).parent
        final_paths = move_files_to_finalized_artwork(
            temp_folder=str(temp_folder),
            seo_filename=Path(artwork_db.seo_filename).stem,
            final_folder=str(settings.FINALIZED_ARTWORK_DIR_ABSOLUTE),
            create_subfolder=True,
        )

        if final_paths and final_paths.get("main_artwork_path"):
            artwork_db.renamed_artwork_path = final_paths.get("main_artwork_path")
            artwork_db.thumb_path = final_paths.get("thumbnail_path")
            artwork_db.openai_image_path = final_paths.get("openai_variant_path")
            artwork_db.artwork_base_folder_path = final_paths.get(
                "artwork_folder", artwork_db.artwork_base_folder_path
            )
            artwork_db.original_file_storage_path = final_paths.get("main_artwork_path")
            artwork_db.status = "finalized"
            artwork_db.finalized_at = datetime.now(timezone.utc)
            db.commit()
        else:
            raise Exception("move_files_to_finalized_artwork returned invalid paths")
    except Exception as e_move:
        logger.error(f"File move during analysis failed for artwork ID {artwork_db.id}: {e_move}", exc_info=True)
        error_msg = f"Artwork '{original_filename}' analyzed but file move failed."
        redirect_url = (
            f"{analyze_page_url}?processed_artwork_id={artwork_db.id}&error_message={urllib.parse.quote(error_msg)}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    # -------------------------------------------------------------------------
    # 5. Trigger mockup generation from finalized file
    # -------------------------------------------------------------------------
    try:
        from scripts.generate_composites import generate_composites_for_artwork
        result = generate_composites_for_artwork(artwork_db.seo_filename)
        if not result.get("success"):
            logger.warning(f"Mockup generation warning: {result.get('message')}")
    except Exception as e:
        logger.error(f"Mockup generation failed after analysis: {e}", exc_info=True)

    # -------------------------------------------------------------------------
    # 6. Redirect to /edit-listing/<aspect>/<filename> page
    # -------------------------------------------------------------------------
    try:
        aspect_folder = artwork_db.aspect_ratio or "4x5"
        seo_filename = Path(artwork_db.seo_filename).stem
        edit_url = f"/edit-listing/{aspect_folder}/{seo_filename}.jpg"
        logger.info(f"Redirecting to listing editor: {edit_url}")
        return RedirectResponse(url=edit_url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to redirect to edit listing: {e}", exc_info=True)
        fallback_msg = f"Artwork analyzed but redirect to editor failed: {e}"
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_db.id}&error_message={urllib.parse.quote(fallback_msg)}",
            status_code=status.HTTP_303_SEE_OTHER
        )


# === [ Section 6: Accept & Finalize Artwork Route ] ===
@router.post("/accept-finalize/{artwork_id}", name="accept_finalize_artwork_and_organize_files")
async def accept_and_finalize_artwork_route(
    artwork_id: int, request: Request, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)
):
    """Finalizes an artwork, renaming and moving files to their permanent location."""
    logger.info(f"User '{current_user.username}' initiating ACCEPT & FINALIZE for artwork ID: {artwork_id}")
    artwork_db = _get_artwork_or_404(artwork_id, db, current_user)
    analyze_page_url = str(request.url_for('analyze_artworks_page'))

    missing_keys = [key for key in ["original_file_storage_path", "generated_title", "sku", "seo_filename"] if not getattr(artwork_db, key)]
    if missing_keys:
        error_msg = f"Cannot finalize: Missing required data: {', '.join(missing_keys)}."
        logger.error(error_msg)
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )

    try:
        from ..utils.file_utils import move_files_to_finalized_artwork

        temp_folder = artwork_db.artwork_base_folder_path or Path(artwork_db.original_file_storage_path).parent
        final_paths = move_files_to_finalized_artwork(
            temp_folder=str(temp_folder),
            seo_filename=Path(artwork_db.seo_filename).stem,
            final_folder=str(settings.FINALIZED_ARTWORK_DIR_ABSOLUTE),
            create_subfolder=True,
        )
        if not final_paths or not final_paths.get("main_artwork_path"):
            raise Exception("move_files_to_finalized_artwork did not return expected paths")
    except Exception as e_org:
        logger.error(f"File move failed for artwork ID {artwork_id}: {e_org}", exc_info=True)
        artwork_db.status = "error_file_move"
        db.commit()
        return RedirectResponse(
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message=File+move+failed.",
            status_code=303,
        )

    # Update artwork with final paths and status
    artwork_db.renamed_artwork_path = final_paths.get("main_artwork_path")
    artwork_db.thumb_path = final_paths.get("thumbnail_path")
    artwork_db.openai_image_path = final_paths.get("openai_variant_path")
    artwork_db.artwork_base_folder_path = final_paths.get("artwork_folder", artwork_db.artwork_base_folder_path)
    artwork_db.original_file_storage_path = final_paths.get("main_artwork_path")
    artwork_db.status = "finalized"
    artwork_db.finalized_at = datetime.now(timezone.utc)
    artwork_db.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        logger.info(f"Artwork ID {artwork_db.id} finalized successfully.")
        success_msg = f"Artwork '{artwork_db.seo_filename}' finalized and organized successfully!"
        redirect_url = f"{analyze_page_url}?processed_artwork_id={artwork_id}&message={urllib.parse.quote(success_msg)}"
    except Exception as e_commit:
        db.rollback()
        logger.error(
            f"DB commit error after finalizing artwork ID {artwork_id}: {e_commit}",
            exc_info=True,
        )
        redirect_url = (
            f"{analyze_page_url}?processed_artwork_id={artwork_id}&error_message=Database+save+failed+after+finalization."
        )

    return RedirectResponse(url=redirect_url, status_code=303)

# ==============================================================================
# SECTION 7: ADDITIONAL ARTWORK ACTIONS
# ==============================================================================

# ------------------------------------------------------------------------------
# 7.1: Mark Artwork as Ready for Export
# ------------------------------------------------------------------------------

@router.post("/mark-ready-export/{artwork_id}", name="mark_artwork_ready_for_export")
async def mark_artwork_ready_for_export_route(
    artwork_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Marks a finalized artwork as ready for export. Updates the status to 'ready_for_export'
    and returns user back to the Analyze Artworks admin page.
    """
    logger.info(f"User '{current_user.username}' marking artwork ID {artwork_id} as ready for export.")
    analyze_page_url = str(request.url_for('analyze_artworks_page'))
    artwork_db = _get_artwork_or_404(artwork_id, db, current_user)

    # --- Prevent marking if not finalized ---
    if artwork_db.status != "finalized":
        error_msg = (
            f"Artwork ID {artwork_db.id} must be finalized before marking ready for export. "
            f"Current status: {artwork_db.status}"
        )
        return RedirectResponse(
            f"{analyze_page_url}?artwork_id={artwork_db.id}&error_message={urllib.parse.quote(error_msg)}",
            status_code=303,
        )

    # --- Update fields ---
    artwork_db.ready_for_export = True
    artwork_db.status = "ready_for_export"
    artwork_db.updated_at = datetime.now(timezone.utc)

    # --- Commit changes or handle DB error ---
    try:
        db.commit()
        db.refresh(artwork_db)
        message = f"Artwork ID {artwork_db.id} marked ready for export."
    except Exception as e:
        db.rollback()
        message = f"DB error marking artwork ID {artwork_db.id} ready for export: {e}"
        logger.error(message, exc_info=True)
        return RedirectResponse(
            f"{analyze_page_url}?artwork_id={artwork_db.id}&error_message={urllib.parse.quote(message)}",
            status_code=303,
        )

    return RedirectResponse(
        f"{analyze_page_url}?processed_artwork_id={artwork_db.id}&message={urllib.parse.quote(message)}",
        status_code=303,
    )


# ==============================================================================
# SECTION 8: FULL LISTING PREVIEW PAGE
# ==============================================================================

# ------------------------------------------------------------------------------
# 8.1: Etsy/Nembol Preview for Single Artwork
# ------------------------------------------------------------------------------

@router.get("/full-preview/{artwork_id}", response_class=HTMLResponse, name="full_listing_preview_page")
async def full_listing_preview_page(
    artwork_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """
    Displays a full Etsy/Nembol preview of the generated listing data for a specific artwork.
    Replaces blocks in the Etsy master template based on artwork metadata and aspect ratio.
    """
    logger.info(f"User '{current_user.username}' generating full listing preview for ArtID: {artwork_id}")
    artwork = _get_artwork_or_404(artwork_id, db, current_user)

    assembled_description = "Error: Master Etsy template file could not be processed."
    aspect_ratio_key = "2:3"

    try:
        if ETSY_MASTER_TEMPLATE_PATH.is_file():
            master_template = clean_listing_text(ETSY_MASTER_TEMPLATE_PATH.read_text(encoding="utf-8"))

            # --- Determine aspect ratio key ---
            if artwork.aspect_ratio_str:
                match = re.match(r"(\d+:\d+)", artwork.aspect_ratio_str)
                if match:
                    aspect_ratio_key = match.group(1)
                elif artwork.width and artwork.height:
                    from ..utils.image_processing_utils import parse_aspect_ratio
                    aspect_ratio_key = parse_aspect_ratio(artwork.width, artwork.height)[0].split(" ")[0]

            # --- Load blocks ---
            aspect_details_block = get_aspect_ratio_block(aspect_ratio_key)
            dot_painting_block = (
                get_dot_painting_history_block()
                if artwork.ai_profile_used and "aboriginal" in artwork.ai_profile_used.lower()
                else ""
            )

            # --- Replace tokens in template ---
            assembled_description = (
                master_template
                .replace("{AI_GENERATED_TITLE}", artwork.generated_title or "")
                .replace("{AI_GENERATED_FULL_DESCRIPTION_CONTENT}", artwork.generated_description or "")
                .replace("{ASPECT_RATIO_DETAILS_BLOCK}", aspect_details_block)
                .replace("{CONDITIONAL_DOT_PAINTING_HISTORY_BLOCK}", dot_painting_block)
                .replace("https://www.etsy.com/au/shop/RobinCustance", settings.ETSY_SHOP_URL or "#")
            )
            assembled_description = clean_listing_text(assembled_description)
        else:
            logger.error(f"Etsy master template not found at: {ETSY_MASTER_TEMPLATE_PATH}")
    except Exception as e:
        logger.error(f"Error assembling listing description for ArtID {artwork.id}: {e}", exc_info=True)

    context = {
        "page_title": f"Listing Preview: {artwork.generated_title or artwork.original_filename}",
        "artwork_db_id": artwork.id,
        "artwork_title": artwork.generated_title,
        "artwork_status": artwork.status,
        "assembled_listing_description": assembled_description,
        "etsy_shop_url": settings.ETSY_SHOP_URL,
        "current_user": current_user,
    }
    return templates.TemplateResponse(request, "full_listing_preview.html", context)


# ==============================================================================
# SECTION 9: ADMIN + ANALYSIS API ROUTES
# ==============================================================================

# ------------------------------------------------------------------------------
# 9.1: Admin View of Individual Artwork
# ------------------------------------------------------------------------------

@router.get("/admin/artwork/{artwork_id}", response_class=HTMLResponse, name="admin_artwork_detail_page")
async def admin_artwork_detail_route(
    artwork_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """(Admin) Displays a detailed view of an individual artwork."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")

    artwork = _get_artwork_or_404(artwork_id, db, current_user)
    context = {"page_title": f"Admin View: {artwork.original_filename}", "artwork": artwork}
    return templates.TemplateResponse(request, "artwork_admin_details.html", context)


# ------------------------------------------------------------------------------
# 9.2: API – Get Artworks for Gallery Display
# ------------------------------------------------------------------------------

@router.get("/artworks-for-analysis", response_model=Optional[List[Dict[str, Any]]], name="json_artworks_for_analysis_gallery")
async def get_artworks_for_analysis_gallery_api(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns artwork metadata for the Analyze Gallery grid.
    Filters by multiple artwork statuses.
    """
    gallery_statuses = [
        "qc_passed",
        "analyzed_pending_acceptance",
        "analysis_rejected",
        "finalized",
        "ready_for_export",
    ]
    artworks_db = crud.get_artworks_by_statuses(
        db,
        statuses=gallery_statuses,
        owner_id=None if current_user.is_superuser else current_user.id,
    )

    return [
        {
            "id": art.id,
            "original_filename": art.original_filename,
            "thumb_url": get_artwork_display_url(request, art.thumb_path, art.status),
            "status_raw": art.status or "unknown",
            "status_display": (art.status or "Unknown").replace("_", " ").title(),
            "generated_title_display": art.generated_title or get_short_prompt_hint(art.original_filename),
            "sku_display": art.sku,
            "resolution": art.resolution,
            "dpi": str(art.dpi) if art.dpi is not None else None,
        }
        for art in artworks_db
    ]


# ------------------------------------------------------------------------------
# 9.3: API – Update Artwork Status
# ------------------------------------------------------------------------------

@router.post("/artwork/{artwork_id}/update-status", name="update_artwork_status_api_analyze")
async def update_artwork_status_api_route_analyze(
    artwork_id: int,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
) -> JSONResponse:
    """
    Updates the status of an artwork via the Analyze section.
    Only allows transitions to pre-defined valid statuses.
    """
    artwork = _get_artwork_or_404(artwork_id, db, current_user)
    valid_statuses = [
        "uploaded_pending_qc",
        "qc_passed",
        "qc_failed_metrics",
        "analyzed_pending_acceptance",
        "analysis_rejected",
        "finalized",
        "ready_for_export",
    ]

    if new_status not in valid_statuses:
        return JSONResponse(status_code=400, content={"error": f"Invalid status: {new_status}"})

    artwork.status = new_status
    artwork.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(artwork)
        return JSONResponse(content={"message": "Status updated", "new_status": new_status})
    except Exception as e_db:
        db.rollback()
        logger.error(f"DB error updating status for ArtID {artwork_id}: {e_db}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Database error on status update."})

# ==============================================================================
# END OF FILE — analyze_routes.py
# ==============================================================================
