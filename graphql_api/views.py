from django.views.decorators.csrf import csrf_exempt
from strawberry.channels import GraphQLWSConsumer
from strawberry.django.views import GraphQLView

from graphql_api.context import GQLContext
from graphql_api.schema import schema


class DataPulseGraphQLView(GraphQLView):
    """HTTP endpoint; authenticates with ``Authorization`` only (no cookies).

    Ignoring the session means CSRF cannot be used against it, so the view is
    safely CSRF-exempt.
    """

    def get_context(self, request, response):
        return GQLContext(request)


graphql_view = csrf_exempt(DataPulseGraphQLView.as_view(schema=schema, graphql_ide='graphiql'))


class DataPulseGraphQLWSConsumer(GraphQLWSConsumer):
    async def get_context(self, request, response):
        return GQLContext()


def ws_consumer():
    return DataPulseGraphQLWSConsumer.as_asgi(schema=schema)
