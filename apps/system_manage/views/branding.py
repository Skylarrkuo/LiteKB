import base64
import binascii
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.views import APIView

from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import RoleConstants
from common.result import result
from system_manage.models.system_setting import SettingType, SystemSetting


class BrandingSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, allow_blank=False)
    icon = serializers.CharField(max_length=350000, allow_blank=True, trim_whitespace=False)

    def validate_icon(self, value):
        if not value:
            return ''
        prefix = 'data:image/png;base64,'
        if not value.startswith(prefix):
            raise serializers.ValidationError('Choose a PNG image.')
        try:
            raw = base64.b64decode(value[len(prefix):], validate=True)
            if len(raw) > 256 * 1024:
                raise ValueError
            with Image.open(BytesIO(raw), formats=['PNG']) as image:
                if max(image.size) > 512 or image.is_animated:
                    raise ValueError
                image.verify()
            with Image.open(BytesIO(raw), formats=['PNG']) as image:
                clean = BytesIO()
                image.convert('RGBA').save(clean, format='PNG')
            if clean.tell() > 256 * 1024:
                raise ValueError
            return prefix + base64.b64encode(clean.getvalue()).decode('ascii')
        except (ValueError, OSError, SyntaxError, binascii.Error, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError('Choose a static PNG up to 512 × 512 and 256 KiB.') from exc


class BrandingAuthentication(TokenAuth):
    def authenticate(self, request):
        if request.method == 'PUT':
            return super().authenticate(request)
        return None


class BrandingView(APIView):
    authentication_classes = [BrandingAuthentication]

    def get(self, request):
        data = SystemSetting.objects.filter(type=SettingType.BRANDING).values_list('meta', flat=True).first()
        return result.success(data or {'name': 'LiteKB', 'icon': ''})

    @has_permissions(RoleConstants.ADMIN)
    def put(self, request):
        form = BrandingSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        SystemSetting.objects.update_or_create(type=SettingType.BRANDING, defaults={'meta': dict(form.validated_data)})
        return result.success(form.validated_data)
