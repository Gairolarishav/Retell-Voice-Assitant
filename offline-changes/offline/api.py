from django.db import connection
from rest_framework.decorators import api_view,authentication_classes, permission_classes
from rest_framework.response import Response
from django.utils import timezone
import json
from django.http import JsonResponse
from accounts.models import User
from forms.models import Entries,EntryDetails,Form,FormField,EntryUpdateHistory,Deletion,form_columns,EntryNotes
from folder.models import FolderEntries,Folders
from forms.views import check_submission_limits_mobile,add_submission_mobile,submission_limit_notification
from enggforms.methods import send_form_notification,set_db_connection
from django.db import transaction
from datetime import datetime, timedelta
from django.core.files.storage import FileSystemStorage
import uuid 
import os 
from rest_framework import status
from django.db import connections
from django.conf import settings
from dateutil.parser import parse
from django.apps import apps
from settings_app.models import SettingsModel
import csv


# Mapping MySQL data types to SQLite data types
MYSQL_TO_SQLITE_TYPE_MAPPING = {
    "INT": "INTEGER",
    "BIGINT": "INTEGER",
    "TINYINT": "INTEGER",
    "SMALLINT": "INTEGER",
    "MEDIUMINT": "INTEGER",
    "VARCHAR": "TEXT",
    "CHAR": "TEXT",
    "TEXT": "TEXT",
    "BLOB": "BLOB",
    "DATETIME": "TEXT",
    "TIMESTAMP": "TEXT",
    "DATE": "TEXT",
    "TIME": "TEXT",
    "DECIMAL": "REAL",
    "DOUBLE": "REAL",
    "FLOAT": "REAL"
}


@api_view(["GET"])
def offline_all_tables_structure(request):
        
    # List of tables to process
    tables = [
        'auth_user', 'capabilities', 'capability_permissions', 'categories', 'forms', 'form_columns',
        'form_permissions', 'form_fields', 'roles', 'roles_form_permissions', 'role_permissions',
        'role_users', 'user_form_permissions', 'entries', 'entry_details', 'entry_flags', 'entry_notes',
        'entry_rules', 'entry_update_history','submission_details', 'folders', 'folder_entries', 'folder_request_access',
        'folder_roles_capabilities', 'folder_users_capabilities', 'folder_user_access','form_certificates' , 'form_notifications','certificate_rules'
    ]

    # Special column additions for specific tables
    additional_columns = {
        'entries': ["is_sync INTEGER", "server_id INTEGER"],
        'entry_details': ["server_id INTEGER", "entry_server_id INTEGER"],
        'entry_notes': ["server_id INTEGER", "entry_server_id INTEGER"],
        'entry_flags': ["server_id INTEGER", "entry_server_id INTEGER"],
        'entry_update_history': ["server_id INTEGER", "entry_server_id INTEGER"],
        'submission_details': ["server_id INTEGER", "entry_server_id INTEGER"],
        'folder_entries': ["server_id INTEGER", "entry_server_id INTEGER"]
    }

    # Additional custom table structures
    custom_tables = {
        'deletions': """CREATE TABLE deletions (id INTEGER PRIMARY KEY AUTOINCREMENT,table_name VARCHAR(255) NOT NULL,record_id INTEGER NOT NULL,deleted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,sync_status TEXT NOT NULL DEFAULT 'pending' CHECK(sync_status IN ('pending', 'synced', 'failed')),last_synced_at TIMESTAMP,error_message TEXT);""",
        'app_config': """CREATE TABLE IF NOT EXISTS app_config (id INTEGER PRIMARY KEY AUTOINCREMENT,config_key TEXT NOT NULL UNIQUE,config_value TEXT NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""",
        'sync_metadata': """CREATE TABLE sync_metadata (id INTEGER PRIMARY KEY AUTOINCREMENT,table_name TEXT NOT NULL,request TEXT NOT NULL,last_synced_at TEXT NOT NULL)""",
    }

    # Dictionary to store SQL queries for each table
    table_queries = {}

    with connection.cursor() as cursor:
        for table_name in tables:
            try:
                # Fetch column details from INFORMATION_SCHEMA
                cursor.execute(f"""
                    SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = %s AND TABLE_SCHEMA = DATABASE();
                """, [table_name])

                # Start building the CREATE TABLE command
                columns_sql = []
                for column in cursor.fetchall():
                    column_name = column[0]
                    # Handle reserved keywords
                    if column_name.upper() in {"VALUES", "ADD", "DELETE"}:
                        column_name = f'"{column_name}"'

                    mysql_type = column[1].upper()
                    primary_key = column[2] == "PRI"
                    nullable = column[3] == "YES"

                    # Map MySQL type to SQLite type
                    sqlite_type = MYSQL_TO_SQLITE_TYPE_MAPPING.get(mysql_type, "TEXT")
                    column_definition = f'{column_name} {sqlite_type}'

                    # Add NOT NULL if not nullable
                    if not nullable:
                        column_definition += " NOT NULL"

                    # Add PRIMARY KEY if applicable
                    if primary_key:
                        column_definition += " PRIMARY KEY"

                    columns_sql.append(column_definition)

                # Add additional columns for specific tables
                if table_name in additional_columns:
                    columns_sql.extend(additional_columns[table_name])

                # Add foreign key constraints unless it's auth_user table
                if table_name != 'auth_user':
                    # Add foreign key constraints
                    cursor.execute("""
                        SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA = DATABASE();
                    """, [table_name])

                    foreign_keys = cursor.fetchall()

                    # Combine all column definitions into a single string
                    create_statement = f'CREATE TABLE {table_name} ({", ".join(columns_sql)});'
                    table_queries[table_name] = [create_statement]

                    for fk_column, ref_table, ref_column in foreign_keys:
                        fk_def = f"FOREIGN KEY ({fk_column}) REFERENCES {ref_table}({ref_column}) ON DELETE CASCADE"
                        columns_sql.append(fk_def)

                # Final CREATE TABLE SQL
                create_statement = f"CREATE TABLE {table_name} ({', '.join(columns_sql)});"
                table_queries[table_name] = [create_statement]


            except Exception as e:
                # Log error and store it in the dictionary
                table_queries[table_name] = [f"-- Error processing table {table_name}: {str(e)}"]

    # Add custom table structures
    table_queries.update({key: [query] for key, query in custom_tables.items()})
    
    # Prepare JSON response
    response = {
        "table_queries": table_queries
    }
    return Response(response)


# Reserved Keywords in MySQL/MariaDB
RESERVED_KEYWORDS = {
    "add", "all", "alter", "analyze", "and", "as", "asc", "before", "between", "both",
    "by", "case", "check", "column", "constraint", "create", "cross", "current_date", 
    "database", "default", "delete", "desc", "distinct", "drop", "else", "exists", 
    "false", "from", "group", "having", "if", "index", "insert", "into", "is", "join",
    "key", "left", "like", "limit", "lock", "match", "not", "null", "on", "option",
    "or", "order", "outer", "primary", "references", "rename", "replace", "restrict",
    "right", "select", "set", "show", "table", "then", "to", "union", "unique", 
    "update", "use", "values", "where", "while"
}

def escape_reserved_keywords(row):
    """
    Escapes reserved keywords in MySQL/MariaDB for column names.
    """
    return {
        f"`{key}`" if key.lower() in RESERVED_KEYWORDS else key: value
        for key, value in row.items()
    }

