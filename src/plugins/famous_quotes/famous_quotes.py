"""
Famous Quotes Plugin for InkyPi
This plugin fetches famous quotes from the API Ninjas Quotes API v2
and displays them on the InkyPi device with optional category filtering.
Supports real-time translation via Argos Translate.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from utils.app_utils import get_font
from flask import request as flask_request, jsonify
from blueprints.plugin import plugin_bp
from PIL import Image, ImageDraw
import logging
import os

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "nl": "Dutch",
    "en": "English",
    "fr": "French",
    "de": "German",
    "id": "Indonesian",
    "it": "Italian",
    "pt": "Portuguese",
    "es": "Spanish",
}


def _build_api_url(category):
    base_url = "https://api.api-ninjas.com/v2/randomquotes"
    if category and category != "random":
        return f"{base_url}?categories={category}"
    return base_url


def _translate_text(text, target_lang):
    """Translate text from English to target language using Argos Translate."""
    if not text or target_lang == "en":
        return text
    try:
        import argostranslate.package
        import argostranslate.translate

        # Check if the required package is already installed
        installed = argostranslate.package.get_installed_packages()
        pkg_exists = any(
            p.from_code == "en" and p.to_code == target_lang
            for p in installed
        )

        if not pkg_exists:
            logger.info(f"Downloading Argos Translate package: en -> {target_lang}")
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
            pkg = next(
                (p for p in available if p.from_code == "en" and p.to_code == target_lang),
                None,
            )
            if pkg is None:
                logger.warning(f"No Argos Translate package available for en -> {target_lang}")
                return text
            argostranslate.package.install_from_path(pkg.download())
            logger.info(f"Installed Argos Translate package: en -> {target_lang}")

        translated = argostranslate.translate.translate(text, "en", target_lang)
        return translated
    except Exception as e:
        logger.error(f"Translation failed (en -> {target_lang}): {e}")
        return text


# ===================================================================
# Translation package management routes (registered on plugin_bp at import time)
# ===================================================================


def _get_argos_package_size(pkg):
    """Calculate installed Argos package size in MB."""
    pkg_path = getattr(pkg, "package_path", None)
    if not pkg_path or not os.path.isdir(pkg_path):
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(pkg_path):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return round(total / (1024 * 1024), 1)


@plugin_bp.route('/translation_packages', methods=['GET'])
def _handle_list_packages():
    """GET /translation_packages — list installed Argos en→X packages."""
    try:
        import argostranslate.package
        installed = argostranslate.package.get_installed_packages()
        packages = []
        for p in installed:
            if p.from_code == "en" and p.to_code in SUPPORTED_LANGUAGES:
                packages.append({
                    "from_code": p.from_code,
                    "to_code": p.to_code,
                    "to_name": SUPPORTED_LANGUAGES.get(p.to_code, p.to_code),
                    "size_mb": _get_argos_package_size(p),
                })
        return jsonify({"packages": packages}), 200
    except Exception as e:
        logger.error(f"Error listing translation packages: {e}")
        return jsonify({"error": str(e)}), 500


@plugin_bp.route('/translation_packages/install', methods=['POST'])
def _handle_install_package():
    """POST /translation_packages/install — download & install an en→X package."""
    try:
        data = flask_request.get_json(silent=True) or {}
        lang_code = data.get("lang_code", "").strip()
        if not lang_code or lang_code not in SUPPORTED_LANGUAGES:
            return jsonify({"error": "Invalid language code"}), 400

        import argostranslate.package
        installed = argostranslate.package.get_installed_packages()
        already = any(p.from_code == "en" and p.to_code == lang_code for p in installed)
        if already:
            return jsonify({"success": True, "message": "Package already installed"}), 200

        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (p for p in available if p.from_code == "en" and p.to_code == lang_code),
            None,
        )
        if pkg is None:
            return jsonify({"error": f"No package found for en → {lang_code}"}), 404

        logger.info(f"Installing Argos package: en -> {lang_code}")
        argostranslate.package.install_from_path(pkg.download())
        logger.info(f"Installed Argos package: en -> {lang_code}")
        return jsonify({"success": True, "message": f"Installed en → {lang_code}"}), 200
    except Exception as e:
        logger.error(f"Error installing translation package: {e}")
        return jsonify({"error": str(e)}), 500


@plugin_bp.route('/translation_packages/delete', methods=['POST'])
def _handle_delete_package():
    """POST /translation_packages/delete — uninstall an en→X package."""
    try:
        data = flask_request.get_json(silent=True) or {}
        lang_code = data.get("lang_code", "").strip()
        if not lang_code or lang_code not in SUPPORTED_LANGUAGES:
            return jsonify({"error": "Invalid language code"}), 400

        import argostranslate.package
        installed = argostranslate.package.get_installed_packages()
        pkg = next(
            (p for p in installed if p.from_code == "en" and p.to_code == lang_code),
            None,
        )
        if pkg is None:
            return jsonify({"error": "Package not installed"}), 404

        argostranslate.package.uninstall(pkg)
        logger.info(f"Uninstalled Argos package: en -> {lang_code}")
        return jsonify({"success": True, "message": f"Removed en → {lang_code}"}), 200
    except Exception as e:
        logger.error(f"Error deleting translation package: {e}")
        return jsonify({"error": str(e)}), 500


class FamousQuotes(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "API Ninjas",
            "expected_key": "API_NINJAS"
        }
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Famous Quotes Plugin: Starting image generation ===")

        api_key = device_config.load_env_key("API_NINJAS")
        if not api_key:
            logger.error("API Ninjas API Key not configured")
            raise RuntimeError("API Ninjas API Key not configured.")

        # Get category setting
        category = settings.get("category", "random")
        
        # Fetch quote from API
        quote_data = self._fetch_quote(api_key, category)
        
        if not quote_data:
            logger.error("Failed to fetch quote or API returned empty")
            raise RuntimeError("Failed to retrieve quote from API.")

        # Parse quote data
        quote_text = quote_data.get("quote", "")
        author = quote_data.get("author", "")
        
        if not quote_text:
            logger.error("API returned empty quote")
            raise RuntimeError("API returned no quote text.")

        # Translate if a non-English language is selected
        language = settings.get("language", "en")
        if language != "en":
            logger.info(f"Translating quote to {SUPPORTED_LANGUAGES.get(language, language)}")
            quote_text = _translate_text(quote_text, language)
            if author:
                author = _translate_text(author, language)

        # Get display settings and normalize types
        raw_show = settings.get("show_author")
        if isinstance(raw_show, str):
            show_author = raw_show.lower() == 'true'
        elif isinstance(raw_show, bool):
            show_author = raw_show
        else:
            # If the form omitted the checkbox (e.g., unchecked), treat as False
            show_author = False

        try:
            max_lines = int(settings.get("max_lines", 3))
        except Exception:
            max_lines = 3

        # Get device dimensions
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
            logger.debug(f"Vertical orientation detected, dimensions: {dimensions[0]}x{dimensions[1]}")

        # Calculate dynamic font sizing based on content and available space
        try:
            width_px = int(dimensions[0])
            height_px = int(dimensions[1])
        except Exception:
            width_px = 800
            height_px = 480

        text_length = len(quote_text)
        chars_per_line = max(1, int(text_length / max_lines))

        # Base sizes (px) derived from display width
        base_quote_px = max(18, int(width_px * 0.06))
        max_quote_px = int(width_px * 0.12)
        min_quote_px = max(12, int(width_px * 0.035))

        # Prefer ~28 chars per line; scale font according to density
        target_cpl = 28
        ratio = target_cpl / chars_per_line
        ratio = max(0.6, min(ratio, 1.4))

        quote_font_px = int(base_quote_px * ratio)
        quote_font_px = max(min_quote_px, min(quote_font_px, max_quote_px))

        author_font_px = max(10, int(quote_font_px * 0.45))

        template_params = {
            "quote": quote_text,
            "author": author if (show_author and author) else "",
            "max_lines": max_lines,
            "show_author": show_author and bool(author),
            "plugin_settings": settings,
            # CSS-friendly sizing values (px)
            "quote_font_px": quote_font_px,
            "author_font_px": author_font_px,
            "title_font_px": max(14, int(quote_font_px * 0.65))
        }

        # --- Fallback scaling: ensure rendered text fits the content area ---
        # Helper to wrap text according to pixel width
        def _wrap_text(draw, text, font, max_width):
            words = text.split()
            if not words:
                return [""]
            lines = []
            cur = words[0]
            for w in words[1:]:
                test = cur + " " + w
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            return lines

        # Create a dummy image for measurement
        measure_img = Image.new("RGB", (max(1, width_px), max(1, height_px)), (255, 255, 255))
        draw = ImageDraw.Draw(measure_img)

        # Convert CSS-like margins to px for measurement (keep consistent with CSS)
        horiz_margin = max(8, int(width_px * 0.04))
        vert_margin = max(8, int(height_px * 0.04))

        content_width = max(10, width_px - horiz_margin * 2)

        # Measure title and author heights
        title_font = get_font("Jost", template_params["title_font_px"]) or get_font("Jost", 18)
        title_bbox = draw.textbbox((0, 0), "FAMOUS QUOTE", font=title_font)
        title_h = title_bbox[3] - title_bbox[1]

        author_font = get_font("Jost", template_params["author_font_px"]) or get_font("Jost", 12)
        author_h = draw.textbbox((0, 0), "— " + (template_params["author"] or ""), font=author_font)[3]

        # Available height for quote block
        spacing_title_quote = int(title_h * 0.6)
        spacing_quote_author = int(author_h * 0.6)
        available_h = height_px - (vert_margin * 2) - title_h - spacing_title_quote - spacing_quote_author - author_h

        # Iteratively reduce font until the wrapped text fits or reaches minimum
        fits = False
        min_font = min_quote_px
        cur_font = quote_font_px
        while cur_font >= min_font:
            font = get_font("Jost", cur_font) or get_font("Jost", min_font)
            lines = _wrap_text(draw, quote_text, font, content_width)
            # Respect max_lines
            if len(lines) > max_lines:
                block_h = (draw.textbbox((0, 0), "Ay", font=font)[3] - draw.textbbox((0, 0), "Ay", font=font)[1]) * max_lines
            else:
                # compute total height with line spacing
                single_h = draw.textbbox((0, 0), "Ay", font=font)[3] - draw.textbbox((0, 0), "Ay", font=font)[1]
                block_h = int(single_h * len(lines) * 1.15)

            # Check horizontal overflow per line
            too_wide = any((draw.textbbox((0, 0), ln, font=font)[2] - draw.textbbox((0, 0), ln, font=font)[0]) > content_width for ln in lines)

            if not too_wide and block_h <= available_h and len(lines) <= max_lines:
                fits = True
                break

            cur_font -= 2

        if not fits:
            # Final fallback: truncate to max_lines with ellipsis
            font = get_font("Jost", max(min_font, cur_font)) or get_font("Jost", min_font)
            lines = _wrap_text(draw, quote_text, font, content_width)
            if len(lines) > max_lines:
                visible = lines[: max_lines]
                # truncate last line to fit with ellipsis
                last = visible[-1]
                ell = "…"
                while True:
                    bbox = draw.textbbox((0, 0), last + ell, font=font)
                    if bbox[2] - bbox[0] <= content_width or len(last) == 0:
                        break
                    last = last[:-1]
                visible[-1] = last + ell
                rendered_quote = "\n".join(visible)
            else:
                rendered_quote = "\n".join(lines)
            template_params["quote"] = rendered_quote
            template_params["quote_font_px"] = max(min_font, cur_font)
        else:
            # fits with cur_font
            template_params["quote_font_px"] = cur_font

        logger.info(f"Rendering quote: {quote_text[:50]}...")
        image = self.render_image(
            dimensions,
            "famous_quotes.html",
            "famous_quotes.css",
            template_params
        )

        logger.info("=== Famous Quotes Plugin: Image generation complete ===")
        return image


    def _fetch_quote(self, api_key, category):
        """Fetch a quote from API Ninjas random quotes API v2."""
        try:
            headers = {"X-Api-Key": api_key}
            session = get_http_session()

            url = _build_api_url(category)

            logger.debug(f"Fetching from URL: {url}")
            response = session.get(url, headers=headers, timeout=10)

            logger.debug(f"API Ninjas response: {response.status_code} {response.text}")

            if response.status_code != 200:
                logger.error(f"API error (status {response.status_code}): {response.text}")
                return None

            data = response.json()
            # API returns an array of quotes, use the first one
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            elif isinstance(data, dict):
                return data
            else:
                logger.error(f"Unexpected API response format: {data}")
                return None

        except Exception as e:
            logger.error(f"Error fetching quote: {str(e)}")
            return None

    def _render_error_image(self, device_config, settings, error_message):
        """Render error message"""
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "quote": error_message,
            "author": "",
            "show_author": False,
            "plugin_settings": settings
        }

        return self.render_image(
            dimensions,
            "famous_quotes.html",
            "famous_quotes.css",
            template_params
        )
