"""
URL configuration for repair_service project.
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from requests_app.views.auth import RoleBasedLoginView, RoleBasedLogoutView, RootView, TestMessagesView, GetFreeMasterView, GetMasterUsernameView, GetRandomMasterView

urlpatterns = [
    path('', RootView.as_view(), name='root'),
    path('admin/', admin.site.urls),
    path('login/', RoleBasedLoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', RoleBasedLogoutView.as_view(), name='logout'),
    path('test/messages/', TestMessagesView.as_view(), name='test-messages'),
    path('test/get_free_master/', GetFreeMasterView.as_view(), name='get-free-master'),
    path('test/get_random_master/', GetRandomMasterView.as_view(), name='get-random-master'),
    path('test/get_master_username/<int:pid>/', GetMasterUsernameView.as_view(), name='get-master-username'),
    path('client/', include('requests_app.urls.client')),
    path('master/', include('requests_app.urls.master')),
    path('dispatcher/', include('requests_app.urls.dispatcher')),
]