@api_view(["POST"])
def offline_table_data(request):
    if request.user.is_authenticated:
        user_id = request.user.id
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': f'User with ID {user_id} not found'}, status=404)
        table_name = request.data.get('table_name')
        # sync_month = int(request.data.get('sync_month', '1'))
        # print("sync_month ==", sync_month)

        if table_name == 'entries':
            # days_for_sync = sync_month * 30
            # today = timezone.now().date()
            # three_months_ago = today - timedelta(days=days_for_sync)

            with connection.cursor() as cursor:
                # Get entries
                entry_query = """
                SELECT * FROM entries
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 20
                """
                cursor.execute(entry_query, [user.id])
                entries = cursor.fetchall()
                entry_columns = [col[0] for col in cursor.description]

                structured_data = []
                for entry in entries:
                    entry_dict = dict(zip(entry_columns, entry))
                    entry_id = entry_dict['id']

                    # Get entry details
                    cursor.execute("""
                        SELECT id AS server_id,value,created_at,updated_at,entry_id AS entry_server_id,field_id,info  FROM entry_details 
                        WHERE entry_id = %s
                    """, [entry_id])
                    details_columns = [col[0] for col in cursor.description]
                    details = [dict(zip(details_columns, row)) for row in cursor.fetchall()]

                    # Get entry notes
                    cursor.execute("""
                        SELECT id AS server_id,note,created_at,entry_id AS entry_server_id,user_id FROM entry_notes 
                        WHERE entry_id = %s
                    """, [entry_id])
                    notes_columns = [col[0] for col in cursor.description]
                    notes = [dict(zip(notes_columns, row)) for row in cursor.fetchall()]

                    # Get entry flags
                    cursor.execute("""
                        SELECT id AS server_id,created_at,entry_id AS entry_server_id,flagged_by_id,flagged_to_id,
                        flag_text,cleared,cleared_by_id,flagged_reason FROM entry_flags 
                        WHERE entry_id = %s
                    """, [entry_id])
                    flags_columns = [col[0] for col in cursor.description]
                    flags = [dict(zip(flags_columns, row)) for row in cursor.fetchall()]
                    
                    # Get entry update history
                    cursor.execute("""
                        SELECT id AS server_id,updated_at,entry_id AS entry_server_id,user_id FROM entry_update_history
                        WHERE entry_id = %s
                    """, [entry_id])
                    history_columns = [col[0] for col in cursor.description]
                    history = [dict(zip(history_columns, row)) for row in cursor.fetchall()]
                    
                    # Get submission_details
                    cursor.execute("""
                        SELECT id AS server_id,created_at,action_type,entry_id AS entry_server_id,user_id FROM submission_details
                        WHERE entry_id = %s
                    """, [entry_id])
                    submission_details_columns = [col[0] for col in cursor.description]
                    submission_details = [dict(zip(submission_details_columns, row)) for row in cursor.fetchall()]

                    # Get folder_details
                    cursor.execute("""
                        SELECT id AS server_id,created_at,updated_at,entry_id AS entry_server_id,folder_id FROM folder_entries
                        WHERE entry_id = %s
                    """, [entry_id])
                    folder_entries_columns = [col[0] for col in cursor.description]
                    folder_entries = [dict(zip(folder_entries_columns, row)) for row in cursor.fetchall()]

                    # Structure the data
                    entry_data = {
                        'entries': {
                            'server_id': entry_dict['id'],
                            'created_at': entry_dict['created_at'].isoformat() if entry_dict['created_at'] else None,
                            'updated_at': entry_dict['updated_at'].isoformat() if entry_dict['updated_at'] else None,
                            'form_id': entry_dict['form_id'],
                            'is_approved': entry_dict['is_approved'],
                            'is_trash': entry_dict['is_trash'],
                            'user_id': entry_dict['user_id'],
                            'is_read': entry_dict['is_read'],
                            'is_flagged': entry_dict['is_flagged'],
                            'type': entry_dict['type'],
                            'location': entry_dict['location'],
                            'flagged_at': entry_dict['flagged_at'].isoformat() if entry_dict['flagged_at'] else None,
                            'is_sync' : 1
                        },
                        'entry_details': details,
                        'entry_notes': notes,
                        'entry_flags': flags,
                        'entry_update_history': history,
                        'submission_details': submission_details,
                        'folder_entries': folder_entries,
                    }
                    structured_data.append(entry_data)

                return Response({
                    'status': True,
                    'message': 'Data fetched successfully',
                    'data': structured_data
                })

        elif table_name == 'app_config':
            current_db = connections.databases['default']['NAME']
            print("current_db ===", current_db)
            data = [
                    {"config_key": "account_db_name", "config_value": current_db}
                ]


        elif table_name == 'sync_metadata':
            current_db = connections.databases['default']['NAME']
            current_timestamp = datetime.utcnow().isoformat() + "Z"  # Adding "Z" to indicate UTC time
            print("current_db ===", current_db)
            data = [
                    {"table_name": "all table","request":"POST" ,"last_synced_at": current_timestamp},
                    {"table_name": "all table","request":"GET" ,"last_synced_at": current_timestamp}
                ]

        # elif table_name == 'folder_entries':
        #     days_for_sync = sync_month * 30
        #     today = timezone.now().date()
        #     three_months_ago = today - timedelta(days=days_for_sync)

        #     with connection.cursor() as cursor:
        #         # Get entries
        #         entry_query = f"""
        #         SELECT * FROM `{table_name}` 
        #         WHERE updated_at >= %s 
        #         ORDER BY updated_at DESC
        #         """
        #         cursor.execute(entry_query, [three_months_ago])
        #         entries = cursor.fetchall()
        #         entry_columns = [col[0] for col in cursor.description]  
        #         data = [dict(zip(entry_columns, row)) for row in entries]     
 
        else:
            # Fetch table data
            with connection.cursor() as cursor:
                # Escape table name with backticks
                cursor.execute(f"SELECT * FROM `{table_name}`")
                columns = [col[0] for col in cursor.description]
                data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Escape reserved keyword columns (like `values`)
        escaped_data = [escape_reserved_keywords(row) for row in data]

        response = {
            "name": table_name,
            "data": escaped_data
        }
        return Response(response)

    else:
        return Response({"message": "User is not authenticated"}, status=401)


