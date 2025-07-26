{# -- templates/edit_listing.html -- #}
{% extends "main.html" %}
{% block title %}Edit Listing{% endblock %}

{% block content %}
<style>
  .action-form { width: 100%; }
  .form-col { flex: 1; }
</style>

<div class="container">
  <div class="home-hero">
    <h1>
      <img src="{{ url_for('static', filename='icons/svg/light/number-circle-three-light.svg') }}" class="hero-step-icon" alt="Step 3 Icon">
      Edit Listing
    </h1>
  </div>

  {# -- Flash messages -- #}
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div class="flash-message-block">
        {% for category, message in messages %}
          <div class="flash flash-{{ category }}">{{ message }}</div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}

  <div class="review-artwork-grid row">
    <!-- === LEFT: Artwork & Mockups === -->
    <div class="col col-6 mockup-col">
      <div class="main-thumb">
        <a href="#"
           class="main-thumb-link"
           data-img="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder ~ '.jpg') }}?t={{ cache_ts }}">
          <img
            src="{{ url_for('artwork.processed_image', seo_folder=seo_folder, filename=seo_folder ~ '-THUMB.jpg') }}?t={{ cache_ts }}"
            class="main-artwork-thumb"
            alt="Main artwork thumbnail for {{ seo_folder }}">
        </a>
        <div class="thumb-note">Click thumbnail for full size</div>
      </div>

      <h3>Preview Mockups</h3>
      <div class="debug-categories">
        <strong>Categories:</strong>
        {{ categories | join(', ') if categories else 'none' }}
      </div>

      <div class="mockup-preview-grid">
        {% for m in mockups %}
          <div class="mockup-card">
            {% if m.exists %}
              {% set thumb_name = m.path.stem ~ '-thumb.jpg' %}
              {% set thumb_path = 'art-processing/processed-artwork/' ~ seo_folder ~ '/THUMBS/' ~ thumb_name %}
              {% set full_path = 'art-processing/processed-artwork/' ~ seo_folder ~ '/' ~ m.path.name %}

              <a href="{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}"
                 class="mockup-img-link"
                 data-img="{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}">
                <img 
                  src="{{ url_for('static', filename=thumb_path) }}?t={{ cache_ts }}"
                  onerror="this.onerror=null; this.src='{{ url_for('static', filename=full_path) }}?t={{ cache_ts }}';"
                  class="mockup-thumb-img"
                  alt="Mockup preview {{ loop.index }}">
              </a>
            {% else %}
              <img src="{{ url_for('static', filename='img/default-mockup.jpg') }}"
                   class="mockup-thumb-img"
                   alt="Default mockup placeholder">
            {% endif %}

            {% if categories %}
              <form method="post"
                    action="{{ url_for('artwork.review_swap_mockup', seo_folder=seo_folder, slot_idx=m.index) }}"
                    class="swap-form">
                <select name="new_category" aria-label="Swap mockup category for slot {{ m.index }}">
                  {% for c in categories %}
                    <option value="{{ c }}" {% if c == m.category %}selected{% endif %}>{{ c }}</option>
                  {% endfor %}
                </select>
                <button type="submit" class="btn btn-sm">Swap</button>
              </form>
            {% else %}
              <div class="no-categories-warning">No categories found.</div>
            {% endif %}
          </div>
        {% endfor %}
      </div>
    </div>

    <!-- === RIGHT: Edit Metadata Form === -->
    <div class="col col-6 edit-listing-col">
      <p class="status-line {% if finalised %}status-finalised{% else %}status-pending{% endif %}">
        Status: {% if finalised %}<strong>finalised</strong>{% else %}<em>NOT yet finalised</em>{% endif %}
        {% if locked %}<span class="locked-badge">Locked</span>{% endif %}
      </p>

      {% if errors %}
        <div class="flash-error"><ul>{% for e in errors %}<li>{{ e }}</li>{% endfor %}</ul></div>
      {% endif %}

      <form id="edit-form" method="POST" autocomplete="off">
        <label for="title-input">Title:</label>
        <textarea name="title" id="title-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.title|e }}</textarea>

        <label for="description-input">Description:</label>
        <textarea name="description" id="description-input" rows="12" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.description|e }}</textarea>

        <label for="tags-input">Tags (comma-separated):</label>
        <textarea name="tags" id="tags-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.tags|e }}</textarea>

        <label for="materials-input">Materials (comma-separated):</label>
        <textarea name="materials" id="materials-input" rows="2" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.materials|e }}</textarea>

        <div class="row-inline">
          <div class="form-col">
            <label for="primary_colour-select">Primary Colour:</label>
            <select name="primary_colour" id="primary_colour-select" class="long-field" {% if not editable %}disabled{% endif %}>
              {% for col in colour_options %}
                <option value="{{ col }}" {% if artwork.primary_colour==col %}selected{% endif %}>{{ col }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="form-col">
            <label for="secondary_colour-select">Secondary Colour:</label>
            <select name="secondary_colour" id="secondary_colour-select" class="long-field" {% if not editable %}disabled{% endif %}>
              {% for col in colour_options %}
                <option value="{{ col }}" {% if artwork.secondary_colour==col %}selected{% endif %}>{{ col }}</option>
              {% endfor %}
            </select>
          </div>
        </div>

        <label for="seo_filename-input">SEO Filename:</label>
        <input type="text" id="seo_filename-input" name="seo_filename" class="long-field" value="{{ artwork.seo_filename|e }}" {% if not editable %}disabled{% endif %}>

        <div class="price-sku-row">
          <div>
            <label for="price-input">Price:</label>
            <input type="text" id="price-input" name="price" value="{{ artwork.price|e }}" class="long-field" {% if not editable %}disabled{% endif %}>
          </div>
          <div>
            <label for="sku-input">SKU:</label>
            <input type="text" id="sku-input" value="{{ artwork.sku|e }}" class="long-field" readonly disabled>
          </div>
        </div>

        <label for="images-input">Image URLs (one per line):</label>
        <textarea name="images" id="images-input" rows="5" class="long-field" {% if not editable %}disabled{% endif %}>{{ artwork.images|e }}</textarea>
      </form>

      <div class="edit-actions-col">
        <button form="edit-form" type="submit" name="action" value="save" class="btn btn-primary wide-btn" {% if not editable %}disabled{% endif %}>Save Changes</button>
        <button form="edit-form" type="submit" name="action" value="delete" class="btn btn-danger wide-btn" onclick="return confirm('Delete this artwork and all files?');" {% if not editable %}disabled{% endif %}>Delete</button>

        {% if not finalised %}
          <form method="post" action="{{ url_for('artwork.finalise_artwork', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Finalise</button>
          </form>
        {% endif %}

        <form method="POST" action="{{ url_for('artwork.analyze_artwork', aspect=aspect, filename=filename) }}" class="action-form analyze-form">
          <select name="provider" class="form-select form-select-sm mb-2">
            <option value="openai">OpenAI</option>
            <option value="google">Google</option>
          </select>
          <button type="submit" class="btn btn-primary wide-btn" {% if locked %}disabled{% endif %}>Re-analyse Artwork</button>
        </form>

        {% if finalised and not locked %}
          <form method="post" action="{{ url_for('artwork.lock_listing', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Lock it in</button>
          </form>
        {% elif locked %}
          <form method="post" action="{{ url_for('artwork.unlock_listing', aspect=aspect, filename=filename) }}" class="action-form">
            <button type="submit" class="btn btn-primary wide-btn">Unlock</button>
          </form>
        {% endif %}

        <form method="post" action="{{ url_for('artwork.reset_sku', aspect=aspect, filename=filename) }}" class="action-form">
          <button type="submit" class="btn-primary wide-btn" {% if locked %}disabled{% endif %}>Reset SKU</button>
        </form>
      </div>

      {% if openai_analysis %}
        <div class="openai-details">
          {% set entries = openai_analysis if openai_analysis is iterable and openai_analysis.__class__ != dict else [openai_analysis] %}
          {% for info in entries %}
            <table class="openai-analysis-table">
              <thead><tr><th colspan="2">OpenAI Analysis Details</th></tr></thead>
              <tbody>
                <tr><th>Original File</th><td>{{ info.original_file }}</td></tr>
                <tr><th>Optimized File</th><td>{{ info.optimized_file }}</td></tr>
                <tr><th>Size</th><td>{{ info.size_mb }} MB ({{ info.size_bytes }} bytes)</td></tr>
                <tr><th>Dimensions</th><td>{{ info.dimensions }}</td></tr>
                <tr><th>Time Sent</th><td>{{ info.time_sent }}</td></tr>
                <tr><th>Time Responded</th><td>{{ info.time_responded }}</td></tr>
                <tr><th>Duration</th><td>{{ info.duration_sec }} s</td></tr>
                <tr><th>Status</th><td>{{ info.status }}</td></tr>
                {% if info.api_response %}<tr><th>API Response</th><td>{{ info.api_response }}</td></tr>{% endif %}
                {% if info.naming_method %}<tr><th>Naming Method</th><td>{{ info.naming_method }}{% if info.used_fallback_naming %} (fallback){% endif %}</td></tr>{% endif %}
              </tbody>
            </table>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  </div>

  <!-- === Modal Carousel for Mockups === -->
  <div id="mockup-carousel" class="modal-bg" tabindex="-1">
    <button id="carousel-close" class="modal-close" aria-label="Close">&times;</button>
    <button id="carousel-prev" class="carousel-nav" aria-label="Previous">&#10094;</button>
    <div class="modal-img"><img id="carousel-img" src="" alt="Mockup Preview" /></div>
    <button id="carousel-next" class="carousel-nav" aria-label="Next">&#10095;</button>
  </div>
</div>

<script src="{{ url_for('static', filename='js/edit_listing.js') }}"></script>
{% endblock %}
