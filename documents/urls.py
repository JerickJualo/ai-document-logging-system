from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("documents/new/", views.upload_document, name="upload-document"),
    path("documents/<int:pk>/process/", views.process_document, name="process-document"),
    path("documents/<int:pk>/review/", views.review_document, name="review-document"),
    path("documents/<int:pk>/", views.document_detail, name="document-detail"),
    path("documents/", views.records, name="records"),
]
