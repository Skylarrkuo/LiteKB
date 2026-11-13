"""Product-facing endpoints, resource isolation, and PostgreSQL ingestion lifecycle."""
from io import StringIO
from copy import deepcopy
from uuid import uuid4
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from knowledge.models import Document, DocumentTag, Embedding, File, FileSourceType, Knowledge, KnowledgeFolder, KnowledgeType
from knowledge.models import Paragraph, Problem, ProblemParagraphMapping, Tag
from models_provider.models import Model
from users.models import User

from .models import Project, ProjectKnowledge, ServiceClient


class KnowledgeAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username="scope-test", nick_name="scope test", password="unused", role="ADMIN")
        folder = KnowledgeFolder.objects.create(pk="scope-test", name="scope test", workspace_id="scope-test")
        a = Project.objects.create(slug="product-a", name="A", owner=owner, workspace_id=folder.pk)
        b = Project.objects.create(slug="product-b", name="B", owner=owner, workspace_id=folder.pk)
        cls.client_a, cls.key_a = ServiceClient.issue(a, "A server")
        cls.client_b, cls.key_b = ServiceClient.issue(b, "B server")
        model = Model.objects.create(name="scope-model", model_type="EMBEDDING", model_name="test",
                                     provider="test", credential="server-only", workspace_id=folder.pk)
        a.models.add(model)
        cls.model_id = model.pk
        cls.kbs = []
        for project in (a, b):
            kb = Knowledge.objects.create(name=project.name, desc="", folder=folder, workspace_id=folder.pk,
                                          type=KnowledgeType.BASE, embedding_model=model)
            ProjectKnowledge.objects.create(project=project, knowledge=kb)
            cls.kbs.append(kb)
        cls.doc = Document.objects.create(name="private document", knowledge=cls.kbs[1], char_length=0)

    def setUp(self):
        self.http = APIClient()
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_a)

    def test_invalid_and_revoked_keys_are_unauthorized(self):
        path = "/v1/knowledge-bases"
        self.assertEqual(APIClient().get(path).status_code, 401)
        for token in ("old-token", "lk_" + "x" * 43):
            self.http.credentials(HTTP_AUTHORIZATION="Bearer " + token)
            self.assertEqual(self.http.get(path).status_code, 401)
        ServiceClient.objects.filter(pk=self.client_b.pk).update(is_active=False)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        self.assertEqual(self.http.get(path).status_code, 401)

    def test_projects_in_same_workspace_have_disjoint_lists_and_updates(self):
        response = self.http.get("/v1/knowledge-bases").json()
        self.assertEqual([row["id"] for row in response["results"]], [str(self.kbs[0].pk)])
        self.assertEqual(self.http.patch(f"/v1/knowledge-bases/{self.kbs[1].pk}", {"name": "x"},
                                         format="json").status_code, 404)
        self.assertEqual(self.http.delete(f"/v1/knowledge-bases/{self.kbs[1].pk}").status_code, 404)
        response = self.http.patch(f"/v1/knowledge-bases/{self.kbs[0].pk}", {"description": "edited"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "edited")

    def test_document_id_is_bound_to_knowledge_base_for_every_operation(self):
        for kb in self.kbs:
            path = f"/v1/knowledge-bases/{kb.pk}/documents/{self.doc.pk}"
            for suffix in ("", "/source", "/paragraphs"):
                self.assertEqual(self.http.get(path + suffix).status_code, 404)
            self.assertEqual(self.http.patch(path, {"name": "x"}, format="json").status_code, 404)
            self.assertEqual(self.http.delete(path).status_code, 404)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        path = f"/v1/knowledge-bases/{self.kbs[1].pk}/documents/{self.doc.pk}"
        self.assertEqual(self.http.get(path).status_code, 200)

    def test_model_response_and_mutations_do_not_expose_credentials_or_scope_fields(self):
        rows = self.http.get("/v1/models").json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertNotIn("credential", rows[0])
        self.assertEqual(self.http.post("/v1/knowledge-bases", {
            "name": "new", "embedding_model_id": self.model_id, "workspace_id": "forged",
        }, format="json").status_code, 400)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        self.assertEqual(self.http.get("/v1/models").json()["results"], [])

    def test_mixed_scope_retrieval_fails_before_any_model_call(self):
        for mode in ("embedding", "rrf"):
            response = self.http.post("/v1/retrievals", {"knowledge_base_ids": [str(k.pk) for k in self.kbs],
                                                         "query": "private", "mode": mode}, format="json")
            self.assertEqual(response.status_code, 404)

    @skipUnless(connection.vendor == "postgresql", "RRF candidate selection uses PostgreSQL")
    def test_rrf_checks_all_model_grants_before_inference_and_embeds_once_per_model(self):
        kb = self.kbs[0]
        other = Knowledge.objects.create(name="additional", folder=kb.folder, workspace_id=kb.workspace_id,
                                         type=KnowledgeType.BASE, embedding_model=kb.embedding_model)
        ProjectKnowledge.objects.create(project=self.client_a.project, knowledge=other)
        query = {"knowledge_base_ids": [str(kb.pk), str(other.pk)], "query": "contract", "mode": "rrf"}
        with patch("knowledge.serializers.common.get_embedding_model_by_knowledge") as factory:
            factory.return_value.embed_query.return_value = [1., 0.]
            response = self.http.post("/v1/retrievals", query, format="json")
            self.assertEqual(response.json()["hits"], [])
            factory.return_value.embed_query.assert_called_once_with("contract")
            factory.reset_mock()
            other.embedding_model = Model.objects.create(name="ungranted", model_type="EMBEDDING", model_name="test",
                                                          provider="test", credential="", workspace_id=kb.workspace_id)
            other.save()
            response = self.http.post("/v1/retrievals", query, format="json")
            self.assertEqual(response.status_code, 404)
            factory.assert_not_called()

    def test_cannot_import_another_projects_preview_or_an_ungranted_model(self):
        foreign = File(file_name="other.txt", source_id=str(self.kbs[1].pk),
                       source_type=FileSourceType.KNOWLEDGE, loid=0, meta={"litekb_preview": True})
        File.objects.bulk_create([foreign])
        response = self.http.post(f"/v1/knowledge-bases/{self.kbs[0].pk}/documents", {
            "name": "copy", "paragraphs": [{"content": "x"}], "source_file_id": str(foreign.pk),
        }, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.http.delete(f"/v1/knowledge-bases/{self.kbs[0].pk}/split/{foreign.pk}").status_code, 404)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        response = self.http.post("/v1/knowledge-bases", {"name": "new", "embedding_model_id": self.model_id},
                                  format="json")
        self.assertEqual(response.status_code, 404)

    def test_provisioning_and_revocation(self):
        options = ["--workspace", "scope-test", "--owner", "scope-test", "--model", str(self.model_id)]
        result = StringIO()
        call_command("litekb_client", "provisioned", "--issue", "first", *options, stdout=result)
        response = dict(line.split("=", 1) for line in result.getvalue().strip().splitlines())
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + response["service_key"])
        self.assertEqual(self.http.get("/v1/models").json()["count"], 1)
        self.assertNotEqual(ServiceClient.objects.get(pk=response["client_id"]).key_hash, response["service_key"])
        with self.assertRaises(CommandError):
            call_command("litekb_client", "provisioned", "--issue", "bad", "--knowledge", str(self.kbs[0].pk),
                         *options, stdout=StringIO())
        self.assertEqual(ServiceClient.objects.filter(project__slug="provisioned").count(), 1)
        call_command("litekb_client", "provisioned", "--revoke", response["client_id"], stdout=StringIO())
        self.assertEqual(self.http.get("/v1/models").status_code, 401)

    @skipUnless(connection.vendor == "postgresql", "File large objects, paragraph arrays and index SQL use PostgreSQL")
    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_postgresql_file_and_paragraph_lifecycle(self):
        response = self.http.post("/v1/knowledge-bases", {"name": "manuals", "embedding_model_id": self.model_id},
                                  format="json")
        self.assertEqual(response.status_code, 201, response.content)
        base = "/v1/knowledge-bases/" + response.json()["id"]
        payload = b"Product warranty lasts two years."
        preview = self.http.post(base + "/split", {"file": SimpleUploadedFile("manual.txt", payload)})
        self.assertEqual(preview.status_code, 201, preview.content)
        data = preview.json()["documents"][0]
        self.assertEqual(data["paragraphs"][0]["content"], payload.decode())
        with patch("litekb_api.index_tasks.embedding_by_document.delay") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.http.post(base + "/documents", data, format="json")
            self.assertEqual(response.status_code, 201, response.content)
            doc = response.json()["documents"][0]
            publish.assert_called_once_with(doc["id"], str(self.model_id))
            self.assertEqual(doc["index_status"], "pending")
            url = base + "/documents/" + doc["id"]
            self.assertEqual(self.http.get(url + "/source").content, payload)
            updated = b"An updated downloadable original"
            replaced = self.http.put(url + "/source", {"file": SimpleUploadedFile("updated.txt", updated)},
                                     format="multipart")
            self.assertEqual(replaced.status_code, 200, replaced.content)
            self.assertEqual(self.http.get(url + "/source").content, updated)
            self.assertEqual(self.http.delete(url + "/source").status_code, 204)
            self.assertEqual(self.http.get(url + "/source").status_code, 404)
            self.assertEqual(self.http.get(url + "/paragraphs").json()["count"], 1)
            added = self.http.post(url + "/paragraphs", {"title": "Details", "content": "Conditions."}, format="json")
            self.assertEqual(added.status_code, 201, added.content)
            para = url + "/paragraphs/" + added.json()["id"]
            self.assertEqual(self.http.patch(para, {"content": "Updated."}, format="json").json()["content"], "Updated.")
            self.assertEqual(self.http.get(url).json()["character_count"], len(payload) + len("Updated."))
            self.assertEqual(self.http.post(url + "/reindex").status_code, 202)
            self.assertEqual(self.http.delete(para).status_code, 204)
            self.assertEqual(self.http.get(url + "/paragraphs").json()["count"], 1)
            self.assertEqual(self.http.delete(url).status_code, 204)
            # Reuse the KB-owned preview after deleting the first document's source.
            response = self.http.post(base + "/documents", data, format="json")
            self.assertEqual(response.status_code, 201, response.content)
            imported = base + "/documents/" + response.json()["documents"][0]["id"]
            self.assertEqual(self.http.delete(base + "/split/" + data["source_file_id"]).status_code, 204)
            self.assertEqual(self.http.post(base + "/documents", data, format="json").status_code, 404)
            self.assertEqual(self.http.get(imported + "/source").content, payload)
            response = self.http.post(base + "/documents", {"file": SimpleUploadedFile("another.txt", payload)})
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.http.delete(base).status_code, 204)
        self.assertEqual(self.http.get(base).status_code, 404)

    @skipUnless(connection.vendor == "postgresql", "Vector retrieval uses pgvector and a document worker lock")
    def test_pgvector_index_and_retrieval_return_document_citations(self):
        from knowledge.task.embedding import embedding_by_document

        base = f"/v1/knowledge-bases/{self.kbs[0].pk}"
        response = self.http.post(base + "/documents", {"name": "Terms", "content": "Warranty covers repairs."},
                                  format="json")
        self.assertEqual(response.status_code, 201, response.content)
        doc = response.json()["documents"][0]
        model = Mock()
        model.embed_documents.side_effect = lambda texts: [[1., 0.] for _ in texts]
        model.embed_query.return_value = [1., 0.]
        with patch("knowledge.task.embedding.get_embedding_model", return_value=model):
            embedding_by_document.run(doc["id"], str(self.model_id))
        url = base + "/documents/" + doc["id"]
        self.assertEqual(self.http.get(url).json()["index_status"], "success")
        with patch("knowledge.serializers.knowledge.get_embedding_model_by_knowledge_id", return_value=model):
            query = {"knowledge_base_ids": [str(self.kbs[0].pk)], "query": "warranty"}
            for mode in ("embedding", "keywords", "blend"):
                response = self.http.post("/v1/retrievals", {**query, "mode": mode}, format="json")
                self.assertEqual(response.status_code, 200, response.content)
                hits = response.json()["hits"]
                self.assertEqual(len(hits), 1, mode)
                self.assertEqual(hits[0]["content"], "Warranty covers repairs.")
                self.assertEqual(hits[0]["document_id"], doc["id"])
                self.assertEqual(hits[0]["knowledge_base_id"], str(self.kbs[0].pk))
                self.assertTrue(hits[0]["paragraph_id"])
            self.assertEqual(self.http.patch(url, {"is_active": False}, format="json").status_code, 200)
            self.assertEqual(self.http.post("/v1/retrievals", query, format="json").json()["hits"], [])

    @skipUnless(connection.vendor == "postgresql", "Independent vector and FTS candidate queries use pgvector")
    def test_rrf_returns_lexical_only_match_and_filters_inactive_and_cross_project_candidates(self):
        from django.contrib.postgres.search import SearchVector
        from django.db.models import Value

        kb, other = self.kbs
        doc = Document.objects.create(knowledge=kb, name="Field notes", char_length=0)
        def sample(knowledge, document, text, vector, active=True, paragraph=None):
            p = paragraph or Paragraph.objects.create(knowledge=knowledge, document=document, content=text, is_active=active)
            Embedding.objects.create(id=str(uuid4()), source_id=str(p.pk), paragraph=p, document=document,
                                     knowledge=knowledge, embedding=vector, search_vector=SearchVector(Value(text),
                                                                                                      config="simple"))
            return str(p.pk)

        target = sample(kb, doc, "zxq 901", [0., 1.])
        for i in range(32):
            sample(kb, doc, "wireless router", [1., .001 * i])
        other_doc = Document.objects.create(knowledge=kb, name="Withdrawn", char_length=0, is_active=False)
        sample(kb, other_doc, "zxq 901", [1., 0.])
        sample(kb, doc, "zxq 901", [1., 0.], active=False)
        foreign = Paragraph.objects.create(knowledge=other, document=self.doc, content="private zxq 901")
        sample(other, self.doc, "zxq 901", [1., 0.], paragraph=foreign)
        sample(kb, doc, "zxq 901", [1., 0.], paragraph=foreign)  # Inconsistent legacy embedding row.
        model = Mock()
        model.embed_query.return_value = [1., 0.]
        query = {"knowledge_base_ids": [str(kb.pk)], "query": "ZXQ-901", "top_k": 3}
        with patch("knowledge.serializers.knowledge.get_embedding_model_by_knowledge_id", return_value=model):
            old = self.http.post("/v1/retrievals", {**query, "mode": "blend"}, format="json")
            self.assertNotIn(target, [p["paragraph_id"] for p in old.json()["hits"]])
        with patch("knowledge.serializers.common.get_embedding_model_by_knowledge", return_value=model):
            result = self.http.post("/v1/retrievals", {**query, "mode": "rrf"}, format="json")
            self.assertEqual(result.status_code, 200, result.content)
            hits = result.json()["hits"]
            self.assertIn(target, [p["paragraph_id"] for p in hits])
            self.assertEqual(len(hits), 3)
            self.assertEqual([p["rank_score"] for p in hits], sorted([p["rank_score"] for p in hits], reverse=True))
            self.assertTrue(all(p["document_id"] == str(doc.pk) and p["content"] in ("zxq 901", "wireless router")
                                for p in hits))
            strict = self.http.post("/v1/retrievals", {**query, "mode": "rrf", "min_score": 2}, format="json")
            self.assertEqual(strict.json()["hits"], [])

    @skipUnless(connection.vendor == "postgresql", "The Agent retrieval steps execute real pgvector/FTS queries")
    def test_agent_pipeline_workflow_and_debug_preserve_rrf_order_filters_and_scores(self):
        from django.contrib.postgres.search import SearchVector
        from django.db.models import Value
        from application.chat_pipeline.step.search_dataset_step.impl.base_search_dataset_step import BaseSearchDatasetStep
        from application.flow.step_node.search_knowledge_node.impl import base_search_knowledge_node as workflow
        from knowledge.serializers.knowledge import KnowledgeSerializer
        from knowledge.vector.pg_vector import PGVector
        from knowledge.models import SearchMode
        from .run_policy import project_scope

        kb = self.kbs[0]
        passages = []
        for text, vector in [("beacon", [0., 1.]), ("generic first", [1., 0.]), ("generic next", [.95, .2])]:
            doc = Document.objects.create(knowledge=kb, name=text, char_length=len(text))
            p = Paragraph.objects.create(knowledge=kb, document=doc, content=text)
            passages.append(p)
            Embedding.objects.create(id=str(uuid4()), source_id=str(p.pk), paragraph=p, document=doc, knowledge=kb,
                                     embedding=vector, search_vector=SearchVector(Value(text), config="simple"))
        ids = [str(kb.pk)]
        model = Mock()
        model.embed_query.return_value = [1., 0.]
        with patch("knowledge.serializers.common.get_embedding_model_by_knowledge", return_value=model):
            hits = self.http.post("/v1/retrievals", {"mode": "rrf", "query": "beacon", "knowledge_base_ids": ids,
                                                     "top_k": 3}, format="json").json()["hits"]
        expected = [(h["paragraph_id"], h["score"], h["rank_score"]) for h in hits]
        self.assertEqual([p[0] for p in expected], [str(p.pk) for p in passages])
        self.assertLess(expected[0][1], expected[1][1])  # Sorting by score would change the prompt order.

        with patch("knowledge.serializers.knowledge.get_embedding_model_by_knowledge_id", return_value=model):
            debug = KnowledgeSerializer.HitTest(data={
                "workspace_id": kb.workspace_id, "knowledge_id": kb.pk, "search_mode": "rrf", "query_text": "beacon",
                "top_number": 3, "similarity": 0,
            }).hit_test()
        self.assertEqual([(str(p["id"]), p["similarity"], p["rank_score"]) for p in debug], expected)

        manager = SimpleNamespace(context={"problem_text": "beacon", "knowledge_id_list": ids, "top_n": 3,
                                           "search_mode": "rrf", "similarity": 0, "workspace_id": kb.workspace_id,
                                           "exclude_document_id_list": [], "exclude_paragraph_id_list": []})
        step = BaseSearchDatasetStep()
        # The web/worker runtime releases its connection between steps. Keep TestCase's transaction alive.
        with (project_scope(self.client_a.project), patch.object(connection, "close"),
              patch("common.config.embedding_config.ModelManage.get_model", return_value=model)):
            step.run(manager)
        self.assertEqual([(p.id, p.similarity, p.to_dict()["rank_score"]) for p in manager.context["paragraph_list"]],
                         expected)

        node_manager = Mock()
        node_manager.get_body.return_value = {"workspace_id": kb.workspace_id}
        node_manager.get_resource_user_id.return_value = self.client_a.project.owner_id
        node = workflow.BaseSearchKnowledgeNode(SimpleNamespace(id="lookup", properties={}), {}, node_manager)
        args = {"knowledge_id_list": ids, "question": "beacon", "show_knowledge": True, "search_scope_type": "custom",
                "search_scope_source": "knowledge", "search_scope_reference": [],
                "knowledge_setting": {"top_n": 3, "similarity": 0, "search_mode": "rrf"}}
        with (project_scope(self.client_a.project), patch.object(workflow.connection, "close"),
              patch.object(workflow, "get_model_instance_by_model_workspace_id", return_value=model)):
            rows = node.execute(**args).node_variable["paragraph_list"]
            self.assertEqual([(p["id"], p["similarity"], p["rank_score"]) for p in rows], expected)
            node_manager.get_reference_field.return_value = [str(passages[1].document_id), str(self.doc.pk), None]
            args.update(search_scope_type="referencing", search_scope_source="document", search_scope_reference=["docs"])
            scoped = node.execute(**args).node_variable["paragraph_list"]
            self.assertEqual([p["id"] for p in scoped], [str(passages[1].pk)])
            self.assertEqual(node.execute(**args, exclude_paragraph_id_list=[str(passages[1].pk)]).node_variable[
                "paragraph_list"], [])
        vector = PGVector()
        self.assertEqual(vector.query("beacon", [1., 0.], ids, [], None, None, True, 3, 0, SearchMode.rrf), [])
        filtered = vector.query("beacon", [1., 0.], ids, None, [str(passages[0].document_id)], None, True,
                                3, 0, SearchMode.rrf)
        self.assertNotIn(passages[0].pk, [p["paragraph_id"] for p in filtered])

    def test_tag_crud_and_atomic_scoped_document_associations(self):
        a, b = self.kbs
        path = f"/v1/knowledge-bases/{a.pk}/tags"
        added = self.http.post(path, {"key": "dept", "value": "support"}, format="json")
        self.assertEqual(added.status_code, 201, added.content)
        tag_id = added.json()["id"]
        self.assertEqual(self.http.post(path, {"key": "dept", "value": "support"}, format="json").status_code, 200)
        tag_url = path + "/" + tag_id
        self.assertEqual(self.http.patch(tag_url, {"value": "care"}, format="json").json()["value"], "care")
        duplicate = Tag.objects.create(knowledge=a, key="dept", value="sales")
        self.assertEqual(self.http.patch(tag_url, {"value": duplicate.value}, format="json").status_code, 409)
        foreign = Tag.objects.create(knowledge=b, key="private", value="b")
        doc = Document.objects.create(knowledge=a, name="A", char_length=0)
        links = f"/v1/knowledge-bases/{a.pk}/documents/{doc.pk}/tags"
        self.assertEqual(self.http.put(links, {"tag_ids": [tag_id]}, format="json").status_code, 200)
        self.assertEqual(self.http.put(links, {"tag_ids": [str(duplicate.pk), str(foreign.pk)]},
                                       format="json").status_code, 404)
        self.assertEqual([row["id"] for row in self.http.get(links).json()["results"]], [tag_id])
        self.assertEqual(self.http.delete(path + "/" + str(foreign.pk)).status_code, 404)
        self.assertEqual(self.http.delete(tag_url).status_code, 204)
        self.assertFalse(DocumentTag.objects.filter(document=doc).exists())

    @skipUnless(connection.vendor == "postgresql", "Indexes use PostgreSQL and Redis")
    def test_editing_and_unlinking_shared_questions_refreshes_retrieval(self):
        from knowledge.task.embedding import embedding_by_document

        kb = self.kbs[0]
        base = f"/v1/knowledge-bases/{kb.pk}"
        doc = Document.objects.create(knowledge=kb, name="Answers", char_length=6)
        paras = [Paragraph.objects.create(knowledge=kb, document=doc, content=word) for word in ("One", "Two")]
        urls = [f"{base}/documents/{doc.pk}/paragraphs/{para.pk}/questions" for para in paras]
        model = Mock()
        model.embed_documents.side_effect = lambda texts: [[1., 0.] for _ in texts]
        model.embed_query.return_value = [1., 0.]

        def write(method, url, content=None):
            with self.captureOnCommitCallbacks(execute=True):
                return getattr(self.http, method)(url, {"content": content} if content else {}, format="json")

        def search(word):
            result = self.http.post("/v1/retrievals", {"knowledge_base_ids": [str(kb.pk)], "query": word,
                                                       "mode": "keywords"}, format="json")
            self.assertEqual(result.status_code, 200, result.content)
            return {row["paragraph_id"] for row in result.json()["hits"]}

        with (patch("litekb_api.index_tasks.dispatch_document_index", side_effect=embedding_by_document.run),
              patch("knowledge.task.embedding.get_embedding_model", return_value=model),
              patch("knowledge.serializers.knowledge.get_embedding_model_by_knowledge_id", return_value=model)):
            first = write("post", urls[0], "crimson")
            self.assertEqual(first.status_code, 201, first.content)
            second = write("post", urls[1], "crimson")
            self.assertEqual(write("post", urls[0], "crimson").status_code, 200)
            ids = [str(p.pk) for p in paras]
            self.assertEqual(search("crimson"), set(ids))
            self.assertEqual(self.http.get(urls[0] + "/" + second.json()["id"]).status_code, 404)
            item = urls[0] + "/" + first.json()["id"]
            edited = write("patch", item, "saffron")
            self.assertEqual(edited.status_code, 200, edited.content)
            self.assertEqual(edited.json()["id"], first.json()["id"])
            self.assertEqual(search("crimson"), {ids[1]})
            self.assertEqual(search("saffron"), {ids[0]})
            self.assertEqual(write("delete", item).status_code, 204)
            self.assertEqual(search("saffron"), set())
            self.assertEqual(search("crimson"), {ids[1]})
            self.assertFalse(Problem.objects.filter(knowledge=kb, content="saffron").exists())

    @skipUnless(connection.vendor == "postgresql", "Archive contents include paragraph arrays")
    def test_plain_json_export_roundtrip_pagination_retry_and_rollback(self):
        a, b = self.kbs
        source, target = [f"/v1/knowledge-bases/{kb.pk}" for kb in (a, b)]
        self.client_b.project.models.add(self.model_id)
        doc = Document.objects.create(knowledge=a, name="Portable", char_length=15, is_active=False,
                                      meta={"private": "hidden", "source_file_id": str(uuid4())})
        para = Paragraph.objects.create(knowledge=a, document=doc, content="Preserved body.", title="Heading",
                                        is_active=False, position=1)
        question = Problem.objects.create(knowledge=a, content="How?")
        ProblemParagraphMapping.objects.create(knowledge=a, document=doc, paragraph=para, problem=question)
        foreign = Problem.objects.create(knowledge=b, content="Do not export")
        ProblemParagraphMapping.objects.create(knowledge=a, document=doc, paragraph=para, problem=foreign)
        tag = Tag.objects.create(knowledge=a, key="lang", value="en")
        DocumentTag.objects.create(document=doc, tag=tag)
        empty = Document.objects.create(knowledge=a, name="Empty", char_length=0)
        first = self.http.get(source + "/export?limit=1")
        self.assertEqual(first.status_code, 200, first.content)
        second = self.http.get(source + "/export", {"limit": 1, "after": first["X-Next-After"]})
        self.assertNotIn("X-Next-After", second)
        first_doc, second_doc = first.json()["documents"][0], second.json()["documents"][0]
        self.assertEqual([first_doc["key"], second_doc["key"]], [str(doc.pk), str(empty.pk)])
        archive = self.http.get(source + "/export").json()
        self.assertEqual(archive["documents"][0]["paragraphs"][0]["questions"], ["How?"])
        self.assertNotIn("source_file_id", str(archive))
        self.assertEqual(self.http.post(source + "/import", archive, format="json").json()["skipped_documents"], 2)
        self.assertEqual(self.http.post(target + "/import", archive, format="json").status_code, 404)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        self.assertEqual(self.http.get(source + "/export").status_code, 404)
        def write(data):
            return self.http.post(target + "/import", data, format="json")

        result = write(archive)
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.json(), {"created_documents": 2, "skipped_documents": 0})
        self.assertEqual(write(archive).json(), {"created_documents": 0, "skipped_documents": 2})
        reexport = self.http.get(target + "/export").json()
        records = [row for row in reexport["documents"] if row["key"] in {str(doc.pk), str(empty.pk)}]
        self.assertEqual(records, archive["documents"])
        changed = deepcopy(archive)
        changed["tags"].append({"key": "rollback", "value": "x"})
        changed["documents"][0]["key"] = str(uuid4())
        changed["documents"][1]["name"] = "conflicting replay"
        self.assertEqual(write(changed).status_code, 409)
        self.assertFalse(Tag.objects.filter(knowledge=b, key="rollback").exists())
        self.assertEqual(Document.objects.filter(knowledge=b).count(), 3)
        injected = deepcopy(archive)
        injected["documents"][0]["paragraphs"][0]["document_id"] = str(doc.pk)
        self.assertEqual(write(injected).status_code, 400)

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=32)
    def test_oversized_json_import_is_rejected(self):
        result = self.http.post(f"/v1/knowledge-bases/{self.kbs[0].pk}/import", {
            "format": "litekb.knowledge.v1", "documents": [], "tags": [],
        }, format="json")
        self.assertEqual(result.status_code, 413, result.content[:1200])

    @skipUnless(connection.vendor == "postgresql", "Model switch drops and rebuilds a pgvector index")
    def test_switch_model_during_inference_discards_old_vectors_and_rebuilds_with_latest(self):
        from knowledge.task.embedding import embedding_by_document, embedding_by_knowledge
        from django.db.models import Func, IntegerField

        kb = self.kbs[0]
        base = f"/v1/knowledge-bases/{kb.pk}"
        doc = Document.objects.create(knowledge=kb, name="Manual", char_length=4)
        Paragraph.objects.create(knowledge=kb, document=doc, content="Text")
        new_model = Model.objects.create(name="New", model_type="EMBEDDING", model_name="new", provider="test",
                                         credential="unused", workspace_id=kb.workspace_id)
        new_id, old_id = str(new_model.pk), str(self.model_id)
        change = {"embedding_model_id": new_id, "file_count_limit": 85}
        self.assertEqual(self.http.patch(base, change, format="json").status_code, 404)
        self.client_a.project.models.add(new_model)

        def dimensions():
            return list(Embedding.objects.filter(knowledge=kb).annotate(
                dims=Func("embedding", function="vector_dims", output_field=IntegerField())
            ).values_list("dims", flat=True))

        old, new = Mock(), Mock()
        old.embed_documents.side_effect = lambda texts: [[1., 0.] for _ in texts]
        new.embed_documents.side_effect = lambda texts: [[1., 0., 0.] for _ in texts]
        with (patch("knowledge.task.embedding.get_embedding_model",
                    side_effect=lambda model_id, *args: {old_id: old, new_id: new}[str(model_id)]),
              patch("litekb_api.index_tasks.dispatch_document_index") as enqueue):
            embedding_by_document.run(str(doc.pk), old_id)
            self.assertEqual(dimensions(), [2])

            def switch_while_waiting_for_old_provider(texts):
                response = self.http.patch(base, change, format="json")
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["file_count_limit"], 85)
                self.assertEqual(dimensions(), [])
                return [[1., 0.] for _ in texts]

            old.embed_documents.side_effect = switch_while_waiting_for_old_provider
            with self.captureOnCommitCallbacks(execute=True):
                embedding_by_document.run(str(doc.pk), old_id)
            self.assertEqual(self.http.get(base).json()["embedding_model_id"], new_id)
            self.assertEqual(dimensions(), [])
            self.assertEqual(self.http.get(base + "/documents/" + str(doc.pk)).json()["index_status"], "pending")
            enqueue.assert_called_with(str(doc.pk), new_id)
            # Deliver a stale legacy message restricted to a previous status. It must use the current model.
            embedding_by_document.run(str(doc.pk), old_id, state_list=["2"])
            self.assertEqual(dimensions(), [3])
            with connection.cursor() as cursor:
                cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", [f"embedding_hnsw_idx_{kb.pk}"])
                index = cursor.fetchone()
                self.assertIsNotNone(index)
                self.assertIn("vector(3)", index[0])
            embedding_by_knowledge.run(str(kb.pk), old_id)
            self.assertEqual(dimensions(), [3])
            enqueue.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.http.patch(base, change, format="json").status_code, 200)
            enqueue.assert_not_called()

    @skipUnless(connection.vendor == "postgresql", "Document creation includes paragraph arrays")
    def test_document_hit_settings_are_validated_and_portable(self):
        base = f"/v1/knowledge-bases/{self.kbs[0].pk}"
        settings = {"hit_handling_method": "directly_return", "directly_return_similarity": 0.82}
        response = self.http.post(base + "/documents", {"name": "Doc", "content": "Terms.", **settings}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        doc = response.json()["documents"][0]
        self.assertEqual(doc["hit_handling_method"], settings["hit_handling_method"])
        self.assertEqual(doc["directly_return_similarity"], settings["directly_return_similarity"])
        path = base + "/documents/" + doc["id"]
        self.assertEqual(self.http.patch(path, {"hit_handling_method": "invalid"}, format="json").status_code, 400)
        self.assertEqual(self.http.patch(path, {"directly_return_similarity": 2.1}, format="json").status_code, 400)
        updated = self.http.patch(path, {"directly_return_similarity": 1.1}, format="json")
        self.assertEqual(updated.json()["directly_return_similarity"], 1.1)
        archive = self.http.get(base + "/export").json()
        self.assertEqual(archive["documents"][0]["directly_return_similarity"], 1.1)
        self.assertEqual(self.http.post(base + "/import", archive, format="json").json()["skipped_documents"], 1)
        self.client_b.project.models.add(self.model_id)
        self.http.credentials(HTTP_AUTHORIZATION="Bearer " + self.key_b)
        target = f"/v1/knowledge-bases/{self.kbs[1].pk}"
        self.assertEqual(self.http.post(target + "/import", archive, format="json").status_code, 201)
        imported = Document.objects.get(knowledge=self.kbs[1], name="Doc")
        self.assertEqual(imported.directly_return_similarity, 1.1)
        self.assertEqual(imported.hit_handling_method, "directly_return")
