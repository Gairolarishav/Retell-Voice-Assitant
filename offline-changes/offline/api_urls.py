from django.urls import path
from offline import api


urlpatterns = [
    path('schema/',api.offline_all_tables_structure,name="offline_all_tables_structure"),
    path('table-data/',api.offline_table_data,name="offline_table_data"),
    path('folder-table-data/',api.folder_table_data,name="folder_table_data"),
    path('single-entry-data/',api.online_entry_download,name="online_entry_download"),
    path('table-data-test/',api.offline_table_data_test,name="offline_table_data_test"),
    path('entries-sync/',api.offline_entries_sync,name="offline_entries_sync"),
    path('sync/',api.database_sync_view,name="database_sync_view"),
    path('sync-active-columns/',api.update_active_columns,name="update_active_columns"),
    path('send-qr-email/', api.qr_email_thread, name='send-qr-email'),
    path('address-equipment-file/', api.address_and_equipment_file, name='address_and_equipment_file'),
]