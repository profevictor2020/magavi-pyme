from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from audit.services import registrar_auditoria
from core.throttling import CompanyScopedRateThrottle

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        registrar_auditoria(
            company=None,
            user=user,
            action="auth.register",
            entity_type="User",
            entity_id=user.id,
        )
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=201,
        )


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LoginView(TokenObtainPairView):
    """Ver docs/SECURITY.md #2 (rate limiting agresivo contra fuerza
    bruta) y #10 (auditar login). `TokenObtainPairView` ya valida
    credenciales y no expone `request.user` (usa `AllowAny` +
    `authentication_classes = ()`), así que el usuario se busca por el
    email recién validado en vez de depender de `request.user`.
    """

    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.filter(email=request.data.get("email", "")).first()
            registrar_auditoria(
                company=None,
                user=user,
                action="auth.login",
                entity_type="User",
                entity_id=user.id if user else "",
            )
        return response


class LogoutView(TokenBlacklistView):
    """Invalida (blacklist) el refresh token y audita quién cerró sesión
    — a diferencia del login, aquí no hay email en el body, así que el
    usuario se identifica decodificando el propio refresh token.
    """

    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = None
            try:
                token = RefreshToken(request.data.get("refresh", ""))
                user = User.objects.filter(pk=token.get("user_id")).first()
            except TokenError:
                pass
            registrar_auditoria(
                company=None,
                user=user,
                action="auth.logout",
                entity_type="User",
                entity_id=user.id if user else "",
            )
        return response


class RefreshView(TokenRefreshView):
    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "auth"
