DOCS_PATHS = ('/api/schema/swagger-ui/', '/api/schema/redoc/')

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' wss:; "
    "font-src 'self'; "
    "frame-ancestors 'none';"
)

# Swagger UI and ReDoc load their bundles, styles and fonts from public CDNs.
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net blob:; "
    "worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://cdn.jsdelivr.net https://redocly.github.io; "
    "connect-src 'self'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware:
    """Adds security headers to every response.

    Supplements Django's built-in security middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        # Prevent MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        # XSS filter (legacy browsers)
        response['X-XSS-Protection'] = '1; mode=block'
        # Referrer policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Permissions policy: restrict unnecessary browser APIs
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), '
            'payment=(), usb=(), magnetometer=()'
        )

        # Content-Security-Policy: only for HTML responses
        if 'text/html' in response.get('Content-Type', ''):
            response['Content-Security-Policy'] = DOCS_CSP if request.path in DOCS_PATHS else CSP

        return response
