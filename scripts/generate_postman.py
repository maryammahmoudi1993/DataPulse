"""Generate a Postman 2.1 collection from the live OpenAPI schema.

Run once the server is up: ``python scripts/generate_postman.py [base_url]``.
"""
import json
import os
import re
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
OUT = 'api_collection/datapulse.postman_collection.json'
SKIP_PATHS = {'/api/schema/', '/api/schema/swagger-ui/', '/api/schema/redoc/'}
HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete'}
BODY_METHODS = {'post', 'put', 'patch'}
PUBLIC_PATHS = {
    '/api/auth/register/', '/api/auth/token/', '/api/auth/token/refresh/',
    '/api/auth/token/verify/', '/health/', '/readiness/',
}


def build_item(path, method, op):
    """Return one Postman request item for an OpenAPI operation."""
    segments = [re.sub(r'\{(\w+)\}', r':\1', part) for part in path.strip('/').split('/')]
    headers = [{'key': 'Content-Type', 'value': 'application/json'}] if method in BODY_METHODS else []
    request = {
        'method': method.upper(),
        'header': headers,
        'url': {
            'raw': '{{base_url}}/' + '/'.join(segments),
            'host': ['{{base_url}}'],
            'path': segments,
            'variable': [
                {'key': name, 'value': ''}
                for name in re.findall(r'\{(\w+)\}', path)
            ],
        },
    }
    if method in BODY_METHODS:
        request['body'] = {'mode': 'raw', 'raw': '{}', 'options': {'raw': {'language': 'json'}}}
    if path in PUBLIC_PATHS:
        request['auth'] = {'type': 'noauth'}
    return {
        'name': op.get('summary') or f'{method.upper()} {path}',
        'request': request,
    }


def main():
    schema = requests.get(f'{BASE}/api/schema/?format=json', timeout=30).json()
    folders = {}
    count = 0
    for path, methods in schema.get('paths', {}).items():
        if path in SKIP_PATHS:
            continue
        for method, op in methods.items():
            if method not in HTTP_METHODS:
                continue
            tag = (op.get('tags') or ['other'])[0]
            folders.setdefault(tag, []).append(build_item(path, method, op))
            count += 1

    collection = {
        'info': {
            'name': 'DataPulse API',
            'description': 'Real-time anomaly detection platform: all endpoints.',
            'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
        },
        'auth': {
            'type': 'bearer',
            'bearer': [{'key': 'token', 'value': '{{access_token}}', 'type': 'string'}],
        },
        'variable': [
            {'key': 'base_url', 'value': BASE},
            {'key': 'access_token', 'value': ''},
        ],
        'item': [{'name': tag, 'item': items} for tag, items in sorted(folders.items())],
    }

    os.makedirs('api_collection', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as handle:
        json.dump(collection, handle, indent=2)
    print(f'Collection written to {OUT} ({count} requests)')


if __name__ == '__main__':
    main()
