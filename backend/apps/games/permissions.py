from rest_framework.permissions import BasePermission

from .models import GameParticipant


class IsGameParticipant(BasePermission):
    message = "Vous devez participer à cette partie."

    def has_object_permission(self, request, view, obj):
        return GameParticipant.objects.filter(game=obj, user=request.user).exists()


class IsGameHost(BasePermission):
    message = "Seul l’hôte peut effectuer cette action."

    def has_object_permission(self, request, view, obj):
        return obj.host_id == request.user.id


class CanViewGame(BasePermission):
    message = "Cette partie est privée."

    def has_object_permission(self, request, view, obj):
        if (
            obj.visibility == obj.Visibility.PUBLIC
            and obj.status == obj.Status.WAITING
        ):
            return True
        return GameParticipant.objects.filter(game=obj, user=request.user).exists()
