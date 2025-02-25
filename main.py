from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Dict, Any
import logging
import json
import io
import base64
import pandas as pd
import numpy as np
from elasticsearch import Elasticsearch, helpers
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database setup
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String)
    email = Column(String)
    phone = Column(String)
    gender = Column(String)

# Create database tables
Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Elasticsearch connection
def connect_to_elasticsearch():
    try:
        client = Elasticsearch(
            "https://34f7228b4caf49b2b71904c41aa4f2a9.us-central1.gcp.cloud.es.io:443",
            api_key="bnlUSjg1UUJUcFBJaUlQVG1tX2g6LURsZHc5MTRTaXVpSW41bWZ0MmNjdw==",
        )
        if client.ping():
            return client
    except Exception as e:
        logger.error(f"Elasticsearch connection error: {e}")
    return None

# Create Elasticsearch index
def create_index(es_client, index_name):
    if not es_client.indices.exists(index=index_name):
        try:
            es_client.indices.create(index=index_name)
            logger.info(f"Index '{index_name}' created successfully.")
        except Exception as e:
            logger.error(f"Error creating index '{index_name}': {e}")
    else:
        logger.info(f"Index '{index_name}' already exists.")

# Index student data from JSON file
def index_student_data(es_client, index_name):
    try:
        # Log the current working directory
        logger.info(f"Current working directory: {os.getcwd()}")

        if not os.path.exists("students1.json"):
            logger.error("Error: students1.json file not found!")
            return  # Exit the function if file is missing

        with open("students1.json", "r") as file:
            students = json.load(file)

        actions = [
            {
                "_index": index_name,
                "_source": student
            }
            for student in students
        ]
        helpers.bulk(es_client, actions)
        logger.info("Student data indexed successfully.")
    except Exception as e:
        logger.error(f"Error indexing student data: {e}")

# Search data from Elasticsearch
def search_data(es_client, index_name, size=200):
    try:
        res = es_client.search(index=index_name, body={"query": {"match_all": {}}}, size=size)
        return res['hits']['hits']
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# Convert search results to DataFrame
def results_to_dataframe(search_results):
    data = [hit['_source'] for hit in search_results]
    return pd.DataFrame(data)

# Convert Matplotlib figure to HTML image tag
def plot_to_html(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    buf.close()
    plt.close(fig)
    return f'<img src="data:image/png;base64,{img_str}" style="width:100%; height:auto;">'

# Create visualization
# (Previous code remains the same until the create_visualization function)

def create_visualization(df: pd.DataFrame, x_axis: str, y_axis: str, graph_type: str, hue: str = None, title: str = None) -> str:
    plt.figure(figsize=(12, 6))
    plt.clf()

    try:
        if graph_type == 'bar':
            sns.barplot(data=df, x=x_axis, y=y_axis, hue=hue)
            plt.xticks(rotation=45, ha='right')

        elif graph_type == 'line':
            sns.lineplot(data=df, x=x_axis, y=y_axis, hue=hue, marker="o")
            plt.xticks(rotation=45, ha='right')

        elif graph_type == 'scatter':
            sns.scatterplot(data=df, x=x_axis, y=y_axis, hue=hue)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45, ha='right')
            plt.grid(True, which='minor', linestyle=':', alpha=0.4)
            plt.minorticks_on()

        elif graph_type == 'pie':
            if x_axis:
                value_counts = df[x_axis].value_counts()
                plt.pie(value_counts, labels=value_counts.index, autopct='%1.1f%%')
                plt.axis('equal')

        # Add a title to the graph
        if title:
            plt.title(title, fontsize=16, pad=20)
        else:
            plt.title(f"{graph_type.capitalize()} Plot: {x_axis} vs {y_axis}", fontsize=16, pad=20)

        plt.tight_layout()
        return plot_to_html(plt.gcf())

    except Exception as e:
        logger.error(f"Visualization error: {e}")
        return f"<p>Error creating visualization: {str(e)}</p>"



# Startup event to index data into Elasticsearch
@app.on_event("startup")
async def startup_event():
    es_client = connect_to_elasticsearch()
    if es_client:
        index_name = "student1-index"
        create_index(es_client, index_name)
        index_student_data(es_client, index_name)

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "message": request.query_params.get("message", "")}
    )

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "message": request.query_params.get("message", "")})

@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...), email: str = Form(...), phone: str = Form(...), gender: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user:
        return RedirectResponse(url="/signup?message=Username+already+exists.+Try+another+one.", status_code=303)
    new_user = User(username=username, password=password, email=email, phone=phone, gender=gender)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/?message=Successfully+signed+up!+Please+log+in.", status_code=303)

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.password == password).first()
    if user:
        return templates.TemplateResponse("welcome.html", {"request": request, "username": username, "website_name": "MyWebsite"})
    return RedirectResponse(url="/?message=Incorrect+username+or+password.+Please+try+again.", status_code=303)

