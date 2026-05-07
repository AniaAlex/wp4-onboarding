from django.urls import path

from . import views

urlpatterns = [
    # Liveness probe (Docker HEALTHCHECK / k8s readinessProbe)
    path("healthz/", views.healthz, name="healthz"),

    # Operator UI
    path("", views.root, name="root"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "schemes/<int:scheme_id>/",
        views.scheme_detail, name="scheme_detail",
    ),
    path(
        "schemes/<int:scheme_id>/entities/new/",
        views.entity_create, name="entity_create",
    ),
    path(
        "schemes/<int:scheme_id>/entities/<int:entity_id>/edit/",
        views.entity_edit, name="entity_edit",
    ),
    path(
        "schemes/<int:scheme_id>/entities/<int:entity_id>/delete/",
        views.entity_delete, name="entity_delete",
    ),
    path(
        "schemes/<int:scheme_id>/pointers/new/",
        views.pointer_create, name="pointer_create",
    ),
    path(
        "schemes/<int:scheme_id>/pointers/<int:pointer_id>/edit/",
        views.pointer_edit, name="pointer_edit",
    ),
    path(
        "schemes/<int:scheme_id>/pointers/<int:pointer_id>/delete/",
        views.pointer_delete, name="pointer_delete",
    ),

    # Public trust-list endpoints (no auth)
    path("lists/", views.lists_index_html, name="lists_index_html"),
    path("lists/index.json", views.lists_manifest, name="lists_manifest"),
    path("lists/<str:filename>", views.list_unsigned, name="list_unsigned"),

    # API documentation
    path("openapi.yaml", views.openapi_yaml, name="openapi_yaml"),
    path("swagger/", views.swagger_ui, name="swagger_ui"),
]
