import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pydeck as pdk
import requests
from datetime import datetime
from supabase import create_client, Client
import cohere

# ============================
# API KEYS and CONFIGURATION
# ============================
API_KEYS = st.secrets.get("api_keys", {})
NEWS_API_KEY = API_KEYS.get("news_api_key", "YOUR_NEWS_API_KEY")

SUPABASE_CONFIG = st.secrets.get("supabase", {})
SUPABASE_URL = SUPABASE_CONFIG.get("url", "YOUR_SUPABASE_PROJECT_URL")
SUPABASE_ANON_KEY = SUPABASE_CONFIG.get("anon_key", "YOUR_SUPABASE_ANON_KEY")
SUPABASE_TABLE = SUPABASE_CONFIG.get("table_name", "feedback")

# Cohere API key
COHERE_API_KEY = st.secrets["COHERE_API_KEY"]
cohere_client = cohere.Client(COHERE_API_KEY)

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================
# API Integration Functions
# ============================

def get_coordinates(address):
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    response = requests.get(url, headers={'User -Agent': 'Mozilla/5.0'})
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return lat, lon
    return None, None

def get_route_info(origin_coords, destination_coords):
    start_lon, start_lat = origin_coords[1], origin_coords[0]
    end_lon, end_lat = destination_coords[1], destination_coords[0]
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=full&geometries=geojson"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data and 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            distance = route['distance'] / 1609.34  # convert meters to miles
            duration = route['duration'] / 3600.0   # convert seconds to hours
            geometry = route.get("geometry", {}).get("coordinates", [])
            return distance, duration, geometry
    return None, None, None

def get_carbon_estimate(distance, vehicle_type='car'):
    return distance * 0.411

def get_news_articles(query):
    if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_NEWS_API_KEY":
        return []
    url = (
        f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt"
        f"&apiKey={NEWS_API_KEY}&language=en&pageSize=5"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])
        return articles
    return []

def save_feedback_to_supabase(name, email, feedback):
    data = {
        "Name": name,
        "Email": email,
        "Feedback": feedback,
        "Timestamp": datetime.now().isoformat()
    }
    response = supabase.table(SUPABASE_TABLE).insert(data).execute()
    return response.data is not None

def generate_recommendations(user_goal):
    """Generate recommendations using Cohere API."""
    prompt = f"Based on the sustainability goal of '{user_goal}', provide tailored recommendations for reducing environmental impact in logistics."
    response = cohere_client.generate(
        model='command',
        prompt=prompt,
        max_tokens=15000,
        temperature=0.7,
        stop_sequences=["--"]
    )
    return response.generations[0].text.strip()

# ============================
# Page Configuration & Sidebar
# ============================
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide",
)

st.sidebar.title("Navigation")
pages = [
    "Overview", 
    "Personalized Recommendations", 
    "Educational Content",
    "Sustainability Metrics",
    "Route Optimization Simulator",
    "Real-Time News",
    "User  Feedback"
]
page = st.sidebar.radio("Go to", pages)

# Initialize session state for sustainability metrics
if 'sustainability_metrics' not in st.session_state:
    st.session_state.sustainability_metrics = {
        "Total Emissions Reduced (kg)": 0,
        "Fuel Savings (liters)": 0,
        "Cost Savings (USD)": 0,
        "Optimized Routes": 0
    }

# ============================
# Overview Page
# ============================
if page == "Overview":
    st.title("GreenRoute: Revolutionizing Sustainable Logistics")
    st.markdown("""
    **Welcome to GreenRoute!**

    Our platform leverages advanced AI, real-time data, and cutting-edge route optimization to help you make sustainable logistics decisions.
    Explore personalized recommendations, educational content, and an interactive route planner—all designed for today's logistics challenges.
    """)
    st.image("https://images.unsplash.com/photo-1504384308090-c894fdcc538d",
             caption="Sustainable Logistics in Action", use_column_width=True)
    st.markdown("### Use the sidebar to explore the features!")

# ============================
# Personalized Recommendations Page
# ============================
elif page == "Personalized Recommendations":
    st.title("Personalized Recommendations")
    st.markdown("""
    **Tailored Solutions for Your Sustainability Goals**

    Enter your sustainability focus (e.g., reducing fuel consumption, minimizing emissions) to get customized recommendations powered by our AI engine.
    """)
    user_goal = st.text_input("Enter your sustainability goal:")
    if st.button("Get Recommendation"):
        if user_goal.strip():
            recommendation = generate_recommendations(user_goal.strip())
            st.success(f"Based on your goal to **{user_goal.strip()}**, here are some recommendations:")
            st.write(recommendation)
        else:
            st.warning("Please enter a sustainability goal.")

# ============================
# Educational Content Page
# ============================
elif page == "Educational Content":
    st.title("Educational Content")
    st.markdown("""
    ### Dive into Sustainable Logistics

    **Sustainable Logistics:**  
    Embrace strategies that minimize environmental impact while optimizing your supply chain. Our resources cover renewable energy, electric vehicles, smart routing, and more.

    **Emissions Management:**  
    Understand best practices for tracking and reducing emissions through advanced data analytics and cleaner technologies.

    **Our Approach:**  
    - **Personalized Insights:** Custom recommendations to match your goals.
    - **Real-Time Data:** Stay ahead with live news and analytics.
    - **Interactive Tools:** Engage with dynamic simulations and educational resources.
    """)
    st.info("Empower your logistics operations with knowledge and innovation.")

