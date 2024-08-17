from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login
from .forms import SignUpForm, UploadForm
from .models import SchemaInfo
from django.views.decorators.csrf import csrf_exempt
import json
import os
import google
from google.cloud import bigquery
import tempfile
import logging
from .utils import gemini_llm, gemini_llm_graph_suggestions, get_schema_details, execute_bigquery, is_sql_query, generate_plotly_graphs
from django.db import transaction, IntegrityError
import google.api_core.exceptions as google_exceptions

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def landing_page(request):
    return render(request, 'core/landing.html')

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('chat_page')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})

@csrf_exempt
def chat_message(request):
    if request.method == 'POST':
        try:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            message = data.get('message', '')
            max_retries = 5
            retry_count = 0

            if message:
                schema_details = get_schema_details(request.user)
                error_message = None

                while retry_count < max_retries:
                    gemini_response = gemini_llm(message, schema_details, error_message)
                    if isinstance(gemini_response, dict) and "error" in gemini_response:
                        logger.error(f'Gemini LLM error: {gemini_response["error"]}')
                        return JsonResponse({'status': 'error', 'message': 'An error occurred while processing your request.'}, status=500)

                    print(f'LLM Response: {gemini_response}')

                    if is_sql_query(gemini_response):
                        credentials_path = request.session.get('google_credentials_path')
                        if not credentials_path or not os.path.exists(credentials_path):
                            logger.error('Credentials not found. Please reconnect the database.')
                            return JsonResponse({'status': 'error', 'message': 'Credentials not found. Please reconnect the database.'}, status=500)

                        try:
                            logger.info(f'Executing query: {gemini_response}')
                            bigquery_data = execute_bigquery(gemini_response, credentials_path)
                            print('BigQuery Data:', bigquery_data)

                            graph_suggestions = gemini_llm_graph_suggestions(message, schema_details)
                            if isinstance(graph_suggestions, dict) and "error" in graph_suggestions:
                                logger.error(f'Gemini LLM error: {graph_suggestions["error"]}')
                                return JsonResponse({'status': 'error', 'message': 'An error occurred while getting graph suggestions.'}, status=500)

                            graphs_json = generate_plotly_graphs(bigquery_data, graph_suggestions)
                            
                            response_data = {
                                'status': 'success',
                                'message': 'Query executed successfully',
                                'bigquery_data': bigquery_data,
                                'graphs_json': graphs_json
                            }
                            return JsonResponse(response_data)
                        except google_exceptions.GoogleAPIError as e:
                            logger.error(f'Google API error: {e}')
                            error_message = str(e)
                            retry_count += 1
                        except google_exceptions.BadRequest as e:
                            logger.error(f'SQL Syntax error: {e.message}')
                            error_message = e.message
                            retry_count += 1
                        except Exception as e:
                            logger.error(f'Unexpected error during query execution: {e}')
                            error_message = str(e)
                            retry_count += 1
                    else:
                        response_data = {
                            'status': 'success',
                            'message': gemini_response,
                            'bigquery_data': None,
                            'graphs_json': None
                        }
                        return JsonResponse(response_data)

                return JsonResponse({'status': 'error', 'message': 'Failed to execute the query after several attempts.'}, status=500)
            else:
                logger.error('Message is empty')
                return JsonResponse({'status': 'fail', 'message': 'Message is empty'}, status=400)
        except json.JSONDecodeError:
            logger.error('Invalid JSON received')
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            return JsonResponse({'status': 'error', 'message': 'An error occurred while processing your request.'}, status=500)
    return JsonResponse({'status': 'fail', 'message': 'Invalid request method'}, status=400)



def chat_page(request):
    success = request.GET.get('success', 'false') == 'true'
    schema_info = SchemaInfo.objects.filter(user=request.user) if success else []

    schema_details = {}
    for schema in schema_info:
        table_name = schema.table_name
        if table_name not in schema_details:
            schema_details[table_name] = []
        schema_details[table_name].append({
            "field_name": schema.field_name,
            "field_type": schema.field_type
        })

    schema_details_json = json.dumps(schema_details)
    return render(request, 'core/chat.html', {
        'success': success,
        'schema_info': schema_info,
        'schema_details_json': schema_details_json
    })

def db_connect(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                passkey_file = request.FILES['passkey_file']
                project_id = form.cleaned_data['project_id']
                dataset_id = form.cleaned_data['dataset_id']

                with tempfile.NamedTemporaryFile(delete=False) as temp_passkey_file:
                    for chunk in passkey_file.chunks():
                        temp_passkey_file.write(chunk)
                    temp_passkey_path = temp_passkey_file.name

                request.session['google_credentials_path'] = temp_passkey_path

                client = bigquery.Client.from_service_account_json(temp_passkey_path)
                dataset_ref = f"{project_id}.{dataset_id}"
                tables = client.list_tables(dataset_ref)
               
                with transaction.atomic():
                    for table in tables:
                        table_ref = f"{dataset_ref}.{table.table_id}"
                        table = client.get_table(table_ref)

                        for schema_field in table.schema:
                            try:
                                logging.info(f"Saving schema: {table_ref} - {schema_field.name} - {schema_field.field_type}")
                                SchemaInfo.objects.create(
                                    user=request.user,
                                    table_name=table_ref,
                                    field_name=schema_field.name,
                                    field_type=schema_field.field_type
                                )
                            except IntegrityError as ie:
                                logging.error(f"IntegrityError occurred: {ie}")
                                raise

                return redirect('/chat/?success=true')
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                return render(request, 'core/db.html', {'form': form, 'error': str(e)})
    else:
        form = UploadForm()
    return render(request, 'core/db.html', {'form': form})
