from collections.abc import Mapping

from rest_framework import serializers


class Input(serializers.Serializer):
    """Reject unrecognized fields instead of passing unchecked input to legacy serializers."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - self.fields.keys()
            if unknown:
                raise serializers.ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class KnowledgeCreate(Input):
    name = serializers.CharField(max_length=64)
    description = serializers.CharField(max_length=256, required=False, default="", allow_blank=True)
    embedding_model_id = serializers.UUIDField()


class KnowledgeEdit(Input):
    name = serializers.CharField(max_length=64, required=False)
    description = serializers.CharField(max_length=256, required=False, allow_blank=True)
    file_size_limit = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    file_count_limit = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    embedding_model_id = serializers.UUIDField(required=False)


class ParagraphContent(Input):
    title = serializers.CharField(max_length=256, allow_blank=True, required=False, default="")
    content = serializers.CharField(max_length=102400, trim_whitespace=False)


class ParagraphEdit(ParagraphContent):
    is_active = serializers.BooleanField(required=False)


class DocumentSettings(Input):
    hit_handling_method = serializers.ChoiceField(choices=("optimization", "directly_return"), required=False)
    directly_return_similarity = serializers.FloatField(min_value=0, max_value=2, required=False)


class DocumentCreate(DocumentSettings):
    name = serializers.CharField(max_length=128)
    paragraphs = ParagraphContent(many=True, allow_empty=False, max_length=10000, required=False)
    content = serializers.CharField(max_length=10_000_000, trim_whitespace=False, required=False)
    source_file_id = serializers.UUIDField(required=False)

    def validate(self, data):
        if ("paragraphs" in data) == ("content" in data):
            raise serializers.ValidationError("Supply either content or paragraphs.")
        return data


class DocumentEdit(DocumentSettings):
    name = serializers.CharField(max_length=128, required=False)
    is_active = serializers.BooleanField(required=False)


class UploadInput(Input):
    file = serializers.FileField()

    def to_internal_value(self, data):
        if hasattr(data, "getlist") and len(data.getlist("file")) != 1:
            raise serializers.ValidationError({"file": "Supply one file per request."})
        return super().to_internal_value(data)


class FileInput(UploadInput):
    split_length = serializers.IntegerField(default=4096, min_value=32, max_value=102400)


class RetrieveInput(Input):
    knowledge_base_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=20)
    query = serializers.CharField(max_length=10240)
    top_k = serializers.IntegerField(min_value=1, max_value=100, default=5)
    min_score = serializers.FloatField(min_value=0, max_value=2, default=0)
    mode = serializers.ChoiceField(choices=("embedding", "keywords", "blend", "rrf"), default="embedding")


def validated(cls, data, *, partial=False):
    serializer = cls(data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
