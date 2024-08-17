import google.generativeai as genai
from django.conf import settings
from google.cloud import bigquery
import re
import google.api_core.exceptions as google_exceptions
import plotly.express as px
import pandas as pd
import json
import plotly
from django.views.decorators.csrf import csrf_exempt
import json
import google
def initialize_llm():
    GOOGLE_API_KEY = settings.GOOGLE_API_KEY
    genai.configure(api_key=GOOGLE_API_KEY)

def get_schema_details(user):
    from core.models import SchemaInfo  # Avoid circular imports
    schema_info = SchemaInfo.objects.filter(user=user)
    schema_details = {}
    for schema in schema_info:
        table_name = schema.table_name
        if table_name not in schema_details:
            schema_details[table_name] = []
        schema_details[table_name].append({
            "field_name": schema.field_name,
            "field_type": schema.field_type
        })
    return schema_details

def gemini_llm(content, schema_details, error_message=None):
    initialize_llm()
    combined_content = f"Schema Details: {schema_details}\nUser Message: {content}"
    if error_message:
        combined_content += f"\nError: {error_message}\nPlease generate a correct SQL query based on the error and schema details."
    else:
        combined_content += "\nPlease generate a SQL query based on the schema details."
    
    model = genai.GenerativeModel('gemini-1.0-pro')
    response = model.generate_content(combined_content)

    if not response or not hasattr(response, 'text') or not response.text:
        return {"error": "The response from Gemini was blocked or invalid. Please try again."}

    return response.text
def gemini_llm_graph_suggestions(content, schema_details):
    initialize_llm()
    combined_content = f"Schema Details: {schema_details}\nUser Message: {content}\nSuggest the best 4 types of graphs for the given data schema."
    model = genai.GenerativeModel('gemini-1.0-pro')
    response = model.generate_content(combined_content)

    if not response or not hasattr(response, 'text') or not response.text:
        return {"error": "The response from Gemini was blocked or invalid. Please try again."}

    graph_suggestions = response.text.split('\n')[:4]  
    # Assuming response contains graph descriptions as separate lines
    print(graph_suggestions)
    return graph_suggestions

def execute_bigquery(query, credentials_path):
    query = query.strip('```sql').strip('```').strip()
    if not query or query.strip() == '':
        raise ValueError("The query is empty or invalid.")
    
    client = bigquery.Client.from_service_account_json(credentials_path)
    
    try:
        query_job = client.query(query)
        results = query_job.result()
    except google.api_core.exceptions.GoogleAPIError as e:
        raise e
    except google.api_core.exceptions.BadRequest as e:
        raise e
    except Exception as e:
        raise e

    result_list = [dict(row) for row in results]
    return result_list

def is_sql_query(response):
    sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
    return any(keyword in response.upper() for keyword in sql_keywords)

def generate_plotly_graphs(data, graph_types):
    df = pd.DataFrame(data)
    graphs = {}


import plotly.express as px
import pandas as pd
import json
import plotly

def generate_plotly_graphs(data, graph_suggestions):
    df = pd.DataFrame(data)
    graphs = {}

    for suggestion in graph_suggestions:
        suggestion_lower = suggestion.lower()
        
        if "bar" in suggestion_lower:
            fig = px.bar(df, x=df.columns[0], y=df.columns[1], title=suggestion)
            graph_type = "bar"
        elif "scatter" in suggestion_lower:
            fig = px.scatter(df, x=df.columns[0], y=df.columns[1], color=df.columns[2] if len(df.columns) > 2 else None, title=suggestion)
            graph_type = "scatter"
        elif "heat map" in suggestion_lower or "heatmap" in suggestion_lower:
            fig = px.density_heatmap(df, x=df.columns[0], y=df.columns[1], z=df.columns[2] if len(df.columns) > 2 else None, title=suggestion)
            graph_type = "heatmap"
        elif "line" in suggestion_lower:
            fig = px.line(df, x=df.columns[0], y=df.columns[1], color=df.columns[2] if len(df.columns) > 2 else None, title=suggestion)
            graph_type = "line"
        elif "histogram" in suggestion_lower:
            fig = px.histogram(df, x=df.columns[0], title=suggestion)
            graph_type = "histogram"
        elif "box" in suggestion_lower:
            fig = px.box(df, x=df.columns[0], y=df.columns[1], title=suggestion)
            graph_type = "box"
        elif "pie" in suggestion_lower:
            fig = px.pie(df, names=df.columns[0], values=df.columns[1], title=suggestion)
            graph_type = "pie"
        elif "violin" in suggestion_lower:
            fig = px.violin(df, x=df.columns[0], y=df.columns[1], title=suggestion)
            graph_type = "violin"
        else:
            continue  # Skip unknown graph types

        fig.update_layout(
            title={
                'text': suggestion,
                'y':0.9,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title=df.columns[0],
            yaxis_title=df.columns[1],
            margin=dict(l=40, r=40, t=40, b=40),
            paper_bgcolor="LightSteelBlue",
        )
        fig.update_traces(marker_color='rgb(55, 83, 109)', marker_line_color='rgb(8, 48, 107)',
                          marker_line_width=1.5, opacity=0.6)

        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        graphs[graph_type] = graph_json
    
    return graphs


