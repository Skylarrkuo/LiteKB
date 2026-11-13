from django.urls import include, path

from . import knowledge_views as views
from . import knowledge_archive as archive
from . import knowledge_catalog as catalog


base = "knowledge-bases/<uuid:kb_id>"
doc = base + "/documents/<uuid:doc_id>"
para = doc + "/paragraphs/<uuid:paragraph_id>"
urlpatterns = [
    path("models", views.Models.as_view()),
    path("knowledge-bases", views.KnowledgeBases.as_view()),
    path(base, views.KnowledgeBase.as_view()),
    path(base + "/export", archive.ExportContent.as_view()),
    path(base + "/import", archive.ImportContent.as_view()),
    path(base + "/tags", catalog.Tags.as_view()),
    path(base + "/tags/<uuid:tag_id>", catalog.TagItem.as_view()),
    path(base + "/documents", views.Documents.as_view()),
    path(base + "/split", views.SplitFile.as_view()),
    path(base + "/split/<uuid:file_id>", views.SplitPreview.as_view()),
    path(base + "/reindex", views.Reindex.as_view()),
    path(doc, views.DocumentItem.as_view()),
    path(doc + "/tags", catalog.DocumentTags.as_view()),
    path(doc + "/source", views.DocumentSource.as_view()),
    path(doc + "/reindex", views.Reindex.as_view()),
    path(doc + "/paragraphs", views.Paragraphs.as_view()),
    path(para, views.ParagraphItem.as_view()),
    path(para + "/questions", catalog.Questions.as_view()),
    path(para + "/questions/<uuid:question_id>", catalog.QuestionItem.as_view()),
    path("retrievals", views.Retrievals.as_view()),
    path("", include("litekb_api.run_urls")),
]
