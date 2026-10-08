from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'api_keys.authentication.APIKeyAuthentication'
    name = 'apiKeyAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Send `Authorization: Api-Key dp_live_...`. Keys are only accepted on endpoints that opt in.',
        }
