# Image Integration Testing Rules

Always use base64-encoded images for tests.
Accepted formats: JPEG, PNG, WEBP only (no SVG/BMP/HEIC/animated).
Use real visual content (no blank/solid-color images).
Re-detect and update MIME type after any transformation.
Animated formats: extract first frame only.
Resize large images to reasonable bounds.

For RIVALS endgame scoreboard OCR:
- Test endpoint: POST /api/matches/{id}/scoreboard
- Body: {"image_b64": "data:image/png;base64,..."}
- Expected: returns {"rows": [{"username": "...", "kills": N, "deaths": N}, ...]}
