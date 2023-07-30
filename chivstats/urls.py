from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings

urlpatterns = [
    path('leaderboards/', include('leaderboards.urls')),
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/leaderboards/', permanent=True)),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),  # changed url to path
    ] + urlpatterns
