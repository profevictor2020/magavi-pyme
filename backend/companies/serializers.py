from rest_framework import serializers

from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "rut", "is_active", "created_at", "role"]
        read_only_fields = ["id", "is_active", "created_at", "role"]

    def get_role(self, obj):
        request = self.context.get("request")
        membership = obj.memberships.filter(user=request.user, is_active=True).first()
        return membership.role if membership else None
