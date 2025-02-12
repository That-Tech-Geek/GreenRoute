import streamlit as st
st.set_page_config(
    page_title="GreenRoute - Sustainable Logistics Dashboard",
    page_icon="🌱",
    layout="wide"
)

import pandas as pd
import numpy as np
import altair as alt
import folium
import requests
import sqlite3
from datetime import datetime
from supabase import create_client, Client
import cohere  # For generating advice
from streamlit_folium import folium_static

# ============================
# API KEYS and CONFIGURATION
# ============================
NEWS_API_KEY = st.secrets["NEWS-API"]["NEWS_API"]
COHERE_API_KEY = st.secrets["COHERE_API_KEY"]

SUPABASE_CONFIG = st.secrets.get("supabase", {})
SUPABASE_URL = SUPABASE_CONFIG.get("url")
SUPABASE_ANON_KEY = SUPABASE_CONFIG.get("anon_key")
SUPABASE_TABLE = SUPABASE_CONFIG.get("table_name")

# Initialize Supabase Client (used for feedback)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================
# SQLite Database Setup for Sustainability Metrics
# ============================
def init_db():
    conn = sqlite3.connect("metrics.db", check_same_thread=False)
    c = conn.cursor()
    # Create table if it doesn't exist (fuel savings removed)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sustainability_metrics (
            id INTEGER PRIMARY KEY,
            total_distance REAL,
            total_emissions_saved REAL
        )
    """)
    # Check if the table has at least one row; if not, insert initial values.
    c.execute("SELECT * FROM sustainability_metrics LIMIT 1")
    if c.fetchone() is None:
        c.execute("INSERT INTO sustainability_metrics (total_distance, total_emissions_saved) VALUES (?, ?)",
                  (0.0, 0.0))
        conn.commit()
    conn.close()

init_db()

@st.cache_data
def get_metrics_from_db():
    """Retrieve sustainability metrics from SQLite and return as a dict."""
    conn = sqlite3.connect("metrics.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT total_distance, total_emissions_saved FROM sustainability_metrics LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return {"total_distance": 0.0, "total_emissions_saved": 0.0}
    return {"total_distance": row[0], "total_emissions_saved": row[1]}

def update_metrics_in_db(new_distance: float, new_emissions: float):
    """
    Update the sustainability metrics in the SQLite DB.
    new_distance: distance in kilometers
    new_emissions: emissions saved in kg CO₂
    """
    conn = sqlite3.connect("metrics.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT total_distance, total_emissions_saved FROM sustainability_metrics LIMIT 1")
    row = c.fetchone()
    if row is None:
        current_distance, current_emissions = 0.0, 0.0
    else:
        current_distance, current_emissions = row
    new_total_distance = current_distance + new_distance
    new_total_emissions = current_emissions + new_emissions
    c.execute("UPDATE sustainability_metrics SET total_distance = ?, total_emissions_saved = ? WHERE id = 1", 
              (new_total_distance, new_total_emissions))
    conn.commit()
    conn.close()
    get_metrics_from_db.clear()  # Clear cache so updated values are returned

def get_sustainability_metrics():
    """Return the current sustainability metrics from SQLite."""
    return get_metrics_from_db()

# ============================
# Cohere Advice Function
# ============================
def get_cohere_advice(goal: str) -> str:
    """
    Generate actionable sustainability advice using Cohere API based on the user's sustainability goal.
    If an error occurs, display an error message and return a default string.
    """
    try:
        co = cohere.Client(COHERE_API_KEY)
        prompt = f"Provide practical, actionable advice on how to improve sustainability and reduce emissions with a focus on {goal}."
        response = co.generate(
             model="command-xlarge-nightly",
             prompt=prompt,
             max_tokens=6000,
             temperature=0.7,
             k=0,
             p=0.75,
             frequency_penalty=0,
             presence_penalty=0,
             stop_sequences=["--"]
        )
        advice = response.generations[0].text.strip()
        return advice
    except Exception as e:
        st.error("Error generating advice. Please check your Cohere API key. " + str(e))
        return "No advice available at this time."

# ============================
# API Integration Functions
# ============================
def get_coordinates(address):
    """Geocode an address using the free Nominatim API."""
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return lat, lon
    return None, None

def get_route_info(origin_coords, destination_coords):
    """
    Retrieve route info using OSRM API.
    Returns distance (in miles), duration (in hours), and route geometry as a GeoJSON LineString.
    """
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
        if data and "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]
            distance = route["distance"] / 1609.34  # convert meters to miles
            duration = route["duration"] / 3600.0     # convert seconds to hours
            geometry = route.get("geometry", {}).get("coordinates", [])
            if not geometry or len(geometry) < 2:
                geometry = [[start_lon, start_lat], [end_lon, end_lat]]
            return distance, duration, geometry
    return None, None, None

def get_carbon_estimate(distance, vehicle_type='car'):
    """
    Estimate CO₂ emissions for a given distance (in miles).
    Example: a typical car emits ~0.411 kg CO₂ per mile.
    """
    return distance * 0.411

def get_news_articles(query):
    """Fetch news articles using NewsAPI."""
    if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_NEWS_API_KEY":
        return []  # No API key provided
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
    """Save user feedback to Supabase."""
    data = {
        "Name": name,
        "Email": email,
        "Feedback": feedback,
        "Timestamp": datetime.now().isoformat()
    }
    response = supabase.table(SUPABASE_TABLE).insert(data).execute()
    return response.data is not None

# ============================
# Page Configuration & Sidebar
# ============================
st.sidebar.title("Navigation")
pages = [
    "Overview", 
    "Personalized Recommendations", 
    "Educational Content",
    "Sustainability Metrics",
    "Route Optimization Simulator",
    "Real-Time News",
    "User Feedback",
    "Sceptical?"
]
page = st.sidebar.radio("Go to", pages)

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
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get Recommendation"):
            if user_goal.strip():
                st.success(f"Based on your goal to **{user_goal.strip()}**, explore our tools designed to optimize operations and reduce environmental impact.")
            else:
                st.warning("Please enter a sustainability goal.")
    with col2:
        if st.button("Get Advice"):
            if user_goal.strip():
                advice = get_cohere_advice(user_goal.strip())
                st.markdown("### Advice:")
                st.info(advice)
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
    st.markdown("### Overall Impact of GreenRoute")
    
    metrics = get_sustainability_metrics()
    total_distance = metrics.get("total_distance", 0.0)
    total_emissions_saved = metrics.get("total_emissions_saved", 0.0)
    
    avg_emissions_saved = total_emissions_saved / total_distance if total_distance else 0

    st.write(f"**Total Kilometers Simulated:** {total_distance:.2f} km")
    st.write(f"**Total CO₂ Emissions Saved:** {total_emissions_saved:.2f} kg")
    st.write(f"**Average Emissions Saved per Kilometer:** {avg_emissions_saved:.2f} kg/km")
    
    metrics_df = pd.DataFrame({
        "Metric": [
            "Total Kilometers Simulated",
            "Total Emissions Saved (kg)",
            "Avg Emissions per km (kg/km)"
        ],
        "Value": [
            total_distance,
            total_emissions_saved,
            avg_emissions_saved
        ]
    })
    chart = alt.Chart(metrics_df).mark_bar().encode(
        x=alt.X("Metric:N", sort=None),
        y=alt.Y("Value:Q"),
        color=alt.Color("Metric:N")
    ).properties(width=700, height=400)
    st.altair_chart(chart, use_container_width=True)
    
    st.info("GreenRoute has been instrumental in reducing emissions through optimized routing.")

# ============================
# Route Optimization Simulator Page
# ============================
elif page == "Route Optimization Simulator":
    st.title("Route Optimization Simulator")
    st.markdown("""
    **Simulate Your Route and Visualize the Optimal Path**

    Enter your origin and destination below to calculate the best route. Our system retrieves the route geometry via the OSRM API and displays it on an interactive map.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Enter Origin", "New York, NY")
    with col2:
        destination = st.text_input("Enter Destination", "Los Angeles, CA")
    
    if st.button("Simulate Route"):
        if origin and destination:
            origin_coords = get_coordinates(origin)  # (lat, lon)
            destination_coords = get_coordinates(destination)  # (lat, lon)
            if None in origin_coords or None in destination_coords:
                st.error("Could not geocode the provided addresses. Please try different inputs.")
            else:
                result = get_route_info(origin_coords, destination_coords)
                if result[0] is not None:
                    distance, duration, geometry = result
                    emissions_estimated = get_carbon_estimate(distance)
                    st.success(f"Optimized route from **{origin}** to **{destination}**:")
                    st.write(f"**Estimated Distance:** {distance:.2f} miles")
                    st.write(f"**Estimated Travel Time:** {duration:.2f} hours")
                    st.write(f"**Estimated CO₂ Emissions Saved:** {emissions_estimated:.2f} kg")
                    
                    # Convert distance from miles to kilometers and update metrics in SQLite
                    km_distance = distance * 1.60934
                    update_metrics_in_db(new_distance=km_distance, new_emissions=emissions_estimated)
                    
                    if not geometry or len(geometry) < 2:
                        geometry = [[origin_coords[1], origin_coords[0]], [destination_coords[1], destination_coords[0]]]
                    
                    # Convert OSRM geometry ([lon, lat]) to Folium format ([lat, lon])
                    folium_geometry = [[pt[1], pt[0]] for pt in geometry]
                    
                    center_lat = sum(pt[0] for pt in folium_geometry) / len(folium_geometry)
                    center_lon = sum(pt[1] for pt in folium_geometry) / len(folium_geometry)
                    
                    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
                    folium.PolyLine(locations=folium_geometry, color="red", weight=5).add_to(m)
                    folium.Marker(location=[origin_coords[0], origin_coords[1]], popup="Origin").add_to(m)
                    folium.Marker(location=[destination_coords[0], destination_coords[1]], popup="Destination").add_to(m)
                    
                    folium_static(m, width=700, height=500)
                    
                    # Display updated sustainability metrics immediately
                    metrics = get_sustainability_metrics()
                    st.markdown("### Updated Sustainability Impact")
                    st.write(f"**Total Kilometers Simulated:** {metrics.get('total_distance', 0.0):.2f} km")
                    st.write(f"**Total CO₂ Emissions Saved:** {metrics.get('total_emissions_saved', 0.0):.2f} kg")
                    st.info("For a more detailed view, please check the 'Sustainability Metrics' page in the sidebar.")
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
elif page == "User Feedback":
    st.title("User Feedback")
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
elif page == "Sceptical?":
    st.title("How this program works")
    text = (
        "The code calculates and updates its sustainability metrics by storing and aggregating values in a local SQLite database. "
        "Initially, a table named sustainability_metrics is created (if it does not already exist) with two columns: total_distance and total_emissions_saved. "
        "When the database is initialized, a single row with zeros is inserted if no data exists. Whenever the dashboard needs to display metrics, the function that retrieves data from the database (get_metrics_from_db) is called. "
        "This function connects to the SQLite database, reads the current values for total_distance and total_emissions_saved, and returns these in a dictionary. To improve performance, the result is cached; however, the cache is cleared after any update so that new values are immediately visible. "
        "When a user simulates a route using the Route Optimization Simulator page, the code first calls an external API (OSRM) to obtain route information. This API returns the route’s distance (in miles), duration (in hours), and the route geometry. "
        "The distance is then used in two calculations. First, it is converted from miles to kilometers (by multiplying by 1.60934) so that it matches the unit used in the database. "
        "Second, the function get_carbon_estimate estimates the CO₂ emissions saved by multiplying the distance in miles by a constant factor (0.411 kg CO₂ per mile). "
        "The update_metrics_in_db function reads the current metric values from the database and then updates them by adding the new route’s data. "
        "The new total distance becomes the previous distance plus the newly simulated distance (in kilometers), and the new total emissions saved is the previous value plus the estimated CO₂ saved from the current route. "
        "After updating, the new values are written back to the database and the cache is cleared to ensure that the updated metrics are displayed. "
        "On the Sustainability Metrics page, the dashboard displays the cumulative total kilometers simulated and total CO₂ emissions saved. "
        "These values are then visualized using a bar chart generated with Altair."
    )
    st.write(text)