@app.get("/elasticsearch", response_class=HTMLResponse)
async def elasticsearch_page(request: Request):
    es_client = connect_to_elasticsearch()
    if not es_client:
        return HTMLResponse(content="<h1>Could not connect to Elasticsearch.</h1>", status_code=500)

    search_results = search_data(es_client, 'student-index')
    df = results_to_dataframe(search_results)

    return templates.TemplateResponse("elasticsearch.html", {
        "request": request,
        "data": df.to_dict(orient="records")
    })

@app.post("/update_table")
async def update_table(request: Request):
    try:
        data = await request.json()
        filter_type = data.get('filterType')
        filter_value = data.get('filterValue')
        month = data.get('month')
        subject = data.get('subject')

        es_client = connect_to_elasticsearch()
        if not es_client:
            return JSONResponse(content={"error": "Could not connect to Elasticsearch"}, status_code=500)

        search_results = search_data(es_client, 'student-index')
        df = results_to_dataframe(search_results)

        # Log available columns for debugging
        logger.info(f"Available columns in dataframe: {df.columns.tolist()}")

        if filter_type and filter_value:
            filter_column = {
                'gender': 'Gender',
                'course': 'Course_Recommendation',
                'grade': 'Grade',
                'study_hours': 'Study_Hours'
            }.get(filter_type)

            if filter_column:
                if filter_column not in df.columns:
                    logger.error(f"Column '{filter_column}' not found in DataFrame.")
                    return JSONResponse(content={"error": f"Column '{filter_column}' not found."}, status_code=400)
                df = df[df[filter_column] == filter_value]

        if month:
            if 'Month' not in df.columns:
                logger.error("Column 'Month' not found in DataFrame.")
                return JSONResponse(content={"error": "Column 'Month' not found."}, status_code=400)
            df = df[df['Month'] == month]

        if subject:
            if 'Subjects' not in df.columns:
                logger.error("Column 'Subjects' not found in DataFrame.")
                return JSONResponse(content={"error": "Column 'Subjects' not found."}, status_code=400)
            df['Subject_Score'] = df['Subjects'].apply(lambda x: x.get(subject))
            df = df.dropna(subset=['Subject_Score'])

        # Format the Subjects column as a string
        df['Subjects'] = df['Subjects'].apply(lambda x: json.dumps(x))

        return JSONResponse(content={"filteredData": df.to_dict(orient="records")})
    except Exception as e:
        logger.error(f"Update Table error: {e}")
        return JSONResponse(content={"error": f"Error updating Table: {str(e)}"}, status_code=500)

@app.post("/update-visualization")
async def update_visualization(request: Request):
    try:
        data = await request.json()

        filter_type = data.get('filterType')
        filter_value = data.get('filterValue')
        month = data.get('month')
        subject = data.get('subject')
        x_axis = data.get('xAxis')
        y_axis = data.get('yAxis')
        graph_type = data.get('graphType')
        hue = data.get('hue')  # Add hue parameter

        if not all([x_axis, y_axis, graph_type]):
            return JSONResponse(content={"error": "Missing required parameters"}, status_code=400)

        es_client = connect_to_elasticsearch()
        if not es_client:
            return JSONResponse(content={"error": "Could not connect to Elasticsearch"}, status_code=500)

        search_results = search_data(es_client, 'student-index')
        df = results_to_dataframe(search_results)

        if filter_type and filter_value:
            filter_column = {
                'gender': 'Gender',
                'course': 'Course_Recommendation',
                'grade': 'Grade',
                'study_hours': 'Study_Hours'
            }.get(filter_type)
            if filter_column:
                df = df[df[filter_column] == filter_value]
        if month:
            df = df[df['Month'] == month]
        if subject:
            df['Subject_Score'] = df['Subjects'].apply(lambda x: x.get(subject))
            df = df.dropna(subset=['Subject_Score'])

        if y_axis in ['Math', 'Physics', 'Chemistry']:
            df[y_axis] = df['Subjects'].apply(lambda x: x.get(y_axis))
            y_axis_data = y_axis  # Use the subject name as the y-axis data
        else:
            y_axis_data = y_axis  # Use the original y-axis value

        # Generate a dynamic title for the graph
        title = f"{graph_type.capitalize()} Plot: {x_axis} vs {y_axis_data}"
        if filter_type and filter_value:
            title += f" (Filter: {filter_value})"
        if month:
            title += f" (Month: {month})"
        if subject:
            title += f" (Subject: {subject})"

        graph_html = create_visualization(df, x_axis, y_axis_data, graph_type, hue, title)  # Pass title parameter
        return JSONResponse({
            "filteredData": df.to_dict(orient="records"),
            "graphHtml": graph_html
        })
    except Exception as e:
        logger.error(f"Update visualization error: {e}")
        return JSONResponse(content={"error": f"Error updating visualization: {str(e)}"}, status_code=500)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return HTMLResponse(
        content="<h1>Internal Server Error</h1><p>An unexpected error occurred.</p>",
        status_code=500
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)