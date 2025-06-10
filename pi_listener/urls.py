# pi_listener/urls.py
from django.urls import path
from . import views

app_name = 'pi_listener'

urlpatterns = [
    path('update_status/', views.update_status_view, name='update_status'),
    #path('get_last_status/', views.get_last_status_view, name='get_last_status'),
    # --- ADAUGĂ ACEASTĂ LINIE ---
    path('status/', views.status_display_view, name='status_display'), # URL pentru pagina HTML
    path('send_command/', views.send_door_command_view, name='send_door_command'),
]