@api_view(["POST"])        
def folder_table_data(request):
    if request.user.is_authenticated:
        user_id = request.user.id
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': f'User with ID {user_id} not found'}, status=404)
        table_name = request.data.get('table_name')
        folder_id = request.data.get('folder_id')

        try:
            folder = Folders.objects.get(id=folder_id)
        except Folders.DoesNotExist:
            return JsonResponse({'error': f'Folder with ID {folder_id} not found'}, status=404)

        # Use the existing recursive method to get all children (including itself)
        all_children = folder.get_all_children()

        # Extract only the IDs (excluding the root folder if needed)
        folder_ids = [f.id for f in all_children]  # exclude root if you want
        # sync_month = int(request.data.get('sync_month', '1'))
        # user_id = int(request.data.get('user_id'))

        if table_name == 'folder_entries':
            # days_for_sync = sync_month * 30
            # today = timezone.now().date()
            # three_months_ago = today - timedelta(days=days_for_sync)

            with connection.cursor() as cursor:
                format_strings = ','.join(['%s'] * len(folder_ids))  # creates: %s,%s,%s,...
                # Get entries
                folder_entry_query = f"""
                SELECT id AS server_id,created_at,updated_at,entry_id AS entry_server_id,folder_id FROM folder_entries
                WHERE folder_id IN ({format_strings}) ORDER BY updated_at DESC  """
                cursor.execute(folder_entry_query, folder_ids)
                folder_entries = cursor.fetchall()
                folder_entry_columns = [col[0] for col in cursor.description]

                structured_data = []
                for folder_entry in folder_entries:
                    folder_entry_dict = dict(zip(folder_entry_columns, folder_entry))
                    folder_entry_id = folder_entry_dict['entry_server_id']
                    # print("folder_entry_id===", folder_entry_id)
                    
                    # 2. Get the main entry from entries table
                    cursor.execute("""
                        SELECT * FROM entries
                        WHERE id = %s
                    """, [folder_entry_id])
                    entry_row = cursor.fetchone()
                    if not entry_row:
                        continue  # Skip if entry is not found (should not happen, but safety)
                    entry_columns = [col[0] for col in cursor.description]
                    entry_dict = dict(zip(entry_columns, entry_row))

                    # Get entry details
                    cursor.execute("""
                        SELECT id AS server_id,value,created_at,updated_at,entry_id AS entry_server_id,field_id,info  FROM entry_details 
                        WHERE entry_id = %s
                    """, [folder_entry_id])
                    details_columns = [col[0] for col in cursor.description]
                    details = [dict(zip(details_columns, row)) for row in cursor.fetchall()]

                    # Get entry notes
                    cursor.execute("""
                        SELECT id AS server_id,note,created_at,entry_id AS entry_server_id,user_id FROM entry_notes 
                        WHERE entry_id = %s
                    """, [folder_entry_id])
                    notes_columns = [col[0] for col in cursor.description]
                    notes = [dict(zip(notes_columns, row)) for row in cursor.fetchall()]

                    # Get entry flags
                    cursor.execute("""
                        SELECT id AS server_id,created_at,entry_id AS entry_server_id,flagged_by_id,flagged_to_id,
                        flag_text,cleared,cleared_by_id,flagged_reason FROM entry_flags 
                        WHERE entry_id = %s
                    """, [folder_entry_id])
                    flags_columns = [col[0] for col in cursor.description]
                    flags = [dict(zip(flags_columns, row)) for row in cursor.fetchall()]
                    
                    # Get entry update history
                    cursor.execute("""
                        SELECT id AS server_id,updated_at,entry_id AS entry_server_id,user_id FROM entry_update_history
                        WHERE entry_id = %s
                    """, [folder_entry_id])
                    history_columns = [col[0] for col in cursor.description]
                    history = [dict(zip(history_columns, row)) for row in cursor.fetchall()]
                    
                    # Get submission_details
                    cursor.execute("""
                        SELECT id AS server_id,created_at,action_type,entry_id AS entry_server_id,user_id FROM submission_details
                        WHERE entry_id = %s
                    """, [folder_entry_id])
                    submission_details_columns = [col[0] for col in cursor.description]
                    submission_details = [dict(zip(submission_details_columns, row)) for row in cursor.fetchall()]

                    # Structure the data
                    entry_data = {
                        'entries': {
                            'server_id': entry_dict['id'],
                            'created_at': entry_dict['created_at'].isoformat() if entry_dict['created_at'] else None,
                            'updated_at': entry_dict['updated_at'].isoformat() if entry_dict['updated_at'] else None,
                            'form_id': entry_dict['form_id'],
                            'is_approved': entry_dict['is_approved'],
                            'is_trash': entry_dict['is_trash'],
                            'user_id': entry_dict['user_id'],
                            'is_read': entry_dict['is_read'],
                            'is_flagged': entry_dict['is_flagged'],
                            'type': entry_dict['type'],
                            'location': entry_dict['location'],
                            'flagged_at': entry_dict['flagged_at'].isoformat() if entry_dict['flagged_at'] else None,
                            'is_sync' : 1
                        },
                        'entry_details': details,
                        'entry_notes': notes,
                        'entry_flags': flags,
                        'entry_update_history': history,
                        'submission_details': submission_details,
                        'folder_entries': {
                            'server_id': folder_entry_dict['server_id'],
                            'created_at': folder_entry_dict['created_at'].isoformat() if folder_entry_dict['created_at'] else None,
                            'updated_at': folder_entry_dict['updated_at'].isoformat() if folder_entry_dict['updated_at'] else None,
                            'entry_server_id': folder_entry_dict['entry_server_id'],
                            'folder_id': folder_entry_dict['folder_id']
                        },
                    }
                    structured_data.append(entry_data)

                return Response({
                    'status': True,
                    'message': 'Data fetched successfully',
                    'data': structured_data
                })

    else:
        return Response({"message": "User is not authenticated"}, status=401)


import concurrent.futures

def sanitize_column_name(column):
    """
    Sanitize SQLite column names by adding a prefix to reserved keywords
    """
    # Common SQLite reserved keywords
    sqlite_reserved = {
        'abort', 'action', 'add', 'after', 'all', 'alter', 'analyze', 'and', 'as', 'asc',
        'attach', 'autoincrement', 'before', 'begin', 'between', 'by', 'cascade', 'case',
        'cast', 'check', 'collate', 'column', 'commit', 'conflict', 'constraint', 'create',
        'cross', 'current_date', 'current_time', 'current_timestamp', 'database', 'default',
        'deferrable', 'deferred', 'delete', 'desc', 'detach', 'distinct', 'drop', 'each',
        'else', 'end', 'escape', 'except', 'exclusive', 'exists', 'explain', 'fail', 'for',
        'foreign', 'from', 'full', 'glob', 'group', 'having', 'if', 'ignore', 'immediate',
        'in', 'index', 'indexed', 'initially', 'inner', 'insert', 'instead', 'intersect',
        'into', 'is', 'isnull', 'join', 'key', 'left', 'like', 'limit', 'match', 'natural',
        'no', 'not', 'notnull', 'null', 'of', 'offset', 'on', 'or', 'order', 'outer', 'plan',
        'pragma', 'primary', 'query', 'raise', 'recursive', 'references', 'regexp', 'reindex',
        'release', 'rename', 'replace', 'restrict', 'right', 'rollback', 'row', 'savepoint',
        'select', 'set', 'table', 'temp', 'temporary', 'then', 'to', 'transaction', 'trigger',
        'union', 'unique', 'update', 'using', 'vacuum', 'values', 'view', 'virtual', 'when',
        'where', 'with', 'without'
    }
    
    if column.lower() in sqlite_reserved:
        return f'"{column}"'
    return column


