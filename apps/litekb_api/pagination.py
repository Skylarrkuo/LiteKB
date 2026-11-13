from rest_framework.pagination import LimitOffsetPagination


class Page(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def page(request, queryset, render):
    paginator = Page()
    items = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([render(item) for item in items])
