from rest_framework.routers import DefaultRouter
from .views_api import (
    CollectionTransferActionView,
    CollectionTransferListCreateView,
    LoginView,
    OperatorViewSet,
    RegisterView,
    TechnicianViewSet,
    TypeOfServiceViewSet,
    UserListCreateView,
    UserRetrieveUpdateDestroyView,
    UserViewSet,
    WorkFromTheRoleViewSet,
    MaterialViewSet,
    WorkReportListCreateView,
    WorkReportRetrieveUpdateDestroyView,
    WorkStbViewSet,
    login_user,
    register_user
)

from django.urls import path

urlpatterns = [
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", UserRetrieveUpdateDestroyView.as_view(), name="user-detail"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),

    path("users/register/", RegisterView.as_view(), name="register"),
    path("users/login/", LoginView.as_view(), name="login"),
    path("users/", UserListCreateView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserRetrieveUpdateDestroyView.as_view(), name="user-detail"),

    path("collection-transfers/", CollectionTransferListCreateView.as_view(), name="transfer-list-create"),
    path("collection-transfers/<int:pk>/action/", CollectionTransferActionView.as_view(), name="transfer-action"),


    path("workreports/", WorkReportListCreateView.as_view(), name="workreport-list"),
    path("workreports/<int:pk>/", WorkReportRetrieveUpdateDestroyView.as_view(), name="workreport-detail"),

    path('register/', register_user, name='register'),
    path('login/', login_user, name='login'),

]


router = DefaultRouter()
router.register('operators', OperatorViewSet)
router.register('service-types', TypeOfServiceViewSet)
router.register('roles', WorkFromTheRoleViewSet)
router.register('materials', MaterialViewSet)


router.register('technicians', TechnicianViewSet)
router.register('works', WorkStbViewSet)
router.register('users', UserViewSet)


urlpatterns += router.urls