# ============================
# Sustainability Metrics Page
# ============================
elif page == "Sustainability Metrics":
    st.title("Sustainability Metrics")
    st.markdown("### Comprehensive Metrics Dashboard")
    metrics = st.session_state.sustainability_metrics
    st.subheader("Key Performance Indicators")
    st.write(metrics)
    df_metrics = pd.DataFrame({
        "Metric": list(metrics.keys()),
        "Value": list(metrics.values())
    })
    chart = alt.Chart(df_metrics).mark_bar().encode(
        x=alt.X("Metric:N", sort=None),
        y=alt.Y("Value:Q", title="Value"),
        color=alt.Color("Metric:N")
    ).properties(width=700, height=400)
    st.altair_chart(chart, use_container_width=True)
    st.info("Monitor these metrics to evaluate your sustainability performance.")

# ============================
# Route Optimization Simulator Page
# ============================
elif page == "Route Optimization Simulator":
    st.title("Route Optimization Simulator")
    st.markdown("""
    **Simulate Your Route and Visualize the Optimal Path**

    Enter your origin and destination below to calculate the best route. Our system retrieves the full route geometry, estimates travel details, and displays the path interactively.
    """)
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Enter Origin", "New York, NY")
    with col2:
        destination = st.text_input("Enter Destination", "Los Angeles, CA")
    
    if st.button("Simulate Route"):
        if origin and destination:
            origin_coords = get_coordinates(origin)
            destination_coords = get_coordinates(destination)
            if None in origin_coords or None in destination_coords:
                st.error("Could not geocode the provided addresses. Please try different inputs.")
            else:
                result = get_route_info(origin_coords, destination_coords)
                if result[0] is not None:
                    distance, duration, geometry = result
                    emissions = get_carbon_estimate(distance)
                    
                    # Update sustainability metrics in session state
                    st.session_state.sustainability_metrics["Total Emissions Reduced (kg)"] += emissions
                    st.session_state.sustainability_metrics["Optimized Routes"] += 1
                    
                    st.success(f"Optimized route from **{origin}** to **{destination}**:")
                    st.write(f"**Estimated Distance:** {distance:.2f} miles")
                    st.write(f"**Estimated Travel Time:** {duration:.2f} hours")
                    st.write(f"**Estimated CO₂ Emissions:** {emissions:.2f} kg")
                    
                    if geometry:
                        lats = [coord[1] for coord in geometry]
                        lons = [coord[0] for coord in geometry]
                        avg_lat = sum(lats) / len(lats)
                        avg_lon = sum(lons) / len(lons)
                        
                        route_layer = pdk.Layer(
                            "PathLayer",
                            data=[{"path": geometry, "name": "Route"}],
                            get_path="path",
                            get_color="[255, 0, 0, 255]",
                            width_scale=20,
                            width_min_pixels=2,
                            get_width=5,
                        )
                        view_state = pdk.ViewState(
                            latitude=avg_lat,
                            longitude=avg_lon,
                            zoom=6,
                            pitch=0,
                        )
                        deck = pdk.Deck(
                            layers=[route_layer],
                            initial_view_state=view_state,
                            tooltip={"text": "{name}"}
                        )
                        st.pydeck_chart(deck)
                    else:
                        st.error("Route geometry not available.")
                else:
                    st.error("Could not retrieve route information. Please try again later.")
        else:
            st.warning("Please enter both origin and destination.")

# ============================
# Real-Time News Page
# ============================
elif page == "Real-Time News":
    st.title("Real-Time News")
    st.markdown("""
    **Stay Updated with the Latest in Sustainable Logistics**

    We fetch live news articles using NewsAPI to keep you informed about trends and innovations in the logistics industry.
    """)
    query = "sustainable logistics"
    articles = get_news_articles(query)
    if articles:
        for article in articles:
            st.subheader(article.get("title", "No Title"))
            st.write(article.get("description", "No Description"))
            st.markdown(f"[Read more]({article.get('url', '#')})")
            st.markdown("---")
    else:
        st.info("No real-time news available. Please ensure you have set your News API key correctly.")

# ============================
# User Feedback Page
# ============================
elif page == "User  Feedback":
    st.title("User  Feedback")
    st.markdown("""
    **We Value Your Input**

    Please share your feedback or suggestions to help us improve GreenRoute.
    """)
    with st.form("feedback_form"):
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")
        feedback = st.text_area("Your Feedback", "Enter your feedback here...")
        submitted = st.form_submit_button("Submit Feedback")
        if submitted:
            if name and email and feedback:
                success = save_feedback_to_supabase(name, email, feedback)
                if success:
                    st.success("Thank you for your feedback! It has been successfully saved.")
                else:
                    st.error("There was an error saving your feedback. Please try again later.")
            else:
                st.warning("Please fill in all fields before submitting.")