@api_view(["POST"])
def offline_table_data_test(request):
    if not request.user.is_authenticated:
        return Response({"message": "User is not authenticated"}, status=401)

    table_name = request.data.get("table_name")
    sync_month = int(request.data.get("sync_month", "1"))
    days_for_sync = sync_month * 30
    today = timezone.now().date()
    three_months_ago = today - timedelta(days=days_for_sync)

    def fetch_data(query, params):
        """Helper function to execute a query and fetch all results."""
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            return columns, cursor.fetchall()

    if table_name == "entries":
        # Get entries
        entry_query = """
        SELECT id AS server_id, created_at, updated_at, form_id, is_approved, 
               is_trash, user_id, is_read, is_flagged, type, location, flagged_at 
        FROM entries 
        WHERE updated_at >= %s 
        ORDER BY updated_at DESC
        """
        entry_columns, entries = fetch_data(entry_query, [three_months_ago])

        if not entries:
            return Response({"status": True, "message": "No data found", "data": []})

        # Initialize accumulator lists
        entry_value = []
        entry_columnsss = None
        entrydetail_value = []
        entrydetail_columnsss = None
        entrynotes_value = []
        entrynotes_columnsss = None
        entryflags_value = []
        entryflags_columnsss = None
        entryhistory_value = []
        entryhistory_columnsss = None
        entrysubmission_details_value = []
        entrysubmission_details_columnsss = None
        entryfolder_entries_value = []
        entryfolder_entries_columnsss = None

        # Collect entry IDs for batch queries
        entry_ids = tuple(entry[0] for entry in entries)

        # Fetch all related data in bulk
        related_queries = {
            "entry_details": """
                SELECT id AS server_id, value, created_at, updated_at, entry_id AS entry_server_id, field_id, info
                FROM entry_details WHERE entry_id IN %s
            """,
            "entry_notes": """
                SELECT id AS server_id, note, created_at, entry_id AS entry_server_id, user_id
                FROM entry_notes WHERE entry_id IN %s
            """,
            "entry_flags": """
                SELECT id AS server_id, created_at, entry_id AS entry_server_id, flagged_by_id, flagged_to_id,
                       flag_text, cleared, cleared_by_id, flagged_reason
                FROM entry_flags WHERE entry_id IN %s
            """,
            "entry_update_history": """
                SELECT id AS server_id, updated_at, entry_id AS entry_server_id, user_id
                FROM entry_update_history WHERE entry_id IN %s
            """,
            "submission_details": """
                SELECT id AS server_id, created_at, action_type, entry_id AS entry_server_id, user_id
                FROM submission_details WHERE entry_id IN %s
            """,
            "folder_entries": """
                SELECT id AS server_id, created_at, updated_at, entry_id AS entry_server_id, folder_id
                FROM folder_entries WHERE entry_id IN %s
            """
        }

        # Fetch all related data in parallel
        def fetch_related_data(query_info):
            key, query = query_info
            columns, rows = fetch_data(query, [entry_ids])
            return key, {"columns": columns, "values": rows}

        related_data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_query = {
                executor.submit(fetch_related_data, (key, query)): key 
                for key, query in related_queries.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_query):
                key, data = future.result()
                related_data[key] = data

        # Process entries
        structured_data = []
        for entry in entries:
            entry_dict = dict(zip(entry_columns, entry))
            
            if entry_dict:
                entry_columnsss = entry_columns
                entry_value.append(list(entry_dict.values()))

        # Process related data
        if related_data.get("entry_details", {}).get("values"):
            entrydetail_columnsss = related_data["entry_details"]["columns"]
            entrydetail_value.extend([list(row) for row in related_data["entry_details"]["values"]])

        if related_data.get("entry_notes", {}).get("values"):
            entrynotes_columnsss = related_data["entry_notes"]["columns"]
            entrynotes_value.extend([list(row) for row in related_data["entry_notes"]["values"]])

        if related_data.get("entry_flags", {}).get("values"):
            entryflags_columnsss = related_data["entry_flags"]["columns"]
            entryflags_value.extend([list(row) for row in related_data["entry_flags"]["values"]])

        if related_data.get("entry_update_history", {}).get("values"):
            entryhistory_columnsss = related_data["entry_update_history"]["columns"]
            entryhistory_value.extend([list(row) for row in related_data["entry_update_history"]["values"]])

        if related_data.get("submission_details", {}).get("values"):
            entrysubmission_details_columnsss = related_data["submission_details"]["columns"]
            entrysubmission_details_value.extend([list(row) for row in related_data["submission_details"]["values"]])

        if related_data.get("folder_entries", {}).get("values"):
            entryfolder_entries_columnsss = related_data["folder_entries"]["columns"]
            entryfolder_entries_value.extend([list(row) for row in related_data["folder_entries"]["values"]])

        entry_data = {
            'entries': {
                'columns': entry_columnsss,
                'values': entry_value
            },
            'entry_details': {
                'columns': entrydetail_columnsss,
                'values': entrydetail_value
            },
            'entry_notes': {
                'columns': entrynotes_columnsss,
                'values': entrynotes_value
            },
            'entry_flags': {
                'columns': entryflags_columnsss,
                'values': entryflags_value
            },
            'entry_update_history': {
                'columns': entryhistory_columnsss,
                'values': entryhistory_value
            },
            'submission_details': {
                'columns': entrysubmission_details_columnsss,
                'values': entrysubmission_details_value
            },
            'folder_entries': {
                'columns': entryfolder_entries_columnsss,
                'values': entryfolder_entries_value
            }
        }

        structured_data.append(entry_data)

        return Response({
            'status': True,
            'message': 'Data fetched successfully',
            'data': structured_data
        })

    elif table_name == 'app_config':
        current_db = connection.settings_dict["NAME"]
        data = [{"config_key": "account_db_name", "config_value": current_db}]
        columns = list(data[0].keys())
        values = [list(d.values()) for d in data]
        return Response({
            "name": table_name,
            "columns": columns,
            "data": values
        })

    elif table_name == 'sync_metadata':
        current_timestamp = datetime.utcnow().isoformat() + "Z"
        data = [{"table_name": "all table", "last_synced_at": current_timestamp}]
        columns = list(data[0].keys())
        values = [list(d.values()) for d in data]
        return Response({
            "name": table_name,
            "columns": columns,
            "data": values
        })

    else:
        query = f"SELECT * FROM `{table_name}`"
        columns, rows = fetch_data(query, [])

        # Sanitize column names
        safe_columns = [sanitize_column_name(col) for col in columns]
        if not rows:
            return Response({
                "name": table_name,
                "columns": [],
                "data": []
            })
        
        return Response({
            "name": table_name,
            "columns": safe_columns,
            "data": rows
        })


def form_upload_path(request):
    current_db = connections.databases['default']['NAME']
    print("current_db ===", current_db)
    try:
        relative_path = 'form'
        if current_db != 'enggforms':
            relative_path = f"{relative_path}/{current_db}"
        
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
            os.chmod(full_path, 0o777)

        print("full_path ===", full_path)
        return relative_path + '/'
    except Exception as e:
        print("Cannot create folder", str(e))

def handle_file_upload(request, file_data):
    """Handles file uploads and returns the saved file name."""
    try:
        fs = FileSystemStorage()
        file = file_data.get('file')
        print("file======", file)
        if file:
            ext = file.name.split('.')[-1]
            filename = f"{uuid.uuid4()}.{ext}"
            fs.save(form_upload_path(request) + filename, file)
            print("filename======", filename)
            return filename
        return None
    except Exception as e:
        print("Error handling file upload:", str(e))
        raise e


@api_view(["POST"])
def offline_entries_sync(request):
    try:
        print("offline_entries_sync ===========nowkkkkk")
        user_id = request.user.id
        entries_data = request.data.get('alldata')
        print("entries_data ===now data for sync", entries_data)

        if not entries_data:
            return JsonResponse({'error': 'No entries provided'}, status=400)

        # Better JSON handling
        try:
            if isinstance(entries_data, list):
                entries_data = entries_data[0]
            entries_data = json.loads(entries_data) if isinstance(entries_data, str) else entries_data
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        uploaded_files = request.FILES.getlist('files')
        print("uploaded_files ===", uploaded_files)
        files_map = {}
        for file in uploaded_files:
            try:
                field_id, actual_name = file.name.split("_", 1)
                field_id = int(field_id)
                if field_id:
                    files_map[field_id] = handle_file_upload(request, {'file': file})
            except ValueError:
                return JsonResponse({'error': f'Invalid file name format: {file.name}'}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': f'User with ID {user_id} not found'}, status=404)

        successful_entries = []
        failed_entries = []

        print("files_map ===", files_map)

        for entry_data in entries_data:
            print("entry_data =====kkkkkk", entry_data)
            try:
                entry_id = entry_data.get('entry_id')
                type = entry_data.get('type')
                server_id = entry_data.get('server_id')
                form_id = entry_data.get('form_id')
                entry_type = entry_data.get('type')
                details = entry_data.get('details')
                notes = entry_data.get('notes')


                if not form_id or not details:
                    failed_entries.append({
                        'entry': entry_data,
                        'error': 'Missing form_id or details'
                    })
                    continue

                try:
                    form = Form.objects.get(pk=form_id)
                except Form.DoesNotExist:
                    print('error : ', f'Form with ID {form_id} not found')
                    failed_entries.append({
                        'entry': entry_data,
                        'error': f'Form with ID {form_id} not found'
                    })
                    continue

                limit_info = check_submission_limits_mobile(request, user)
                if not limit_info['remaining_limit']:
                    failed_entries.append({
                        'entry': entry_data,
                        'error': limit_info['msg']
                    })
                    continue

                
                # Better server_id handling
                if server_id:
                    try:
                        entry = Entries.objects.get(id=server_id)
                    except Entries.DoesNotExist:
                        entry = Entries.objects.create(form=form, user_id=user_id, type=entry_type)

                else:
                    # Create a new entry if it doesn't exist
                    entry = Entries.objects.create(form=form, user_id=user_id, type=entry_type)


                note_id_to_local_id = {}

                # Delete existing notes for this entry
                EntryNotes.objects.filter(entry=entry).delete()

                # Process Notes Data
                print("notes -======", notes)
                for note in notes:
                    local_note_id  = note.get('note_id')
                    note_text  = note.get('note')
                    entry_notes_created_at = note.get('entry_notes_created_at')
                    note_user_id  = note.get('user_id')

                    created_note = EntryNotes.objects.create(entry=entry, user_id=note_user_id, note=note_text,created_at = entry_notes_created_at)

                    # Map the local note ID to the generated note ID
                    if local_note_id:
                        note_id_to_local_id[str(local_note_id)] = {
                            'id': created_note.id,
                            'created_at': created_note.created_at
                        }


                entry_details_to_create = []
                entry_details_to_update = {}
                field_id_to_local_id = {}

                for detail in details:
                    field_id = detail.get('field_id')
                    value = detail.get('value')
                    info = detail.get('info', None)
                    local_entry_detail_id = detail.get('entry_detail_id')

                    print(f"Processing detail - field_id: {field_id}, local_entry_detail_id: {local_entry_detail_id}")

                    try:
                        form_field = FormField.objects.get(pk=field_id)

                    except FormField.DoesNotExist:
                        print(f"Field with ID {field_id} not found")
                        continue

                    if field_id in files_map:
                        # Get existing entry detail to check for previous file
                        existing_detail = EntryDetails.objects.filter(entry=entry, field_id=field_id).first()
                        print("existing_detail====", existing_detail)
                        if existing_detail and existing_detail.value:
                            # Delete the previous file if it exists
                            try:
                                # Construct the file path
                                dir_path = os.path.join(settings.MEDIA_ROOT, 'form')
                                current_db = connections.databases['default']['NAME']
                                print("current_db=======for deltion ==", current_db)
                                
                                if current_db != 'enggforms':
                                    dir_path = os.path.join(dir_path, current_db)
                                
                                file_path = os.path.join(dir_path, existing_detail.value)
                                
                                # Try to delete the file
                                if os.path.exists(file_path):
                                    try:
                                        os.remove(file_path)
                                        print(f"Successfully deleted file: {file_path}")
                                    except (OSError, PermissionError) as e:
                                        error_msg = f"Error deleting file {file_path}: {str(e)}"
                                        print(error_msg)
                                        file_deletion_errors.append({
                                            'entry_id': entry_id,
                                            'field_id': field_id,
                                            'file_path': file_path,
                                            'error': error_msg
                                        })
                                        # Continue processing despite deletion error
                            except Exception as e:
                                error_msg = f"Unexpected error handling file deletion: {str(e)}"
                                print(error_msg)
                                file_deletion_errors.append({
                                    'entry_id': entry_id,
                                    'field_id': field_id,
                                    'error': error_msg
                                })
                                # Continue processing despite the error
                        value = files_map[field_id]

                    # Check if entry detail exists
                    entry_detail = EntryDetails.objects.filter(entry=entry, field_id=field_id).first()

                    if entry_detail:
                        # Update existing entry detail
                        entry_details_to_update[entry_detail.id] = {
                            'value': value,
                            'info': info,
                            'updated_at': timezone.now(),
                        }
                    else:
                        # Create a new entry detail if it doesn't exist
                        entry_details_to_create.append(
                            EntryDetails(entry=entry, field_id=field_id, value=value, info=info)
                        )

                    if local_entry_detail_id:
                        field_id_to_local_id[field_id] = str(local_entry_detail_id)

                print("entry_details_to_create =====", entry_details_to_create)
                print("entry_details_to_update =====", entry_details_to_update)

                if entry_details_to_create:
                    EntryDetails.objects.bulk_create(entry_details_to_create)

                if entry_details_to_update:
                    for detail_id, updates in entry_details_to_update.items():
                        EntryDetails.objects.filter(id=detail_id).update(**updates)

                    # Update existing entry timestamp
                    entry.user=user
                    entry.updated_at = timezone.now()  # Explicitly update the timestamp
                    entry.type = type
                    entry.save()

                EntryUpdateHistory.objects.create(entry=entry, user=user)

                #add submission details

                add_submission_mobile(request, entry, user, 'update')


                # send form notification

                if entry.type == 1: 

                    send_form_notification(entry.id, request)


                # send notification if submission reached 50 or 80 % 

                submission_limit_notification(request)    

                # Fetch created or updated details with field_ids
                created_details_with_ids = EntryDetails.objects.filter(
                    entry=entry
                ).select_related('field').values('id', 'field_id', 'created_at', 'updated_at')

                detail_mapping = {}
                for created_detail in created_details_with_ids:
                    field_id = created_detail['field_id']
                    if field_id in field_id_to_local_id:
                        local_id = field_id_to_local_id[field_id]
                        detail_mapping[local_id] = {
                            'id': created_detail['id'],
                            'created_at': created_detail['created_at'],
                            'updated_at': created_detail['updated_at'],
                        }

                print("Final detail_mapping:", detail_mapping)

                successful_entries.append({
                    str(entry_id): entry.id,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    'detail_mapping': detail_mapping,
                    'note_mapping': note_id_to_local_id  # Include generated note IDs
                })

            except Exception as e:
                failed_entries.append({
                    'entry_id': entry_id,
                    'error': str(e)
                })

        return JsonResponse({
            'message': 'Entries processed',
            'status': 'partial_success' if failed_entries else 'success',
            'successful_entries': successful_entries,
            'failed_entries': failed_entries
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@api_view(['GET','POST'])
def database_sync_view(request):

    if request.method == 'GET':
        # Get the timestamp from the request
        sync_timestamp = request.query_params.get('last_sync_timestamp')
        
        if not sync_timestamp:
            return Response(
                {"error": "sync_timestamp is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Convert timestamp to datetime object
            sync_datetime = parse(sync_timestamp)
        except ValueError:
            return Response(
                {"error": "Invalid timestamp format"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Define table configurations based on their column structure
        table_configs = {
             # 'no_timestamps' : ['capabilities', 'capability_permissions','form_columns',
             #                     'form_permissions', 'roles', 'roles_form_permissions','role_permissions',
             #                     'role_users','user_form_permissions','entry_rules','folder_request_access',
             #                     'folder_roles_capabilities', 'folder_users_capabilities', 'folder_user_access'],
             'no_timestamps' : ['form_columns','role_users'],
             'both_timestamps': [
                'auth_user', 'categories', 'forms', 'form_fields', 
                'entries', 'folders', 'folder_entries','form_certificates' , 'form_notifications', 'entry_notes'
             ]
        }
        
        # Prepared response
        sync_data = {}
        
        # Use the default database connection
        with connection.cursor() as cursor:
            # Process tables with both created_at and updated_at
            for table in table_configs['both_timestamps']:
                # Sync entries, entry notes, flags, details, and update history separately
                if table == 'entries':

                    # Get entries
                    entry_query = """
                    SELECT * FROM entries 
                    WHERE updated_at >= %s 
                    ORDER BY updated_at DESC
                    """
                    cursor.execute(entry_query, [sync_datetime])
                    entries = cursor.fetchall()
                    entry_columns = [col[0] for col in cursor.description]

                    structured_data = []
                    for entry in entries:
                        entry_dict = dict(zip(entry_columns, entry))
                        entry_id = entry_dict['id']

                        # Get entry details
                        cursor.execute("""
                            SELECT id AS server_id,value,created_at,updated_at,entry_id AS entry_server_id,field_id,info  FROM entry_details 
                            WHERE entry_id = %s
                        """, [entry_id])
                        details_columns = [col[0] for col in cursor.description]
                        details = [dict(zip(details_columns, row)) for row in cursor.fetchall()]

                        # Get entry notes
                        cursor.execute("""
                            SELECT id AS server_id,note,created_at,entry_id AS entry_server_id,user_id FROM entry_notes 
                            WHERE entry_id = %s
                        """, [entry_id])
                        notes_columns = [col[0] for col in cursor.description]
                        notes = [dict(zip(notes_columns, row)) for row in cursor.fetchall()]

                        # Get entry flags
                        cursor.execute("""
                            SELECT id AS server_id,created_at,entry_id AS entry_server_id,flagged_by_id,flagged_to_id,
                            flag_text,cleared,cleared_by_id,flagged_reason FROM entry_flags 
                            WHERE entry_id = %s
                        """, [entry_id])
                        flags_columns = [col[0] for col in cursor.description]
                        flags = [dict(zip(flags_columns, row)) for row in cursor.fetchall()]

                        # Get entry update history
                        cursor.execute("""
                            SELECT id AS server_id,updated_at,entry_id AS entry_server_id,user_id FROM entry_update_history
                            WHERE entry_id = %s
                        """, [entry_id])
                        history_columns = [col[0] for col in cursor.description]
                        history = [dict(zip(history_columns, row)) for row in cursor.fetchall()]

                        # Get submission_details
                        cursor.execute("""
                            SELECT id AS server_id,created_at,action_type,entry_id AS entry_server_id,user_id FROM submission_details
                            WHERE entry_id = %s
                        """, [entry_id])
                        submission_details_columns = [col[0] for col in cursor.description]
                        submission_details = [dict(zip(submission_details_columns, row)) for row in cursor.fetchall()]

                        # Structure the data
                        entry_data = {
                            'entries': {
                                'server_id': entry_dict['id'],
                                'created_at': entry_dict['created_at'].isoformat() if entry_dict['created_at'] else None,
                                'updated_at': entry_dict['updated_at'].isoformat() if entry_dict['updated_at'] else None,
                                'form_id': entry_dict['form_id'],
                                'is_approved': entry_dict['is_approved'],
                                'is_trash': entry_dict['is_trash'],
                                'user_id': entry_dict['user_id'],
                                'is_read': entry_dict['is_read'],
                                'is_flagged': entry_dict['is_flagged'],
                                'type': entry_dict['type'],
                                'location': entry_dict['location'],
                                'flagged_at': entry_dict['flagged_at'].isoformat() if entry_dict['flagged_at'] else None,
                                'is_sync' : 1
                            },
                            'entry_details': details,
                            'entry_notes': notes,
                            'entry_flags': flags,
                            'entry_update_history': history,
                            'submission_details': submission_details,
                        }
                        structured_data.append(entry_data)

                    # Fetch deleted records for entries
                    cursor.execute("""
                        SELECT * FROM deleted_records
                        WHERE table_name = 'entries' AND deleted_at >= %s
                    """, [sync_datetime])
                    deleted_columns = [col[0] for col in cursor.description]
                    deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]


                    print("structured_data ===for entries===", structured_data)

                    sync_data['entries'] = {
                        "updated": structured_data or [],
                        "deleted": deleted_records or []
                    }

                elif table == 'form_certificates':
                    try:
                        # Fetch updated forms
                        form_query = """
                        SELECT * FROM form_certificates
                        WHERE updated_at >= %s
                        """
                        updated_form_certificates = _execute_query(cursor, form_query, [sync_datetime])

                        # Build form_id list
                        form_certificates_ids = [form_certificates['id'] for form_certificates in updated_form_certificates]

                        # Fetch form_certificates
                        structured_data = []
                        if form_certificates_ids:
                            cursor.execute("""
                                SELECT * FROM certificate_rules
                                WHERE certificate_id IN %s
                            """, [tuple(form_certificates_ids)])
                            rules_columns = [col[0] for col in cursor.description]
                            certificate_rules = [dict(zip(rules_columns, row)) for row in cursor.fetchall()]
                        else:
                            certificate_rules = []


                        # Query for deleted forms
                        cursor.execute("""
                            SELECT * FROM deleted_records
                            WHERE table_name = %s AND deleted_at >= %s
                        """, [table, sync_datetime])
                        deleted_columns = [col[0] for col in cursor.description]
                        deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]

                        # Structure the data
                        form_certificates_data = {
                            'form_certificates': updated_form_certificates,
                            'certificate_rules': certificate_rules,
                        }
                        structured_data.append(form_certificates_data)

                        # Final sync data structure for forms
                        sync_data['form_certificates'] = {
                            "updated": structured_data or [],
                            "deleted": deleted_records or []
                        }
                    except Exception as e:
                        print(f"Error syncing table {table}: {str(e)}")

                elif table == 'form_notifications':
                    try:
                        # Fetch updated forms
                        form_query = """
                        SELECT * FROM form_notifications
                        WHERE created_at >= %s
                        """
                        updated_form_notifications = _execute_query(cursor, form_query, [sync_datetime])

                        # Build form_id list
                        form_notifications_ids = [form_notifications['id'] for form_notifications in updated_form_notifications]


                        # Query for deleted forms
                        cursor.execute("""
                            SELECT * FROM deleted_records
                            WHERE table_name = %s AND deleted_at >= %s
                        """, [table, sync_datetime])
                        deleted_columns = [col[0] for col in cursor.description]
                        deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]


                        # Escape reserved keyword columns (like `values`)
                        updated_records = [escape_reserved_keywords(row) for row in updated_form_notifications]

                        sync_data[table] = {
                            "updated": updated_records or [],
                            "deleted": deleted_records or []
                        }
                    except Exception as e:
                        print(f"Error syncing table {table}: {str(e)}")

                elif table == 'entry_notes':
                    try:
                        # Fetch updated forms
                        form_query = """
                        SELECT id AS server_id,note,created_at,entry_id AS entry_server_id,user_id FROM entry_notes
                        WHERE created_at >= %s
                        """
                        updated_entry_notes = _execute_query(cursor, form_query, [sync_datetime])

                        # Build form_id list
                        entry_notes_ids = [entry_notes['server_id'] for entry_notes in updated_entry_notes]

                        # Query for deleted forms
                        cursor.execute("""
                            SELECT * FROM deleted_records
                            WHERE table_name = %s AND deleted_at >= %s
                        """, [table, sync_datetime])
                        deleted_columns = [col[0] for col in cursor.description]
                        deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]

                        # Escape reserved keyword columns (like `values`)
                        updated_records = [escape_reserved_keywords(row) for row in updated_entry_notes]

                        sync_data[table] = {
                            "updated": updated_records or [],
                            "deleted": deleted_records or []
                        }
                    except Exception as e:
                        print(f"Error syncing table {table}: {str(e)}")


                else:
                    try:
                        # Query for updated records
                        query = f"""
                        SELECT * FROM {table}
                        WHERE updated_at > %s
                        """
                        updated_records = _execute_query(cursor, query, [sync_datetime])
                        # Rename 'id' to 'server_id' for the 'folder_entries' table
                        if table == 'folder_entries':
                            key_mapping = {
                                'id': 'server_id',
                                'entry_id': 'entry_server_id'
                            }
                            updated_records = [
                                {key_mapping.get(key, key): value for key, value in record.items()}
                                for record in updated_records
                            ]                        
                        # Query for deleted records
                        deleted_query = """
                        SELECT * FROM deleted_records
                        WHERE table_name = %s AND deleted_at >= %s
                        """
                        cursor.execute(deleted_query, [table, sync_datetime])
                        deleted_columns = [col[0] for col in cursor.description]
                         # Rename 'id' to 'server_id' for the 'folder_entries' table
                        if table == 'folder_entries':
                            columns = ['server_id' if col == 'id' else col for col in deleted_columns]
                        deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]

                        # Escape reserved keyword columns (like `values`)
                        updated_records = [escape_reserved_keywords(row) for row in updated_records]

                        sync_data[table] = {
                            "updated": updated_records or [],
                            "deleted": deleted_records or []
                        }
                            
                    except Exception as e:
                        print(f"Error syncing table {table}: {str(e)}")
        

            for table in table_configs['no_timestamps']:
                try:
                    # Query for updated records
                    query = f"""
                    SELECT * FROM {table} ORDER BY id ASC
                    """                       
                    cursor.execute(query)

                    columns = [col[0] for col in cursor.description]


                    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    
                    # Query for deleted records
                    deleted_query = """
                    SELECT * FROM deleted_records
                    WHERE table_name = %s AND deleted_at >= %s
                    """
                    cursor.execute(deleted_query, [table, sync_datetime])
                    deleted_columns = [col[0] for col in cursor.description]
                    
                    
                    deleted_records = [dict(zip(deleted_columns, row)) for row in cursor.fetchall()]

                    data = [escape_reserved_keywords(row) for row in data]

                    sync_data[table] = {
                        "updated": data or [],
                        "deleted": deleted_records or []
                    }
                        
                except Exception as e:
                    print(f"Error syncing table {table}: {str(e)}")
        
        # print("sync_data ====", sync_data)
        print("get sync timestamp ====", datetime.utcnow().isoformat() + "Z" )
        return Response({
            "data": sync_data,
            "sync_timestamp": datetime.utcnow().isoformat() + "Z" 
        }, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        data = request.data.get('data')

        if not data:
            return JsonResponse({"error": "data is required."}, status=400)

        try:
            id_mapping = {}  # Dictionary to store local ID to server ID mapping
            for table_name, operations in data.items():
                # Handle 'auth_user' table updates
                if table_name == 'auth_user':
                    for record in operations.get('updated', []):
                        if record:
                            print("Updating auth_user record:", record)
                            try:
                                obj = User.objects.filter(id=record['id']).first()
                                if obj:
                                    for key, value in record.items():
                                        setattr(obj, key, value)
                                    obj.save()
                                    print(f"Updated auth_user record with id {obj.id}")
                                else:
                                    print(f"No auth_user record found with id {record['id']}")
                            except Exception as e:
                                print(f"Error updating auth_user: {str(e)}")
                        else:
                            print("Nothing to update in auth_user")

                # Handle 'entries' table updates
                elif table_name == 'entries':
                    for record in operations.get('updated', []):
                        if record:
                            print("Updating entries record:", record)
                            try:
                                obj = Entries.objects.filter(id=record['server_id']).first()
                                if obj:
                                    for key, value in record.items():
                                        # Skip updating 'server_id' or 'id' fields
                                        if key not in ['id', 'server_id']:
                                            setattr(obj, key, value)
                                    obj.save()
                                    print(f"Updated entry with id {obj.id}")
                                else:
                                    print(f"No entry found with id {record['server_id']}")
                            except Exception as e:
                                print(f"Error updating entry: {str(e)}")
                        else:
                            print("Nothing to update in entries")

                    for record in operations.get('deleted', []):
                        if record:
                            print("Deleting entries record:", record)
                            try:
                                obj = Entries.objects.filter(id=record['record_id']).first()
                                if obj:
                                    current_db = connections.databases['default']['NAME']
                                    print("current_db ===", current_db)
                                    dir_path = None
                                    try:
                                        # Set the base directory path
                                        dir_path = settings.MEDIA_ROOT + '/form/'
                                        print("dir_path ===", dir_path)
                                        
                                        # Adjust the directory path based on current database
                                        if current_db != 'enggforms':
                                            dir_path = dir_path + '/' + current_db + '/'

                                        field_types = ['fileupload', 'signature']

                                        # Process EntryDetails records related to the entries
                                        print("obj =====", obj.id)
                                        entry_details = EntryDetails.objects.filter(entry_id=obj.id, field__type__in=field_types)
                                        print("entry_details ===", entry_details)
                                        if entry_details:
                                            for data in entry_details:
                                                try:
                                                    # Remove files associated with the entry
                                                    if data.value and os.path.exists(dir_path + data.value):
                                                        print(" ==========file ===", dir_path + data.value)
                                                        os.remove(dir_path + data.value)
                                                        print(" ==========file REMOVED ===", dir_path + data.value)
                                                    
                                                    if data.info:
                                                        extra_files = json.loads(data.info)
                                                        for file in extra_files:
                                                            if os.path.exists(dir_path + file):
                                                                os.remove(dir_path + file)
                                                except Exception as e:
                                                    print(f"Error removing files for entry {obj.id}: {str(e)}")
                                        
                                        # Delete the record
                                        Deletion.objects.create(table_name='entries', record_id=obj.id)
                                        obj.delete()
                                        print(f"Record with id {record['record_id']} from table {table_name} deleted successfully.")
                                    except Exception as e:
                                        print(f"An error occurred while processing the directory or deleting files: {str(e)}")
                                else:
                                    print(f"Record with id {record['record_id']} not found in {table_name}.")
                            except Exception as e:
                                print(f"Error deleting entry: {str(e)}")
                        else:
                            print("Nothing to delete in entries")
                
                # Handle 'entry_notes' table updates
                elif table_name == 'entry_notes':
                    for record in operations.get('updated', []):
                        if record:
                            print("Updating entries record:", record)
                            server_id = record.get('server_id')
                            if server_id:
                                try:
                                    # Check if object already exists
                                    EntryNotes.objects.get(id=server_id)
                                    print(f"EntryNote with id {server_id} already exists — skipping update.")
                                    continue  # Skip updates
                                except EntryNotes.DoesNotExist:
                                    EntryNotes.objects.create(entry=record.get('entry_server_id'), user=record.get('user_id'), note=record.get('note'))
                        else:
                            EntryNotes.objects.create(entry=record.get('entry_server_id'), user=record.get('user_id'), note=record.get('note'))

                    for record in operations.get('deleted', []):
                        if record:
                            print("Deleting entries record:", record)
                            try:
                                obj = EntryNotes.objects.filter(id=record['record_id']).first()
                                if obj:
                                    Deletion.objects.create(table_name='entry_notes', record_id=obj.id)
                                    obj.delete()
                                    print(f"Record with id {record['record_id']} from table {table_name} deleted successfully.")
                                else:
                                    print(f"Record with id {record['record_id']} not found in {table_name}.")
                            except Exception as e:
                                print(f"Error deleting entry: {str(e)}")
                        else:
                            print("Nothing to delete in entries")

                # Handle other tables
                else:
                    id_mapping['folder_entries'] = {}
                    for record in operations.get('updated', []):
                        print(f"Updating {table_name} record:", record)
                        try:

                            print("record========", record)
                            entry_id = record.get('entry_server_id')
                            local_id = record.get('id')  # Local database ID

                            # Step 1: Delete previous folder entries related to this entry
                            if entry_id:
                                # Fetch the folder IDs related to this entry before deletion
                                folder_ids = FolderEntries.objects.filter(entry_id=entry_id).values_list('id', flat=True)

                                # Insert each deleted folder ID into the Deletion table
                                for folder_id in folder_ids:
                                    Deletion.objects.create(table_name='folder_entries', record_id=folder_id)
                                    print(f"Inserted folder_id {folder_id} into Deletion table.")

                                # Delete the folder entries
                                deleted_count, _ = FolderEntries.objects.filter(entry_id=entry_id).delete()
                                print(f"Deleted {deleted_count} folder entries related to entry_id: {entry_id}")
                                obj = FolderEntries.objects.create(entry_id=entry_id, folder_id=record.get('folder_id'))
                                print(f"Folder entry created for {entry_id}")
                                # Store mapping of local ID to created ID
                                id_mapping['folder_entries'][local_id] = obj.id  # Example: {'folder_entries': {12: 5194}}
                            else:
                                print("Nothing to update in folder_entries")
                        except Exception as e:
                            print(f"Error updating folder_entries: {str(e)}")
            
            print("post sync timestamp ====", datetime.utcnow().isoformat() + "Z" )
            return JsonResponse({
                "message": "Sync online database with local processed successfully.",
                "sync_timestamp": datetime.utcnow().isoformat() + "Z",
                "id_mapping": id_mapping  # Return mapping for offline DB update
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)


def _execute_query(cursor, query, params):
    """
    Execute a query and process the results
    
    Args:
        cursor: Database cursor
        query: SQL query string
        params: Query parameters
    
    Returns:
        List of processed records
    """
    cursor.execute(query, params)
    columns = [col[0] for col in cursor.description]
    records = []
    
    for row in cursor.fetchall():
        row_dict = dict(zip(columns, row))
        
        # Convert datetime to ISO format
        for key, value in row_dict.items():
            if isinstance(value, datetime):
                row_dict[key] = value.isoformat()
        
        records.append(row_dict)
    
    return records



from settings_app.models import SettingsModel
from django.core.mail import EmailMultiAlternatives
import json

@api_view(['POST'])
@authentication_classes([])  # Disable authentication
@permission_classes([])  # Disable permission checks
def qr_email_thread(request):
    main_db = settings.MAIN_DB
    set_db_connection(main_db)

    try:
        # Fetch email settings from the database
        email_model = SettingsModel.objects.using(main_db).get(name='email_smtp')
        email_settings = json.loads(email_model.value)

        # Set email configurations from settings
        settings.EMAIL_HOST = email_settings["EMAIL_HOST"]
        settings.EMAIL_PORT = email_settings["EMAIL_PORT"]
        settings.EMAIL_HOST_USER = email_settings["EMAIL_HOST_USER"]
        settings.EMAIL_HOST_PASSWORD = email_settings["EMAIL_HOST_PASSWORD"]
        outgoing_email = email_settings["OUTGOING_EMAIL_RECEIVE"] if email_settings["OUTGOING_EMAIL_RECEIVE"] else ''
        from_email = email_settings['FROM_EMAIL'] if email_settings['FROM_EMAIL'] else email_settings["EMAIL_HOST_USER"]
        from_email = f"Engineering Forms <{from_email}>"

        # Prepare email content
        subject = f"Hi parveen"
        body = f"Hi parveen,\n\nYou have a new notification.\n\nBest regards,\nEngineering Forms"

        # Send the email
        email = EmailMultiAlternatives(subject=subject, body=body, to=["parveen6286@gmail.com"], from_email=from_email)
        email.send()

        print('qr-email sent')

        return Response({"message": "Email sent successfully"}, status=status.HTTP_200_OK)

    except Exception as e:
        print("qr-email error", str(e))
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# online single entry download
@api_view(["POST"])
def online_entry_download(request):
    if request.user.is_authenticated:
        entry_id = request.data.get('entry_id')

        with connection.cursor() as cursor:
            # Get entries
            entry_query = """
            SELECT * FROM entries 
            WHERE id = %s 
            """
            cursor.execute(entry_query, [entry_id])
            entries = cursor.fetchall()
            entry_columns = [col[0] for col in cursor.description]

            structured_data = []
            for entry in entries:
                entry_dict = dict(zip(entry_columns, entry))
                entry_id = entry_dict['id']

                # Get entry details
                cursor.execute("""
                    SELECT id AS server_id,value,created_at,updated_at,entry_id AS entry_server_id,field_id,info  FROM entry_details 
                    WHERE entry_id = %s
                """, [entry_id])
                details_columns = [col[0] for col in cursor.description]
                details = [dict(zip(details_columns, row)) for row in cursor.fetchall()]

                # Get entry notes
                cursor.execute("""
                    SELECT id AS server_id,note,created_at,entry_id AS entry_server_id,user_id FROM entry_notes 
                    WHERE entry_id = %s
                """, [entry_id])
                notes_columns = [col[0] for col in cursor.description]
                notes = [dict(zip(notes_columns, row)) for row in cursor.fetchall()]

                # Get entry flags
                cursor.execute("""
                    SELECT id AS server_id,created_at,entry_id AS entry_server_id,flagged_by_id,flagged_to_id,
                    flag_text,cleared,cleared_by_id,flagged_reason FROM entry_flags 
                    WHERE entry_id = %s
                """, [entry_id])
                flags_columns = [col[0] for col in cursor.description]
                flags = [dict(zip(flags_columns, row)) for row in cursor.fetchall()]
                
                # Get entry update history
                cursor.execute("""
                    SELECT id AS server_id,updated_at,entry_id AS entry_server_id,user_id FROM entry_update_history
                    WHERE entry_id = %s
                """, [entry_id])
                history_columns = [col[0] for col in cursor.description]
                history = [dict(zip(history_columns, row)) for row in cursor.fetchall()]
                
                # Get submission_details
                cursor.execute("""
                    SELECT id AS server_id,created_at,action_type,entry_id AS entry_server_id,user_id FROM submission_details
                    WHERE entry_id = %s
                """, [entry_id])
                submission_details_columns = [col[0] for col in cursor.description]
                submission_details = [dict(zip(submission_details_columns, row)) for row in cursor.fetchall()]

                # Get folder_details
                cursor.execute("""
                    SELECT id AS server_id,created_at,updated_at,entry_id AS entry_server_id,folder_id FROM folder_entries
                    WHERE entry_id = %s
                """, [entry_id])
                folder_entries_columns = [col[0] for col in cursor.description]
                folder_entries = [dict(zip(folder_entries_columns, row)) for row in cursor.fetchall()]

                # Structure the data
                entry_data = {
                    'entries': {
                        'server_id': entry_dict['id'],
                        'created_at': entry_dict['created_at'].isoformat() if entry_dict['created_at'] else None,
                        'updated_at': entry_dict['updated_at'].isoformat() if entry_dict['updated_at'] else None,
                        'form_id': entry_dict['form_id'],
                        'is_approved': entry_dict['is_approved'],
                        'is_trash': entry_dict['is_trash'],
                        'user_id': entry_dict['user_id'],
                        'is_read': entry_dict['is_read'],
                        'is_flagged': entry_dict['is_flagged'],
                        'type': entry_dict['type'],
                        'location': entry_dict['location'],
                        'flagged_at': entry_dict['flagged_at'].isoformat() if entry_dict['flagged_at'] else None,
                        'is_sync' : 1
                    },
                    'entry_details': details,
                    'entry_notes': notes,
                    'entry_flags': flags,
                    'entry_update_history': history,
                    'submission_details': submission_details,
                    'folder_entries': folder_entries,
                }
                structured_data.append(entry_data)

            return Response({
                'status': True,
                'message': 'Data fetched successfully',
                'data': structured_data
            })

    else:
        return Response({"message": "User is not authenticated"}, status=401)



@api_view(["GET", "POST"])
def address_and_equipment_file(request):
    try:
        # Fetch settings
        sett = SettingsModel.objects.get(name="form_settings")
        sett = json.loads(sett.value)

        # Retrieve stored file names (default to empty strings if missing)
        stored_address_file = sett.get('address_file', '').replace(".csv", "")
        stored_equipment_file = sett.get('equipment_file', '').replace(".csv", "")

        if request.method == 'GET':
            return JsonResponse({
                "address_file": stored_address_file,
                "address_option": autocomplete_options(sett.get('address_file', '')) if stored_address_file else {},
                "equipment_file": stored_equipment_file,
                "equipment_option": autocomplete_options(sett.get('equipment_file', '')) if stored_equipment_file else {},
            })

        elif request.method == 'POST':
            # Get filenames from request
            address_file_name = request.data.get('address_file')
            equipment_file_name = request.data.get('equipment_file')

            # Determine if files have changed and fetch new options if needed
            address_option = (
                autocomplete_options(sett.get('address_file', '')) if address_file_name != stored_address_file 
                else {"message": "No Update Available"}
            )
            equipment_option = (
                autocomplete_options(sett.get('equipment_file', '')) if equipment_file_name != stored_equipment_file
                else {"message": "No Update Available"}
            )

            return JsonResponse({
                "address_file": stored_address_file,
                "address_option": address_option,
                "equipment_file": stored_equipment_file,
                "equipment_option": equipment_option,
            })

    except SettingsModel.DoesNotExist:
        return JsonResponse({"error": "Settings not found"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format in settings"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def autocomplete_options(filename):
    options = {}

    try:
        if filename:
            file_path = os.path.join(settings.MEDIA_ROOT, 'form', filename)

            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file, delimiter=',')
                headers = next(reader)  # Read first row as headers

                # Clean headers (remove empty ones)
                headers = [h.strip() for h in headers if h.strip()]
                
                # Initialize dictionary
                options = {col: [] for col in headers}

                # Read and store values
                for row in reader:
                    for i, col in enumerate(row[:len(headers)]):  # Prevent index errors
                        options[headers[i]].append(col.strip())

    
    except Exception as e:
        print(str(e))
    
    return options


@api_view(["POST"])
def update_active_columns(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            columns = data.get("columns", [])  # List of column IDs
            form_id = data.get("form_id")
            user_id = data.get("user_id")

            if not form_id or not user_id or not isinstance(columns, list):
                return JsonResponse({"status": False, "message": "Invalid data"}, status=400)

            # Fetch form and user
            try:
                form = Form.objects.get(id=form_id)
                user = User.objects.get(id=user_id)
            except (Form.DoesNotExist, User.DoesNotExist):
                return JsonResponse({"status": False, "message": "Form or User not found"}, status=404)

            # Convert list to JSON string for storage
            columns_json = json.dumps(columns)

            # Check if an entry exists
            obj = form_columns.objects.filter(form=form, user=user).first()
            
            if obj:
                obj.columns = columns_json  # Update existing record
                message = "Active columns updated"
                created = False
            else:
                obj = form_columns(form=form, user=user, columns=columns_json)  # Create new record
                message = "Active columns created"
                created = True
            
            obj.save()  # Save the changes

            return JsonResponse({"status": True, "message": message, "created": created,"sync_timestamp": datetime.utcnow().isoformat() + "Z",})
        
        except json.JSONDecodeError:
            return JsonResponse({"status": False, "message": "Invalid JSON"}, status=400)
        
    return JsonResponse({"status": False, "message": "Only POST method allowed"}, status=405)
